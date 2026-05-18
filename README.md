# Awaaz Relay

**Multilingual AI copilot that helps frontline welfare workers in Tamil Nadu guide citizens through government pension applications in their own language.**

---

## The Problem

Over 10 million citizens in Tamil Nadu are eligible for government welfare pensions like widow pension, old age pension, disability pension, and nine other schemes. But the gap between eligibility and enrollment is huge.

Frontline community workers who connect citizens to these schemes face three hard problems:

1. **Language** — Forms and guidelines are in English. Citizens speak Tamil, Telugu, Kannada, or Hindi.
2. **Complexity** — Each scheme has different age cutoffs, income limits, document requirements, and deadlines.
3. **Verification** — Workers can't risk giving wrong advice. A wrong answer means a rejected application and an 8-month wait.

Awaaz Relay solves all three at once.

---

## What It Does

A worker submits a query by typing, uploading a photo of a government form, or speaking in their language. The system:

1. Reads the input (OCR for images via Gemini Vision, speech-to-text for voice)
2. Searches 214 verified government facts using semantic similarity + BM25 keyword retrieval
3. Sends the retrieved facts + query to Gemini to generate a structured response
4. Returns a **dual output** an actionable checklist for the worker, and a plain-language explanation for the citizen in the correct language

Every response shows the source facts it was grounded on. If confidence drops below 40%, guidance is suppressed and the helpline is shown instead.

---

## Key Features

| Feature | Detail |
|---|---|
| **Multimodal input** | Text, government form image (OCR), voice recording |
| **5 languages** | Tamil, Telugu, Kannada, Hindi, English |
| **12 welfare schemes** | Widow, Old Age, Disability, Deserted Women, Transgender, Girl Child, and more |
| **214 grounded facts** | Sourced from official Tamil Nadu government portals (2024–2026) |
| **Hybrid retrieval** | Gemini `gemini-embedding-001` semantic search + BM25 keyword fallback |
| **Model chain** | `gemini-2.0-flash-lite` → `gemini-2.0-flash` → `gemini-2.5-flash` (auto-fallback) |
| **Multi-turn context** | Conversation history passed to Gemini — up to 8 turns |
| **Safety gates** | Confidence < 40% suppresses answer and shows helpline |
| **Dark mode** | Persistent preference — field workers use phones outdoors |
| **Mobile responsive** | Single-column layout below 768px |

---

## Architecture

```
User (text / image / voice)
        │
        ▼
┌───────────────────────────────────────────────────────── ┐
│  React + Vite  (Vercel)                                  │
│  InputPanel → App.jsx → ConfidenceCard, WorkerCard, …    │
└────────────────────┬──────────────────────────────────── ┘
                     │ POST /analyze (FormData)
                     ▼
┌───────────────────────────────────────────────────────── ┐
│  FastAPI  (Render)                                       │
│                                                          │
│  input_processor.py  →  CaseInput                        │
│        OCR (Gemini Vision), language detection           │
│                                                          │
│  retriever.py  →  RetrievalResult                        │
│        Semantic: cosine on gemini-embedding-001 vectors  │
│        Fallback: BM25 with category boost                │
│                                                          │
│  gemma_orchestrator.py  →  GemmaResponse                 │
│        Gemini model chain, structured JSON output        │
│                                                          │
│  safety_scorer.py  →  SafetyScorerOutput                 │
│        Confidence blend, escalation gate, evidence panel │
└───────────────────────────────────────────────────────── ┘
```

**Confidence formula:** `(retrieval_score × 0.6) + (gemini_self_estimate × 0.4)`

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI | Gemini 2.0 Flash, Gemini 2.5 Flash, gemini-embedding-001 |
| Backend | Python 3.11, FastAPI, Pydantic v2, SQLite |
| Frontend | React 18, Vite, Plus Jakarta Sans |
| Retrieval | Semantic (3072-dim cosine) + BM25 hybrid |
| Deployment | Render (backend), Vercel (frontend), Docker |
| CI | GitHub Actions — pytest + vitest + Docker build |
| Tests | 70 tests (48 backend unit + integration, 22 frontend component) |

---

## Knowledge Base

214 facts extracted and verified from official Tamil Nadu government sources:

| Category | Facts | Source |
|---|---|---|
| Eligibility | 39 | TN Social Welfare Dept guidelines |
| Documents | 39 | District portal fact sheets |
| Process | 38 | CRA Tamil Nadu, e-Sevai portal |
| Benefits | 25 | Official scheme circulars 2024–2026 |
| Deadline | 23 | Annual enrollment notices |
| Income | 13 | Income calculation guidance notes |
| Contact / Escalation | 14 | TN government contact directory |

All 214 facts have `gemini-embedding-001` vectors pre-computed for instant semantic retrieval.

---

## Local Setup

### Prerequisites
- Python 3.10+
- Node 18+
- Google API key with Gemini enabled — [get one free](https://aistudio.google.com/apikey)

### Backend

```bash
cd backend
python -m pip install -r requirements.txt

cp ../.env.example ../.env
# Open .env and set GOOGLE_API_KEY

python -m uvicorn main:app --reload
# Runs at http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Runs at http://localhost:5173
```

### Run Tests

```bash
# Backend — 48 tests
cd backend && pytest tests/ -v

# Frontend — 22 tests
cd frontend && npm test
```

### Docker (full stack)

```bash
cp .env.example .env
# Set GOOGLE_API_KEY in .env
docker compose up --build
```

---

## API

### `POST /analyze`

`multipart/form-data`

| Field | Type | Description |
|---|---|---|
| `input_type` | string | `text`, `image`, or `voice` |
| `language` | string | `ta` `te` `kn` `hi` `en` |
| `text` | string | Query text |
| `file` | file | Government form image (JPG/PNG) |
| `conversation_context` | string | JSON array of prior turns |

### `POST /feedback`

```json
{ "case_id": "...", "rating": "up", "query_summary": "...", "confidence_percent": 85 }
```

### `GET /health` · `GET /config` · `GET /kb/stats`

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_API_KEY` | Yes | Gemini API key |
| `DEMO_MODE` | No | `true` for mock responses without API calls |
| `CORS_ORIGINS` | No | Comma-separated allowed origins |

---

## Project Structure

```
awaaz-relay/
├── backend/
│   ├── main.py                  FastAPI app, SQLite rate limiting, lifespan
│   ├── input_processor.py       Multimodal input → CaseInput
│   ├── retriever.py             Hybrid retrieval (semantic + BM25)
│   ├── gemma_orchestrator.py    Gemini model chain, JSON parser
│   ├── safety_scorer.py         Confidence blend, safety gates
│   ├── schemas.py               Pydantic models
│   ├── data_extraction/         KB curation and embedding scripts
│   ├── prompts/system_prompt.txt
│   ├── pytest.ini
│   ├── requirements.txt
│   ├── Dockerfile
│   └── tests/                   48 tests
├── frontend/
│   ├── src/
│   │   ├── App.jsx              Main app, conversation history, dark mode
│   │   ├── components/          8 UI components
│   │   └── test/                22 Vitest tests
│   ├── nginx.conf
│   ├── Dockerfile
│   └── vercel.json
├── data/
│   ├── knowledge_base.json      214 welfare facts
│   ├── multilingual_summaries.json  Pre-verified translations
│   └── government_sources/      Official TN government PDFs
├── render.yaml
├── docker-compose.yml
├── .env.example
└── .github/workflows/ci.yml
```

---

## Safety Design

- Confidence < 40% then the answer is suppressed, helpline number shown
- Every response shows source rule IDs and confidence scores
- No hallucination without retrieval grounding model chain only generates after facts are retrieved
- Explicit disclaimer on every response: not legal advice
- Rate limiting: 20 requests per minute per IP, persisted to SQLite

**Helpline:** 1800-425-1700 (toll-free, Mon–Sat 9 AM–5 PM)

---

## Supported Languages

Tamil (`ta`) · Telugu (`te`) · Kannada (`kn`) · Hindi (`hi`) · English (`en`)

Pre-verified regional summaries cover all 13 common query scenarios in all 5 languages.
