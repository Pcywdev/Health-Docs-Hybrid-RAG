"""Offline smoke tests for the Streamlit pages, with the API client stubbed."""

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import api_client

HOME = str(Path(__file__).resolve().parent.parent / "frontend" / "Home.py")

RESPONSE = {
    "answer": "Adults should do 150-300 minutes [Source 1].",
    "sources": [
        {"index": 1, "source": "9789240015128-eng.pdf", "page": 18, "text": "150 to 300 minutes"}
    ],
    "citation_report": {
        "total_citations": 1,
        "valid_citations": 1,
        "fabricated_citations": 0,
        "citation_accuracy": 1.0,
        "has_citation": True,
    },
}


@pytest.fixture(autouse=True)
def api_up(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend the API is reachable, and drop the cached health check between tests."""
    st.cache_data.clear()
    monkeypatch.setattr(api_client, "health", lambda: True)


def find_container(node, key: str):
    """The container created with ``key=key``; Streamlit ends its block id with the key."""
    if str(getattr(getattr(node, "proto", None), "id", "")).endswith(f"-{key}"):
        return node
    for child in getattr(node, "children", {}).values():
        if (found := find_container(child, key)) is not None:
            return found
    return None


def ask_question(question: str) -> AppTest:
    """Run the Ask page and submit one question."""
    app = AppTest.from_file(HOME).run()
    app.chat_input[0].set_value(question).run()
    return app


def test_home_renders_answer_badges_and_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_client, "ask", lambda question, top_k=5: RESPONSE)

    app = ask_question("How much activity?")

    assert not app.exception
    markdown = " ".join(block.value for block in app.markdown)
    assert ":primary-badge[1]" in markdown
    assert app.expander[0].label == "Sources (1)"
    assert any("retrieved passage" in caption.value for caption in app.caption)


def test_home_shows_api_errors_instead_of_crashing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(question: str, top_k: int = 5) -> dict:
        raise api_client.ApiError("Can't reach the API")

    monkeypatch.setattr(api_client, "ask", fail)

    app = ask_question("How much activity?")

    assert not app.exception
    assert app.error[0].value == "Can't reach the API"


def test_empty_chat_shows_examples_and_a_click_asks_one(monkeypatch: pytest.MonkeyPatch) -> None:
    asked = []
    monkeypatch.setattr(
        api_client, "ask", lambda question, top_k=5: asked.append(question) or RESPONSE
    )

    app = AppTest.from_file(HOME).run()
    example = app.button(key="example_0")
    example.click().run()

    assert asked == [example.label]
    assert not [button for button in app.button if button.key == "example_0"]


def test_slider_value_is_sent_as_top_k(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = {}
    monkeypatch.setattr(
        api_client, "ask", lambda question, top_k=5: seen.update(top_k=top_k) or RESPONSE
    )

    app = AppTest.from_file(HOME).run()
    app.slider(key="top_k").set_value(8).run()
    app.chat_input[0].set_value("q").run()

    assert seen["top_k"] == 8


def test_clear_chat_returns_to_the_empty_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_client, "ask", lambda question, top_k=5: RESPONSE)

    app = ask_question("How much activity?")
    clear = next(button for button in app.button if button.label == "Clear chat")
    assert not clear.disabled
    clear.click().run()

    assert app.session_state.messages == []
    assert app.button(key="example_0")


def test_sidebar_reports_an_unreachable_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_client, "health", lambda: False)

    app = AppTest.from_file(HOME).run()

    assert any("API unreachable" in block.value for block in app.sidebar.markdown)


HISTORY = str(Path(HOME).parent / "pages" / "1_History.py")

ITEM = {
    "id": 1,
    "question": "How much activity?",
    "answer_preview": "150-300 minutes [Source 1]",
    "created_at": "2026-11-17T09:30:00+00:00",
    "num_sources": 5,
    "total_citations": 1,
    "valid_citations": 1,
    "fabricated_citations": 0,
    "citation_accuracy": 1.0,
    "has_citations": True,
}


def history_with(total: int, fabricated: list | None = None) -> dict:
    return {
        "stats": {
            "total_queries": total,
            "mean_citation_accuracy_cited": 1.0 if total else None,
            "mean_citation_accuracy_all": 0.5 if total else None,
            "answers_with_citations": total,
            "refusals": 0,
            "refusal_rate": 0.25 if total else None,
            "queries_with_fabrication": len(fabricated or []),
            "total_fabricated_citations": 0,
            "avg_sources_retrieved": 5.0 if total else None,
            "window_days": 30,
        },
        "recent": [ITEM] if total else [],
        "fabricated": fabricated or [],
    }


def test_history_shows_metrics_and_recent_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_client, "get_history", lambda days=None, limit=20: history_with(4))

    app = AppTest.from_file(HISTORY).run()

    assert not app.exception
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Questions"] == "4"
    assert metrics["Refusal rate"] == "25%"
    assert len(app.dataframe) == 1  # no fabricating answers -> no second table
    assert any("None in this window" in caption.value for caption in app.caption)


def test_history_window_filter_sets_days(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    monkeypatch.setattr(
        api_client, "get_history", lambda days=None, limit=20: calls.append(days) or history_with(1)
    )

    app = AppTest.from_file(HISTORY).run()
    app.button_group(key="window").set_value("All time").run()

    assert calls == [30, None]


def test_history_empty_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_client, "get_history", lambda days=None, limit=20: history_with(0))

    app = AppTest.from_file(HISTORY).run()

    assert "No questions logged" in app.info[0].value
    assert not app.metric


def test_history_reports_a_database_outage(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(days=None, limit=20) -> dict:
        raise api_client.ApiError("The history database is unavailable.")

    monkeypatch.setattr(api_client, "get_history", fail)

    app = AppTest.from_file(HISTORY).run()

    assert not app.exception
    assert app.error[0].value == "The history database is unavailable."


@pytest.mark.parametrize("page", [HOME, HISTORY])
def test_pages_apply_the_shared_style_and_header(
    page: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api_client, "get_history", lambda days=None, limit=20: history_with(0))

    app = AppTest.from_file(page).run()

    assert not app.exception
    assert any(".st-key-hero" in block.proto.body for block in app.get("html"))
    assert app.title[0].value in {"Health Docs Hybrid RAG", "Answer quality"}


def test_question_is_drawn_in_its_keyed_card(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_client, "ask", lambda question, top_k=5: RESPONSE)

    app = ask_question("How much activity?")

    card = find_container(app._tree, "user_q_0")
    assert card is not None
    assert card.markdown[0].value == "How much activity?"


def test_sidebar_badge_when_api_is_up() -> None:
    app = AppTest.from_file(HOME).run()

    assert any("API connected" in block.value for block in app.sidebar.markdown)


def test_stylesheet_has_no_tag_like_text() -> None:
    """DOMPurify drops the whole style tag if its text contains a less-than sign."""
    stylesheet = Path(HOME).with_name("style.css").read_text(encoding="utf-8")

    assert "<" not in stylesheet
