#!/usr/bin/env python3
"""
Pre-compute and persist Gemini embeddings for all KB facts.

Run ONCE before starting the server (or after KB changes):
    python backend/data_extraction/precompute_embeddings.py

Uses concurrent single-embed calls with retry + backoff for rate limits.
Only re-embeds facts missing from an existing cache (incremental).
"""

import json
import os
import sys
import time
import logging
import concurrent.futures

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

import requests

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

KB_PATH     = os.path.join(os.path.dirname(__file__), "..", "..", "data", "knowledge_base.json")
CACHE_PATH  = os.path.join(os.path.dirname(__file__), "..", "..", "data", "embeddings_cache.json")
API_KEY     = os.getenv("GOOGLE_API_KEY", "")
EMBED_MODEL = "gemini-embedding-001"
EMBED_URL   = f"https://generativelanguage.googleapis.com/v1beta/models/{EMBED_MODEL}:embedContent"
MAX_WORKERS = 3   # Reduced to stay under rate limit for larger KBs


def embed_one(text: str) -> list | None:
    """Embed a single text with up to 3 retries on 429 rate-limit."""
    payload = {
        "model": f"models/{EMBED_MODEL}",
        "content": {"parts": [{"text": text[:1500]}]},
        "taskType": "RETRIEVAL_DOCUMENT",
    }
    for attempt in range(3):
        try:
            resp = requests.post(EMBED_URL, params={"key": API_KEY}, json=payload, timeout=20)
            if resp.status_code == 429:
                wait = 2 ** attempt * 5   # 5s, 10s, 20s
                logger.debug(f"  Rate limited — waiting {wait}s before retry {attempt + 1}")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()["embedding"]["values"]
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 429 and attempt < 2:
                time.sleep(2 ** attempt * 5)
                continue
            logger.warning(f"  ✗ Embed failed: {e}")
            return None
        except Exception as e:
            logger.warning(f"  ✗ Embed failed: {e}")
            return None
    return None


def load_existing_cache() -> dict:
    """Load existing cache and return {rule_id: vector} map."""
    if not os.path.exists(CACHE_PATH):
        return {}
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
        return {
            item["rule_id"]: item["embedding"]
            for item in cache.get("embeddings", [])
            if item.get("embedding") is not None
        }
    except Exception:
        return {}


def main():
    if not API_KEY:
        print("ERROR: Set GOOGLE_API_KEY in .env before running this script.")
        sys.exit(1)

    with open(KB_PATH, "r", encoding="utf-8") as f:
        kb = json.load(f)
    facts = kb["facts"]
    total = len(facts)

    # Load existing cache — only embed facts that are missing
    existing = load_existing_cache()
    missing = [(i, f) for i, f in enumerate(facts) if existing.get(f["rule_id"]) is None]

    if not missing:
        logger.info(f"All {total} embeddings already cached. Nothing to do.")
        return

    logger.info(f"KB has {total} facts. {len(existing)} already cached, {len(missing)} to embed ({MAX_WORKERS} workers)…")

    results = dict(existing)  # start with what we have
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        future_map = {pool.submit(embed_one, f["text"]): (i, f) for i, f in missing}
        done = 0
        for future in concurrent.futures.as_completed(future_map):
            _, fact = future_map[future]
            vec = future.result()
            if vec is not None:
                results[fact["rule_id"]] = vec
            done += 1
            if done % 10 == 0 or done == len(missing):
                ok = sum(1 for v in results.values() if v is not None)
                logger.info(f"  ✓ {done}/{len(missing)} new facts embedded ({ok} total in cache)")

    cache = {
        "model": EMBED_MODEL,
        "total": total,
        "embeddings": [
            {"rule_id": f["rule_id"], "embedding": results.get(f["rule_id"])}
            for f in facts
        ],
    }

    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)

    ok = sum(1 for e in cache["embeddings"] if e["embedding"] is not None)
    logger.info(f"\nDone. {ok}/{total} embeddings saved → {CACHE_PATH}")
    if ok < total:
        logger.warning(f"{total - ok} facts have no embedding — BM25 will cover them as fallback.")
    else:
        logger.info("All facts embedded. Server startup will now be instant.")


if __name__ == "__main__":
    main()
