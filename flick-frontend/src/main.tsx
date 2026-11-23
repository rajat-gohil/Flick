import React from "react";
import ReactDOM from "react-dom/client";
import "material-symbols/outlined.css";
import App from "./App";
import "./index.css";
import posthog from "posthog-js";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

const posthogKey = import.meta.env.VITE_POSTHOG_KEY;
const posthogHost = import.meta.env.VITE_POSTHOG_HOST || "https://us.i.posthog.com";

if (posthogKey && posthogKey !== "your_posthog_project_key") {
  posthog.init(posthogKey, {
    api_host: posthogHost,
    autocapture: false,        // IMPORTANT
    capture_pageview: false,   // IMPORTANT
    disable_session_recording: true, // IMPORTANT
  });
}