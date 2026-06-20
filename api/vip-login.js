const crypto = require("crypto");

const COOKIE_NAME = "prediktor_vip";
const MAX_AGE = 60 * 60 * 24 * 31;

function sessionToken() {
  const password = process.env.VIP_PASSWORD;
  const secret = process.env.VIP_SESSION_SECRET || "prediktor-vip-v1";
  if (!password) return null;
  return crypto.createHash("sha256").update(`${password}:${secret}`).digest("hex");
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let body = "";
    req.on("data", chunk => {
      body += chunk;
      if (body.length > 10000) {
        reject(new Error("payload_too_large"));
        req.destroy();
      }
    });
    req.on("end", () => resolve(body));
    req.on("error", reject);
  });
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.statusCode = 405;
    res.setHeader("Allow", "POST");
    res.end("Method not allowed");
    return;
  }

  const expected = process.env.VIP_PASSWORD;
  const token = sessionToken();
  if (!expected || !token) {
    res.statusCode = 500;
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    res.end(JSON.stringify({ ok: false, error: "VIP_PASSWORD no configurado" }));
    return;
  }

  let submitted = "";
  try {
    const body = await readBody(req);
    const params = new URLSearchParams(body);
    submitted = params.get("password") || "";
  } catch (error) {
    res.statusCode = 400;
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    res.end(JSON.stringify({ ok: false, error: "Solicitud inválida" }));
    return;
  }

  if (submitted !== expected) {
    res.statusCode = 401;
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    res.end(JSON.stringify({ ok: false, error: "Contraseña incorrecta" }));
    return;
  }

  res.statusCode = 200;
  res.setHeader("Set-Cookie", `${COOKIE_NAME}=${token}; Path=/; Max-Age=${MAX_AGE}; HttpOnly; Secure; SameSite=Lax`);
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.end(JSON.stringify({ ok: true }));
};
