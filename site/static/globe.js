/* Front-page stage: live counter, deadpan line, "right now" feed, globe/map of events. */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var fmt = function (n) { return n == null ? "–" : Math.round(n).toLocaleString("en-US"); };
  var reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var dataEl = $("#events");
  if (!dataEl) return;
  var events = JSON.parse(dataEl.textContent);

  // ---------------------------------------------------------------- live counter
  var tick = $("[data-ticker]"), agoEl = $("[data-ago]"), dead = $("[data-deadpan]");
  var base = +tick.dataset.base, pace = +tick.dataset.pace, updated = new Date(tick.dataset.updated);
  function estimate(now) { return base + Math.max(0, (now - updated) / 1000) * pace; }
  function renderTick() {
    var now = Date.now();
    tick.textContent = fmt(Math.floor(estimate(now)));
    var mins = Math.max(0, Math.round((now - updated) / 60000));
    agoEl.textContent = mins < 1 ? "updated just now" : mins < 60 ? "updated " + mins + " min ago" : "updated " + Math.round(mins / 60) + " h ago";
  }
  renderTick();
  setInterval(renderTick, 1000);

  // Deadpan lines rotate. The first one is computed from the same pace as the counter.
  var every = +dead.dataset.every, week = +dead.dataset.week, cos = +dead.dataset.cos;
  var latest = events.filter(function (e) { return e.n; })[0];
  var lines = [
    function () {
      var s = every ? Math.floor(((Date.now() - updated) / 1000) % every) : 0;
      return "Statistically, someone lost their job " + s + " second" + (s === 1 ? "" : "s") + " ago.";
    },
    function () { return fmt(week) + " people were laid off this week. " + cos + " companies."; },
    function () { return latest ? latest.c + " cut " + fmt(latest.n) + " jobs " + ago(latest.d) + "." : ""; },
    function () { return "At this pace, someone loses their job every " + every + " seconds."; }
  ];
  var li = 0, liSince = Date.now();
  function renderDead() {
    if (Date.now() - liSince > 7000 && !reduced) { li = (li + 1) % lines.length; liSince = Date.now(); dead.classList.remove("in"); void dead.offsetWidth; dead.classList.add("in"); }
    var t = lines[li]();
    if (dead.textContent !== t) dead.textContent = t;
  }
  renderDead();
  setInterval(renderDead, 1000);

  // Snap to verified numbers when the hourly build publishes new data.
  function poll() {
    fetch("/live.json", { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
      if (!d || d.updated === tick.dataset.updated) return;
      tick.dataset.updated = d.updated; updated = new Date(d.updated); base = d.ytd; pace = d.pace_per_hour / 3600;
      renderTick();
    }).catch(function () {});
  }
  setInterval(poll, 5 * 60 * 1000);

  // ---------------------------------------------------------------- right now feed
  var rn = $("[data-rightnow]"), pool = events.filter(function (e) { return e.n || e.ps; }).slice(0, 14), rnI = 4;
  function ago(d) {
    var days = Math.round((Date.now() - new Date(d + "T12:00:00")) / 864e5);
    return days <= 0 ? "today" : days === 1 ? "yesterday" : days + " days ago";
  }
  function rnItem(e) {
    var li = document.createElement("li"), a = document.createElement("a"), b = document.createElement("b"),
      sp = document.createElement("span"), t = document.createElement("time");
    a.href = "/company/" + e.s + "/"; b.textContent = e.c;
    sp.textContent = e.n ? fmt(e.n) + " jobs" + (e.ps ? " · " + e.ps + " of staff" : "") : e.ps + " of staff";
    t.textContent = ago(e.d);
    a.appendChild(b); a.appendChild(sp); a.appendChild(t); li.appendChild(a); return li;
  }
  if (rn && pool.length > 4 && !reduced) {
    setInterval(function () {
      if (document.hidden) return;
      var e = pool[rnI % pool.length]; rnI++;
      var item = rnItem(e); item.className = "enter";
      rn.insertBefore(item, rn.firstChild);
      while (rn.children.length > 4) rn.removeChild(rn.lastChild);
    }, 4500);
  }

  // ---------------------------------------------------------------- globe / map
  // Both views zoom (wheel, pinch, +/− buttons) and pan (drag: rotate the globe, move the map).
  // Dots keep a near-constant screen size, so zooming spreads them apart; labels appear as room allows.
  var box = $("[data-globe-box]"), canvas = $("[data-globe]");
  if (!box || !window.d3 || !window.topojson) return;
  var ctx = canvas.getContext("2d"), pin = $("[data-pin]");
  var warn = [];
  try { warn = JSON.parse(($("#warn") || {}).textContent || "[]"); } catch (_) {}
  var dots = events.filter(function (e) { return e.la != null; }).map(function (e) {
    var age = (Date.now() - new Date(e.d + "T12:00:00")) / 864e5;
    return { e: e, ll: [e.lo2, e.la], age: age, r: e.n ? Math.min(26, 2.2 + Math.sqrt(e.n) * 0.16) : 2.6, lw: 0 };
  }).sort(function (a, b) { return b.r - a.r; });
  var view = "globe", rot = [40, -24], land, borders, w = 0, h = 0, dpr = Math.min(2, window.devicePixelRatio || 1);
  var ortho = d3.geoOrthographic().clipAngle(90).precision(0.6), flat = d3.geoNaturalEarth1();
  var grat = d3.geoGraticule10(), visible = true, lastInteract = 0, selected = null;
  var K_MAX = { globe: 10, map: 14 }, k = 1, gScale = 1, fScale = 1, fT0 = [0, 0], fT = [0, 0];
  var zoomReset = $("[data-zoom=reset]");
  var LABEL_FONT = "500 11px Geist, system-ui, sans-serif";
  var C = { ocean: "#111214", land: "#232428", border: "#34363b", grid: "rgba(255,255,255,0.045)", rim: "rgba(255,255,255,0.08)",
    fresh: "#ff6b5e", old: "rgba(230,103,103,0.42)", mid: "rgba(230,103,103,0.75)", ring: "rgba(255,107,94,",
    edge: "rgba(10,10,11,0.7)", label: "#e9e8e4", halo: "rgba(10,10,11,0.85)" };

  function resize(force) {
    var r = box.getBoundingClientRect();
    if (!force && Math.abs(r.width - w) < 1 && Math.abs(r.height - h) < 1) return;
    w = r.width; h = r.height;
    canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    gScale = Math.min(w, h) / 2 - 6;
    ortho.translate([w / 2, h / 2]);
    flat.scale(1).translate([0, 0]).fitExtent([[6, 6], [w - 6, h - 6]], { type: "Sphere" });
    fScale = flat.scale(); fT0 = flat.translate().slice(); fT = fT0.slice(); k = 1;
    apply();
  }
  function apply() {
    ortho.scale(gScale * k);
    flat.scale(fScale * k).translate(fT);
    if (zoomReset) zoomReset.hidden = k < 1.02 && Math.abs(fT[0] - fT0[0]) + Math.abs(fT[1] - fT0[1]) < 1;
  }
  // Keep the flat map covering the centre of the box so it can't be dragged away.
  function clampMap() {
    var mw = (fT0[0] - 6) * 2 * k, mh = (fT0[1] - 6) * 2 * k;
    var sx = Math.max(0, (mw - w) / 2) + w * 0.25, sy = Math.max(0, (mh - h) / 2) + h * 0.25;
    fT[0] = Math.max(w / 2 - sx, Math.min(w / 2 + sx, fT[0]));
    fT[1] = Math.max(h / 2 - sy, Math.min(h / 2 + sy, fT[1]));
  }
  // Zoom by factor f around screen point (px, py). The globe zooms around its centre.
  function zoomBy(f, px, py) {
    var k1 = Math.max(1, Math.min(K_MAX[view], k * f)), g = k1 / k;
    if (g === 1) return;
    if (view === "map") {
      if (px == null) { px = w / 2; py = h / 2; }
      fT = [px - (px - fT[0]) * g, py - (py - fT[1]) * g];
      k = k1;
      if (k <= 1.001) fT = fT0.slice();
      clampMap();
    } else {
      k = k1;
    }
    apply(); lastInteract = Date.now();
  }
  function proj() { return view === "globe" ? ortho.rotate(rot) : flat; }
  function onFront(ll) { return view !== "globe" || d3.geoDistance(ll, [-rot[0], -rot[1]]) < Math.PI / 2 - 0.02; }
  function radius(d) {
    if (k <= 1.01) return d.r;
    return Math.max(3, d.r * Math.min(1.5, 1 + 0.2 * Math.log2(k)));
  }
  function minLabelN() { return k >= 6 ? 0 : k >= 3.5 ? 300 : k >= 2 ? 1500 : Infinity; }

  function draw(t) {
    var p = proj(), path = d3.geoPath(p, ctx);
    ctx.clearRect(0, 0, w, h);
    ctx.beginPath(); path({ type: "Sphere" }); ctx.fillStyle = C.ocean; ctx.fill();
    ctx.beginPath(); path(grat); ctx.strokeStyle = C.grid; ctx.lineWidth = 1; ctx.stroke();
    if (land) {
      ctx.beginPath(); path(land); ctx.fillStyle = C.land; ctx.fill();
      ctx.beginPath(); path(borders); ctx.strokeStyle = C.border; ctx.lineWidth = 0.6; ctx.stroke();
    }
    ctx.beginPath(); path({ type: "Sphere" }); ctx.strokeStyle = C.rim; ctx.lineWidth = 1; ctx.stroke();
    var phase = (t % 2400) / 2400, zoomed = k > 1.4;
    for (var i = 0; i < dots.length; i++) {
      var d = dots[i];
      if (!onFront(d.ll)) { d.xy = null; continue; }
      var xy = p(d.ll); d.xy = xy;
      if (!xy || xy[0] < -40 || xy[1] < -40 || xy[0] > w + 40 || xy[1] > h + 40) { d.xy = null; continue; }
      var fresh = d.age <= 7, r = d.rr = radius(d);
      if (fresh && !reduced) {
        var rr = r + 4 + phase * 22;
        ctx.beginPath(); ctx.arc(xy[0], xy[1], rr, 0, 6.283);
        ctx.strokeStyle = C.ring + (0.55 * (1 - phase)).toFixed(3) + ")"; ctx.lineWidth = 1.5; ctx.stroke();
      }
      ctx.beginPath(); ctx.arc(xy[0], xy[1], r, 0, 6.283);
      ctx.fillStyle = fresh ? C.fresh : d.age <= 30 ? C.mid : C.old; ctx.fill();
      if (zoomed) { ctx.lineWidth = 1; ctx.strokeStyle = C.edge; ctx.stroke(); }
      if (d === selected) { ctx.lineWidth = 2; ctx.strokeStyle = "#f0efec"; ctx.stroke(); }
    }
    drawLabels();
  }
  // Greedy, collision-free labels: biggest events first, selected dot always.
  function drawLabels() {
    var minN = minLabelN();
    if (minN === Infinity && !selected) return;
    ctx.font = LABEL_FONT; ctx.textBaseline = "middle"; ctx.lineJoin = "round";
    var boxes = [], count = 0;
    var cand = selected && selected.xy ? [selected] : [];
    for (var i = 0; i < dots.length && cand.length < 400; i++) {
      var d = dots[i];
      if (d.xy && d !== selected && (d.e.n || 0) >= minN) cand.push(d);
    }
    for (var j = 0; j < cand.length && count < 70; j++) {
      var c = cand[j];
      if (!c.lw) c.lw = ctx.measureText(c.e.c).width;
      var x = c.xy[0] + c.rr + 4, y = c.xy[1], bx = [x - 2, y - 8, x + c.lw + 2, y + 8];
      if (bx[2] > w - 2) { x = c.xy[0] - c.rr - 4 - c.lw; bx = [x - 2, y - 8, x + c.lw + 2, y + 8]; }
      if (bx[0] < 2 || bx[1] < 2 || bx[3] > h - 2) continue;
      var clash = false;
      for (var b = 0; b < boxes.length; b++) {
        var o = boxes[b];
        if (bx[0] < o[2] && bx[2] > o[0] && bx[1] < o[3] && bx[3] > o[1]) { clash = true; break; }
      }
      if (clash && c !== selected) continue;
      boxes.push(bx); count++;
      ctx.lineWidth = 3; ctx.strokeStyle = C.halo; ctx.strokeText(c.e.c, x, y);
      ctx.fillStyle = C.label; ctx.fillText(c.e.c, x, y);
    }
  }
  function frame(t) {
    if (visible && !document.hidden) {
      if (view === "globe" && !pointers.size && !reduced && k < 1.05 && Date.now() - lastInteract > 4000 && !selected) rot[0] += 0.06;
      draw(t);
    }
    requestAnimationFrame(frame);
  }

  function hit(x, y) {
    var best = null, bd = 1e9;
    dots.forEach(function (d) {
      if (!d.xy) return;
      var dx = d.xy[0] - x, dy = d.xy[1] - y, dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < Math.max((d.rr || d.r) + 4, 12) && dist < bd) { bd = dist; best = d; }
    });
    return best;
  }

  // ---------------------------------------------------------------- panel (opens on the first screen)
  var LOCK = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>';
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function track(t) {
    try { fetch("/api/event", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ t: t }), keepalive: true }).catch(function () {}); } catch (_) {}
  }
  function closePin() { pin.hidden = true; selected = null; }
  function showPin(d) {
    selected = d; var e = d.e;
    pin.textContent = "";
    var close = el("button", "pin-x", "×"); close.type = "button"; close.setAttribute("aria-label", "Close");
    close.addEventListener("click", closePin);
    pin.appendChild(close);
    pin.appendChild(el("div", "pin-co", e.c));
    pin.appendChild(el("div", "pin-n", e.n ? fmt(e.n) : e.pl ? fmt(e.pl) : e.ps ? e.ps : "Undisclosed"));
    var sub = e.pl ? "announced plan" + (e.hz && e.hz !== "multi-year" ? ", by " + e.hz : ", several years") + " · not counted" :
      e.n && e.lo && e.hi && e.lo !== e.hi ? "people · sources say " + fmt(e.lo) + "–" + fmt(e.hi) : e.n ? "people" : e.ps ? "of staff" : "no number published yet";
    pin.appendChild(el("div", "pin-sub", sub));
    if (e.n && e.ps) pin.appendChild(el("div", "pin-sub", e.ps + " " + (e.pn || "of staff")));
    var dt = new Date(e.d + "T12:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    var facts = el("div", "pin-facts");
    facts.appendChild(el("span", null, dt));
    var cf = el("span", "pin-conf"); cf.textContent = e.l + (e.cf != null ? " · " + e.cf + "/100" : "");
    cf.title = "Confidence from " + e.np + " independent source" + (e.np === 1 ? "" : "s");
    facts.appendChild(cf);
    facts.appendChild(el("span", null, e.np + " source" + (e.np === 1 ? "" : "s")));
    pin.appendChild(facts);
    var ul = el("ul", "pin-src");
    (e.src || []).forEach(function (s) {
      var li = el("li"), a = el("a", null, s[0]); a.href = s[1]; a.target = "_blank"; a.rel = "noopener nofollow";
      li.appendChild(a); ul.appendChild(li);
    });
    pin.appendChild(ul);
    // Early-warning teaser: WARN notices filed but not yet effective.
    var mine = warn.filter(function (x) { return x.s === e.s; });
    if (warn.length) {
      var ew = el("button", "pin-warn"); ew.type = "button";
      ew.innerHTML = LOCK;
      ew.appendChild(document.createTextNode(mine.length
        ? " Early warning: " + mine.length + " WARN notice" + (mine.length === 1 ? "" : "s") + " for " + e.c + ", not yet effective"
        : " Early warning: " + warn.length + " layoffs already filed by WARN notice, not yet effective"));
      ew.addEventListener("click", function () { if (window.lrGate) window.lrGate.open(e, "warn"); });
      pin.appendChild(ew);
    }
    var row = el("div", "pin-actions");
    var dive = el("button", "btn primary pin-dive", "Dive deeper"); dive.type = "button";
    dive.addEventListener("click", function () { if (window.lrGate) window.lrGate.open(e, "company"); });
    var more = el("a", "pin-more", "Timeline →"); more.href = "/company/" + e.s + "/";
    row.appendChild(dive); row.appendChild(more); pin.appendChild(row);
    pin.hidden = false;
    track("panel");
    if (matchMedia("(max-width: 720px)").matches) { pin.style.left = pin.style.top = ""; return; }
    var x = d.xy[0], y = d.xy[1], pw = pin.offsetWidth, ph = pin.offsetHeight;
    pin.style.left = Math.max(8, Math.min(w - pw - 8, x + 14)) + "px";
    pin.style.top = Math.max(8, Math.min(h - ph - 8, y - ph / 2)) + "px";
  }

  // ---------------------------------------------------------------- pointer input: drag, pinch, tap
  var pointers = new Map(), gesture = null;
  function startDrag() {
    var p = pointers.values().next().value;
    gesture = { mode: "drag", x: p.x, y: p.y, rot: rot.slice(), fT: fT.slice(), moved: gesture ? gesture.moved : false };
  }
  function startPinch() {
    var it = pointers.values(), a = it.next().value, b = it.next().value;
    gesture = { mode: "pinch", dist: Math.hypot(a.x - b.x, a.y - b.y) || 1, k: k, mx: (a.x + b.x) / 2, my: (a.y + b.y) / 2,
      rot: rot.slice(), fT: fT.slice(), moved: true };
  }
  function local(ev) { var b = canvas.getBoundingClientRect(); return { x: ev.clientX - b.left, y: ev.clientY - b.top }; }
  canvas.addEventListener("pointerdown", function (ev) {
    lastInteract = Date.now();
    pointers.set(ev.pointerId, local(ev));
    try { canvas.setPointerCapture(ev.pointerId); } catch (_) {}
    if (pointers.size === 1) { gesture = null; startDrag(); } else if (pointers.size === 2) startPinch();
  });
  canvas.addEventListener("pointermove", function (ev) {
    var p = local(ev);
    if (!pointers.has(ev.pointerId)) {
      canvas.style.cursor = hit(p.x, p.y) ? "pointer" : "grab";
      return;
    }
    pointers.set(ev.pointerId, p);
    lastInteract = Date.now();
    if (gesture && gesture.mode === "pinch" && pointers.size >= 2) {
      var it = pointers.values(), a = it.next().value, b = it.next().value;
      var mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2, k1 = gesture.k * Math.hypot(a.x - b.x, a.y - b.y) / gesture.dist;
      k1 = Math.max(1, Math.min(K_MAX[view], k1));
      if (view === "map") {
        var g = k1 / gesture.k;
        fT = [mx - (gesture.mx - gesture.fT[0]) * g, my - (gesture.my - gesture.fT[1]) * g];
        k = k1; if (k <= 1.001) fT = fT0.slice(); clampMap();
      } else {
        k = k1;
        rot = [gesture.rot[0] + (mx - gesture.mx) * 0.35 / k, Math.max(-80, Math.min(80, gesture.rot[1] - (my - gesture.my) * 0.35 / k))];
      }
      apply();
    } else if (gesture && gesture.mode === "drag") {
      var dx = p.x - gesture.x, dy = p.y - gesture.y;
      if (Math.abs(dx) + Math.abs(dy) > 4) gesture.moved = true;
      if (!gesture.moved) return;
      if (view === "globe") rot = [gesture.rot[0] + dx * 0.35 / k, Math.max(-80, Math.min(80, gesture.rot[1] - dy * 0.35 / k))];
      else { fT = [gesture.fT[0] + dx, gesture.fT[1] + dy]; clampMap(); apply(); }
    }
  });
  function endPointer(ev) {
    if (!pointers.has(ev.pointerId)) return;
    var p = pointers.get(ev.pointerId), wasTap = gesture && gesture.mode === "drag" && !gesture.moved && ev.type === "pointerup";
    pointers.delete(ev.pointerId);
    lastInteract = Date.now();
    if (pointers.size === 1) { startDrag(); gesture.moved = true; return; } // pinch -> drag without a jump
    if (pointers.size) return;
    gesture = null;
    if (!wasTap) return;
    var d = hit(p.x, p.y);
    if (d) showPin(d); else closePin();
  }
  canvas.addEventListener("pointerup", endPointer);
  canvas.addEventListener("pointercancel", endPointer);
  canvas.addEventListener("wheel", function (ev) {
    ev.preventDefault();
    var dy = ev.deltaMode === 1 ? ev.deltaY * 33 : ev.deltaMode === 2 ? ev.deltaY * 400 : ev.deltaY;
    var p = local(ev);
    zoomBy(Math.exp(-dy * (ev.ctrlKey ? 0.01 : 0.0018)), p.x, p.y);
  }, { passive: false });
  canvas.addEventListener("dblclick", function (ev) { var p = local(ev); zoomBy(2, p.x, p.y); });
  // iOS Safari: stop the page from zooming while pinching the map.
  ["gesturestart", "gesturechange"].forEach(function (t) { canvas.addEventListener(t, function (ev) { ev.preventDefault(); }); });
  $$("[data-zoom]").forEach(function (b) {
    b.addEventListener("click", function () {
      var z = b.dataset.zoom;
      if (z === "reset") { k = 1; fT = fT0.slice(); apply(); }
      else zoomBy(z === "in" ? 1.8 : 1 / 1.8);
    });
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape" && !document.querySelector("[data-dive]:not([hidden])")) closePin();
  });

  $$("[data-view]").forEach(function (b) {
    b.addEventListener("click", function () {
      view = b.dataset.view; closePin();
      box.classList.toggle("is-map", view === "map");
      $$("[data-view]").forEach(function (x) { x.setAttribute("aria-pressed", x === b); });
      resize(true);
    });
  });
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (en) { visible = en[0].isIntersecting; }).observe(box);
  }
  window.addEventListener("resize", function () { resize(false); });
  resize(true);
  draw(0);
  fetch("/static/vendor/countries-110m.json").then(function (r) { return r.json(); }).then(function (topo) {
    land = topojson.feature(topo, topo.objects.land);
    borders = topojson.mesh(topo, topo.objects.countries, function (a, b) { return a !== b; });
    draw(0);
    requestAnimationFrame(frame);
  });
})();
