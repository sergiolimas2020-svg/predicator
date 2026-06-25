const fs = require("fs");
const path = require("path");

function exists(relativePath) {
  return fs.existsSync(path.join(process.cwd(), relativePath));
}

module.exports = async function handler(req, res) {
  const checks = {
    vip_configured: Boolean(process.env.VIP_PASSWORD),
    assistant_data: exists("static/market_analyzer.json"),
    pwa_manifest: exists("site.webmanifest"),
    service_worker: exists("sw.js"),
    icon_192: exists("icons/icon-192.png"),
    icon_512: exists("icons/icon-512.png")
  };

  const ok = Object.values(checks).every(Boolean);
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.statusCode = ok ? 200 : 503;
  res.end(JSON.stringify({ ok, checks }));
};
