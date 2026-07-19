const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

let currentPlan = null;
let currentState = null;
let profileSignature = "";
let toastTimer = 0;
let rewardShown = false;
let reactionTimer = 0;
let soundLibrary = { tracks: [], categories: [] };
let currentSoundIndex = -1;
let activeSoundCategory = "all";
let synthAudioContext = null;
let synthNodes = [];
let synthPlaying = false;
let synthStartedAt = 0;
let synthElapsedSeconds = 0;
let synthGain = null;
let cloudAISettings = null;
let currentPetActionAssets = {};
let currentPetGrowthAsset = "";

const goalInput = $("#goal-input");
const planButton = $("#plan-button");
const aiPlanToggle = $("#ai-plan-toggle");
const startButton = $("#start-button");
const sceneList = $("#scene-list");
const ambientAudio = $("#ambient-audio");

const STORY_SCENES = {
  idle: { image: "/media/picture/relax.png", kicker: "CAT CAM · RESTING", alt: "小猫放松地躺着", line: (name) => `${name}正在假装不在意你。` },
  focus: { image: "/media/picture/focus.png", kicker: "CAT CAM · DEEP WORK", alt: "小猫认真使用电脑", line: (name) => `${name}已进入陪跑模式：你写，它盯。` },
  confused: { image: "/media/picture/confused.png", kicker: "CAT CAM · WAIT, WHAT?", alt: "小猫困惑地观察", line: (name) => `${name}歪头：这个页面也在计划里吗？` },
  spill: { image: "/media/picture/split_cup.png", kicker: "CAT CAM · CUP DOWN", alt: "小猫不小心打翻了杯子", line: (name) => `${name}把杯子碰倒了。看来它比你先急。` },
  scared: { image: "/media/picture/scared.png", kicker: "CAT CAM · ABORTED", alt: "小猫受到惊吓", line: (name) => `${name}被提前结束吓成了问号。` },
  celebrate: { image: "/media/picture/happy.png", kicker: "CAT CAM · WE DID IT", alt: "小猫开心庆祝", line: (name) => `${name}已开始庆功，你也可以喘口气。` },
  gift: { image: "/media/picture/gift.png", kicker: "CAT CAM · LEVEL UP", alt: "小猫从礼物盒中出现", line: (name) => `${name}带着升级礼物来报到。` },
};

Object.values(STORY_SCENES).forEach((scene) => {
  const image = new Image();
  image.src = scene.image;
});

async function api(path, payload = null) {
  const options = payload === null ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  };
  const response = await fetch(path, options);
  const result = await response.json().catch(() => ({ ok: false, error: "本地服务返回异常" }));
  if (!response.ok || !result.ok) throw new Error(result.error || "请求失败");
  return result.data;
}

function showToast(message, error = false) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.toggle("error", error);
  toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("show"), 2800);
}

function targetLabel(target) {
  const labels = {
    "code.exe": "VS Code", "windowsterminal.exe": "终端", "winword.exe": "Word",
    "wps.exe": "WPS文字", "powerpnt.exe": "PowerPoint", "wpp.exe": "WPS演示",
    "excel.exe": "Excel", "et.exe": "WPS表格", "acrord32.exe": "PDF阅读器",
    "photoshop.exe": "Photoshop", "devenv.exe": "Visual Studio",
    "msedge.exe": "Edge 浏览器", "chrome.exe": "Chrome 浏览器", "firefox.exe": "Firefox 浏览器",
  };
  if (target.kind === "domain") return `网址 · ${String(target.value)}`;
  if (target.kind === "window_title") return `页面 · ${String(target.value)}`;
  return labels[String(target.value).toLowerCase()] || String(target.value).replace(/\.exe$/i, "");
}

function looksLikeWebAddress(value) {
  return /^(?:https?:\/\/)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:[/:?#]|$)/i.test(String(value).trim());
}

function createTargetChip(target, checked = true) {
  const label = document.createElement("label");
  label.className = "target-chip";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.className = "target-check";
  input.checked = checked;
  input.dataset.target = JSON.stringify(target);
  const text = document.createElement("span");
  text.textContent = targetLabel(target);
  label.append(input, text);
  return label;
}

function renderScenes() {
  sceneList.replaceChildren();
  const scenes = currentPlan?.scenes || [];
  if (!scenes.length) {
    sceneList.className = "scene-list empty-scenes";
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<span>✦</span><p>这个目标不需要软件，或者请选择完全离屏。</p>";
    sceneList.append(empty);
    return;
  }
  sceneList.className = "scene-list";
  scenes.forEach((scene, index) => {
    const card = document.createElement("article");
    card.className = "scene-card";
    card.style.animationDelay = `${Math.min(index * 45, 180)}ms`;
    const title = document.createElement("h3");
    title.textContent = scene.name;
    const description = document.createElement("p");
    description.textContent = scene.description;
    const targets = document.createElement("div");
    targets.className = "target-list";
    scene.targets.forEach((target) => targets.append(createTargetChip(target)));
    card.append(title, description, targets);
    sceneList.append(card);
  });
}

function setSegment(container, attribute, value) {
  $$(`${container} button`).forEach((button) => {
    button.classList.toggle("active", button.dataset[attribute] === String(value));
  });
}

function selectedValue(container, attribute, fallback) {
  return $(`${container} button.active`)?.dataset[attribute] || fallback;
}

function selectedTargets() {
  return $$(".target-check:checked").map((input) => JSON.parse(input.dataset.target));
}

async function planGoal() {
  const goal = goalInput.value.trim();
  if (!goal) {
    showToast("先写下这轮要完成的结果", true);
    goalInput.focus();
    return null;
  }
  planButton.disabled = true;
  planButton.classList.add("loading");
  const useAI = Boolean(aiPlanToggle?.checked);
  const cloudMode = cloudAISettings?.text_provider === "openrouter";
  planButton.querySelectorAll("span")[1].textContent = useAI
    ? (cloudMode ? "云端AI正在理解" : "本机AI正在理解")
    : "正在匹配场景";
  $("#ai-model-pill").dataset.state = useAI ? "thinking" : "local";
  $("#model-status").textContent = useAI
    ? (cloudMode ? "云端AI思考中" : "本机AI思考中")
    : "本地场景库";
  $("#plan-note").textContent = useAI
    ? "AI只负责理解目标；最终权限仍由本地规则校验。"
    : "无需模型，使用内置场景数据库立即解析。";
  try {
    currentPlan = await api("/api/plan", { goal, use_ai: useAI });
    renderScenes();
    const config = currentPlan.config;
    setSegment("#mode-control", "mode", config.mode);
    setSegment("#duration-control", "minutes", config.duration_minutes);
    $("#custom-duration").value = config.duration_minutes;
    setSegment("#intensity-control", "intensity", config.roast_intensity);
    $("#plan-source").textContent = `${currentPlan.source} · ${currentPlan.scenes.length}个场景`;
    $("#plan-note").textContent = currentPlan.fallback_reason
      ? "所选AI暂时不可用，已自动使用内置场景库，不影响本轮专注。"
      : (currentPlan.detail || "勾选结果是最终白名单；不确定的工具不会偷偷获得权限。");
    $("#model-status").textContent = currentPlan.source;
    $("#ai-model-pill").dataset.state = currentPlan.ai_used ? "ready" : (useAI ? "fallback" : "local");
    showToast(currentPlan.ai_used
      ? `AI已理解，拆出 ${currentPlan.scenes.length} 个任务场景`
      : `本地规划完成 · ${currentPlan.scenes.length} 个场景`);
    return currentPlan;
  } catch (error) {
    showToast(error.message, true);
    $("#plan-note").textContent = "规划失败了，但不会影响已经开始的专注。";
    return null;
  } finally {
    planButton.disabled = false;
    planButton.classList.remove("loading");
    planButton.querySelectorAll("span")[1].textContent = aiPlanToggle?.checked
      ? "AI解析任务场景"
      : "本地解析任务场景";
  }
}

function buildConfig() {
  const mode = selectedValue("#mode-control", "mode", "whitelist");
  const duration = Math.max(1, Math.min(480, Number($("#custom-duration").value) || 45));
  const intensity = selectedValue("#intensity-control", "intensity", "mild");
  const targets = mode === "blackout" ? [] : selectedTargets();
  if (mode !== "blackout" && !targets.length) throw new Error("至少保留一个工具，或选择完全离屏");
  return {
    ...currentPlan.config,
    duration_minutes: duration,
    mode,
    allowed_targets: mode === "whitelist" ? targets : [],
    blocked_targets: mode === "blacklist" ? targets : [],
    roast_intensity: intensity,
    needs_clarification: false,
    clarification_question: "",
  };
}

async function startSession() {
  const goal = goalInput.value.trim();
  if (!currentPlan || currentPlan.goal !== goal) {
    const planned = await planGoal();
    if (!planned) return;
  }
  try {
    const config = buildConfig();
    currentState = await api("/api/session/start", { goal, config });
    rewardShown = false;
    renderState(currentState);
    showToast(currentState.browser_bridge?.connected
      ? "本轮开始。小猫已上岗。"
      : "本轮已开始。正在等待扩展上报，连接恢复前不会误扣。");
  } catch (error) {
    showToast(error.message, true);
  }
}

function formatClock(seconds) {
  const value = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(value / 60);
  return `${String(minutes).padStart(2, "0")}:${String(value % 60).padStart(2, "0")}`;
}

function renderCatStory(state) {
  let story = "idle";
  if (state.state === "completed" && state.reward?.grew_up) story = "gift";
  else if (state.state === "completed") story = "celebrate";
  else if (state.state === "stopped") story = "scared";
  else if (state.violating && Number(state.alert_count || 0) > 0) story = "spill";
  else if (state.violating) story = "confused";
  else if (state.state === "running") story = "focus";
  else if (state.state === "paused") story = "idle";

  const frame = $("#cat-story");
  const scene = STORY_SCENES[story];
  if (frame.dataset.story !== story) {
    frame.dataset.story = story;
    const image = $("#cat-story-image");
    const head = $("#cat-story-head");
    image.classList.remove("scene-enter");
    frame.classList.remove("story-playing");
    image.src = scene.image;
    image.alt = scene.alt;
    head.src = scene.image;
    requestAnimationFrame(() => {
      image.classList.add("scene-enter");
      frame.classList.add("story-playing");
    });
  }
  $("#story-kicker").textContent = scene.kicker;
  const catName = state.profile?.pet?.name || state.profile?.cat_name || "Luna";
  $("#cat-line").textContent = scene.line(catName);
}

function stateLabel(state) {
  return ({ idle: "NOT STARTED", running: "FOCUSING", paused: "PAUSED", completed: "COMPLETED", stopped: "STOPPED" })[state] || String(state).toUpperCase();
}

function renderSuggestion(suggestions) {
  const box = $("#smart-suggestion");
  const suggestion = suggestions?.[0];
  if (!suggestion) {
    box.hidden = true;
    box.replaceChildren();
    return;
  }
  box.hidden = false;
  box.replaceChildren();
  const title = document.createElement("h3");
  title.textContent = `${suggestion.label} 像是任务队友`;
  const reason = document.createElement("p");
  reason.textContent = `${suggestion.reason} · 缓冲 ${suggestion.soft_remaining_seconds}s`;
  const actions = document.createElement("div");
  actions.className = "suggestion-actions";
  const definitions = [
    ["本轮允许", "/api/suggestion/approve", { id: suggestion.id, remember: false }],
    ["以后允许", "/api/suggestion/approve", { id: suggestion.id, remember: true }],
    ["不是队友", "/api/suggestion/dismiss", { id: suggestion.id }],
  ];
  definitions.forEach(([label, path, payload]) => {
    const button = document.createElement("button");
    button.textContent = label;
    button.addEventListener("click", async () => {
      try { await api(path, payload); await refreshState(); }
      catch (error) { showToast(error.message, true); }
    });
    actions.append(button);
  });
  box.append(title, reason, actions);
}

function renderState(state) {
  if (!state) return;
  currentState = state;
  const live = ["running", "paused"].includes(state.state);
  const total = Math.max(1, state.total_seconds || currentPlan?.config?.duration_minutes * 60 || 2700);
  const progress = Math.max(0, Math.min(1, state.remaining_seconds / total));
  const displaySeconds = state.state === "idle" && !state.total_seconds ? total : state.remaining_seconds;
  $("#timer-text").textContent = formatClock(displaySeconds);
  $("#ring-progress").style.strokeDashoffset = String(603.19 * (1 - progress));
  $("#session-state-pill").textContent = stateLabel(state.state);
  $("#session-state-pill").classList.toggle("live", state.state === "running");
  $("#alert-count").textContent = `${state.alert_count || 0} 次偏航`;
  $("#current-window").textContent = state.current || "等待开始";
  $("#smart-status").textContent = state.smart_allow || "关联工具会先智能缓冲，不会立刻打扰。";
  $("#session-panel").classList.toggle("session-live", state.state === "running");
  const livePenalty = state.penalty || { focus_score: 100 };
  const veryAngry = Boolean(state.violating && livePenalty.focus_score <= 40);
  $("#session-panel").classList.toggle("cat-alerting", Boolean(state.violating && !veryAngry));
  $("#session-panel").classList.toggle("cat-angry", veryAngry || state.state === "stopped");
  $("#session-panel").classList.toggle("cat-celebrate", Boolean(state.reward && state.state === "completed"));
  $("#session-panel").classList.toggle("cat-curious", Boolean(state.suggestions?.length));
  renderCatStory(state);
  $("#pause-button").disabled = !live;
  $("#stop-button").disabled = !live;
  $("#pause-button").textContent = state.state === "paused" ? "继续" : "暂停";
  startButton.disabled = live;
  renderSuggestion(state.suggestions);
  const penalty = state.penalty || {
    alert_count: 0, focus_score: 100, grade: "S", coins_lost: 0,
    xp_lost: 0, next_penalty_points: 8,
  };
  $("#focus-score").textContent = penalty.focus_score;
  $("#focus-score-bar").style.width = `${penalty.focus_score}%`;
  $("#focus-score-bar").style.backgroundPosition = `${penalty.focus_score}% 0`;
  $("#focus-grade").textContent = penalty.grade;
  $("#penalty-panel").dataset.grade = penalty.grade;
  $("#penalty-copy").textContent = penalty.alert_count
    ? `本轮已少 ${penalty.coins_lost} 猫币、${penalty.xp_lost} XP加成`
    : `第一次偏航：清醒值 -${penalty.next_penalty_points}，预计少 2 猫币`;
  renderProfile(state.profile || {});
  renderDatabase(state.relation_database || {}, state.roast_database || {});
  renderBrowserBridge(state.browser_bridge || {});
  if (state.cloud_ai) cloudAISettings = state.cloud_ai;
  renderAIPlanner(state.ai_planner || {});
  if (state.reward && !rewardShown) {
    rewardShown = true;
    showToast(state.reward.grew_up
      ? `${state.reward.pet_name}长大了 · 清醒值 ${state.reward.focus_score}`
      : `清醒值 ${state.reward.focus_score} · +${state.reward.coins} 猫币 · 损失 ${state.reward.coins_lost} 枚`);
  }
}

function renderAIPlanner(status) {
  if (!status || currentPlan) return;
  const pill = $("#ai-model-pill");
  const state = status.state || "not_checked";
  pill.dataset.state = state;
  const labels = {
    not_checked: "本地模式就绪",
    thinking: cloudAISettings?.text_provider === "openrouter" ? "云端AI思考中" : "本机AI思考中",
    fallback: "AI离线 · 本地接管",
    local: "本地场景库",
    ready: `${cloudAISettings?.text_provider === "openrouter" ? "云端AI" : "本机AI"} · ${status.model || "Ollama"}`,
  };
  $("#model-status").textContent = labels[state] || "本地模式就绪";
}

function renderProfile(profile) {
  const pet = profile.pet || {
    name: profile.cat_name || "Luna",
    stage: profile.cat_stage || "刚到家的幼猫",
    stage_index: 0,
    growth_minutes: profile.total_minutes || 0,
    next_stage_minutes: 60,
    minutes_to_next_stage: Math.max(0, 60 - (profile.total_minutes || 0)),
    progress_percent: 0,
    meals_served: 0,
    mood: "等着第一顿专注猫粮，也等着认识你",
  };
  const signature = JSON.stringify(profile);
  const skin = pet.skin || profile.cat_skin || "tuxedo";
  const catalog = Array.isArray(profile.cat_skins) ? profile.cat_skins : [];
  const selectedSkin = catalog.find((item) => item.id === skin);
  const safeSkin = ["orange", "tuxedo", "ragdoll"].includes(skin) ? skin : "tuxedo";
  const adultAsset = selectedSkin?.asset_url || `/assets/cat-story-skins/${safeSkin}-adult-v2.png`;
  const youngAsset = selectedSkin?.young_asset_url || `/assets/cat-story-skins/${safeSkin}-young-v2.png`;
  const customStages = Array.isArray(selectedSkin?.stage_assets) ? selectedSkin.stage_assets : [];
  const customStageIndex = Math.min(3, Math.max(0, Number(pet.stage_index || 0)));
  const assetUrl = customStages[customStageIndex]
    || (Number(pet.stage_index || 0) <= 1 ? youngAsset : adultAsset);
  currentPetGrowthAsset = assetUrl;
  currentPetActionAssets = selectedSkin?.action_assets || {};
  $("#rail-cat-image").src = assetUrl;
  const focusCatSprite = $(".cat-sprite");
  if (focusCatSprite) focusCatSprite.style.backgroundImage = `url('${assetUrl}')`;
  $(".nurture-kitten").style.backgroundImage = `url('${assetUrl}')`;
  $(".nurture-head").style.backgroundImage = `url('${assetUrl}')`;
  $$('[data-cat-skin]').forEach((button) => {
    const active = button.dataset.catSkin === skin;
    button.classList.toggle("selected", active);
    button.setAttribute("aria-checked", active ? "true" : "false");
  });
  renderCustomPets(catalog.filter((item) => item.custom), skin);
  $("#streak-metric").textContent = profile.current_streak || 0;
  $("#minutes-metric").textContent = profile.total_minutes || 0;
  $("#coins-metric").textContent = profile.coins || 0;
  $("#rail-cat-name").textContent = pet.name;
  $("#rail-cat-stage").textContent = pet.stage;
  $("#preview-cat-button span").textContent = `叫${pet.name}出来`;
  if (signature === profileSignature) return;
  profileSignature = signature;

  $("#pet-name-heading").textContent = pet.name;
  $("#pet-stage-title").textContent = pet.stage;
  $("#pet-mood").textContent = pet.mood;
  if (document.activeElement !== $("#pet-name-input")) $("#pet-name-input").value = pet.name;
  $("#pet-care-minutes").textContent = pet.growth_minutes || 0;
  $("#pet-meals").textContent = pet.meals_served || 0;
  $("#pet-growth-progress").style.width = `${pet.progress_percent || 0}%`;
  $("#pet-growth-copy").textContent = pet.minutes_to_next_stage > 0
    ? `${pet.growth_minutes} / ${pet.next_stage_minutes} 分钟 · 还差 ${pet.minutes_to_next_stage}`
    : `${pet.growth_minutes} 分钟 · 已解锁全部阶段`;
  $("#pet-room").dataset.stage = String(pet.stage_index || 0);
  $("#session-panel").dataset.petStage = String(pet.stage_index || 0);
  $$('[data-stage-step]').forEach((step) => {
    const index = Number(step.dataset.stageStep);
    step.classList.toggle("complete", index < Number(pet.stage_index || 0));
    step.classList.toggle("active", index === Number(pet.stage_index || 0));
  });
  $("#level-stage").textContent = `${pet.name} · ${pet.stage}`;
  $("#level-number").textContent = profile.level || 1;
  const levelProgress = Math.max(0, Math.min(100, ((profile.level_progress || 0) / (profile.level_target || 250)) * 100));
  $("#level-progress").style.width = `${levelProgress}%`;
  $("#level-copy").textContent = `${profile.level_progress || 0} / ${profile.level_target || 250} XP`;
  $("#growth-summary").textContent = `累计 ${profile.total_minutes || 0} 分钟 · 完成 ${profile.completed_sessions || 0} 轮 · 最长连续 ${profile.best_streak || 0} 天`;

  const week = profile.weekly_minutes || [];
  const chart = $("#week-chart");
  chart.replaceChildren();
  const maxMinutes = Math.max(30, ...week.map((item) => item.minutes || 0));
  week.forEach((item) => {
    const wrapper = document.createElement("div");
    wrapper.className = "day-bar";
    const bar = document.createElement("i");
    bar.style.height = `${Math.max(3, ((item.minutes || 0) / maxMinutes) * 100)}%`;
    bar.title = `${item.minutes || 0} 分钟`;
    const label = document.createElement("span");
    label.textContent = item.date?.slice(5).replace("-", "/") || "--";
    wrapper.append(bar, label);
    chart.append(wrapper);
  });

  const badgeList = $("#badge-list");
  badgeList.replaceChildren();
  (profile.badges || []).slice(0, 5).forEach((badge) => {
    const item = document.createElement("div");
    item.className = `badge-item${badge.unlocked ? " unlocked" : ""}`;
    const icon = document.createElement("span");
    icon.className = "badge-icon";
    icon.textContent = badge.unlocked ? "✦" : "·";
    const copy = document.createElement("div");
    const name = document.createElement("b");
    name.textContent = badge.name;
    const description = document.createElement("small");
    description.textContent = badge.unlocked ? "已解锁" : `${badge.progress}/${badge.target} · ${badge.description}`;
    copy.append(name, description);
    item.append(icon, copy);
    badgeList.append(item);
  });

  const historyList = $("#history-list");
  historyList.replaceChildren();
  const history = [...(profile.history || [])].reverse().slice(0, 6);
  if (!history.length) {
    const empty = document.createElement("div");
    empty.className = "history-empty";
    empty.textContent = "完成第一轮后，证据会出现在这里。";
    historyList.append(empty);
  }
  history.forEach((session) => {
    const item = document.createElement("div");
    item.className = "history-item";
    const date = document.createElement("time");
    date.textContent = session.date;
    const goal = document.createElement("b");
    goal.textContent = session.goal || "未命名目标";
    const result = document.createElement("small");
    result.textContent = session.completed
      ? `${session.minutes}m · 清醒${session.focus_score ?? 100} · +${session.xp}XP`
      : `${session.minutes}m · 提前结束`;
    item.append(date, goal, result);
    historyList.append(item);
  });
}

function renderCustomPets(items, selectedSkin) {
  const list = $("#custom-pet-list");
  if (!list) return;
  list.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "custom-pet-empty";
    empty.textContent = "还没有自定义伙伴，上传一张正脸清晰的照片试试。";
    list.append(empty);
    return;
  }
  items.forEach((pet) => {
    const card = document.createElement("article");
    card.className = `custom-pet-card${pet.id === selectedSkin ? " selected" : ""}`;
    const image = document.createElement("img");
    image.src = pet.young_asset_url || pet.asset_url;
    image.alt = pet.name;
    const copy = document.createElement("span");
    const name = document.createElement("b");
    name.textContent = pet.name;
    const detail = document.createElement("small");
    detail.textContent = pet.id === selectedSkin ? "正在陪你长大" : "本机生成的伙伴";
    copy.append(name, detail);
    const actions = document.createElement("div");
    const adopt = document.createElement("button");
    adopt.type = "button";
    adopt.dataset.customPetSelect = pet.id;
    adopt.textContent = pet.id === selectedSkin ? "已领养" : "领养";
    adopt.disabled = pet.id === selectedSkin;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "danger";
    remove.dataset.customPetDelete = pet.custom_id;
    remove.textContent = "删除";
    actions.append(adopt, remove);
    card.append(image, copy, actions);
    list.append(card);
  });
}

function renderDatabase(database, roasts) {
  $("#app-count").textContent = database.application_count || 0;
  $("#relation-count").textContent = database.relation_count || 0;
  $("#learned-count").textContent = database.learned_count || 0;
  $("#roast-count").textContent = roasts.line_count || 0;
  $("#roast-category-count").textContent = roasts.category_count || 0;
}

function renderBrowserBridge(bridge) {
  const card = $("#browser-bridge-card");
  const connected = Boolean(bridge.connected);
  card.dataset.connected = connected ? "true" : "false";
  card.dataset.extensionPath = bridge.extension_path || "browser_extension";
  $("#browser-bridge-title").textContent = connected ? "具体网址识别已连接" : "扩展正在等待上报";
  $("#browser-bridge-copy").textContent = connected
    ? `${bridge.browser || "浏览器"} 正在识别 ${bridge.current_domain || "当前域名"}，域名只留在内存里。`
    : "本轮仍可正常开始；暂时没有收到域名时不会扣分。打开或刷新任意普通网页后，Focus 扩展会自动恢复连接。";
}

function formatAudioTime(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "00:00";
  const minutes = Math.floor(seconds / 60);
  return `${String(minutes).padStart(2, "0")}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
}

function categoryMeta(categoryId) {
  return soundLibrary.categories.find((item) => item.id === categoryId)
    || { id: "ambient", label: "漫游", icon: "∞", description: "自然氛围" };
}

function soundSceneFor(categoryId) {
  return ({ rain: "scared", water: "relax", ocean: "relax", birds: "confused", sunny: "focus", ambient: "relax" })[categoryId] || "relax";
}

function currentSoundTrack() {
  return soundLibrary.tracks[currentSoundIndex] || null;
}

function isSyntheticTrack(track = currentSoundTrack()) {
  return track?.source === "synth";
}

function createNoiseBuffer(context) {
  const length = context.sampleRate * 4;
  const buffer = context.createBuffer(1, length, context.sampleRate);
  const data = buffer.getChannelData(0);
  for (let index = 0; index < length; index += 1) data[index] = Math.random() * 2 - 1;
  return buffer;
}

function stopSyntheticSound({ reset = false } = {}) {
  if (synthPlaying) {
    synthElapsedSeconds += (performance.now() - synthStartedAt) / 1000;
  }
  synthNodes.forEach((node) => {
    try { node.stop?.(); } catch {}
    try { node.disconnect?.(); } catch {}
  });
  synthNodes = [];
  synthGain = null;
  synthPlaying = false;
  if (reset) synthElapsedSeconds = 0;
}

async function playSyntheticSound(track) {
  stopSyntheticSound();
  const AudioEngine = window.AudioContext || window.webkitAudioContext;
  if (!AudioEngine) throw new Error("当前系统不支持合成环境声");
  synthAudioContext ||= new AudioEngine();
  await synthAudioContext.resume();
  const source = synthAudioContext.createBufferSource();
  source.buffer = createNoiseBuffer(synthAudioContext);
  source.loop = true;
  const filter = synthAudioContext.createBiquadFilter();
  const gain = synthAudioContext.createGain();
  const settings = {
    rain: { kind: "highpass", frequency: 900, gain: 0.29 },
    water: { kind: "bandpass", frequency: 1450, gain: 0.24 },
    ocean: { kind: "lowpass", frequency: 540, gain: 0.37 },
    birds: { kind: "bandpass", frequency: 2100, gain: 0.16 },
  }[track.category] || { kind: "lowpass", frequency: 480, gain: 0.32 };
  filter.type = settings.kind;
  filter.frequency.value = settings.frequency;
  gain.gain.value = settings.gain * Number($("#sound-volume").value || 38) / 100;
  source.connect(filter).connect(gain).connect(synthAudioContext.destination);
  source.start();
  synthNodes = [source, filter, gain];
  synthGain = gain;
  synthPlaying = true;
  synthStartedAt = performance.now();
}

function syncSoundPlayingState() {
  const playing = isSyntheticTrack()
    ? synthPlaying
    : !ambientAudio.paused && !ambientAudio.ended && Boolean(ambientAudio.src);
  $("#sound-player").dataset.playing = playing ? "true" : "false";
  $(".sound-visual").dataset.playing = playing ? "true" : "false";
  $("#sound-quick-toggle").dataset.playing = playing ? "true" : "false";
  $("#sound-play").textContent = playing ? "Ⅱ" : "▶";
  $("#sound-play").setAttribute("aria-label", playing ? "暂停" : "播放");
  const current = soundLibrary.tracks[currentSoundIndex];
  $("#sound-quick-label").textContent = current ? (playing ? current.title : `已选 · ${current.title}`) : "白噪音";
  $$(".sound-track").forEach((button) => {
    button.classList.toggle("playing", playing && button.dataset.trackId === current?.id);
  });
}

function renderSoundCategories() {
  const list = $("#sound-category-list");
  list.replaceChildren();
  const all = [{
    id: "all", label: "全部声音", icon: "⌘",
    description: "浏览本地声音库", count: soundLibrary.tracks.length,
  }, ...soundLibrary.categories];
  all.forEach((category) => {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.soundCategory = category.id;
    button.classList.toggle("active", category.id === activeSoundCategory);
    const icon = document.createElement("i");
    icon.textContent = category.icon;
    const copy = document.createElement("span");
    const title = document.createElement("b");
    title.textContent = category.label;
    const description = document.createElement("small");
    description.textContent = category.description;
    copy.append(title, description);
    const count = document.createElement("em");
    count.textContent = category.count;
    button.append(icon, copy, count);
    button.addEventListener("click", () => {
      activeSoundCategory = category.id;
      renderSoundCategories();
      renderSoundTracks();
    });
    list.append(button);
  });
}

function renderSoundTracks() {
  const list = $("#sound-track-list");
  list.replaceChildren();
  const tracks = soundLibrary.tracks.filter((track) => activeSoundCategory === "all" || track.category === activeSoundCategory);
  $("#sound-result-count").textContent = `${tracks.length} TRACKS`;
  $("#sound-library-title").textContent = activeSoundCategory === "all" ? "全部声音" : categoryMeta(activeSoundCategory).label;
  tracks.forEach((track) => {
    const meta = categoryMeta(track.category);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "sound-track";
    button.dataset.trackId = track.id;
    button.classList.toggle("selected", soundLibrary.tracks[currentSoundIndex]?.id === track.id);
    const art = document.createElement("span");
    art.className = `track-art category-${track.category}`;
    art.textContent = meta.icon;
    const copy = document.createElement("span");
    copy.className = "track-copy";
    const title = document.createElement("b");
    title.textContent = track.title;
    const detail = document.createElement("small");
    detail.textContent = `${track.artist} · ${meta.label}`;
    copy.append(title, detail);
    const action = document.createElement("span");
    action.className = "track-action";
    action.textContent = "▶";
    button.append(art, copy, action);
    button.addEventListener("click", () => selectSoundTrack(track.id, true));
    list.append(button);
  });
  syncSoundPlayingState();
}

async function selectSoundTrack(trackId, playNow = false) {
  const index = soundLibrary.tracks.findIndex((track) => track.id === trackId);
  if (index < 0) return;
  currentSoundIndex = index;
  const track = soundLibrary.tracks[index];
  ambientAudio.pause();
  stopSyntheticSound({ reset: true });
  if (isSyntheticTrack(track)) {
    ambientAudio.removeAttribute("src");
    ambientAudio.dataset.trackId = track.id;
    ambientAudio.load();
    $("#sound-current-time").textContent = "00:00";
    $("#sound-duration").textContent = "∞";
    $("#sound-progress").value = "0";
    $("#sound-progress").disabled = true;
  } else if (ambientAudio.dataset.trackId !== track.id) {
    ambientAudio.dataset.trackId = track.id;
    ambientAudio.src = track.url;
    ambientAudio.load();
    $("#sound-progress").disabled = false;
  }
  localStorage.setItem("focus-sound-track", track.id);
  $("#player-track-title").textContent = track.title;
  $("#player-track-artist").textContent = `${track.artist} · ${categoryMeta(track.category).label}`;
  const coverScene = STORY_SCENES[soundSceneFor(track.category)] || STORY_SCENES.idle;
  $("#player-cover-image").src = coverScene.image;
  renderSoundTracks();
  if (playNow) {
    try {
      if (isSyntheticTrack(track)) await playSyntheticSound(track);
      else await ambientAudio.play();
      syncSoundPlayingState();
    } catch {
      showToast("系统暂时阻止播放，请再点一次播放键", true);
    }
  }
}

async function toggleSound() {
  if (currentSoundIndex < 0) {
    switchView("ambience");
    showToast("先在声音花园选一种环境");
    return;
  }
  const track = currentSoundTrack();
  if (isSyntheticTrack(track)) {
    if (synthPlaying) stopSyntheticSound();
    else {
      try { await playSyntheticSound(track); }
      catch { showToast("系统暂时阻止播放，请在声音花园中点击曲目", true); }
    }
    syncSoundPlayingState();
  } else if (ambientAudio.paused) {
    try { await ambientAudio.play(); }
    catch { showToast("系统暂时阻止播放，请在声音花园中点击曲目", true); }
  } else {
    ambientAudio.pause();
  }
}

function stepSound(direction) {
  if (!soundLibrary.tracks.length) return;
  const next = currentSoundIndex < 0
    ? 0
    : (currentSoundIndex + direction + soundLibrary.tracks.length) % soundLibrary.tracks.length;
  selectSoundTrack(soundLibrary.tracks[next].id, true);
}

async function loadSoundLibrary() {
  try {
    soundLibrary = await api("/api/media/library");
    renderSoundCategories();
    const saved = localStorage.getItem("focus-sound-track");
    const initial = soundLibrary.tracks.find((track) => track.id === saved);
    if (initial) await selectSoundTrack(initial.id, false);
    else renderSoundTracks();
  } catch (error) {
    showToast(error.message, true);
  }
}

function switchView(name) {
  $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === name));
  $$(".view").forEach((view) => view.classList.toggle("active", view.id === `${name}-view`));
}

async function refreshState() {
  try {
    const state = await api("/api/state");
    $("#service-copy").textContent = "本地监测已连接";
    renderState(state);
  } catch {
    $("#service-copy").textContent = "正在重连本地服务";
  }
}

function renderCloudAISettings(settings) {
  if (!settings) return;
  cloudAISettings = settings;
  $("#text-provider").value = settings.text_provider || "local";
  $("#pet-renderer-setting").value = settings.pet_renderer || "local";
  $("#custom-pet-renderer").value = settings.pet_renderer || "local";
  const account = settings.focus_account || {};
  const cloudAvailable = Boolean(settings.focus_cloud_available);
  for (const select of [$("#text-provider"), $("#pet-renderer-setting"), $("#custom-pet-renderer")]) {
    const option = select.querySelector('option[value="focus_cloud"]');
    if (option) option.disabled = !cloudAvailable;
    if (!cloudAvailable && select.value === "focus_cloud") select.value = "local";
  }
  $("#focus-account-status").textContent = account.signed_in
    ? account.mode === "cloud"
      ? `已登录 ${account.username} · Focus免费AI已连接，无需API Key`
      : `已登录 ${account.username} · 本机账户会在这台电脑上保持登录`
    : settings.focus_cloud_available
      ? "尚未登录。注册和登录均不会要求服务商密钥。"
      : "可创建仅保存在这台电脑的本机资料；这不会开通云端能力或在线模型额度。";
  $("#focus-account-name").value = account.signed_in ? account.username : "";
  $("#focus-account-name").disabled = Boolean(account.signed_in);
  $("#focus-account-password").hidden = Boolean(account.signed_in);
  $("#focus-account-register").hidden = Boolean(account.signed_in);
  $("#focus-account-login").hidden = Boolean(account.signed_in);
  $("#focus-account-logout").hidden = !account.signed_in;
  $("#openrouter-key-status").textContent = settings.openrouter_configured
    ? `已安全保存 · ${settings.openrouter_model}`
    : "未配置。免费路由仍需申请个人 Key，并受服务商限额约束。";
  $("#gemini-key-status").textContent = settings.gemini_configured
    ? `已安全保存 · ${settings.gemini_image_model} · 图片生成可能计费`
    : "云端图片生成可能产生服务商费用，上传前会再次征得同意。";
  $("#ai-settings-button").textContent = account.signed_in
    ? `${account.username} · ${account.mode === "cloud" ? "免费AI" : "本机账户"}`
    : "AI 与本机资料";
  updatePetRendererConsent();
}

async function loadCloudAISettings() {
  try {
    renderCloudAISettings(await api("/api/ai/settings"));
  } catch (error) {
    showToast(`AI连接设置读取失败：${error.message}`, true);
  }
}

function updatePetRendererConsent() {
  const cloud = ["focus_cloud", "gemini"].includes($("#custom-pet-renderer").value);
  $("#pet-cloud-consent-row").hidden = !cloud;
  if (!cloud) $("#pet-cloud-consent").checked = false;
}

planButton.addEventListener("click", planGoal);
startButton.addEventListener("click", startSession);
const currentUIVersion = "4.2.1";
const savedAIPlanning = localStorage.getItem("focus-ai-planning");
if (localStorage.getItem("focus-ui-version") !== currentUIVersion) {
  aiPlanToggle.checked = false;
  localStorage.setItem("focus-ai-planning", "false");
  localStorage.setItem("focus-ui-version", currentUIVersion);
} else if (savedAIPlanning !== null) {
  aiPlanToggle.checked = savedAIPlanning !== "false";
}
planButton.querySelectorAll("span")[1].textContent = aiPlanToggle.checked
  ? "AI解析任务场景"
  : "解析任务场景";
aiPlanToggle.addEventListener("change", () => {
  localStorage.setItem("focus-ai-planning", String(aiPlanToggle.checked));
  currentPlan = null;
  planButton.querySelectorAll("span")[1].textContent = aiPlanToggle.checked
    ? "AI解析任务场景"
    : "解析任务场景";
  $("#plan-source").textContent = aiPlanToggle.checked ? "等待AI解析" : "等待本地解析";
});

$("#ai-settings-button").addEventListener("click", () => $("#ai-settings-dialog").showModal());
$("#ai-settings-close").addEventListener("click", () => $("#ai-settings-dialog").close());
$("#ai-settings-cancel").addEventListener("click", () => $("#ai-settings-dialog").close());
$("#ai-settings-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const save = $("#ai-settings-save");
  save.disabled = true;
  save.textContent = "正在保存…";
  try {
    const settings = await api("/api/ai/settings", {
      text_provider: $("#text-provider").value,
      openrouter_api_key: $("#openrouter-key").value.trim(),
      pet_renderer: $("#pet-renderer-setting").value,
      gemini_api_key: $("#gemini-key").value.trim(),
    });
    $("#openrouter-key").value = "";
    $("#gemini-key").value = "";
    renderCloudAISettings(settings);
    aiPlanToggle.checked = settings.text_provider !== "local";
    localStorage.setItem("focus-ai-planning", String(aiPlanToggle.checked));
    currentPlan = null;
    $("#ai-settings-dialog").close();
    showToast(settings.text_provider === "focus_cloud" ? "Focus Cloud任务解析已连接" : "AI设置已保存");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    save.disabled = false;
    save.textContent = "保存连接";
  }
});

async function submitFocusAccount(action) {
  const username = $("#focus-account-name").value.trim();
  const password = $("#focus-account-password").value;
  if (!username || password.length < 8) {
    showToast("请输入用户名和至少8位密码", true);
    return;
  }
  const buttons = [$("#focus-account-register"), $("#focus-account-login")];
  buttons.forEach((button) => { button.disabled = true; });
  try {
    const settings = await api(`/api/account/${action}`, { username, password });
    $("#focus-account-password").value = "";
    renderCloudAISettings(settings);
    const cloudAccount = settings.focus_account?.mode === "cloud";
    $("#text-provider").value = cloudAccount ? "focus_cloud" : "local";
    if (cloudAccount) {
      $("#pet-renderer-setting").value = "focus_cloud";
      $("#custom-pet-renderer").value = "focus_cloud";
    }
    aiPlanToggle.checked = cloudAccount;
    localStorage.setItem("focus-ai-planning", String(cloudAccount));
    showToast(
      cloudAccount
        ? action === "register" ? "云端账户已创建，免费AI已连接" : "云端账户已登录，免费AI已连接"
        : action === "register" ? "本机账户已创建并保持登录" : "本机账户已登录并保存"
    );
  } catch (error) {
    showToast(error.message, true);
  } finally {
    buttons.forEach((button) => { button.disabled = false; });
  }
}

$("#focus-account-register").addEventListener("click", () => submitFocusAccount("register"));
$("#focus-account-login").addEventListener("click", () => submitFocusAccount("login"));
$("#focus-account-logout").addEventListener("click", async () => {
  try {
    renderCloudAISettings(await api("/api/account/logout", {}));
    aiPlanToggle.checked = false;
    localStorage.setItem("focus-ai-planning", "false");
    showToast("已退出Focus账户，本地功能不受影响");
  } catch (error) {
    showToast(error.message, true);
  }
});
$("#pet-renderer-setting").addEventListener("change", () => {
  $("#custom-pet-renderer").value = $("#pet-renderer-setting").value;
  updatePetRendererConsent();
});
$("#custom-pet-renderer").addEventListener("change", updatePetRendererConsent);

$("#preview-cat-button").addEventListener("click", async () => {
  try {
    const result = await api("/api/preview/alert", {});
    const name = result.cat_name || currentState?.profile?.pet?.name || "Luna";
    showToast(result.mood === "judging" ? `${name}这次会认真盯你` : `${name}正在从屏幕边缘赶来`);
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#pet-name-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = $("#pet-name-input").value.trim();
  try {
    const profile = await api("/api/pet/name", { name });
    if (currentState) currentState.profile = profile;
    renderProfile(profile);
    showToast(`好，以后它就叫${profile.pet?.name || name}`);
  } catch (error) {
    showToast(error.message, true);
  }
});

async function selectPetSkin(skin) {
  try {
    const profile = await api("/api/pet/skin", { skin });
    if (currentState) currentState.profile = profile;
    profileSignature = "";
    renderProfile(profile);
    showToast(`${profile.pet?.name || "小猫"}换好新外观了`);
  } catch (error) {
    showToast(error.message, true);
  }
}

$$('[data-cat-skin]').forEach((button) => button.addEventListener("click", () => {
  if (!button.classList.contains("selected")) selectPetSkin(button.dataset.catSkin);
}));

let customPetImage = "";
$("#custom-pet-file").addEventListener("change", () => {
  const file = $("#custom-pet-file").files?.[0];
  if (!file) return;
  if (file.size > 6 * 1024 * 1024) {
    showToast("照片需小于6MB", true);
    $("#custom-pet-file").value = "";
    return;
  }
  const reader = new FileReader();
  reader.addEventListener("load", () => {
    customPetImage = String(reader.result || "");
    $("#custom-pet-preview").src = customPetImage;
    $("#custom-pet-preview").hidden = false;
    $("#custom-pet-drop-copy").hidden = true;
  });
  reader.readAsDataURL(file);
});

$("#custom-pet-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = $("#custom-pet-name").value.trim();
  if (!customPetImage) {
    showToast("先选择一张宠物照片", true);
    return;
  }
  const button = $("#custom-pet-create");
  const renderer = $("#custom-pet-renderer").value;
  const consent = Boolean($("#pet-cloud-consent").checked);
  if (["focus_cloud", "gemini"].includes(renderer) && !consent) {
    showToast("使用AI卡通化前，请先确认本次照片可以发送给所选云端模型", true);
    return;
  }
  button.disabled = true;
  button.textContent = renderer === "local" ? "正在本机生成…" : "AI正在画它…";
  try {
    const profile = await api("/api/pet/custom/create", {
      name,
      image: customPetImage,
      renderer,
      consent,
    });
    if (currentState) currentState.profile = profile;
    profileSignature = "";
    renderProfile(profile);
    customPetImage = "";
    $("#custom-pet-form").reset();
    $("#custom-pet-preview").hidden = true;
    $("#custom-pet-drop-copy").hidden = false;
    updatePetRendererConsent();
    showToast(`${profile.pet?.name || name}已经搬进成长房间`);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "生成并领养";
  }
});

$("#custom-pet-list").addEventListener("click", async (event) => {
  const select = event.target.closest("[data-custom-pet-select]");
  if (select) {
    await selectPetSkin(select.dataset.customPetSelect);
    return;
  }
  const remove = event.target.closest("[data-custom-pet-delete]");
  if (!remove) return;
  if (!window.confirm("删除后本机生成的成长图片也会一起移除，确定吗？")) return;
  try {
    const profile = await api("/api/pet/custom/delete", { id: remove.dataset.customPetDelete });
    if (currentState) currentState.profile = profile;
    profileSignature = "";
    renderProfile(profile);
    showToast("已经从本机猫窝移除");
  } catch (error) {
    showToast(error.message, true);
  }
});

$$('[data-cat-action]').forEach((button) => button.addEventListener("click", async () => {
  const kind = button.dataset.catAction;
  const room = $("#pet-room");
  const actionKey = kind === "shy" ? "happy" : kind;
  const actionAsset = currentPetActionAssets[actionKey];
  clearTimeout(reactionTimer);
  room.dataset.reaction = "";
  requestAnimationFrame(() => {
    room.dataset.reaction = kind;
    if (actionAsset) {
      $(".nurture-kitten").style.backgroundImage = `url('${actionAsset}')`;
      $(".nurture-head").style.backgroundImage = `url('${actionAsset}')`;
    }
    reactionTimer = setTimeout(() => {
      room.dataset.reaction = "";
      if (currentPetGrowthAsset) {
        $(".nurture-kitten").style.backgroundImage = `url('${currentPetGrowthAsset}')`;
        $(".nurture-head").style.backgroundImage = `url('${currentPetGrowthAsset}')`;
      }
    }, 2700);
  });
  try {
    const result = await api("/api/preview/reaction", { kind });
    showToast(`${result.cat_name || "小猫"}正在表演`);
  } catch (error) {
    showToast(error.message, true);
  }
}));

$$('[data-goal]').forEach((button) => button.addEventListener("click", () => {
  goalInput.value = button.dataset.goal;
  currentPlan = null;
  planGoal();
}));

goalInput.addEventListener("input", () => {
  if (currentPlan && currentPlan.goal !== goalInput.value.trim()) {
    $("#plan-source").textContent = "目标已修改 · 请重新解析";
  }
});

$$('#mode-control button').forEach((button) => button.addEventListener("click", () => {
  setSegment("#mode-control", "mode", button.dataset.mode);
  $(".plan-panel").classList.toggle("blackout", button.dataset.mode === "blackout");
}));

$$('#duration-control button').forEach((button) => button.addEventListener("click", () => {
  setSegment("#duration-control", "minutes", button.dataset.minutes);
  $("#custom-duration").value = button.dataset.minutes;
  if (!currentState || !["running", "paused"].includes(currentState.state)) {
    $("#timer-text").textContent = `${String(button.dataset.minutes).padStart(2, "0")}:00`;
  }
}));

$("#custom-duration").addEventListener("input", () => {
  $$("#duration-control button").forEach((button) => button.classList.remove("active"));
});

$$('#intensity-control button').forEach((button) => button.addEventListener("click", () => {
  setSegment("#intensity-control", "intensity", button.dataset.intensity);
}));

$("#add-target-button").addEventListener("click", () => {
  let value = $("#custom-target-value").value.trim();
  if (!value) return showToast("先写软件名、页面关键词或网址", true);
  if (!currentPlan) return showToast("先解析一次目标，再补充工具", true);
  let kind = $("#custom-target-kind").value;
  if (looksLikeWebAddress(value)) {
    kind = "domain";
    $("#custom-target-kind").value = "domain";
  }
  if (kind === "domain") {
    try {
      value = new URL(value.includes("://") ? value : `https://${value}`).hostname.replace(/^www\./i, "").toLowerCase();
      if (!value.includes(".")) throw new Error();
    } catch {
      return showToast("请填写网址或域名，例如：bilibili.com", true);
    }
    if (!currentState?.browser_bridge?.connected) {
      showToast("域名已加入；开始前请先连接网址桥接", true);
    }
  }
  const target = {
    kind,
    value,
    match: kind === "window_title" ? "contains" : kind === "domain" ? "domain_suffix" : "exact",
  };
  let scene = currentPlan.scenes.find((item) => item.name === "手动补充");
  if (!scene) {
    scene = { name: "手动补充", description: "由你确认的任务工具", targets: [] };
    currentPlan.scenes.push(scene);
  }
  const duplicate = currentPlan.scenes.some((item) => item.targets.some((existing) => JSON.stringify(existing) === JSON.stringify(target)));
  if (!duplicate) scene.targets.push(target);
  $("#custom-target-value").value = "";
  renderScenes();
  showToast(kind === "domain" ? `已按网址识别：${value}` : "已加入本轮工具草案");
});

$("#custom-target-kind").addEventListener("change", (event) => {
  const input = $("#custom-target-value");
  input.placeholder = event.target.value === "domain"
    ? "粘贴网址，例如：https://www.bilibili.com/video"
    : "补充软件或页面，例如：Notion / Code.exe";
});

$("#copy-extension-path").addEventListener("click", async () => {
  const path = $("#browser-bridge-card").dataset.extensionPath;
  try {
    await navigator.clipboard.writeText(path);
    showToast("安装位置已复制：去扩展页选择“加载解压缩的扩展”");
  } catch {
    showToast(path);
  }
});

$("#pause-button").addEventListener("click", async () => {
  try {
    const path = currentState?.state === "paused" ? "/api/session/resume" : "/api/session/pause";
    renderState(await api(path, {}));
  } catch (error) { showToast(error.message, true); }
});

$("#stop-button").addEventListener("click", async () => {
  if (!confirm("结束这一轮？提前结束不会结算XP，但已投入的时间会保留在记录里。")) return;
  try { renderState(await api("/api/session/stop", {})); }
  catch (error) { showToast(error.message, true); }
});

$$('.nav-item').forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));

$("#sound-quick-toggle").addEventListener("click", toggleSound);
$("#sound-play").addEventListener("click", toggleSound);
$("#sound-prev").addEventListener("click", () => stepSound(-1));
$("#sound-next").addEventListener("click", () => stepSound(1));

const savedVolume = Math.max(0, Math.min(1, Number(localStorage.getItem("focus-sound-volume") || .38)));
ambientAudio.volume = savedVolume;
$("#sound-volume").value = String(Math.round(savedVolume * 100));
$("#sound-volume").addEventListener("input", (event) => {
  ambientAudio.volume = Number(event.target.value) / 100;
  if (synthGain) {
    const track = currentSoundTrack();
    const maxGain = ({ rain: .29, water: .24, ocean: .37, birds: .16 })[track?.category] || .32;
    synthGain.gain.value = maxGain * Number(event.target.value) / 100;
  }
  localStorage.setItem("focus-sound-volume", String(ambientAudio.volume));
});

$("#sound-progress").addEventListener("input", (event) => {
  if (Number.isFinite(ambientAudio.duration) && ambientAudio.duration > 0) {
    ambientAudio.currentTime = (Number(event.target.value) / 1000) * ambientAudio.duration;
  }
});

ambientAudio.addEventListener("loadedmetadata", () => {
  $("#sound-duration").textContent = formatAudioTime(ambientAudio.duration);
});
ambientAudio.addEventListener("timeupdate", () => {
  $("#sound-current-time").textContent = formatAudioTime(ambientAudio.currentTime);
  const progress = Number.isFinite(ambientAudio.duration) && ambientAudio.duration > 0
    ? Math.round((ambientAudio.currentTime / ambientAudio.duration) * 1000)
    : 0;
  $("#sound-progress").value = String(progress);
});
ambientAudio.addEventListener("play", syncSoundPlayingState);
ambientAudio.addEventListener("pause", syncSoundPlayingState);
ambientAudio.addEventListener("error", () => {
  if (isSyntheticTrack()) return;
  syncSoundPlayingState();
  showToast("这段声音没有成功加载，请换一首或检查文件", true);
});

$("#motion-toggle").addEventListener("click", () => {
  document.body.classList.toggle("reduce-motion");
  localStorage.setItem("focus-reduce-motion", document.body.classList.contains("reduce-motion") ? "1" : "0");
  showToast(document.body.classList.contains("reduce-motion") ? "已减少非必要动效" : "已恢复轻量动效");
});

if (localStorage.getItem("focus-reduce-motion") === "1") document.body.classList.add("reduce-motion");
refreshState();
loadSoundLibrary();
loadCloudAISettings();
setInterval(refreshState, 800);
setInterval(() => {
  if (!synthPlaying) return;
  const elapsed = synthElapsedSeconds + (performance.now() - synthStartedAt) / 1000;
  $("#sound-current-time").textContent = formatAudioTime(elapsed);
}, 1000);
