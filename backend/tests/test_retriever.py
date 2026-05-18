"""Unit tests for the retrieval module (BM25 logic; no API calls needed)."""
import pytest
from retriever import _tokenise, _stem, _bm25_score, _build_index, _cosine_sim


def test_stem_strips_ing():
    assert _stem("applying") == "apply"


def test_stem_no_false_positive_still():
    assert _stem("still") == "still"


def test_stem_preserves_short_words():
    assert _stem("ill") == "ill"


def test_tokenise_lowercases():
    tokens = _tokenise("Apply for Pension")
    assert "apply" in tokens
    assert "pension" in tokens


def test_tokenise_strips_rupee_sign():
    tokens = _tokenise("income ₹3500 per month")
    assert "3500" in tokens


def test_tokenise_adds_stemmed_variants():
    tokens = _tokenise("applying for pension")
    assert "apply" in tokens
    assert "applying" in tokens


def test_tokenise_empty_string():
    assert _tokenise("") == []


def test_bm25_nonzero_for_matching_token():
    s = _bm25_score(["widow"], ["widow", "pension", "apply"], 10, 5.0, {"widow": 3})
    assert s > 0.0


def test_bm25_zero_for_no_match():
    s = _bm25_score(["unrelated"], ["widow", "pension", "apply"], 10, 5.0, {"widow": 3})
    assert s == 0.0


def test_bm25_higher_tf_gives_higher_score():
    low  = _bm25_score(["widow"], ["widow", "pension"], 10, 5.0, {"widow": 2})
    high = _bm25_score(["widow"], ["widow", "widow", "widow", "pension"], 10, 5.0, {"widow": 2})
    assert high > low


def test_cosine_identical_vectors():
    v = [1.0, 0.0, 1.0]
    assert abs(_cosine_sim(v, v) - 1.0) < 1e-9


def test_cosine_orthogonal_vectors():
    assert abs(_cosine_sim([1.0, 0.0], [0.0, 1.0])) < 1e-9


def test_cosine_zero_vector_returns_zero():
    assert _cosine_sim([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_bm25_index_builds_correctly():
    facts = [
        {"text": "widow pension income limit", "tags": []},
        {"text": "documents required for application", "tags": []},
    ]
    tokenised_docs, corpus_size, avg_dl, df_map = _build_index(facts)
    assert corpus_size == 2
    assert "widow" in df_map
