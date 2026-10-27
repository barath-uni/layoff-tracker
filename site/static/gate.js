/* "Dive deeper": a full-height drawer (a sheet on phones) of designed rows. The first rows are clear; the rest sit
   blurred behind an email-only unlock card. A soft gate to measure demand, not a paywall: the data stays public in
   /data.json and the unlock is client-side. Endpoints: POST /api/signup, POST /api/event (see functions/api). */
(function () {
  "use strict";
  var root = document.querySelector("[data-dive]");
  if (!root) return;
  var inner = root.querySelector(".drawer-in");
  var FREE = 4, FREE_WARN = 3, LOCKED_PREVIEW = 6, MAX_ROWS = 300, KEY = "lr_unlocked";
  var events = null, warn = null, cur = null, tab = "company", lastFocus = null, gateSeen = false, autoTab = false, okNote = "";
  var U = function () { return window.lrUI; };
  var unlocked = function () { try { return localStorage.getItem(KEY) === "1"; } catch (_) { return false; } };
  function load() {
    if (events) return;
    try { events = JSON.parse(document.getElementById("events").textContent); } catch (_) { events = []; }
    try { warn = JSON.parse(document.getElementById("warn").textContent); } catch (_) { warn = []; }
    events.forEach(function (e) { e.t = e.t || Date.parse(e.d + "T12:00:00"); });
  }
  function el(tag, cls, text) { var n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; }
  function day(d, y) { return d ? new Date(d + "T12:00:00").toLocaleDateString("en-US", y ? { month: "short", day: "numeric", year: "numeric" } : { month: "short", day: "numeric" }) : "–"; }

  function tabs(e) {
    var co = events.filter(function (x) { return x.s === e.s; });
    var sec = e.i && e.i !== "Unknown" && e.i !== "Other" ? events.filter(function (x) { return x.i === e.i; }) : [];
    var ctry = e.k && e.k !== "Unknown" ? events.filter(function (x) { return x.k === e.k; }) : [];
    var ew = warn.filter(function (x) { return x.s === e.s; }).concat(warn.filter(function (x) { return x.s !== e.s; }));
    var out = [{ id: "company", label: e.c, rows: co }];
    if (sec.length) out.push({ id: "sector", label: e.i, rows: sec });
    if (ctry.length) out.push({ id: "country", label: (U().flag(e.cc) ? U().flag(e.cc) + " " : "") + e.k, rows: ctry });
    if (ew.length) out.push({ id: "warn", label: "Early warning", rows: ew, warn: true });
    return out;
  }

  function eventRow(x, showCo) {
    var a = el("a", "dr" + (cur && x.s === cur.s && showCo ? " me" : "")); a.href = "/company/" + x.s + "/";
    a.appendChild(U().logoEl(x));
    a.appendChild(el("span", "dr-co", showCo ? x.c : day(x.d, true)));
    var n = el("span", "dr-n num", x.n ? U().fmt(x.n) : x.ps || "–");
    n.appendChild(el("small", null, x.n ? "people" : x.ps ? "of staff" : "undisclosed"));
    a.appendChild(n);
    var meta = el("span", "dr-meta");
    if (showCo) meta.appendChild(el("span", null, day(x.d)));
    if (x.cc) meta.appendChild(el("span", null, U().flag(x.cc)));
    meta.appendChild(U().confTag(x));
    if (x.np) meta.appendChild(el("span", null, x.np + " src"));
    a.appendChild(meta);
    var p = U().pctNum(x.ps);
    if (p != null && x.n) {
      var bar = el("span", "dr-bar"); bar.appendChild(U().pbar(p)); bar.appendChild(el("span", null, x.ps + " of staff"));
      a.appendChild(bar);
    }
    return a;
  }
  function warnRow(x) {
    var a = el(x.s ? "a" : "div", "dr warn"); if (x.s) a.href = "/company/" + x.s + "/";
    var lk = el("span", "lk"); lk.innerHTML = U().LOCK; a.appendChild(lk);
    a.appendChild(el("span", "dr-co", x.c || "Undisclosed employer"));
    var n = el("span", "dr-n num", U().fmt(x.n)); n.appendChild(el("small", null, "people")); a.appendChild(n);
    var meta = el("span", "dr-meta");
    meta.appendChild(el("span", null, "effective " + day(x.e)));
    if (x.loc) meta.appendChild(el("span", null, x.loc));
    a.appendChild(meta);
    var f = el("span", "dr-bar"); f.appendChild(el("span", null, "WARN filed " + day(x.f) + (x.kd ? " · " + x.kd : ""))); a.appendChild(f);
    return a;
  }

  function unlockCard(total, t) {
    var g = el("div", "unlock");
    var ic = el("div", "ic"); ic.innerHTML = U().LOCK.replace(/width="12" height="12"/, 'width="16" height="16"'); g.appendChild(ic);
    g.appendChild(el("h3", null, t.warn ? "See every early warning" : "See all " + U().fmt(total) + " rows"));
    g.appendChild(el("p", null, t.warn ? "Layoffs already filed with the state, before they happen. Free during early access."
      : "Plus the early-warning list of layoffs filed but not yet effective. Free during early access."));
    var f = el("form"); f.noValidate = true;
    var hp = el("input"); hp.type = "text"; hp.name = "website"; hp.tabIndex = -1; hp.autocomplete = "off"; hp.className = "hp"; hp.setAttribute("aria-hidden", "true");
    var em = el("input"); em.type = "email"; em.name = "email"; em.required = true; em.placeholder = "you@work.com"; em.autocomplete = "email";
    em.setAttribute("aria-label", "Email"); em.inputMode = "email";
    var btn = el("button", "btn", "Unlock"); btn.type = "submit";
    var msg = el("p", "msg"); msg.setAttribute("role", "status");
    f.appendChild(hp); f.appendChild(em); f.appendChild(btn);
    var opened = false;
    em.addEventListener("focus", function () { if (!opened) { opened = true; U().track("signup_open"); } });
    f.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var v = em.value.trim();
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(v)) { msg.textContent = "Enter a valid email."; em.focus(); return; }
      btn.disabled = true; btn.textContent = "…"; msg.textContent = "";
      fetch("/api/signup", { method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: v, website: hp.value, src: "dive:" + t.id + ":" + (cur ? cur.s : "") }) })
        .then(function (r) { return r.json().catch(function () { return {}; }).then(function (d) { return { ok: r.ok && d.ok, d: d }; }); })
        .then(function (res) {
          btn.disabled = false; btn.textContent = "Unlock";
          if (!res.ok) { msg.textContent = res.d.error || "Something went wrong. Try again."; return; }
          try { localStorage.setItem(KEY, "1"); } catch (_) {}
          okNote = res.d.known ? "Welcome back. Everything is unlocked." : "You're in. Everything is unlocked in this browser.";
          render();
        }, function () { btn.disabled = false; btn.textContent = "Unlock"; msg.textContent = "Network error. Try again."; });
    });
    g.appendChild(f); g.appendChild(msg);
    g.appendChild(el("p", "fine", "Email only. No password, no spam."));
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
    var head = el("div", "d-head"), top = el("div", "d-top");
    top.appendChild(U().logoEl(e, true));
    var tt = el("div"); tt.appendChild(el("div", "d-eyebrow", "Dive deeper"));
    var h = el("h2", null, e.c); h.id = "dive-title"; tt.appendChild(h); top.appendChild(tt);
    var x = el("button", "c-x", "×"); x.type = "button"; x.setAttribute("aria-label", "Close"); x.addEventListener("click", close);
    top.appendChild(x); head.appendChild(top);
    var seg = el("div", "d-tabs"); seg.setAttribute("role", "tablist");
    all.forEach(function (tb) {
      var b = el("button", tb.warn ? "is-warn" : null); b.type = "button"; b.setAttribute("role", "tab");
      b.setAttribute("aria-selected", tb.id === tab);
      if (tb.warn) b.innerHTML = U().LOCK;
      b.appendChild(document.createTextNode(tb.label));
      b.appendChild(el("span", "ct", String(tb.rows.length)));
      b.addEventListener("click", function () { tab = tb.id; render(); });
      seg.appendChild(b);
    });
    head.appendChild(seg);
    inner.appendChild(head);

    var body = el("div", "d-body");
    if (okNote && open) { body.appendChild(el("p", "d-ok", okNote)); okNote = ""; }
    var note = el("p", "d-note");
    if (t.warn) {
      note.className = "d-note is-warn";
      note.textContent = "WARN = official advance notice. US employers generally must file it about 60 days before a mass layoff. " +
        "These " + t.rows.length + " are filed, but the layoff date is still ahead. California and Maryland for now.";
    } else {
      var ppl = t.rows.reduce(function (s, r) { return s + (r.n || 0); }, 0);
      note.appendChild(el("b", null, t.rows.length + " layoff" + (t.rows.length === 1 ? "" : "s")));
      note.appendChild(document.createTextNode((ppl ? ", " + U().fmt(ppl) + " people" : "") +
        (t.id === "company" ? " at " + e.c : t.id === "sector" ? " in " + e.i : " in " + e.k) + " this year. Newest first."));
    }
    body.appendChild(note);
    var free = t.warn ? FREE_WARN : FREE, total = t.rows.length, showCo = t.id !== "company";
    var mk = function (r) { return t.warn ? warnRow(r) : eventRow(r, showCo); };
    if (!total) body.appendChild(el("p", "empty", "Nothing here yet."));
    if (open || total <= free) {
      t.rows.slice(0, MAX_ROWS).forEach(function (r) { body.appendChild(mk(r)); });
      if (total > MAX_ROWS) body.appendChild(el("p", "d-more", "Showing " + MAX_ROWS + " of " + U().fmt(total) + ". The full data is in /data.json."));
    } else {
      t.rows.slice(0, free).forEach(function (r) { body.appendChild(mk(r)); });
      var lw = el("div", "locked-wrap"), lr = el("div", "locked-rows");
      lr.setAttribute("aria-hidden", "true");
      t.rows.slice(free, free + LOCKED_PREVIEW).forEach(function (r) { var n = mk(r); n.tabIndex = -1; lr.appendChild(n); });
      lw.appendChild(lr); lw.appendChild(unlockCard(total, t));
      body.appendChild(lw);
      body.appendChild(el("p", "d-more", "+ " + U().fmt(total - free) + " more row" + (total - free === 1 ? "" : "s") + " locked"));
      if (!gateSeen) { gateSeen = true; U().track("gate_view"); }
      requestAnimationFrame(function () {   // keep the card fully inside the blurred area
        var c = lw.lastChild; lw.style.minHeight = (c.offsetHeight + 60) + "px";
      });
    }
    inner.appendChild(body);
  }

  function close() {
    root.hidden = true;
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }
  function open(e, which) {
    load();
    cur = e; tab = which || "company"; lastFocus = document.activeElement; gateSeen = false; autoTab = true; okNote = "";
    root.hidden = false;
    render();
    inner.focus();
  }
  root.addEventListener("click", function (ev) { if (ev.target === root) close(); });
  document.addEventListener("keydown", function (ev) { if (ev.key === "Escape" && !root.hidden) close(); });
  window.lrGate = { open: open };
})();
