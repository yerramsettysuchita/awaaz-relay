"""
Safety and confidence scoring layer.
Wraps Gemma response with safety gates and evidence traceability.
"""

from typing import List
from schemas import GemmaResponse, RetrievalResult, SafetyScorerOutput, RetrievedFact

DISCLAIMER = (
    "Awaaz Relay provides information to help applicants prepare. "
    "All final eligibility decisions are made by the Tamil Nadu Social Welfare Department. "
    "This is not legal advice."
)

ESCALATION_CONTACT = (
    "Call the Tamil Nadu Social Welfare helpline at 1800-425-1700, toll-free, Monday to Saturday, 9 AM to 5 PM. "
    "Or visit your nearest Block Development Office."
)


def score(gemma: GemmaResponse, retrieval: RetrievalResult) -> SafetyScorerOutput:
    """
    Apply safety gates and return a SafetyScorerOutput.
    Confidence = retrieval quality (0.6 weight) + LLM self-estimate (0.4 weight).
    Retrieval quality is objective (cosine similarity / BM25 score).
    LLM estimate is subjective but captures reasoning quality.
    """
    # Blend: retrieval score weighted higher (objective) vs LLM self-estimate (subjective).
    # BM25 scores are already capped at 0.65 in retriever.py to acknowledge lower precision.
    blended = round((retrieval.retrieval_score * 0.6) + (gemma.confidence * 0.4), 3)
    pct  = int(blended * 100)
    band = "high" if pct >= 70 else "medium" if pct >= 40 else "low"

    # Determine safety flags
    safe_to_answer = pct >= 40
    show_warning = 40 <= pct < 70
    escalate_immediately = pct < 40 or gemma.escalation_needed

    # Build evidence panel: prioritise facts cited by Gemma
    used_ids = set(gemma.evidence_used)
    cited = [f for f in retrieval.retrieved_facts if f.rule_id in used_ids]

    # Fill remaining slots with top retrieved facts not already included
    remaining = [f for f in retrieval.retrieved_facts if f.rule_id not in used_ids
                 and not f.rule_id.startswith("PENSION_02")]  # skip safety boilerplate

    evidence_panel: List[RetrievedFact] = cited + remaining[:max(0, 4 - len(cited))]

    # Always append the safety disclaimer fact at the end
    safety_facts = [f for f in retrieval.retrieved_facts if f.rule_id == "PENSION_025"]
    if safety_facts and safety_facts[0] not in evidence_panel:
        evidence_panel.append(safety_facts[0])

    disclaimer = DISCLAIMER
    if escalate_immediately:
        disclaimer = f"{disclaimer}\n\nESCALATION REQUIRED: {ESCALATION_CONTACT}"

    return SafetyScorerOutput(
        confidence_percent=pct,
        confidence_band=band,
        safe_to_answer=safe_to_answer,
        show_warning=show_warning,
        escalate_immediately=escalate_immediately,
        evidence_panel=evidence_panel,
        disclaimer=disclaimer,
    )


def format_evidence_text(evidence: List[RetrievedFact]) -> str:
    """Human-readable evidence summary for the UI Evidence Panel."""
    if not evidence:
        return "No specific sources cited."
    lines = []
    for f in evidence:
        excerpt = f.text[:120] + ("..." if len(f.text) > 120 else "")
        lines.append(
            f"[{f.rule_id}] {f.category.upper()} | \"{excerpt}\" "
            f"| Source: {f.source} (base confidence: {int(f.confidence_base * 100)}%)"
        )
    return "\n".join(lines)


def confidence_color(band: str) -> str:
    """Returns CSS class name for the confidence band."""
    return {"high": "confidence-high", "medium": "confidence-medium", "low": "confidence-low"}.get(band, "confidence-low")


def confidence_label(band: str, pct: int) -> str:
    labels = {
        "high": f"High Confidence ({pct}%). Answer is well-supported by sources.",
        "medium": f"Medium Confidence ({pct}%). Answer is likely correct but verify with the office.",
        "low": f"Low Confidence ({pct}%). Cannot answer safely. Please speak to a human officer.",
    }
    return labels.get(band, f"Confidence: {pct}%")
