"""HTTP client for the Ask My Health Docs API.

No Streamlit imports, so it can be unit-tested with a mocked transport.
Every failure surfaces as ``ApiError`` carrying a message that is safe to show.
"""

from typing import Any

import httpx

from ui_settings import ui_settings


class ApiError(Exception):
    """A request failed; ``str(error)`` is a user-facing explanation."""


# What each /query failure means to someone using the UI
QUERY_ERRORS: dict[int, str] = {
    422: "That question couldn't be processed. Keep it between 1 and 2,000 characters.",
    502: "The language-model service didn't respond. Try again in a moment.",
    503: "The document index isn't built yet. Run the ingest step on the API first.",
}

HISTORY_ERRORS: dict[int, str] = {
    422: "That history filter isn't valid.",
    503: "The history database is unavailable. Check that Postgres is running.",
}


def _client() -> httpx.Client:
    """A client pointed at the configured API."""
    return httpx.Client(base_url=ui_settings.api_url, timeout=ui_settings.request_timeout_s)


def _request(
    client: httpx.Client,
    method: str,
    path: str,
    errors: dict[int, str],
    **kwargs: Any,
) -> dict[str, Any]:
    """Send a request and return the JSON body, or raise ``ApiError``."""
    try:
        response = client.request(method, path, **kwargs)
    except httpx.ConnectError:
        raise ApiError(
            f"Can't reach the API at {ui_settings.api_url}. Is `uvicorn app.main:app` running?"
        )
    except httpx.TimeoutException:
        raise ApiError(
            f"The API took longer than {ui_settings.request_timeout_s:.0f}s to respond."
        )
    except httpx.HTTPError:
        raise ApiError("The request to the API failed. Try again in a moment.")

    if response.is_success:
        return response.json()
    raise ApiError(errors.get(response.status_code, f"The API returned an error ({response.status_code})."))


def ask(question: str, top_k: int = 5, client: httpx.Client | None = None) -> dict[str, Any]:
    """POST /query: the answer, its cited sources and the citation report."""
    with client or _client() as http:
        return _request(
            http, "POST", "/query", QUERY_ERRORS, json={"question": question, "top_k": top_k}
        )


def get_history(
    days: int | None = None, limit: int = 20, client: httpx.Client | None = None
) -> dict[str, Any]:
    """GET /history: citation-quality stats plus recent and fabricating queries."""
    params: dict[str, int] = {"limit": limit}
    if days is not None:
        params["days"] = days
    with client or _client() as http:
        return _request(http, "GET", "/history", HISTORY_ERRORS, params=params)


def health(client: httpx.Client | None = None) -> bool:
    """GET /health: True when the API answers, False on any failure."""
    try:
        with client or httpx.Client(base_url=ui_settings.api_url, timeout=2.0) as http:
            return http.get("/health").is_success
    except httpx.HTTPError:
        return False
