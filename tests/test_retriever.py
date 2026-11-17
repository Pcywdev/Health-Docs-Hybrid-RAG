import logging
from types import SimpleNamespace

import pytest
from cohere.core.api_error import ApiError

from app import retriever
from app.retriever import ensure_source_diversity, reciprocal_rank_fusion, retrieve

# --- reciprocal_rank_fusion --------------------------------------------------


def test_single_list_scores_by_rank(make_chunk) -> None:
    fused = reciprocal_rank_fusion([[make_chunk("a"), make_chunk("b")]])
    assert [c["id"] for c in fused] == ["a", "b"]
    assert fused[0]["rrf_score"] == pytest.approx(1 / 61)
    assert fused[1]["rrf_score"] == pytest.approx(1 / 62)
    assert all(c["found_in"] == 1 for c in fused)


def test_chunk_in_both_lists_sums_and_ranks_first(make_chunk) -> None:
    vector = [make_chunk("a"), make_chunk("shared")]
    bm25 = [make_chunk("b"), make_chunk("shared")]
    fused = reciprocal_rank_fusion([vector, bm25])
    assert fused[0]["id"] == "shared"
    assert fused[0]["found_in"] == 2
    assert fused[0]["rrf_score"] == pytest.approx(2 / 62)


def test_ties_keep_first_seen_order(make_chunk) -> None:
    # Rank 1 in each list -> identical scores; "a" was seen first
    fused = reciprocal_rank_fusion([[make_chunk("a")], [make_chunk("b")]])
    assert [c["id"] for c in fused] == ["a", "b"]
    assert fused[0]["rrf_score"] == fused[1]["rrf_score"]


def test_method_specific_keys_are_dropped(make_chunk) -> None:
    fused = reciprocal_rank_fusion(
        [[make_chunk("a", distance=0.1)], [make_chunk("a", score=3.2, score_source="bm25")]]
    )
    assert set(fused[0]) == {"id", "text", "source", "page", "rrf_score", "found_in"}


def test_custom_k_changes_scores(make_chunk) -> None:
    fused = reciprocal_rank_fusion([[make_chunk("a")]], k=10)
    assert fused[0]["rrf_score"] == pytest.approx(1 / 11)


def test_empty_input() -> None:
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


# --- retrieve(): rerank and fallback -----------------------------------------


@pytest.fixture
def stub_searches(monkeypatch: pytest.MonkeyPatch, make_chunk) -> None:
    """Replace both searches with fixed results so no index is needed."""
    monkeypatch.setattr(
        retriever, "vector_search", lambda query, k: [make_chunk("a"), make_chunk("b")]
    )
    monkeypatch.setattr(
        retriever, "bm25_search", lambda query, k: [make_chunk("b"), make_chunk("c")]
    )


def test_retrieve_returns_reranked_chunks(
    monkeypatch: pytest.MonkeyPatch, stub_searches: None
) -> None:
    def fake_rerank(*, query, documents, model, top_n):
        assert top_n == 2
        # Cohere says the 2nd candidate is best
        return SimpleNamespace(
            results=[
                SimpleNamespace(index=1, relevance_score=0.9),
                SimpleNamespace(index=0, relevance_score=0.4),
            ]
        )

    monkeypatch.setattr(retriever.settings, "source_diversity", False)
    monkeypatch.setattr(retriever.cohere_client, "rerank", fake_rerank)
    chunks = retrieve("how much exercise", k=2)
    assert [c["rerank_score"] for c in chunks] == [0.9, 0.4]
    assert len(chunks) == 2
    assert "rrf_score" in chunks[0]  # earlier-stage keys survive reranking


def test_retrieve_falls_back_to_rrf_order_when_cohere_fails(
    monkeypatch: pytest.MonkeyPatch, stub_searches: None, caplog: pytest.LogCaptureFixture
) -> None:
    def failing_rerank(**kwargs):
        raise ApiError(status_code=500, body="boom")

    monkeypatch.setattr(retriever.cohere_client, "rerank", failing_rerank)
    with caplog.at_level(logging.WARNING, logger="app.retriever"):
        chunks = retrieve("how much exercise", k=2)

    # "b" is in both lists, so RRF puts it first; no rerank_score on fallback
    assert [c["id"] for c in chunks] == ["b", "a"]
    assert all("rerank_score" not in c for c in chunks)
    assert "falling back to RRF order" in caplog.text


def test_retrieve_with_diversity_reranks_whole_pool_and_swaps(
    monkeypatch: pytest.MonkeyPatch, make_chunk
) -> None:
    # RRF order: us1, us2, who1. Cohere keeps that order.
    monkeypatch.setattr(
        retriever, "vector_search",
        lambda query, k: [make_chunk("us1", source="us.pdf"), make_chunk("us2", source="us.pdf")],
    )
    monkeypatch.setattr(
        retriever, "bm25_search", lambda query, k: [make_chunk("who1", source="who.pdf")]
    )

    def fake_rerank(*, query, documents, model, top_n):
        assert top_n == len(documents) == 3  # whole pool, not just k
        return SimpleNamespace(
            results=[SimpleNamespace(index=i, relevance_score=s) for i, s in [(0, 0.9), (1, 0.8), (2, 0.5)]]
        )

    monkeypatch.setattr(retriever.settings, "source_diversity", True)
    monkeypatch.setattr(retriever.settings, "diversity_min_score", 0.3)
    monkeypatch.setattr(retriever.cohere_client, "rerank", fake_rerank)
    assert [c["id"] for c in retrieve("compare WHO and US", k=2)] == ["us1", "who1"]


def test_retrieve_rejects_bad_arguments() -> None:
    with pytest.raises(ValueError):
        retrieve("   ")
    with pytest.raises(ValueError):
        retrieve("question", k=0)


# --- ensure_source_diversity -------------------------------------------------


@pytest.fixture
def pool(make_chunk):
    """Build a ranked pool from (id, source, rerank_score) triples."""

    def _pool(*specs: tuple[str, str, float]) -> list[dict]:
        return [make_chunk(cid, source=src, rerank_score=score) for cid, src, score in specs]

    return _pool


def ids(chunks: list[dict]) -> list[str]:
    return [c["id"] for c in chunks]


def test_missing_source_is_swapped_in_at_the_end(pool) -> None:
    # q035's shape: top 5 all US, best WHO chunk ranked 7th
    ranked = pool(
        ("us1", "us.pdf", 0.63), ("us2", "us.pdf", 0.57), ("us3", "us.pdf", 0.51),
        ("us4", "us.pdf", 0.46), ("us5", "us.pdf", 0.45), ("us6", "us.pdf", 0.35),
        ("who1", "who.pdf", 0.32), ("who2", "who.pdf", 0.27),
    )
    result = ensure_source_diversity(ranked, k=5, min_score=0.3)
    assert ids(result) == ["us1", "us2", "us3", "us4", "who1"]


def test_low_score_candidate_is_not_swapped_in(pool) -> None:
    ranked = pool(("us1", "us.pdf", 0.6), ("us2", "us.pdf", 0.5), ("who1", "who.pdf", 0.1))
    assert ids(ensure_source_diversity(ranked, k=2, min_score=0.3)) == ["us1", "us2"]


def test_single_source_is_unchanged(pool) -> None:
    ranked = pool(("a", "us.pdf", 0.9), ("b", "us.pdf", 0.8), ("c", "us.pdf", 0.7))
    assert ids(ensure_source_diversity(ranked, k=2, min_score=0.0)) == ["a", "b"]


def test_already_diverse_is_unchanged(pool) -> None:
    ranked = pool(("us1", "us.pdf", 0.9), ("who1", "who.pdf", 0.8), ("us2", "us.pdf", 0.7))
    assert ids(ensure_source_diversity(ranked, k=2, min_score=0.0)) == ["us1", "who1"]


def test_a_sources_only_chunk_is_never_dropped(pool) -> None:
    # k=2 with three sources: one source must stay out, rather than swapping in a loop
    ranked = pool(("a1", "a.pdf", 0.9), ("b1", "b.pdf", 0.8), ("c1", "c.pdf", 0.7))
    assert ids(ensure_source_diversity(ranked, k=2, min_score=0.0)) == ["a1", "b1"]


def test_chunks_without_rerank_score_are_never_swapped_in(make_chunk) -> None:
    # The RRF fallback has no rerank_score; treat it as 0.0
    ranked = [make_chunk("us1", source="us.pdf"), make_chunk("who1", source="who.pdf")]
    assert ids(ensure_source_diversity(ranked, k=1, min_score=0.1)) == ["us1"]


@pytest.mark.parametrize("k", [1, 3, 5, 10])
def test_output_never_exceeds_k_and_input_is_not_modified(pool, k: int) -> None:
    ranked = pool(
        ("us1", "us.pdf", 0.9), ("us2", "us.pdf", 0.8), ("us3", "us.pdf", 0.7),
        ("who1", "who.pdf", 0.6),
    )
    before = ids(ranked)
    result = ensure_source_diversity(ranked, k=k, min_score=0.0)
    assert len(result) <= k
    assert ids(ranked) == before
