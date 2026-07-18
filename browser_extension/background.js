const PORTS = Array.from({ length: 11 }, (_, index) => 8765 + index);
let cachedPort = null;

function browserProcess() {
  const agent = navigator.userAgent || "";
  if (/Edg\//i.test(agent)) return "msedge.exe";
  if (/Firefox\//i.test(agent)) return "firefox.exe";
  return "chrome.exe";
}

async function request(port, path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 700);
  try {
    return await fetch(`http://127.0.0.1:${port}${path}`, {
      ...options,
      signal: controller.signal,
      cache: "no-store",
    });
  } finally {
    clearTimeout(timeout);
  }
}

async function locateService() {
  if (cachedPort !== null) return cachedPort;
  for (const port of PORTS) {
    try {
      const response = await request(port, "/api/health");
      const payload = await response.json();
      if (response.ok && payload?.data?.service === "focus") {
        cachedPort = port;
        return port;
      }
    } catch (_) {
      // Try the next local port.
    }
  }
  return null;
}

async function publishActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (!tab?.url || tab.incognito) return;
  let parsed;
  try {
    parsed = new URL(tab.url);
  } catch (_) {
    return;
  }
  if (!["http:", "https:"].includes(parsed.protocol)) return;
  let port = await locateService();
  if (port === null) return;
  const body = JSON.stringify({
    process_name: browserProcess(),
    domain: parsed.hostname.replace(/^www\./i, ""),
    title: tab.title || "",
  });
  try {
    const response = await request(port, "/api/browser/active", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });
    if (!response.ok) cachedPort = null;
  } catch (_) {
    cachedPort = null;
  }
}

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "focus-heartbeat") publishActiveTab();
});
chrome.tabs.onActivated.addListener(publishActiveTab);
chrome.tabs.onUpdated.addListener((_tabId, changeInfo, tab) => {
  if (tab.active && (changeInfo.url || changeInfo.status === "complete")) publishActiveTab();
});
chrome.windows.onFocusChanged.addListener(publishActiveTab);
