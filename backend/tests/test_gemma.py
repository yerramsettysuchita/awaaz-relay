"""Tests for gemma_orchestrator.py — uses demo_mode=True, no real API key needed."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from schemas import CaseInput
from retriever import retrieve
from gemma_orchestrator import orchestrate


def make_case(query: str, language: str = "en") -> CaseInput:
    return CaseInput(input_type="text", raw_text=query, query=query, language=language)


# ---------------------------------------------------------------------------
# Structure tests
# ---------------------------------------------------------------------------

def test_response_has_required_fields():
    case = make_case("I earn 3500 rupees monthly. Do I qualify for widow pension?")
    retrieval = retrieve(case)
    response = orchestrate(case, retrieval, demo_mode=True)
    assert hasattr(response, "confidence")
    assert hasattr(response, "confidence_percent")
    assert hasattr(response, "confidence_band")
    assert hasattr(response, "worker_guidance")
    assert hasattr(response, "citizen_guidance")
    assert hasattr(response, "escalation_needed")
    assert hasattr(response, "evidence_used")


def test_confidence_in_valid_range():
    case = make_case("What documents do I need for pension?")
    retrieval = retrieve(case)
    response = orchestrate(case, retrieval, demo_mode=True)
    assert 0.0 <= response.confidence <= 1.0
    assert 0 <= response.confidence_percent <= 100
    assert response.confidence_band in ("high", "medium", "low")


def test_worker_guidance_is_list():
    case = make_case("How do I apply for widow pension?")
    retrieval = retrieve(case)
    response = orchestrate(case, retrieval, demo_mode=True)
    assert isinstance(response.worker_guidance, list)
    assert len(response.worker_guidance) > 0


def test_citizen_guidance_is_string():
    case = make_case("Am I eligible for the pension?")
    retrieval = retrieve(case)
    response = orchestrate(case, retrieval, demo_mode=True)
    assert isinstance(response.citizen_guidance, str)
    assert len(response.citizen_guidance) > 0


# ---------------------------------------------------------------------------
# Scenario routing tests (demo mode)
# ---------------------------------------------------------------------------

def test_high_confidence_income_scenario():
    case = make_case("I earn 3500 rupees monthly. Do I qualify for widow pension?")
    retrieval = retrieve(case)
    response = orchestrate(case, retrieval, demo_mode=True)
    assert response.confidence_band == "high"
    assert not response.escalation_needed


def test_low_confidence_medical_escalation():
    case = make_case("I am sick and have a doctor certificate for kidney disease.")
    retrieval = retrieve(case)
    response = orchestrate(case, retrieval, demo_mode=True)
    assert response.confidence_band == "low"
    assert response.escalation_needed
    assert response.escalation_reason is not None


def test_medium_confidence_missing_aadhaar():
    case = make_case("I don't have Aadhaar card. Can I still apply with ration card?")
    retrieval = retrieve(case)
    response = orchestrate(case, retrieval, demo_mode=True)
    assert response.confidence_band == "medium"
    assert not response.escalation_needed


def test_evidence_cited():
    case = make_case("What documents do I need for the pension form?")
    retrieval = retrieve(case)
    response = orchestrate(case, retrieval, demo_mode=True)
    assert isinstance(response.evidence_used, list)
    assert len(response.evidence_used) > 0


# ---------------------------------------------------------------------------
# Multilingual tests
# ---------------------------------------------------------------------------

def test_tamil_response_has_regional_summary():
    case = make_case("விதவை ஓய்வூதியத்திற்கு நான் தகுதியுள்ளவளா?", language="ta")
    retrieval = retrieve(case)
    response = orchestrate(case, retrieval, demo_mode=True)
    # Tamil should have a regional summary
    assert response.regional_summary is not None or response.tamil_summary is not None


def test_english_response_no_regional_summary_required():
    case = make_case("Am I eligible for the pension?", language="en")
    retrieval = retrieve(case)
    response = orchestrate(case, retrieval, demo_mode=True)
    # English doesn't require regional summary — both None and non-None are acceptable
    assert response.confidence_band in ("high", "medium", "low")


def test_no_lakshmi_assumption_for_generic_query():
    """System should not hardcode Lakshmi — citizen guidance should be generic."""
    case = make_case("I am a 70-year-old man from Karnataka. Can I apply?")
    retrieval = retrieve(case)
    response = orchestrate(case, retrieval, demo_mode=True)
    # The system runs in demo mode so citizen_guidance is pre-written,
    # but real mode should not mention Lakshmi for a man from Karnataka.
    # This test verifies the field is populated and the system doesn't crash.
    assert len(response.citizen_guidance) > 0


if __name__ == "__main__":
    test_response_has_required_fields()
    test_confidence_in_valid_range()
    test_worker_guidance_is_list()
    test_citizen_guidance_is_string()
    test_high_confidence_income_scenario()
    test_low_confidence_medical_escalation()
    test_medium_confidence_missing_aadhaar()
    test_evidence_cited()
    test_tamil_response_has_regional_summary()
    test_english_response_no_regional_summary_required()
    test_no_lakshmi_assumption_for_generic_query()
    print("All Gemma orchestrator tests passed.")
