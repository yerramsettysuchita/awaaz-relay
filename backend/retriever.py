"""
Knowledge base retrieval.
Primary: gemini-embedding-001 semantic search (cosine similarity).
Fallback: BM25 keyword matching (when API unavailable or embeddings not ready).
"""

import json
import math
import re
import os
import logging
from collections import Counter
from typing import List, Optional

from schemas import CaseInput, RetrievedFact, RetrievalResult

logger = logging.getLogger(__name__)

KB_PATH         = os.path.join(os.path.dirname(__file__), "..", "data", "knowledge_base.json")
EMBED_CACHE_PATH= os.path.join(os.path.dirname(__file__), "..", "data", "embeddings_cache.json")
GOOGLE_API_KEY  = os.getenv("GOOGLE_API_KEY", "")
EMBED_MODEL     = "gemini-embedding-001"
EMBED_URL       = f"https://generativelanguage.googleapis.com/v1beta/models/{EMBED_MODEL}:embedContent"

_KB: List[dict] = []
_KB_EMBEDDINGS: List[Optional[list]] = []   # parallel to _KB
_EMBEDDINGS_READY = False
_BM25_INDEX: tuple = ()  # (tokenised_docs, corpus_size, avg_dl, df_map) — built once per KB load


# ---------------------------------------------------------------------------
# KB loading
# ---------------------------------------------------------------------------

def _load_kb() -> List[dict]:
    with open(KB_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["facts"]


def _get_kb() -> List[dict]:
    global _KB
    if not _KB:
        _KB = _load_kb()
    return _KB


def reload_kb() -> None:
    global _KB, _KB_EMBEDDINGS, _EMBEDDINGS_READY, _BM25_INDEX
    _KB = _load_kb()
    _KB_EMBEDDINGS = []
    _EMBEDDINGS_READY = False
    _BM25_INDEX = ()
    logger.info(f"[KB] Reloaded {len(_KB)} facts. Embeddings will reload from disk cache on next query.")


# ---------------------------------------------------------------------------
# Semantic embedding helpers
# ---------------------------------------------------------------------------

def _embed_one_doc(text: str) -> Optional[list]:
    """Embed a single document text via embedContent endpoint."""
    if not GOOGLE_API_KEY:
        return None
    try:
        import requests  # type: ignore
        payload = {
            "model": f"models/{EMBED_MODEL}",
            "content": {"parts": [{"text": text[:1500]}]},
            "taskType": "RETRIEVAL_DOCUMENT",
        }
        resp = requests.post(EMBED_URL, params={"key": GOOGLE_API_KEY}, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()["embedding"]["values"]
    except Exception as e:
        logger.debug(f"[EMBED] Single doc embed failed: {e}")
        return None


def _batch_embed_kb(facts: List[dict]) -> List[Optional[list]]:
    """Embed all KB facts using concurrent single-embed calls (5 workers).
    The batchEmbedContents endpoint returns 404 for this model — use individual calls."""
    if not GOOGLE_API_KEY:
        return [None] * len(facts)
    import concurrent.futures
    results: List[Optional[list]] = [None] * len(facts)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        future_map = {pool.submit(_embed_one_doc, f["text"]): i for i, f in enumerate(facts)}
        done = 0
        for future in concurrent.futures.as_completed(future_map):
            idx = future_map[future]
            results[idx] = future.result()
            done += 1
            if done % 15 == 0 or done == len(facts):
                logger.info(f"[EMBED] {done}/{len(facts)} KB facts embedded…")
    return results


def _embed_query(query: str) -> Optional[list]:
    """Embed a single query string. Returns vector or None."""
    if not GOOGLE_API_KEY:
        return None
    try:
        import requests  # type: ignore
        payload = {
            "model": f"models/{EMBED_MODEL}",
            "content": {"parts": [{"text": query[:1000]}]},
            "taskType": "RETRIEVAL_QUERY",
        }
        resp = requests.post(EMBED_URL, params={"key": GOOGLE_API_KEY}, json=payload, timeout=8)
        resp.raise_for_status()
        return resp.json()["embedding"]["values"]
    except Exception as e:
        logger.warning(f"[EMBED] Query embedding failed: {e}")
        return None


def _cosine_sim(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na  = math.sqrt(sum(x * x for x in a))
    nb  = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _load_embed_cache() -> bool:
    """Load pre-computed embeddings from disk. Returns True on success."""
    global _KB_EMBEDDINGS, _EMBEDDINGS_READY
    if not os.path.exists(EMBED_CACHE_PATH):
        return False
    try:
        with open(EMBED_CACHE_PATH, "r", encoding="utf-8") as fh:
            cache = json.load(fh)
        facts = _get_kb()
        id_to_vec = {item["rule_id"]: item["embedding"] for item in cache.get("embeddings", [])}
        _KB_EMBEDDINGS = [id_to_vec.get(f["rule_id"]) for f in facts]
        _EMBEDDINGS_READY = True
        ready = sum(1 for v in _KB_EMBEDDINGS if v is not None)
        logger.info(f"[EMBED] Loaded {ready}/{len(facts)} embeddings from disk cache (instant startup)")
        return True
    except Exception as e:
        logger.warning(f"[EMBED] Cache load failed: {e}. Will recompute.")
        return False


def _save_embed_cache() -> None:
    """Persist current in-memory embeddings to disk for next startup."""
    facts = _get_kb()
    try:
        cache = {
            "model": EMBED_MODEL,
            "total": len(facts),
            "embeddings": [
                {"rule_id": f["rule_id"], "embedding": vec}
                for f, vec in zip(facts, _KB_EMBEDDINGS)
            ],
        }
        with open(EMBED_CACHE_PATH, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, ensure_ascii=False)
        logger.info(f"[EMBED] Embeddings cached to disk → {EMBED_CACHE_PATH}")
    except Exception as e:
        logger.warning(f"[EMBED] Could not save cache: {e}")


def _ensure_kb_embeddings() -> None:
    global _KB_EMBEDDINGS, _EMBEDDINGS_READY
    if _EMBEDDINGS_READY:
        return
    # 1. Try loading from disk (instant, no API calls)
    if _load_embed_cache():
        return
    # 2. Compute via API and persist for next time
    facts = _get_kb()
    logger.info(f"[EMBED] No cache found. Computing embeddings for {len(facts)} KB facts…")
    _KB_EMBEDDINGS = _batch_embed_kb(facts)
    _EMBEDDINGS_READY = True
    ready = sum(1 for v in _KB_EMBEDDINGS if v is not None)
    logger.info(f"[EMBED] {ready}/{len(facts)} facts embedded")
    _save_embed_cache()


# ---------------------------------------------------------------------------
# BM25 helpers (fallback)
# ---------------------------------------------------------------------------

_SUFFIXES = ("ing", "tion", "ies", "ied", "ness", "ment", "able", "es", "ed", "ly", "er", "al", "s")


def _stem(word: str) -> str:
    for sfx in _SUFFIXES:
        if word.endswith(sfx) and len(word) - len(sfx) >= 3:
            return word[: -len(sfx)]
    return word


def _tokenise(text: str) -> List[str]:
    text = text.lower()
    text = re.sub(r"[^\w\s₹]", " ", text)
    text = re.sub(r"₹(\d)", r"\1", text)
    tokens = [t for t in text.split() if len(t) > 1]
    expanded = []
    for t in tokens:
        expanded.append(t)
        stemmed = _stem(t)
        if stemmed != t:
            expanded.append(stemmed)
    return expanded


def _bm25_score(query_tokens: List[str], doc_tokens: List[str], corpus_size: int,
                avg_dl: float, df_map: dict, k1: float = 1.5, b: float = 0.75) -> float:
    dl = len(doc_tokens)
    tf_map = Counter(doc_tokens)
    score = 0.0
    for token in query_tokens:
        if token not in tf_map:
            continue
        tf = tf_map[token]
        df = df_map.get(token, 1)
        idf = math.log((corpus_size - df + 0.5) / (df + 0.5) + 1)
        tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avg_dl))
        score += idf * tf_norm
    return score


def _build_index(facts: List[dict]):
    tokenised_docs = [_tokenise(f["text"] + " " + " ".join(f.get("tags", []))) for f in facts]
    corpus_size = len(facts)
    avg_dl = sum(len(d) for d in tokenised_docs) / corpus_size if corpus_size else 1
    df_map: dict = {}
    for doc in tokenised_docs:
        for token in set(doc):
            df_map[token] = df_map.get(token, 0) + 1
    return tokenised_docs, corpus_size, avg_dl, df_map


CATEGORY_KEYWORD_MAP = {
    "eligibility": ["eligible", "qualify", "widow", "income", "annual", "limit", "standing"],
    "documents":   ["document", "aadhaar", "certificate", "death", "bank", "passport", "ration", "id"],
    "deadline":    ["deadline", "date", "june", "when", "expire", "miss", "last", "close"],
    "benefits":    ["pension", "amount", "money", "receive", "pay", "credit", "monthly"],
    "process":     ["apply", "submit", "steps", "how", "office", "form", "fill"],
    "contact":     ["contact", "call", "phone", "number", "helpline", "office", "where"],
    "escalation":  ["unclear", "confuse", "unsure", "help", "officer", "human"],
}


def _boost_by_category(query_tokens: List[str]) -> List[str]:
    categories = []
    for cat, keywords in CATEGORY_KEYWORD_MAP.items():
        if any(kw in query_tokens for kw in keywords):
            categories.append(cat)
    return categories


def _ensure_bm25_index(facts: List[dict]) -> tuple:
    """Return cached BM25 index, building it once on first call."""
    global _BM25_INDEX
    if not _BM25_INDEX:
        _BM25_INDEX = _build_index(facts)
        logger.info(f"[BM25] Index built for {len(facts)} facts")
    return _BM25_INDEX


def _bm25_retrieve(query: str, facts: List[dict], top_k: int) -> List[tuple]:
    """Returns (score, fact) pairs sorted descending."""
    query_tokens = _tokenise(query)
    if not query_tokens:
        return [(0.0, f) for f in facts[:top_k]]
    tokenised_docs, corpus_size, avg_dl, df_map = _ensure_bm25_index(facts)
    preferred_categories = _boost_by_category(query_tokens)
    scored = []
    for i, fact in enumerate(facts):
        score = _bm25_score(query_tokens, tokenised_docs[i], corpus_size, avg_dl, df_map)
        if fact["category"] in preferred_categories:
            score *= 1.3
        if "always-include" in fact.get("tags", []):
            score = max(score, 2.0)
        scored.append((score, fact))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]


# ---------------------------------------------------------------------------
# Public retrieval function
# ---------------------------------------------------------------------------

def retrieve(case: CaseInput, top_k: int = 5) -> RetrievalResult:
    facts = _get_kb()
    query = (case.query or "").strip()

    if not query:
        fallback = [f for f in facts if "safety" in f.get("tags", []) or "escalation" in f.get("tags", [])][:top_k]
        return RetrievalResult(
            retrieved_facts=[_to_retrieved(f, 0.0) for f in fallback],
            retrieval_score=0.0,
            query_used=query,
        )

    # --- Try semantic search first ---
    _ensure_kb_embeddings()
    if any(v is not None for v in _KB_EMBEDDINGS):
        q_vec = _embed_query(query)
        if q_vec:
            scored = sorted(
                [(fact, _cosine_sim(q_vec, doc_vec))
                 for fact, doc_vec in zip(facts, _KB_EMBEDDINGS)
                 if doc_vec is not None],
                key=lambda x: x[1],
                reverse=True,
            )[:top_k]
            max_score = scored[0][1] if scored else 1.0
            retrieved  = [_to_retrieved(f, s / max_score if max_score > 0 else 0.0) for f, s in scored]
            overall    = sum(s for _, s in scored) / (top_k * max_score) if max_score > 0 else 0.0
            logger.info(f"[RETRIEVAL] Semantic search OK (top cosine={max_score:.3f})")
            return RetrievalResult(
                retrieved_facts=retrieved,
                retrieval_score=round(min(overall, 1.0), 3),
                query_used=query,
                retrieval_method="semantic",
            )

    # --- BM25 fallback ---
    logger.info("[RETRIEVAL] Falling back to BM25")
    scored_bm25 = _bm25_retrieve(query.lower(), facts, top_k)
    max_score   = scored_bm25[0][0] if scored_bm25 else 1.0
    retrieved   = [_to_retrieved(f, s / max_score if max_score > 0 else 0.0) for s, f in scored_bm25]
    # BM25 overall score is capped at 0.65: keyword matching is less precise than semantic
    raw_overall = sum(s for s, _ in scored_bm25) / (top_k * max_score) if max_score > 0 else 0.0
    return RetrievalResult(
        retrieved_facts=retrieved,
        retrieval_score=round(min(raw_overall * 0.65, 0.65), 3),
        query_used=query,
        retrieval_method="bm25",
    )


def _to_retrieved(fact: dict, relevance_score: float) -> RetrievedFact:
    return RetrievedFact(
        rule_id=fact["rule_id"],
        category=fact["category"],
        text=fact["text"],
        source=fact["source"],
        confidence_base=fact["confidence_base"],
        relevance_score=round(relevance_score, 3),
    )
