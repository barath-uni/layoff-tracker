// POST /api/signup {email, website, src}. `website` is a hidden honeypot: filled = fake success, nothing logged.
const { EMAIL_RE, send, body } = require("./_lib");

module.exports = (req, res) => {
  if (req.method !== "POST") return send(res, 405, { ok: false });
  const d = body(req);
  if (!d) return send(res, 400, { ok: false, error: "bad json" });
  if (d.website) return send(res, 200, { ok: true });
  const email = String(d.email || "").trim().toLowerCase();
  if (email.length > 254 || !EMAIL_RE.test(email)) return send(res, 400, { ok: false, error: "Enter a valid email." });
  console.log("signup", JSON.stringify({ email, at: new Date().toISOString().slice(0, 19) + "Z", src: String(d.src || "").slice(0, 80) }));
  return send(res, 200, { ok: true, known: false });
};
