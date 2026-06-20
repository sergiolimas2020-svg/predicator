const crypto = require("crypto");

const COOKIE_NAME = "prediktor_vip";

function readCookie(header, name) {
  return String(header || "")
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${name}=`))
    ?.slice(name.length + 1);
}

function sessionToken() {
  const password = process.env.VIP_PASSWORD;
  const secret = process.env.VIP_SESSION_SECRET || "prediktor-vip-v1";
  if (!password) return null;
  return crypto.createHash("sha256").update(`${password}:${secret}`).digest("hex");
}

module.exports = async function handler(req, res) {
  const expected = sessionToken();
  const token = readCookie(req.headers.cookie, COOKIE_NAME);
  const isPro = Boolean(expected && token === expected);

  res.setHeader("Cache-Control", "no-store");
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.statusCode = 200;
  res.end(JSON.stringify({ ok: true, is_pro: isPro }));
};
