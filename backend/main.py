"""
FastAPI server — Awaaz Relay backend.
POST /analyze   → full pipeline: input → retrieval → Gemma → safety
POST /feedback  → persist 👍/👎 feedback to SQLite
GET  /health    → liveness + readiness check
GET  /config    → dynamic KB badge counts
GET  /kb/stats  → KB breakdown for debugging
"""

import time
import json
import os
import sqlite3
import logging
import warnings
from typing import Optional
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# FastAPI/Starlette call asyncio.iscoroutinefunction which is deprecated in
# Python 3.12+ (removal in 3.16). Both fastapi.routing and starlette._utils
# trigger this. Suppress globally on this message until upstream ships a fix.
warnings.filterwarnings(
    "ignore",
    message=".*asyncio\\.iscoroutinefunction.*",
    category=DeprecationWarning,
)

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from schemas import AnalyzeResponse, CaseInput, FeedbackPayload
from input_processor import build_case
from retriever import retrieve, reload_kb
from gemma_orchestrator import orchestrate
from safety_scorer import score

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths + env
# ---------------------------------------------------------------------------
KB_PATH     = os.path.join(os.path.dirname(__file__), "..", "data", "knowledge_base.json")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "config.json")
CACHE_PATH  = os.path.join(os.path.dirname(__file__), "..", "data", "embeddings_cache.json")
DB_PATH     = os.path.join(os.path.dirname(__file__), "..", "data", "awaaz_relay.db")
DEMO_MODE   = os.getenv("DEMO_MODE", "true").lower() == "true"

# ---------------------------------------------------------------------------
# SQLite helpers — single db for rate limits + feedback
# ---------------------------------------------------------------------------

def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                ip       TEXT PRIMARY KEY,
                count    INTEGER NOT NULL DEFAULT 0,
                reset_at TEXT    NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id           TEXT    NOT NULL,
                rating            TEXT    NOT NULL,
                query_summary     TEXT,
                confidence_percent INTEGER,
                created_at        TEXT    NOT NULL
            )
        """)
        conn.commit()


# ---------------------------------------------------------------------------
# Startup readiness flags — set once at app start
# ---------------------------------------------------------------------------
_STATUS: dict = {
    "kb_loaded": False,
    "kb_facts": 0,
    "embeddings_ready": False,
    "embeddings_count": 0,
    "started_at": None,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup checks before serving requests."""
    _STATUS["started_at"] = datetime.now().isoformat()
    _init_db()

    try:
        with open(KB_PATH, "r", encoding="utf-8") as f:
            kb = json.load(f)
        _STATUS["kb_loaded"] = True
        _STATUS["kb_facts"] = len(kb.get("facts", []))
        logger.info(f"[STARTUP] KB loaded: {_STATUS['kb_facts']} facts")
    except Exception as e:
        logger.error(f"[STARTUP] KB load failed: {e}")

    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
        embedded = sum(1 for e in cache.get("embeddings", []) if e.get("embedding") is not None)
        _STATUS["embeddings_ready"] = embedded > 0
        _STATUS["embeddings_count"] = embedded
        logger.info(f"[STARTUP] Embeddings ready: {embedded}/{_STATUS['kb_facts']}")
    except FileNotFoundError:
        logger.warning("[STARTUP] No embeddings cache — BM25 fallback active")
    except Exception as e:
        logger.error(f"[STARTUP] Embeddings check failed: {e}")

    yield  # server runs here


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Awaaz Relay API",
    description="Multilingual field intelligence copilot for government welfare applications.",
    version="3.0.0",
    lifespan=lifespan,
)

# CORS — whitelist specific origins from env
_raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]
logger.info(f"CORS origins: {ALLOWED_ORIGINS}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# Gzip — compress responses ≥ 1 KB (cuts bandwidth ~60%)
app.add_middleware(GZipMiddleware, minimum_size=1000)


# ---------------------------------------------------------------------------
# Rate limiting — 20 requests / minute per IP, persisted to SQLite
# Survives server restarts; expired entries are pruned on each check.
# ---------------------------------------------------------------------------

def _check_rate_limit(ip: str) -> bool:
    now = datetime.now()
    now_iso = now.isoformat()
    reset_iso = (now + timedelta(minutes=1)).isoformat()

    with _get_db() as conn:
        # Prune all expired entries in one pass
        conn.execute("DELETE FROM rate_limits WHERE reset_at < ?", (now_iso,))

        row = conn.execute(
            "SELECT count, reset_at FROM rate_limits WHERE ip = ?", (ip,)
        ).fetchone()

        if row is None:
            conn.execute(
                "INSERT INTO rate_limits (ip, count, reset_at) VALUES (?, 1, ?)",
                (ip, reset_iso),
            )
            conn.commit()
            return True

        if row["count"] >= 20:
            conn.commit()
            return False

        conn.execute(
            "UPDATE rate_limits SET count = count + 1 WHERE ip = ?", (ip,)
        )
        conn.commit()
        return True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    """Liveness + readiness. Frontend polls this to show server status."""
    is_ready = _STATUS["kb_loaded"]
    return {
        "status": "ok" if is_ready else "starting",
        "kb_loaded": _STATUS["kb_loaded"],
        "kb_facts": _STATUS["kb_facts"],
        "embeddings_ready": _STATUS["embeddings_ready"],
        "embeddings_count": _STATUS["embeddings_count"],
        "demo_mode": DEMO_MODE,
        "retrieval": "semantic" if _STATUS["embeddings_ready"] else "bm25_fallback",
        "started_at": _STATUS["started_at"],
    }


@app.get("/config")
def get_config():
    """Return dynamic KB stats for frontend badges."""
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    try:
        with open(KB_PATH, "r", encoding="utf-8") as f:
            kb = json.load(f)
        return {"facts_count": len(kb.get("facts", [])), "schemes_count": 6, "languages_count": 5}
    except Exception:
        return {"facts_count": 0, "schemes_count": 6, "languages_count": 5}


@app.get("/kb/stats")
def kb_stats():
    """KB category breakdown — useful for debugging and demo."""
    try:
        with open(KB_PATH, "r", encoding="utf-8") as f:
            kb = json.load(f)
        categories: dict = {}
        for fact in kb.get("facts", []):
            cat = fact.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1
        return {
            "total_facts": len(kb["facts"]),
            "embedded_facts": _STATUS["embeddings_count"],
            "bm25_only_facts": len(kb["facts"]) - _STATUS["embeddings_count"],
            "categories": dict(sorted(categories.items(), key=lambda x: x[1], reverse=True)),
            "last_updated": kb.get("metadata", {}).get("last_updated"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KB stats error: {e}")


@app.get("/knowledge-base")
def get_knowledge_base():
    with open(KB_PATH, "r", encoding="utf-8") as f:
        return JSONResponse(content=json.load(f))


@app.post("/reload-kb")
def reload_knowledge_base():
    reload_kb()
    _STATUS["kb_loaded"] = True
    return {"status": "ok", "message": "Knowledge base reloaded"}


@app.post("/feedback")
def submit_feedback(payload: FeedbackPayload):
    """Persist worker feedback (thumbs up/down) to SQLite."""
    try:
        with _get_db() as conn:
            conn.execute(
                """INSERT INTO feedback (case_id, rating, query_summary, confidence_percent, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    payload.case_id,
                    payload.rating,
                    payload.query_summary,
                    payload.confidence_percent,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        logger.info(f"[FEEDBACK] {payload.rating} for case {payload.case_id[:8]}")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"[FEEDBACK] Failed to save: {e}")
        raise HTTPException(status_code=500, detail="Could not save feedback.")


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    request: Request,
    input_type: str = Form(...),
    language: str = Form("ta"),
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    conversation_context: Optional[str] = Form(None),
):
    client_ip = request.client.host if request.client else "unknown"

    if not _check_rate_limit(client_ip):
        logger.warning(f"[RATE LIMIT] {client_ip} exceeded 20 req/min")
        raise HTTPException(
            status_code=429,
            detail="You have sent too many requests. Please wait one minute and try again.",
        )

    start = time.time()

    image_bytes = None
    audio_bytes = None
    if file:
        raw_bytes = await file.read()
        if input_type == "image":
            image_bytes = raw_bytes
        elif input_type == "voice":
            audio_bytes = raw_bytes

    # Parse conversation history for multi-turn context
    history: list | None = None
    if conversation_context:
        try:
            history = json.loads(conversation_context)
            if not isinstance(history, list):
                history = None
        except Exception:
            history = None

    try:
        case: CaseInput = build_case(
            input_type=input_type,
            image_bytes=image_bytes,
            audio_bytes=audio_bytes,
            text=text,
            language_hint=language,
        )
    except Exception as e:
        logger.error(f"[INPUT] Processing failed for {client_ip}: {e}")
        raise HTTPException(status_code=422, detail=f"Could not process your input: {e}")

    retrieval = retrieve(case, top_k=5)
    gemma_response = orchestrate(case, retrieval, demo_mode=DEMO_MODE, conversation_history=history)
    safety_output = score(gemma_response, retrieval)

    elapsed_ms = int((time.time() - start) * 1000)
    logger.info(f"[ANALYZE] {client_ip} lang={case.language} {elapsed_ms}ms conf={safety_output.confidence_percent}%")

    return AnalyzeResponse(
        case_id=case.case_id,
        input_summary=f"[{input_type.upper()}] {(case.query or '')[:200]}",
        language=case.language,
        retrieval=retrieval,
        gemma=gemma_response,
        safety=safety_output,
        processing_time_ms=elapsed_ms,
    )
