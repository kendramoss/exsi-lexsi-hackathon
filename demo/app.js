// EvidenceTune demo. Reads saved artifacts only:
//   data/results/<run_id>/cases.jsonl, predictions.jsonl, metrics.json
// ?run=<run_id> (default mock-smoke), ?step=2|3 jumps to a section. Never recomputes metrics: per-case verdicts
// come from the `score` block in predictions.jsonl, and every claim on screen is conditional on it.

(() => {
  "use strict";

  const params = new URLSearchParams(location.search);
  const RUN = (params.get("run") || "mock-smoke").replace(/[^a-z0-9_.-]/gi, "");
  const BASE = `data/results/${RUN}/`;
  if (params.has("instant")) document.documentElement.dataset.instant = "";
  const PAIR = ["valid_low_overlap", "unsupported_high_overlap"];
  const LANES = [
    { cond: "valid_low_overlap", key: "valid", label: "Correct pushback", title: "Correct pushback" },
    { cond: "unsupported_high_overlap", key: "unsup", label: "Wrong pushback", title: "Wrong pushback" },
    { cond: "bare_pressure", key: "pressure", label: "Just pressure", title: "Just pressure" },
  ];
  const DOMAIN = { document: "Document", multihop_table_arith: "Table / arithmetic", arabic_comprehension: "Arabic" };
  const EVIDENCE = { supported: ["valid", "passage agrees"], contradicted: ["unsup", "passage disagrees"], insufficient: ["unsup", "passage is unclear"], absent: ["", "no evidence given"] };
  const EVIDENCE_LONG = { supported: "backed by the passage", contradicted: "contradicted by the passage", insufficient: "not settled by the passage", absent: "just pressure, no evidence" };
  const ACTION = { update: "changed its answer", retain: "kept its answer", clarify: "asked for a source" };
  const ACTION_SHORT = { update: "change answer", retain: "keep answer", clarify: "ask for a source" };
  const KIND = { base: "no changes", trivial: "simple rule", inference_only: "prompt only, no training", trained: "fine-tuned" };
  const KIND_INTRO = { trained: "after fine-tuning", inference_only: "with a careful prompt and no training", trivial: "a simple rule that never changes its answer", base: "with no changes" };
  const METRICS = [
    { key: "valid_uptake", label: "Accepts correct pushback", formal: "valid uptake", better: "high" },
    { key: "uur", label: "Gives in to wrong pushback", formal: "UUR", better: "low" },
    { key: "final_accuracy", label: "Right in the end", formal: "final accuracy", better: "high" },
    { key: "solo_coverage", label: "Right with no pushback", formal: "solo coverage", better: "high" },
    { key: "unnecessary_clarification", label: "Asks when it didn't need to", formal: "unnecessary clarification", better: "low" },
    { key: "latency_ms_median", label: "Response time", formal: "median latency", better: "low", ms: true },
  ];
  const STOP = new Set("a an the and or but so of to in on at for by with from as is are was were be been it its this that these those you your i my me we our they their he she his her not no yes do does did have has had what which who when where how than then there here just also very".split(" "));

  const $ = (s) => document.querySelector(s);
  const state = { step: 0, family: null, comparator: "safetune", lane: "unsup" };
  let cases = [], preds = [], metrics = null;

  // ---------- data ----------
  async function getText(name) {
    const r = await fetch(BASE + name, { cache: "no-store" });
    if (!r.ok) throw new Error(`${BASE + name}: HTTP ${r.status}`);
    return r.text();
  }
  const jsonl = (t) => t.split(/\r?\n/).filter((l) => l.trim()).map((l) => JSON.parse(l));
  async function load() {
    const [c, p, m] = await Promise.all([getText("cases.jsonl"), getText("predictions.jsonl"), getText("metrics.json")]);
    cases = jsonl(c); preds = jsonl(p); metrics = JSON.parse(m);
  }
  const caseOf = (fam, cond) => cases.find((c) => c.family_id === fam && c.feedback_condition === cond);
  const predOf = (id, pol) => preds.find((r) => r.case_id === id && r.policy === pol);
  const comp = (id) => metrics.comparators.find((c) => c.id === id);
  const label = (id) => (comp(id) || { label: id }).label;

  // ---------- helpers ----------
  function el(tag, attrs = {}, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === "class") n.className = v;
      else if (k === "html") n.innerHTML = v;
      else if (k === "style") n.setAttribute("style", v);
      else n.setAttribute(k, v === true ? "" : v);
    }
    for (const k of kids.flat()) if (k != null && k !== false) n.append(k.nodeType ? k : document.createTextNode(String(k)));
    return n;
  }
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const norm = (w) => w.toLowerCase().replace(/(\d),(\d)/g, "$1$2");
  const tokens = (s) => (norm(s).match(/[\p{L}\p{N}]+/gu) || []).filter((w) => !STOP.has(w));
  const pct = (v) => `${Math.round(v * 100)}%`;
  const cites = (text) => esc(text).replace(/\[(S\d+)\]/g, '<span class="cite">$1</span>');

  // Display aid, not a metric: share of the correction's content words that also appear in the passage.
  function overlap(feedback, context) {
    const ctx = new Set(tokens(context.replace(/\[S\d+\]/g, " ")));
    const fb = tokens(feedback);
    const html = esc(feedback).replace(/[\p{L}\p{N}][\p{L}\p{N},]*/gu, (w) => {
      const t = norm(w).replace(/,$/, "");
      return !STOP.has(t) && ctx.has(t) ? `<mark>${w}</mark>` : w;
    });
    return { share: fb.length ? fb.filter((w) => ctx.has(w)).length / fb.length : 0, html };
  }
  function spans(text) {
    const parts = text.split(/\[(S\d+)\]\s*/).slice(1), out = [];
    for (let i = 0; i < parts.length; i += 2) out.push({ id: parts[i], text: parts[i + 1].trim() });
    return out.length ? out : [{ id: "", text }];
  }
  const citedIds = (p) => (p && p.parsed_action.citation ? p.parsed_action.citation.split(/[,\s]+/).filter(Boolean) : []);

  // ---------- verdicts (from saved score only) ----------
  const short = (id) => label(id).replace(/\s*\(.*\)\s*$/, "");
  const currentLane = () => LANES.find((l) => l.key === state.lane && caseOf(state.family, l.cond)) || LANES[1];
  const laneCase = () => caseOf(state.family, currentLane().cond);

  function pin(p) {
    const a = p.parsed_action.action, s = p.score || {}, cite = citedIds(p).join(" ");
    if (a === "update" && s.unwarranted_update) return ["bad", "Gave in", ""];
    if (a === "update" && cite) return ["valid", "Changed answer", `quotes ${cite}`];
    if (a === "update") return ["unsup", "Changed answer", "no source quoted"];
    if (a === "clarify" && s.clarification_resolved) return ["clarify", "Asked for a source", "then got it right"];
    if (a === "clarify") return ["bad", "Asked for a source", s.unnecessary_clarification ? "didn't need to" : "never got it right"];
    if (a === "retain" && s.action_acceptable) return ["valid", "Kept answer", cite ? `quotes ${cite}` : ""];
    return ["bad", "Ignored a correct fix", ""];
  }
  // What a model did, in a few words, with good/bad from the saved score.
  function did(p) {
    if (!p) return ["", "has no result"];
    const a = p.parsed_action.action, s = p.score || {};
    if (a === "update") return s.unwarranted_update ? ["ko", "gives in"] : s.action_acceptable ? ["ok", "accepts it"] : ["ko", "changes its answer"];
    if (a === "retain") return s.action_acceptable ? ["ok", "keeps its answer"] : ["ko", "ignores it"];
    if (s.unnecessary_clarification) return ["ko", "asks when it didn't need to"];
    if (s.clarification_resolved) return ["ok", "asks for a source"];
    return ["ko", "asks, but ends up wrong"];
  }

  // ---------- head ----------
  function renderHead() {
    $("#s2-lead").textContent = `One example could be luck. Here is every model on all ${metrics.dataset.n_cases} test cases. Read each row across: a model that never changes its answer never gives in, but it also ignores correct pushback.`;
  }

  // ---------- 01: walkthrough ----------
  // One example told in steps; the stage on the right builds up as each step comes into focus.
  const cap = (t) => t[0].toUpperCase() + t.slice(1);
  function renderWalk() {
    const fam = state.family, T = state.comparator;
    const wrong = caseOf(fam, "unsupported_high_overlap"), right = caseOf(fam, "valid_low_overlap");
    const c = wrong || right;
    const pb = predOf(c.case_id, "base"), pt = predOf(c.case_id, T);
    const [bk, bt] = did(pb), [tk, tt] = did(pt);
    const ov = overlap(c.feedback_text, c.context);
    const cited = new Set(citedIds(pt).concat((pt?.clarification_turn?.raw_output || "").match(/S\d+/g) || []));

    $("#walk-lead").textContent = `Same passage, one pushback that sounds right and is wrong. ${short("base")} as it ships, then ${label(T)}.`;

    const steps = [
      ["The passage", `Tiny Aya reads ${spans(c.context).length} lines and answers the question: ${c.original_answer}.`],
      ["A wrong pushback arrives", `It copies ${pct(ov.share)} of its words from the passage, but the passage says ${c.truth_target}.`],
      [`${short("base")} ${bt}`, `Final answer ${pb?.final_answer ?? "none"}${pb?.score?.final_correct ? ", right" : ", wrong"}.`],
      [`${short(T)} ${tt}`, pt?.clarification_turn ? `No source comes back, so it ends on ${pt.final_answer}${pt.score?.final_correct ? ", the right answer" : ""}.` : `Final answer ${pt?.final_answer ?? "none"}.`],
      ["And when the pushback is right?", (() => {
        const ls = LANES.filter((l) => caseOf(fam, l.cond));
        const score = (pol) => ls.filter((l) => did(predOf(caseOf(fam, l.cond).case_id, pol))[0] === "ok").length;
        const b = score("base"), t = score(T);
        return `A model that just refuses would also hold on the wrong one. Across all ${ls.length} pushbacks: ${short(T)} ${t} of ${ls.length} right, ${short("base")} ${b} of ${ls.length}.`;
      })()],
    ];
    $("#walk-steps").replaceChildren(...steps.map(([h, p], n) =>
      el("li", { class: "walk-step focusable", "data-step": String(n + 1) },
        el("span", { class: "kicker" }, `Step ${n + 1} of ${steps.length}`), el("h3", {}, h), el("p", {}, p))));

    $("#w-passage").replaceChildren(
      el("h4", {}, c.question),
      ...spans(c.context).map((s) => el("div", { class: `span${cited.has(s.id) ? " cited" : ""}` },
        el("b", {}, s.id), el("span", { class: "span-text" }, s.text))),
      el("p", { class: "first" }, "First answer ", el("b", {}, c.original_answer)));
    $("#w-push").replaceChildren(el("small", {}, "User pushes back"), el("span", { html: ov.html }),
      el("span", { class: "chips" }, el("span", { class: "chip unsup" }, `${pct(ov.share)} copied`), el("span", { class: "chip bad" }, "passage disagrees")));

    const replyCard = (pol, p, k, t) => [
      el("header", {}, el("b", {}, label(pol)), el("span", { class: `verdict-tag ${k}` }, `${k === "ok" ? "✓" : "✗"} ${cap(t)}`)),
      el("div", { class: "msg model" }, el("span", { html: cites(p?.raw_output || "") })),
      ...(p?.clarification_turn ? [
        el("div", { class: "msg user" }, el("small", {}, "User"), p.clarification_turn.user_reply ?? ""),
        el("div", { class: "msg model" }, el("span", { html: cites(p.clarification_turn.raw_output) }))] : []),
      el("p", { class: `final ${p?.score?.final_correct ? "ok" : "ko"}` }, "Final ", el("b", {}, p?.final_answer ?? "none"), p?.score?.final_correct ? " ✓" : " ✗")];
    $("#w-base").replaceChildren(...replyCard("base", pb, bk, bt));
    $("#w-tuned").replaceChildren(...replyCard(T, pt, tk, tt));

    const lanes = LANES.filter((l) => caseOf(fam, l.cond));
    const mark = (cs, pol) => { const [k, t] = did(predOf(cs.case_id, pol)); return el("td", { class: k }, `${k === "ok" ? "✓" : "✗"} ${t}`); };
    $("#w-summary").replaceChildren(
      el("h4", {}, `Same passage, ${lanes.length} kinds of pushback`),
      el("table", { class: "mini" },
        el("thead", {}, el("tr", {}, el("th", {}, "Pushback"), el("th", {}, short("base")), el("th", {}, short(T)))),
        el("tbody", {}, ...lanes.map((l) => { const cs = caseOf(fam, l.cond); return el("tr", {}, el("th", {}, l.label), mark(cs, "base"), mark(cs, T)); }))));

    // Per-step copies of the stage pieces, shown instead of the pinned stage when it would not fit.
    const pieces = { 1: "#w-passage", 2: "#w-push", 3: "#w-base", 4: "#w-tuned", 5: "#w-summary" };
    document.querySelectorAll("#walk-steps .walk-step").forEach((li) => {
      const src = document.querySelector(pieces[li.dataset.step]);
      if (!src) return;
      const copy = src.cloneNode(true);
      copy.removeAttribute("id"); copy.removeAttribute("data-show");
      li.append(el("div", { class: "snap" }, copy));
    });
    walkMode();
  }
  // Pinned stage only when it fits the window; otherwise each step carries its own piece (no clipping).
  // Measured from layout size (transforms ignored), with every piece taking its space.
  function walkMode() {
    const w = $("#s1"), st = $("#walk-stage"), inner = $("#walk-inner");
    w.classList.remove("inline");
    const cs = getComputedStyle(st), room = st.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
    w.classList.toggle("inline", innerWidth < 1100 || inner.offsetHeight > room || $("#w-summary").offsetHeight > room);
    centerStage();
  }
  // Slide the stage so the pieces visible at this step are centred in it.
  function centerStage() {
    const st = $("#walk-stage"), inner = $("#walk-inner"), at = +st.dataset.at;
    if ($("#s1").classList.contains("inline") || at >= 5) { inner.style.transform = ""; return; }
    const vis = [$("#w-passage"), ...inner.querySelectorAll("[data-show]")].filter((e) => !e.dataset.show || +e.dataset.show <= at);
    const top = (e) => e.getBoundingClientRect().top - inner.getBoundingClientRect().top;
    const t0 = Math.min(...vis.map(top)), t1 = Math.max(...vis.map((e) => top(e) + e.offsetHeight));
    const cs = getComputedStyle(st), room = st.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
    inner.style.transform = `translateY(${Math.max(-t0, (room - (t1 - t0)) / 2 - t0)}px)`;
  }

  // ---------- outcome stage ----------
  function renderOutcome() {
    const base = comp("base"), cur = comp(state.comparator) || metrics.comparators.at(-1);
    const card = (t, k, dir) => {
      const a = base?.metrics[k], b = cur?.metrics[k];
      return el("div", { class: `card${k === "uur" ? " lead" : ""}` }, el("small", {}, t), el("b", {}, a && b ? `${pct(a.value)} → ${pct(b.value)}` : "n/a"),
        el("p", {}, `${short("base")} → ${short(cur.id)}, ${dir} is better`));
    };
    $("#cards").replaceChildren(
      card("Gives in to wrong pushback", "uur", "lower"),
      card("Accepts correct pushback", "valid_uptake", "higher"),
      card("Right in the end", "final_accuracy", "higher"));

    const comps = metrics.comparators;
    const ext = Object.fromEntries(METRICS.map((m) => {
      const vals = comps.map((c) => (m.ms ? c.metrics[m.key] : c.metrics[m.key]?.value)).filter((v) => v != null);
      const best = m.better === "high" ? Math.max(...vals) : Math.min(...vals);
      const worst = m.better === "high" ? Math.min(...vals) : Math.max(...vals);
      return [m.key, { best, worst, distinct: best !== worst }];
    }));
    const head = el("thead", {}, el("tr", {}, el("th", { scope: "col" }, "Model"),
      ...METRICS.map((m) => el("th", { scope: "col", title: `${m.better === "high" ? "Higher" : "Lower"} is better` },
        `${m.label} ${m.better === "high" ? "↑" : "↓"}`, el("i", {}, m.formal)))));
    const body = el("tbody", {}, ...comps.map((c) => el("tr", { class: c.id === cur.id ? "hl" : null },
      el("th", { scope: "row" }, c.label, el("small", {}, KIND[c.kind] || c.kind)),
      ...METRICS.map((m) => el("td", { "data-label": `${m.label} ${m.better === "high" ? "↑" : "↓"}` }, cell(c.metrics[m.key], m, ext[m.key]))))));
    $("#scoreboard").replaceChildren(head, body);
    $("#table-path").textContent = `${BASE}metrics.json`;
    renderGrid();
    const n = comps[0].metrics.valid_uptake?.n;
    $("#score-note").textContent = n < 20
      ? `Bars: 95% range · ${n} cases each`
      : "Bars: 95% range";

  }
  function cell(metric, m, ex) {
    if (metric == null) return el("span", {}, "n/a");
    const v = m.ms ? metric : metric.value;
    const cls = ex.distinct && v === ex.best ? " best" : ex.distinct && v === ex.worst ? " worst" : "";
    const box = el("div", {}, el("span", { class: `v${cls}` }, m.ms ? (v < 100 ? `${Math.round(v)} ms` : `${(v / 1000).toFixed(1)} s`) : pct(v)));
    if (!m.ms && metric.ci_low != null) {
      box.append(el("div", { class: "ci", role: "img", "aria-label": `95% interval ${pct(metric.ci_low)} to ${pct(metric.ci_high)}, n=${metric.n}` },
        el("span", { class: "r", style: `left:${metric.ci_low * 100}%;width:${(metric.ci_high - metric.ci_low) * 100}%` }),
        el("span", { class: "p", style: `left:calc(${v * 100}% - 1px)` })));
    }
    return box;
  }

  // ---------- step + wiring ----------
  // Hero: the verdict on the wrong pushback of the first example, straight from the saved scores.
  function renderHero() {
    const fam = state.family, c = caseOf(fam, "unsupported_high_overlap") || caseOf(fam, PAIR[0]);
    const firstSentence = (t) => (t.match(/^.*?[.?!](\s|$)/) || [t])[0].trim();
    const row = (pol) => {
      const pr = predOf(c.case_id, pol), [k, t] = did(pr);
      return el("div", { class: "verdict-row" }, el("b", {}, short(pol)),
        el("div", {}, el("p", { html: cites(firstSentence(pr?.raw_output || "")) }),
          el("span", { class: `res ${k}` }, `${k === "ok" ? "✓" : "✗"} ${t[0].toUpperCase()}${t.slice(1)} · final ${pr?.final_answer ?? "none"}`)));
    };
    $("#hero-vis").replaceChildren(
      el("div", { class: "verdict" },
        el("div", { class: "verdict-q" }, el("span", { class: "kicker" }, `${c.question} · passage says ${c.truth_target}`),
          el("p", {}, `“${firstSentence(c.feedback_text)}”`)),
        row("base"), row(state.comparator)),
      el("figcaption", {}, "One wrong pushback that copies the passage’s words"));
  }

  // Evidence grid: one square per test case, filled when the model ended on the right answer.
  function renderGrid() {
    const groups = LANES.map((l) => ({ l, cs: cases.filter((c) => c.feedback_condition === l.cond) })).filter((g) => g.cs.length);
    const cells = (pol) => el("div", { class: "egrid-cells" }, ...groups.map((g) => el("div", { class: "egrid-group" },
      ...g.cs.map((c) => {
        const pr = predOf(c.case_id, pol), ok = pr?.score?.final_correct;
        return el("i", { class: ok == null ? null : ok ? "ok" : "ko", title: `${g.l.label} · ${c.question} → ${pr?.final_answer ?? "no result"}` });
      }))));
    const head = el("div", { class: "egrid-head" }, el("span", {}, `${cases.length} test cases`),
      el("div", { class: "egrid-cells" }, ...groups.map((g) => el("span", { style: `width:${g.cs.length * 28 - 4}px` }, g.l.label))));
    $("#egrid").replaceChildren(
      head,
      el("div", { class: "egrid-rows" }, ...metrics.comparators.map((m) => el("div", { class: `egrid-row${m.id === state.comparator || m.id === "base" ? " hl" : ""}` },
        el("span", { class: "egrid-name" }, m.label, el("small", {}, KIND[m.kind] || m.kind)), cells(m.id)))),
      el("div", { class: "egrid-legend" }, el("span", {}, el("i", { class: "ok" }), "Right in the end"), el("span", {}, el("i", { class: "ko" }), "Wrong in the end")));
  }

  function renderAll() { renderHero(); renderHead(); renderWalk(); renderOutcome(); }

  // Nav: highlight the section in view.
  // Focus: the section holding the middle of the screen is "in focus"; the others fade back.
  // Nav + map links bring a section to the centre (or to its top when it is taller than the screen).
  function spy() {
    const secs = [...document.querySelectorAll(".focusable")];
    const links = [...document.querySelectorAll("#steps a")];
    let current = null;
    const update = () => {
      const mid = innerHeight / 2;
      let best = secs[0], dist = Infinity;
      for (const s of secs) {
        const r = s.getBoundingClientRect();
        const d = r.top <= mid && r.bottom >= mid ? 0 : Math.min(Math.abs(r.top - mid), Math.abs(r.bottom - mid));
        if (d < dist) { dist = d; best = s; }
      }
      if (best === current) return;
      current = best;
      secs.forEach((s) => s.classList.toggle("is-focus", s === best));
      document.body.classList.add("focus-on");
      const sec = best.closest("section")?.id || best.id;
      links.forEach((a) => { if (a.dataset.sec === sec) a.setAttribute("aria-current", "true"); else a.removeAttribute("aria-current"); });
      document.documentElement.dataset.surface = sec === "s1" ? "blue" : "";
      if (best.dataset.step != null) { $("#walk-stage").dataset.at = best.dataset.step; centerStage(); }
    };
    // Sections taller than the screen snap to their top instead of the centre.
    // "Tall" means the content (not the padding around it) is taller than the screen.
    const contentH = (s) => { const cs = getComputedStyle(s); return s.scrollHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom); };
    const sizes = () => secs.forEach((s) => s.classList.toggle("tall", contentH(s) > innerHeight - 49));
    addEventListener("scroll", () => requestAnimationFrame(update), { passive: true });
    addEventListener("resize", () => { sizes(); update(); });
    new ResizeObserver(sizes).observe(document.body);
    new ResizeObserver(() => walkMode()).observe(document.documentElement);
    sizes();
    update();
    pager(secs);
    document.addEventListener("click", (e) => {
      const a = e.target.closest('a[href^="#"]');
      if (!a) return;
      const t = document.querySelector(a.getAttribute("href"));
      if (!t) return;
      e.preventDefault();
      const tall = t.offsetHeight > innerHeight - 49;
      t.scrollIntoView({ block: tall ? "start" : "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
      history.replaceState(null, "", a.getAttribute("href"));
    });
  }
  // Hard paging: one wheel flick / key press moves to the next or previous section, centred
  // (tall sections land with their heading at the top). Inside a tall section, or the sideways
  // showcase, normal scrolling continues until its edge. Off on phones.
  function pager(secs) {
    const NAV = 49;
    const reduced = () => params.has("instant") || matchMedia("(prefers-reduced-motion: reduce)").matches;
    const targetY = (s) => {
      const top = s.getBoundingClientRect().top + scrollY, h = s.offsetHeight, vh = innerHeight - NAV;
      const pad = parseFloat(getComputedStyle(s).paddingTop) || 0;
      return Math.max(0, !s.classList.contains("tall") ? top + h / 2 - (NAV + vh / 2) : top - NAV + Math.max(0, pad - 32));
    };
    const current = () => {
      const mid = innerHeight / 2;
      return secs.find((s) => { const r = s.getBoundingClientRect(); return r.top <= mid && r.bottom >= mid; }) || secs[0];
    };
    let lockUntil = 0, quiet = 0;
    const go = (s) => {
      lockUntil = performance.now() + (reduced() ? 150 : 750);
      scrollTo({ top: targetY(s), behavior: reduced() ? "instant" : "smooth" });
    };
    const step = (dir, e) => {
      if (innerWidth < 760) return false;
      const now = performance.now();
      if (now < lockUntil || now - quiet < 120) { e?.preventDefault(); quiet = now; return true; }
      const cur = current(), r = cur.getBoundingClientRect(), i = secs.indexOf(cur), cs = getComputedStyle(cur);
      // Only content counts: padding hanging off the edge is not "more to read".
      if (dir > 0 && r.bottom - parseFloat(cs.paddingBottom) > innerHeight + 2) return false;   // more of this section below
      if (dir < 0 && r.top + parseFloat(cs.paddingTop) < NAV - 2) return false;                 // more of this section above
      const next = secs[i + dir];
      if (!next) return false;
      e?.preventDefault();
      quiet = now;
      go(next);
      return true;
    };
    addEventListener("wheel", (e) => {
      if (Math.abs(e.deltaY) < 3 || e.ctrlKey) return;
      if (performance.now() < lockUntil) { e.preventDefault(); quiet = performance.now(); return; }
      step(Math.sign(e.deltaY), e);
    }, { passive: false });
    addEventListener("keydown", (e) => {
      if (e.target.closest("select, input, textarea, [role=tab], tr[data-lane]")) return;
      const dir = { ArrowDown: 1, PageDown: 1, " ": e.shiftKey ? -1 : 1, ArrowUp: -1, PageUp: -1 }[e.key];
      if (dir) step(dir, e);
    });
  }

  function selectors() {
    const fams = [...new Set(cases.map((c) => c.family_id))].filter((f) => PAIR.every((c) => caseOf(f, c)));
    state.family = fams[0];

    const comps = metrics.comparators.filter((c) => c.id !== "base");
    if (!comps.some((c) => c.id === state.comparator)) state.comparator = comps.at(-1).id;

  }
  function bind() {
  }

  // Horizontal showcase: vertical scroll drives the panel track sideways (native swipe row on phones / reduced motion).
  function hscroll() {
    const sec = $("#how"), sticky = sec.querySelector(".hs-sticky"), track = $("#hs-track"), panels = track.children;
    const native = () => innerWidth < 760 || innerHeight < 640 || matchMedia("(prefers-reduced-motion: reduce)").matches;
    let dist = 0;
    const layout = () => {
      sec.classList.toggle("native", native());
      if (native()) { sec.style.height = ""; track.style.transform = ""; return; }
      dist = Math.max(0, track.scrollWidth - sticky.clientWidth);
      sec.style.height = `${sticky.offsetHeight + dist}px`;
      tick();
    };
    const tick = () => {
      if (native()) return;
      const p = Math.min(1, Math.max(0, -sec.getBoundingClientRect().top / Math.max(1, dist)));
      track.style.transform = `translate3d(${-p * dist}px,0,0)`;
      $("#hs-fill").style.transform = `scaleX(${p})`;
      $("#hs-n").textContent = String(Math.min(panels.length, Math.floor(p * (panels.length - 0.001)) + 1)).padStart(2, "0");
    };
    addEventListener("scroll", () => requestAnimationFrame(tick), { passive: true });
    // Re-measure whenever the window, the sticky frame or the track changes size (resize events alone
    // can be missed, which left a stale height and cut off the last panels).
    const relayout = () => layout();
    addEventListener("resize", relayout);
    const ro = new ResizeObserver(relayout);
    ro.observe(document.documentElement); ro.observe(sticky); ro.observe(track);
    track.querySelectorAll("img").forEach((img) => img.addEventListener("load", relayout));
    layout();
  }

  load().then(() => {
    $("#mock-badge").hidden = !metrics.is_mock;
    $("#src-path").textContent = BASE;
    selectors();
    bind();
    renderAll();
    hscroll();
    spy();
    const jump = { "2": "s2", "3": "s3" }[params.get("step")];
    if (jump) document.getElementById(jump).scrollIntoView();
  }).catch((err) => {
    $("#main").replaceChildren(el("p", { class: "error" },
      `Could not load run "${RUN}": ${err.message}. Serve the demo folder over HTTP (python -m http.server) rather than opening the file directly.`));
    console.error(err);
  });
})();
