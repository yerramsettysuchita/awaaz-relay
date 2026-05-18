#!/usr/bin/env python3
"""
Extract structured facts from official government PDF documents.

Usage:
  1. Place PDFs in data/government_sources/
  2. Run: python backend/data_extraction/pdf_extractor.py
  3. Review data/knowledge_base_from_pdfs.json
  4. Merge good facts into data/knowledge_base.json

Download PDFs from:
  • Tamil Nadu Pension Dept  → https://www.tnpension.tn.gov.in/
  • Ministry of Social Justice → https://socialjustice.gov.in/
  • NFSA                      → https://nfsa.gov.in/

Requires: pip install pdfplumber
"""

import json
import os
import re
import sys
import hashlib
from pathlib import Path
from datetime import datetime

try:
    import pdfplumber
except ImportError:
    print("ERROR: pdfplumber not installed. Run: pip install pdfplumber")
    sys.exit(1)

SOURCES_DIR = Path(__file__).parent.parent.parent / "data" / "government_sources"
OUTPUT_PATH = Path(__file__).parent.parent.parent / "data" / "knowledge_base_from_pdfs.json"

CATEGORY_SIGNALS = {
    "eligibility": ["eligible", "eligibility", "qualify", "criteria", "must be", "shall be", "condition", "widow"],
    "documents":   ["document", "certificate", "aadhaar", "proof", "attested", "original", "submit", "attach"],
    "income":      ["income", "annual income", "salary", "earnings", "below", "lakh", "rupees", "bpl", "poverty"],
    "deadline":    ["deadline", "last date", "within", "days", "month", "annual", "june", "march", "expire"],
    "benefits":    ["amount", "pension", "₹", "rs.", "rupees", "monthly", "benefit", "payment", "1000", "500"],
    "process":     ["apply", "application", "submit", "office", "block", "taluk", "form", "procedure", "step"],
    "contact":     ["contact", "helpline", "phone", "toll-free", "call", "address", "1800"],
    "appeal":      ["appeal", "rejection", "grievance", "complaint", "redressal", "district collector", "reject"],
}


def detect_category(text: str) -> str:
    text_lower = text.lower()
    for cat, signals in CATEGORY_SIGNALS.items():
        if any(s in text_lower for s in signals):
            return cat
    return "general"


def is_useful_line(text: str) -> bool:
    text = text.strip()
    if len(text) < 35:
        return False
    if text.isupper() and len(text) < 80:
        return False  # Skip ALL-CAPS headings
    if re.match(r"^[\d\.\-\*\s]+$", text):
        return False  # Skip pure number/bullet lines
    if len(text.split()) < 5:
        return False  # Skip very short fragments
    return True


def extract_from_pdf(pdf_path: Path, source_name: str) -> list:
    facts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                chunks = re.split(r"(?<=[.!?])\s+|\n{2,}", text)
                for chunk in chunks:
                    chunk = " ".join(chunk.split())  # normalise whitespace
                    if not is_useful_line(chunk):
                        continue
                    uid = hashlib.md5(chunk.encode()).hexdigest()[:8].upper()
                    rule_id = f"PDF_{source_name[:8].upper()}_{uid}"
                    facts.append({
                        "rule_id":         rule_id,
                        "category":        detect_category(chunk),
                        "text":            chunk,
                        "source":          f"{pdf_path.name} — Tamil Nadu Social Welfare Dept (official), p.{page_num}",
                        "confidence_base": 0.92,
                        "tags":            [detect_category(chunk), "pdf_extracted", "official_government"],
                    })
    except Exception as e:
        print(f"  ERROR extracting {pdf_path.name}: {e}")
    return facts


def main():
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = list(SOURCES_DIR.glob("*.pdf"))

    if not pdfs:
        print(f"No PDFs found in {SOURCES_DIR}")
        print("\nDownload official PDFs and place them there:")
        print("  1. Go to https://www.tnpension.tn.gov.in/")
        print("  2. Download: Widow Pension Form, Eligibility Guide, Process Document")
        print("  3. Re-run this script")
        return

    all_facts = []
    for pdf in pdfs:
        print(f"Extracting: {pdf.name} …")
        source_name = re.sub(r"[^a-zA-Z0-9]", "_", pdf.stem)
        facts = extract_from_pdf(pdf, source_name)
        all_facts.extend(facts)
        print(f"  -> {len(facts)} facts extracted")

    # Deduplicate by text content
    seen = set()
    unique_facts = []
    for f in all_facts:
        key = f["text"][:80]
        if key not in seen:
            seen.add(key)
            unique_facts.append(f)

    output = {
        "metadata": {
            "extracted_from": [p.name for p in pdfs],
            "extraction_date": datetime.now().isoformat(),
            "total_facts": len(unique_facts),
            "source_type": "official_government_pdfs",
            "note": "Review facts before merging into knowledge_base.json",
        },
        "facts": unique_facts,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nDone: {len(unique_facts)} unique facts -> {OUTPUT_PATH}")
    print("Next: review the file, then run merge_kb.py or manually add to knowledge_base.json")


if __name__ == "__main__":
    main()
