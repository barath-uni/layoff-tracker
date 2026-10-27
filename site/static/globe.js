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
  var box = $("[data-globe-box]"), canvas = $("[data-globe]");
  if (!box || !window.d3 || !window.topojson) return;
  var ctx = canvas.getContext("2d"), pin = $("[data-pin]");
  var dots = events.filter(function (e) { return e.la != null; }).map(function (e) {
    var age = (Date.now() - new Date(e.d + "T12:00:00")) / 864e5;
    return { e: e, ll: [e.lo2, e.la], age: age, r: e.n ? Math.min(26, 2.2 + Math.sqrt(e.n) * 0.16) : 2.6 };
  }).sort(function (a, b) { return b.r - a.r; });
  var view = "globe", rot = [40, -24], land, borders, w = 0, h = 0, dpr = Math.min(2, window.devicePixelRatio || 1);
  var ortho = d3.geoOrthographic().clipAngle(90).precision(0.6), flat = d3.geoNaturalEarth1();
  var grat = d3.geoGraticule10(), visible = true, dragging = null, lastInteract = 0, selected = null;
  var C = { ocean: "#111214", land: "#232428", border: "#34363b", grid: "rgba(255,255,255,0.045)", rim: "rgba(255,255,255,0.08)",
    fresh: "#ff6b5e", old: "rgba(230,103,103,0.42)", mid: "rgba(230,103,103,0.75)", ring: "rgba(255,107,94," };

  function resize() {
    var r = box.getBoundingClientRect(); w = r.width; h = r.height;
    canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ortho.translate([w / 2, h / 2]).scale(Math.min(w, h) / 2 - 6);
    flat.fitExtent([[6, 6], [w - 6, h - 6]], { type: "Sphere" });
  }
  function proj() { return view === "globe" ? ortho.rotate(rot) : flat; }
  function onFront(ll) { return view !== "globe" || d3.geoDistance(ll, [-rot[0], -rot[1]]) < Math.PI / 2 - 0.02; }

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
    var phase = (t % 2400) / 2400;
    for (var i = 0; i < dots.length; i++) {
      var d = dots[i];
      if (!onFront(d.ll)) { d.xy = null; continue; }
      var xy = p(d.ll); d.xy = xy;
      if (!xy) continue;
      var fresh = d.age <= 7;
      if (fresh && !reduced) {
        var rr = d.r + 4 + phase * 22;
        ctx.beginPath(); ctx.arc(xy[0], xy[1], rr, 0, 6.283);
        ctx.strokeStyle = C.ring + (0.55 * (1 - phase)).toFixed(3) + ")"; ctx.lineWidth = 1.5; ctx.stroke();
      }
      ctx.beginPath(); ctx.arc(xy[0], xy[1], d.r, 0, 6.283);
      ctx.fillStyle = fresh ? C.fresh : d.age <= 30 ? C.mid : C.old; ctx.fill();
      if (d === selected) { ctx.lineWidth = 2; ctx.strokeStyle = "#f0efec"; ctx.stroke(); }
    }
  }
  function frame(t) {
    if (visible && !document.hidden) {
      if (view === "globe" && !dragging && !reduced && Date.now() - lastInteract > 4000 && !selected) rot[0] += 0.06;
      draw(t);
    }
    requestAnimationFrame(frame);
  }

  function hit(x, y) {
    var best = null, bd = 1e9;
    dots.forEach(function (d) {
      if (!d.xy) return;
      var dx = d.xy[0] - x, dy = d.xy[1] - y, dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < Math.max(d.r + 4, 12) && dist < bd) { bd = dist; best = d; }
    });
    return best;
  }
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function showPin(d) {
    selected = d; var e = d.e;
    pin.textContent = "";
    var close = el("button", "pin-x", "×"); close.type = "button"; close.setAttribute("aria-label", "Close");
    close.addEventListener("click", function () { pin.hidden = true; selected = null; });
    pin.appendChild(close);
    pin.appendChild(el("div", "pin-co", e.c));
    pin.appendChild(el("div", "pin-n", e.n ? fmt(e.n) : e.ps ? e.ps : "Undisclosed"));
    var sub = e.n && e.lo && e.hi && e.lo !== e.hi ? "sources say " + fmt(e.lo) + "–" + fmt(e.hi) : e.n ? "people" : e.ps ? "of staff" : "no number published yet";
    pin.appendChild(el("div", "pin-sub", sub));
    if (e.n && e.ps) pin.appendChild(el("div", "pin-sub", e.ps + " " + (e.pn || "of staff")));
    var dt = new Date(e.d + "T12:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    pin.appendChild(el("div", "pin-meta", dt + " · " + e.l + " · " + e.np + " source" + (e.np === 1 ? "" : "s")));
    var ul = el("ul", "pin-src");
    (e.src || []).forEach(function (s) {
      var li = el("li"), a = el("a", null, s[0]); a.href = s[1]; a.target = "_blank"; a.rel = "noopener nofollow";
      li.appendChild(a); ul.appendChild(li);
    });
    pin.appendChild(ul);
    var more = el("a", "pin-more", "Full timeline and sources →"); more.href = "/company/" + e.s + "/";
    pin.appendChild(more);
    pin.hidden = false;
    var x = d.xy[0], y = d.xy[1], pw = pin.offsetWidth, ph = pin.offsetHeight;
    pin.style.left = Math.max(8, Math.min(w - pw - 8, x + 14)) + "px";
    pin.style.top = Math.max(8, Math.min(h - ph - 8, y - ph / 2)) + "px";
  }

  canvas.addEventListener("pointerdown", function (ev) {
    lastInteract = Date.now();
    dragging = { x: ev.clientX, y: ev.clientY, r: rot.slice(), moved: false };
    if (view === "globe") canvas.setPointerCapture(ev.pointerId);
  });
  canvas.addEventListener("pointermove", function (ev) {
    var b = canvas.getBoundingClientRect();
    if (dragging && view === "globe") {
      var dx = ev.clientX - dragging.x, dy = ev.clientY - dragging.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) dragging.moved = true;
      rot = [dragging.r[0] + dx * 0.35, Math.max(-60, Math.min(60, dragging.r[1] - dy * 0.35))];
      lastInteract = Date.now();
    } else {
      canvas.style.cursor = hit(ev.clientX - b.left, ev.clientY - b.top) ? "pointer" : view === "globe" ? "grab" : "default";
    }
  });
  canvas.addEventListener("pointerup", function (ev) {
    var b = canvas.getBoundingClientRect(), moved = dragging && dragging.moved;
    dragging = null; lastInteract = Date.now();
    if (moved) return;
    var d = hit(ev.clientX - b.left, ev.clientY - b.top);
    if (d) showPin(d); else { pin.hidden = true; selected = null; }
  });
  document.addEventListener("keydown", function (ev) { if (ev.key === "Escape") { pin.hidden = true; selected = null; } });

  $$("[data-view]").forEach(function (b) {
    b.addEventListener("click", function () {
      view = b.dataset.view; pin.hidden = true; selected = null;
      box.classList.toggle("is-map", view === "map");
      $$("[data-view]").forEach(function (x) { x.setAttribute("aria-pressed", x === b); });
      resize();
    });
  });
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (en) { visible = en[0].isIntersecting; }).observe(box);
  }
  window.addEventListener("resize", resize);
  resize();
  draw(0);
  fetch("/static/vendor/countries-110m.json").then(function (r) { return r.json(); }).then(function (topo) {
    land = topojson.feature(topo, topo.objects.land);
    borders = topojson.mesh(topo, topo.objects.countries, function (a, b) { return a !== b; });
    draw(0);
    requestAnimationFrame(frame);
  });
})();
