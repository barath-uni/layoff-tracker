/* "Dive deeper": a table preview with the first rows free and the rest blurred behind an email-only sign-up.
   A soft gate to measure demand, not a paywall: the data stays public in /data.json, and the unlock is client-side. */
(function () {
  "use strict";
  var root = document.querySelector("[data-dive]");
  if (!root) return;
  var inner = root.querySelector(".dive-in");
  var FREE = 4, FREE_WARN = 3, LOCKED_PREVIEW = 8, KEY = "lr_unlocked";
  var LOCK = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>';
  var events = null, warn = null, cur = null, tab = "company", lastFocus = null, gateSeen = false, autoTab = false;
  var fmt = function (n) { return n == null ? "–" : Math.round(n).toLocaleString("en-US"); };
  var unlocked = function () { try { return localStorage.getItem(KEY) === "1"; } catch (_) { return false; } };
  function load() {
    if (events) return;
    try { events = JSON.parse(document.getElementById("events").textContent); } catch (_) { events = []; }
    try { warn = JSON.parse(document.getElementById("warn").textContent); } catch (_) { warn = []; }
  }
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function day(d, y) { return d ? new Date(d + "T12:00:00").toLocaleDateString("en-US", y ? { month: "short", day: "numeric", year: "numeric" } : { month: "short", day: "numeric" }) : "–"; }
  function track(t) {
    try { fetch("/api/event", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ t: t }), keepalive: true }).catch(function () {}); } catch (_) {}
  }

  function tabs(e) {
    var co = events.filter(function (x) { return x.s === e.s; });
    var sec = e.i && e.i !== "Unknown" ? events.filter(function (x) { return x.i === e.i; }) : [];
    var ctry = e.k && e.k !== "Unknown" ? events.filter(function (x) { return x.k === e.k; }) : [];
    var mine = warn.filter(function (x) { return x.s === e.s; });
    var ew = mine.concat(warn.filter(function (x) { return x.s !== e.s; }));
    var out = [{ id: "company", label: e.c, rows: co }];
    if (sec.length) out.push({ id: "sector", label: e.i, rows: sec });
    if (ctry.length) out.push({ id: "country", label: e.k, rows: ctry });
    if (ew.length) out.push({ id: "warn", label: "Early warning", rows: ew, warn: true });
    return out;
  }

  function eventTable(rows, n, showCo) {
    var t = el("table", "dt"), head = el("tr");
    ["Date", showCo ? "Company" : null, "People", "% of staff", "Confidence"].forEach(function (h, i) {
      if (h == null) return;
      var th = el("th", i >= 2 ? "r" : null, h); if (h === "% of staff") th.className = "r opt"; head.appendChild(th);
    });
    var thead = el("thead"); thead.appendChild(head); t.appendChild(thead);
    var tb = el("tbody");
    rows.slice(0, n).forEach(function (x) {
      var tr = el("tr", cur && x.s === cur.s && showCo ? "me" : null);
      tr.appendChild(el("td", "mono", day(x.d)));
      if (showCo) { var td = el("td"), a = el("a", null, x.c); a.href = "/company/" + x.s + "/"; td.appendChild(a); tr.appendChild(td); }
      tr.appendChild(el("td", "r num", x.n ? fmt(x.n) : "–"));
      tr.appendChild(el("td", "r opt", x.ps || "–"));
      tr.appendChild(el("td", "r", x.l + (x.cf != null ? " · " + x.cf : "")));
      tb.appendChild(tr);
    });
    t.appendChild(tb);
    return t;
  }
  function warnTable(rows, n) {
    var t = el("table", "dt warn"), head = el("tr");
    ["", "Effective", "Company", "People", "Where", "Filed"].forEach(function (h, i) {
      var th = el("th", i === 3 ? "r" : i === 5 ? "opt" : null, h); head.appendChild(th);
    });
    var thead = el("thead"); thead.appendChild(head); t.appendChild(thead);
    var tb = el("tbody");
    rows.slice(0, n).forEach(function (x) {
      var tr = el("tr"), lk = el("td", "lk"); lk.innerHTML = LOCK; tr.appendChild(lk);
      tr.appendChild(el("td", "mono", day(x.e)));
      tr.appendChild(el("td", null, x.c));
      tr.appendChild(el("td", "r num", fmt(x.n)));
      tr.appendChild(el("td", "loc", x.loc || "–"));
      tr.appendChild(el("td", "mono opt", day(x.f)));
      tb.appendChild(tr);
    });
    t.appendChild(tb);
    return t;
  }

  function gateForm(total, t) {
    var g = el("div", "gate");
    var ic = el("div", "gate-ic"); ic.innerHTML = LOCK; g.appendChild(ic);
    g.appendChild(el("h3", null, "See all " + fmt(total) + " rows" + (t.warn ? "" : " and the early-warning list")));
    g.appendChild(el("p", null, "Free during early access. Email only, no password. We'll write when alerts by company, sector and country launch."));
    var f = el("form", "gate-form"); f.noValidate = true;
    var hp = el("input"); hp.type = "text"; hp.name = "website"; hp.tabIndex = -1; hp.autocomplete = "off"; hp.className = "hp"; hp.setAttribute("aria-hidden", "true");
    var em = el("input"); em.type = "email"; em.name = "email"; em.required = true; em.placeholder = "you@work.com"; em.autocomplete = "email";
    em.setAttribute("aria-label", "Email"); em.inputMode = "email";
    var btn = el("button", "btn primary", "Unlock"); btn.type = "submit";
    var msg = el("p", "gate-msg"); msg.setAttribute("role", "status");
    f.appendChild(hp); f.appendChild(em); f.appendChild(btn);
    var opened = false;
    em.addEventListener("focus", function () { if (!opened) { opened = true; track("signup_open"); } });
    f.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var v = em.value.trim();
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(v)) { msg.textContent = "Enter a valid email."; em.focus(); return; }
      btn.disabled = true; msg.textContent = "";
      fetch("/api/signup", { method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: v, website: hp.value, src: "dive:" + t.id + ":" + (cur ? cur.s : "") }) })
        .then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { ok: r.ok && d.ok, d: d }; }); })
        .then(function (res) {
          btn.disabled = false;
          if (!res.ok) { msg.textContent = res.d.error || "Something went wrong. Try again."; return; }
          try { localStorage.setItem(KEY, "1"); } catch (_) {}
          render();
          var note = inner.querySelector(".dive-note");
          if (note) note.textContent = res.d.known ? "Welcome back. Full table unlocked." : "You're in. Full table unlocked.";
        }, function () { btn.disabled = false; msg.textContent = "Network error. Try again."; });
    });
    g.appendChild(f); g.appendChild(msg);
    return g;
  }

  function render() {
    var e = cur, all = tabs(e), open = unlocked();
    // A company with only a few events would show nothing locked: land on its sector (or country) instead.
    if (autoTab && tab === "company" && !open && all[0].rows.length <= FREE && all.length > 1 && !all[1].warn) tab = all[1].id;
    autoTab = false;
    var t = all.filter(function (x) { return x.id === tab; })[0] || all[0];
    tab = t.id;
    inner.textContent = "";
    var head = el("div", "dive-head");
    var hl = el("div");
    hl.appendChild(el("div", "dive-eyebrow", "Dive deeper"));
    var h = el("h2", null, e.c); h.id = "dive-title"; hl.appendChild(h);
    head.appendChild(hl);
    var x = el("button", "pin-x", "×"); x.type = "button"; x.setAttribute("aria-label", "Close"); x.addEventListener("click", close);
    head.appendChild(x);
    inner.appendChild(head);

    var seg = el("div", "seg dive-tabs"); seg.setAttribute("role", "tablist");
    all.forEach(function (tt) {
      var b = el("button", tt.warn ? "is-warn" : null); b.type = "button"; b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", tt.id === tab); b.setAttribute("aria-pressed", tt.id === tab);
      if (tt.warn) b.innerHTML = LOCK + " ";
      b.appendChild(document.createTextNode(tt.label + " "));
      b.appendChild(el("span", "ct", String(tt.rows.length)));
      b.addEventListener("click", function () { tab = tt.id; render(); });
      seg.appendChild(b);
    });
    inner.appendChild(seg);

    var note = el("p", "dive-note");
    if (t.warn) {
      note.className = "dive-note is-warn";
      note.textContent = "WARN = official advance notice. US employers generally must file it about 60 days before a mass layoff or closure. " +
        "These " + t.rows.length + " notices are filed, but the layoff date is still ahead. California and Maryland only for now.";
    } else {
      var ppl = t.rows.reduce(function (s, r) { return s + (r.n || 0); }, 0);
      note.textContent = t.rows.length + " event" + (t.rows.length === 1 ? "" : "s") + (ppl ? ", " + fmt(ppl) + " people" : "") +
        (t.id === "company" ? " at " + e.c : t.id === "sector" ? " in " + e.i : " in " + e.k) + " this year. Newest first.";
    }
    inner.appendChild(note);

    var free = t.warn ? FREE_WARN : FREE, total = t.rows.length;
    var wrapT = el("div", "dt-wrap");
    var mk = function (n) { return t.warn ? warnTable(t.rows, n) : eventTable(t.rows, n, t.id !== "company"); };
    if (open || total <= free) {
      wrapT.appendChild(mk(total));
      inner.appendChild(wrapT);
    } else {
      var shown = mk(free + Math.min(LOCKED_PREVIEW, total - free));
      Array.prototype.slice.call(shown.tBodies[0].rows, free).forEach(function (r) { r.className = "locked"; r.setAttribute("aria-hidden", "true"); });
      wrapT.appendChild(shown);
      var lockBox = el("div", "dt-lock");
      lockBox.appendChild(gateForm(total, t));
      wrapT.appendChild(lockBox);
      wrapT.classList.add("is-locked");
      if (!gateSeen) { gateSeen = true; track("gate_view"); }
      inner.appendChild(wrapT);
      var top = shown.tBodies[0].rows[free].offsetTop;  // overlay starts where the free rows end
      lockBox.style.top = top + "px";
      wrapT.style.minHeight = (top + lockBox.firstChild.offsetHeight + 32) + "px";
      inner.appendChild(el("p", "dive-more", "+ " + fmt(total - free) + " more row" + (total - free === 1 ? "" : "s") + " locked"));
    }
  }

  function close() {
    root.hidden = true; document.documentElement.classList.remove("dive-open");
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }
  function open(e, which) {
    load();
    cur = e; tab = which || "company"; lastFocus = document.activeElement; gateSeen = false; autoTab = true;
    root.hidden = false; document.documentElement.classList.add("dive-open");
    render();
    inner.focus();
  }
  root.addEventListener("click", function (ev) { if (ev.target === root) close(); });
  document.addEventListener("keydown", function (ev) { if (ev.key === "Escape" && !root.hidden) close(); });
  window.lrGate = { open: open };
})();
