import { useState, useEffect } from "react";
import TypewriterText from "./TypewriterText";

const LANG_CONFIG = {
  ta: { nativeName: "தமிழ்",  greeting: "அக்கா" },
  te: { nativeName: "తెలుగు", greeting: "అక్కా" },
  kn: { nativeName: "ಕನ್ನಡ",  greeting: "ಅಕ್ಕ"  },
  hi: { nativeName: "हिंदी",  greeting: "दीदी"  },
  en: { nativeName: "English", greeting: "Akka"   },
};

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

export default function CitizenGuidanceCard({
  guidance,
  regionalSummary,
  tamilSummary,
  language,
}) {
  const bestSummary = regionalSummary || (language === "ta" ? tamilSummary : null);
  const hasRegional  = !!bestSummary && language !== "en";

  const [showRegional, setShowRegional] = useState(hasRegional);
  const [copied, setCopied]             = useState(false);

  useEffect(() => {
    setShowRegional(hasRegional);
  }, [regionalSummary, tamilSummary, language]);

  const cfg = LANG_CONFIG[language] || LANG_CONFIG.en;
  const activeText = hasRegional && showRegional ? bestSummary : guidance;

  const handleCopy = async () => {
    await copyToClipboard(activeText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="citizen-card card">
      <div className="card-header">
        <h3 className="card-title">For You, {cfg.greeting}</h3>
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span className="citizen-tag">Plain Language</span>
          <button className="copy-btn" onClick={handleCopy} title="Copy guidance">
            {copied ? "✓ Copied" : "Copy"}
          </button>
        </div>
      </div>

      {hasRegional && (
        <div className="citizen-lang-toggle">
          <button
            type="button"
            className={`lang-btn ${showRegional ? "active" : ""}`}
            onClick={() => setShowRegional(true)}
          >
            {cfg.nativeName}
          </button>
          <button
            type="button"
            className={`lang-btn ${!showRegional ? "active" : ""}`}
            onClick={() => setShowRegional(false)}
          >
            English
          </button>
        </div>
      )}

      {hasRegional && showRegional ? (
        <p className="regional-text">
          <TypewriterText key={bestSummary} text={bestSummary} speed={8} />
        </p>
      ) : (
        <p className="citizen-text">
          <TypewriterText key={guidance} text={guidance} speed={10} />
        </p>
      )}

      {hasRegional && !showRegional && (
        <div className="regional-peek">
          <hr className="divider" />
          <p className="regional-text small">{bestSummary}</p>
        </div>
      )}
    </div>
  );
}
