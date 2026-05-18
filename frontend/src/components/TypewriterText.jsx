import { useState, useEffect, useRef } from "react";

const prefersReducedMotion =
  typeof window !== "undefined" &&
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export default function TypewriterText({ text, speed = 10 }) {
  const [displayed, setDisplayed] = useState(prefersReducedMotion ? text : "");
  const [done, setDone] = useState(prefersReducedMotion);
  const timerRef = useRef(null);
  const idxRef   = useRef(0);

  useEffect(() => {
    if (prefersReducedMotion) {
      setDisplayed(text);
      setDone(true);
      return;
    }
    clearTimeout(timerRef.current);
    idxRef.current = 0;
    setDisplayed("");
    setDone(false);

    const tick = () => {
      idxRef.current++;
      setDisplayed(text.slice(0, idxRef.current));
      if (idxRef.current < text.length) {
        timerRef.current = setTimeout(tick, speed);
      } else {
        setDone(true);
      }
    };
    timerRef.current = setTimeout(tick, speed);
    return () => clearTimeout(timerRef.current);
  }, [text, speed]);

  const skip = () => {
    clearTimeout(timerRef.current);
    setDisplayed(text);
    setDone(true);
  };

  return (
    <span>
      {displayed}
      {!done && <span className="typewriter-cursor" aria-hidden="true" />}
      {!done && (
        <button type="button" className="typewriter-skip" onClick={skip} aria-label="Show full text">
          Skip
        </button>
      )}
    </span>
  );
}
