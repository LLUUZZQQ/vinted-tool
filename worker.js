// Proxy Worker — 代理 GitHub Releases 下载，隐藏 GitHub URL
const REPO = "LLUUZZQQ/vinted-tool";
const RAW = `https://raw.githubusercontent.com/${REPO}/main`;
const DL = `https://github.com/${REPO}/releases/download`;

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
      d.download_url = `https://${url.hostname}/download`;
      return Response.json(d, { headers: { "Access-Control-Allow-Origin": "*" } });
    }

    // /download — EXE
    if (p === "/download") {
      const v = await getVersion();
      if (!v) return new Response("Version unavailable", { status: 502 });
      return proxy(`${DL}/${v}/ImageMAX.exe`, "ImageMAX.exe");
    }

    // /dl — ZIP
    if (p === "/dl") {
      const v = await getVersion();
      if (!v) return new Response("Version unavailable", { status: 502 });
      return proxy(`${DL}/${v}/ImageMAX_${v}.zip`, `ImageMAX_${v}.zip`);
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
