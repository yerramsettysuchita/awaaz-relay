import { useState } from "react";

async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const el = document.createElement("textarea");
    el.value = text;
    document.body.appendChild(el);
    el.select();
    document.execCommand("copy");
    document.body.removeChild(el);
  }
}

const DOMAIN_LABELS = {
  pension_eligibility: "Pension Eligibility",
  documents_required:  "Documents",
  deadline:            "Deadline",
  benefits:            "Benefits",
  process:             "How to Apply",
  contact:             "Contact",
  out_of_scope:        "Out of Scope",
  old_age_pension:     "Old Age Pension",
  disability_pension:  "Disability Pension",
  schemes_overview:    "Schemes Overview",
};

export default function WorkerGuidanceCard({ guidance, domain, escalationNeeded, escalationReason }) {
  const [checked, setChecked] = useState({});
  const [copied, setCopied]   = useState(false);

  const toggle = (i) => setChecked((prev) => ({ ...prev, [i]: !prev[i] }));
  const doneCount = guidance.filter((_, i) => checked[i]).length;
  const allDone = guidance.length > 0 && doneCount === guidance.length;
  const domainLabel = DOMAIN_LABELS[domain] || domain?.replace(/_/g, " ");

  const handleCopy = async () => {
    const lines = [
      `Awaaz Relay — Worker Checklist (${domainLabel})`,
      "",
      ...guidance.map((item, i) => `${checked[i] ? "☑" : "☐"} ${item}`),
    ];
    await copyToClipboard(lines.join("\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="worker-card card">
      <div className="card-header">
        <h3 className="card-title">Worker Guidance</h3>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span className="domain-tag">{domainLabel}</span>
          <button className="copy-btn" onClick={handleCopy} title="Copy checklist">
            {copied ? "✓ Copied" : "Copy"}
          </button>
        </div>
      </div>

      {escalationNeeded && escalationReason && (
        <div className="escalation-banner">
          <strong>Escalation required.</strong> {escalationReason}
        </div>
      )}

      <ul className="checklist">
        {guidance.map((item, i) => (
          <li key={i} className={`checklist-item ${checked[i] ? "checked" : ""}`}>
            <label className="checklist-label">
              <input
                type="checkbox"
                checked={!!checked[i]}
                onChange={() => toggle(i)}
              />
              <span>{item}</span>
            </label>
          </li>
        ))}
      </ul>

      {guidance.length > 0 && (
        <div className="checklist-progress">
          <div className="progress-bar-bg">
            <div
              className="progress-bar-fill"
              style={{ width: `${(doneCount / guidance.length) * 100}%` }}
            />
          </div>
          <span className="progress-label">
            {allDone ? "✓ All steps completed — ready to submit!" : `${doneCount} / ${guidance.length} steps done`}
          </span>
        </div>
      )}
    </div>
  );
}
