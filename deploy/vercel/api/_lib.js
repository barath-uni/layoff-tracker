// Shared helpers for the Vercel functions (files starting with _ are not routes).
// TODO: store sign-ups and counts in Upstash Redis. For now they only go to the function logs (Vercel → Logs).
const EMAIL_RE = /^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$/;
const COUNTABLE = new Set(["panel", "gate_view", "signup_open"]);

function send(res, code, obj) {
  res.setHeader("cache-control", "no-store");
  res.status(code).json(obj);
}

function body(req) {
  if (req.body && typeof req.body === "object") return req.body;
  try { return JSON.parse(req.body || "{}"); } catch { return null; }
}

module.exports = { EMAIL_RE, COUNTABLE, send, body };
