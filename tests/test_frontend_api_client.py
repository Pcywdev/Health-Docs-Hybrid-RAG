"""Offline tests for frontend/api_client.py, using a mocked HTTP transport."""

import httpx
import pytest

import api_client

ANSWER = {
    "answer": "Adults should do 150-300 minutes [Source 1].",
    "sources": [{"index": 1, "source": "who.pdf", "page": 18, "text": "..."}],
    "citation_report": {
        "total_citations": 1,
        "valid_citations": 1,
        "fabricated_citations": 0,
        "citation_accuracy": 1.0,
        "has_citation": True,
    },
}


def client_returning(handler) -> httpx.Client:
    """An httpx client whose every request is answered by ``handler``."""
    return httpx.Client(base_url="http://test", transport=httpx.MockTransport(handler))


def test_ask_posts_question_and_returns_body() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = request.read()
        return httpx.Response(200, json=ANSWER)

    result = api_client.ask("How much activity?", top_k=3, client=client_returning(handler))

    assert result == ANSWER
    assert seen["path"] == "/query"
    assert b'"top_k":3' in seen["body"].replace(b" ", b"")


@pytest.mark.parametrize("status", [422, 502, 503])
def test_ask_maps_known_errors_to_friendly_messages(status: int) -> None:
    client = client_returning(lambda request: httpx.Response(status, json={"detail": "x"}))

    with pytest.raises(api_client.ApiError) as error:
        api_client.ask("q", client=client)

    assert str(error.value) == api_client.QUERY_ERRORS[status]


def test_ask_reports_unknown_status_code() -> None:
    client = client_returning(lambda request: httpx.Response(500))

    with pytest.raises(api_client.ApiError, match="500"):
        api_client.ask("q", client=client)


def test_ask_explains_when_api_is_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(api_client.ApiError, match="Can't reach the API"):
        api_client.ask("q", client=client_returning(handler))


def test_ask_explains_a_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(api_client.ApiError, match="longer than"):
        api_client.ask("q", client=client_returning(handler))


def test_health_true_when_api_answers() -> None:
    assert api_client.health(client_returning(lambda request: httpx.Response(200)))


def test_health_false_when_api_is_down() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    assert not api_client.health(client_returning(handler))


def test_get_history_sends_window_and_limit() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"stats": {}, "recent": [], "fabricated": []})

    api_client.get_history(days=7, limit=20, client=client_returning(handler))
    assert seen["params"] == {"days": "7", "limit": "20"}

    api_client.get_history(days=None, client=client_returning(handler))
    assert "days" not in seen["params"]


def test_get_history_explains_a_database_outage() -> None:
    client = client_returning(lambda request: httpx.Response(503))

    with pytest.raises(api_client.ApiError, match="history database"):
        api_client.get_history(client=client)
