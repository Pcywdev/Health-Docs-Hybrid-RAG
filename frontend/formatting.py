"""Pure helpers that turn API responses into Streamlit markdown. No Streamlit imports."""

import re
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any

import yaml

CONTENT_FILE = Path(__file__).with_name("content.yaml")

# Mirrors app/generator.py (CITATION_PATTERN, MAX_RANGE, _cited_numbers) so the
# badges show exactly the numbers validate_citation counted. Mirrored, not
# imported: the frontend talks to the API over HTTP only.
CITATION_PATTERN = re.compile(r"\[Source[^\]]*\]")
NUMBER_OR_RANGE = re.compile(r"(\d+)(?:\s*[-–]\s*(\d+))?")
MAX_RANGE = 50

# ASCII punctuation that markdown or Streamlit directives (":red[...]") act on
MARKDOWN_SPECIALS = re.compile(r"([\\`*_{}\[\]<>()#+\-.!|$~:])")


@cache
def load_content() -> dict[str, Any]:
    """The UI copy in content.yaml (document titles, example questions)."""
    return yaml.safe_load(CONTENT_FILE.read_text(encoding="utf-8"))


def document_title(filename: str) -> str:
    """Readable title for a source PDF, falling back to its filename."""
    return load_content().get("documents", {}).get(filename, filename)


def citation_numbers(citation: str) -> list[int]:
    """Source numbers in one citation, in order: ``[Source 2-4]`` gives [2, 3, 4]."""
    numbers: list[int] = []
    for match in NUMBER_OR_RANGE.finditer(citation):
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else start
        start, end = min(start, end), max(start, end)
        for n in range(start, min(end, start + MAX_RANGE - 1) + 1):
            if n not in numbers:
                numbers.append(n)
    return numbers


def escape_markdown(text: str) -> str:
    """Show text literally: collapse PDF line breaks and escape markdown syntax."""
    return MARKDOWN_SPECIALS.sub(r"\\\1", " ".join(text.split()))


def render_answer(answer: str, valid: set[int]) -> str:
    """Answer markdown with each ``[Source N]`` replaced by numbered badges.

    Numbers in ``valid`` (cited and retrieved) get the accent colour; any other
    number points outside the retrieved chunks and is flagged in orange.
    The answer's own markdown (lists, bold) is kept; only ``$`` is escaped so
    amounts are not rendered as LaTeX.
    """

    def badges(match: re.Match[str]) -> str:
        return " ".join(
            f":primary-badge[{n}]" if n in valid else f":orange-badge[{n}?]"
            for n in citation_numbers(match.group(0))
        )

    return CITATION_PATTERN.sub(badges, answer.replace("$", r"\$"))


def citation_summary(report: dict[str, Any]) -> str:
    """One honest line on citation quality, as Streamlit markdown.

    The API checks only that each ``[Source N]`` points at a retrieved passage,
    not that the passage supports the claim, so the wording says exactly that.
    """
    total = report["total_citations"]
    fabricated = report["fabricated_citations"]
    if not report["has_citation"]:
        return ":gray[:material/info: No sources cited. The guidelines may not cover this question.]"
    if fabricated:
        return (
            f":orange[:material/warning: {fabricated} of {total} citations don't match "
            "a retrieved passage.]"
        )
    noun = "citation points" if total == 1 else f"{total} citations point"
    prefix = "The" if total == 1 else "All"
    return f":primary[:material/check_circle:] {prefix} {noun} to a retrieved passage."



def percent(value: float | None) -> str:
    """A 0-1 fraction as a whole percentage; a dash when there is no data."""
    return "–" if value is None else f"{value:.0%}"


def history_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """/history items as table rows: plain values, one row per logged question."""
    return [
        {
            # JSON carries ISO strings; the table's date column needs datetimes
            "Asked": datetime.fromisoformat(item["created_at"]) if item["created_at"] else None,
            "Question": item["question"],
            "Answer": item["answer_preview"],
            "Citations": (
                f"{item['valid_citations']} of {item['total_citations']} resolve"
                if item["has_citations"]
                else "None (refusal)"
            ),
            "Accuracy": item["citation_accuracy"] if item["has_citations"] else None,
            "Retrieved": item["num_sources"],
        }
        for item in items
    ]
