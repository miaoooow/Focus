const $ = (selector) => document.querySelector(selector);
const STORAGE_KEY = "focus-web-v1";
const CIRCUMFERENCE = 2 * Math.PI * 96;
const EXTENSION_MODE = Boolean(globalThis.chrome?.runtime?.id) && location.protocol === "chrome-extension:";

const scenes = [
  { name: "编程开发", keys: ["代码", "编程", "python", "java", "开发", "debug"], tools: ["代码编辑器", "终端", "项目文件"], domains: ["github.com", "stackoverflow.com", "docs.python.org"] },
  { name: "文档写作", keys: ["文档", "报告", "论文", "简历", "写作"], tools: ["文档编辑器", "资料参考", "文件夹"], domains: ["docs.google.com", "office.com", "cnki.net"] },
  { name: "课程学习", keys: ["作业", "课程", "复习", "高数", "英语", "学习"], tools: ["课程资料", "笔记", "计算工具"], domains: ["coursera.org", "icourse163.org", "bilibili.com"] },
  { name: "数据整理", keys: ["数据", "excel", "表格", "统计", "分析"], tools: ["表格软件", "数据文件", "计算器"], domains: ["kaggle.com", "docs.google.com"] },
  { name: "演示设计", keys: ["ppt", "演示", "答辩", "设计", "原型"], tools: ["演示软件", "素材文件", "参考资料"], domains: ["figma.com", "canva.com"] },
  { name: "视频剪辑", keys: ["视频", "剪辑", "播客", "录音"], tools: ["剪辑软件", "素材文件", "音频工具"], domains: ["youtube.com", "drive.google.com"] },
];

const defaults = {
  totalMinutes: 0,
  coins: 0,
  completed: 0,
  session: null,
  petName: "Luna",
  petImage: null,
  petActions: null,
};

let state = loadState();
let timerHandle = null;
let hiddenAt = null;
const ambientAudio = new Audio();
ambientAudio.loop = true;
ambientAudio.preload = "metadata";
ambientAudio.volume = 0.42;
let pendingPetImage = state.petImage;
let pendingPetActions = state.petActions;
let lastExtensionEventId = 0;
let lastExtensionDriftCount = 0;
let extensionRefreshBusy = false;
let domainsTouched = false;
let initialDomain = "";

function extensionSend(type, payload) {
  if (!EXTENSION_MODE) return Promise.resolve({ ok: false, error: "扩展未连接" });
  return chrome.runtime.sendMessage({ type, payload });
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

function allowedDomains() {
  return [...new Set(
    $("#allowed-domains").value
      .split(/[\n,，\s]+/)
      .map(normalizeDomain)
      .filter(Boolean)
  )];
}

function setAllowedDomains(domains) {
  $("#allowed-domains").value = [...new Set(domains.map(normalizeDomain).filter(Boolean))].join(", ");
}

function addAllowedDomain(domain) {
  const normalized = normalizeDomain(domain);
  if (!normalized) return;
  setAllowedDomains([...allowedDomains(), normalized]);
  domainsTouched = true;
  renderPlan();
}

function petName() {
  return (state.petName || "Luna").trim() || "Luna";
}

function defaultPetImage(kind = "") {
  return {
    annoyed: "media/confused.png",
    happy: "media/happy.png",
    focus: "media/focus.png",
  }[kind] || "media/relax.png";
}

function selectedPetImage(kind = "") {
  if (!state.petActions) return state.petImage || defaultPetImage(kind);
  const action = kind === "annoyed"
    ? ((state.session?.driftCount || 0) <= 1 ? "wiggle" : "angry")
    : kind === "happy" ? "happy" : "idle";
  return state.petActions[action] || state.petImage || defaultPetImage(kind);
}

function loadState() {
  try {
    return { ...defaults, ...JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") };
  } catch {
    return { ...defaults };
  }
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function parseGoal(goal) {
  const normalized = goal.toLowerCase();
  const matched = scenes.filter((scene) => scene.keys.some((key) => normalized.includes(key)));
  const selected = matched.length
    ? matched.slice(0, 2)
    : [{ name: "专注任务", tools: ["任务资料", "必要工具"], domains: [] }];
  return {
    names: selected.map((scene) => scene.name),
    tools: [...new Set(selected.flatMap((scene) => scene.tools))],
    domains: [...new Set(selected.flatMap((scene) => scene.domains || []))],
  };
}

function renderDomainSuggestions(domains = []) {
  const container = $("#domain-suggestions");
  if (!domains.length) {
    container.innerHTML = "<small>没有固定网站也没关系，可以直接输入域名。</small>";
    return;
  }
  container.innerHTML = domains
    .map((domain) => `<button type="button" data-domain="${domain}">＋ ${domain}</button>`)
    .join("");
  container.querySelectorAll("[data-domain]").forEach((button) => {
    button.addEventListener("click", () => addAllowedDomain(button.dataset.domain));
  });
}

function renderPlan() {
  const goal = $("#goal").value.trim();
  const match = goal.match(/(\d{1,3})\s*分钟/);
  if (match) {
    const value = String(Math.min(240, Math.max(1, Number(match[1]))));
    if (![...$("#duration").options].some((option) => option.value === value)) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = `${value} 分钟`;
      $("#duration").append(option);
    }
    $("#duration").value = value;
  }
  if (!goal) {
    $("#plan-result").innerHTML = "<p>写下目标后，这里会出现本地场景建议。</p>";
    renderDomainSuggestions([]);
    return;
  }
  const plan = parseGoal(goal);
  if (!domainsTouched) setAllowedDomains([initialDomain, ...plan.domains]);
  $("#plan-result").innerHTML = `
    <p>识别为 <b>${plan.names.join(" + ")}</b>。${EXTENSION_MODE ? "扩展会按下方域名监督当前标签页；建议准备：" : "免安装网页不会读取其他软件；建议准备："}</p>
    <div class="plan-chips">${plan.tools.map((tool) => `<span>${tool}</span>`).join("")}</div>
  `;
  renderDomainSuggestions(plan.domains);
}

function formatTime(milliseconds) {
  const seconds = Math.max(0, Math.ceil(milliseconds / 1000));
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

function remainingMs() {
  if (!state.session) return Number($("#duration").value) * 60 * 1000;
  if (state.session.status === "paused") return state.session.remainingWhenPaused;
  return Math.max(0, state.session.endAt - Date.now());
}

function rewardPreview() {
  if (!state.session) return 0;
  const minutes = Math.max(1, Math.round(state.session.durationSeconds / 60));
  return Math.max(2, Math.round(minutes / 5) + (state.session.driftCount === 0 ? 5 : 0) - state.session.driftCount * 2);
}

function catReact(kind, title, note) {
  const cat = $("#hero-cat");
  const image = $("#hero-pet-image");
  cat.classList.remove("annoyed", "happy");
  image.classList.remove("annoyed", "happy");
  void cat.offsetWidth;
  void image.offsetWidth;
  if (kind) {
    cat.classList.add(kind);
    image.classList.add(kind);
  }
  image.src = selectedPetImage(kind);
  $("#cat-note-title").textContent = title;
  $("#cat-note").textContent = note;
}

async function startSession() {
  const goal = $("#goal").value.trim();
  if (!goal) {
    $("#form-message").textContent = `${petName()} 还不知道该盯哪件事，请先写下目标。`;
    $("#goal").focus();
    return;
  }
  const durationMinutes = Number($("#duration").value);
  const durationSeconds = durationMinutes * 60;
  if (EXTENSION_MODE) {
    const domains = allowedDomains();
    if (!domains.length) {
      $("#form-message").textContent = "至少留一个本轮允许访问的网站；可以点“当前网站”或场景推荐。";
      $("#allowed-domains").focus();
      return;
    }
    $("#start").disabled = true;
    const result = await extensionSend("start", {
      goal,
      durationMinutes,
      allowedDomains: domains,
      tone: $("#tone").value,
    });
    $("#start").disabled = false;
    if (!result?.ok) {
      $("#form-message").textContent = result?.error || "扩展后台没有响应，请重新加载扩展。";
      return;
    }
    applyExtensionState(result.state);
    $("#form-message").textContent = `已开始：只允许 ${domains.join("、")}，离开 8 秒后提醒。`;
    catReact("focus", `${petName()} 开工了`, "扩展会继续监督，即使你切到别的标签页。");
    beginTimer();
    render();
    return;
  }
  state.session = {
    goal,
    tone: $("#tone").value,
    durationSeconds,
    startedAt: Date.now(),
    endAt: Date.now() + durationSeconds * 1000,
    remainingWhenPaused: null,
    status: "running",
    driftCount: 0,
  };
  $("#form-message").textContent = "";
  saveState();
  catReact("focus", `${petName()} 开工了`, "别追求完美，先把这一轮做完。");
  beginTimer();
  render();
}

async function pauseOrResume() {
  if (!state.session) return;
  if (EXTENSION_MODE) {
    const action = state.session.status === "running" ? "pause" : "resume";
    const result = await extensionSend(action);
    if (!result?.ok) {
      $("#form-message").textContent = result?.error || "扩展后台没有响应。";
      return;
    }
    applyExtensionState(result.state);
    catReact(
      "",
      action === "pause" ? "先喘口气" : "继续就好",
      action === "pause" ? "计时和标签页监督都暂停了。" : "扩展已经重新盯住当前标签页。"
    );
    beginTimer();
    render();
    return;
  }
  if (state.session.status === "running") {
    state.session.remainingWhenPaused = remainingMs();
    state.session.status = "paused";
    clearInterval(timerHandle);
    timerHandle = null;
    catReact("", "先喘口气", "暂停不是逃跑，记得回来。");
  } else if (state.session.status === "paused") {
    state.session.endAt = Date.now() + Math.max(1000, state.session.remainingWhenPaused);
    state.session.remainingWhenPaused = null;
    state.session.status = "running";
    catReact("", "继续就好", "重新坐下，也算一种能力。");
    beginTimer();
  }
  saveState();
  render();
}

async function stopSession() {
  if (!state.session) return;
  if (EXTENSION_MODE) {
    const result = await extensionSend("stop");
    if (!result?.ok) {
      $("#form-message").textContent = result?.error || "扩展后台没有响应。";
      return;
    }
    applyExtensionState(result.state);
    clearInterval(timerHandle);
    timerHandle = null;
    catReact("annoyed", "这轮先收回", "下次目标可以再小一点，但别假装没开始过。");
    render();
    return;
  }
  state.session = null;
  clearInterval(timerHandle);
  timerHandle = null;
  hiddenAt = null;
  saveState();
  catReact("annoyed", "这轮先收回", "下次目标可以再小一点，但别假装没开始过。");
  render();
}

function completeSession() {
  if (!state.session || state.session.status === "finished") return;
  const minutes = Math.max(1, Math.round(state.session.durationSeconds / 60));
  state.totalMinutes += minutes;
  state.coins += rewardPreview();
  state.completed += 1;
  state.session.status = "finished";
  state.session.finishedAt = Date.now();
  clearInterval(timerHandle);
  timerHandle = null;
  saveState();
  catReact("happy", `${petName()} 有点骄傲`, "完成比完美更会养大一只猫。");
  render();
}

function beginTimer() {
  clearInterval(timerHandle);
  if (EXTENSION_MODE) {
    timerHandle = setInterval(syncExtensionState, 700);
    return;
  }
  timerHandle = setInterval(() => {
    if (state.session?.status === "running" && remainingMs() <= 0) completeSession();
    renderSession();
  }, 500);
}

function reactToExtensionEvent(event) {
  if (!event?.id || event.id === lastExtensionEventId) return;
  lastExtensionEventId = event.id;
  if (event.type === "drift") {
    catReact("annoyed", event.title || "散步路线挺熟", event.message || "回来就好。");
  } else if (event.type === "complete") {
    clearInterval(timerHandle);
    timerHandle = null;
    catReact("happy", `${petName()} 有点骄傲`, event.message || "完成比完美更会养大一只猫。");
  }
}

function applyExtensionState(remote) {
  if (!remote) return;
  state.totalMinutes = Number(remote.totalMinutes || 0);
  state.coins = Number(remote.coins || 0);
  state.completed = Number(remote.completed || 0);
  state.session = remote.session ? { ...remote.session } : null;
  saveState();

  const browser = remote.browser || {};
  if (browser.currentDomain) {
    const verdict = browser.allowed ? "白名单内" : "白名单外";
    $("#event-line").textContent = `当前：${browser.currentDomain} · ${verdict} · 离开白名单持续 8 秒才计为走神。`;
  }
  if (state.session && state.session.driftCount !== lastExtensionDriftCount) {
    lastExtensionDriftCount = state.session.driftCount;
  }
  reactToExtensionEvent(remote.lastEvent);
}

async function syncExtensionState() {
  if (!EXTENSION_MODE || extensionRefreshBusy) return;
  extensionRefreshBusy = true;
  try {
    const result = await extensionSend("state");
    if (result?.ok) {
      applyExtensionState(result.state);
      render();
    }
  } finally {
    extensionRefreshBusy = false;
  }
}

function registerDrift(secondsAway) {
  if (!state.session || state.session.status !== "running" || secondsAway < 8) return;
  state.session.driftCount += 1;
  saveState();
  const funny = state.session.tone === "funny";
  catReact(
    "annoyed",
    funny ? "散步路线挺熟" : `${petName()} 在等你`,
    funny ? `离开 ${secondsAway} 秒，页面没丢，专注先丢了一点。` : "回来就好，把下一小步做完。"
  );
  $("#event-line").textContent = `刚才离开页面 ${secondsAway} 秒，本轮清醒值已调整。`;
  renderSession();
}

function renderSession() {
  const session = state.session;
  const durationMs = (session?.durationSeconds || Number($("#duration").value) * 60) * 1000;
  const remaining = remainingMs();
  const ratio = session ? Math.min(1, Math.max(0, remaining / durationMs)) : 1;
  $("#timer").textContent = session?.status === "finished" ? "完成" : formatTime(remaining);
  $("#timer-progress").style.strokeDasharray = CIRCUMFERENCE;
  $("#timer-progress").style.strokeDashoffset = String(CIRCUMFERENCE * ratio);
  $("#session-title").textContent = session?.goal || "还没有开始";
  $("#session-status").textContent =
    session?.status === "running" ? "专注中" : session?.status === "paused" ? "已暂停" : session?.status === "finished" ? "已完成" : "待机";
  $("#session-status").classList.toggle("active", session?.status === "running");
  $("#timer-caption").textContent =
    session?.status === "running" ? `${petName()} 正在守着这一轮` : session?.status === "paused" ? "时间已暂停" : session?.status === "finished" ? "奖励已结算" : "准备好就开始";
  $("#pause").disabled = !session || session.status === "finished";
  $("#finish").disabled = !session || session.status === "finished";
  $("#pause").textContent = session?.status === "paused" ? "继续" : "暂停";
  $("#drift-count").textContent = session?.driftCount || 0;
  $("#focus-score").textContent = Math.max(20, 100 - (session?.driftCount || 0) * 12);
  $("#coin-preview").textContent = `+${rewardPreview()}`;
}

function renderGrowth() {
  const stages = [
    { at: 0, next: 60, name: "刚到家的幼猫", copy: `${petName()} 会开始认主。` },
    { at: 60, next: 180, name: "会认主的小猫", copy: `${petName()} 会长成少年猫。` },
    { at: 180, next: 420, name: "有点主意的少年猫", copy: `${petName()} 会成为稳定搭档。` },
    { at: 420, next: 900, name: "可靠的专注搭档", copy: `${petName()} 会解锁守护形态。` },
    { at: 900, next: null, name: "守护专注的大猫", copy: "你们已经走了很远。" },
  ];
  const index = stages.findLastIndex((stage) => state.totalMinutes >= stage.at);
  const stage = stages[Math.max(0, index)];
  const progress = stage.next
    ? ((state.totalMinutes - stage.at) / (stage.next - stage.at)) * 100
    : 100;
  $("#total-minutes").textContent = state.totalMinutes;
  $("#coins").textContent = state.coins;
  $("#completed").textContent = state.completed;
  $("#growth-stage").textContent = stage.name;
  $("#growth-fill").style.width = `${Math.min(100, Math.max(0, progress))}%`;
  $("#growth-next").textContent = stage.next
    ? `再专注 ${Math.max(0, stage.next - state.totalMinutes)} 分钟，${stage.copy}`
    : stage.copy;
  $("#pet-name").value = petName();
  const image = $("#hero-pet-image");
  if (!image.classList.contains("annoyed") && !image.classList.contains("happy")) {
    image.src = selectedPetImage(state.session?.status === "running" ? "focus" : "");
  }
}

function render() {
  renderSession();
  renderGrowth();
}

function stopSound() {
  ambientAudio.pause();
  ambientAudio.removeAttribute("src");
  ambientAudio.load();
  document.querySelectorAll(".sound-card").forEach((button) => button.classList.remove("active"));
}

function createPetActionSet(file) {
  return new Promise((resolve, reject) => {
    if (!file?.type?.startsWith("image/")) {
      reject(new Error("请选择 PNG、JPG 或 WebP 图片。"));
      return;
    }
    const objectUrl = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      const actions = {};
      const size = 320;
      const drawFrame = (action) => {
        const canvas = document.createElement("canvas");
        canvas.width = 400;
        canvas.height = 320;
        const context = canvas.getContext("2d", { willReadFrequently: true });
        context.clearRect(0, 0, canvas.width, canvas.height);
        context.fillStyle = "rgba(21, 73, 52, .18)";
        context.beginPath();
        context.ellipse(200, 292, 132, 18, 0, 0, Math.PI * 2);
        context.fill();

        const sourceRatio = image.naturalWidth / image.naturalHeight;
        let sourceWidth = image.naturalWidth;
        let sourceHeight = image.naturalHeight;
        if (sourceRatio > 1) sourceWidth = image.naturalHeight;
        else sourceHeight = image.naturalWidth;
        const sourceX = (image.naturalWidth - sourceWidth) / 2;
        const sourceY = Math.max(0, (image.naturalHeight - sourceHeight) * .38);

        context.save();
        context.translate(200, 154);
        if (action === "wiggle") context.rotate(-.07);
        context.beginPath();
        context.ellipse(0, 0, size / 2, size / 2, 0, 0, Math.PI * 2);
        context.clip();
        context.filter = action === "angry"
          ? "saturate(1.08) contrast(1.2)"
          : "saturate(1.24) contrast(1.1)";
        context.drawImage(
          image,
          sourceX,
          sourceY,
          sourceWidth,
          sourceHeight,
          -size / 2,
          -size / 2,
          size,
          size,
        );
        context.restore();
        const pixels = context.getImageData(40, 0, size, size);
        for (let index = 0; index < pixels.data.length; index += 4) {
          pixels.data[index] = Math.round(pixels.data[index] / 24) * 24;
          pixels.data[index + 1] = Math.round(pixels.data[index + 1] / 24) * 24;
          pixels.data[index + 2] = Math.round(pixels.data[index + 2] / 24) * 24;
        }
        context.putImageData(pixels, 40, 0);

        context.strokeStyle = "#f6efd9";
        context.lineWidth = 8;
        context.beginPath();
        context.ellipse(200, 154, size / 2, size / 2, 0, 0, Math.PI * 2);
        context.stroke();
        if (action === "happy") {
          context.fillStyle = "rgba(245, 132, 145, .7)";
          context.beginPath(); context.ellipse(126, 208, 24, 11, 0, 0, Math.PI * 2); context.fill();
          context.beginPath(); context.ellipse(274, 208, 24, 11, 0, 0, Math.PI * 2); context.fill();
          context.fillStyle = "#fff4cf";
          context.font = "32px sans-serif";
          context.fillText("♡", 304, 90);
        } else if (action === "wiggle") {
          context.strokeStyle = "#8bc59a";
          context.lineWidth = 6;
          context.beginPath(); context.arc(45, 150, 28, -.8, .8); context.stroke();
          context.beginPath(); context.arc(355, 130, 28, 2.3, 3.9); context.stroke();
        } else if (action === "angry") {
          context.strokeStyle = "#63343a";
          context.lineWidth = 9;
          context.beginPath(); context.moveTo(130, 116); context.lineTo(176, 132); context.stroke();
          context.beginPath(); context.moveTo(224, 132); context.lineTo(270, 116); context.stroke();
          context.fillStyle = "#e47a72";
          context.beginPath(); context.moveTo(334, 222); context.lineTo(374, 206); context.lineTo(362, 250); context.fill();
        }
        return canvas.toDataURL("image/webp", .72);
      };
      ["idle", "happy", "wiggle", "angry"].forEach((action) => {
        actions[action] = drawFrame(action);
      });
      URL.revokeObjectURL(objectUrl);
      resolve({ portrait: actions.idle, actions });
    };
    image.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      reject(new Error("这张图片没能读出来，请换一张试试。"));
    };
    image.src = objectUrl;
  });
}

async function previewPetPhoto() {
  const file = $("#pet-photo").files?.[0];
  if (!file) return;
  try {
    const generated = await createPetActionSet(file);
    pendingPetImage = generated.portrait;
    pendingPetActions = generated.actions;
    $("#hero-pet-image").src = pendingPetImage;
    $("#form-message").textContent = "已在本机生成待机、害羞、扭身和生气四种动作，保存后正式入住。";
  } catch (error) {
    $("#form-message").textContent = error.message;
  }
}

function savePet() {
  state.petName = $("#pet-name").value.trim().slice(0, 12) || "Luna";
  state.petImage = pendingPetImage || null;
  state.petActions = pendingPetActions || null;
  try {
    saveState();
  } catch {
    state.petImage = null;
    state.petActions = null;
    pendingPetImage = null;
    pendingPetActions = null;
    saveState();
    $("#form-message").textContent = "图片太大，浏览器房间放不下；请换一张更小的。";
    render();
    return;
  }
  catReact("happy", `${petName()} 正式入住`, "照片和名字只留在这台设备的当前浏览器。");
  $("#form-message").textContent = "领养信息已保存。";
  renderGrowth();
}

function resetPet() {
  state.petName = "Luna";
  state.petImage = null;
  state.petActions = null;
  pendingPetImage = null;
  pendingPetActions = null;
  $("#pet-photo").value = "";
  saveState();
  catReact("happy", "Luna 回来了", "原装小猫重新接管了计时岗位。");
  $("#form-message").textContent = "已恢复默认宠物。";
  renderGrowth();
}

async function playSound(source, button) {
  stopSound();
  ambientAudio.src = new URL(source, location.href).href;
  try {
    await ambientAudio.play();
    button.classList.add("active");
  } catch {
    $("#form-message").textContent = "声音没有开始播放，请再点一次或检查浏览器是否允许音频。";
  }
}

$("#goal").addEventListener("input", renderPlan);
$("#allowed-domains").addEventListener("input", () => {
  domainsTouched = true;
});
$("#duration").addEventListener("change", renderSession);
$("#start").addEventListener("click", startSession);
$("#pause").addEventListener("click", pauseOrResume);
$("#finish").addEventListener("click", stopSession);
$("#use-current-domain").addEventListener("click", async () => {
  const result = await extensionSend("activeTab");
  const domain = result?.state?.domain || initialDomain;
  if (domain) {
    addAllowedDomain(domain);
    $("#form-message").textContent = `已把 ${domain} 加入本轮白名单。`;
  } else {
    $("#form-message").textContent = "当前没有可识别的网站，请直接输入域名。";
  }
});
$("#pet-photo").addEventListener("change", previewPetPhoto);
$("#save-pet").addEventListener("click", savePet);
$("#reset-pet").addEventListener("click", resetPet);
document.querySelectorAll("[data-sound]").forEach((button) => {
  button.addEventListener("click", () => playSound(button.dataset.sound, button));
});
$("#sound-stop").addEventListener("click", stopSound);
$("#hero-pet-image").addEventListener("load", () => {
  $("#hero-pet-image").hidden = false;
  $("#hero-cat").style.display = "none";
});
$("#hero-pet-image").addEventListener("error", () => {
  $("#hero-pet-image").hidden = true;
  $("#hero-cat").style.display = "block";
});

document.addEventListener("visibilitychange", () => {
  if (EXTENSION_MODE) return;
  if (!state.session || state.session.status !== "running") return;
  if (document.hidden) {
    hiddenAt = Date.now();
  } else if (hiddenAt) {
    registerDrift(Math.round((Date.now() - hiddenAt) / 1000));
    hiddenAt = null;
  }
});

async function initialize() {
  if (EXTENSION_MODE) {
    document.title = "Focus · 完整专注台";
    $("#edition-label").textContent = "COMPLETE EXTENSION";
    $("#privacy-pill").textContent = "扩展已连接 · 仅本机";
    $("#download-link").textContent = "查看项目";
    $("#hero-intro").textContent =
      "写下目标，扩展会把场景建议变成本轮网站白名单。即使切换标签页，Luna 也会在后台守住计时和奖励。";
    $("#use-current-domain").hidden = false;
    $("#monitor-mode-note").textContent =
      "扩展只读取当前标签页的域名和标题用于本轮判断；数据保存在浏览器本机。白名单外持续 8 秒才会提醒。";
    $("#drift-label").textContent = "白名单外";
    $("footer span").textContent = "Focus Complete · 专注数据仅保存在扩展本机";

    const fromQuery = normalizeDomain(new URLSearchParams(location.search).get("domain"));
    const active = await extensionSend("activeTab");
    initialDomain = fromQuery || normalizeDomain(active?.state?.domain);
    if (initialDomain) setAllowedDomains([initialDomain]);

    const current = await extensionSend("state");
    if (current?.ok) {
      lastExtensionEventId = current.state?.lastEvent?.id || 0;
      applyExtensionState(current.state);
      if (state.session?.allowedDomains?.length) {
        setAllowedDomains(state.session.allowedDomains);
        domainsTouched = true;
      }
      if (state.session?.status === "running" || state.session?.status === "paused") beginTimer();
    } else {
      $("#form-message").textContent = "扩展后台没有响应，请在扩展管理页重新加载 Focus。";
    }
  } else if (state.session?.status === "running") {
    if (remainingMs() <= 0) completeSession();
    else beginTimer();
  }
  renderPlan();
  render();
}

initialize();

if (!EXTENSION_MODE && "serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("sw.js"));
}
