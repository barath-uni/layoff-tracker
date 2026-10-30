(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var fmt = function (n) { return n == null ? "–" : n.toLocaleString("en-US"); };

  // Theme toggle: explicit choice wins over the OS setting.
  $$("[data-theme-toggle]").forEach(function (b) {
    b.addEventListener("click", function () {
      var root = document.documentElement;
      var dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
      root.dataset.theme = dark ? "light" : "dark";
      try { localStorage.setItem("theme", root.dataset.theme); } catch (_) {}
    });
  });

  var toastEl = $(".toast"), toastT;
  function toast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.add("show");
    clearTimeout(toastT);
    toastT = setTimeout(function () { toastEl.classList.remove("show"); }, 1800);
  }
  document.addEventListener("click", function (ev) {
    var b = ev.target.closest("[data-copy]");
    if (!b) return;
    var url = b.getAttribute("data-copy");
    if (navigator.clipboard) navigator.clipboard.writeText(url).then(function () { toast("Link copied"); }, function () { toast(url); });
    else toast(url);
  });

  // Chart tooltips (hover + keyboard focus).
  $$("[data-chart]").forEach(function (chart) {
    var tip = $(".tip", chart);
    function show(rect) {
      var d = JSON.parse(rect.getAttribute("data-tip"));
      tip.textContent = "";
      var b = document.createElement("b"); b.textContent = fmt(d.v) + " people";
      var w = document.createElement("span"); w.textContent = d.w;
      tip.appendChild(b); tip.appendChild(w);
      if (d.t) { var t = document.createElement("div"); var k = document.createElement("span"); k.className = "key";
        t.appendChild(k); t.appendChild(document.createTextNode(d.t)); tip.appendChild(t); }
      var cr = chart.getBoundingClientRect(), rr = rect.getBoundingClientRect();
      var x = rr.left - cr.left + rr.width / 2;
      tip.style.left = Math.max(0, Math.min(cr.width - tip.offsetWidth, x - tip.offsetWidth / 2)) + "px";
      tip.style.top = "-8px";
      tip.style.opacity = 1;
      $$(".col.on", chart).forEach(function (c) { c.classList.remove("on"); });
      var col = rect.nextElementSibling;
      if (col && col.classList.contains("col")) col.classList.add("on");
    }
    function hide() { tip.style.opacity = 0; $$(".col.on", chart).forEach(function (c) { c.classList.remove("on"); }); }
    $$(".hit", chart).forEach(function (r) {
      r.addEventListener("pointerenter", function () { show(r); });
      r.addEventListener("focus", function () { show(r); });
      r.addEventListener("blur", hide);
    });
    chart.addEventListener("pointerleave", hide);
  });

  // Count-up for the hero number (respects reduced motion).
  var big = $("[data-count]");
  if (big && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
    var target = +big.getAttribute("data-count"), t0 = null;
    var step = function (ts) {
      if (!t0) t0 = ts;
      var p = Math.min(1, (ts - t0) / 1100), eased = 1 - Math.pow(1 - p, 3);
      big.textContent = fmt(Math.round(target * eased));
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  // Companies table search.
  var ts = $("[data-table-search]");
  if (ts) ts.addEventListener("input", function () {
    var q = ts.value.trim().toLowerCase();
    $$("[data-table] tbody tr").forEach(function (tr) { tr.hidden = q && tr.getAttribute("data-name").indexOf(q) < 0; });
  });

  // Home: filters scope the breakdowns and the feed.
  var dataEl = $("#events");
  if (!dataEl) return;
  var all = JSON.parse(dataEl.textContent);
  var state = { r: "ytd", i: "", k: "", q: "" }, shown = 30;
  var feed = $("[data-feed]"), more = $("[data-more]"), fsum = $("[data-fsum]");
  var today = new Date(), iso = function (d) { return d.toISOString().slice(0, 10); };
  var label = { Official: 4, Corroborated: 3, Reported: 2, Unverified: 1 };

  function filtered() {
    var since = state.r === "ytd" ? "0000" : iso(new Date(today.getTime() - (+state.r) * 864e5));
    var q = state.q.toLowerCase();
    return all.filter(function (e) {
      return e.d >= since && (!state.i || e.i === state.i) && (!state.k || e.k === state.k) &&
        (!q || e.c.toLowerCase().indexOf(q) >= 0);
    });
  }
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function badge(e) {
    var s = el("span", "conf"), m = el("span", "meter");
    for (var i = 0; i < 4; i++) m.appendChild(el("i", i < (label[e.l] || 1) ? "on" : ""));
    s.title = "Confidence " + e.cf + "/100 from " + e.np + " independent source" + (e.np === 1 ? "" : "s");
    s.appendChild(m); s.appendChild(document.createTextNode(e.l)); return s;
  }
  function row(e) {
    var a = el("a", "row"); a.href = "/company/" + e.s + "/";
    var dt = new Date(e.d + "T00:00:00");
    a.appendChild(el("span", "when", dt.toLocaleDateString("en-US", { month: "short", day: "numeric" })));
    var mid = el("span"); mid.appendChild(el("span", "co", e.c)); mid.appendChild(el("span", "hl", e.h));
    var meta = el("span", "meta"); meta.appendChild(badge(e)); meta.appendChild(el("span", null, e.i));
    meta.appendChild(el("span", null, e.k)); meta.appendChild(el("span", null, e.np + " source" + (e.np === 1 ? "" : "s")));
    mid.appendChild(meta); a.appendChild(mid);
    var num = el("span", "num");
    num.appendChild(el("b", null, e.n ? fmt(e.n) : e.p ? e.p + "%" : "Undisclosed"));
    var sub = e.n && e.lo && e.hi && e.lo !== e.hi ? "sources say " + fmt(e.lo) + "–" + fmt(e.hi)
      : e.n && e.p ? e.p + "% of staff" : !e.n && e.p ? "of staff, headcount not given" : e.n ? "people" : "no number yet";
    num.appendChild(el("small", null, sub)); a.appendChild(num);
    return a;
  }
  function bars(key, list) {
    var box = $('[data-bars="' + key + '"]'), acc = {};
    list.forEach(function (e) { if (e.n) acc[e[key]] = (acc[e[key]] || 0) + e.n; });
    var rows = Object.keys(acc).map(function (k) { return [k, acc[k]]; })
      .sort(function (a, b) { return (a[0] === "Unknown") - (b[0] === "Unknown") || b[1] - a[1]; }).slice(0, 10);
    box.textContent = "";
    if (!rows.length) { box.appendChild(el("p", "empty", "No events match.")); return; }
    var max = Math.max.apply(null, rows.map(function (r) { return r[1]; })) || 1;
    rows.forEach(function (r) {
      var b = el("button", "bar-row" + (state[key] === r[0] ? " active" : "")); b.type = "button";
      b.title = "Filter by " + r[0];
      b.appendChild(el("span", "name", r[0]));
      var tr = el("span", "track"), f = el("span", "fill"); f.style.width = Math.max(0.6, 100 * r[1] / max) + "%";
      tr.appendChild(f); b.appendChild(tr); b.appendChild(el("span", "val", fmt(r[1])));
      b.addEventListener("click", function () { state[key] = state[key] === r[0] ? "" : r[0]; sync(); render(); });
      box.appendChild(b);
    });
  }
  function sync() {
    $('[data-f="i"]').value = state.i; $('[data-f="k"]').value = state.k;
    $$("[data-range] button").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-r") === state.r); });
  }
  function render() {
    var list = filtered();
    var people = list.reduce(function (s, e) { return s + (e.n || 0); }, 0);
    fsum.textContent = fmt(people) + " people · " + fmt(list.length) + " events";
    bars("i", list); bars("k", list);
    $$(".row, .empty", feed).forEach(function (n) { n.remove(); });
    var frag = document.createDocumentFragment();
    list.slice(0, shown).forEach(function (e) { frag.appendChild(row(e)); });
    if (!list.length) frag.appendChild(el("p", "empty", "No events match these filters."));
    feed.insertBefore(frag, more);
    more.hidden = list.length <= shown;
  }
  $$("[data-range] button").forEach(function (b) {
    b.addEventListener("click", function () { state.r = b.getAttribute("data-r"); shown = 30; sync(); render(); });
  });
  $$("[data-f]").forEach(function (inp) {
    inp.addEventListener("input", function () { state[inp.getAttribute("data-f")] = inp.value; shown = 30; render(); });
  });
  more.addEventListener("click", function () { shown += 30; render(); });
  render();
})();
