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
  // Plain-language names for people who don't know the models; the technical name stays in hover titles.
  const PLAIN = { base: "Currently", never_update: "Never budges", harness: "Careful prompt only", ordinary_sft: "Plain training", safetune: "With EvidenceTune" };
  const label = (id) => PLAIN[id] || (comp(id) || { label: id }).label;

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
  }

  // ---------- 01: the conversation ----------
  // Two chat windows play the same conversation; they split at the reply. Everything comes from the saved run.
  const cap = (t) => t[0].toUpperCase() + t.slice(1);
  let convoTimers = [], convoWins = [], convoPlayed = false;
  function renderWalk() {
    const fam = state.family, T = state.comparator;
    const c = caseOf(fam, "unsupported_high_overlap") || caseOf(fam, "valid_low_overlap");
    const pb = predOf(c.case_id, "base"), pt = predOf(c.case_id, T);
    const ov = overlap(c.feedback_text, c.context);
    const cited = new Set(citedIds(pt).concat((pt?.clarification_turn?.raw_output || "").match(/S\d+/g) || []));
    const fileName = `${String(c.source?.source_id || "passage").replace(/^mock-doc-/, "")}.pdf`;

    $("#walk-lead").textContent = "You ask an AI a question and attach a document. Then you push back with the wrong answer. Here’s the same chat with the AI as it ships today, and with EvidenceTune.";

    const row = (who, ...kids) => el("div", { class: `chat-row ${who}` }, el("i", { class: "av", "aria-hidden": "true" }), el("div", { class: "bubbles" }, ...kids));
    const bubble = (cls, ...kids) => el("div", { class: `bubble ${cls}` }, ...kids);
    // The attachment: a file card with a little page that shows the passage, its deciding line highlighted.
    const file = () => el("div", { class: "file", title: spans(c.context).map((x) => x.text).join(" ") },
      el("div", { class: "file-page", "aria-hidden": "true" },
        ...spans(c.context).map((x) => el("p", { class: cited.has(x.id) ? "hl" : null }, x.text))),
      el("div", { class: "file-meta" }, el("i", { class: "file-ico", "aria-hidden": "true" }, "PDF"),
        el("span", {}, el("b", {}, fileName), el("small", {}, "1 page"))));
    const shared = [
      { from: "user", make: () => row("user", bubble("q", c.question), file()) },
      { from: "ai", make: () => row("ai", bubble("a", el("b", {}, c.original_answer), ", according to the document.")) },
      { from: "user", make: () => row("user push", bubble("q", el("span", { html: ov.html })), el("small", { class: "note" }, "Underlined words are copied from the document")) },
    ];
    const replies = (p) => [
      { from: "ai", make: () => row("ai", bubble("a", el("span", { html: cites(p?.raw_output || "") }))) },
      ...(p?.clarification_turn ? [
        { from: "user", make: () => row("user", bubble("q", p.clarification_turn.user_reply ?? "")) },
        { from: "ai", make: () => row("ai", bubble("a", el("span", { html: cites(p.clarification_turn.raw_output) }))) }] : []),
    ];
    const win = (pol, p, who) => {
      const [k, t] = did(p);
      const list = el("div", { class: "cw-list" });
      const verdict = el("div", { class: `cw-verdict ${k}` }, el("b", {}, k === "ok" ? "✓" : "✗"), `${cap(t)} · ends on `, el("strong", {}, p?.final_answer ?? "none"));
      const w = el("article", { class: `cw ${who}`, "aria-label": `${label(pol)}: ${cap(t)}, ends on ${p?.final_answer}` },
        el("header", { class: "cw-head" }, el("i", { class: "cw-av", "aria-hidden": "true" }),
          el("span", {}, el("b", {}, label(pol)), el("small", {}, who === "base" ? "the AI as it ships today" : "after EvidenceTune training"))),
        list, verdict);
      return { w, list, verdict, msgs: [...shared, ...replies(p)] };
    };
    convoWins = [win("base", pb, "base"), win(T, pt, "tuned")];
    $("#convo").replaceChildren(...convoWins.map((x) => x.w));
    if (convoPlayed) playConvo(); else convoWins.forEach((x) => x.list.replaceChildren());

    // what comes after: all three kinds of pushback, side by side
    $("#after-lead").textContent = "Refusing to budge isn’t the goal: when the pushback is backed by the document, a good model should change its answer. Today’s model only scores on the correct one because it agrees with everyone.";
    const lanes = LANES.filter((l) => caseOf(fam, l.cond));
    $("#w-summary").replaceChildren(
      el("div", { class: "big-grid" },
        el("span", {}), el("b", {}, short("base")), el("b", {}, short(T)),
        ...lanes.flatMap((l) => { const cs = caseOf(fam, l.cond);
          const cell = (pol) => { const [k, t] = did(predOf(cs.case_id, pol)); return el("i", { class: `bg-${k}`, title: cap(t) }, el("strong", {}, k === "ok" ? "✓" : "✗")); };
          return [el("span", {}, l.label), cell("base"), cell(T)]; })));
  }

  // Play: people's messages pop in, the AI shows typing dots first. Both windows share the timing, so they
  // stay in step until the replies split.
  function playConvo() {
    convoPlayed = true;
    convoTimers.forEach(clearTimeout); convoTimers = [];
    const at = (ms, fn) => convoTimers.push(setTimeout(fn, ms));
    const add = (w, node) => { w.list.append(node); w.list.scrollTo({ top: w.list.scrollHeight, behavior: "smooth" }); };
    const typing = () => el("div", { class: "chat-row ai typing-row" }, el("i", { class: "av", "aria-hidden": "true" }),
      el("div", { class: "bubbles" }, el("div", { class: "bubble a typing", "aria-label": "typing" }, el("i"), el("i"), el("i"))));
    convoWins.forEach((w) => { w.list.replaceChildren(); w.verdict.classList.remove("show"); });
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      convoWins.forEach((w) => { w.msgs.forEach((m) => w.list.append(m.make())); w.verdict.classList.add("show"); });
      return;
    }
    convoWins.forEach((w) => {
      let t = 500;
      w.msgs.forEach((m) => {
        if (m.from === "ai") {
          at(t, () => add(w, typing()));
          t += 1200;
          at(t, () => { w.list.querySelector(".typing-row")?.remove(); add(w, m.make()); });
          t += 1100;
        } else {
          at(t, () => add(w, m.make()));
          t += 1700;
        }
      });
      at(t, () => w.verdict.classList.add("show"));
    });
  }
  function convoWatch() {
    const box = $("#convo");
    $("#replay").addEventListener("click", playConvo);
    if (!("IntersectionObserver" in window)) { playConvo(); return; }
    const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { io.disconnect(); playConvo(); } }, { threshold: 0.45 });
    io.observe(box);
  }
  // The old scroll walkthrough's layout hooks; nothing to lay out now.
  function walkMode() {}
  function centerStage() {}

  // ---------- outcome stage ----------
  function renderOutcome() {
    const base = comp("base"), cur = comp(state.comparator) || metrics.comparators.at(-1);
    const card = (t, k, dir) => {
      const a = base?.metrics[k], b = cur?.metrics[k];
      return el("div", { class: `card${k === "uur" ? " lead" : ""}`, title: `${short("base")} → ${short(cur.id)}, ${dir} is better` },
        el("small", {}, `${t} ${dir === "lower" ? "↓" : "↑"}`), el("b", {}, a && b ? `${pct(a.value)} → ${pct(b.value)}` : "n/a"));
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
      el("th", { scope: "row", title: c.label }, label(c.id), el("small", {}, KIND[c.kind] || c.kind)),
      ...METRICS.map((m) => el("td", { "data-label": `${m.label} ${m.better === "high" ? "↑" : "↓"}` }, cell(c.metrics[m.key], m, ext[m.key]))))));
    $("#scoreboard").replaceChildren(head, body);
    $("#table-path").textContent = `${BASE}metrics.json`;
    renderGrid();
    // Showcase panel 05: base vs tuned on the three scores, as bars
    const sb = $("#hs-score");
    if (sb) sb.replaceChildren(...[["valid_uptake", "Accepts correct pushback", "↑"], ["uur", "Gives in to wrong pushback", "↓"], ["final_accuracy", "Right in the end", "↑"]].map(([k, t, d]) => {
      const a = base?.metrics[k]?.value, b = cur?.metrics[k]?.value;
      return el("div", { class: "snum", title: `${short("base")} → ${short(cur.id)} on ${metrics.dataset.n_cases} test cases` },
        el("span", {}, `${t} ${d}`), el("b", {}, a == null ? "n/a" : pct(a), el("i", {}, " → "), b == null ? "n/a" : pct(b)));
    }));
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

  const d_note = () => `${metrics.dataset.n_cases} test cases · read the three together`;

  // ---------- step + wiring ----------
  // Hero metaphor: the answer is a clock hand. One wrong pushback tries to turn it; the base model's hand
  // swings, the tuned one twitches and holds. Under each clock, a tear-off calendar: every test case is a
  // day, crossed off when the model ended wrong. Everything comes from the saved scores.
  const SVGNS = "http://www.w3.org/2000/svg";
  function svg(tag, attrs = {}, ...kids) {
    const n = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(attrs)) if (v != null) n.setAttribute(k, v);
    for (const k of kids.flat()) if (k != null) n.append(k.nodeType ? k : document.createTextNode(String(k)));
    return n;
  }
  const sameAns = (a, b) => a != null && b != null &&
    String(a).toLowerCase().replace(/[^\p{L}\p{N}]/gu, "") === String(b).toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
  let heroTimer = 0;

  function clock(c, pr) {
    const at = (deg, r) => { const a = (deg - 90) * Math.PI / 180; return [80 + r * Math.cos(a), 80 + r * Math.sin(a)]; };
    const A = -50, B = 50; // first answer at ten to, the pushback's answer at ten past
    const face = svg("svg", { viewBox: "0 0 160 160", class: "clock", "aria-hidden": "true" });
    face.append(svg("circle", { cx: 80, cy: 80, r: 74, class: "c-rim" }));
    for (let t = 0; t < 12; t++) {
      const [x1, y1] = at(t * 30, 64), [x2, y2] = at(t * 30, 72);
      face.append(svg("line", { x1, y1, x2, y2, class: "c-tick big" }));
    }
    const mark = (deg, text, cls) => {
      const [x, y] = at(deg, 47);
      face.append(svg("text", { x, y: y + 5, "text-anchor": "middle", class: `c-lbl ${cls}` }, String(text).slice(0, 8)));
    };
    const firstIsTruth = sameAns(c.original_answer, c.truth_target);
    mark(A, c.original_answer, firstIsTruth ? "truth" : "");
    if (firstIsTruth) { const [x, y] = at(A, 47); face.append(svg("rect", { x: x - 3, y: y + 10, width: 6, height: 6, class: "c-fact" })); }
    const hasPush = c.correction_target != null && !sameAns(c.correction_target, c.original_answer);
    if (hasPush) mark(B, c.correction_target, "push");
    const final = pr?.final_answer;
    const end = sameAns(final, c.original_answer) ? A : hasPush && sameAns(final, c.correction_target) ? B : 180;
    if (end === 180 && final != null) mark(180, final, "");
    const hand = svg("g", { class: "c-hand" }, svg("line", { x1: 80, y1: 90, x2: 80, y2: 50 }), svg("rect", { x: 76, y: 44, width: 8, height: 8 }));
    face.append(hand, svg("rect", { x: 75, y: 75, width: 10, height: 10, class: "c-hub" }));
    return { face, hand, start: A, end, pull: hasPush ? B : A + 40 };
  }

  // Loop: rest on the first answer, pushback arrives, hand swings (or twitches and returns), pause, repeat.
  function animateClocks(fig, items) {
    clearTimeout(heroTimer);
    const set = (it, deg) => (it.hand.style.transform = `rotate(${deg}deg)`);
    items.forEach((it) => set(it, it.start));
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      items.forEach((it) => set(it, it.end)); fig.classList.add("is-push"); return;
    }
    const run = () => {
      fig.classList.remove("is-push");
      items.forEach((it) => set(it, it.start));
      heroTimer = setTimeout(() => {
        fig.classList.add("is-push");
        items.forEach((it) => set(it, it.end === it.start ? it.start + (it.pull - it.start) * 0.22 : it.end));
        heroTimer = setTimeout(() => {
          items.forEach((it) => { if (it.end === it.start) set(it, it.start); });
          heroTimer = setTimeout(run, 3400);
        }, 420);
      }, 1100);
    };
    requestAnimationFrame(run);
  }

  function tearoff(pol) {
    const laneOf = (cs) => (LANES.find((l) => l.cond === cs.feedback_condition) || { label: cs.feedback_condition }).label;
    let crossed = 0;
    const days = cases.map((cs, i) => {
      const [k, t] = did(predOf(cs.case_id, pol));
      if (k === "ko") crossed++;
      return el("i", { class: k || null, title: `Case ${i + 1}: ${cs.question} · ${laneOf(cs)} · ${t}` }, k === "ok" ? "✓" : k === "ko" ? "✗" : "");
    });
    return el("div", { class: "tear", style: `--cols:${cases.length > 42 ? 14 : 7}`, title: `${crossed} of ${cases.length} test cases ended wrong`,
      role: "img", "aria-label": `Every test case as a calendar day: ${crossed} of ${cases.length} crossed off` },
      el("div", { class: "tear-rings", "aria-hidden": "true" }, el("i"), el("i"), el("i"), el("i")),
      el("div", { class: "tear-head", "aria-hidden": "true" }, `Tested on ${cases.length} questions like this`),
      el("div", { class: "tear-grid", "aria-hidden": "true" }, days));
  }

  function renderHero() {
    const fam = state.family, c = caseOf(fam, "unsupported_high_overlap") || caseOf(fam, PAIR[0]);
    const firstSentence = (t) => (t.match(/^.*?[.?!](\s|$)/) || [t])[0].trim();
    const items = [];
    const col = (pol) => {
      const pr = predOf(c.case_id, pol), [k, t] = did(pr), ck = clock(c, pr);
      if (k) ck.face.classList.add(k);
      items.push(ck);
      return el("article", { class: "dial", title: `${label(pol)}: ${t}, ends on ${pr?.final_answer ?? "none"}` },
        el("header", {}, el("b", {}, short(pol)),
          el("span", { class: `verdict-mark ${k}`, "aria-label": `${cap(t)}, ends on ${pr?.final_answer ?? "none"}` }, k === "ok" ? "✓" : "✗")),
        ck.face,
        tearoff(pol));
    };
    const fig = $("#hero-vis");
    fig.replaceChildren(
      el("p", { class: "hv-q" }, `${c.question} `, el("span", {}, "The passage says "), el("b", {}, c.truth_target)),
      el("p", { class: "hv-push" }, el("small", {}, "Someone insists"), `“${firstSentence(c.feedback_text)}”`),
      el("div", { class: "dials" }, col("base"), col(state.comparator)),
      el("figcaption", { class: "sr" }, `${c.question} The passage says ${c.truth_target}. The clock hand is each model's answer; a wrong pushback tries to turn it. Each calendar day is one test case, crossed off when the model ended wrong.`));
    animateClocks(fig, items);
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
        el("span", { class: "egrid-name", title: `${m.label} · ${KIND[m.kind] || m.kind}` }, label(m.id)), cells(m.id)))),
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
    if ("scrollRestoration" in history) history.scrollRestoration = "manual";
    const targetY = (s) => {
      const top = s.getBoundingClientRect().top + scrollY, h = s.offsetHeight, vh = innerHeight - NAV;
      const pad = parseFloat(getComputedStyle(s).paddingTop) || 0;
      return Math.max(0, !s.classList.contains("tall") ? top + h / 2 - (NAV + vh / 2) : top - NAV + Math.max(0, pad - 32));
    };
    const current = () => {
      const mid = innerHeight / 2;
      return secs.find((s) => { const r = s.getBoundingClientRect(); return r.top <= mid && r.bottom >= mid; }) || secs[0];
    };
    // Can this section still scroll natively in direction dir? (content only; padding hanging off an edge doesn't count)
    const moreInside = (cur, dir) => {
      const r = cur.getBoundingClientRect(), cs = getComputedStyle(cur);
      return dir > 0 ? r.bottom - parseFloat(cs.paddingBottom) > innerHeight + 2 : r.top + parseFloat(cs.paddingTop) < NAV - 2;
    };

    let moving = false, until = 0, lastEvt = 0, tail = false, acc = 0, accDir = 0;
    const settle = () => { moving = false; };
    addEventListener("scrollend", () => { if (moving && performance.now() > until - 600) settle(); });
    const go = (s) => {
      moving = true; tail = true;
      until = performance.now() + (reduced() ? 150 : 1100);         // hard cap if scrollend never fires
      setTimeout(() => { if (performance.now() >= until) settle(); }, (reduced() ? 150 : 1100) + 20);
      scrollTo({ top: targetY(s), behavior: reduced() ? "instant" : "smooth" });
    };
    const jump = (dir) => {
      const cur = current(), next = secs[secs.indexOf(cur) + dir];
      if (!next) return false;
      go(next);
      return true;
    };

    addEventListener("wheel", (e) => {
      if (e.ctrlKey || innerWidth < 760) return;
      const now = performance.now(), gap = now - lastEvt;
      lastEvt = now;
      const dy = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? innerHeight : 1);
      if (!dy) return;
      const dir = Math.sign(dy);
      // 1. While a jump is animating, swallow everything.
      if (moving) { e.preventDefault(); return; }
      // 2. Momentum that keeps arriving right after a jump is the same gesture: swallow it until it pauses.
      if (tail && gap < 180) { e.preventDefault(); return; }
      tail = false;
      // 3. Inside a section taller than the screen, scroll normally until its edge.
      const cur = current();
      if (moreInside(cur, dir)) { acc = 0; return; }
      // 4. Otherwise collect small trackpad steps into one deliberate jump.
      e.preventDefault();
      if (dir !== accDir || gap > 300) { acc = 0; accDir = dir; }
      acc += dy;
      if (Math.abs(acc) >= 40) { acc = 0; jump(dir); }
    }, { passive: false });

    addEventListener("keydown", (e) => {
      if (innerWidth < 760 || e.target.closest("select, input, textarea, [role=tab], tr[data-lane]")) return;
      const dir = { ArrowDown: 1, PageDown: 1, " ": e.shiftKey ? -1 : 1, ArrowUp: -1, PageUp: -1 }[e.key];
      if (!dir) return;
      if (moving) { e.preventDefault(); return; }
      if (moreInside(current(), dir)) return;
      e.preventDefault();
      jump(dir);
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
      // Counter shows the panel nearest the middle of the screen
      const mid = innerWidth / 2;
      let best = 0, bd = Infinity;
      [...panels].forEach((el, i) => { const r = el.getBoundingClientRect(), d = Math.abs(r.left + r.width / 2 - mid); if (d < bd) { bd = d; best = i; } });
      $("#hs-n").textContent = String(best + 1).padStart(2, "0");
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
    convoWatch();
    spy();
    const jump = { "2": "s2", "3": "s3" }[params.get("step")];
    if (jump) document.getElementById(jump).scrollIntoView();
  }).catch((err) => {
    $("#main").replaceChildren(el("p", { class: "error" },
      `Could not load run "${RUN}": ${err.message}. Serve the demo folder over HTTP (python -m http.server) rather than opening the file directly.`));
    console.error(err);
  });
})();
