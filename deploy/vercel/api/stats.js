// GET /api/stats: not available until storage exists (TODO: Upstash Redis). Sign-ups are in the function logs.
const { send } = require("./_lib");

module.exports = (req, res) => send(res, 501, { ok: false, error: "No storage yet: see the function logs for sign-ups and events." });
