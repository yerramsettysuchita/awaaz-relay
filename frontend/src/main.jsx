import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// Register service worker for offline-first caching
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js")
      .then((reg) => {
        console.log("[SW] Registered:", reg.scope);
        // Notify app shell when SW activates
        reg.addEventListener("updatefound", () => {
          const newWorker = reg.installing;
          newWorker?.addEventListener("statechange", () => {
            if (newWorker.state === "activated") {
              console.log("[SW] Activated — app is now offline-capable");
              // Update offline badge
              const badge = document.getElementById("offline-badge");
              if (badge) badge.textContent = "● Offline-ready";
            }
          });
        });
      })
      .catch((err) => console.warn("[SW] Registration failed:", err));
  });
}
