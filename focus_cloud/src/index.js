const encoder = new TextEncoder();
const SESSION_TTL_SECONDS = 30 * 24 * 60 * 60;
const PASSWORD_ITERATIONS = 120000;

function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-content-type-options": "nosniff",
      ...headers,
    },
  });
}

function bytesToBase64(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function base64ToBytes(value) {
  const binary = atob(value);
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

function randomToken(size = 32) {
  const bytes = new Uint8Array(size);
  crypto.getRandomValues(bytes);
  return bytesToBase64(bytes).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

async function sha256(value) {
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(value));
  return bytesToBase64(new Uint8Array(digest));
}

async function hashPassword(password, salt) {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(password),
    "PBKDF2",
    false,
    ["deriveBits"]
  );
  const bits = await crypto.subtle.deriveBits(
    {
      name: "PBKDF2",
      hash: "SHA-256",
      salt: base64ToBytes(salt),
      iterations: PASSWORD_ITERATIONS,
    },
    key,
    256
  );
  return bytesToBase64(new Uint8Array(bits));
}

function constantTimeEqual(left, right) {
  if (left.length !== right.length) return false;
  let mismatch = 0;
  for (let index = 0; index < left.length; index += 1) {
    mismatch |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return mismatch === 0;
}

function allowedOrigin(request, env) {
  const origin = request.headers.get("origin") || "";
  if (!origin) return "";
  const prefixes = String(env.ALLOWED_ORIGINS || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  return prefixes.some((prefix) => {
    if (prefix.endsWith("://")) return origin.startsWith(prefix);
    return origin === prefix || origin.startsWith(`${prefix}:`);
  })
    ? origin
    : "";
}

function corsHeaders(request, env) {
  const origin = allowedOrigin(request, env);
  return origin
    ? {
        "access-control-allow-origin": origin,
        "access-control-allow-methods": "GET,POST,OPTIONS",
        "access-control-allow-headers": "authorization,content-type",
        "access-control-max-age": "600",
        vary: "Origin",
      }
    : {};
}

async function bodyJson(request, maxBytes = 100000) {
  const length = Number(request.headers.get("content-length") || 0);
  if (length > maxBytes) throw new Error("请求内容过大");
  const payload = await request.json();
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("请求格式不正确");
  }
  return payload;
}

function normalizeUsername(value) {
  const username = String(value || "").trim().toLowerCase();
  if (!/^[a-z0-9_\-\u4e00-\u9fff]{3,24}$/u.test(username)) {
    throw new Error("用户名需为3—24位中文、字母、数字、下划线或短横线");
  }
  return username;
}

function validatePassword(value) {
  const password = String(value || "");
  if (password.length < 8 || password.length > 72) {
    throw new Error("密码需为8—72个字符");
  }
  return password;
}

async function issueSession(env, user) {
  const token = randomToken();
  const now = Math.floor(Date.now() / 1000);
  const expiresAt = now + SESSION_TTL_SECONDS;
  await env.DB.prepare(
    "INSERT INTO sessions(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)"
  )
    .bind(await sha256(token), user.id, expiresAt, now)
    .run();
  return { token, expires_at: expiresAt, username: user.username };
}

async function currentUser(request, env) {
  const header = request.headers.get("authorization") || "";
  const token = header.startsWith("Bearer ") ? header.slice(7).trim() : "";
  if (!token) return null;
  const now = Math.floor(Date.now() / 1000);
  return env.DB.prepare(
    `SELECT users.id, users.username, sessions.token_hash, sessions.expires_at
       FROM sessions JOIN users ON users.id = sessions.user_id
      WHERE sessions.token_hash = ? AND sessions.expires_at > ?`
  )
    .bind(await sha256(token), now)
    .first();
}

async function requireUser(request, env) {
  const user = await currentUser(request, env);
  if (!user) throw new Response("登录已过期，请重新登录", { status: 401 });
  return user;
}

async function useQuota(env, userId, field) {
  const day = new Date().toISOString().slice(0, 10);
  await env.DB.prepare(
    "INSERT OR IGNORE INTO daily_usage(user_id,usage_day,chat_count,pet_count) VALUES(?,?,0,0)"
  )
    .bind(userId, day)
    .run();
  const limit = Number(
    field === "chat_count" ? env.DAILY_CHAT_LIMIT || 30 : env.DAILY_PET_LIMIT || 2
  );
  const result = await env.DB.prepare(
    `UPDATE daily_usage
       SET ${field}=${field}+1
     WHERE user_id=? AND usage_day=? AND ${field}<?`
  )
    .bind(userId, day, limit)
    .run();
  if (Number(result.meta?.changes || 0) !== 1) {
    throw new Response("今天的免费AI额度已用完，明天会自动恢复", { status: 429 });
  }
  return { day, field };
}

async function refundQuota(env, userId, reservation) {
  await env.DB.prepare(
    `UPDATE daily_usage
       SET ${reservation.field}=MAX(0,${reservation.field}-1)
     WHERE user_id=? AND usage_day=?`
  )
    .bind(userId, reservation.day)
    .run();
}

async function register(request, env) {
  const payload = await bodyJson(request);
  const username = normalizeUsername(payload.username);
  const password = validatePassword(payload.password);
  const existing = await env.DB.prepare("SELECT id FROM users WHERE username=?")
    .bind(username)
    .first();
  if (existing) return json({ ok: false, error: "这个用户名已经被使用" }, 409);
  const saltBytes = new Uint8Array(16);
  crypto.getRandomValues(saltBytes);
  const salt = bytesToBase64(saltBytes);
  const user = { id: crypto.randomUUID(), username };
  await env.DB.prepare(
    "INSERT INTO users(id,username,password_hash,password_salt,created_at) VALUES(?,?,?,?,?)"
  )
    .bind(user.id, username, await hashPassword(password, salt), salt, Date.now())
    .run();
  return json({ ok: true, data: await issueSession(env, user) }, 201);
}

async function login(request, env) {
  const payload = await bodyJson(request);
  const username = normalizeUsername(payload.username);
  const password = validatePassword(payload.password);
  const user = await env.DB.prepare(
    "SELECT id,username,password_hash,password_salt FROM users WHERE username=?"
  )
    .bind(username)
    .first();
  const candidate = user
    ? await hashPassword(password, user.password_salt)
    : await hashPassword(password, bytesToBase64(new Uint8Array(16)));
  if (!user || !constantTimeEqual(candidate, user.password_hash)) {
    return json({ ok: false, error: "用户名或密码不正确" }, 401);
  }
  return json({ ok: true, data: await issueSession(env, user) });
}

async function logout(request, env) {
  const user = await requireUser(request, env);
  await env.DB.prepare("DELETE FROM sessions WHERE token_hash=?").bind(user.token_hash).run();
  return json({ ok: true, data: { logged_out: true } });
}

function cleanMessages(payload) {
  if (!Array.isArray(payload.messages) || !payload.messages.length) {
    throw new Error("缺少模型消息");
  }
  const messages = payload.messages.slice(-10).map((item) => ({
    role: ["system", "user", "assistant"].includes(item?.role) ? item.role : "user",
    content: String(item?.content || "").slice(0, 6000),
  }));
  if (messages.reduce((sum, item) => sum + item.content.length, 0) > 18000) {
    throw new Error("模型上下文过长");
  }
  return messages;
}

async function chat(request, env) {
  const user = await requireUser(request, env);
  const payload = await bodyJson(request, 30000);
  const messages = cleanMessages(payload);
  const quota = await useQuota(env, user.id, "chat_count");
  let text;
  try {
    const result = await env.AI.run(
      env.TEXT_MODEL || "@cf/meta/llama-3.1-8b-instruct-fp8-fast",
      {
        messages,
        max_tokens: 900,
        temperature: 0.1,
      }
    );
    text = String(result?.response || result?.result?.response || "").trim();
    if (!text) throw new Error("免费模型没有返回可用内容");
  } catch (error) {
    await refundQuota(env, user.id, quota);
    throw error;
  }
  return json({
    ok: true,
    data: {
      text,
      model: env.TEXT_MODEL || "@cf/meta/llama-3.1-8b-instruct-fp8-fast",
    },
  });
}

async function plan(request, env) {
  const user = await requireUser(request, env);
  const payload = await bodyJson(request, 12000);
  const goal = String(payload.goal || "").trim().slice(0, 300);
  if (!goal) throw new Error("请先填写目标");
  const quota = await useQuota(env, user.id, "chat_count");
  let result;
  try {
    result = await env.AI.run(
      env.TEXT_MODEL || "@cf/meta/llama-3.1-8b-instruct-fp8-fast",
      {
      messages: [
        {
          role: "system",
          content:
            "你是Focus任务规划器。只输出合法JSON，不要Markdown。字段：duration_minutes整数；scene不超过12字；tools为2到5个短字符串；domains为0到6个纯域名。只推荐完成目标真正需要的工具和网站，不要推荐娱乐网站。",
        },
        { role: "user", content: goal },
      ],
      max_tokens: 420,
      temperature: 0.1,
      }
    );
  } catch (error) {
    await refundQuota(env, user.id, quota);
    throw error;
  }
  const raw = String(result?.response || "").trim().replace(/^```json\s*|\s*```$/g, "");
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    await refundQuota(env, user.id, quota);
    throw new Error("模型规划格式不稳定，请重试；本地推荐仍可继续使用");
  }
  return json({
    ok: true,
    data: {
      duration_minutes: Math.max(1, Math.min(240, Number(parsed.duration_minutes) || 25)),
      scene: String(parsed.scene || "专注任务").slice(0, 20),
      tools: Array.isArray(parsed.tools)
        ? parsed.tools.map((item) => String(item).slice(0, 30)).filter(Boolean).slice(0, 5)
        : [],
      domains: Array.isArray(parsed.domains)
        ? parsed.domains
            .map((item) => String(item).toLowerCase().replace(/^https?:\/\//, "").split("/")[0])
            .filter((item) => /^[a-z0-9.-]+\.[a-z]{2,}$/i.test(item))
            .slice(0, 6)
        : [],
      model: env.TEXT_MODEL || "@cf/meta/llama-3.1-8b-instruct-fp8-fast",
    },
  });
}

async function pet(request, env) {
  const user = await requireUser(request, env);
  const payload = await bodyJson(request, 8 * 1024 * 1024);
  const sourceImage = String(payload.image || "");
  if (sourceImage.length > 8 * 1024 * 1024) throw new Error("宠物照片过大");
  const match = sourceImage.match(
    /^data:image\/(?:png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=\r\n]+)$/i
  );
  if (!match) throw new Error("请选择PNG、JPG或WebP宠物照片");
  const quota = await useQuota(env, user.id, "pet_count");
  const prompt =
    "Turn the same pet in the input photo into a premium hand-drawn 2D mascot for a focus app. Preserve species, coat color, markings, ear shape and eye color. Full body, centered, cream outline, flat soft green background, no text, no watermark, no extra animal.";
  let result;
  try {
    result = await env.AI.run(
      env.PET_MODEL || "@cf/runwayml/stable-diffusion-v1-5-img2img",
      {
      prompt,
      negative_prompt:
        "text, watermark, extra animal, cropped body, duplicate, photorealistic background",
      image_b64: match[1],
      strength: 0.42,
      guidance: 7.5,
      num_steps: 16,
      width: 768,
      height: 768,
      }
    );
  } catch (error) {
    await refundQuota(env, user.id, quota);
    throw error;
  }
  const buffer = await new Response(result).arrayBuffer();
  if (!buffer.byteLength) {
    await refundQuota(env, user.id, quota);
    throw new Error("图片模型没有返回结果");
  }
  return json({
    ok: true,
    data: { image: `data:image/png;base64,${bytesToBase64(new Uint8Array(buffer))}` },
  });
}

async function route(request, env) {
  const url = new URL(request.url);
  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: corsHeaders(request, env) });
  }
  if (request.headers.get("origin") && !allowedOrigin(request, env)) {
    return json({ ok: false, error: "来源未获准" }, 403);
  }
  if (request.method === "GET" && url.pathname === "/health") {
    return json({ ok: true, data: { service: "focus-cloud", model: env.TEXT_MODEL } });
  }
  if (request.method === "GET" && url.pathname === "/v1/account") {
    const user = await requireUser(request, env);
    return json({ ok: true, data: { username: user.username, expires_at: user.expires_at } });
  }
  if (request.method === "POST" && url.pathname === "/v1/auth/register") return register(request, env);
  if (request.method === "POST" && url.pathname === "/v1/auth/login") return login(request, env);
  if (request.method === "POST" && url.pathname === "/v1/auth/logout") return logout(request, env);
  if (request.method === "POST" && url.pathname === "/v1/chat") return chat(request, env);
  if (request.method === "POST" && url.pathname === "/v1/plan") return plan(request, env);
  if (request.method === "POST" && url.pathname === "/v1/pet") return pet(request, env);
  return json({ ok: false, error: "接口不存在" }, 404);
}

export default {
  async fetch(request, env) {
    const cors = corsHeaders(request, env);
    try {
      const response = await route(request, env);
      for (const [key, value] of Object.entries(cors)) response.headers.set(key, value);
      return response;
    } catch (error) {
      if (error instanceof Response) {
        return json({ ok: false, error: await error.text() }, error.status, cors);
      }
      return json(
        { ok: false, error: String(error?.message || "服务暂时不可用").slice(0, 180) },
        400,
        cors
      );
    }
  },
};
