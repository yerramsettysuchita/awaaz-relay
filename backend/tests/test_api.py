"""
Integration tests — FastAPI endpoints via TestClient.
Runs with DEMO_MODE=true so no real API calls are made.
"""
import json
import os
import sys
import pytest

# Force demo mode before any app import
os.environ["DEMO_MODE"] = "true"
os.environ.setdefault("GOOGLE_API_KEY", "test-key-not-real")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app


@pytest.fixture(scope="module")
def client():
    """Module-scoped TestClient — runs lifespan startup/shutdown once."""
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

def test_health_returns_200(client):
    assert client.get("/health").status_code == 200


def test_health_has_required_fields(client):
    data = client.get("/health").json()
    for field in ("status", "kb_loaded", "kb_facts", "embeddings_ready", "demo_mode"):
        assert field in data, f"Missing field: {field}"


def test_health_kb_loaded(client):
    data = client.get("/health").json()
    assert data["kb_loaded"] is True
    assert data["kb_facts"] > 0


def test_health_demo_mode_true(client):
    assert client.get("/health").json()["demo_mode"] is True


# ---------------------------------------------------------------------------
# /config
# ---------------------------------------------------------------------------

def test_config_returns_facts_count(client):
    data = client.get("/config").json()
    assert "facts_count" in data
    assert data["facts_count"] > 0


# ---------------------------------------------------------------------------
# /kb/stats
# ---------------------------------------------------------------------------

def test_kb_stats_has_categories(client):
    data = client.get("/kb/stats").json()
    assert "total_facts" in data
    assert "categories" in data
    assert isinstance(data["categories"], dict)
    assert len(data["categories"]) > 0


# ---------------------------------------------------------------------------
# /analyze — text input
# ---------------------------------------------------------------------------

def test_analyze_text_returns_full_response(client):
    resp = client.post("/analyze", data={
        "input_type": "text",
        "language": "ta",
        "text": "Am I eligible for widow pension if I earn Rs 3500 per month?",
    })
    assert resp.status_code == 200
    data = resp.json()
    for field in ("case_id", "gemma", "safety", "retrieval", "processing_time_ms"):
        assert field in data, f"Missing field: {field}"


def test_analyze_returns_valid_confidence(client):
    resp = client.post("/analyze", data={
        "input_type": "text",
        "language": "en",
        "text": "What documents do I need to apply?",
    })
    assert resp.status_code == 200
    data = resp.json()
    pct = data["safety"]["confidence_percent"]
    assert 0 <= pct <= 100
    assert data["safety"]["confidence_band"] in ("high", "medium", "low")


def test_analyze_returns_worker_guidance_list(client):
    resp = client.post("/analyze", data={
        "input_type": "text",
        "language": "ta",
        "text": "How do I apply for widow pension?",
    })
    assert resp.status_code == 200
    guidance = resp.json()["gemma"]["worker_guidance"]
    assert isinstance(guidance, list)
    assert len(guidance) > 0


def test_analyze_correct_language_echoed(client):
    resp = client.post("/analyze", data={
        "input_type": "text",
        "language": "te",
        "text": "When is the deadline to apply?",
    })
    assert resp.status_code == 200
    assert resp.json()["language"] == "te"


def test_analyze_with_conversation_context(client):
    history = [
        {
            "query": "Am I eligible for widow pension?",
            "domain": "pension_eligibility",
            "confidence_percent": 88,
            "guidance_summary": "You qualify based on income.",
        }
    ]
    resp = client.post("/analyze", data={
        "input_type": "text",
        "language": "ta",
        "text": "What documents do I need?",
        "conversation_context": json.dumps(history),
    })
    assert resp.status_code == 200
    assert "gemma" in resp.json()


def test_analyze_invalid_conversation_context_ignored(client):
    resp = client.post("/analyze", data={
        "input_type": "text",
        "language": "ta",
        "text": "Am I eligible?",
        "conversation_context": "not-valid-json{{",
    })
    # Bad JSON is silently ignored — should still return 200
    assert resp.status_code == 200


def test_analyze_retrieval_method_present(client):
    resp = client.post("/analyze", data={
        "input_type": "text",
        "language": "en",
        "text": "What is the income limit for widow pension?",
    })
    assert resp.status_code == 200
    method = resp.json()["retrieval"]["retrieval_method"]
    assert method in ("semantic", "bm25")


# ---------------------------------------------------------------------------
# /feedback
# ---------------------------------------------------------------------------

def test_feedback_up_returns_ok(client):
    resp = client.post("/feedback", json={
        "case_id": "test-case-001",
        "rating": "up",
        "query_summary": "widow pension eligibility",
        "confidence_percent": 85,
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_feedback_down_returns_ok(client):
    resp = client.post("/feedback", json={
        "case_id": "test-case-002",
        "rating": "down",
        "query_summary": "document requirements",
        "confidence_percent": 55,
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_feedback_minimal_payload(client):
    resp = client.post("/feedback", json={
        "case_id": "test-case-003",
        "rating": "up",
    })
    assert resp.status_code == 200
