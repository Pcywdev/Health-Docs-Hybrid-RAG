"""Ask page: the Streamlit entry point (run `streamlit run frontend/Home.py` from the repo root).

Streamlit reruns this whole script on every interaction, so the conversation
lives in ``st.session_state`` and is redrawn from it each time. Each question
is sent to /query on its own: earlier turns are shown, not sent.
"""

from typing import Any

import streamlit as st

import api_client
from formatting import (
    citation_summary,
    document_title,
    escape_markdown,
    load_content,
    render_answer,
)
from theme import APP_NAME, apply_style, page_header
from ui_settings import ui_settings

st.set_page_config(page_title=APP_NAME, layout="centered")
apply_style()

MAX_QUESTION_CHARS = 2000  # matches QueryRequest.question in app/main.py
AVATARS = {"user": ":material/person:", "assistant": ":material/menu_book:"}


@st.cache_data(ttl=10, show_spinner=False)
def api_is_up() -> bool:
    """Cached health check, so every rerun doesn't ping the API."""
    return api_client.health()


def ask_example(question: str) -> None:
    """Button callback: queue an example question for this rerun to answer."""
    st.session_state.pending_question = question


def clear_chat() -> None:
    """Button callback: forget the conversation."""
    st.session_state.messages = []


def show_sidebar(has_chat: bool) -> None:
    """API status, retrieval setting, and a short explanation of the pipeline."""
    with st.sidebar:
        # Badges, not coloured dots: a badge carries its own background, so it stays readable on any sidebar colour
        if api_is_up():
            st.markdown(":primary-badge[:material/check_circle: API connected]")
        else:
            st.markdown(":red-badge[:material/error: API unreachable]")
            st.caption(f"Expected at `{ui_settings.api_url}`")

        st.button(
            "Clear chat",
            on_click=clear_chat,
            disabled=not has_chat,
            width="stretch",
        )

        with st.expander("Advanced"):
            st.slider(
                "Passages to retrieve",
                min_value=1,
                max_value=20,
                value=5,
                key="top_k",
                help="How many reranked passages the answer is written from. "
                "More gives broader coverage but a longer prompt.",
            )

        with st.expander("How it works"):
            st.markdown(
                "1. **Search.** Your question is matched against the guidelines two ways, "
                "by meaning (embeddings) and by keywords (BM25), and the results are merged.\n"
                "2. **Rerank.** A reranking model orders the candidates by relevance and "
                "keeps the best few.\n"
                "3. **Answer.** The language model writes an answer from those passages only, "
                "citing each claim. Every citation is checked against the passages it was given."
            )
            st.markdown("**Documents covered**")
            for title in load_content()["documents"].values():
                st.markdown(f"- {escape_markdown(title)}")


def show_examples() -> None:
    """Empty state: starter questions that show what the tool is good at."""
    st.markdown("Try one of these, or ask your own below.")
    examples = load_content()["examples"]
    with st.container(key="examples"):
        columns = st.columns(2)
        for i, example in enumerate(examples):
            columns[i % 2].button(
                example, on_click=ask_example, args=(example,), width="stretch", key=f"example_{i}"
            )


def show_sources(sources: list[dict[str, Any]]) -> None:
    """The cited passages, collapsed under the answer so they never push it away."""
    with st.expander(f"Sources ({len(sources)})"):
        for source in sources:
            with st.container(border=True):
                st.markdown(
                    f":primary-badge[{source['index']}] "
                    f"**{escape_markdown(document_title(source['source']))}** · p. {source['page']}"
                )
                st.caption(escape_markdown(source["text"]))


def show_answer(response: dict[str, Any]) -> None:
    """Answer with citation badges, a citation-quality line, and its sources."""
    valid = {source["index"] for source in response["sources"]}
    st.markdown(render_answer(response["answer"], valid))
    st.caption(citation_summary(response["citation_report"]))
    if response["sources"]:
        show_sources(response["sources"])


def show_message(message: dict[str, Any], index: int) -> None:
    """Draw one stored turn: a question, an answer, or a failed request.

    ``index`` (the turn's position in the chat) gives each question card a
    unique key, which style.css uses to draw the outlined card.
    """
    with st.chat_message(message["role"], avatar=AVATARS[message["role"]]):
        if "error" in message:
            st.error(message["error"], icon=":material/error:")
        elif message["role"] == "assistant":
            show_answer(message["response"])
        else:
            with st.container(key=f"user_q_{index}"):
                st.markdown(escape_markdown(message["content"]))


if "messages" not in st.session_state:
    st.session_state.messages = []

page_header(
    APP_NAME,
    "Answers drawn only from public exercise-science and public-health guidelines, "
    "with page-level citations. Not medical advice.",
)

typed = st.chat_input(
    "Ask about exercise or public-health guidelines", max_chars=MAX_QUESTION_CHARS
)
# An example click (queued by its callback) counts as a question too
question = typed or st.session_state.pop("pending_question", None)

# Drawn before this run's question is stored, so count that question as chat too
show_sidebar(has_chat=bool(st.session_state.messages or question))

if not st.session_state.messages and not question:
    show_examples()

for index, message in enumerate(st.session_state.messages):
    show_message(message, index)

if question:
    user_turn = {"role": "user", "content": question}
    st.session_state.messages.append(user_turn)
    show_message(user_turn, len(st.session_state.messages) - 1)

    with st.spinner("Searching the guidelines…"):
        try:
            response = api_client.ask(question, top_k=st.session_state.top_k)
            reply = {"role": "assistant", "response": response}
        except api_client.ApiError as error:
            reply = {"role": "assistant", "error": str(error)}

    st.session_state.messages.append(reply)
    show_message(reply, len(st.session_state.messages) - 1)
