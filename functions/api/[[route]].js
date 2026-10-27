// Cloudflare Pages Function: /api/signup, /api/event, /api/stats.
// Storage: a D1 binding named DB (preferred) or a KV namespace bound as SIGNUPS. Tables create themselves.
// Local preview (`python -m radar serve`) implements the same routes in radar/build.py and writes data/signups.jsonl.
// No third-party analytics: only counts (panel opens, gate views, sign-ups) and the emails people type in.

const EMAIL_RE = /^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$/;
const COUNTABLE = new Set(["panel", "gate_view", "signup_open"]);
const LIMITS = { signup: 5, event: 120 }; // per IP hash per 10 minutes
const WINDOW_S = 600;

const json = (code, obj) =>
  new Response(JSON.stringify(obj), { status: code, headers: { "content-type": "application/json", "cache-control": "no-store" } });

async function ipHash(request, env) {
  const ip = request.headers.get("cf-connecting-ip") || "0.0.0.0";
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode((env.HASH_SALT || "lr") + ip));
  return [...new Uint8Array(buf)].slice(0, 12).map((b) => b.toString(16).padStart(2, "0")).join("");
}
const today = () => new Date().toISOString().slice(0, 10);

// ---------------------------------------------------------------- D1
let ready = false;
async function d1(env) {
  if (!ready) {
    await env.DB.batch([
      env.DB.prepare("CREATE TABLE IF NOT EXISTS signups (email TEXT PRIMARY KEY, created_at TEXT, src TEXT, ua TEXT, ip TEXT)"),
      env.DB.prepare("CREATE TABLE IF NOT EXISTS counts (name TEXT, day TEXT, n INTEGER, PRIMARY KEY (name, day))"),
      env.DB.prepare("CREATE TABLE IF NOT EXISTS hits (ip TEXT, kind TEXT, at INTEGER)"),
    ]);
    ready = true;
  }
  return env.DB;
}
const D1 = {
  async allow(env, ip, kind) {
    const db = await d1(env), now = Math.floor(Date.now() / 1000);
    const r = await db.prepare("SELECT COUNT(*) AS n FROM hits WHERE ip = ? AND kind = ? AND at > ?").bind(ip, kind, now - WINDOW_S).first();
    if (r.n >= LIMITS[kind]) return false;
    await db.batch([
      db.prepare("INSERT INTO hits (ip, kind, at) VALUES (?, ?, ?)").bind(ip, kind, now),
      db.prepare("DELETE FROM hits WHERE at < ?").bind(now - WINDOW_S),
    ]);
    return true;
  },
  async bump(env, name) {
    const db = await d1(env);
    await db.prepare("INSERT INTO counts (name, day, n) VALUES (?, ?, 1) ON CONFLICT(name, day) DO UPDATE SET n = n + 1").bind(name, today()).run();
  },
  async addSignup(env, row) {
    const db = await d1(env);
    const r = await db.prepare("INSERT OR IGNORE INTO signups (email, created_at, src, ua, ip) VALUES (?, ?, ?, ?, ?)")
      .bind(row.email, row.at, row.src, row.ua, row.ip).run();
    return r.meta.changes === 0; // true = already known
  },
  async stats(env) {
    const db = await d1(env);
    const n = (await db.prepare("SELECT COUNT(*) AS n FROM signups").first()).n;
    const rows = (await db.prepare("SELECT name, day, n FROM counts ORDER BY day").all()).results;
    return { signups: n, rows };
  },
};

// ---------------------------------------------------------------- KV (fallback; counts are approximate under heavy concurrency)
const KV = {
  async allow(env, ip, kind) {
    const k = `rl:${kind}:${ip}`, n = +((await env.SIGNUPS.get(k)) || 0);
    if (n >= LIMITS[kind]) return false;
    await env.SIGNUPS.put(k, String(n + 1), { expirationTtl: WINDOW_S });
    return true;
  },
  async bump(env, name) {
    const k = `count:${name}:${today()}`;
    await env.SIGNUPS.put(k, String(+((await env.SIGNUPS.get(k)) || 0) + 1));
  },
  async addSignup(env, row) {
    const k = `email:${row.email}`;
    if (await env.SIGNUPS.get(k)) return true;
    await env.SIGNUPS.put(k, JSON.stringify(row));
    return false;
  },
  async stats(env) {
    let signups = 0, rows = [], cursor;
    do {
      const page = await env.SIGNUPS.list({ cursor });
      for (const { name } of page.keys) {
        if (name.startsWith("email:")) signups++;
        else if (name.startsWith("count:")) {
          const [, n, day] = name.split(":");
          rows.push({ name: n, day, n: +(await env.SIGNUPS.get(name)) });
        }
      }
      cursor = page.list_complete ? null : page.cursor;
    } while (cursor);
    return { signups, rows };
  },
};

export async function onRequest({ request, env, params }) {
  const route = (params.route || []).join("/");
  const store = env.DB ? D1 : env.SIGNUPS ? KV : null;
  if (!store) return json(503, { ok: false, error: "No storage bound (add D1 as DB or KV as SIGNUPS)." });

  if (route === "stats" && request.method === "GET") {
    const key = new URL(request.url).searchParams.get("key");
    if (!env.STATS_KEY || key !== env.STATS_KEY) return json(403, { ok: false });
    const { signups, rows } = await store.stats(env);
    const by_day = {}, totals = {};
    for (const r of rows) {
      (by_day[r.name] ||= {})[r.day] = r.n;
      totals[r.name] = (totals[r.name] || 0) + r.n;
    }
    return json(200, { signups, totals, by_day });
  }
  if (request.method !== "POST") return json(405, { ok: false });

  let d;
  try { d = await request.json(); } catch { return json(400, { ok: false, error: "bad json" }); }
  const ip = await ipHash(request, env);

  if (route === "event") {
    if (!COUNTABLE.has(d.t)) return json(400, { ok: false });
    if (await store.allow(env, ip, "event")) await store.bump(env, d.t);
    return json(200, { ok: true });
  }
  if (route !== "signup") return json(404, { ok: false });

  if (d.website) return json(200, { ok: true }); // honeypot: bots get a fake success
  const email = String(d.email || "").trim().toLowerCase();
  if (email.length > 254 || !EMAIL_RE.test(email)) return json(400, { ok: false, error: "Enter a valid email." });
  if (!(await store.allow(env, ip, "signup"))) return json(429, { ok: false, error: "Too many tries. Wait a few minutes." });
  const known = await store.addSignup(env, {
    email, at: new Date().toISOString().slice(0, 19) + "Z", src: String(d.src || "").slice(0, 80),
    ua: (request.headers.get("user-agent") || "").slice(0, 160), ip,
  });
  if (!known) await store.bump(env, "signup");
  return json(200, { ok: true, known });
}
