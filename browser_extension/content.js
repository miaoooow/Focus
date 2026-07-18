function heartbeat() {
  try {
    chrome.runtime.sendMessage({ type: "focus-heartbeat" });
  } catch (_) {
    // The background worker can be restarting; the next heartbeat retries.
  }
}

heartbeat();
setInterval(heartbeat, 1800);
