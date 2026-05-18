"""
Input processing pipeline: image → OCR text, audio → transcript, text → normalised case.
Falls back gracefully when APIs are unavailable (offline-first design).
"""

import base64
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from schemas import CaseInput

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Language detection (simple heuristic; real apps use langdetect or Google)
# ---------------------------------------------------------------------------

SCRIPT_RANGES = {
    "ta": (0x0B80, 0x0BFF),   # Tamil
    "te": (0x0C00, 0x0C7F),   # Telugu
    "kn": (0x0C80, 0x0CFF),   # Kannada
    "hi": (0x0900, 0x097F),   # Devanagari (Hindi)
}


def detect_language(text: str) -> str:
    if not text:
        return "en"
    counts = {lang: 0 for lang in SCRIPT_RANGES}
    for ch in text:
        cp = ord(ch)
        for lang, (lo, hi) in SCRIPT_RANGES.items():
            if lo <= cp <= hi:
                counts[lang] += 1
                break
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else "en"


# ---------------------------------------------------------------------------
# OCR: image → text
# ---------------------------------------------------------------------------

def ocr_image(image_bytes: bytes, language_hint: str = "ta") -> Tuple[str, float]:
    """
    Returns (extracted_text, confidence_score).
    Priority: Gemini Vision (multimodal) → Google Vision API → Tesseract
    """
    # Best: Gemini multimodal OCR (no extra credentials needed)
    try:
        return _ocr_gemini_vision(image_bytes)
    except Exception as e:
        logger.warning(f"Gemini Vision OCR failed: {e}. Trying Google Vision...")

    # Try Google Vision API
    try:
        return _ocr_google_vision(image_bytes, language_hint)
    except Exception as e:
        logger.warning(f"Google Vision OCR failed: {e}. Falling back to Tesseract.")

    # Last resort: Tesseract local
    try:
        return _ocr_tesseract(image_bytes, language_hint)
    except Exception as e:
        logger.error(f"All OCR methods failed: {e}")
        return ("", 0.0)


def _ocr_gemini_vision(image_bytes: bytes) -> Tuple[str, float]:
    """Use Gemini multimodal to extract text from form image. Retries once on 503."""
    import requests as req
    import base64
    import time

    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        raise RuntimeError("No GOOGLE_API_KEY set")

    # Detect mime type from magic bytes
    mime = "image/jpeg"
    if image_bytes[:4] == b'\x89PNG':
        mime = "image/png"
    elif image_bytes[:4] == b'%PDF':
        raise RuntimeError("PDF not supported by Gemini Vision inline — convert to image first")

    image_b64 = base64.b64encode(image_bytes).decode()
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": (
                    "Extract ALL text from this government form image exactly as written. "
                    "Include every word, number, and field. Return only the extracted text, "
                    "no commentary, no formatting."
                )},
                {"inline_data": {"mime_type": mime, "data": image_b64}},
            ]
        }],
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 1024},
    }

    # Try gemini-2.5-flash, fall back to gemini-2.0-flash-lite on 503
    for ocr_model in ["gemini-2.5-flash", "gemini-2.0-flash-lite"]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{ocr_model}:generateContent"
        try:
            resp = req.post(url, params={"key": api_key}, json=payload, timeout=30)
            if resp.status_code == 503:
                logger.warning(f"OCR model {ocr_model} returned 503, trying next...")
                time.sleep(1)
                continue
            resp.raise_for_status()
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            logger.info(f"Gemini Vision OCR ({ocr_model}) extracted {len(text)} chars")
            return (text.strip(), 0.95)
        except Exception as e:
            logger.warning(f"OCR model {ocr_model} failed: {e}")
            continue

    raise RuntimeError("All Gemini Vision OCR models failed")


def _ocr_google_vision(image_bytes: bytes, language_hint: str) -> Tuple[str, float]:
    from google.cloud import vision  # type: ignore

    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_bytes)
    image_context = vision.ImageContext(language_hints=[language_hint, "en"])
    response = client.document_text_detection(image=image, image_context=image_context)

    if response.error.message:
        raise RuntimeError(response.error.message)

    full_text = response.full_text_annotation.text
    # Approximate confidence from per-symbol scores
    symbols = [
        s for page in response.full_text_annotation.pages
        for block in page.blocks
        for para in block.paragraphs
        for word in para.words
        for s in word.symbols
    ]
    avg_conf = sum(s.confidence for s in symbols) / len(symbols) if symbols else 0.0
    return (full_text, avg_conf)


def _ocr_tesseract(image_bytes: bytes, language_hint: str) -> Tuple[str, float]:
    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore
    import io

    lang_map = {"ta": "tam", "te": "tel", "kn": "kan", "en": "eng"}
    tess_lang = f"{lang_map.get(language_hint, 'tam')}+eng"

    image = Image.open(io.BytesIO(image_bytes))
    text = pytesseract.image_to_string(image, lang=tess_lang)
    # Tesseract does not return a confidence score per call; return 0.75 as default
    return (text.strip(), 0.75)


# ---------------------------------------------------------------------------
# Speech-to-text: audio → transcript
# ---------------------------------------------------------------------------

def transcribe_audio(audio_bytes: bytes, language_code: str = "ta-IN") -> Tuple[str, float]:
    """
    Returns (transcript, confidence).
    Tries Google Cloud Speech-to-Text; falls back to a stub for offline/demo.
    """
    try:
        return _transcribe_google_speech(audio_bytes, language_code)
    except Exception as e:
        logger.warning(f"Google Speech-to-Text failed: {e}. Using stub transcript.")
        return _stub_transcript(language_code)


def _transcribe_google_speech(audio_bytes: bytes, language_code: str) -> Tuple[str, float]:
    from google.cloud import speech  # type: ignore

    client = speech.SpeechClient()
    audio = speech.RecognitionAudio(content=audio_bytes)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code=language_code,
        alternative_language_codes=["en-IN"],
        enable_automatic_punctuation=True,
    )
    response = client.recognize(config=config, audio=audio)
    if not response.results:
        return ("", 0.0)

    best = response.results[0].alternatives[0]
    return (best.transcript, best.confidence)


def _stub_transcript(language_code: str) -> Tuple[str, float]:
    # Offline demo stub — returns sample Tamil query
    stub = (
        "இந்த படிவத்தில் 'வருடாந்திர வருமானம்' என்பது என்ன? "
        "நான் தினசரி வேலை செய்கிறேன். என்னுடைய வருமானம் மாதம் 3500 ரூபாய். "
        "விதவை ஓய்வூதியத்திற்கு நான் தகுதியானவளா?"
    )
    return (stub, 0.85)


# ---------------------------------------------------------------------------
# Text normalisation
# ---------------------------------------------------------------------------

def normalise_text(raw_text: str) -> str:
    """Basic cleanup: strip extra whitespace, remove null bytes."""
    return " ".join(raw_text.replace("\x00", "").split())


# ---------------------------------------------------------------------------
# Main entry point: build CaseInput from raw inputs
# ---------------------------------------------------------------------------

def build_case(
    input_type: str,
    image_bytes: Optional[bytes] = None,
    audio_bytes: Optional[bytes] = None,
    text: Optional[str] = None,
    language_hint: str = "ta",
) -> CaseInput:
    """
    Converts raw inputs into a structured CaseInput object.
    """
    extracted_text = ""
    raw_image_b64 = None
    raw_audio_b64 = None

    if input_type == "image" and image_bytes:
        raw_image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        ocr_text, _ = ocr_image(image_bytes, language_hint)
        extracted_text = normalise_text(ocr_text)

    elif input_type == "voice" and audio_bytes:
        raw_audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        lang_code_map = {"ta": "ta-IN", "te": "te-IN", "kn": "kn-IN", "en": "en-IN"}
        transcript, _ = transcribe_audio(audio_bytes, lang_code_map.get(language_hint, "ta-IN"))
        extracted_text = normalise_text(transcript)

    elif input_type == "text" and text:
        extracted_text = normalise_text(text)

    # Trust the user's explicit dropdown selection; auto-detect only as fallback
    # when the text contains clear non-Latin script (overrides a wrong hint)
    auto = detect_language(extracted_text) if extracted_text else language_hint
    detected_lang = auto if auto != "en" else language_hint

    return CaseInput(
        case_id=str(uuid.uuid4()),
        input_type=input_type,
        raw_image=raw_image_b64,
        raw_audio=raw_audio_b64,
        raw_text=extracted_text,
        language=detected_lang,
        query=extracted_text,
        metadata={
            "upload_time": datetime.now(timezone.utc).isoformat(),
            "user_role": "community_worker",
        },
    )
