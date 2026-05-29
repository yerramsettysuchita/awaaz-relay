import { useState, useEffect, useRef } from "react";
import InputPanel from "./components/InputPanel";
import ConfidenceCard from "./components/ConfidenceCard";
import WorkerGuidanceCard from "./components/WorkerGuidanceCard";
import CitizenGuidanceCard from "./components/CitizenGuidanceCard";
import EvidencePanel from "./components/EvidencePanel";
import EscalationCard from "./components/EscalationCard";
import ErrorBoundary from "./components/ErrorBoundary";
import "./index.css";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const StepIcon = ({ d }) => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
);

const LOADING_STEPS = [
  { id: "input",     label: "Processing input…",         iconD: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M12 18v-6 M9 15h6" },
  { id: "retrieval", label: "Searching knowledge base…", iconD: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z M21 21l-4.35-4.35" },
  { id: "ai",        label: "Generating AI response…",   iconD: "M12 2L2 7l10 5 10-5-10-5z M2 17l10 5 10-5 M2 12l10 5 10-5" },
];

export default function App() {
  const [result, setResult]   = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);
  const [loadStep, setLoadStep] = useState(0);
  const [serverStatus, setServerStatus] = useState("unknown"); // "ok" | "starting" | "offline" | "unknown"
  const [kbConfig, setKbConfig] = useState({ facts_count: null, schemes_count: 6, languages_count: 5 });
  const [feedback, setFeedback]   = useState(null); // "up" | "down" | null
  const [conversationHistory, setConversationHistory] = useState([]); // multi-turn context
  const [kbStats, setKbStats] = useState(null); // live category breakdown from /kb/stats
  const [darkMode, setDarkMode]   = useState(() => localStorage.getItem("awaaz_theme") === "dark");
  const lastCaseIdRef = useRef(null); // tracks case_id for feedback submission
  const stepTimers = useRef([]);
  const resultRef = useRef(null);

  // Server health polling — retry with backoff so a cold-start shows "Starting up" not "offline"
  useEffect(() => {
    let retries = 0;
    const checkHealth = () => {
      fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(8000) })
        .then((r) => r.ok ? r.json() : null)
        .then((data) => {
          if (!data) {
            retries++;
            setServerStatus(retries <= 4 ? "starting" : "offline");
            return;
          }
          retries = 0;
          setServerStatus(data.status === "ok" ? "ok" : "starting");
          if (data.kb_facts) setKbConfig((prev) => ({ ...prev, facts_count: data.kb_facts }));
        })
        .catch(() => {
          retries++;
          setServerStatus(retries <= 4 ? "starting" : "offline");
        });
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30_000);
    return () => clearInterval(interval);
  }, []);

  // Apply dark mode to document root
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", darkMode ? "dark" : "light");
    localStorage.setItem("awaaz_theme", darkMode ? "dark" : "light");
  }, [darkMode]);

  // Fetch dynamic KB config on mount
  useEffect(() => {
    fetch(`${API_BASE}/config`)
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data) setKbConfig(data); })
      .catch(() => {});
    fetch(`${API_BASE}/kb/stats`)
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data) setKbStats(data); })
      .catch(() => {});
  }, []);

  const clearTimers = () => {
    stepTimers.current.forEach(clearTimeout);
    stepTimers.current = [];
  };

  const handleSubmit = async (formData) => {
    setLoading(true);
    setError(null);
    setResult(null);
    setLoadStep(0);
    setFeedback(null);
    clearTimers();

    // Attach conversation context for multi-turn awareness
    if (conversationHistory.length > 0) {
      formData.append("conversation_context", JSON.stringify(conversationHistory));
    }

    // Animate loading steps
    stepTimers.current.push(setTimeout(() => setLoadStep(1), 300));
    stepTimers.current.push(setTimeout(() => setLoadStep(2), 700));

    try {
      const res = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        body: formData,
      });

      if (res.status === 429) {
        throw new Error("Too many requests. Please wait one minute and try again. / அதிகமான கோரிக்கைகள். ஒரு நிமிடம் காத்திருந்து மீண்டும் முயற்சிக்கவும்.");
      }
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || `Server error ${res.status}`);
      }

      const data = await res.json();
      setResult(data);
      lastCaseIdRef.current = data.case_id;

      // Append this turn to conversation history — capped at 8 turns to prevent prompt bloat
      const MAX_TURNS = 8;
      const rawQuery = data.input_summary.replace(/^\[(?:TEXT|IMAGE|VOICE)\]\s*/i, "");
      setConversationHistory((prev) => [
        ...prev.slice(-(MAX_TURNS - 1)),
        {
          query: rawQuery.slice(0, 200),
          domain: data.gemma.domain,
          confidence_percent: data.safety.confidence_percent,
          guidance_summary: data.gemma.citizen_guidance.slice(0, 150),
        },
      ]);

      // Scroll to results
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 100);
    } catch (err) {
      setError(err.message || "Something went wrong. Please try again.");
    } finally {
      clearTimers();
      setLoading(false);
      setLoadStep(0);
    }
  };

  const handleNewQuery = () => {
    setResult(null);
    setError(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleResetConversation = () => {
    setConversationHistory([]);
    setResult(null);
    setError(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handlePrint = () => window.print();

  const language = result?.language || "ta";

  const statusLabel = { ok: "Ready", starting: "Starting up…", offline: "Server offline", unknown: "Checking…" }[serverStatus];
  const statusClass = { ok: "online", starting: "starting", offline: "offline", unknown: "offline" }[serverStatus];

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-content">
          <div>
            <h1 className="app-title">Awaaz Relay</h1>
            <p className="app-subtitle">Field Intelligence Copilot for Pension and Welfare Applications</p>
          </div>
          <div className="header-badges" role="region" aria-label="System status">
            <span className={`online-badge ${statusClass}`} title={serverStatus === "starting" ? "Server is initialising — first query may be slower" : undefined}>
              <span className="badge-dot" />
              {statusLabel}
            </span>
            <span className="scheme-badge">
              {kbConfig.facts_count !== null ? kbConfig.facts_count : "…"} Facts · {kbConfig.schemes_count} Schemes · {kbConfig.languages_count} Languages
            </span>
            <button
              className="dark-toggle"
              onClick={() => setDarkMode((d) => !d)}
              aria-label={darkMode ? "Switch to light mode" : "Switch to dark mode"}
              title={darkMode ? "Light mode" : "Dark mode"}
            >
              {darkMode ? (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
                  <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                  <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
                  <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
                </svg>
              ) : (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
                </svg>
              )}
              <span>{darkMode ? "Light" : "Dark"}</span>
            </button>
          </div>
        </div>
      </header>

      <main className="app-main" id="main-content" aria-label="Query submission and results">
        <section className="left-panel" aria-label="Submit a query">
          <InputPanel onSubmit={handleSubmit} loading={loading} />

          {error && (
            <div className="error-card card">
              <strong>Error:</strong> {error}
            </div>
          )}
        </section>

        <section className="right-panel" ref={resultRef} aria-label="Query results" aria-live="polite">
          {/* Loading state */}
          {loading && (
            <div className="loading-card card">
              <div className="loading-title">Analysing your query…</div>
              <div className="loading-steps">
                {LOADING_STEPS.map((step, i) => (
                  <div
                    key={step.id}
                    className={`loading-step ${
                      i < loadStep ? "done" : i === loadStep ? "active" : "pending"
                    }`}
                  >
                    <span className="step-icon">
                      {i < loadStep
                        ? <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                        : <StepIcon d={step.iconD} />
                      }
                    </span>
                    <span className="step-label">{step.label}</span>
                    {i === loadStep && <span className="step-spinner" />}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Results */}
          {result && !loading && (
            <ErrorBoundary>
              {/* Action bar */}
              <div className="action-bar">
                <button className="action-btn secondary" onClick={handleNewQuery}>
                  New Query
                </button>
                {conversationHistory.length > 1 && (
                  <button
                    className={`action-btn secondary ${conversationHistory.length >= 7 ? "warn-btn" : ""}`}
                    onClick={handleResetConversation}
                    title={conversationHistory.length >= 8 ? "Context is full — reset to start a fresh conversation" : "Clear conversation memory and start fresh"}
                  >
                    {conversationHistory.length >= 8 ? "Context full — Reset" : `Reset (${conversationHistory.length} turns)`}
                  </button>
                )}
                <button className="action-btn print" onClick={handlePrint}>
                  Print / Save PDF
                </button>
              </div>

              {/* Conversation thread — shows prior turns so user knows context is active */}
              {conversationHistory.length > 1 && (
                <div className="conversation-thread" aria-label="Conversation context">
                  <div className="thread-header">
                    <span className="thread-title">Conversation context</span>
                    <span className="thread-count">{conversationHistory.length - 1} prior {conversationHistory.length - 1 === 1 ? "turn" : "turns"}</span>
                    <span className={`thread-limit-badge ${conversationHistory.length >= 7 ? "warn" : ""}`}>
                      {conversationHistory.length}/8 turns
                    </span>
                  </div>
                  <ol className="thread-list">
                    {conversationHistory.slice(0, -1).map((turn, i) => {
                      const bandClass = turn.confidence_percent >= 70 ? "high" : turn.confidence_percent >= 40 ? "medium" : "low";
                      return (
                        <li key={i} className="thread-turn">
                          <span className="thread-q">Q{i + 1}</span>
                          <span className="thread-query">{turn.query.length > 80 ? turn.query.slice(0, 80) + "…" : turn.query}</span>
                          <span className={`thread-band thread-band--${bandClass}`}>
                            {turn.domain?.replace(/_/g, " ")} · {turn.confidence_percent}%
                          </span>
                        </li>
                      );
                    })}
                  </ol>
                </div>
              )}

              {/* Confidence */}
              <ConfidenceCard
                band={result.safety.confidence_band}
                percent={result.safety.confidence_percent}
                processingMs={result.processing_time_ms}
              />

              {/* Escalation */}
              {result.safety.escalate_immediately && (
                <EscalationCard reason={result.gemma.escalation_reason} />
              )}

              {/* Dual output: worker + citizen */}
              {result.safety.safe_to_answer && (
                <div className="dual-output">
                  <WorkerGuidanceCard
                    guidance={result.gemma.worker_guidance}
                    domain={result.gemma.domain}
                    escalationNeeded={result.gemma.escalation_needed}
                    escalationReason={result.gemma.escalation_reason}
                  />
                  <CitizenGuidanceCard
                    guidance={result.gemma.citizen_guidance}
                    regionalSummary={result.gemma.regional_summary}
                    tamilSummary={result.gemma.tamil_summary}
                    language={language}
                  />
                </div>
              )}

              {/* Medium confidence — show content but with warning */}
              {!result.safety.safe_to_answer && !result.safety.escalate_immediately && (
                <div className="dual-output">
                  <WorkerGuidanceCard
                    guidance={result.gemma.worker_guidance}
                    domain={result.gemma.domain}
                    escalationNeeded={result.gemma.escalation_needed}
                    escalationReason={result.gemma.escalation_reason}
                  />
                  <CitizenGuidanceCard
                    guidance={result.gemma.citizen_guidance}
                    regionalSummary={result.gemma.regional_summary}
                    tamilSummary={result.gemma.tamil_summary}
                    language={language}
                  />
                </div>
              )}

              {/* Evidence */}
              <EvidencePanel
                evidence={result.safety.evidence_panel}
                disclaimer={result.safety.disclaimer}
                showWarning={result.safety.show_warning}
              />

              {/* Feedback bar — POSTs to /feedback for persistence */}
              <div className="feedback-bar">
                <span className="feedback-label">Was this helpful?</span>
                {["up", "down"].map((rating) => (
                  <button
                    key={rating}
                    className={`feedback-btn ${feedback === rating ? "active" : ""}`}
                    disabled={feedback !== null}
                    onClick={() => {
                      setFeedback(rating);
                      fetch(`${API_BASE}/feedback`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                          case_id: lastCaseIdRef.current || "unknown",
                          rating,
                          query_summary: result?.input_summary?.slice(0, 120),
                          confidence_percent: result?.safety?.confidence_percent,
                        }),
                      }).catch(() => {}); // fire-and-forget; UI already updated
                    }}
                    aria-pressed={feedback === rating}
                  >
                    {rating === "up" ? "👍 Yes" : "👎 Not quite"}
                  </button>
                ))}
                {feedback && (
                  <span className="feedback-thanks">
                    {feedback === "up" ? "Thank you! Glad this helped." : "Thank you. We'll keep improving."}
                  </span>
                )}
              </div>
            </ErrorBoundary>
          )}

          {/* Empty state — live KB insights */}
          {!result && !loading && !error && (
            <div className="empty-state">
              {/* Impact stats */}
              <div className="impact-stats">
                <div className="impact-stat">
                  <span className="impact-num">10M+</span>
                  <span className="impact-label">Eligible citizens</span>
                </div>
                <div className="impact-stat">
                  <span className="impact-num">12</span>
                  <span className="impact-label">Welfare schemes</span>
                </div>
                <div className="impact-stat">
                  <span className="impact-num">214</span>
                  <span className="impact-label">Verified facts</span>
                </div>
                <div className="impact-stat">
                  <span className="impact-num">5</span>
                  <span className="impact-label">Languages</span>
                </div>
              </div>

              <h3 className="empty-title">Ready to help</h3>
              <p className="empty-text">
                Submit a query on the left — type, upload a government form image, or speak in Tamil, Telugu, Kannada, Hindi, or English.
              </p>

              {/* How it works */}
              <div className="how-it-works">
                <div className="hiw-step">
                  <span className="hiw-num">1</span>
                  <div>
                    <strong>Ask in any language</strong>
                    <p>Type, speak, or upload a government form photo</p>
                  </div>
                </div>
                <div className="hiw-step">
                  <span className="hiw-num">2</span>
                  <div>
                    <strong>AI searches 214 facts</strong>
                    <p>Hybrid retrieval finds the most relevant official rules</p>
                  </div>
                </div>
                <div className="hiw-step">
                  <span className="hiw-num">3</span>
                  <div>
                    <strong>Dual output returned</strong>
                    <p>Worker checklist + plain-language explanation for the citizen</p>
                  </div>
                </div>
              </div>

              {/* Live scheme pills from config */}
              <div className="scheme-pills">
                {(kbConfig.schemes_list || ["Widow Pension", "Old Age Pension", "Disability Pension", "Deserted Women", "IGNOAPS", "CMUPT"]).map((s) => (
                  <span key={s} className="scheme-pill">{s}</span>
                ))}
              </div>

              {/* Live KB stats panel */}
              {kbStats && (
                <div className="kb-insights-panel">
                  <div className="kb-insights-header">
                    <span className="kb-insights-title">Knowledge Base</span>
                    <span className="kb-insights-meta">
                      {kbStats.total_facts} facts
                      {kbStats.last_updated && ` · Updated ${kbStats.last_updated}`}
                    </span>
                  </div>
                  <div className="kb-insights-grid">
                    {Object.entries(kbStats.categories || {})
                      .sort((a, b) => b[1] - a[1])
                      .slice(0, 9)
                      .map(([cat, count]) => (
                        <div key={cat} className="kb-insight-row">
                          <span className="kb-cat-label">{cat.replace(/_/g, " ")}</span>
                          <span className="kb-cat-bar-wrap">
                            <span
                              className="kb-cat-bar"
                              style={{ width: `${Math.round((count / kbStats.total_facts) * 100)}%` }}
                            />
                          </span>
                          <span className="kb-cat-count">{count}</span>
                        </div>
                      ))}
                  </div>
                  {kbStats.embedded_facts > 0 && (
                    <div className="kb-insights-footer">
                      <span className="kb-retrieval-badge semantic">
                        {kbStats.embedded_facts} semantic
                      </span>
                      {kbStats.bm25_only_facts > 0 && (
                        <span className="kb-retrieval-badge bm25">
                          {kbStats.bm25_only_facts} BM25
                        </span>
                      )}
                      <span className="kb-retrieval-note">retrieval methods active</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </section>
      </main>

      {/* Print-only footer */}
      <div className="print-footer">
        <p>Generated by Awaaz Relay · Field Intelligence Copilot for Tamil Nadu Welfare Pensions</p>
        <p>For official decisions, contact the Block Development Office or call 1800-425-1700</p>
      </div>
    </div>
  );
}
