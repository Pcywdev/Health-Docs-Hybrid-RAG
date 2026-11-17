"""History page: citation-quality dashboard over the questions logged by /query.

Eval runs are not here: the eval runner bypasses /query, so this shows real traffic only.
"""

from typing import Any

import streamlit as st

import api_client
from formatting import history_rows, percent
from theme import APP_NAME, apply_style, page_header

st.set_page_config(page_title=f"History · {APP_NAME}", layout="wide")
apply_style()

WINDOWS: dict[str, int | None] = {"Last 7 days": 7, "Last 30 days": 30, "All time": None}
ROWS_PER_TABLE = 20

COLUMNS = {
    "Asked": st.column_config.DatetimeColumn(format="D MMM, HH:mm", width="medium"),
    "Question": st.column_config.TextColumn(width="medium"),
    "Answer": st.column_config.TextColumn("Answer (preview)", width="large"),
    "Citations": st.column_config.TextColumn(width="small"),
    "Accuracy": st.column_config.ProgressColumn(
        "Accuracy", format="percent", min_value=0.0, max_value=1.0, width="small",
        help="Share of the answer's citations that point at a retrieved passage.",
    ),
    "Retrieved": st.column_config.NumberColumn("Passages", width="small"),
}


def show_metrics(stats: dict[str, Any]) -> None:
    """Headline numbers for the selected window."""
    questions, accuracy, refusals, fabrication = st.columns(4, border=True)
    questions.metric("Questions", stats["total_queries"])
    accuracy.metric(
        "Citation accuracy",
        percent(stats["mean_citation_accuracy_cited"]),
        help="Mean over answers that cited something. Refusals are left out, "
        "since they score 0 by definition.",
    )
    refusals.metric(
        "Refusal rate",
        percent(stats["refusal_rate"]),
        help="Answers that cited nothing, usually because the guidelines don't cover the question.",
    )
    fabrication.metric(
        "Answers with bad citations",
        stats["queries_with_fabrication"],
        help="Answers citing a source number outside the passages they were given.",
    )


def show_table(items: list[dict[str, Any]]) -> None:
    """One read-only table of logged questions."""
    st.dataframe(history_rows(items), column_config=COLUMNS, hide_index=True, width="stretch")


page_header(
    "Answer quality",
    "How well answers to real questions cite their sources. Evaluation runs are not included.",
)

window = st.segmented_control("Window", list(WINDOWS), default="Last 30 days", key="window")

try:
    history = api_client.get_history(days=WINDOWS[window or "All time"], limit=ROWS_PER_TABLE)
except api_client.ApiError as error:
    st.error(str(error), icon=":material/error:")
    st.stop()

if not history["stats"]["total_queries"]:
    st.info("No questions logged in this window yet. Ask one on the Home page.", icon=":material/info:")
    st.stop()

show_metrics(history["stats"])

st.subheader("Recent questions")
show_table(history["recent"])

st.subheader("Answers with citations outside the retrieved passages")
if history["fabricated"]:
    show_table(history["fabricated"])
else:
    st.caption(":primary[:material/check_circle:] None in this window.")
