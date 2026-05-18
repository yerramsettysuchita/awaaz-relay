import { useEffect, useState } from "react";

const BAND_CONFIG = {
  high: {
    color: "#4a7c59",
    bg: "#eef5f0",
    border: "#4a7c59",
    icon: "✓",
    label: "High Confidence",
    message: "Answer is well-supported by official government sources.",
    detail: "The information retrieved closely matches your query. You can proceed with confidence, though always confirm final decisions with the office.",
  },
  medium: {
    color: "#b5860d",
    bg: "#fdf8ec",
    border: "#b5860d",
    icon: "⚠",
    label: "Medium Confidence",
    message: "Some uncertainty. Verify with the Block Development Office before submitting.",
    detail: "Parts of this query are not fully covered by the knowledge base. The guidance is likely correct but please confirm the specific details with the office before acting.",
  },
  low: {
    color: "#c0392b",
    bg: "#fdf0ef",
    border: "#c0392b",
    icon: "!",
    label: "Low Confidence",
    message: "Not enough reliable information. Please speak directly to a human officer.",
    detail: "This query falls outside the pension knowledge base or involves a situation that requires a human officer to assess. Call 1800-425-1700 (toll-free) for guidance.",
  },
};

export default function ConfidenceCard({ band, percent, processingMs }) {
  const cfg = BAND_CONFIG[band] || BAND_CONFIG.low;
  const [animated, setAnimated] = useState(0);
  const [showDetail, setShowDetail] = useState(false);

  useEffect(() => {
    setAnimated(0);
    const t = setTimeout(() => setAnimated(percent), 80);
    return () => clearTimeout(t);
  }, [percent]);

  const ariaLabel = `${cfg.label}: ${percent} percent. ${cfg.message}`;

  return (
    <div
      className="confidence-card card"
      style={{ borderLeft: `4px solid ${cfg.border}`, background: cfg.bg }}
      role="status"
      aria-live="polite"
      aria-label={ariaLabel}
    >
      <div className="confidence-header">
        <span className="confidence-icon" style={{ color: cfg.color }} aria-hidden="true">{cfg.icon}</span>
        <span
          className="confidence-label"
          style={{ color: cfg.color }}
          id="confidence-label"
        >
          {cfg.label}
        </span>
        <span
          className="confidence-percent"
          style={{ color: cfg.color }}
          aria-hidden="true"
        >
          {percent}%
        </span>
      </div>

      <div
        className="confidence-bar-bg"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-labelledby="confidence-label"
      >
        <div
          className="confidence-bar-fill"
          style={{
            width: `${animated}%`,
            background: cfg.color,
            transition: "width 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)",
          }}
          aria-hidden="true"
        />
      </div>

      <div className="confidence-footer">
        <p className="confidence-message">{cfg.message}</p>
        {processingMs !== undefined && (
          <span className="confidence-timing" aria-label={`Processed in ${processingMs} milliseconds`}>
            ⚡ {processingMs}ms
          </span>
        )}
      </div>

      <details
        style={{ marginTop: "0.6rem" }}
        onToggle={(e) => setShowDetail(e.target.open)}
      >
        <summary
          style={{
            fontSize: "0.78rem",
            color: cfg.color,
            cursor: "pointer",
            userSelect: "none",
            listStyle: "none",
            display: "flex",
            alignItems: "center",
            gap: "0.3rem",
          }}
          aria-expanded={showDetail}
        >
          <span aria-hidden="true">{showDetail ? "▾" : "▸"}</span>
          What does this mean?
        </summary>
        <div
          style={{
            marginTop: "0.5rem",
            paddingLeft: "0.75rem",
            borderLeft: `2px solid ${cfg.border}`,
            fontSize: "0.82rem",
            color: "#555",
            lineHeight: "1.5",
          }}
        >
          <p style={{ margin: "0 0 0.4rem 0" }}>{cfg.detail}</p>
          <p style={{ margin: 0, color: "#888", fontSize: "0.75rem" }}>
            Score formula: (retrieval quality × 60%) + (AI certainty × 40%) = {percent}%
          </p>
        </div>
      </details>
    </div>
  );
}
