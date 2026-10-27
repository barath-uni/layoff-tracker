/* Home app: dot-matrix globe with company-logo pins, live counter, live feed, pin card and the "Replay" scrubber.
   Canvas 2D + d3-geo (vendored). One requestAnimationFrame loop; devicePixelRatio capped at 2. */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var dataEl = $("#events");
  if (!dataEl) return;
  var events = JSON.parse(dataEl.textContent);
  var warn = []; try { warn = JSON.parse($("#warn").textContent); } catch (_) {}
  var WK = JSON.parse($("#weekly").textContent);
  var reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var DAY = 864e5, TAU = Math.PI * 2, RAD = Math.PI / 180;
  var fmt = function (n) { return n == null ? "–" : Math.round(n).toLocaleString("en-US"); };
  var tOf = function (d) { return Date.parse(d + "T12:00:00"); };
  var mobile = function () { return innerWidth < 900; };
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function flag(cc) { return cc && cc.length === 2 ? String.fromCodePoint(0x1F1E6 + cc.charCodeAt(0) - 65, 0x1F1E6 + cc.charCodeAt(1) - 65) : ""; }
  function agoShort(t, now) { var d = Math.floor((now - t) / DAY); return d <= 0 ? "today" : d < 14 ? d + "d" : d < 60 ? Math.round(d / 7) + "w" : Math.round(d / 30.4) + "mo"; }
  function agoLong(t) {
    var d = Math.floor((Date.now() - t) / DAY);
    return d <= 0 ? "today" : d === 1 ? "yesterday" : d < 14 ? d + " days ago" : new Date(t).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }
  function pctNum(ps) { if (!ps) return null; var v = parseFloat(String(ps).replace(/[^0-9.]/g, "")); return isFinite(v) ? v : null; }
  function hash(s) { var h = 2166136261; for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return (h >>> 0) / 4294967296; }
  function initials(name) {
    var w = name.replace(/^the\s+/i, "").split(/[\s\-&/]+/).filter(function (x) { return /[A-Za-z0-9]/.test(x); });
    return ((w[0] || "?")[0] + (w.length > 1 ? w[1][0] : (w[0] || "").slice(1, 2))).toUpperCase();
  }
  function track(t) {
    try { fetch("/api/event", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ t: t }), keepalive: true }).catch(function () {}); } catch (_) {}
  }
  var toastEl = $(".toast"), toastT;
  function toast(m) { toastEl.textContent = m; toastEl.classList.add("show"); clearTimeout(toastT); toastT = setTimeout(function () { toastEl.classList.remove("show"); }, 1800); }
  function copy(url) {
    if (navigator.clipboard) navigator.clipboard.writeText(url).then(function () { toast("Link copied"); }, function () { toast(url); });
    else toast(url);
  }
  document.addEventListener("click", function (ev) { var b = ev.target.closest("[data-copy]"); if (b) copy(b.getAttribute("data-copy")); });
  var warnBySlug = {}; warn.forEach(function (w) { if (w.s) (warnBySlug[w.s] = warnBySlug[w.s] || []).push(w); });

  // ---------------------------------------------------------------- logos (favicon in a white disc, monogram fallback)
  var LOGO_SRC = [function (d) { return "https://www.google.com/s2/favicons?domain=" + d + "&sz=64"; },
                  function (d) { return "https://icons.duckduckgo.com/ip3/" + d + ".ico"; }];
  var imgCache = {};   // domain -> {img, ok, fail, cbs}
  function loadLogo(dm, cb) {
    var c = imgCache[dm];
    if (!c) {
      c = imgCache[dm] = { ok: false, fail: false, cbs: [], i: 0, img: new Image() };
      c.img.referrerPolicy = "no-referrer";
      c.img.onload = function () {
        if (c.img.naturalWidth <= 2) return c.img.onerror();
        c.ok = true; c.cbs.forEach(function (f) { f(c); }); c.cbs = [];
      };
      c.img.onerror = function () {
        c.i++;
        if (c.i < LOGO_SRC.length) { c.img.src = LOGO_SRC[c.i](dm); return; }
        c.fail = true; c.cbs.forEach(function (f) { f(c); }); c.cbs = [];
      };
      c.img.src = LOGO_SRC[0](dm);
    }
    if (c.ok || c.fail) cb(c); else c.cbs.push(cb);
  }
  function logoEl(e, big) {
    var s = el("span", "lg" + (big ? " lg-lg" : ""));
    var mono = function () { s.classList.add("mono"); s.textContent = initials(e.c); };
    if (!e.dm) { mono(); return s; }
    loadLogo(e.dm, function (c) {
      if (c.fail) { s.textContent = ""; mono(); return; }
      if (!s.firstChild) { var im = el("img"); im.alt = ""; im.referrerPolicy = "no-referrer"; im.src = c.img.src; s.appendChild(im); }
    });
    return s;
  }
  var SP = 64, sprites = {};   // slug -> canvas (circular, SP×SP device px)
  function sprite(e) {
    var sp = sprites[e.s];
    if (sp) return sp;
    sp = sprites[e.s] = document.createElement("canvas");
    sp.width = sp.height = SP;
    var g = sp.getContext("2d");
    var mono = function () {
      g.clearRect(0, 0, SP, SP);
      g.beginPath(); g.arc(SP / 2, SP / 2, SP / 2, 0, TAU); g.fillStyle = "#1d212b"; g.fill();
      g.fillStyle = "#eef0f4"; g.font = "600 " + Math.round(SP * 0.36) + "px Geist, system-ui, sans-serif";
      g.textAlign = "center"; g.textBaseline = "middle"; g.fillText(initials(e.c), SP / 2, SP / 2 + 1);
    };
    mono();
    if (e.dm) {
      loadLogo(e.dm, function (c) {
        if (c.fail) return;
        g.clearRect(0, 0, SP, SP);
        g.beginPath(); g.arc(SP / 2, SP / 2, SP / 2, 0, TAU); g.fillStyle = "#f4f5f7"; g.fill();
        var s = SP * 0.6;
        try { g.drawImage(c.img, (SP - s) / 2, (SP - s) / 2, s, s); } catch (_) { mono(); }
      });
    }
    return sp;
  }

  // ---------------------------------------------------------------- marks (one per geocoded event)
  var marks = [];
  events.forEach(function (e) {
    e.t = tOf(e.d);
    if (e.la == null) return;
    var h1 = hash(e.s + e.d), h2 = hash(e.d + e.s + "j");
    var jr = e.pc ? 0.5 + 1.8 * h2 : 0.15 * h2, ja = h1 * TAU;  // spread pins that share a country centroid
    var lat = e.la + jr * Math.sin(ja), lon = e.lo2 + jr * Math.cos(ja) / Math.max(0.3, Math.cos(e.la * RAD));
    var c = Math.cos(lat * RAD);
    e.mark = { e: e, lon: lon, lat: lat, x: c * Math.cos(lon * RAD), y: c * Math.sin(lon * RAD), z: Math.sin(lat * RAD),
      r: Math.max(11, Math.min(20, 9 + 2.4 * Math.log10((e.n || 0) + 10))), ph: h1, sx: 0, sy: 0, rr: 0, vis: false, born: 0, pin: false };
    marks.push(e.mark);
  });

  // ---------------------------------------------------------------- globe state + projection (same maths as d3.geoOrthographic().rotate([λ, φ]))
  var canvas = $("[data-globe]"), ctx = canvas.getContext("2d");
  var dpr = Math.min(2, window.devicePixelRatio || 1), W = 0, H = 0, cx = 0, cy = 0, R = 200, k = 1, K_MAX = 8;
  var cyOff = 0, cyOffT = 0;
  var rot = [100, -28], vel = [0, 0], lastInteract = 0, fly = null, camera = true;
  var cl = 1, sl = 0, cp = 1, sp_ = 0, S = R;
  var land = null, landDots = null, ortho = null, gradCache = null, landStep = 1.2;
  function setRot() {
    cl = Math.cos(rot[0] * RAD); sl = Math.sin(rot[0] * RAD); cp = Math.cos(rot[1] * RAD); sp_ = Math.sin(rot[1] * RAD); S = R * k;
  }
  function project(m) {   // writes m.sx, m.sy; returns depth (>0 = front hemisphere)
    var x1 = m.x * cl - m.y * sl, y1 = m.x * sl + m.y * cl;
    var xp = x1 * cp - m.z * sp_, zp = m.z * cp + x1 * sp_;
    m.sx = cx + S * y1; m.sy = cy + cyOff - S * zp;
    return xp;
  }
  function invert(px, py) {   // screen -> [lon, lat] or null
    var y1 = (px - cx) / S, zp = (cy + cyOff - py) / S, q = y1 * y1 + zp * zp;
    if (q > 1) return null;
    var xp = Math.sqrt(1 - q), x1 = xp * cp + zp * sp_, z1 = zp * cp - xp * sp_;
    return [Math.atan2(y1, x1) / RAD - rot[0], Math.asin(Math.max(-1, Math.min(1, z1))) / RAD];
  }
  function wrap(a) { return ((a % 360) + 540) % 360 - 180; }
  function clampLat(v) { return Math.max(-70, Math.min(70, v)); }

  function layout() {
    W = innerWidth; H = innerHeight;
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    if (mobile()) {
      var hud = $("[data-hud]").getBoundingClientRect(), rp = $("[data-replay]").getBoundingClientRect();
      var top = hud.bottom + 6, bot = rp.top - 6;
      cx = W / 2; cy = (top + bot) / 2; R = Math.max(80, Math.min(W * 0.45, (bot - top) * 0.5));
    } else {
      var fl = $("[data-feed]").getBoundingClientRect().left, aw = fl - 20;
      cx = aw * 0.56; cy = (H - 70) / 2 + 8; R = Math.max(120, 0.46 * Math.min(aw * 0.95, H - 96));
    }
    gradCache = null; setRot();
    drawSpark();
  }

  // Dot-matrix land: rasterise the land polygons once (equirectangular), then sample a near-equal-area lattice.
  function buildLand(topo) {
    land = topojson.feature(topo, topo.objects.land);
    var LW = 1024, LH = 512, off = document.createElement("canvas"); off.width = LW; off.height = LH;
    var g = off.getContext("2d");
    var eq = d3.geoEquirectangular().scale(LW / TAU).translate([LW / 2, LH / 2]);
    g.fillStyle = "#fff"; g.beginPath(); d3.geoPath(eq, g)(land); g.fill();
    var px = g.getImageData(0, 0, LW, LH).data, out = [], STEP = mobile() ? 1.5 : 1.2;
    for (var lat = -58; lat <= 83; lat += STEP) {
      var n = Math.max(1, Math.round(360 * Math.cos(lat * RAD) / STEP));
      for (var i = 0; i < n; i++) {
        var lon = -180 + (i + 0.5) * 360 / n;
        var X = Math.min(LW - 1, Math.floor((lon + 180) / 360 * LW)), Y = Math.min(LH - 1, Math.floor((90 - lat) / 180 * LH));
        if (px[(Y * LW + X) * 4 + 3] > 100) {
          var c = Math.cos(lat * RAD);
          out.push(c * Math.cos(lon * RAD), c * Math.sin(lon * RAD), Math.sin(lat * RAD));
        }
      }
    }
    landDots = new Float32Array(out);
    landStep = STEP;
    ortho = d3.geoOrthographic().clipAngle(90).precision(0.8);
  }
  var LEVELS = 7, buckets = [], DOT_A = [0.06, 0.12, 0.2, 0.3, 0.42, 0.55, 0.68];
  for (var bi = 0; bi < LEVELS; bi++) buckets.push([]);

  function drawEarth() {
    var Y = cy + cyOff;
    if (!gradCache || gradCache.S !== S || gradCache.cy !== Y || gradCache.cx !== cx) {
      var g = ctx.createRadialGradient(cx - S * 0.35, Y - S * 0.4, S * 0.05, cx, Y, S * 1.02);
      g.addColorStop(0, "#121826"); g.addColorStop(0.7, "#0a0d15"); g.addColorStop(1, "#06080d");
      var a = ctx.createRadialGradient(cx, Y, S * 0.96, cx, Y, S * 1.18);
      a.addColorStop(0, "rgba(130,160,255,0.13)"); a.addColorStop(0.35, "rgba(130,160,255,0.04)"); a.addColorStop(1, "rgba(130,160,255,0)");
      gradCache = { S: S, cy: Y, cx: cx, g: g, a: a };
    }
    ctx.beginPath(); ctx.arc(cx, Y, S * 1.18, 0, TAU); ctx.fillStyle = gradCache.a; ctx.fill();
    ctx.beginPath(); ctx.arc(cx, Y, S, 0, TAU); ctx.fillStyle = gradCache.g; ctx.fill();
    ctx.lineWidth = 1; ctx.strokeStyle = "rgba(255,255,255,0.07)"; ctx.stroke();
    if (!landDots) return;
    for (var b = 0; b < LEVELS; b++) buckets[b].length = 0;
    var d = landDots, n = d.length, ds = Math.max(1.1, Math.min(2.6, S * landStep * RAD * 0.34)), h = ds / 2;
    for (var i = 0; i < n; i += 3) {
      var x1 = d[i] * cl - d[i + 1] * sl, y1 = d[i] * sl + d[i + 1] * cl, z = d[i + 2];
      var xp = x1 * cp - z * sp_;
      if (xp <= 0.02) continue;
      var sx = cx + S * y1, sy = Y - S * (z * cp + x1 * sp_);
      if (sx < -ds || sx > W + ds || sy < -ds || sy > H + ds) continue;
      buckets[Math.min(LEVELS - 1, (xp * LEVELS) | 0)].push(sx - h, sy - h);
    }
    for (b = 0; b < LEVELS; b++) {
      var bk = buckets[b];
      if (!bk.length) continue;
      ctx.fillStyle = "rgba(160,174,204," + DOT_A[b] + ")";
      for (var j = 0; j < bk.length; j += 2) ctx.fillRect(bk[j], bk[j + 1], ds, ds);
    }
    if (k > 1.7 && ortho && land) {   // coastlines fade in when zoomed, so sparse dots keep their context
      ortho.scale(S).translate([cx, Y]).rotate(rot);
      ctx.beginPath(); d3.geoPath(ortho, ctx)(land);
      ctx.strokeStyle = "rgba(160,174,204," + Math.min(0.28, (k - 1.7) * 0.2).toFixed(3) + ")"; ctx.lineWidth = 0.8; ctx.stroke();
    }
  }

  // ---------------------------------------------------------------- pins, rings, chips
  var replay = { on: false, playing: false, cur: 0, prev: 0, target: null, dur: 20000,
    t0: Date.parse(WK.y + "-01-01T00:00:00"), t1: tOf(WK.today) + DAY / 2 - 1 };
  var selected = null, hover = null, placed = [], chipBoxes = [];
  var cardEl = $("[data-card]");
  function nowRef() { return replay.on ? replay.cur : Date.now(); }
  function pinCap() { return Math.round((mobile() ? 22 : 42) * Math.min(2.6, 1 + 0.45 * Math.log2(k))); }
  function chipCap() { return Math.round((mobile() ? 3 : 7) * Math.min(3, 1 + 0.6 * Math.log2(k))); }
  function ringColor(m, now) { var a = (now - m.e.t) / DAY; return a <= 7 ? "#ff4d4a" : a <= 30 ? "rgba(255,138,134,0.85)" : "rgba(214,220,232,0.55)"; }

  function drawMarks(t) {
    var now = nowRef(), vis = [], i, m;
    for (i = 0; i < marks.length; i++) {
      m = marks[i]; m.pin = false;
      if (replay.on && m.e.t > replay.cur) { m.vis = false; continue; }
      var dp = project(m);
      m.vis = dp > 0.04 && m.sx > -30 && m.sx < W + 30 && m.sy > -30 && m.sy < H + 30;
      if (!m.vis) continue;
      var age = (now - m.e.t) / DAY;
      m.score = Math.log10((m.e.n || 0) + 10) + 2.4 * Math.exp(-Math.max(0, age) / 12) + (m === selected || m === hover ? 100 : 0);
      vis.push(m);
    }
    vis.sort(function (a, b) { return b.score - a.score; });
    // Greedy placement: biggest and freshest first, one pin per company, no heavy overlaps.
    placed = [];
    var seen = {}, cap = pinCap(), scl = mobile() ? 0.85 : 1;
    for (i = 0; i < vis.length && placed.length < cap; i++) {
      m = vis[i];
      if (seen[m.e.s] && m !== selected) continue;
      var r = m.r * scl, ok = true;
      for (var j = 0; j < placed.length; j++) {
        var o = placed[j], dx = o.sx - m.sx, dy = o.sy - m.sy;
        if (dx * dx + dy * dy < Math.pow((o.rr + r) * 0.78, 2)) { ok = false; break; }
      }
      if (!ok && m !== selected && m !== hover) continue;
      m.pin = true; m.rr = r; seen[m.e.s] = 1; placed.push(m);
    }
    // pulse rings: fresh events when live, freshly landed ones during the replay
    if (!reduced) {
      ctx.lineWidth = 1.5;
      for (i = 0; i < vis.length; i++) {
        m = vis[i];
        var p = -1;
        if (replay.on) { if (m.born && t - m.born < 1600) p = (t - m.born) / 1600; }
        else if ((now - m.e.t) / DAY <= 7) p = ((t / 2600) + m.ph) % 1;
        if (p < 0) continue;
        ctx.beginPath(); ctx.arc(m.sx, m.sy, (m.pin ? m.rr + 2 : 3) + p * (replay.on ? 34 : 24), 0, TAU);
        ctx.strokeStyle = "rgba(255,77,74," + (0.6 * (1 - p)).toFixed(3) + ")"; ctx.stroke();
      }
    }
    // small dots for everything without a pin
    ctx.lineWidth = 1;
    for (i = vis.length - 1; i >= 0; i--) {
      m = vis[i];
      if (m.pin) continue;
      var fresh = (now - m.e.t) / DAY <= 7;
      ctx.beginPath(); ctx.arc(m.sx, m.sy, fresh ? 3 : 2.3, 0, TAU);
      ctx.fillStyle = fresh ? "#ff4d4a" : "rgba(226,231,240,0.6)"; ctx.fill();
      ctx.strokeStyle = "rgba(5,6,10,0.8)"; ctx.stroke();
    }
    // logo pins, lowest priority first so the biggest sit on top
    for (i = placed.length - 1; i >= 0; i--) {
      m = placed[i];
      var rad = m.rr;
      if (m.born && t - m.born < 420 && !reduced) { var q = (t - m.born) / 420 - 1; rad *= Math.max(0.05, 1 + 2.7 * q * q * q + 1.7 * q * q); }  // ease-out-back pop
      ctx.beginPath(); ctx.arc(m.sx, m.sy + 2, rad + 4, 0, TAU); ctx.fillStyle = "rgba(0,0,0,0.45)"; ctx.fill();
      ctx.beginPath(); ctx.arc(m.sx, m.sy, rad + 2.5, 0, TAU); ctx.fillStyle = m === selected ? "#ffffff" : ringColor(m, now); ctx.fill();
      ctx.drawImage(sprite(m.e), m.sx - rad, m.sy - rad, rad * 2, rad * 2);
      if (warnBySlug[m.e.s]) {
        ctx.beginPath(); ctx.arc(m.sx + rad * 0.74, m.sy - rad * 0.74, 4.2, 0, TAU); ctx.fillStyle = "#ff4d4a"; ctx.fill();
        ctx.lineWidth = 1.6; ctx.strokeStyle = "#05060a"; ctx.stroke();
      }
    }
    drawChips(now);
  }

  var CHIP_FONT = "600 11.5px Geist, system-ui, sans-serif", CHIP_MONO = "500 11px 'Geist Mono', ui-monospace, monospace";
  function drawChips(now) {
    chipBoxes = [];
    var cap = chipCap(), count = 0, i, m, list = placed.slice();
    if (hover && hover.pin && list.indexOf(hover) > 0) { list.splice(list.indexOf(hover), 1); list.unshift(hover); }
    ctx.textBaseline = "middle";
    for (i = 0; i < list.length && (count < cap || list[i] === hover); i++) {
      m = list[i];
      if (m === selected && !cardEl.hidden) continue;
      var e = m.e, parts = [[e.c, CHIP_FONT, "#eef0f4"], [e.n ? " −" + fmt(e.n) : e.ps ? " −" + e.ps : "", CHIP_FONT, "#ff8a86"],
        [" · " + agoShort(e.t, now), CHIP_MONO, "#7c8290"]], w = 16;
      for (var p = 0; p < parts.length; p++) { ctx.font = parts[p][1]; parts[p][3] = ctx.measureText(parts[p][0]).width; w += parts[p][3]; }
      var hgt = 22, x = m.sx + m.rr + 7, y = m.sy - hgt / 2, box = [x, y, x + w, y + hgt];
      if (box[2] > W - 8 || clash(box, m)) { x = m.sx - m.rr - 7 - w; box = [x, y, x + w, y + hgt]; }
      if ((box[0] < 8 || box[1] < 8 || box[3] > H - 8 || clash(box, m)) && m !== hover) continue;
      chipBoxes.push(box); count++;
      roundRect(x, y, w, hgt, 7); ctx.fillStyle = "rgba(10,12,18,0.86)"; ctx.fill();
      ctx.lineWidth = 1; ctx.strokeStyle = m === hover ? "rgba(255,255,255,0.24)" : "rgba(255,255,255,0.09)"; ctx.stroke();
      var tx = x + 8;
      for (p = 0; p < parts.length; p++) { ctx.font = parts[p][1]; ctx.fillStyle = parts[p][2]; ctx.fillText(parts[p][0], tx, y + hgt / 2 + 0.5); tx += parts[p][3]; }
    }
  }
  function clash(b, self) {
    for (var i = 0; i < chipBoxes.length; i++) { var o = chipBoxes[i]; if (b[0] < o[2] && b[2] > o[0] && b[1] < o[3] && b[3] > o[1]) return true; }
    for (i = 0; i < placed.length; i++) {
      var m = placed[i], r = m.rr + 2;
      if (m !== self && b[0] < m.sx + r && b[2] > m.sx - r && b[1] < m.sy + r && b[3] > m.sy - r) return true;
    }
    return false;
  }
  function roundRect(x, y, w, h, r) {
    ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }

  // ---------------------------------------------------------------- frame loop
  var lastT = 0;
  function frame(t) {
    var dt = Math.min(64, lastT ? t - lastT : 16); lastT = t;
    if (!document.hidden) {
      step(t, dt);
      ctx.clearRect(0, 0, W, H);
      drawEarth();
      drawMarks(t);
      if (selected) placeCard(false);
    }
    requestAnimationFrame(frame);
  }
  function step(t, dt) {
    cyOff += (cyOffT - cyOff) * Math.min(1, dt * 0.008);
    if (fly) {
      var p = Math.min(1, (t - fly.t0) / fly.dur), e = 1 - Math.pow(1 - p, 3);
      rot = [fly.a[0] + fly.d[0] * e, fly.a[1] + fly.d[1] * e];
      if (fly.k) k = fly.k[0] + (fly.k[1] - fly.k[0]) * e;
      if (p >= 1) fly = null;
    } else if (!pointers.size) {
      if (Math.abs(vel[0]) + Math.abs(vel[1]) > 0.0005) {   // inertia after a flick
        rot[0] += vel[0] * dt; rot[1] = clampLat(rot[1] + vel[1] * dt);
        var f = Math.pow(0.94, dt / 16); vel[0] *= f; vel[1] *= f;
      } else if (replay.playing && camera && replay.target) {
        var g = Math.min(1, dt * 0.0022);
        rot[0] += wrap(replay.target[0] - rot[0]) * g; rot[1] += (replay.target[1] - rot[1]) * g;
      } else if (!reduced && !selected && Date.now() - lastInteract > 3500 && !replay.on) {
        rot[0] += 0.0028 * dt / Math.max(1, k);
      }
    }
    if (replay.playing) advanceReplay(t, dt);
    setRot();
  }
  function flyTo(m, ms) {
    fly = { t0: performance.now(), dur: reduced ? 1 : ms || 750, a: rot.slice(), d: [wrap(-m.lon - rot[0]), clampLat(-m.lat) - rot[1]],
      k: k < 1.6 ? [k, mobile() ? 1.5 : 1.7] : null };
    vel = [0, 0];
  }

  // ---------------------------------------------------------------- input: drag with inertia, pinch, wheel, tap
  var pointers = new Map(), gesture = null;
  function local(ev) { return { x: ev.clientX, y: ev.clientY, t: performance.now() }; }
  canvas.addEventListener("pointerdown", function (ev) {
    lastInteract = Date.now(); fly = null; vel = [0, 0];
    if (replay.playing) camera = false;
    pointers.set(ev.pointerId, local(ev));
    try { canvas.setPointerCapture(ev.pointerId); } catch (_) {}
    canvas.classList.add("grabbing");
    if (pointers.size === 1) gesture = { mode: "drag", moved: false, start: local(ev), last: local(ev), hist: [] };
    else if (pointers.size === 2) {
      var it = pointers.values(), a = it.next().value, b = it.next().value;
      gesture = { mode: "pinch", d0: Math.hypot(a.x - b.x, a.y - b.y) || 1, k0: k, mx: (a.x + b.x) / 2, my: (a.y + b.y) / 2, moved: true };
    }
  });
  canvas.addEventListener("pointermove", function (ev) {
    var p = local(ev);
    if (!pointers.has(ev.pointerId)) {
      if (ev.pointerType === "mouse") {
        var h = hit(p.x, p.y);
        if (h !== hover) { hover = h; canvas.classList.toggle("on-pin", !!h); syncFeedHover(); }
      }
      return;
    }
    pointers.set(ev.pointerId, p);
    lastInteract = Date.now();
    if (gesture && gesture.mode === "pinch" && pointers.size >= 2) {
      var it = pointers.values(), a = it.next().value, b = it.next().value;
      var mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      k = Math.max(1, Math.min(K_MAX, gesture.k0 * Math.hypot(a.x - b.x, a.y - b.y) / gesture.d0));
      setRot();
      rot[0] += (mx - gesture.mx) / S / RAD; rot[1] = clampLat(rot[1] - (my - gesture.my) / S / RAD);
      gesture.mx = mx; gesture.my = my;
    } else if (gesture && gesture.mode === "drag") {
      if (!gesture.moved && Math.abs(p.x - gesture.start.x) + Math.abs(p.y - gesture.start.y) < 6) return;
      gesture.moved = true;
      var d0 = (p.x - gesture.last.x) / S / RAD, d1 = -(p.y - gesture.last.y) / S / RAD;
      rot[0] += d0; rot[1] = clampLat(rot[1] + d1);
      gesture.hist.push([p.t, d0, d1]); if (gesture.hist.length > 6) gesture.hist.shift();
      gesture.last = p;
    }
  });
  function endPointer(ev) {
    if (!pointers.has(ev.pointerId)) return;
    var p = pointers.get(ev.pointerId);
    pointers.delete(ev.pointerId);
    lastInteract = Date.now();
    if (pointers.size === 1) { var q = pointers.values().next().value; gesture = { mode: "drag", moved: true, start: q, last: q, hist: [] }; return; }
    if (pointers.size) return;
    canvas.classList.remove("grabbing");
    var g = gesture; gesture = null;
    if (!g || g.mode !== "drag") return;
    if (g.moved) {
      var hs = g.hist.filter(function (x) { return p.t - x[0] < 100; });
      if (hs.length > 1 && !reduced) {
        var span = Math.max(16, hs[hs.length - 1][0] - hs[0][0]), s0 = 0, s1 = 0;
        hs.forEach(function (x) { s0 += x[1]; s1 += x[2]; });
        vel = [s0 / span, s1 / span];
      }
      return;
    }
    if (ev.type === "pointerup") {
      var m = hit(p.x, p.y);
      if (m) select(m.e, true); else if (selected) closeCard();
    }
  }
  canvas.addEventListener("pointerup", endPointer);
  canvas.addEventListener("pointercancel", endPointer);
  canvas.addEventListener("pointerleave", function () { if (hover && !pointers.size) { hover = null; syncFeedHover(); canvas.classList.remove("on-pin"); } });
  canvas.addEventListener("wheel", function (ev) {
    ev.preventDefault();
    var dy = ev.deltaMode === 1 ? ev.deltaY * 33 : ev.deltaMode === 2 ? ev.deltaY * 400 : ev.deltaY;
    zoomBy(Math.exp(-dy * (ev.ctrlKey ? 0.01 : 0.0018)), ev.clientX, ev.clientY);
  }, { passive: false });
  canvas.addEventListener("dblclick", function (ev) { zoomBy(2, ev.clientX, ev.clientY); });
  ["gesturestart", "gesturechange"].forEach(function (t) { document.addEventListener(t, function (ev) { ev.preventDefault(); }); });
  function zoomBy(f, px, py) {
    var k1 = Math.max(1, Math.min(K_MAX, k * f)), g = k1 / k;
    if (g === 1) return;
    var ll = px != null ? invert(px, py) : null;
    if (ll && g > 1) {   // drift toward the point under the cursor
      var a = 1 - 1 / g;
      rot[0] += wrap(-ll[0] - rot[0]) * a; rot[1] = clampLat(rot[1] + (-ll[1] - rot[1]) * a);
    }
    k = k1; fly = null; lastInteract = Date.now(); setRot();
  }
  $$("[data-zoom]").forEach(function (b) { b.addEventListener("click", function () { zoomBy(b.dataset.zoom === "in" ? 1.8 : 1 / 1.8); }); });
  function hit(x, y) {
    var best = null, bd = 1e9, i, m, d;
    for (i = 0; i < placed.length; i++) {
      m = placed[i]; d = Math.hypot(m.sx - x, m.sy - y);
      if (d <= m.rr + 4 && d < bd) { bd = d; best = m; }
    }
    if (best) return best;
    for (i = 0; i < marks.length; i++) {
      m = marks[i]; if (!m.vis || m.pin) continue;
      d = Math.hypot(m.sx - x, m.sy - y);
      if (d <= 10 && d < bd) { bd = d; best = m; }
    }
    return best;
  }

  // ---------------------------------------------------------------- live counter + deadpan line
  var tick = $("[data-ticker]"), agoEl = $("[data-ago]"), dead = $("[data-deadpan]"), kick = $("[data-kicker]"), kick2 = $("[data-kicker2]");
  var base = +tick.dataset.base, pace = +tick.dataset.pace, updated = new Date(tick.dataset.updated);
  var kickLive = kick.textContent, kick2Live = kick2.textContent;
  function renderTick() {
    if (replay.on) return;
    var now = Date.now();
    tick.textContent = fmt(Math.floor(base + Math.max(0, (now - updated) / 1000) * pace));
    var mins = Math.max(0, Math.round((now - updated) / 60000));
    agoEl.textContent = mins < 1 ? "Live · just updated" : mins < 60 ? "Live · updated " + mins + "m ago" : "Live · updated " + Math.round(mins / 60) + "h ago";
  }
  renderTick(); setInterval(renderTick, 1000);
  var every = +dead.dataset.every, week = +dead.dataset.week, cos = +dead.dataset.cos;
  var latest = events.filter(function (e) { return e.n; })[0];
  var lines = [
    function () { var s = every ? Math.floor(((Date.now() - updated) / 1000) % every) : 0; return "Statistically, someone lost their job " + s + " second" + (s === 1 ? "" : "s") + " ago."; },
    function () { return fmt(week) + " people were laid off this week. " + cos + " companies."; },
    function () { return latest ? latest.c + " cut " + fmt(latest.n) + " jobs " + agoLong(latest.t) + "." : ""; },
    function () { return "At this pace, someone loses their job every " + every + " seconds."; }
  ];
  var li = 0, liSince = Date.now();
  function renderDead() {
    if (replay.on) return;
    if (Date.now() - liSince > 7000 && !reduced) { li = (li + 1) % lines.length; liSince = Date.now(); dead.classList.remove("in"); void dead.offsetWidth; dead.classList.add("in"); }
    var t = lines[li](); if (dead.textContent !== t) dead.textContent = t;
  }
  renderDead(); setInterval(renderDead, 1000);

  // ---------------------------------------------------------------- live feed
  var feed = $("[data-feed]"), list = $("[data-feed-list]");
  var feedPool = events.filter(function (e) { return e.n || e.ps; });
  function pbar(pct, cls) {
    var b = el("span", "pbar" + (pct >= 10 ? " hot" : "") + (cls ? " " + cls : "")), i = el("i");
    i.style.width = Math.min(100, pct / 25 * 100) + "%"; b.appendChild(i);
    b.title = pct + "% of staff (bar scale 0–25%)";
    return b;
  }
  function feedItem(e, now) {
    var item = el("li"), b = el("button", "fi"); b.type = "button"; b.dataset.s = e.s; b.dataset.d = e.d;
    b.appendChild(logoEl(e));
    b.appendChild(el("span", "fi-co", e.c));
    b.appendChild(el("span", "fi-n" + (e.n ? "" : " u"), e.n ? fmt(e.n) : e.ps + " of staff"));
    var meta = el("span", "fi-meta");
    if (e.cc) meta.appendChild(el("span", "fl", flag(e.cc)));
    var age = ((now || Date.now()) - e.t) / DAY;
    meta.appendChild(el("span", age <= 7 ? "fresh" : null, now ? new Date(e.t).toLocaleDateString("en-US", { month: "short", day: "numeric" }) : agoLong(e.t)));
    if (e.n && e.ps) meta.appendChild(el("span", null, "· " + e.ps + " of staff"));
    b.appendChild(meta);
    var p = pctNum(e.ps);
    b.appendChild(p != null ? pbar(p, "fi-bar") : el("span"));
    b.addEventListener("click", function () { select(e, false); });
    b.addEventListener("pointerenter", function () { hover = e.mark || null; });
    b.addEventListener("pointerleave", function () { if (hover === e.mark) hover = null; });
    item.appendChild(b);
    return item;
  }
  function renderFeed() {
    list.textContent = "";
    var frag = document.createDocumentFragment();
    feedPool.slice(0, 40).forEach(function (e, i) {
      var item = feedItem(e);
      if (!reduced && i < 12) { item.className = "enter"; item.firstChild.style.animationDelay = (i * 45) + "ms"; }
      frag.appendChild(item);
    });
    if (!feedPool.length) frag.appendChild(el("li", "empty", "No layoffs tracked yet this year."));
    list.appendChild(frag);
  }
  function pushFeed(e, at) {
    var item = feedItem(e, at);
    if (!reduced) item.className = "enter";
    list.insertBefore(item, list.firstChild);
    while (list.children.length > 40) list.removeChild(list.lastChild);
  }
  function feedUpTo(t) {
    list.textContent = "";
    feedPool.filter(function (e) { return e.t <= t; }).slice(0, 20).forEach(function (e) { list.appendChild(feedItem(e, t)); });
  }
  function syncFeedHover() {
    $$(".fi.is-on", list).forEach(function (b) { b.classList.remove("is-on"); });
    if (hover) { var b = list.querySelector('.fi[data-s="' + hover.e.s + '"][data-d="' + hover.e.d + '"]'); if (b) b.classList.add("is-on"); }
  }
  renderFeed();
  // phone: the feed is a bottom sheet (tap or swipe the handle)
  var sheetBtn = $("[data-sheet]");
  function sheet(open) { feed.classList.toggle("open", open); sheetBtn.setAttribute("aria-label", open ? "Collapse the feed" : "Expand the feed"); }
  sheetBtn.addEventListener("click", function () { sheet(!feed.classList.contains("open")); });
  $(".feed-head", feed).addEventListener("click", function () { if (mobile()) sheet(!feed.classList.contains("open")); });
  var sy0 = null;
  feed.addEventListener("touchstart", function (ev) { if (ev.target.closest(".feed-handle,.feed-head")) sy0 = ev.touches[0].clientY; }, { passive: true });
  feed.addEventListener("touchend", function (ev) {
    if (sy0 == null) return;
    var dy = ev.changedTouches[0].clientY - sy0; sy0 = null;
    if (dy < -30) sheet(true); else if (dy > 30) sheet(false);
  }, { passive: true });

  // Snap to verified numbers when the hourly build publishes new data; new events slide into the feed.
  setInterval(function () {
    fetch("/live.json", { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
      if (!d || d.updated === tick.dataset.updated) return;
      tick.dataset.updated = d.updated; updated = new Date(d.updated); base = d.ytd; pace = d.pace_per_hour / 3600;
      var have = {}; feedPool.slice(0, 60).forEach(function (e) { have[e.s + e.d] = 1; });
      (d.latest || []).slice().reverse().forEach(function (x) {
        if (have[x.s + x.d]) return;
        var e = { s: x.s, c: x.c, d: x.d, n: x.n, ps: x.ps, t: tOf(x.d), l: "Reported", np: 0, src: [] };
        feedPool.unshift(e); if (!replay.on) pushFeed(e);
      });
      renderTick();
    }).catch(function () {});
  }, 5 * 60 * 1000);

  // ---------------------------------------------------------------- pin card
  var LOCK = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>';
  var LINK = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1.5 1.5"/><path d="M14 11a5 5 0 0 0-7.07 0l-3 3a5 5 0 0 0 7.07 7.07l1.5-1.5"/></svg>';
  var STEPS = { Official: 4, Corroborated: 3, Reported: 2, Unverified: 1 };
  function confTag(e) {
    var t = el("span", "tag conf" + (e.l === "Official" ? " official" : "")), m = el("span", "m");
    for (var i = 0; i < 4; i++) m.appendChild(el("i", i < (STEPS[e.l] || 1) ? "on" : ""));
    t.appendChild(m); t.appendChild(document.createTextNode(e.l || "Reported"));
    t.title = "Confidence " + (e.cf != null ? e.cf + "/100 " : "") + "from " + e.np + " independent source" + (e.np === 1 ? "" : "s");
    return t;
  }
  window.lrUI = { logoEl: logoEl, confTag: confTag, pbar: pbar, flag: flag, fmt: fmt, pctNum: pctNum, track: track, LOCK: LOCK };
  function select(e, fromGlobe) {
    if (replay.playing) togglePlay();
    selected = e.mark || { e: e, none: true };
    hover = null;
    if (e.mark) {
      if (replay.on && e.t > replay.cur) exitReplay();
      flyTo(e.mark, fromGlobe ? 600 : 900);
    }
    if (mobile()) { sheet(false); cyOffT = -Math.min(H * 0.2, 150); }
    buildCard(e);
    track("panel");
  }
  function closeCard() { cardEl.hidden = true; selected = null; cyOffT = 0; }
  function buildCard(e) {
    cardEl.textContent = "";
    var x = el("button", "c-x", "×"); x.type = "button"; x.setAttribute("aria-label", "Close"); x.addEventListener("click", closeCard);
    cardEl.appendChild(x);
    var head = el("div", "c-head"); head.appendChild(logoEl(e, true));
    var hd = el("div"); hd.appendChild(el("div", "c-co", e.c));
    var where = e.cc ? flag(e.cc) + " " + e.k : e.k && e.k !== "Unknown" ? e.k : "";
    hd.appendChild(el("div", "c-sub", [where, e.i && e.i !== "Other" ? e.i : ""].filter(Boolean).join(" · ")));
    head.appendChild(hd); cardEl.appendChild(head);
    var big = el("div", "c-big");
    big.appendChild(el("span", "c-n num" + (e.n ? "" : " u"), e.n ? fmt(e.n) : e.ps ? e.ps : "Undisclosed"));
    big.appendChild(el("span", "c-unit", e.n ? "people" : e.ps ? "of staff" : "no number published yet"));
    cardEl.appendChild(big);
    if (e.n && e.lo && e.hi && e.lo !== e.hi) cardEl.appendChild(el("div", "c-range", "Sources say " + fmt(e.lo) + "–" + fmt(e.hi)));
    var p = pctNum(e.ps);
    if (p != null) {
      var pc = el("div", "c-pct"), row = el("div", "row");
      row.appendChild(el("span", null, e.pn || "of staff")); row.appendChild(el("b", null, e.ps));
      pc.appendChild(row); pc.appendChild(pbar(p)); cardEl.appendChild(pc);
    }
    var facts = el("div", "c-facts");
    facts.appendChild(el("span", "tag", new Date(e.t).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) + " · " + agoLong(e.t)));
    facts.appendChild(confTag(e));
    if (e.np) facts.appendChild(el("span", "tag", e.np + " source" + (e.np === 1 ? "" : "s")));
    cardEl.appendChild(facts);
    if (e.src && e.src.length) {
      var ul = el("ul", "c-src");
      e.src.forEach(function (s) {
        var item = el("li"), a = el("a"); a.href = s[1] || "/company/" + e.s + "/";
        if (s[1]) { a.target = "_blank"; a.rel = "noopener nofollow"; }
        a.appendChild(el("span", null, s[0])); a.appendChild(el("span", null, s[1] ? "↗" : "→")); item.appendChild(a); ul.appendChild(item);
      });
      cardEl.appendChild(ul);
    }
    var mine = warnBySlug[e.s] || [];
    if (warn.length) {
      var w = el("button", "c-warn"); w.type = "button"; w.innerHTML = LOCK;
      w.appendChild(el("span", null, mine.length
        ? "Early warning: " + mine.length + " WARN notice" + (mine.length === 1 ? "" : "s") + " for " + e.c + ", not yet effective"
        : "Early warning: " + warn.length + " layoffs already filed by WARN notice, not yet effective"));
      w.addEventListener("click", function () { if (window.lrGate) window.lrGate.open(e, "warn"); });
      cardEl.appendChild(w);
    }
    var act = el("div", "c-act");
    var dive = el("button", "btn primary", "Dive deeper"); dive.type = "button";
    dive.addEventListener("click", function () { if (window.lrGate) window.lrGate.open(e, "company"); });
    var url = location.origin + "/company/" + e.s + "/";
    var sh = el("button", "btn", "Share"); sh.type = "button";
    sh.addEventListener("click", function () {
      var text = e.c + (e.n ? " cut " + fmt(e.n) + " jobs" : " is cutting jobs") + (e.ps ? " (" + e.ps + " of staff)" : "") + ". Sourced:";
      if (navigator.share && mobile()) navigator.share({ title: e.c + " layoffs", text: text, url: url }).catch(function () {});
      else window.open("https://x.com/intent/post?text=" + encodeURIComponent(text) + "&url=" + encodeURIComponent(url), "_blank", "noopener");
    });
    var cpy = el("button", "btn"); cpy.type = "button"; cpy.setAttribute("aria-label", "Copy link"); cpy.dataset.copy = url; cpy.innerHTML = LINK;
    act.appendChild(dive); act.appendChild(sh); act.appendChild(cpy);
    cardEl.appendChild(act);
    var tl = el("a", "c-link", "Timeline, every source and the share card →"); tl.href = "/company/" + e.s + "/";
    cardEl.appendChild(tl);
    cardEl.hidden = false;
    placeCard(true);
  }
  function placeCard(force) {
    if (cardEl.hidden) return;
    if (mobile()) { cardEl.style.left = cardEl.style.top = ""; return; }
    var m = selected, cw = cardEl.offsetWidth, ch = cardEl.offsetHeight;
    var maxX = $("[data-feed]").getBoundingClientRect().left - cw - 16, x, y;
    if (m && !m.none && m.vis) {
      x = m.sx + m.rr + 18; if (x > maxX) x = m.sx - m.rr - 18 - cw;
      y = m.sy - ch * 0.42;
    } else if (force) { x = cx + 30; y = cy - ch / 2; }
    else return;
    x = Math.max(16, Math.min(maxX, x)); y = Math.max(16, Math.min(H - ch - 84, y));
    cardEl.style.left = Math.round(x) + "px"; cardEl.style.top = Math.round(y) + "px";
  }
  document.addEventListener("keydown", function (ev) {
    if (document.querySelector("[data-dive]:not([hidden])")) return;
    if (ev.key === "Escape") { if (!cardEl.hidden) closeCard(); else if (feed.classList.contains("open")) sheet(false); }
    if (ev.key === " " && ev.target === document.body) { ev.preventDefault(); togglePlay(); }
  });

  // ---------------------------------------------------------------- Replay: the year on the globe in 20 seconds
  var rpEl = $("[data-replay]"), trackEl = $("[data-track]"), headEl = $("[data-head]"), spark = $("[data-spark]"), playBtn = $("[data-play]");
  var rpTitle = $("[data-rp-title]"), rpDate = $("[data-rp-date]"), rpTitle0 = rpTitle.textContent, rpDate0 = rpDate.textContent;
  var byTime = events.filter(function (e) { return e.n; }).sort(function (a, b) { return a.t - b.t; });
  var cum = [], acc = 0; byTime.forEach(function (e, i) { acc += e.n; cum[i] = acc; });
  var marksByTime = marks.slice().sort(function (a, b) { return a.e.t - b.e.t; });
  function upto(t) { var lo = 0, hi = byTime.length; while (lo < hi) { var mid = (lo + hi) >> 1; if (byTime[mid].t <= t) lo = mid + 1; else hi = mid; } return lo; }
  function biggestTo(t) { var b = null, n = upto(t); for (var i = 0; i < n; i++) if (!b || byTime[i].n > b.n) b = byTime[i]; return b; }
  function frac() { return replay.on ? (replay.cur - replay.t0) / (replay.t1 - replay.t0) : 1; }
  function drawSpark() {
    var r = trackEl.getBoundingClientRect(); if (!r.width) return;
    if (spark.width !== Math.round(r.width * dpr)) { spark.width = Math.round(r.width * dpr); spark.height = Math.round(r.height * dpr); }
    var g = spark.getContext("2d"); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, r.width, r.height);
    var w = WK.w, n = w.length, max = Math.max.apply(null, w.concat([1])), f = frac(), bw = r.width / n;
    for (var i = 0; i < n; i++) {
      var h = Math.max(1.5, (r.height - 8) * Math.sqrt(w[i] / max));
      g.fillStyle = (i + 0.5) / n <= f ? (i >= n - 4 ? "rgba(255,77,74,0.9)" : "rgba(214,220,232,0.55)") : "rgba(214,220,232,0.14)";
      g.fillRect(i * bw + bw * 0.18, r.height - 4 - h, Math.max(1, bw * 0.64), h);
    }
    headEl.style.left = (f * 100).toFixed(2) + "%";
    trackEl.setAttribute("aria-valuenow", Math.round(f * 100));
  }
  function setLabels() {
    var d = new Date(Math.min(replay.cur, replay.t1)), n = upto(replay.cur);
    rpTitle.textContent = d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    rpDate.textContent = replay.playing ? "replaying " + WK.y : "paused · press play";
    tick.textContent = fmt(n ? cum[n - 1] : 0);
    kick.textContent = "people laid off by " + d.toLocaleDateString("en-US", { month: "long", day: "numeric" }) + ".";
    kick2.textContent = "";
    agoEl.textContent = "Replay · " + WK.y;
    var b = biggestTo(replay.cur);
    dead.textContent = b ? "Biggest so far: " + b.c + ", " + fmt(b.n) + " people." : "January 1. Nothing yet.";
  }
  function enterReplay(from) {
    replay.on = true; replay.cur = replay.prev = from; camera = true; replay.target = null;
    marks.forEach(function (m) { m.born = 0; });
    if (selected) closeCard();
    feedUpTo(from);
  }
  function exitReplay() {
    replay.on = false; replay.playing = false; rpEl.classList.remove("playing");
    rpTitle.textContent = rpTitle0; rpDate.textContent = rpDate0; kick.textContent = kickLive; kick2.textContent = kick2Live;
    playBtn.setAttribute("aria-label", "Replay " + WK.y);
    marks.forEach(function (m) { m.born = 0; });
    renderFeed(); renderTick(); renderDead(); drawSpark();
  }
  function togglePlay() {
    if (replay.playing) { replay.playing = false; rpEl.classList.remove("playing"); playBtn.setAttribute("aria-label", "Play"); setLabels(); return; }
    if (!replay.on || replay.cur >= replay.t1 - DAY) enterReplay(replay.t0);
    replay.playing = true; replay.prev = replay.cur; rpEl.classList.add("playing"); camera = true;
    playBtn.setAttribute("aria-label", "Pause");
    k = Math.min(k, 1.4); vel = [0, 0]; fly = null;
    setLabels();
  }
  var feedGate = 0, lastLbl = 0;
  function advanceReplay(t, dt) {
    replay.cur = Math.min(replay.t1, replay.cur + dt * (replay.t1 - replay.t0) / replay.dur);
    var best = null, i;
    for (i = 0; i < marksByTime.length; i++) {
      var m = marksByTime[i];
      if (m.e.t <= replay.prev) continue;
      if (m.e.t > replay.cur) break;
      m.born = t;
      if (!best || (m.e.n || 0) > (best.e.n || 0)) best = m;
    }
    if (best && (best.e.n || 0) >= 400) replay.target = [wrap(-best.lon), clampLat(-best.lat * 0.75)];
    // the notable events of the day slide into the feed, a few per second at most
    for (i = feedPool.length - 1; i >= 0; i--) {
      var e = feedPool[i];
      if (e.t > replay.prev && e.t <= replay.cur && (e.n || 0) >= 250 && t - feedGate > 240) { pushFeed(e, replay.cur); feedGate = t; }
    }
    replay.prev = replay.cur;
    if (t - lastLbl > 60) { setLabels(); drawSpark(); lastLbl = t; }
    if (replay.cur >= replay.t1) {
      replay.playing = false; rpEl.classList.remove("playing"); setLabels(); drawSpark();
      setTimeout(function () { if (replay.on && !replay.playing) exitReplay(); }, 2600);
    }
  }
  playBtn.addEventListener("click", togglePlay);
  function scrubTo(clientX) {
    var r = trackEl.getBoundingClientRect(), f = Math.max(0, Math.min(1, (clientX - r.left) / r.width));
    var t = replay.t0 + f * (replay.t1 - replay.t0);
    if (!replay.on) enterReplay(t);
    replay.cur = replay.prev = t; replay.playing = false; rpEl.classList.remove("playing");
    marks.forEach(function (m) { m.born = 0; });
    feedUpTo(t); setLabels(); drawSpark();
  }
  var scrubbing = false;
  trackEl.addEventListener("pointerdown", function (ev) { scrubbing = true; try { trackEl.setPointerCapture(ev.pointerId); } catch (_) {} scrubTo(ev.clientX); });
  trackEl.addEventListener("pointermove", function (ev) { if (scrubbing) scrubTo(ev.clientX); });
  trackEl.addEventListener("pointerup", function () { scrubbing = false; if (replay.cur >= replay.t1 - DAY / 2) exitReplay(); });
  trackEl.addEventListener("keydown", function (ev) {
    if (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight") return;
    ev.preventDefault();
    var r = trackEl.getBoundingClientRect(), f = Math.max(0, Math.min(1, frac() + (ev.key === "ArrowRight" ? 1 : -1) / 52));
    scrubTo(r.left + f * r.width);
    if (f >= 1) exitReplay();
  });
  if (/[?&]replay\b/.test(location.search)) setTimeout(togglePlay, 1200);   // /?replay autoplays, for screen recordings

  // ---------------------------------------------------------------- boot
  window.addEventListener("resize", layout);
  layout();
  requestAnimationFrame(frame);
  fetch("/static/vendor/countries-110m.json").then(function (r) { return r.json(); }).then(buildLand).catch(function () {});
})();
