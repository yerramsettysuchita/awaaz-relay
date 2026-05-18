"""
Gemma / Gemini orchestration engine.
Builds prompt from case + retrieved facts, calls Gemini API, parses structured response.
Falls back to mock responses when API is unavailable or DEMO_MODE=true.
"""

import json
import os
import re
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from schemas import CaseInput, RetrievalResult, GemmaResponse

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", "system_prompt.txt")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
DEMO_MODE_ENV = os.getenv("DEMO_MODE", "true").lower() == "true"
MODEL_CHAIN = [
    ("gemini-2.0-flash-lite",  8),   # Fastest — try first
    ("gemini-2.0-flash",      12),   # High quality fallback
    ("gemini-2.5-flash",      20),   # Last resort
]
GEMINI_MODEL    = MODEL_CHAIN[0][0]   # Used in logs
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/"


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT: str = ""


def _load_system_prompt() -> str:
    global _SYSTEM_PROMPT
    if not _SYSTEM_PROMPT:
        with open(SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
            _SYSTEM_PROMPT = f.read()
    return _SYSTEM_PROMPT


def _build_user_message(case: CaseInput, retrieval: RetrievalResult,
                         conversation_history: list | None = None) -> str:
    history_text = ""
    if conversation_history:
        lines = ["CONVERSATION HISTORY (prior turns — use for follow-up reasoning):"]
        for i, turn in enumerate(conversation_history[-2:], 1):
            lines.append(f"Turn {i} — Query: {str(turn.get('query', ''))[:150]}")
            lines.append(f"Turn {i} — Domain: {turn.get('domain', '?')}, Confidence: {turn.get('confidence_percent', '?')}%")
            if turn.get("guidance_summary"):
                lines.append(f"Turn {i} — Key guidance: {str(turn.get('guidance_summary', ''))[:150]}")
        history_text = "\n".join(lines) + "\n\n"

    facts_text = "\n".join(
        f"[{f.rule_id}] {f.text} (source: {f.source}, conf: {f.confidence_base})"
        for f in retrieval.retrieved_facts
    )
    return f"""{history_text}QUERY: {case.query or ''}
LANGUAGE: {case.language}

FACTS:
{facts_text}

OUTPUT (raw JSON only, no reasoning, no explanation, start with {{):"""


# ---------------------------------------------------------------------------
# Gemini REST API call (no SDK — works with any Python version)
# ---------------------------------------------------------------------------

def _call_gemini(system_prompt: str, user_message: str) -> str:
    import requests  # type: ignore

    combined = f"{system_prompt}\n\n---\n\n{user_message}"
    last_error = None

    for model, timeout in MODEL_CHAIN:
        try:
            url = f"{GEMINI_BASE_URL}{model}:generateContent"
            payload = {
                "contents": [{"role": "user", "parts": [{"text": combined}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096},
            }
            resp = requests.post(url, params={"key": GOOGLE_API_KEY}, json=payload, timeout=timeout)
            resp.raise_for_status()
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            logger.info(f"[LIVE API] {model} responded ({len(text)} chars)")
            return text
        except Exception as e:
            last_error = e
            logger.warning(f"[LIVE API] {model} failed: {e}. Trying next model...")

    raise RuntimeError(f"All models failed. Last error: {last_error}")


# ---------------------------------------------------------------------------
# Response parser — robust against markdown fences and partial JSON
# ---------------------------------------------------------------------------

def _extract_json_candidates(text: str):
    """Yield all top-level {...} blocks found in text, last-to-first."""
    candidates = []
    depth = 0
    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                candidates.append(text[start: i + 1])
                start = None
    return list(reversed(candidates))


def _parse_response(raw: str) -> GemmaResponse:
    """
    Extract JSON from model response.
    Handles:
    - Clean JSON
    - Markdown fences (```json ... ```)
    - Gemma 4 chain-of-thought with JSON buried in reasoning text
    - Backtick-inline JSON (`{...}`)
    """
    raw = raw.strip()

    # 1. Try the whole response as JSON first (cleanest case)
    try:
        data = json.loads(raw)
        if "confidence_percent" in data or "confidence" in data:
            return _build_gemma_response(data)
    except Exception:
        pass

    # 2. Strip markdown fences and try again
    if "```" in raw:
        for block in raw.split("```"):
            block = block.strip().lstrip("json").strip()
            if block.startswith("{"):
                try:
                    data = json.loads(block)
                    if "confidence_percent" in data or "confidence" in data:
                        return _build_gemma_response(data)
                except Exception:
                    pass

    # 3. Find all {...} blocks, try last-to-first (Gemma puts answer at end)
    for candidate in _extract_json_candidates(raw):
        try:
            data = json.loads(candidate)
            if "confidence_percent" in data or "confidence" in data:
                return _build_gemma_response(data)
        except Exception:
            continue

    # 4. Last resort: find the substring starting at last { containing our keys
    for key in ('"confidence_percent"', '"confidence"'):
        idx = raw.rfind(key)
        if idx != -1:
            obj_start = raw.rfind("{", 0, idx)
            if obj_start != -1:
                snippet = raw[obj_start:]
                # Try to close any open braces/brackets to repair truncated JSON
                snippet = _repair_json(snippet)
                try:
                    data = json.loads(snippet)
                    return _build_gemma_response(data)
                except Exception:
                    pass

    raise ValueError(f"No valid JSON found in model response ({len(raw)} chars). Start: {raw[:200]}")


def _repair_json(text: str) -> str:
    """Attempt to close unclosed JSON braces/brackets."""
    stack = []
    in_string = False
    escape_next = False
    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack:
            stack.pop()
    return text + "".join(reversed(stack))


def _build_gemma_response(data: dict) -> GemmaResponse:
    confidence = float(data.get("confidence", 0.5))
    confidence_percent = int(data.get("confidence_percent", int(confidence * 100)))

    if confidence_percent >= 70:
        band = "high"
    elif confidence_percent >= 40:
        band = "medium"
    else:
        band = "low"

    regional = data.get("regional_summary") or data.get("tamil_summary")
    return GemmaResponse(
        confidence=confidence,
        confidence_percent=confidence_percent,
        confidence_band=band,
        domain=data.get("domain", "pension_eligibility"),
        worker_guidance=data.get("worker_guidance", []),
        citizen_guidance=data.get("citizen_guidance", ""),
        escalation_needed=data.get("escalation_needed", band == "low"),
        escalation_reason=data.get("escalation_reason"),
        evidence_used=data.get("evidence_used", []),
        tamil_summary=data.get("tamil_summary"),
        regional_summary=regional,
    )


# ---------------------------------------------------------------------------
# Mock responses for demo / offline mode
# ---------------------------------------------------------------------------

MOCK_RESPONSES = {
    "deadline": GemmaResponse(
        confidence=0.92,
        confidence_percent=92,
        confidence_band="high",
        domain="deadline",
        worker_guidance=[
            "Submit the application today. The June 30 deadline is very close and missing it means waiting 8 more months.",
            "Make sure all documents are ready. You need FORM 1-W, the death certificate, bank passbook, ration card, and 2 passport photos.",
            "If some documents are missing, submit the application now and bring the remaining ones within 15 days (PENSION_020).",
            "Get the acknowledgment receipt when submitting and keep it safe. This receipt has the application number needed for tracking.",
            "Special camps may be available at the local Panchayat even after June 30. Ask the Panchayat President about this.",
            "After submission, track the application status by sending TNPENSION followed by the application number to 7676000100.",
        ],
        citizen_guidance=(
            "Akka, you are asking at exactly the right time. The deadline is June 30 and it is very close. "
            "Please submit your application this week. Even if you do not have every document ready, "
            "you can submit what you have and bring the rest within 15 days. "
            "Do not wait for everything to be perfect because missing the deadline means waiting 8 more months. "
            "Go to the Block Development Office as soon as you can with whatever you have. "
            "After submitting, you will receive an acknowledgment paper. Please keep it safe!"
        ),
        escalation_needed=False,
        escalation_reason=None,
        evidence_used=["PENSION_014", "PENSION_015", "PENSION_020", "PENSION_018", "PENSION_055"],
        tamil_summary=(
            "அக்கா, ஜூன் 30 கடைசி தேதி. இப்போதே விண்ணப்பிக்கவும். "
            "ஆவணங்கள் இல்லாவிட்டாலும் விண்ணப்பிக்கலாம். 15 நாளில் கொண்டு வரலாம். "
            "மேலும் காத்திருந்தால் 8 மாதம் தாமதம் ஆகும்."
        ),
    ),
    "process": GemmaResponse(
        confidence=0.85,
        confidence_percent=85,
        confidence_band="high",
        domain="process",
        worker_guidance=[
            "Collect FORM 1-W for free from the Block Development Office, Taluk Office, or local Panchayat.",
            "Help the applicant fill the form in Tamil or English. A thumb impression is valid if the applicant is illiterate (PENSION_052).",
            "Prepare the documents. You need FORM 1-W, death certificate, Aadhaar or Voter ID, bank passbook, ration card, and 2 passport photos.",
            "Submit at the Block Development Officer's office and insist on receiving an acknowledgment receipt.",
            "After submission, verification takes 30 working days (PENSION_019). Tell the applicant to watch for SMS updates.",
            "Track the status by sending TNPENSION followed by the application number to 7676000100 or by calling 1800-425-1700.",
            "The first pension payment arrives 45 days after approval. A life certificate renewal is needed every October.",
        ],
        citizen_guidance=(
            "Akka, let me explain the steps clearly. First, pick up the application form from the Block Development Office "
            "or your local Panchayat. It is completely free and you do not need to pay anyone for it. "
            "Bring your husband's death certificate, your Aadhaar or Voter ID, your bank passbook, your ration card, "
            "and 2 passport-size photos. After submitting, keep the acknowledgment paper safely because it has your "
            "application number. If approved, your first payment of Rs 1,000 arrives within 45 days!"
        ),
        escalation_needed=False,
        escalation_reason=None,
        evidence_used=["PENSION_018", "PENSION_019", "PENSION_008", "PENSION_043", "PENSION_038", "PENSION_033"],
        tamil_summary=(
            "அக்கா, FORM 1-W BDO அலுவலகத்தில் இலவசமாக கிடைக்கும். "
            "தேவையான ஆவணங்கள்: இறப்பு சான்றிதழ், ஆதார், வங்கி புத்தகம், ரேஷன் கார்டு மற்றும் 2 புகைப்படங்கள். "
            "சமர்ப்பித்த பிறகு 30 நாட்களில் சரிபார்க்கப்படும். ஒப்புகை ரசீதை பத்திரமாக வைத்துக்கொள்ளுங்கள்."
        ),
    ),
    "old_age": GemmaResponse(
        confidence=0.88,
        confidence_percent=88,
        confidence_band="high",
        domain="old_age_pension",
        worker_guidance=[
            "The applicant is 60 or above and qualifies for IGNOAPS, the Old Age Pension scheme, which pays Rs 1,000 per month.",
            "If the applicant is also a widow, she can choose between the widow pension and old-age pension. Both pay the same amount (OAP_004).",
            "Documents needed for IGNOAPS include age proof such as Aadhaar or Voter ID, BPL ration card, bank passbook, and a recent photograph.",
            "Apply at the Block Development Office. The process is the same as for widow pension.",
            "If the applicant is 80 or older, the pension comes as Rs 500 from the central government and Rs 500 from the state, totaling Rs 1,000 per month.",
            "A destitute widow with no income at all may qualify for the destitute widow scheme which pays Rs 1,500 per month (SCHEME_002).",
        ],
        citizen_guidance=(
            "Akka, this is good news. Since you are 60 years or older, you qualify for the Old Age Pension, "
            "which is also called the Indira Gandhi National Old Age Pension Scheme. It gives you the same "
            "Rs 1,000 per month as the widow pension, through the same process and the same office. "
            "If you are also a widow, you can choose whichever scheme is easier for you to qualify for. "
            "Just go to the Block Development Office and ask for the Old Age Pension form. "
            "Bring your age proof like your Aadhaar card, your BPL ration card, and your bank passbook. "
            "You deserve this support, so please apply soon!"
        ),
        escalation_needed=False,
        escalation_reason=None,
        evidence_used=["OAP_001", "OAP_002", "OAP_003", "OAP_004", "SCHEME_001"],
        tamil_summary=(
            "அக்கா, 60 வயதுக்கு மேல் இருந்தால் வயதானோர் ஓய்வூதியம் (IGNOAPS) கிடைக்கும். "
            "மாதம் Rs 1,000 கிடைக்கும், இது விதவை ஓய்வூதியத்திற்கு சமம். "
            "BDO அலுவலகத்தில் விண்ணப்பிக்கவும். ஆதார், BPL கார்டு மற்றும் வங்கி புத்தகம் கொண்டு வாருங்கள்."
        ),
    ),
    "appeal": GemmaResponse(
        confidence=0.82,
        confidence_percent=82,
        confidence_band="high",
        domain="process",
        worker_guidance=[
            "The application was rejected. First, collect the official rejection letter from the Block Development Office.",
            "Read the rejection reason carefully. The most common causes are name mismatch, income miscalculation, or missing documents.",
            "File an appeal at the District Collectorate Social Welfare office within 30 days of receiving the rejection letter (PENSION_032).",
            "Attach the original rejection letter, any corrected or missing documents, and a brief appeal letter explaining what has been corrected.",
            "The appeal is reviewed within 45 working days. Keep a copy of everything submitted.",
            "If the issue is a name mismatch, get an affidavit from a local Notary. The cost is around Rs 50 to Rs 100 and this resolves it quickly (PENSION_050).",
            "If the appeal is also rejected, escalate to the District Collector's grievance cell at pgportal.gov.in.",
        ],
        citizen_guidance=(
            "Akka, please do not lose hope. A rejection is not the final word and you have the right to appeal. "
            "First, go to the Block Development Office and collect the rejection letter to understand why it was rejected. "
            "Most rejections happen because of small document issues that can be easily fixed. "
            "Then take the rejection letter and your corrected documents to the District Collectorate office and file an appeal. "
            "Write a simple letter saying you are appealing this rejection and explain what has been corrected. "
            "They must review your appeal within 45 days. Many first-time rejections are overturned on appeal, "
            "so please do not give up!"
        ),
        escalation_needed=False,
        escalation_reason=None,
        evidence_used=["PENSION_032", "PENSION_031", "PENSION_050", "PENSION_044"],
        tamil_summary=(
            "அக்கா, நிராகரிப்பு இறுதி முடிவல்ல. 30 நாட்களுக்குள் மேல்முறையீடு செய்யலாம். "
            "BDO அலுவலகத்தில் நிராகரிப்பு கடிதம் பெறுங்கள். "
            "மாவட்ட ஆட்சியர் அலுவலகத்தில் மேல்முறையீடு செய்யுங்கள். 45 நாட்களில் பரிசீலிக்கப்படும்."
        ),
    ),
    "high": GemmaResponse(
        confidence=0.88,
        confidence_percent=88,
        confidence_band="high",
        domain="pension_eligibility",
        worker_guidance=[
            "Confirm the applicant is a widow and that the husband's death certificate is available.",
            "Income check shows Rs 3,500 per month equals Rs 42,000 per year. The limit is Rs 2.4 lakhs so the applicant qualifies on income.",
            "Clarify the '10 plus years standing' requirement with the Block Development Officer before submission.",
            "Collect the death certificate, bank passbook, ration card, and 2 passport photos.",
            "Check if Aadhaar is available. If missing, direct the applicant to the nearest Aadhaar Seva Kendra by calling 1947.",
            "Confirm no other government pension is being received (PENSION_028).",
            "The deadline is June 30. Submit immediately to avoid an 8-month wait.",
        ],
        citizen_guidance=(
            "Akka, you are right to ask and we have good news for you. Your monthly earning of Rs 3,500 "
            "comes to Rs 42,000 per year. The limit is Rs 2,40,000 per year so you qualify on income. "
            "The phrase '10 plus years standing' confuses many people. Please ask the officer to explain "
            "what it means when you visit the office. "
            "Bring your husband's death certificate, your bank passbook, and your ration card. "
            "If you do not have Aadhaar, a Voter ID or Ration Card can also work. "
            "The deadline is June 30 so please go to the office soon!"
        ),
        escalation_needed=False,
        escalation_reason=None,
        evidence_used=["PENSION_003", "PENSION_004", "PENSION_005", "PENSION_008", "PENSION_009", "PENSION_014"],
        tamil_summary=(
            "அக்கா, உங்கள் மாத வருமானம் Rs 3,500 என்பது ஆண்டுக்கு Rs 42,000 ஆகும். "
            "வரம்பு Rs 2.4 லட்சம் என்பதால் நீங்கள் வருமான தகுதி பெற்றவர். "
            "தேவையான ஆவணங்கள்: இறப்பு சான்றிதழ், வங்கி பாஸ்புக் மற்றும் ரேஷன் கார்டு."
        ),
    ),
    "medium": GemmaResponse(
        confidence=0.55,
        confidence_percent=55,
        confidence_band="medium",
        domain="documents_required",
        worker_guidance=[
            "Aadhaar is missing. Use a Voter ID or Ration Card as an alternative ID (PENSION_009).",
            "If possible, guide the applicant to the nearest Aadhaar Seva Kendra. They can call 1947 for free.",
            "The old death certificate from 2010 is still valid and does not need to be renewed (PENSION_011).",
            "Confirm the bank account is active for Direct Benefit Transfer.",
            "The '10 plus years standing' requirement is unclear. Please escalate this to the Block Development Officer for clarification.",
        ],
        citizen_guidance=(
            "Akka, please do not worry. Not having Aadhaar is very common and you can use your Voter ID "
            "or Ration Card instead. It would be even better to get Aadhaar before submitting. "
            "You can call 1947 for free to find the nearest centre. "
            "Your old death certificate from 2010 is still perfectly valid and you do not need a new one. "
            "There is one thing we need to clarify with the office and that is the '10 plus years standing' rule. "
            "Please ask the officer what this means for your situation when you visit."
        ),
        escalation_needed=False,
        escalation_reason=None,
        evidence_used=["PENSION_009", "PENSION_010", "PENSION_011", "PENSION_005"],
        tamil_summary=None,
    ),
    "low": GemmaResponse(
        confidence=0.25,
        confidence_percent=25,
        confidence_band="low",
        domain="out_of_scope",
        worker_guidance=[
            "This query involves a medical or health condition which is outside the scope of pension rules.",
            "Refer the applicant to the nearest Primary Health Centre or district hospital for medical guidance.",
            "For disability-related pension enhancement, contact the Block Development Office directly.",
            "Please do not provide medical advice through Awaaz Relay.",
        ],
        citizen_guidance=(
            "Akka, your health question is very important and we take it seriously. "
            "However, only doctors can give medical advice and it would not be right for us to do so. "
            "For the pension form's health section, please write your condition honestly. "
            "Having a chronic illness does not disqualify you from the pension. "
            "Please visit the Primary Health Centre in your area for medical guidance. "
            "For any disability-related pension benefits, speak directly with the Block Development Officer."
        ),
        escalation_needed=True,
        escalation_reason="Query involves a medical condition which is outside the scope of the pension knowledge base. Please route to a human officer.",
        evidence_used=["PENSION_025", "PENSION_026", "PENSION_027"],
        tamil_summary=None,
    ),
}


# ---------------------------------------------------------------------------
# Multilingual regional summaries — loaded from data/multilingual_summaries.json
# Worker guidance is always English; regional_summary is for the citizen
# ---------------------------------------------------------------------------

def _load_multilingual_summaries() -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "data", "multilingual_summaries.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

MULTILINGUAL_SUMMARIES: dict = _load_multilingual_summaries()

# Keep the raw dict below only for reference — the live data is now in JSON.
_MULTILINGUAL_SUMMARIES_LEGACY: dict = {
    "high": {
        "ta": (
            "அக்கா, உங்கள் மாத வருமானம் ₹3,500 ஆகும், அதாவது ஆண்டுக்கு ₹42,000. "
            "வரம்பு ₹2.4 லட்சம். நீங்கள் வருமான தகுதி பெற்றவர். "
            "தேவையான ஆவணங்கள் இறப்பு சான்றிதழ், வங்கி பாஸ்புக் மற்றும் ரேஷன் கார்டு."
        ),
        "te": (
            "అక్కా, మీ నెలసరి ఆదాయం ₹3,500, అంటే సంవత్సరానికి ₹42,000. "
            "పరిమితి ₹2.4 లక్షలు. మీరు ఆదాయ అర్హత పొందారు. "
            "అవసరమైన పత్రాలు మరణ సర్టిఫికెట్, బ్యాంక్ పాస్‌బుక్ మరియు రేషన్ కార్డ్."
        ),
        "kn": (
            "ಅಕ್ಕ, ನಿಮ್ಮ ಮಾಸಿಕ ಆದಾಯ ₹3,500, ಅಂದರೆ ವರ್ಷಕ್ಕೆ ₹42,000. "
            "ಮಿತಿ ₹2.4 ಲಕ್ಷ. ನೀವು ಆದಾಯ ಅರ್ಹತೆ ಪಡೆದಿದ್ದೀರಿ. "
            "ಬೇಕಾದ ದಾಖಲೆಗಳು ಮರಣ ಪ್ರಮಾಣಪತ್ರ, ಬ್ಯಾಂಕ್ ಪಾಸ್‌ಬುಕ್ ಮತ್ತು ರೇಷನ್ ಕಾರ್ಡ್."
        ),
        "hi": (
            "दीदी, आपकी मासिक आय ₹3,500 है, यानी सालाना ₹42,000. "
            "आय सीमा ₹2.4 लाख है। आप आय पात्रता रखती हैं। "
            "जरूरी दस्तावेज मृत्यु प्रमाण पत्र, बैंक पासबुक और राशन कार्ड हैं।"
        ),
        "en": None,
    },
    "medium": {
        "ta": (
            "அக்கா, ஆதார் இல்லாமல் விண்ணப்பிக்கலாம். "
            "வாக்காளர் அடையாள அட்டை அல்லது ரேஷன் கார்டு ஏற்கப்படும். "
            "ஆதார் பெற 1947 என்ற எண்ணில் அழைக்கவும் (இலவசம்)."
        ),
        "te": (
            "అక్కా, ఆధార్ లేకుండా దరఖాస్తు చేయవచ్చు. "
            "వోటర్ ID లేదా రేషన్ కార్డ్ పత్రంగా అంగీకరించబడుతుంది. "
            "ఆధార్ పొందడానికి 1947కి కాల్ చేయండి (ఉచితం)."
        ),
        "kn": (
            "ಅಕ್ಕ, ಆಧಾರ್ ಇಲ್ಲದೆ ಅರ್ಜಿ ಸಲ್ಲಿಸಬಹುದು. "
            "ಮತದಾರರ ಗುರುತಿನ ಚೀಟಿ ಅಥವಾ ರೇಷನ್ ಕಾರ್ಡ್ ದಾಖಲೆಯಾಗಿ ಸ್ವೀಕರಿಸಲಾಗುತ್ತದೆ. "
            "ಆಧಾರ್ ಪಡೆಯಲು 1947ಕ್ಕೆ ಕರೆ ಮಾಡಿ (ಉಚಿತ)."
        ),
        "hi": (
            "दीदी, आधार के बिना भी आवेदन कर सकती हैं। "
            "वोटर ID या राशन कार्ड दस्तावेज़ के रूप में स्वीकार किया जाता है। "
            "आधार बनवाने के लिए 1947 पर कॉल करें (निःशुल्क)।"
        ),
        "en": None,
    },
    "low": {
        "ta": (
            "அக்கா, மருத்துவ கேள்விகளுக்கு நான் பதில் சொல்ல முடியாது. "
            "உங்கள் அருகிலுள்ள ஆரம்ப சுகாதார மையத்தை தொடர்பு கொள்ளவும். "
            "ஓய்வூதிய விஷயங்களுக்கு: 1800-425-1700 என்ற எண்ணில் அழைக்கவும்."
        ),
        "te": (
            "అక్కా, వైద్య ప్రశ్నలకు నేను జవాబు ఇవ్వలేను. "
            "దయచేసి మీ సమీప ప్రాథమిక ఆరోగ్య కేంద్రాన్ని సంప్రదించండి. "
            "పెన్షన్ విషయాలకు: 1800-425-1700కి కాల్ చేయండి."
        ),
        "kn": (
            "ಅಕ್ಕ, ವೈದ್ಯಕೀಯ ಪ್ರಶ್ನೆಗಳಿಗೆ ನಾನು ಉತ್ತರಿಸಲು ಸಾಧ್ಯವಿಲ್ಲ. "
            "ದಯವಿಟ್ಟು ನಿಮ್ಮ ಹತ್ತಿರದ ಪ್ರಾಥಮಿಕ ಆರೋಗ್ಯ ಕೇಂದ್ರವನ್ನು ಸಂಪರ್ಕಿಸಿ. "
            "ಪಿಂಚಣಿ ವಿಷಯಗಳಿಗೆ: 1800-425-1700ಕ್ಕೆ ಕರೆ ಮಾಡಿ."
        ),
        "hi": (
            "दीदी, मैं चिकित्सा प्रश्नों का उत्तर नहीं दे सकती। "
            "कृपया अपने नजदीकी प्राथमिक स्वास्थ्य केंद्र से संपर्क करें। "
            "पेंशन मामलों के लिए: 1800-425-1700 पर कॉल करें।"
        ),
        "en": None,
    },
    "deadline": {
        "ta": (
            "அக்கா, ஜூன் 30 கடைசி தேதி! இப்போதே விண்ணப்பிக்கவும். "
            "ஆவணங்கள் இல்லாவிட்டாலும் விண்ணப்பிக்கவும், 15 நாளில் கொண்டு வரலாம். "
            "மேலும் காத்திருந்தால் 8 மாதம் தாமதம் ஆகும்."
        ),
        "te": (
            "అక్కా, జూన్ 30 చివరి తేదీ! ఇప్పుడే దరఖాస్తు చేయండి. "
            "పత్రాలు లేకపోయినా దరఖాస్తు చేయండి, 15 రోజులలో తీసుకురావచ్చు. "
            "ఆలస్యం చేస్తే 8 నెలలు వేచి ఉండాలి."
        ),
        "kn": (
            "ಅಕ್ಕ, ಜೂನ್ 30 ಕೊನೆಯ ದಿನ! ಈಗಲೇ ಅರ್ಜಿ ಸಲ್ಲಿಸಿ. "
            "ದಾಖಲೆಗಳು ಇಲ್ಲದಿದ್ದರೂ ಅರ್ಜಿ ಸಲ್ಲಿಸಿ, 15 ದಿನಗಳಲ್ಲಿ ತರಬಹುದು. "
            "ತಡ ಮಾಡಿದರೆ 8 ತಿಂಗಳು ಕಾಯಬೇಕು."
        ),
        "hi": (
            "दीदी, 30 जून आखिरी तारीख है! अभी आवेदन करें। "
            "दस्तावेज़ न हों तो भी आवेदन करें, 15 दिन में ला सकती हैं। "
            "देर करने पर 8 महीने इंतजार करना पड़ेगा।"
        ),
        "en": None,
    },
    "process": {
        "ta": (
            "அக்கா, FORM 1-W இலவசமாக BDO அலுவலகத்தில் கிடைக்கும். "
            "ஆவணங்கள்: இறப்பு சான்றிதழ், ஆதார், வங்கி புத்தகம், ரேஷன் கார்டு, 2 புகைப்படங்கள். "
            "30 நாட்களில் சரிபார்ப்பு. ஒப்புகை ரசீதை பாதுகாக்கவும்!"
        ),
        "te": (
            "అక్కా, FORM 1-W BDO కార్యాలయంలో ఉచితంగా లభిస్తుంది. "
            "పత్రాలు: మరణ సర్టిఫికెట్, ఆధార్, బ్యాంక్ పాస్‌బుక్, రేషన్ కార్డ్, 2 ఫోటోలు. "
            "30 రోజులలో తనిఖీ. రసీదు భద్రపరచండి!"
        ),
        "kn": (
            "ಅಕ್ಕ, FORM 1-W BDO ಕಚೇರಿಯಲ್ಲಿ ಉಚಿತವಾಗಿ ಸಿಗುತ್ತದೆ. "
            "ದಾಖಲೆಗಳು: ಮರಣ ಪ್ರಮಾಣಪತ್ರ, ಆಧಾರ್, ಬ್ಯಾಂಕ್ ಪಾಸ್‌ಬುಕ್, ರೇಷನ್ ಕಾರ್ಡ್, 2 ಫೋಟೋಗಳು. "
            "30 ದಿನಗಳಲ್ಲಿ ಪರಿಶೀಲನೆ. ರಸೀದಿ ಸಂರಕ್ಷಿಸಿ!"
        ),
        "hi": (
            "दीदी, FORM 1-W BDO कार्यालय में मुफ्त मिलता है। "
            "दस्तावेज़: मृत्यु प्रमाण पत्र, आधार, बैंक पासबुक, राशन कार्ड, 2 फोटो। "
            "30 दिनों में जांच होगी। रसीद सुरक्षित रखें!"
        ),
        "en": None,
    },
    "old_age": {
        "ta": (
            "அக்கா, 60 வயதுக்கு மேல் இருந்தால் 'வயதானோர் ஓய்வூதியம்' (IGNOAPS) கிடைக்கும். "
            "மாதம் ₹1,000 — விதவை ஓய்வூதியம் போலவே. "
            "BDO அலுவலகத்தில் விண்ணப்பிக்கவும். ஆதார், BPL கார்டு, வங்கி புத்தகம் கொண்டு வாருங்கள்."
        ),
        "te": (
            "అక్కా, 60 ఏళ్ళు పైబడినవారికి వృద్ధాప్య పెన్షన్ (IGNOAPS) వర్తిస్తుంది. "
            "నెలకు ₹1,000 — వితంతు పెన్షన్ మాదిరిగానే. "
            "BDO కార్యాలయంలో దరఖాస్తు చేయండి. ఆధార్, BPL కార్డ్, బ్యాంక్ పాస్‌బుక్ తీసుకురండి."
        ),
        "kn": (
            "ಅಕ್ಕ, 60 ವರ್ಷ ಮೇಲ್ಪಟ್ಟವರಿಗೆ ವೃದ್ಧಾಪ್ಯ ಪಿಂಚಣಿ (IGNOAPS) ಅನ್ವಯಿಸುತ್ತದೆ. "
            "ತಿಂಗಳಿಗೆ ₹1,000 — ವಿಧವಾ ಪಿಂಚಣಿಯಂತೆಯೇ. "
            "BDO ಕಚೇರಿಯಲ್ಲಿ ಅರ್ಜಿ ಸಲ್ಲಿಸಿ. ಆಧಾರ್, BPL ಕಾರ್ಡ್, ಬ್ಯಾಂಕ್ ಪಾಸ್‌ಬುಕ್ ತನ್ನಿ."
        ),
        "hi": (
            "दीदी, 60 वर्ष से अधिक उम्र के लिए वृद्धावस्था पेंशन (IGNOAPS) मिलती है। "
            "महीने में ₹1,000 — विधवा पेंशन जितना ही। "
            "BDO कार्यालय में आवेदन करें। आधार, BPL कार्ड, बैंक पासबुक लाएं।"
        ),
        "en": None,
    },
    "appeal": {
        "ta": (
            "அக்கா, நிராகரிப்பு இறுதி முடிவல்ல! 30 நாட்களுக்குள் மேல்முறையீடு செய்யலாம். "
            "நிராகரிப்பு கடிதத்தை BDO அலுவலகத்தில் பெறுங்கள். "
            "மாவட்ட ஆட்சியர் அலுவலகத்தில் மேல்முறையீடு செய்யுங்கள். 45 நாட்களில் பரிசீலிக்கப்படும்."
        ),
        "te": (
            "అక్కా, తిరస్కరణ తుది నిర్ణయం కాదు! 30 రోజులలోపు అప్పీల్ చేయవచ్చు. "
            "BDO కార్యాలయంలో తిరస్కరణ లేఖ తీసుకోండి. "
            "జిల్లా కలెక్టర్ కార్యాలయంలో అప్పీల్ చేయండి. 45 రోజులలో పరిశీలిస్తారు."
        ),
        "kn": (
            "ಅಕ್ಕ, ತಿರಸ್ಕಾರ ಅಂತಿಮ ನಿರ್ಧಾರ ಅಲ್ಲ! 30 ದಿನಗಳಲ್ಲಿ ಮೇಲ್ಮನವಿ ಸಲ್ಲಿಸಬಹುದು. "
            "BDO ಕಚೇರಿಯಲ್ಲಿ ತಿರಸ್ಕಾರ ಪತ್ರ ಪಡೆಯಿರಿ. "
            "ಜಿಲ್ಲಾ ಕಲೆಕ್ಟರ್ ಕಚೇರಿಯಲ್ಲಿ ಮೇಲ್ಮನವಿ ಸಲ್ಲಿಸಿ. 45 ದಿನಗಳಲ್ಲಿ ಪರಿಶೀಲಿಸಲಾಗುತ್ತದೆ."
        ),
        "hi": (
            "दीदी, अस्वीकृति अंतिम निर्णय नहीं है! 30 दिनों के भीतर अपील कर सकती हैं। "
            "BDO कार्यालय से अस्वीकृति पत्र लें। "
            "जिला कलेक्टर कार्यालय में अपील करें। 45 दिनों में समीक्षा होगी।"
        ),
        "en": None,
    },
}  # end _MULTILINGUAL_SUMMARIES_LEGACY


def _detect_mock_scenario(case: CaseInput) -> str:
    query = (case.query or "").lower()

    # Medical is highest priority — word boundaries avoid "still"→"ill" false positives
    medical_keywords = ["sick", "ill", "disease", "doctor", "hospital", "disability",
                        "kidney", "chronic", "health condition", "நோய்", "மருத்துவர்"]
    if any(re.search(r'\b' + re.escape(kw) + r'\b', query) for kw in medical_keywords):
        return "low"

    # Deadline urgency
    deadline_keywords = ["deadline", "june 30", "june", "last date", "expire", "miss", "when to apply", "ஜூன்"]
    if any(kw in query for kw in deadline_keywords):
        return "deadline"

    # Old age pension
    old_age_keywords = ["old age", "aged", "60 year", "65 year", "70 year", "senior", "elderly",
                        "ignoaps", "old-age pension", "வயதானோர்"]
    if any(kw in query for kw in old_age_keywords):
        return "old_age"

    # Appeal / rejection
    appeal_keywords = ["rejected", "rejection", "appeal", "denied", "not approved", "refused",
                       "நிராகரி", "மேல்முறையீடு"]
    if any(kw in query for kw in appeal_keywords):
        return "appeal"

    # How-to / process questions
    process_keywords = ["how to apply", "how do i", "steps", "process", "procedure", "where to",
                        "what to do", "எப்படி", "என்ன செய்ய"]
    if any(kw in query for kw in process_keywords):
        return "process"

    # Missing Aadhaar as MAIN concern (no income/eligibility context) → medium
    doc_only_keywords = ["don't have aadhaar", "no aadhaar", "missing aadhaar",
                         "aadhaar card", "only id", "ஆதார்"]
    has_income_context = any(kw in query for kw in ["earn", "income", "qualify", "eligible", "rupees", "salary"])
    if any(kw in query for kw in doc_only_keywords) and not has_income_context:
        return "medium"

    return "high"


# ---------------------------------------------------------------------------
# Public orchestrate function
# ---------------------------------------------------------------------------

def orchestrate(
    case: CaseInput,
    retrieval: RetrievalResult,
    demo_mode: bool = False,
    conversation_history: list | None = None,
) -> GemmaResponse:
    """
    Main entry point.
    demo_mode=True  → skip API and return mock (used only for testing / no-key environments).
    demo_mode=False → call real Gemini API; return safe error response on hard failure.
    conversation_history → last N turns for multi-turn context (passed to prompt builder).
    """
    # Force demo when no API key is configured (prevents crashes during local dev)
    use_demo = demo_mode or not GOOGLE_API_KEY.strip()

    if use_demo:
        scenario = _detect_mock_scenario(case)
        logger.info(f"[DEMO] '{scenario}' mock for lang={case.language}")
        base = MOCK_RESPONSES[scenario]
        lang = case.language or "ta"
        regional = MULTILINGUAL_SUMMARIES.get(scenario, {}).get(lang)
        if lang == "ta" and not regional:
            regional = base.tamil_summary
        return base.model_copy(update={
            "regional_summary": regional,
            "tamil_summary": regional if lang == "ta" else base.tamil_summary,
        })

    logger.info(f"[LIVE API] Calling Gemini ({GEMINI_MODEL}) for lang={case.language}")
    try:
        system_prompt = _load_system_prompt()
        user_message  = _build_user_message(case, retrieval, conversation_history)
        raw_response  = _call_gemini(system_prompt, user_message)
        logger.info(f"[LIVE API] Response received ({len(raw_response)} chars)")
        result = _parse_response(raw_response)
        # If Gemini returned no regional_summary (hallucination guard), patch from
        # MULTILINGUAL_SUMMARIES for known scenario patterns
        if not result.regional_summary and case.language != "en":
            scenario = _detect_mock_scenario(case)
            regional = MULTILINGUAL_SUMMARIES.get(scenario, {}).get(case.language)
            if regional:
                result = result.model_copy(update={"regional_summary": regional})
        return result
    except Exception as e:
        logger.error(f"[LIVE API] Failed: {e}. Returning safe error response.")
        return GemmaResponse(
            confidence=0.0,
            confidence_percent=0,
            confidence_band="low",
            domain="out_of_scope",
            worker_guidance=[
                "The AI service is temporarily unavailable. Please retry in a moment.",
                "If the problem persists, call 1800-425-1700 for direct assistance.",
            ],
            citizen_guidance=(
                "We are having trouble connecting to the AI service right now. "
                "Please try your question again in a moment. "
                "If you need immediate help, call 1800-425-1700 (toll-free)."
            ),
            escalation_needed=True,
            escalation_reason="AI service unavailable. Please retry or call 1800-425-1700.",
            evidence_used=[],
            tamil_summary=None,
            regional_summary=None,
        )
