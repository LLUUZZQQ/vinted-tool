// Proxy Worker — GitHub Releases 代理 + AI 背景替换
const REPO = "LLUUZZQQ/vinted-tool";
const RAW = `https://raw.githubusercontent.com/${REPO}/main`;
const DL = `https://github.com/${REPO}/releases/download`;
const AI_MODEL = "google/gemini-2.5-flash-image";

// 最新版本信息（发布时更新此处）
const LATEST_VERSION = "3.6.14";
const LATEST_CHANGELOG = `修复GPS坐标异常 · 补充EXIF标准字段 · 新增清除元数据模式 · 设备匹配JPEG压缩

清除元数据 — 彻底剥离所有拍摄信息，纯净输出

设备匹配 — Apple/Samsung/Canon等16家厂商JPEG压缩指纹`;
const MAX_IMAGE_SIZE = 10 * 1024 * 1024; // 10MB
const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/avif"];
const RATE_LIMIT_WINDOW = 60; // 秒
const RATE_LIMIT_MAX = 30;    // 窗口内最大请求数

// 简易内存速率限制（Worker 实例级，重启清零）
const rateMap = new Map();
function checkRateLimit(clientIp) {
  const now = Math.floor(Date.now() / 1000);
  const entry = rateMap.get(clientIp) || { count: 0, reset: now + RATE_LIMIT_WINDOW };
  if (now > entry.reset) { entry.count = 0; entry.reset = now + RATE_LIMIT_WINDOW; }
  entry.count++;
  rateMap.set(clientIp, entry);
  // 定期清理过期条目
  if (rateMap.size > 5000) {
    for (const [ip, e] of rateMap) { if (now > e.reset) rateMap.delete(ip); }
  }
  return entry.count <= RATE_LIMIT_MAX;
}

async function getVersion() {
  const r = await fetch(`${RAW}/update.json`);
  if (!r.ok) return null;
  const d = await r.json();
  const v = d.version || "";
  return v.startsWith("v") ? v : `v${v}`;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const p = url.pathname;
    const clientIp = request.headers.get("CF-Connecting-IP") || "unknown";

    // 速率限制（跳过静态资源）
    if (!p.startsWith("/download") && !p.startsWith("/dl")) {
      if (!checkRateLimit(clientIp)) {
        return new Response("Too Many Requests", { status: 429 });
      }
    }

    // /update.json — 版本信息内嵌 Worker，不依赖 GitHub raw
    if (p === "/update.json") {
      return Response.json({
        version: LATEST_VERSION,
        changelog: LATEST_CHANGELOG,
        download_url: `https://${url.hostname}/download?v=v${LATEST_VERSION}`,
      }, { headers: { "Access-Control-Allow-Origin": "*" } });
    }

    // /download — EXE（应用内更新用，兼容所有版本）
    if (p === "/download") {
      const v = url.searchParams.get("v") || await getVersion();
      if (!v) return new Response("Version unavailable", { status: 502 });
      return proxy(`${DL}/${v}/ImageMAX.exe`, "ImageMAX.exe");
    }

    // /dl — ZIP（浏览器下载用，避免安全提示）
    if (p === "/dl") {
      const v = await getVersion();
      if (!v) return new Response("Version unavailable", { status: 502 });
      return proxy(`${DL}/${v}/ImageMAX_${v}.zip`, "ImageMAX.zip");
    }

    // /ai-credits — 查看/管理余额
    if (p === "/ai-credits") {
      const hwid = url.searchParams.get("hwid");
      if (!hwid) return new Response("Missing hwid", { status: 400 });

      // POST: 充值（密钥通过 Bearer header 传递）
      if (request.method === "POST") {
        const add = parseInt(url.searchParams.get("add") || "0");
        const auth = request.headers.get("Authorization") || "";
        const secret = auth.startsWith("Bearer ") ? auth.slice(7) : "";
        if (!env.ADMIN_SECRET || secret !== env.ADMIN_SECRET) return new Response("Unauthorized", { status: 403 });
        const key = `credits_${hwid}`;
        const current = parseInt(await env.VTMAX_CREDITS.get(key) || "0");
        await env.VTMAX_CREDITS.put(key, String(current + add));
        return Response.json({ hwid, credits: current + add });
      }

      // GET: 查询
      const key = `credits_${hwid}`;
      const credits = parseInt(await env.VTMAX_CREDITS.get(key) || "0");
      return Response.json({ hwid, credits });
    }

    // /ai-bg-replace — AI 背景替换
    if (p === "/ai-bg-replace" && request.method === "POST") {
      try {
        const formData = await request.formData();
        const imageFile = formData.get("image");
        const hwid = formData.get("hwid");
        const prompt = formData.get("prompt") || "Replace the background with a realistic setting. Keep the product exactly as is. Add natural shadows and proper lighting so it looks like a real photo taken in that environment.";

        if (!imageFile || !hwid) {
          return new Response(JSON.stringify({ error: "Missing image or hwid" }), { status: 400 });
        }

        // 验证图片类型和大小
        if (!ALLOWED_IMAGE_TYPES.includes(imageFile.type)) {
          return new Response(JSON.stringify({ error: "不支持的图片格式，仅支持 JPG/PNG/WebP/AVIF" }), { status: 400 });
        }
        if (imageFile.size > MAX_IMAGE_SIZE) {
          return new Response(JSON.stringify({ error: "图片过大，最大支持 10MB" }), { status: 413 });
        }

        // 检查余额
        const key = `credits_${hwid}`;
        const credits = parseInt(await env.VTMAX_CREDITS.get(key) || "0");
        if (credits <= 0) {
          return Response.json({ error: "余额不足，请联系管理员充值" }, { status: 402 });
        }

        // 图片转 base64（分块转换，避免大文件 OOM）
        const imageBytes = await imageFile.arrayBuffer();
        const uint8 = new Uint8Array(imageBytes);
        let b64 = "";
        const chunk = 8192;
        for (let i = 0; i < uint8.length; i += chunk) {
          b64 += String.fromCharCode(...uint8.slice(i, i + chunk));
        }
        b64 = btoa(b64);
        const mimeType = imageFile.type || "image/jpeg";
        const dataUrl = `data:${mimeType};base64,${b64}`;

        // 调用 OpenRouter
        const orResp = await fetch("https://openrouter.ai/api/v1/chat/completions", {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${env.OR_KEY || ""}`,
            "Content-Type": "application/json",
            "HTTP-Referer": "https://vt-proxy.vtmax.workers.dev",
            "X-Title": "ImageMAX AI"
          },
          body: JSON.stringify({
            model: AI_MODEL,
            modalities: ["image", "text"],
            messages: [{
              role: "user",
              content: [
                { type: "text", text: prompt },
                { type: "image_url", image_url: { url: dataUrl } }
              ]
            }]
          })
        });

        if (!orResp.ok) {
          const errText = await orResp.text();
          return new Response(JSON.stringify({ error: `AI 服务异常: ${errText.slice(0, 200)}` }), { status: 502 });
        }

        const orData = await orResp.json();
        const content = orData.choices?.[0]?.message?.content;

        // 提取返回的图片
        let resultB64 = null;
        if (Array.isArray(content)) {
          for (const item of content) {
            if (item.type === "image_url" && item.image_url?.url) {
              resultB64 = item.image_url.url;
              break;
            }
          }
        }

        if (!resultB64) {
          return new Response(JSON.stringify({ error: "AI 未返回图片" }), { status: 502 });
        }

        // 扣减余额
        await env.VTMAX_CREDITS.put(key, String(credits - 1));

        // 返回图片
        const imgData = resultB64.startsWith("data:")
          ? resultB64.split(",")[1]
          : resultB64;
        const imgBytes = Uint8Array.from(atob(imgData), c => c.charCodeAt(0));

        return new Response(imgBytes, {
          headers: {
            "Content-Type": "image/jpeg",
            "Access-Control-Allow-Origin": "*",
            "X-Credits-Remaining": String(credits - 1)
          }
        });

      } catch (e) {
        return new Response(JSON.stringify({ error: e.message }), { status: 500 });
      }
    }

    return new Response("Not Found", { status: 404 });
  }
};

async function proxy(target, filename) {
  const r = await fetch(target, {
    headers: { "User-Agent": "ImageMAX/1.0" },
    redirect: "follow"
  });
  if (!r.ok) return new Response("File Not Found", { status: 404 });
  const h = new Headers(r.headers);
  h.set("Content-Disposition", `attachment; filename="${filename}"`);
  h.set("Access-Control-Allow-Origin", "*");
  return new Response(r.body, { status: r.status, headers: h });
}
