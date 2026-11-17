"""Shared page chrome: the stylesheet and the page header used by every page."""

from functools import cache
from pathlib import Path

import streamlit as st

STYLE_FILE = Path(__file__).with_name("style.css")
APP_NAME = "Health Docs Hybrid RAG"
EYEBROW = "Exercise & public-health guidelines"


@cache
def _stylesheet() -> str:
    """The contents of style.css, read once per process."""
    return STYLE_FILE.read_text(encoding="utf-8")


def apply_style() -> None:
    """Inject style.css. A style-only st.html block takes no space on the page."""
    st.html(f"<style>{_stylesheet()}</style>")


def page_header(title: str, caption: str) -> None:
    """Eyebrow line, title and caption, underlined by the header rule in style.css."""
    with st.container(key="hero"):
        with st.container(key="eyebrow"):
            st.markdown(EYEBROW)
        st.title(title, anchor=False)
        st.caption(caption)
