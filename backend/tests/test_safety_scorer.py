"""Unit tests for the safety scoring layer."""
import pytest
from schemas import GemmaResponse, RetrievedFact, RetrievalResult
from safety_scorer import score


def _gemma(confidence: float, escalation: bool = False) -> GemmaResponse:
    band = "high" if confidence >= 0.7 else "medium" if confidence >= 0.4 else "low"
    return GemmaResponse(
        confidence=confidence,
        confidence_percent=int(confidence * 100),
        confidence_band=band,
        domain="pension_eligibility",
        worker_guidance=["Confirm eligibility.", "Collect documents."],
        citizen_guidance="You appear to qualify for the widow pension.",
        escalation_needed=escalation,
        evidence_used=["PENSION_003"],
    )


def _retrieval(retrieval_score: float) -> RetrievalResult:
    fact = RetrievedFact(
        rule_id="PENSION_003",
        category="eligibility",
        text="Annual income limit is Rs 2.4 lakh for widow pension.",
        source="TN Social Welfare Rules 2022",
        confidence_base=0.9,
        relevance_score=retrieval_score,
    )
    return RetrievalResult(
        retrieved_facts=[fact],
        retrieval_score=retrieval_score,
        query_used="am I eligible for widow pension",
    )


def test_high_confidence_both_sources():
    out = score(_gemma(0.9), _retrieval(0.9))
    # blended = 0.9*0.6 + 0.9*0.4 = 0.90
    assert out.confidence_band == "high"
    assert out.confidence_percent >= 70
    assert out.safe_to_answer is True
    assert out.escalate_immediately is False
    assert out.show_warning is False


def test_low_retrieval_downgrades_to_medium():
    out = score(_gemma(0.9), _retrieval(0.1))
    # blended = 0.1*0.6 + 0.9*0.4 = 0.06 + 0.36 = 0.42 → medium
    assert out.confidence_band == "medium"
    assert out.show_warning is True
    assert out.safe_to_answer is True


def test_both_low_triggers_escalation():
    out = score(_gemma(0.2), _retrieval(0.2))
    assert out.confidence_band == "low"
    assert out.safe_to_answer is False
    assert out.escalate_immediately is True


def test_explicit_escalation_overrides_high_confidence():
    out = score(_gemma(0.9, escalation=True), _retrieval(0.9))
    assert out.escalate_immediately is True


def test_disclaimer_included_in_output():
    out = score(_gemma(0.8), _retrieval(0.8))
    assert "Tamil Nadu Social Welfare" in out.disclaimer
    assert len(out.disclaimer) > 20


def test_escalation_appends_contact_to_disclaimer():
    out = score(_gemma(0.1), _retrieval(0.1))
    assert "1800-425-1700" in out.disclaimer


def test_evidence_panel_built_from_retrieval():
    out = score(_gemma(0.8), _retrieval(0.8))
    assert len(out.evidence_panel) >= 1
    assert out.evidence_panel[0].rule_id == "PENSION_003"
