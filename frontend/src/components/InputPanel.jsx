import { useState, useRef, useEffect } from "react";

const LANGUAGES = [
  { code: "ta", label: "தமிழ் (Tamil)",    speechCode: "ta-IN" },
  { code: "te", label: "తెలుగు (Telugu)",  speechCode: "te-IN" },
  { code: "kn", label: "ಕನ್ನಡ (Kannada)",  speechCode: "kn-IN" },
  { code: "hi", label: "हिंदी (Hindi)",     speechCode: "hi-IN" },
  { code: "en", label: "English",            speechCode: "en-IN" },
];

const QUICK_QUERIES = [
  { label: "Am I eligible?",       text: "I am a widow. My husband died last year. I earn ₹3,500 per month doing daily wage work. Do I qualify for the widow pension scheme?" },
  { label: "No Aadhaar card",      text: "I don't have an Aadhaar card. Can I still apply with a ration card?" },
  { label: "Deadline",             text: "When is the last date to apply for the widow pension? I don't want to miss the deadline." },
  { label: "How to apply",         text: "What are the steps to apply for widow pension? Where do I go and what do I bring?" },
  { label: "Old age pension",      text: "I am 63 years old and a widow. Do I qualify for old age pension or widow pension?" },
  { label: "Rejected application", text: "My application was rejected. What can I do? How do I appeal?" },
];

const SPEECH_SUPPORTED =
  typeof window !== "undefined" &&
  ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);

const HISTORY_KEY = "awaaz_query_history";
const MAX_HISTORY = 5;

/* ── SVG Icons ──────────────────────────────────────────────────────────── */
const IconPen = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>
  </svg>
);

const IconDoc = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
    <polyline points="14 2 14 8 20 8"/>
    <line x1="12" y1="18" x2="12" y2="12"/>
    <line x1="9" y1="15" x2="15" y2="15"/>
  </svg>
);

const IconMic = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
    <line x1="12" y1="19" x2="12" y2="23"/>
    <line x1="8" y1="23" x2="16" y2="23"/>
  </svg>
);

const IconSend = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13"/>
    <polygon points="22 2 15 22 11 13 2 9 22 2"/>
  </svg>
);

const TABS = [
  { id: "text",  label: "Type",    Icon: IconPen },
  { id: "image", label: "Upload",  Icon: IconDoc },
  { id: "voice", label: "Voice",   Icon: IconMic },
];

const DEMO_QUERY = {
  lang: "en",
  text: "I am a widow. My husband passed away 8 months ago. I earn ₹3,500 per month doing daily wage work. I don't have an Aadhaar card but I have a ration card. Do I qualify for the widow pension? What documents do I need and when is the last date to apply?",
};

export default function InputPanel({ onSubmit, loading }) {
  const runDemo = () => {
    setLanguage(DEMO_QUERY.lang);
    setInputType("text");
    setText(DEMO_QUERY.text);
    const formData = new FormData();
    formData.append("input_type", "text");
    formData.append("language", DEMO_QUERY.lang);
    formData.append("text", DEMO_QUERY.text);
    onSubmit(formData);
  };
  const [inputType, setInputType] = useState("text");
  const [language, setLanguage]   = useState("ta");
  const [text, setText]           = useState("");
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [imageError, setImageError]     = useState(null);
  const [history, setHistory] = useState(() => {
    try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]"); }
    catch { return []; }
  });

  const [recording, setRecording]         = useState(false);
  const [processing, setProcessing]       = useState(false); // true while browser processes speech
  const [liveTranscript, setLiveTranscript] = useState("");
  const [speechError, setSpeechError]     = useState(null);
  const recognitionRef = useRef(null);

  useEffect(() => () => recognitionRef.current?.abort(), []);

  const loadImage = (file) => {
    if (file.size > 4 * 1024 * 1024) {
      setImageError("Image is too large (max 4 MB). Please resize before uploading.");
      return;
    }
    setImageError(null);
    setImageFile(file);
    const reader = new FileReader();
    reader.onload = (ev) => setImagePreview(ev.target.result);
    reader.readAsDataURL(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file?.type.startsWith("image/")) loadImage(file);
  };

  const startVoice = () => {
    setSpeechError(null);
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { setSpeechError("Voice not supported. Use Chrome or Edge, or type your query."); return; }
    const rec = new SR();
    rec.lang = LANGUAGES.find((l) => l.code === language)?.speechCode || "ta-IN";
    rec.interimResults = true;
    rec.continuous = false;
    rec.maxAlternatives = 1;
    let finalText = "";
    rec.onstart = () => { setRecording(true); setProcessing(false); setLiveTranscript(""); };
    rec.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const t = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalText += t + " ";
        else interim = t;
      }
      setLiveTranscript(finalText + interim);
    };
    rec.onend = () => {
      setRecording(false);
      setProcessing(true); // show spinner while browser finalises
      setLiveTranscript("");
      setTimeout(() => {
        setProcessing(false);
        if (finalText.trim()) { setText(finalText.trim()); setInputType("text"); }
      }, 600);
    };
    rec.onerror = (event) => {
      setRecording(false);
      setProcessing(false);
      setLiveTranscript("");
      if (event.error === "no-speech") setSpeechError("No speech detected. Please try again.");
      else if (event.error === "not-allowed") setSpeechError("Microphone permission denied.");
      else setSpeechError(`Voice error: ${event.error}. Please type instead.`);
    };
    recognitionRef.current = rec;
    rec.start();
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const formData = new FormData();
    formData.append("input_type", inputType === "voice" ? "text" : inputType);
    formData.append("language", language);
    if (inputType === "image" && imageFile) {
      formData.append("file", imageFile);
    } else {
      formData.append("text", text);
      if (text.trim()) {
        const updated = [text.trim(), ...history.filter(q => q !== text.trim())].slice(0, MAX_HISTORY);
        setHistory(updated);
        try { localStorage.setItem(HISTORY_KEY, JSON.stringify(updated)); } catch {}
      }
    }
    onSubmit(formData);
  };

  const removeHistory = (q) => {
    const updated = history.filter(h => h !== q);
    setHistory(updated);
    try { localStorage.setItem(HISTORY_KEY, JSON.stringify(updated)); } catch {}
  };

  const canSubmit =
    !loading && (
      inputType === "text" || inputType === "voice"
        ? text.trim().length > 0
        : !!imageFile
    );

  return (
    <div className="input-panel card">
      <div className="panel-header">
        <h2 className="panel-title">Submit Your Query</h2>
        <p className="panel-hint">Ask in any of the 5 supported languages</p>
      </div>

      {/* Language selector */}
      <div className="field-group">
        <label className="field-label" htmlFor="lang-select">Language</label>
        <select
          id="lang-select"
          className="select-input"
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
        >
          {LANGUAGES.map((l) => (
            <option key={l.code} value={l.code}>{l.label}</option>
          ))}
        </select>
      </div>

      {/* Segmented input type control */}
      <div className="tab-group" role="tablist" aria-label="Input method">
        {TABS.map(({ id, label, Icon }) => (
          <button
            key={id}
            role="tab"
            aria-selected={inputType === id}
            className={`tab-btn ${inputType === id ? "active" : ""}`}
            onClick={() => { setInputType(id); if (id === "voice") setSpeechError(null); }}
            type="button"
          >
            <Icon />
            <span>{label}</span>
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit}>
        {/* TEXT */}
        {inputType === "text" && (
          <>
            <textarea
              className="text-input"
              rows={5}
              placeholder="Type your question in Tamil, Telugu, Kannada, Hindi, or English…"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />

            <div className="quick-queries">
              <span className="quick-label">Quick queries</span>
              <div className="quick-chips">
                {QUICK_QUERIES.map((q) => (
                  <button key={q.label} type="button" className="quick-chip" onClick={() => setText(q.text)}>
                    {q.label}
                  </button>
                ))}
              </div>
            </div>

            {history.length > 0 && (
              <div className="quick-queries query-history">
                <span className="quick-label">Recent</span>
                <div className="quick-chips">
                  {history.map((q, i) => (
                    <span key={i} className="history-chip-wrap">
                      <button type="button" className="quick-chip history-chip" onClick={() => setText(q)} title={q}>
                        {q.length > 32 ? q.slice(0, 32) + "…" : q}
                      </button>
                      <button type="button" className="history-remove" onClick={() => removeHistory(q)} aria-label="Remove">
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {/* IMAGE */}
        {inputType === "image" && (
          <>
            <div className="file-drop-zone" onDrop={handleDrop} onDragOver={(e) => e.preventDefault()}>
              <input type="file" accept="image/*" onChange={(e) => { const f = e.target.files[0]; if (f) loadImage(f); }} className="file-input" id="image-upload" />
              {imagePreview ? (
                <label htmlFor="image-upload" className="file-preview-label">
                  <img src={imagePreview} alt="Form preview" className="image-preview" />
                  <span className="image-change-hint">Click to change image</span>
                </label>
              ) : (
                <label htmlFor="image-upload" className="file-label">
                  <span className="upload-icon">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.5 }}>
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                      <polyline points="14 2 14 8 20 8"/>
                      <line x1="12" y1="18" x2="12" y2="12"/>
                      <line x1="9" y1="15" x2="15" y2="15"/>
                    </svg>
                  </span>
                  <span>Click or drag to upload a government form</span>
                  <span className="file-hint">JPG, PNG · Max 4 MB · Gemini Vision reads all text</span>
                </label>
              )}
            </div>
            {imageError && <p className="speech-error">{imageError}</p>}
          </>
        )}

        {/* VOICE */}
        {inputType === "voice" && (
          <div className="voice-zone">
            {!SPEECH_SUPPORTED ? (
              <div className="voice-unsupported-box">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{color:"var(--text-muted)"}}>
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                  <line x1="12" y1="19" x2="12" y2="23"/>
                  <line x1="8" y1="23" x2="16" y2="23"/>
                  <line x1="1" y1="1" x2="23" y2="23" stroke="var(--red)"/>
                </svg>
                <p className="voice-unsupported-title">Voice not available on this browser</p>
                <p className="voice-unsupported-sub">Safari and Firefox do not support voice input. Use Chrome or Edge — or type your question below.</p>
                <button
                  type="button"
                  className="voice-fallback-btn"
                  onClick={() => setInputType("text")}
                >
                  Switch to typing
                </button>
              </div>
            ) : (
              <>
                <div className={`voice-visualizer ${recording ? "active" : ""}`}>
                  {recording ? (
                    <>
                      <div className="voice-bars">
                        {[...Array(5)].map((_, i) => (
                          <div key={i} className="voice-bar" style={{ animationDelay: `${i * 0.1}s` }} />
                        ))}
                      </div>
                      <p className="voice-listening">Listening…</p>
                    </>
                  ) : (
                    <IconMic />
                  )}
                </div>

                {liveTranscript && <p className="live-transcript">"{liveTranscript}"</p>}

                {processing && (
                  <div className="voice-processing">
                    <span className="voice-proc-spinner" />
                    <span className="voice-proc-label">Processing speech…</span>
                  </div>
                )}

                {!recording && !processing ? (
                  <button type="button" className="record-btn" onClick={startVoice}>Start Speaking</button>
                ) : recording ? (
                  <button type="button" className="record-btn recording" onClick={() => recognitionRef.current?.stop()}>
                    Stop Recording
                  </button>
                ) : null}

                {text && inputType === "voice" && (
                  <div className="transcript-ready">
                    <span className="transcript-tick">✓</span>
                    <span>"{text.slice(0, 80)}{text.length > 80 ? "…" : ""}"</span>
                    <button type="button" className="transcript-edit" onClick={() => setInputType("text")}>Edit</button>
                  </div>
                )}

                <p className="voice-hint">Speak clearly in {LANGUAGES.find((l) => l.code === language)?.label || "your language"}.</p>
              </>
            )}
            {speechError && <p className="speech-error">{speechError}</p>}
          </div>
        )}

        <button type="submit" className="submit-btn" disabled={!canSubmit}>
          {loading ? (
            <span className="btn-loading"><span className="btn-spinner" /> Analysing…</span>
          ) : (
            <span className="btn-loading"><IconSend /> Analyse with Awaaz Relay</span>
          )}
        </button>
      </form>

      <div className="panel-footer">
        <button
          type="button"
          className="demo-run-btn"
          onClick={runDemo}
          disabled={loading}
          title="Auto-fill and submit a real widow pension query"
        >
          ▶ Run Live Demo
        </button>
        <span className="offline-badge">Grounded on 214 verified TN government facts</span>
      </div>
    </div>
  );
}
