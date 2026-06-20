const COOKIE_NAME = "prediktor_vip";

export const config = {
  matcher: ["/vip", "/vip/:path*", "/app.html"]
};

function readCookie(header, name) {
  return header
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${name}=`))
    ?.slice(name.length + 1);
}

async function sha256(value) {
  const bytes = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

export default async function middleware(request) {
  const url = new URL(request.url);
  const password = process.env.VIP_PASSWORD;
  const secret = process.env.VIP_SESSION_SECRET || "prediktor-vip-v1";
  const next = encodeURIComponent(`${url.pathname}${url.search}`);

  if (!password) {
    return Response.redirect(new URL(`/vip-login?next=${next}&error=config`, request.url));
  }

  const token = readCookie(request.headers.get("cookie") || "", COOKIE_NAME);
  const expected = await sha256(`${password}:${secret}`);

  if (token === expected) {
    return;
  }

  return Response.redirect(new URL(`/vip-login?next=${next}`, request.url));
}
