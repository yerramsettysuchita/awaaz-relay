from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime, UTC
import uuid


class CaseInput(BaseModel):
    case_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    input_type: Literal["image", "voice", "text"]
    raw_image: Optional[str] = None       # base64 encoded image or file path
    raw_audio: Optional[str] = None       # base64 encoded audio or file path
    raw_text: Optional[str] = None        # direct text input
    language: Literal["ta", "te", "kn", "hi", "en"] = "ta"
    query: Optional[str] = None           # extracted question or concern
    metadata: dict = Field(default_factory=lambda: {
        "upload_time": datetime.now(UTC).isoformat(),
        "user_role": "community_worker"
    })


class RetrievedFact(BaseModel):
    rule_id: str
    category: str
    text: str
    source: str
    confidence_base: float
    relevance_score: float


class RetrievalResult(BaseModel):
    retrieved_facts: List[RetrievedFact]
    retrieval_score: float
    query_used: str
    retrieval_method: str = "semantic"  # "semantic" | "bm25"


class GemmaResponse(BaseModel):
    confidence: float                          # 0.0 – 1.0
    confidence_percent: int                    # 0 – 100
    confidence_band: Literal["high", "medium", "low"]
    domain: str                                # e.g. "pension_eligibility"
    worker_guidance: List[str]                 # checklist for community worker
    citizen_guidance: str                      # plain-language for the citizen (always English)
    escalation_needed: bool
    escalation_reason: Optional[str] = None
    evidence_used: List[str]                   # rule_ids used
    tamil_summary: Optional[str] = None        # kept for backward compat
    regional_summary: Optional[str] = None     # summary in user's chosen language


class SafetyScorerOutput(BaseModel):
    confidence_percent: int
    confidence_band: Literal["high", "medium", "low"]
    safe_to_answer: bool
    show_warning: bool
    escalate_immediately: bool
    evidence_panel: List[RetrievedFact]
    disclaimer: str


class AnalyzeResponse(BaseModel):
    case_id: str
    input_summary: str
    language: str = "ta"
    retrieval: RetrievalResult
    gemma: GemmaResponse
    safety: SafetyScorerOutput
    processing_time_ms: int


class FeedbackPayload(BaseModel):
    case_id: str
    rating: Literal["up", "down"]
    query_summary: Optional[str] = None
    confidence_percent: Optional[int] = None
