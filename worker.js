// Proxy Worker — GitHub Releases 代理 + AI 背景替换
const REPO = "LLUUZZQQ/vinted-tool";
const RAW = `https://raw.githubusercontent.com/${REPO}/main`;
const DL = `https://github.com/${REPO}/releases/download`;
const AI_MODEL = "google/gemini-2.5-flash-image";

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

    // /update.json
    if (p === "/update.json") {
      const r = await fetch(`${RAW}/update.json`);
      if (!r.ok) return new Response("Unavailable", { status: 502 });
      const d = await r.json();
      d.download_url = d.download_url || `https://${url.hostname}/download`;
      return Response.json(d, { headers: { "Access-Control-Allow-Origin": "*" } });
    }

    // /download — EXE（应用内更新用，兼容所有版本）
    if (p === "/download") {
      const v = await getVersion();
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

      // POST: 充值
      if (request.method === "POST") {
        const add = parseInt(url.searchParams.get("add") || "0");
        const secret = url.searchParams.get("secret") || "";
        if (secret !== (env.ADMIN_SECRET || "vtmax_admin_2026")) return new Response("Unauthorized", { status: 403 });
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

        // 检查余额
        const key = `credits_${hwid}`;
        const credits = parseInt(await env.VTMAX_CREDITS.get(key) || "0");
        if (credits <= 0) {
          return Response.json({ error: "余额不足，请联系管理员充值" }, { status: 402 });
        }

        // 图片转 base64
        const imageBytes = await imageFile.arrayBuffer();
        const b64 = btoa(String.fromCharCode(...new Uint8Array(imageBytes)));
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
