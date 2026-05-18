import { useState } from "react";

const CATEGORY_COLOR = {
  eligibility:       "#4a7c59",
  documents:         "#2e86c1",
  income:            "#8e44ad",
  deadline:          "#c0392b",
  benefits:          "#27ae60",
  process:           "#e67e22",
  contact:           "#16a085",
  safety:            "#7f8c8d",
  escalation:        "#c0392b",
  old_age_pension:   "#1a5276",
  disability_pension:"#6c3483",
  schemes_overview:  "#117a65",
  language:          "#935116",
  medical:           "#c0392b",
};

export default function EvidencePanel({ evidence, disclaimer, showWarning }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="evidence-panel card">
      <div className="evidence-header-row">
        <button className="evidence-toggle" onClick={() => setOpen(!open)}>
          {open ? "Hide Sources" : "Show Sources"} ({evidence?.length || 0} facts used)
        </button>
        {showWarning && (
          <span className="evidence-warning-badge">⚠ Verify with office</span>
        )}
      </div>

      {open && (
        <div className="evidence-body">
          {evidence?.length === 0 && (
            <p className="no-evidence">No specific facts cited.</p>
          )}
          {evidence?.map((fact, i) => {
            const color = CATEGORY_COLOR[fact.category] || "#666";
            return (
              <div key={i} className="evidence-item" style={{ borderLeftColor: color }}>
                <div className="evidence-rule-header">
                  <span className="evidence-rule-id" style={{ color }}>
                    [{fact.rule_id}]
                  </span>
                  <span
                    className="evidence-category-badge"
                    style={{ background: color + "18", color }}
                  >
                    {fact.category?.replace(/_/g, " ").toUpperCase()}
                  </span>
                  <span className="evidence-conf-dot" title={`${Math.round((fact.confidence_base || 0) * 100)}% base confidence`}>
                    {Math.round((fact.confidence_base || 0) * 100)}%
                  </span>
                </div>
                <p className="evidence-text">{fact.text}</p>
                <div className="evidence-source">Source: {fact.source}</div>
              </div>
            );
          })}

          <div className="disclaimer">
            <p>{disclaimer}</p>
          </div>
        </div>
      )}
    </div>
  );
}
