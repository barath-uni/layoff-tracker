// POST /api/event {t}: counts panel / gate_view / signup_open. Logged only for now (see _lib.js TODO).
const { COUNTABLE, send, body } = require("./_lib");

module.exports = (req, res) => {
  if (req.method !== "POST") return send(res, 405, { ok: false });
  const d = body(req);
  if (!d || !COUNTABLE.has(d.t)) return send(res, 400, { ok: false });
  console.log("event", d.t);
  return send(res, 200, { ok: true });
};
