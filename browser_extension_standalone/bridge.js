const FOCUS_PAGE_MARKER = "focus-page-v1";
const FOCUS_EXTENSION_MARKER = "focus-extension-v1";
const ALLOWED_ACTIONS = new Set(["ping", "state", "start", "pause", "resume", "stop", "activeTab"]);

window.postMessage(
  { marker: FOCUS_EXTENSION_MARKER, type: "ready", version: chrome.runtime.getManifest().version },
  window.location.origin
);

window.addEventListener("message", (event) => {
  if (event.source !== window || event.origin !== window.location.origin) return;
  const message = event.data;
  if (
    !message ||
    message.marker !== FOCUS_PAGE_MARKER ||
    !ALLOWED_ACTIONS.has(message.type) ||
    typeof message.requestId !== "string"
  ) {
    return;
  }
  chrome.runtime.sendMessage({ type: message.type, payload: message.payload || {} })
    .then((result) => {
      window.postMessage(
        {
          marker: FOCUS_EXTENSION_MARKER,
          type: "response",
          requestId: message.requestId,
          result,
        },
        window.location.origin
      );
    })
    .catch((error) => {
      window.postMessage(
        {
          marker: FOCUS_EXTENSION_MARKER,
          type: "response",
          requestId: message.requestId,
          result: { ok: false, error: String(error?.message || error) },
        },
        window.location.origin
      );
    });
});
