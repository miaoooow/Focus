const STORAGE_KEY = "focusBrowserState";
const LEGACY_STORAGE_KEY = ["focus", "Buddy", "BrowserState"].join("");
const VIOLATION_ALARM = "focus-violation";
const END_ALARM = "focus-end";
const CAT_ICON =
  "data:image/svg+xml;charset=utf-8," +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128"><rect width="128" height="128" rx="30" fill="#173f32"/><path d="M29 51 35 22l23 18h13l23-18 6 29c9 9 13 21 11 35-4 24-22 35-47 35S21 110 17 86c-2-14 3-27 12-35Z" fill="#d8f28b"/><circle cx="48" cy="68" r="5" fill="#173f32"/><circle cx="80" cy="68" r="5" fill="#173f32"/><path d="M57 81q7 8 14 0" fill="none" stroke="#173f32" stroke-width="5" stroke-linecap="round"/></svg>'
  );
const DESKTOP_PORTS = Array.from({ length: 11 }, (_, index) => 8765 + index);
let desktopPort = null;

function browserProcess() {
  const agent = navigator.userAgent || "";
  if (/Edg\//i.test(agent)) return "msedge.exe";
  if (/Firefox\//i.test(agent)) return "firefox.exe";
  return "chrome.exe";
}

async function desktopRequest(port, path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 650);
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

async function locateDesktop() {
  if (desktopPort !== null) return desktopPort;
  for (const port of DESKTOP_PORTS) {
    try {
      const response = await desktopRequest(port, "/api/health");
      const payload = await response.json();
      if (response.ok && payload?.data?.service === "focus") {
        desktopPort = port;
        return port;
      }
    } catch {
      // The EXE may not be running; continue without showing an error.
    }
  }
  return null;
}

async function publishActiveTabToDesktop() {
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (!tab?.url || tab.incognito) return;
  let url;
  try {
    url = new URL(tab.url);
  } catch {
    return;
  }
  if (!["http:", "https:"].includes(url.protocol)) return;
  const port = await locateDesktop();
  if (port === null) return;
  try {
    const response = await desktopRequest(port, "/api/browser/active", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        process_name: browserProcess(),
        domain: normalizeDomain(url.hostname),
        title: String(tab.title || "").slice(0, 120),
      }),
    });
    if (!response.ok) desktopPort = null;
  } catch {
    desktopPort = null;
  }
}

const defaultState = () => ({
  session: null,
  pendingViolation: null,
  totalMinutes: 0,
  coins: 0,
  completed: 0,
  browser: {
    currentDomain: "",
    currentTitle: "",
    lastWebDomain: "",
    checkedAt: 0,
    allowed: true,
  },
  lastEvent: null,
});

async function readState() {
  const stored = await chrome.storage.local.get([STORAGE_KEY, LEGACY_STORAGE_KEY]);
  const saved = stored[STORAGE_KEY] || stored[LEGACY_STORAGE_KEY] || {};
  if (!stored[STORAGE_KEY] && stored[LEGACY_STORAGE_KEY]) {
    await chrome.storage.local.set({ [STORAGE_KEY]: saved });
    await chrome.storage.local.remove(LEGACY_STORAGE_KEY);
  }
  const base = defaultState();
  return {
    ...base,
    ...saved,
    completed: Number(saved.completed ?? saved.completedSessions ?? 0),
    browser: { ...base.browser, ...(saved.browser || {}) },
  };
}

async function writeState(state) {
  await chrome.storage.local.set({ [STORAGE_KEY]: state });
  return state;
}

function normalizeDomain(value) {
  const raw = String(value || "").trim().toLowerCase();
  if (!raw) return "";
  try {
    const url = raw.includes("://") ? new URL(raw) : new URL(`https://${raw}`);
    return url.hostname.replace(/^www\./, "");
  } catch {
    return raw.replace(/^www\./, "").split("/")[0];
  }
}

function isAllowed(hostname, domains) {
  const host = normalizeDomain(hostname);
  return domains.some((item) => host === item || host.endsWith(`.${item}`));
}

async function clearViolation(state) {
  await chrome.alarms.clear(VIOLATION_ALARM);
  if (state.pendingViolation) {
    state.pendingViolation = null;
    await writeState(state);
  }
}

async function showNotification(title, message) {
  try {
    await chrome.notifications.create({
      type: "basic",
      iconUrl: CAT_ICON,
      title,
      message,
      priority: 1,
    });
  } catch {
    await chrome.action.setBadgeBackgroundColor({ color: "#d65b5b" });
    await chrome.action.setBadgeText({ text: "!" });
  }
}

async function finishSession(state) {
  if (!state.session || state.session.status === "finished") return state;
  const minutes = Math.max(1, Math.round(state.session.durationSeconds / 60));
  const cleanBonus = state.session.driftCount === 0 ? 5 : 0;
  state.totalMinutes += minutes;
  state.coins += Math.max(2, Math.round(minutes / 5) + cleanBonus - state.session.driftCount * 2);
  state.completed += 1;
  state.session = { ...state.session, status: "finished", finishedAt: Date.now() };
  state.pendingViolation = null;
  state.lastEvent = {
    id: Date.now(),
    type: "complete",
    title: "Luna 有点骄傲",
    message: "完成比完美更会养大一只猫。",
  };
  await chrome.alarms.clear(VIOLATION_ALARM);
  await chrome.alarms.clear(END_ALARM);
  await writeState(state);
  await chrome.action.setBadgeBackgroundColor({ color: "#7ca65c" });
  await chrome.action.setBadgeText({ text: "✓" });
  await showNotification("Luna：这轮守住了", "专注完成，猫币已经放进小鱼干罐。");
  return state;
}

async function evaluateActiveTab() {
  publishActiveTabToDesktop();
  const state = await readState();
  const session = state.session;
  if (!session || session.status !== "running") return;
  if (Date.now() >= session.endAt) {
    await finishSession(state);
    return;
  }

  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (!tab || !tab.url || tab.url.startsWith("chrome-extension://")) {
    state.browser = {
      ...state.browser,
      currentDomain: "Focus",
      currentTitle: "完整专注台",
      checkedAt: Date.now(),
      allowed: true,
    };
    await writeState(state);
    await clearViolation(state);
    return;
  }

  let host = "";
  try {
    host = normalizeDomain(new URL(tab.url).hostname);
  } catch {
    await clearViolation(state);
    return;
  }

  const allowed = Boolean(host && isAllowed(host, session.allowedDomains));
  state.browser = {
    currentDomain: host,
    currentTitle: String(tab.title || "").slice(0, 120),
    lastWebDomain: host || state.browser.lastWebDomain,
    checkedAt: Date.now(),
    allowed,
  };
  await writeState(state);

  if (!host || allowed) {
    await clearViolation(state);
    await chrome.action.setBadgeText({ text: "" });
    return;
  }

  if (state.pendingViolation?.host === host && state.pendingViolation?.tabId === tab.id) {
    return;
  }
  state.pendingViolation = { host, tabId: tab.id, startedAt: Date.now() };
  await writeState(state);
  await chrome.alarms.clear(VIOLATION_ALARM);
  await chrome.alarms.create(VIOLATION_ALARM, { when: Date.now() + session.graceSeconds * 1000 });
}

async function confirmViolation() {
  const state = await readState();
  const session = state.session;
  const pending = state.pendingViolation;
  if (!session || session.status !== "running" || !pending) return;

  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  let host = "";
  try {
    host = tab?.url ? normalizeDomain(new URL(tab.url).hostname) : "";
  } catch {
    host = "";
  }
  if (!host || host !== pending.host || isAllowed(host, session.allowedDomains)) {
    await clearViolation(state);
    return;
  }

  session.driftCount += 1;
  state.pendingViolation = null;
  const lines = [
    `${host} 今天也没打算替你交作业。`,
    `Luna 看见你绕路了：${host}`,
    `这页很会留人，可你的目标还在等。`,
    `逛得挺丝滑，进度条可没跟上。`,
  ];
  const message = lines[(session.driftCount - 1) % lines.length];
  state.lastEvent = {
    id: Date.now(),
    type: "drift",
    host,
    title: "散步路线挺熟",
    message,
  };
  await writeState(state);
  await chrome.action.setBadgeBackgroundColor({ color: "#d65b5b" });
  await chrome.action.setBadgeText({ text: String(Math.min(9, session.driftCount)) });
  await showNotification("Focus · 走神提醒", message);
}

async function startSession(payload) {
  const state = await readState();
  const durationMinutes = Math.max(1, Math.min(240, Number(payload.durationMinutes) || 25));
  const allowedDomains = [...new Set((payload.allowedDomains || []).map(normalizeDomain).filter(Boolean))];
  if (!String(payload.goal || "").trim()) throw new Error("请先写下这一轮的目标");
  if (!allowedDomains.length) throw new Error("至少添加一个允许访问的网站域名");

  const now = Date.now();
  state.session = {
    goal: String(payload.goal).trim().slice(0, 180),
    durationSeconds: durationMinutes * 60,
    startedAt: now,
    endAt: now + durationMinutes * 60 * 1000,
    remainingWhenPaused: null,
    status: "running",
    allowedDomains,
    graceSeconds: 8,
    driftCount: 0,
    tone: String(payload.tone || "funny"),
  };
  state.pendingViolation = null;
  state.lastEvent = {
    id: Date.now(),
    type: "start",
    title: "Luna 开工了",
    message: "当前标签页开始由扩展在本机监督。",
  };
  await writeState(state);
  await chrome.alarms.clear(VIOLATION_ALARM);
  await chrome.alarms.create(END_ALARM, { when: state.session.endAt });
  await chrome.action.setBadgeText({ text: "" });
  await evaluateActiveTab();
  return state;
}

async function pauseSession() {
  const state = await readState();
  if (state.session?.status === "running") {
    state.session.remainingWhenPaused = Math.max(0, state.session.endAt - Date.now());
    state.session.status = "paused";
    state.pendingViolation = null;
    await chrome.alarms.clear(VIOLATION_ALARM);
    await chrome.alarms.clear(END_ALARM);
    state.lastEvent = {
      id: Date.now(),
      type: "pause",
      title: "先喘口气",
      message: "计时和标签页监督都已暂停。",
    };
    await writeState(state);
  }
  return state;
}

async function resumeSession() {
  const state = await readState();
  if (state.session?.status === "paused") {
    state.session.endAt = Date.now() + Math.max(1000, state.session.remainingWhenPaused || 1000);
    state.session.remainingWhenPaused = null;
    state.session.status = "running";
    state.lastEvent = {
      id: Date.now(),
      type: "resume",
      title: "继续就好",
      message: "扩展已经重新盯住当前标签页。",
    };
    await writeState(state);
    await chrome.alarms.create(END_ALARM, { when: state.session.endAt });
    await evaluateActiveTab();
  }
  return state;
}

async function stopSession() {
  const state = await readState();
  state.session = null;
  state.pendingViolation = null;
  state.lastEvent = {
    id: Date.now(),
    type: "stop",
    title: "这轮先收回",
    message: "下次把目标切小一点，再来一轮。",
  };
  await chrome.alarms.clear(VIOLATION_ALARM);
  await chrome.alarms.clear(END_ALARM);
  await chrome.action.setBadgeText({ text: "" });
  return writeState(state);
}

async function activeTabSummary() {
  const state = await readState();
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  let domain = "";
  try {
    if (tab?.url && !tab.url.startsWith("chrome-extension://")) {
      domain = normalizeDomain(new URL(tab.url).hostname);
    }
  } catch {
    domain = "";
  }
  return {
    domain: domain || state.browser.lastWebDomain || "",
    title: String(tab?.title || state.browser.currentTitle || "").slice(0, 120),
  };
}

chrome.runtime.onInstalled.addListener(async () => {
  const current = await chrome.storage.local.get(STORAGE_KEY);
  if (!current[STORAGE_KEY]) await writeState(defaultState());
  await publishActiveTabToDesktop();
});
chrome.runtime.onStartup.addListener(() => publishActiveTabToDesktop());

chrome.tabs.onActivated.addListener(() => evaluateActiveTab());
chrome.tabs.onUpdated.addListener((_tabId, changeInfo) => {
  if (changeInfo.url || changeInfo.status === "complete") evaluateActiveTab();
});
chrome.windows.onFocusChanged.addListener(() => evaluateActiveTab());
chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name === VIOLATION_ALARM) await confirmViolation();
  if (alarm.name === END_ALARM) await finishSession(await readState());
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  const actions = {
    ping: async () => ({ connected: true, version: chrome.runtime.getManifest().version }),
    state: readState,
    start: () => startSession(message.payload || {}),
    pause: pauseSession,
    resume: resumeSession,
    stop: stopSession,
    activeTab: activeTabSummary,
  };
  const action = actions[message.type];
  if (!action) {
    sendResponse({ ok: false, error: "未知操作" });
    return false;
  }
  action()
    .then((state) => sendResponse({ ok: true, state }))
    .catch((error) => sendResponse({ ok: false, error: String(error.message || error) }));
  return true;
});
