"""Offline tests for frontend/formatting.py."""

from datetime import UTC, datetime

import pytest

from formatting import (
    citation_numbers,
    citation_summary,
    document_title,
    escape_markdown,
    history_rows,
    percent,
    render_answer,
)


@pytest.mark.parametrize(
    ("citation", "expected"),
    [
        ("[Source 1]", [1]),
        ("[Source 1, 3]", [1, 3]),
        ("[Source 2-4]", [2, 3, 4]),
        ("[Source 2–4]", [2, 3, 4]),  # en dash
        ("[Source 3-1]", [1, 2, 3]),  # reversed range
        ("[Source 1, 1]", [1]),
    ],
)
def test_citation_numbers_matches_backend_rules(citation: str, expected: list[int]) -> None:
    assert citation_numbers(citation) == expected


def test_citation_numbers_caps_huge_ranges() -> None:
    assert len(citation_numbers("[Source 1-100000]")) == 50


def test_render_answer_badges_valid_and_flags_out_of_range() -> None:
    rendered = render_answer("Walk more [Source 1] and rest [Source 1, 9].", valid={1})

    assert rendered == "Walk more :primary-badge[1] and rest :primary-badge[1] :orange-badge[9?]."


def test_render_answer_escapes_dollar_signs() -> None:
    assert render_answer("Costs $5 [Source 2]", valid={2}) == r"Costs \$5 :primary-badge[2]"


def test_escape_markdown_neutralises_syntax_and_line_breaks() -> None:
    escaped = escape_markdown("# Table 1\n*150* min :red[x]")

    assert "\n" not in escaped
    assert escaped == r"\# Table 1 \*150\* min \:red\[x\]"


def report(total: int, valid: int, has_citation: bool = True) -> dict:
    return {
        "total_citations": total,
        "valid_citations": valid,
        "fabricated_citations": total - valid,
        "citation_accuracy": valid / total if total else 0.0,
        "has_citation": has_citation,
    }


def test_citation_summary_for_a_refusal() -> None:
    assert "No sources cited" in citation_summary(report(0, 0, has_citation=False))


def test_citation_summary_flags_fabrication() -> None:
    assert "1 of 3 citations don't match" in citation_summary(report(3, 2))


def test_citation_summary_when_all_citations_resolve() -> None:
    assert "All 3 citations point to a retrieved passage" in citation_summary(report(3, 3))
    assert "The citation points" in citation_summary(report(1, 1))


def test_document_title_uses_mapping_then_filename() -> None:
    assert document_title("9789240015128-eng.pdf").startswith("WHO guidelines")
    assert document_title("unknown.pdf") == "unknown.pdf"


def history_item(**overrides) -> dict:
    item = {
        "id": 1,
        "question": "How much activity?",
        "answer_preview": "150-300 minutes [Source 1]",
        "created_at": "2026-11-17T09:30:00+00:00",
        "num_sources": 5,
        "total_citations": 2,
        "valid_citations": 2,
        "fabricated_citations": 0,
        "citation_accuracy": 1.0,
        "has_citations": True,
    }
    return item | overrides


def test_percent_formats_fractions_and_missing_data() -> None:
    assert percent(0.256) == "26%"
    assert percent(None) == "–"


def test_history_rows_for_a_cited_answer() -> None:
    (row,) = history_rows([history_item()])

    assert row["Asked"] == datetime(2026, 11, 17, 9, 30, tzinfo=UTC)
    assert row["Citations"] == "2 of 2 resolve"
    assert row["Accuracy"] == 1.0


def test_history_rows_for_a_refusal_has_no_accuracy() -> None:
    (row,) = history_rows(
        [history_item(total_citations=0, valid_citations=0, citation_accuracy=0.0, has_citations=False)]
    )

    assert row["Citations"] == "None (refusal)"
    assert row["Accuracy"] is None
