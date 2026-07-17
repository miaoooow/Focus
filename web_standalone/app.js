const $ = (selector) => document.querySelector(selector);
const STORAGE_KEY = "focus-buddy-web-v1";
const CIRCUMFERENCE = 2 * Math.PI * 96;

const scenes = [
  { name: "编程开发", keys: ["代码", "编程", "python", "java", "开发", "debug"], tools: ["代码编辑器", "终端", "项目文件"] },
  { name: "文档写作", keys: ["文档", "报告", "论文", "简历", "写作"], tools: ["文档编辑器", "资料参考", "文件夹"] },
  { name: "课程学习", keys: ["作业", "课程", "复习", "高数", "英语", "学习"], tools: ["课程资料", "笔记", "计算工具"] },
  { name: "数据整理", keys: ["数据", "excel", "表格", "统计", "分析"], tools: ["表格软件", "数据文件", "计算器"] },
  { name: "演示设计", keys: ["ppt", "演示", "答辩", "设计", "原型"], tools: ["演示软件", "素材文件", "参考资料"] },
  { name: "视频剪辑", keys: ["视频", "剪辑", "播客", "录音"], tools: ["剪辑软件", "素材文件", "音频工具"] },
];

const defaults = {
  totalMinutes: 0,
  coins: 0,
  completed: 0,
  session: null,
  petName: "Luna",
  petImage: null,
};

let state = loadState();
let timerHandle = null;
let hiddenAt = null;
let audioContext = null;
let soundNodes = [];
let pendingPetImage = state.petImage;

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
  const selected = matched.length ? matched.slice(0, 2) : [{ name: "专注任务", tools: ["任务资料", "必要工具"] }];
  return {
    names: selected.map((scene) => scene.name),
    tools: [...new Set(selected.flatMap((scene) => scene.tools))],
  };
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
    return;
  }
  const plan = parseGoal(goal);
  $("#plan-result").innerHTML = `
    <p>识别为 <b>${plan.names.join(" + ")}</b>。网页版不会读取其他软件，建议开始前准备：</p>
    <div class="plan-chips">${plan.tools.map((tool) => `<span>${tool}</span>`).join("")}</div>
  `;
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
  image.src = state.petImage || defaultPetImage(kind);
  $("#cat-note-title").textContent = title;
  $("#cat-note").textContent = note;
}

function startSession() {
  const goal = $("#goal").value.trim();
  if (!goal) {
    $("#form-message").textContent = `${petName()} 还不知道该盯哪件事，请先写下目标。`;
    $("#goal").focus();
    return;
  }
  const durationMinutes = Number($("#duration").value);
  const durationSeconds = durationMinutes * 60;
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

function pauseOrResume() {
  if (!state.session) return;
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

function stopSession() {
  if (!state.session) return;
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
  timerHandle = setInterval(() => {
    if (state.session?.status === "running" && remainingMs() <= 0) completeSession();
    renderSession();
  }, 500);
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
    image.src = state.petImage || defaultPetImage(state.session?.status === "running" ? "focus" : "");
  }
}

function render() {
  renderSession();
  renderGrowth();
}

function stopSound() {
  soundNodes.forEach((node) => {
    try { node.stop?.(); } catch {}
    try { node.disconnect?.(); } catch {}
  });
  soundNodes = [];
  document.querySelectorAll(".sound-card").forEach((button) => button.classList.remove("active"));
}

function compressPetPhoto(file) {
  return new Promise((resolve, reject) => {
    if (!file?.type?.startsWith("image/")) {
      reject(new Error("请选择 PNG、JPG 或 WebP 图片。"));
      return;
    }
    const objectUrl = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      const maxSide = 512;
      const scale = Math.min(1, maxSide / Math.max(image.naturalWidth, image.naturalHeight));
      const canvas = document.createElement("canvas");
      canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
      canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
      canvas.getContext("2d").drawImage(image, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(objectUrl);
      resolve(canvas.toDataURL("image/jpeg", .82));
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
    pendingPetImage = await compressPetPhoto(file);
    $("#hero-pet-image").src = pendingPetImage;
    $("#form-message").textContent = "新伙伴已经试穿完毕，点“保存领养信息”正式入住。";
  } catch (error) {
    $("#form-message").textContent = error.message;
  }
}

function savePet() {
  state.petName = $("#pet-name").value.trim().slice(0, 12) || "Luna";
  state.petImage = pendingPetImage || null;
  try {
    saveState();
  } catch {
    state.petImage = null;
    pendingPetImage = null;
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
  pendingPetImage = null;
  $("#pet-photo").value = "";
  saveState();
  catReact("happy", "Luna 回来了", "原装小猫重新接管了计时岗位。");
  $("#form-message").textContent = "已恢复默认宠物。";
  renderGrowth();
}

function createNoiseBuffer(context) {
  const length = context.sampleRate * 3;
  const buffer = context.createBuffer(1, length, context.sampleRate);
  const data = buffer.getChannelData(0);
  for (let index = 0; index < length; index += 1) data[index] = Math.random() * 2 - 1;
  return buffer;
}

async function playSound(type, button) {
  stopSound();
  audioContext ||= new AudioContext();
  await audioContext.resume();
  const source = audioContext.createBufferSource();
  source.buffer = createNoiseBuffer(audioContext);
  source.loop = true;
  const filter = audioContext.createBiquadFilter();
  const gain = audioContext.createGain();
  const settings = {
    rain: { kind: "highpass", frequency: 900, gain: 0.12 },
    stream: { kind: "bandpass", frequency: 1500, gain: 0.09 },
    wind: { kind: "lowpass", frequency: 420, gain: 0.16 },
  }[type];
  filter.type = settings.kind;
  filter.frequency.value = settings.frequency;
  gain.gain.value = settings.gain;
  source.connect(filter).connect(gain).connect(audioContext.destination);
  source.start();
  soundNodes = [source, filter, gain];
  button.classList.add("active");
}

$("#goal").addEventListener("input", renderPlan);
$("#duration").addEventListener("change", renderSession);
$("#start").addEventListener("click", startSession);
$("#pause").addEventListener("click", pauseOrResume);
$("#finish").addEventListener("click", stopSession);
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
  if (!state.session || state.session.status !== "running") return;
  if (document.hidden) {
    hiddenAt = Date.now();
  } else if (hiddenAt) {
    registerDrift(Math.round((Date.now() - hiddenAt) / 1000));
    hiddenAt = null;
  }
});

if (state.session?.status === "running") {
  if (remainingMs() <= 0) completeSession();
  else beginTimer();
}
renderPlan();
render();

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("sw.js"));
}
