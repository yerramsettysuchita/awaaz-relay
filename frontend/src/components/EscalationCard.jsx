export default function EscalationCard({ reason }) {
  return (
    <div className="escalation-card card">
      <div className="escalation-header">
        <span className="escalation-icon">!</span>
        <h3 className="escalation-title">Human Review Required</h3>
      </div>

      <p className="escalation-reason">{reason || "This query requires a human officer to review."}</p>

      <div className="escalation-contacts">
        <a className="contact-item contact-link" href="tel:18004251700">
          <span className="contact-icon">📞</span>
          <span>
            <strong>Helpline</strong> — 1800-425-1700
            <span className="contact-note"> (Toll-free, Monday to Saturday, 9 AM to 5 PM)</span>
          </span>
        </a>
        <div className="contact-item">
          <span className="contact-icon">🏢</span>
          <span><strong>Visit</strong> the Block Development Office in your district</span>
        </div>
        <a className="contact-item contact-link" href="tel:1947">
          <span className="contact-icon">🆔</span>
          <span><strong>Aadhaar help</strong> — call 1947 (UIDAI, toll-free)</span>
        </a>
        <a className="contact-item contact-link" href="https://pgportal.gov.in" target="_blank" rel="noreferrer">
          <span className="contact-icon">🌐</span>
          <span><strong>Grievance portal</strong> — pgportal.gov.in</span>
        </a>
      </div>

      <p className="escalation-note">
        Awaaz Relay has provided everything it safely can. Please speak directly with an officer for the final decision.
      </p>
    </div>
  );
}
