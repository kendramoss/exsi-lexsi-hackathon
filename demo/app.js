// EvidenceTune demo. Reads saved artifacts only:
//   data/results/<run_id>/cases.jsonl, predictions.jsonl, metrics.json
// ?run=<run_id> (default mock-smoke), ?step=2|3 jumps to a section. Never recomputes metrics: per-case verdicts
// come from the `score` block in predictions.jsonl, and every claim on screen is conditional on it.

(() => {
  "use strict";

  const params = new URLSearchParams(location.search);
  const RUN = (params.get("run") || "final-fresh").replace(/[^a-z0-9_.-]/gi, "");
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
  const state = { step: 0, family: null, comparator: "safetune", ref: "base", lane: "unsup" };
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
  // The nav bar's height comes from the --nav CSS variable, so JS and CSS never disagree.
  const navH = () => parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--nav")) || 49;
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
  // Chat bubbles show what the model says, not its machine-readable header lines (ACTION: / ANSWER:).
  const said = (text) => String(text).split(/\r?\n/).filter((l) => !/^\s*(ACTION|ANSWER)\s*:/i.test(l)).join(" ").trim() || String(text);
  const cites = (text) => esc(said(text)).replace(/\[(S\d+)\]/g, '<span class="cite">$1</span>');

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
  // The pushback's claim: only the excerpt it quotes is highlighted, since that is what the model has to check.
  function quoted(text) {
    return esc(text).replace(/(&quot;|"|“)(.+?)(&quot;|"|”)/, (m, o, q, c) => `${o}<mark class="claim">${q}</mark>${c}`);
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
    if (a === "clarify" && (s.clarification_resolved || (s.clarification_resolved == null && s.action_acceptable))) return ["clarify", "Asked for a source", "the right call here"];
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
    if (s.clarification_resolved || (s.clarification_resolved == null && s.action_acceptable)) return ["ok", "asks for a source"];
    return ["ko", "asks, but ends up wrong"];
  }

  // Screen 3 verdict under each reply: a line icon for what it did, a few words, and right/wrong at the end.
  const VICON = {
    turn: ["M9 14 4 9l5-5", "M4 9h10.5a5.5 5.5 0 0 1 0 11H11"],                       // switched its answer
    hold: ["M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"],                               // stayed on its answer
    look: ["M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z", "m20 20-3.5-3.5"],                  // asked for the source
  };
  function verdictLine(p, k) {
    const icon = (name) => svg("svg", { viewBox: "0 0 24 24", class: "vi", "aria-hidden": "true" }, ...VICON[name].map((d) => svg("path", { d })));
    const ans = el("strong", {}, p?.final_answer ?? "no answer");
    const a = p?.parsed_action.action, s = p?.score || {};
    let ic = "hold", words;
    if (!p) words = ["No result"];
    else if (a === "update") { ic = "turn"; words = [s.unwarranted_update ? "Switched to " : "Changed to ", ans]; }
    else if (a === "clarify") { ic = "look"; words = s.unnecessary_clarification ? ["Asked when it didn’t need to"] : ["Asked for proof, stayed on ", ans]; }
    else words = [k === "ok" ? "Stayed on " : "Ignored the fix, stayed on ", ans];
    return [icon(ic), el("span", { class: "vt" }, ...words), el("em", {}, k === "ok" ? "right" : "wrong")];
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
    const pb = predOf(c.case_id, state.ref), pt = predOf(c.case_id, T);
    const ov = overlap(c.feedback_text, c.context);
    const cited = new Set(citedIds(pt).concat((pt?.clarification_turn?.raw_output || "").match(/S\d+/g) || []));
    const fileName = `${String(c.source?.source_id || "passage").replace(/^mock-doc-/, "")}.pdf`;

    $("#walk-lead").textContent = "You ask with a document attached, then push back with the wrong answer. Watch where they split.";
    const [kb] = did(pb), [kt] = did(pt);
    const ending = kb === "ko" && kt === "ok" ? "Only EvidenceTune holds" : "See who holds";
    const tl = $("#convo-tl");
    if (tl) tl.replaceChildren(...["Ask, with a PDF", `AI answers ${c.original_answer}`, `You insist: ${c.correction_target}`, "The two AIs split", ending]
      .map((t, i) => el("li", { "data-step": i + 1 }, t)));

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
      { from: "user", make: () => row("user push", bubble("q", el("span", { html: quoted(c.feedback_text) }))) },
    ];
    const replies = (p) => [
      { from: "ai", make: () => row("ai", bubble("a", el("span", { html: cites(p?.raw_output || "") }))) },
      ...(p?.clarification_turn ? [
        { from: "user", make: () => row("user", bubble("q", p.clarification_turn.user_reply ?? "")) },
        { from: "ai", make: () => row("ai", bubble("a", el("span", { html: cites(p.clarification_turn.raw_output) }))) }] : []),
    ];
    // One thread while the two AIs are identical; it branches at the first reply where they differ.
    const branch = (pol, p, who) => {
      const [k, t] = did(p);
      const list = el("div", { class: "branch-list" });
      const verdict = el("div", { class: `cw-verdict v4 ${k}` }, ...verdictLine(p, k));
      const node = el("div", { class: `branch ${who}`, "aria-label": `${label(pol)}: ${cap(t)}, ends on ${p?.final_answer}` },
        el("header", { class: "branch-head" }, el("i", { class: "cw-av", "aria-hidden": "true" }), el("b", {}, label(pol))), list, verdict);
      return { node, list, verdict, msgs: replies(p) };
    };
    const trunk = el("div", { class: "trunk" });
    const fork = el("div", { class: "fork", "aria-hidden": "true" },
      el("i", { class: "stem" }), el("i", { class: "l" }), el("i", { class: "r" }),
      el("span", { class: "fork-tag" }, "They split here"));
    const bL = branch(state.ref, pb, "base"), bR = branch(T, pt, "tuned");
    convoWins = { trunk, fork, shared, branches: [bL, bR] };
    $("#convo").classList.add("flow");
    $("#convo").replaceChildren(trunk, fork, el("div", { class: "branches" }, bL.node, bR.node));
    // Centring is pure CSS (two flexible spacers in #convo, see style.css): centred while the chat fits,
    // bottom-anchored once it overflows. A new row opening its room only ever pushes earlier messages up.
    const box = $("#convo");
    if (!box._resize) {
      // The pushback's slide-to-centre is a pixel offset; redo it (without animating) when the window changes.
      let rt = 0;
      box._resize = () => { cancelAnimationFrame(rt); rt = requestAnimationFrame(() => { if (convoStepAt >= 4) centerPush(false); }); };
      new ResizeObserver(box._resize).observe(box);
    }
    convoShow(Math.max(1, convoStepAt));

    renderListen();
    renderFair();
  }

  // Scroll-stepped conversation (desktop): step n shows
  //   1 the question with its attachment · 2 the AI's answer · 3 the pushback
  //   4 the split, each AI's first reply · 5 the rest of each thread and the verdicts
  const CONVO_STEPS = 5;
  let convoStepAt = 0;
  // A typing bubble on the sender's side: three dots, like a real chat.
  const typingRow = (who) => el("div", { class: `chat-row ${who} typing-row` }, el("i", { class: "av", "aria-hidden": "true" }),
    el("div", { class: "bubbles" }, el("div", { class: `bubble ${who === "ai" ? "a" : "q"} typing`, "aria-label": "typing" }, el("i"), el("i"), el("i"))));

  // At the split the pushback slides to the centre so the fork's stem grows straight out of it.
  function centerPush(animate) {
    const trunk = convoWins.trunk, bub = trunk && trunk.querySelector(".chat-row.push .bubble");
    if (!bub) return;
    const z = parseFloat(getComputedStyle($("#convo")).zoom) || 1;
    bub.style.transition = "none"; bub.style.translate = "0px 0px";
    const tr = trunk.getBoundingClientRect(), br = bub.getBoundingClientRect();
    const dx = ((tr.left + tr.width / 2) - (br.left + br.width / 2)) / z;
    void bub.offsetWidth;
    bub.style.transition = animate ? `translate 650ms ${EASE}` : "none";
    bub.style.translate = `${dx}px 0px`;
  }

  // One step forward or back, from the ‹ › controls or the ← → keys.
  let convoVisited = false;   // set once the reader has reached the chat; after that it resumes where it was
  // Arriving at the chat plays it through on its own, a step at a time, so a reader who only scrolls still sees
  // the two AIs split. It stops as soon as they take over with ‹ › or ← →, or leave the screen.
  let autoTimer = 0;
  const AUTO_HOLD = [0, 2400, 2000, 2400, 3600];   // how long each step stays up before the next (step 1 to 4)
  const stopAuto = () => { clearTimeout(autoTimer); autoTimer = 0; };
  function autoPlayConvo() {
    stopAuto();
    let n = 1;
    const tick = () => {
      if (!$("#s1")?.classList.contains("is-focus") && n > 1) { autoTimer = 0; return; }
      convoShow(n, n === 1 ? 750 : 0);
      if (n >= CONVO_STEPS) { autoTimer = 0; return; }
      autoTimer = setTimeout(tick, AUTO_HOLD[n] + (n === 1 ? 750 : 0));
      n++;
    };
    tick();
  }
  function convoStep(dir) {
    stopAuto();
    convoVisited = true;
    const n = convoStepAt + dir;
    if (n < 1 || n > CONVO_STEPS) return false;
    convoShow(n);
    return true;
  }
  // The step controls and the rail's step label follow the current step.
  function convoUi(n) {
    document.querySelectorAll("#convo-tl li").forEach((li) => {
      const k = +li.dataset.step;
      li.classList.toggle("done", k < n);
      li.classList.toggle("now", k === n);
      if (k === n) li.setAttribute("aria-current", "step"); else li.removeAttribute("aria-current");
    });
    const hint = $("#convo-step");
    if (hint) hint.textContent = `Step ${n} of ${CONVO_STEPS}`;
    const prev = $("#convo-prev"), next = $("#convo-next"), dots = $("#convo-dots");
    if (prev) prev.disabled = n <= 1;
    if (next) next.disabled = n >= CONVO_STEPS;
    if (dots) dots.replaceChildren(...Array.from({ length: CONVO_STEPS }, (_, i) => el("i", { class: i + 1 < n ? "done" : i + 1 === n ? "on" : null })));
  }

  // Going back plays the step in reverse instead of snapping: the newest messages close up, and leaving the
  // split, the replies fade, the fork and columns shrink away while the earlier messages unfold again.
  const EASE = "cubic-bezier(.45, 0, .2, 1)";   // ease in and out, so folding and unfolding read the same both ways
  // Fold the earlier messages away (or back open) using their real heights, so the motion is even from start
  // to end instead of racing through a generous max-height.
  function foldRows(trunk, fold, anims) {
    const rows = [...trunk.children].filter((r) => !r.classList.contains("push"));
    rows.forEach((r) => (r.style.transition = "none"));
    if (!fold) trunk.classList.remove("past");
    const hs = rows.map((r) => r.scrollHeight);
    if (fold) trunk.classList.add("past");
    rows.forEach((r, i) => {
      const open = { maxHeight: `${hs[i]}px`, opacity: 1, marginTop: "0px" }, shut = { maxHeight: "0px", opacity: 0, marginTop: "-10px" };
      const a = r.animate(fold ? [open, shut] : [shut, open], { duration: 650, easing: EASE });
      anims.push(a);
      a.finished.then(() => (r.style.transition = "")).catch(() => {});
    });
  }
  function convoBack(from, to) {
    const W = convoWins, convoEl = $("#convo");
    const at = (ms, fn) => convoTimers.push(setTimeout(fn, ms));
    const keep = (a) => (W.backAnims.push(a), a);
    const exitRow = (r) => {
      r.style.overflow = "clip";
      const a = keep(r.animate([{ height: `${r.offsetHeight}px`, opacity: 1, marginTop: "0px" },
        { height: "0px", opacity: 0, marginTop: r.previousElementSibling ? "-10px" : "0px" }], { duration: 420, easing: EASE, fill: "forwards" }));
      a.finished.then(() => r.remove()).catch(() => {});
    };
    if (from === 5) W.branches.forEach((b) => { b.verdict.classList.remove("show"); [...b.list.children].slice(1).forEach(exitRow); });
    if (from === 4) {
      W.branches.forEach((b) => { b.node.classList.remove("show"); [...b.list.children].forEach(exitRow); });
      at(300, () => {
        const brs = convoEl.querySelector(".branches");
        const shrink = (node, ms) => { node.style.overflow = "clip"; return keep(node.animate([{ height: `${node.offsetHeight}px` }, { height: "0px" }], { duration: ms, easing: EASE, fill: "forwards" })); };
        W.fork.classList.remove("show");
        const done = Promise.all([shrink(W.fork, 500).finished, shrink(brs, 600).finished]);
        foldRows(W.trunk, false, W.backAnims);                  // the earlier messages unfold as the split closes
        const bub = W.trunk.querySelector(".chat-row.push .bubble");
        if (bub) { bub.style.transition = `translate 650ms ${EASE}`; bub.style.translate = "0px 0px"; }
        done.then(() => {
          if (convoStepAt !== to) return;
          convoEl.classList.remove("split");
          W.backAnims.forEach((a) => a.cancel()); W.backAnims = [];
          W.fork.style.overflow = brs.style.overflow = "";
          W.branches.forEach((b) => b.list.replaceChildren());
        }).catch(() => {});
      });
    }
    if (from === 3 || from === 2) { const r = W.trunk.children[from - 1]; if (r) exitRow(r); }
  }

  function convoShow(n, wait = 0) {
    const W = convoWins;
    if (!W.trunk) return;
    convoTimers.forEach(clearTimeout); convoTimers = [];
    (W.backAnims || []).forEach((a) => a.cancel()); W.backAnims = [];
    W.fork.style.overflow = ""; const brs = $("#convo .branches"); if (brs) brs.style.overflow = "";
    const prev = convoStepAt;
    convoStepAt = n; convoPlayed = true;
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const at = (ms, fn) => convoTimers.push(setTimeout(fn, ms));
    if (!still && n === prev - 1) { convoBack(prev, n); convoUi(n); return; }
    // Messages already seen appear at once; new ones are typed (dots), then sent (a short rise and fade in).
    const deliver = (list, items, t0 = 0) => {
      list.replaceChildren();
      let t = t0;
      items.forEach(({ m, step }) => {
        if (still || step <= prev) { list.append(m.make()); return; }
        const who = m.from === "ai" ? "ai" : "user";
        // no typing dots: each message pops in, a beat apart, like a chat app
        t += step === 1 ? 300 : who === "ai" ? 700 : 450;
        at(t, () => { const node = m.make(); node.classList.add("sent"); list.append(node); });
        t += 200;
      });
      return t;
    };
    deliver(W.trunk, W.shared.slice(0, Math.min(n, 3)).map((m, i) => ({ m, step: i + 1 })), wait);
    const split = n >= 4;
    // Arriving at the split, play it in order instead of all at once:
    // the earlier messages fold away, then the fork draws, then the two columns rise in, then the replies pop.
    const staged = split && prev < 4 && !still;
    const convoEl = $("#convo");
    // deliver() just rebuilt the rows; let them lay out at full height first, or the fold has no "before"
    // state and the earlier messages vanish in one frame instead of folding away
    if (staged) { void W.trunk.offsetHeight; foldRows(W.trunk, true, W.backAnims); }
    else W.trunk.classList.toggle("past", split);
    // Arriving at the split it slides over (animated); on any later step the rebuilt bubble is centred in the
    // same frame, or it shows for one frame at its default right-hand spot and visibly flicks sideways.
    if (split && staged) at(0, () => centerPush(true));
    else if (split) centerPush(false);
    if (staged) {
      convoEl.classList.remove("split"); W.fork.classList.remove("show");
      W.branches.forEach((b) => b.node.classList.remove("show"));
      at(500, () => { convoEl.classList.add("split"); W.fork.classList.add("show"); });
      at(1100, () => W.branches.forEach((b) => b.node.classList.add("show")));
    } else {
      convoEl.classList.toggle("split", split);
      W.fork.classList.toggle("show", split);
    }
    W.branches.forEach((b) => {
      if (!staged) b.node.classList.toggle("show", split);
      const count = n >= 5 ? b.msgs.length : split ? 1 : 0;
      const end = deliver(b.list, b.msgs.slice(0, count).map((m, i) => ({ m, step: i === 0 ? 4 : 5 })), staged ? 1500 : 0);
      b.verdict.classList.remove("show");
      if (n >= 5) { if (still || prev >= 5) b.verdict.classList.add("show"); else at(end + 200, () => b.verdict.classList.add("show")); }
    });
    convoUi(n);
  }

  // Play: people's messages pop in, the AI shows typing dots first. Both windows share the timing, so they
  // stay in step until the replies split.
  function playConvo() {
    convoPlayed = true;
    convoTimers.forEach(clearTimeout); convoTimers = [];
    const W = convoWins;
    if (!W.trunk) return;
    const at = (ms, fn) => convoTimers.push(setTimeout(fn, ms));
    W.trunk.replaceChildren(); W.trunk.classList.remove("past"); $("#convo").classList.remove("split"); W.fork.classList.remove("show");
    W.branches.forEach((b) => { b.list.replaceChildren(); b.verdict.classList.remove("show"); b.node.classList.remove("show"); });
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      W.shared.forEach((m) => W.trunk.append(m.make())); $("#convo").classList.add("split"); W.fork.classList.add("show");
      W.branches.forEach((b) => { b.node.classList.add("show"); b.msgs.forEach((m) => b.list.append(m.make())); b.verdict.classList.add("show"); });
      return;
    }
    // people's messages pop in; the AI shows typing dots first
    const play = (list, msgs, t) => {
      msgs.forEach((m) => {
        const who = m.from === "ai" ? "ai" : "user";
        at(t, () => { const node = m.make(); node.classList.add("sent"); list.append(node); }); t += who === "ai" ? 1200 : 900;
      });
      return t;
    };
    let t = play(W.trunk, W.shared, 400);
    at(t, () => { W.trunk.classList.add("past"); $("#convo").classList.add("split"); W.fork.classList.add("show"); }); t += 900;
    at(t, () => W.branches.forEach((b) => b.node.classList.add("show"))); t += 300;
    W.branches.forEach((b) => { const end = play(b.list, b.msgs, t); at(end, () => b.verdict.classList.add("show")); });
  }
  function convoWatch() {
    const box = $("#convo");
    $("#replay").addEventListener("click", playConvo);
    // ‹ › step the chat; a short lock keeps a double click from skipping a step mid-animation
    let lock = 0;
    const press = (dir) => { const now = performance.now(); if (now < lock) return; if (convoStep(dir)) lock = now + 380; };
    $("#convo-prev")?.addEventListener("click", () => press(-1));
    $("#convo-next")?.addEventListener("click", () => press(1));
    if (!("IntersectionObserver" in window)) { playConvo(); return; }
    const io = new IntersectionObserver((es) => { if (innerWidth < 760 && es.some((e) => e.isIntersecting)) { io.disconnect(); playConvo(); } }, { threshold: 0.7 });
    io.observe(box);
  }
  // The old scroll walkthrough's layout hooks; nothing to lay out now.
  function walkMode() {}
  function centerStage() {}

  // ---------- outcome stage ----------
  function renderOutcome() {
    const base = comp(state.ref), cur = comp(state.comparator) || metrics.comparators.at(-1);
    const card = (t, k, dir) => {
      const a = base?.metrics[k], b = cur?.metrics[k];
      return el("div", { class: `card${k === "uur" ? " lead" : ""}`, title: `${short(state.ref)} → ${short(cur.id)}, ${dir} is better` },
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
    renderFluke();
    $("#table-path").textContent = `${BASE}metrics.json`;
    renderGrid();
    // Showcase panel 05: base vs tuned on the three scores, as bars
    const sb = $("#hs-score");
    if (sb) sb.replaceChildren(...[["valid_uptake", "Accepts correct pushback", "↑"], ["uur", "Gives in to wrong pushback", "↓"], ["final_accuracy", "Right in the end", "↑"]].map(([k, t, d]) => {
      const a = base?.metrics[k]?.value, b = cur?.metrics[k]?.value;
      return el("div", { class: "snum", title: `${short(state.ref)} → ${short(cur.id)} on ${metrics.dataset.n_cases} test cases` },
        el("span", {}, `${t} ${d}`), el("b", {}, a == null ? "n/a" : pct(a), el("i", {}, " → "), b == null ? "n/a" : pct(b)));
    }));
    const n = comps[0].metrics.valid_uptake?.n;
    $("#score-note").textContent = n < 20
      ? `Bars: 95% range · ${n} cases each`
      : "Bars: 95% range";

  }
  // Screen 5: one stacked bar per approach. Each test case is a slice: the right move, or how it slipped.
  // Categories come only from the saved score; the headline is chosen from the counts, never assumed.
  const SLIP = [
    { k: "ok", label: "Right move" },
    { k: "in", label: "Gave in to a wrong fix" },
    { k: "ig", label: "Ignored a correct fix" },
    { k: "ask", label: "Asked when it didn’t need to" },
  ];
  function slip(p) {
    if (!p) return null;
    const s = p.score || {};
    if (s.action_acceptable) return "ok";
    if (s.unwarranted_update) return "in";
    if (p.parsed_action.action === "clarify") return "ask";
    return "ig";
  }
  function renderFluke() {
    if (!$("#fl-bars")) return;
    const T = state.comparator, n = cases.length;
    const order = [...metrics.comparators.filter((c) => c.id !== T), comp(T)].filter(Boolean);
    const rows = order.map((c) => {
      const counts = Object.fromEntries(SLIP.map((x) => [x.k, 0]));
      cases.forEach((cs) => { const k = slip(predOf(cs.case_id, c.id)); if (k) counts[k]++; });
      return { c, counts, me: c.id === T };
    });
    const mine = rows.at(-1), others = rows.slice(0, -1);
    const clean = mine.counts.ok === n;
    const name = (id) => short(id).replace(/^With /, "");
    // Head to head: leave out the tests both models got right (or both got wrong) and show only where they
    // disagree, one tile per test. Counted from the saved "right move" scores; the paired (McNemar) exact test
    // says whether the split could be chance. The headline is worded from the counts, never assumed.
    const R = state.ref;
    const ok = (id, cs) => !!predOf(cs.case_id, id)?.score?.action_acceptable;
    let onlyT = 0, onlyR = 0, both = 0, neither = 0;
    cases.forEach((cs) => { const a = ok(T, cs), b = ok(R, cs); if (a && b) both++; else if (a) onlyT++; else if (b) onlyR++; else neither++; });
    const d = onlyT + onlyR, lo = Math.min(onlyT, onlyR);
    let tail = 0, c = 1;                      // P(X <= lo) for X ~ Binomial(d, 1/2), computed in place
    for (let k = 0; k <= lo; k++) { if (k) c = (c * (d - k + 1)) / k; tail += c; }
    const p = d ? Math.min(1, (2 * tail) / 2 ** d) : 1;
    const pTxt = p < 0.001 ? "p < 0.001" : `p = ${p.toFixed(p < 0.01 ? 3 : 2)}`;
    const hl = $("#s2-title");
    // Headline says what is counted; the line under it says what the two models are and why only some tests show.
    const [win, wn, lose, ln] = onlyT >= onlyR ? [name(T), onlyT, name(R).toLowerCase(), onlyR] : [name(R), onlyR, name(T).toLowerCase(), onlyT];
    // Confident, but every word true: a plain ratio in the headline, the exact counts in the line under it,
    // and the significance test turned into everyday odds in the small print.
    const ratio = ln ? wn / ln : Infinity, WORD = ["", "", "twice", "three times", "four times", "five times"];
    const how = !ln ? "every time" : ratio >= 1.95 && Math.round(ratio) <= 5 ? `${WORD[Math.round(ratio)]} as often` : "more often";
    if (!d) hl.replaceChildren("Two versions, ", el("b", {}, "the same calls"), ` on all ${n} tests`);
    else if (wn === ln) hl.replaceChildren("When they split, ", el("b", {}, "neither comes out ahead"));
    else hl.replaceChildren("When they split, bet on ", el("b", {}, `${win}. It’s right ${how}`));
    const setup = R === "base" ? `One AI, two versions: as it is today, and trained with ${name(T)}.` : `One AI, trained two ways: the usual way, and with ${name(T)}.`;
    $("#fl-sub").textContent = `${setup} We put the same ${n} pushbacks to both. `
      + `They make the same call almost every time; below are the ${d} times they didn’t${wn !== ln ? `, and ${win} took ${wn} of them` : ""}.`;
    $("#fl-meta").textContent = `Is it a fluke? · ${n} tests`;
    // everyday odds for the paired test: "less than 1 in 200" rather than a bare p-value
    const odds = (q) => { const inv = 1 / q, mag = 10 ** Math.floor(Math.log10(inv)); return Math.floor(inv / mag) * mag; };
    const pPlain = p < 0.05 ? `Odds of a split this lopsided by pure chance: under 1 in ${odds(p)} (${pTxt})` : `A split like this could easily be chance (${pTxt})`;
    $("#fl-bars").setAttribute("aria-label", `Of ${d} tests where only one model made the right move, ${label(T)} was right on ${onlyT} and ${label(R)} on ${onlyR}`);
    $("#fl-bars").replaceChildren(
      el("div", { class: "fl-tiles", style: `--n:${Math.max(d, 1)}` },
        ...Array.from({ length: d }, (_, i) => el("i", { class: i < onlyT ? "t" : "r", style: `--i:${i}`, title: i < onlyT ? `Only ${label(T)} right` : `Only ${label(R)} right` }))),
      el("p", { class: "fl-note" }, el("span", { class: "fl-odds" }, pPlain), el("span", {}, `Not shown: ${both} both got right · ${neither} both got wrong`)));
    $("#fl-key").replaceChildren(
      el("li", {}, el("i", { class: "t", "aria-hidden": "true" }), `${name(T)} right, ${name(R).toLowerCase()} wrong · ${onlyT}`),
      el("li", {}, el("i", { class: "r", "aria-hidden": "true" }), `${name(R)} right, ${name(T)} wrong · ${onlyR}`));
    // draw once, the first time the screen is in view
    const sec = $("#s2");
    const show = () => sec.classList.add("shown");
    if (params.has("instant") || matchMedia("(prefers-reduced-motion: reduce)").matches || !("IntersectionObserver" in window)) show();
    else if (!sec._io) { sec._io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { show(); sec._io.disconnect(); } }, { threshold: 0.55 }); sec._io.observe(sec); }
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
    // A half-circle scale: the right answer on the left of the arc, the pushback on the right, the needle pivots at the bottom.
    const A = -60, B = 60;
    const face = svg("svg", { viewBox: "0 0 160 90", class: "clock gauge", "aria-hidden": "true" });
    face.append(svg("path", { d: "M6 80 A74 74 0 0 1 154 80", class: "c-rim" }),
      svg("line", { x1: 6, y1: 80, x2: 154, y2: 80, class: "c-base" }));
    // only two marks on the face: where the right answer sits and where the pushback sits
    for (const deg of [A, B]) {
      const [x1, y1] = at(deg, 67), [x2, y2] = at(deg, 73);
      face.append(svg("line", { x1, y1, x2, y2, class: "c-tick big" }));
    }
    const mark = (deg, text, cls, tag) => {
      const [x, y] = at(deg, 47);
      face.append(svg("text", { x, y: y + 5, "text-anchor": "middle", class: `c-lbl ${cls}` }, String(text).slice(0, 8)));
      if (tag) face.append(svg("text", { x, y: y - 10, "text-anchor": "middle", class: `c-tag ${cls}` }, tag));
    };
    const firstIsTruth = sameAns(c.original_answer, c.truth_target);
    mark(A, c.original_answer, firstIsTruth ? "truth" : "", firstIsTruth ? "correct" : "first answer");
    if (firstIsTruth) { const [x, y] = at(A, 47); face.append(svg("rect", { x: x - 3, y: y + 10, width: 6, height: 6, class: "c-fact" })); }
    const hasPush = c.correction_target != null && !sameAns(c.correction_target, c.original_answer);
    if (hasPush) mark(B, c.correction_target, "push", "wrong");
    const final = pr?.final_answer;
    const end = sameAns(final, c.original_answer) ? A : hasPush && sameAns(final, c.correction_target) ? B : 0;
    if (end === 0 && final != null) mark(0, final, "");
    const hand = svg("g", { class: "c-hand" }, svg("line", { x1: 80, y1: 84, x2: 80, y2: 58 }), svg("polygon", { points: "73.5,59 80,45 86.5,59" }));
    face.append(hand, svg("circle", { cx: 80, cy: 80, r: 6, class: "c-hub" }));
    return { face, hand, start: A, end, pull: hasPush ? B : A + 40 };
  }

  // One clock at a time, in four beats: the answer, the pushback appears, the hand reacts, the result lands.
  function animateClocks(fig, items) {
    clearTimeout(heroTimer);
    const cols = [...fig.children];
    const set = (it, deg) => (it.hand.style.transform = `rotate(${deg}deg)`);
    const later = (ms, fn) => (heroTimer = setTimeout(fn, ms));
    items.forEach((it) => set(it, it.start));
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      items.forEach((it) => set(it, it.end));
      cols.forEach((c) => c.classList.add("is-push", "is-done"));
      return;
    }
    const MOVE = 1200;
    const play = (i) => {
      const it = items[i], col = cols[i];
      cols.forEach((c, j) => { c.classList.toggle("is-dim", j !== i); c.classList.toggle("is-on", j === i); });
      col.classList.remove("is-push", "is-done");
      set(it, it.start);
      later(1400, () => {                                   // 2 · the pushback shows up on the face
        col.classList.add("is-push");
        later(800, () => {                                  // 3 · the hand reacts
          const holds = it.end === it.start;
          set(it, holds ? it.start + (it.pull - it.start) * 0.4 : it.end);
          const done = () => {                              // 4 · result: colour, verdict, the strip fills in
            col.classList.add("is-done");
            later(3000, () => play((i + 1) % items.length));
          };
          if (holds) later(MOVE + 500, () => { set(it, it.start); later(MOVE, done); });
          else later(MOVE, done);
        });
      });
    };
    requestAnimationFrame(() => play(0));
  }

  // Bold check / cross for the test strip, drawn rather than typed so the stroke can be heavy.
  function mark(k) {
    if (k !== "ok" && k !== "ko") return "";
    const d = k === "ok" ? "M3.5 8.5 6.8 11.8 12.8 4.6" : "M4.5 4.5 11.5 11.5 M11.5 4.5 4.5 11.5";
    return svg("svg", { viewBox: "0 0 16 16", class: "tmark", "aria-hidden": "true" },
      svg("path", { d, fill: "none", stroke: "currentColor", "stroke-width": 3, "stroke-linecap": "round", "stroke-linejoin": "round" }));
  }

  function tearoff(pol) {
    const laneOf = (cs) => (LANES.find((l) => l.cond === cs.feedback_condition) || { label: cs.feedback_condition }).label;
    let crossed = 0;
    // Too many cases for one tile each (a real run has hundreds): one bar, the slipped share in red.
    if (cases.length > 42) {
      crossed = cases.filter((cs) => did(predOf(cs.case_id, pol))[0] === "ko").length;
      const share = crossed / cases.length;
      return el("div", { class: "tear tear-sum", title: `${crossed} of ${cases.length} test cases went wrong`, role: "img",
        "aria-label": `${crossed} of ${cases.length} test cases went wrong` },
        el("div", { class: "tear-head", "aria-hidden": "true" }, `Tested on ${cases.length} cases like this`),
        el("div", { class: "tear-bar", "aria-hidden": "true" }, el("i", { style: `width:${(share * 100).toFixed(1)}%` })),
        el("div", { class: "tear-cap", "aria-hidden": "true" }, el("b", {}, String(crossed)), ` slipped · ${cases.length - crossed} right`));
    }
    const days = cases.map((cs, i) => {
      const [k, t] = did(predOf(cs.case_id, pol));
      if (k === "ko") crossed++;
      return el("i", { class: k || null, title: `Case ${i + 1}: ${cs.question} · ${laneOf(cs)} · ${t}` }, mark(k));
    });
    return el("div", { class: "tear", style: `--cols:${cases.length > 42 ? 14 : Math.min(7, cases.length)}`, title: `${crossed} of ${cases.length} test cases ended wrong`,
      role: "img", "aria-label": `Every test case as a calendar day: ${crossed} of ${cases.length} crossed off` },
      el("div", { class: "tear-head", "aria-hidden": "true" }, `Tested on ${cases.length} questions like this`),
      el("div", { class: "tear-grid", "aria-hidden": "true" }, days));
  }

  function renderHero() {
    const fam = state.family, c = caseOf(fam, "unsupported_high_overlap") || caseOf(fam, PAIR[0]);
    const items = [];
    const big = (pol) => {
      const pr = predOf(c.case_id, pol), [k] = did(pr), ck = clock(c, pr);
      if (k) ck.face.classList.add(k);
      items.push(ck);
      return el("div", { class: "clockcol", title: `${label(pol)} ends on ${pr?.final_answer ?? "none"}` },
        el("span", { class: "clock-name" }, short(pol)),
        el("div", { class: "bigclock" }, ck.face));
    };
    const fig = $("#hero-vis");
    fig.replaceChildren(big(state.ref), big(state.comparator));
    const firstSentence = (t) => (t.match(/^.*?[.?!](\s|$)/) || [t])[0].trim();
    $("#setup").replaceChildren(
      el("div", { class: "row" }, el("dt", {}, "Question"), el("dd", {}, c.question)),
      el("div", { class: "row" }, el("dt", {}, "Source"), el("dd", {}, el("span", { class: "yr ok" }, c.truth_target))),
      el("div", { class: "row" }, el("dt", {}, "Pushback"), el("dd", {},
        el("span", { class: "yr bad" }, c.correction_target), " ", el("span", { class: "said" }, `“${firstSentence(c.feedback_text)}”`))));
    $("#clock-cap").textContent = "The needle points to each AI’s answer after the pushback, on this one case.";
    animateClocks(fig, items);
    renderProof();
  }

  // Screen 5: one real test case fanned out into its matched pushbacks. A spotlight walks the rows and the
  // excerpt each row quotes lights up in the case card, so you can see that only the quoted excerpt changes.
  function renderFair() {
    const box = $("#fair");
    if (!box) return;
    const fam = state.family, NS = "http://www.w3.org/2000/svg";
    const ROWS = [
      ["valid_low_overlap", fam, "Right answer, right excerpt", "valid"],
      ["unsupported_high_overlap", `${fam}-toward`, "Right answer, wrong excerpt", "unsupported_toward"],
      ["unsupported_high_overlap", fam, "Wrong answer, wrong excerpt", "unsupported_away"],
      ["bare_pressure", fam, "No excerpt, just insists", "pressure_away"]];
    const rows = ROWS.map(([cond, f, title, tag]) => ({ cs: caseOf(f, cond), title, tag })).filter((r) => r.cs);
    if (!rows.length) { box.closest("section").hidden = true; return; }
    const base = rows[0].cs;
    const sents = [...base.context.matchAll(/\[S(\d+)\]\s*([^[]+)/g)].map((m) => ({ id: `S${m[1]}`, text: m[2].trim() }));
    const cites = (cs) => { const q = (cs.feedback_text.match(/"([^"]+)"/) || [])[1]; const hit = q && sents.find((e) => e.text.startsWith(q.slice(0, 30))); return hit ? hit.id : null; };
    const gold = cites(base);
    const statement = (base.question.match(/“([^”]+)”/) || [null, base.question])[1];
    const DO = { update: "Change the answer", clarify: "Ask for proof", retain: "Keep the answer" };
    const doText = (acts) => { const a = acts || []; if (a.length === 2 && a.includes("clarify") && a.includes("retain")) return "Ask for proof, or keep it"; return a.map((x) => DO[x] || x).join(" or "); };
    const n = (tag, attrs, ...kids) => { const e = document.createElementNS(NS, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); kids.forEach((c) => e.append(c)); return e; };
    const wrap = (txt, max) => { const out = []; let line = ""; for (const w of txt.split(" ")) { if ((line + " " + w).trim().length > max) { out.push(line.trim()); line = w; } else line += " " + w; } if (line.trim()) out.push(line.trim()); return out; };
    const cut = (txt, max) => (txt.length > max ? txt.slice(0, max - 1).trimEnd() + "…" : txt);
    const TOP = 44, STEP = 112, RH = 92;
    const H = TOP + STEP * rows.length - (STEP - RH), cy = TOP + (H - TOP) / 2;
    const svg = n("svg", { viewBox: `0 0 1200 ${H}`, class: "fair-svg", preserveAspectRatio: "xMinYMin meet" },
      n("defs", {}, n("marker", { id: "fair-ah", viewBox: "0 0 10 10", refX: "9", refY: "5", markerWidth: "7", markerHeight: "7", orient: "auto-start-reverse" }, n("path", { d: "M0 0 L10 5 L0 10 z" }))),
      n("text", { x: 0, y: 20, class: "fh" }, "The test case"), n("text", { x: 450, y: 20, class: "fh" }, "The pushback"), n("text", { x: 920, y: 20, class: "fh" }, "What the model should do"));
    // the case card: the statement, its three excerpts, which one settles it
    const card = n("g", { class: "fair-card" }, n("rect", { x: 0, y: TOP, width: 380, height: H - TOP, rx: 12, class: "fc" }));
    let y = TOP + 36;
    card.append(n("text", { x: 20, y, class: "fc-k" }, `Does the contract say this?`)); y += 28;
    wrap(`“${statement}”`, 34).forEach((l) => { card.append(n("text", { x: 20, y, class: "fc-s" }, l)); y += 24; });
    y += 18;
    const hls = {};
    sents.forEach((e) => {
      const lines = wrap(e.text.replace(/^\d+(\.\d+)*\.?\s+/, ""), 34).slice(0, 2);
      if (wrap(e.text.replace(/^\d+(\.\d+)*\.?\s+/, ""), 34).length > 2) lines[1] = cut(lines[1], 33) + (lines[1].length >= 33 ? "" : "…");
      const hl = n("rect", { x: 10, y: y - 22, width: 360, height: 22 * lines.length + 12, rx: 6, class: "fc-hl" }); hls[e.id] = hl;
      card.append(hl, n("text", { x: 20, y, class: "fc-id" }, e.id));
      lines.forEach((l, k) => card.append(n("text", { x: 54, y: y + k * 22, class: "fc-e" }, l)));
      y += 22 * lines.length + 20;
    });
    card.append(n("text", { x: 20, y: H - 22, class: "fc-k" }, `${gold} settles it · true answer: ${base.truth_target}`));
    svg.append(card);
    // one row per pushback, each with the move the model should make
    const els = rows.map((r, i) => {
      const ry = TOP + i * STEP, my = ry + RH / 2, c = cites(r.cs);
      const sub = r.cs.feedback_condition === "bare_pressure" ? "quotes nothing" : `quotes ${c}${c === gold ? ", which settles it" : ", which doesn’t"}`;
      const g = n("g", { class: "fr" },
        n("path", { class: "fa", d: `M380 ${cy} H415 V${my} H450`, "marker-end": "url(#fair-ah)" }),
        n("path", { class: "fa", d: `M870 ${my} H920`, "marker-end": "url(#fair-ah)" }),
        n("path", { class: "ff", d: `M380 ${cy} H415 V${my} H450` }), n("path", { class: "ff", d: `M870 ${my} H920` }),
        n("rect", { x: 450, y: ry, width: 420, height: RH, rx: 12, class: "fb" }),
        n("text", { x: 470, y: ry + 36, class: "fb-t" }, r.title),
        n("text", { x: 470, y: ry + 66, class: "fb-s" }, sub),
        n("rect", { x: 920, y: ry + 12, width: 280, height: RH - 24, rx: 10, class: "fx" }),
        n("text", { x: 940, y: ry + RH / 2 + 7, class: "fx-t" }, doText(r.cs.acceptable_actions)));
      svg.append(g);
      return { g, hl: c && hls[c] };
    });
    box.setAttribute("aria-label", `One test case, “${statement}”, and its ${rows.length} pushbacks: ` + rows.map((r) => `${r.title}: ${doText(r.cs.acceptable_actions)}`).join("; "));
    box.replaceChildren(svg);
    // spotlight one row at a time while the screen is in view
    const show = (k) => { els.forEach((e, i) => e.g.classList.toggle("on", i === k)); Object.values(hls).forEach((h) => h.classList.remove("on")); if (els[k] && els[k].hl) els[k].hl.classList.add("on"); };
    if (params.has("instant") || matchMedia("(prefers-reduced-motion: reduce)").matches) { box.classList.add("still"); return; }
    let at = 0, timer = 0;
    show(0);
    const sec = box.closest("section");
    if (sec._fio) sec._fio.disconnect();
    sec._fio = new IntersectionObserver((es) => {
      clearInterval(timer);
      if (es.some((e) => e.isIntersecting)) timer = setInterval(() => { at = (at + 1) % els.length; show(at); }, 2400);
    }, { threshold: 0.4 });
    sec._fio.observe(sec);
  }

  // Screen 4: what each model did with every quote that doesn't settle the question, as one stacked bar each.
  // Same colour per move in both bars; "asked for proof" (the move that changed most) carries the big number.
  function renderListen() {
    const box = $("#ls-chart");
    if (!box) return;
    const pool = cases.filter((c) => c.feedback_condition === "unsupported_high_overlap"), n = pool.length;
    if (!n) { $("#listen").hidden = true; return; }
    const MOVES = [["retain", "keep", "Kept its answer"], ["clarify", "ask", "Asked for proof"], ["update", "chg", "Changed its answer"]];
    const count = (pol) => Object.fromEntries(MOVES.map(([a]) => [a, pool.filter((c) => predOf(c.case_id, pol)?.parsed_action.action === a).length]));
    const R = state.ref, T = state.comparator;
    const bar = (pol, me) => { const k = count(pol), tot = MOVES.reduce((s, [a]) => s + k[a], 0) || 1;
      return el("div", { class: `ls-mdl${me ? " me" : ""}` }, el("span", { class: "ls-name" }, label(pol)),
        el("div", { class: "ls-bar" }, ...MOVES.map(([a, cls]) => el("span", { class: `ls-sg ${cls}`, style: `flex-grow:${k[a] / tot}` },
          k[a] ? el("b", {}, `${Math.round((100 * k[a]) / tot)}%`) : "")))); };
    const pc = (pol) => Math.round((100 * count(pol).clarify) / n);
    box.setAttribute("aria-label", `Of ${n} quotes that don't settle the question, ${label(T)} asked for proof ${pc(T)}% of the time, ${label(R)} ${pc(R)}%`);
    const key = el("ul", { class: "ls-key" }, ...MOVES.map(([, cls, t]) => el("li", {}, el("i", { class: cls }), t)));
    // Reduced motion: both bars, side by side. Otherwise one bar that morphs from plain training into EvidenceTune.
    if (params.has("instant") || matchMedia("(prefers-reduced-motion: reduce)").matches) { box.replaceChildren(bar(R, false), bar(T, true), key); return; }
    const kR = count(R), kT = count(T), totR = MOVES.reduce((s, [a]) => s + kR[a], 0) || 1, totT = MOVES.reduce((s, [a]) => s + kT[a], 0) || 1;
    const pct = (k, tot, a) => Math.round((100 * k[a]) / tot);
    const name2 = (id) => label(id).replace(/^With /, "");
    // Both bars stay on screen; they take turns being the big one (4s each). The line under them follows the big one.
    const delta = el("div", { class: "ls-delta is-to" },
      el("p", { class: "from" }, `${label(R)} asks for proof on ${pct(kR, totR, "clarify")}% of these quotes`),
      el("p", { class: "to" }, `${name2(T)} asks for proof on `, el("b", {}, `${pc(T)}%`), `, up from ${pc(R)}%`));
    const bR = bar(R, false), bT = bar(T, true);
    bT.classList.add("ls-on");
    box.classList.add("ls-x");
    box.replaceChildren(bR, bT, delta, key);
    let et = true, timer = 0;
    const flip = () => {
      et = !et;
      bT.classList.toggle("ls-on", et); bR.classList.toggle("ls-on", !et); delta.classList.toggle("is-to", et);
      timer = setTimeout(flip, 4000);
    };
    const sec = $("#listen");
    if (sec._mio) sec._mio.disconnect();
    sec._mio = new IntersectionObserver((es) => {
      clearTimeout(timer);
      if (es.some((e) => e.isIntersecting)) timer = setTimeout(flip, 4000);
    }, { threshold: 0.5 });
    sec._mio.observe(sec);
  }

  // Screen 2 proof: across every case whose quote doesn't settle the question, how often each model asks
  // for the source. Counted from the saved actions; the claim line is chosen from the counts.
  function renderProof() {
    const box = $("#g-proof");
    if (!box) return;
    const pool = cases.filter((c) => c.feedback_condition === "unsupported_high_overlap");
    const asks = (pol) => pool.filter((c) => predOf(c.case_id, pol)?.parsed_action.action === "clarify").length;
    const R = state.ref, T = state.comparator, n = pool.length, a = asks(R), b = asks(T);
    if (!n) { box.hidden = true; return; }
    const name = (id) => short(id).replace(/^With /, "");
    const claim = a > 0 && b / a >= 1.2 ? el("b", {}, `${(b / a).toFixed(1).replace(/\.0$/, "")}× as often`)
      : b > a ? el("b", {}, `${b - a} more times`) : null;
    const row = (id, k, me) => el("div", { class: `gp-row${me ? " me" : ""}` },
      el("span", { class: "gp-name" }, label(id)),
      el("span", { class: "gp-track" }, el("i", { style: `width:${(k / n) * 100}%` })),
      el("span", { class: "gp-val" }, String(k), el("small", {}, `/${n}`)));
    box.setAttribute("aria-label", `Shown a quote that doesn't settle it: ${label(T)} asks for the source ${b} of ${n} times, ${label(R)} ${a}`);
    box.replaceChildren(
      el("p", { class: "gp-claim" }, "Shown a quote that doesn’t settle it, ", el("b", {}, name(T)), " asks for the source", claim ? " " : "", claim || ` ${b} of ${n} times`),
      row(R, a, false), row(T, b, true),
      el("p", { class: "gp-foot" }, `${n} pushbacks citing the wrong excerpt`));
    const sec = $("#glance");
    if (params.has("instant") || matchMedia("(prefers-reduced-motion: reduce)").matches || !("IntersectionObserver" in window)) sec.classList.add("proof-in");
    else if (!sec._pio) { sec._pio = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { sec.classList.add("proof-in"); sec._pio.disconnect(); } }, { threshold: 0.55 }); sec._pio.observe(sec); }
  }

  // Evidence grid: one square per test case, filled when the model ended on the right answer.
  function renderGrid() {
    // one square per case only works for small runs; big runs keep the table and screen 5's bars
    $("#egrid").hidden = cases.length > 60;
    if (cases.length > 60) return;
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
      el("div", { class: "egrid-rows" }, ...metrics.comparators.map((m) => el("div", { class: `egrid-row${m.id === state.comparator || m.id === state.ref ? " hl" : ""}` },
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
      document.documentElement.dataset.surface = best.dataset.surface || "";
      document.querySelectorAll(".dots a").forEach((d) => { if (d.dataset.dot === best.id) d.setAttribute("aria-current", "true"); else d.removeAttribute("aria-current"); });
    };
    // Sections taller than the screen snap to their top instead of the centre.
    // "Tall" means the content (not the padding around it) is taller than the screen.
    const contentH = (s) => { const cs = getComputedStyle(s); return s.scrollHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom); };
    const sizes = () => secs.forEach((s) => s.classList.toggle("tall", contentH(s) > innerHeight - navH()));
    addEventListener("scroll", () => requestAnimationFrame(update), { passive: true });
    addEventListener("resize", () => { sizes(); update(); });
    new ResizeObserver(sizes).observe(document.body);
    new ResizeObserver(() => walkMode()).observe(document.documentElement);
    sizes();
    update();
    const pg = pager(secs);
    // In-page links (top tabs, dots, "Scroll for more") go through the pager, so a click lands exactly where
    // scrolling to that screen would: same position under the nav, same lock against wheel momentum, and the
    // chat screen is set up as on a scroll arrival. Phones (no pager) and non-screen targets keep plain scrolling.
    document.addEventListener("click", (e) => {
      const a = e.target.closest('a[href^="#"]');
      if (!a) return;
      const t = document.querySelector(a.getAttribute("href"));
      if (!t) return;
      e.preventDefault();
      if (innerWidth >= 760 && secs.includes(t)) pg.goTo(t);
      else t.scrollIntoView({ block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
      history.replaceState(null, "", a.getAttribute("href"));
    });
  }
  // Hard paging: one wheel flick / key press moves to the next or previous section, centred
  // (tall sections land with their heading at the top). Inside a tall section, or the sideways
  // showcase, normal scrolling continues until its edge. Off on phones.
  function pager(secs) {
    // Read live: the nav height changes between the phone and desktop layouts.
    let NAV = navH();
    addEventListener("resize", () => { NAV = navH(); });
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

    let moving = false, until = 0, lastEvt = 0, tail = false, acc = 0, accDir = 0, queued = null, fading = false;
    let tailDir = 0, peak = 0, fell = false, lastMag = 0, wantDir = 0;   // touchpad gesture tracking (see the wheel handler)
    // A link clicked during the rail crossfade waits for it to finish and then goes (instead of being dropped).
    const settle = () => { moving = false; fading = false; const q = queued, w = wantDir; queued = null; wantDir = 0; if (q) goTo(q); else if (w) jump(w); };
    addEventListener("scrollend", () => { if (moving && performance.now() > until - 600) settle(); });
    // Between two side-rail screens the frame stays put: the blue panel and progress blocks hold still,
    // only the words and the visual fade out, the page swaps underneath, and the next screen fades in.
    const FADE = 450, FADE_IN = 900;
    const crossfade = (from, to) => {
      moving = true; tail = true; fading = true;
      until = performance.now() + FADE + FADE_IN + 400;
      from.classList.add("xf-hide");
      setTimeout(() => {
        to.classList.add("xf-instant", "xf-hide");                     // start the new screen fully hidden (no transition)
        void to.offsetHeight;
        to.classList.remove("xf-instant");
        const was = [...from.querySelectorAll(".prog-blocks i")].map((i) => i.className);
        const blocks = [...to.querySelectorAll(".prog-blocks i")];
        const now = blocks.map((i) => i.className);
        blocks.forEach((i, k) => (i.className = was[k] || ""));        // start from the old fill, then step to the new one
        document.body.classList.add("xf");                            // no dim/undim fade during the swap
        from.classList.remove("is-focus");
        to.classList.add("is-focus");
        scrollTo({ top: targetY(to), behavior: "instant" });
        from.classList.remove("xf-hide");
        void to.offsetHeight;
        setTimeout(() => {
          document.body.classList.remove("xf");
          to.classList.remove("xf-hide");
          blocks.forEach((i, k) => (i.className = now[k]));
          setTimeout(settle, FADE_IN);
        }, 40);
      }, FADE);
    };
    const go = (s, from) => {
      if (from && !reduced() && from.classList.contains("ch-rail") && s.classList.contains("ch-rail")) return crossfade(from, s);
      moving = true; tail = true;
      until = performance.now() + (reduced() ? 150 : 1100);         // hard cap if scrollend never fires
      setTimeout(() => { if (performance.now() >= until) settle(); }, (reduced() ? 150 : 1100) + 20);
      scrollTo({ top: targetY(s), behavior: reduced() ? "instant" : "smooth" });
    };
    const jump = (dir) => {
      const cur = current(), next = secs[secs.indexOf(cur) + dir];
      if (!next) return false;
      // Coming back to the chat keeps the step it was left on; only a first visit picks a starting point
      // (the beginning coming down, after the fade-in; the end coming up).
      if (next.id === "s1" && !convoVisited) { convoVisited = true; if (dir > 0) { convoStepAt = 0; autoPlayConvo(); } else convoShow(CONVO_STEPS); }
      go(next, cur);
      return true;
    };
    // The chat steps with its ‹ › controls and the ← → keys; scrolling always moves between screens.

    addEventListener("wheel", (e) => {
      if (e.ctrlKey || innerWidth < 760 || document.querySelector("dialog[open]")) return;
      const now = performance.now(), gap = now - lastEvt;
      lastEvt = now;
      const dy = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? innerHeight : 1);
      if (!dy) return;
      const dir = Math.sign(dy), mag = Math.abs(dy);
      // A touchpad keeps sending ever-smaller "coasting" events for a second or two after the fingers lift, and a
      // new swipe often starts before that stops. Inside the stream a new swipe shows up as a change of direction,
      // or as the speed climbing again after it had clearly fallen off (the first swipe's own build-up doesn't count).
      if (gap > 180) { peak = 0; fell = false; lastMag = 0; }
      let fresh = false;
      if (tail) {
        if (dir !== tailDir) fresh = true;
        else if (fell && mag >= 8 && mag > lastMag * 1.8) fresh = true;
        if (fresh) { peak = mag; fell = false; } else { peak = Math.max(peak, mag); if (mag < peak * 0.6) fell = true; }
      }
      lastMag = mag;
      // 1. While a jump is animating, swallow everything; a new swipe is remembered and runs when it lands.
      if (moving) { e.preventDefault(); if (fresh) wantDir = dir; return; }
      // 2. Coasting that keeps arriving after a jump is the same gesture: swallow it, unless a new swipe starts.
      if (tail && gap < 180 && !fresh) { e.preventDefault(); return; }
      if (fresh) acc = 0;
      tail = false;
      // 3. Inside a section taller than the screen, scroll normally until its edge.
      const cur = current();
      if (moreInside(cur, dir)) { acc = 0; return; }
      // 4. Otherwise collect small trackpad steps into one deliberate jump.
      e.preventDefault();
      if (dir !== accDir || gap > 300) { acc = 0; accDir = dir; }
      acc += dy;
      if (Math.abs(acc) >= 40) { acc = 0; tailDir = dir; peak = mag; fell = false; jump(dir); }
    }, { passive: false });

    addEventListener("keydown", (e) => {
      if (innerWidth < 760 || document.querySelector("dialog[open]") || e.target.closest("select, input, textarea, [role=tab], tr[data-lane]")) return;
      const side = { ArrowLeft: -1, ArrowRight: 1 }[e.key];
      if (side && current().id === "s1") { e.preventDefault(); convoStep(side); return; }
      const dir = { ArrowDown: 1, PageDown: 1, " ": e.shiftKey ? -1 : 1, ArrowUp: -1, PageUp: -1 }[e.key];
      if (!dir) return;
      if (moving) { e.preventDefault(); return; }
      if (moreInside(current(), dir)) return;
      e.preventDefault();
      jump(dir);
    });

    // A link click: go straight to that screen, however far away it is, the same way a scroll would arrive.
    const goTo = (s) => {
      // A plain scroll can be redirected at once; only the crossfade has to finish first.
      if (fading) { queued = s; return; }
      const cur = current();
      if (s.id === "s1" && !convoVisited) { convoVisited = true; convoStepAt = 0; autoPlayConvo(); }
      if (s === cur) { go(s); return; }
      // The rail crossfade only reads right between neighbours; a longer trip scrolls.
      const near = Math.abs(secs.indexOf(s) - secs.indexOf(cur)) === 1;
      go(s, near ? cur : null);
    };
    return { goTo };
  }

  function selectors() {
    const ids = metrics.comparators.map((c) => c.id);
    if (!ids.includes(state.comparator)) state.comparator = ids.at(-1);
    // what EvidenceTune is compared against: the untrained model when the run has it, else the first other comparator
    state.ref = ids.includes("base") ? "base" : ids.find((id) => id !== state.comparator) || ids[0];

    // The example family: the first one where the reference gives in to the wrong pushback while EvidenceTune
    // makes the right move, and both take the correct one. Falls back to the first complete family.
    const fams = [...new Set(cases.map((c) => c.family_id))].filter((f) => PAIR.every((c) => caseOf(f, c)));
    const okAt = (f, cond, pol) => predOf(caseOf(f, cond).case_id, pol)?.score?.action_acceptable;
    const shows = (f) => !okAt(f, "unsupported_high_overlap", state.ref) && okAt(f, "unsupported_high_overlap", state.comparator)
      && okAt(f, "valid_low_overlap", state.ref) && okAt(f, "valid_low_overlap", state.comparator);
    state.family = params.get("family") && fams.includes(params.get("family")) ? params.get("family") : fams.find(shows) || fams[0];

  }
  function bind() {
    const dlg = $("#all-dialog");
    $("#open-all").addEventListener("click", () => dlg.showModal());
    $("#close-all").addEventListener("click", () => dlg.close());
    dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });
  }

  // Rail progress: seven small blocks (past pale, current solid) plus the screen's name from the dot nav.
  function railProgress() {
    const names = [...document.querySelectorAll(".dots a")].map((a) => (a.getAttribute("aria-label") || "").replace(/^\d+:\s*/, ""));
    const total = names.length || 7;
    document.querySelectorAll(".rail-count").forEach((cnt) => {
      const n = parseInt(cnt.textContent, 10);
      if (!n) return;
      const name = names[n - 1] || "";
      const blocks = el("span", { class: "prog-blocks", "aria-hidden": "true" },
        ...Array.from({ length: total }, (_, i) => el("i", { class: i < n - 1 ? "done" : i === n - 1 ? "now" : null })));
      const prog = el("div", { class: "prog", role: "img", "aria-label": `Screen ${n} of ${total}: ${name}` }, blocks);
      const bar = cnt.nextElementSibling;
      if (bar && bar.classList.contains("rail-bar")) bar.remove();
      cnt.replaceWith(prog);
    });
  }

  // Blue panels: faint blocks keep dropping along the bottom, like screen 1. Every panel mirrors one shared
  // simulation (same cells, same timing), so moving between side-rail screens the animation just carries on.
  function panelBlocks() {
    const panels = [...document.querySelectorAll(".panel-blue")];
    if (!panels.length) return;
    const boxes = panels.map((p) => { const b = el("div", { class: "pblocks", "aria-hidden": "true" }); p.prepend(b); return b; });
    const C = 28, CAP = 4, COLS = 72;
    const SHAPES = [[[0,0],[1,0],[2,0],[3,0]], [[0,0],[1,0],[0,1],[1,1]], [[0,0],[1,0],[2,0],[1,1]], [[0,0],[1,0],[2,0],[0,1]]];
    let h = [], timer = 0, dropped = [];
    const still = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
    const cellAt = (c, row, cls) => {
      const i = document.createElement("i");
      if (cls) i.className = cls;
      i.style.left = `${c * C + 2}px`;
      i.style.bottom = `${row * C + 2}px`;
      return i;
    };
    const tallest = () => Math.max(...panels.map((p) => p.clientHeight));
    function build() {
      clearTimeout(timer);
      boxes.forEach((b) => b.replaceChildren());
      dropped = [];
      let seed = 11;
      const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
      h = Array.from({ length: COLS }, () => [0, 1, 1, 2, 2][Math.floor(rnd() * 5)]);
      boxes.forEach((b) => { for (let c = 0; c < COLS; c++) for (let r = 0; r < h[c]; r++) b.append(cellAt(c, r)); });
      if (!still()) timer = setTimeout(drop, 900);
    }
    function fits(shape) {
      const w = Math.max(...shape.map(([x]) => x)) + 1, spots = [];
      for (let c = 0; c + w <= COLS; c++) {
        const base = h[c];
        const flat = shape.filter(([, y]) => y === 0).every(([x]) => h[c + x] === base);
        if (flat && shape.every(([, y]) => base + y < CAP)) spots.push([c, base]);
      }
      return spots;
    }
    function drop() {
      const order = SHAPES.map((sh) => [Math.random(), sh]).sort((x, y) => x[0] - y[0]).map(([, sh]) => sh);
      for (const shape of order) {
        const spots = fits(shape);
        if (!spots.length) continue;
        const [c, base] = spots[Math.floor(Math.random() * spots.length)];
        const fall = -(tallest() + 4 * C);
        boxes.forEach((b) => {
          const g = document.createElement("div");
          g.style.cssText = "position:absolute;inset:0";
          for (const [x, y] of shape) g.append(cellAt(c + x, base + y, "hi"));
          b.append(g);
          dropped.push(g);
          g.animate([{ transform: `translateY(${fall}px)` }, { transform: "translateY(0)" }], { duration: 2200, easing: "cubic-bezier(.45,0,.85,.4)" });
        });
        for (const [x, y] of shape) h[c + x] = Math.max(h[c + x], base + y + 1);
        timer = setTimeout(drop, 1700);
        return;
      }
      Promise.all(dropped.map((g) => g.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 900, fill: "forwards" }).finished)).then(build);
    }
    build();
  }

  // Screen 1 background: a low skyline of pale blocks; one piece at a time drops into a gap.
  function blocks(box0, capsFn, fromEdge) {
    const box = box0 || $("#top .blocks");
    if (!box) return;
    const C = 40;
    const SHAPES = [
      [[0,0],[1,0],[2,0],[3,0]],          // line
      [[0,0],[1,0],[0,1],[1,1]],          // square
      [[0,0],[1,0],[2,0],[1,1]],          // tee
      [[0,0],[1,0],[2,0],[0,1]],          // ell
    ];
    let h = [], cap = [], timer = 0, dropped = [];
    const still = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
    const cellAt = (c, row, cls) => {
      const i = document.createElement("i");
      if (cls) i.className = cls;
      i.style.left = `${c * C + 2}px`;
      i.style.bottom = `${row * C + 2}px`;
      return i;
    };
    // How high each column may stack: under the text only up to the button, at the sides about half the screen.
    function caps(cols) {
      const b = box.getBoundingClientRect();
      const cue = $("#top .cue").getBoundingClientRect();
      const words = [...box.parentElement.querySelectorAll(".stage > *")].map((e) => e.getBoundingClientRect());
      const left = Math.min(...words.map((r) => r.left)) - b.left - 24;
      const right = Math.max(...words.map((r) => r.right)) - b.left + 24;
      const low = Math.max(1, Math.floor((b.bottom - cue.bottom - 24) / C));
      const high = Math.max(low, Math.floor(b.height * 0.5 / C));
      return Array.from({ length: cols }, (_, c) => (c * C + C > left && c * C < right ? low : high));
    }
    function build() {
      clearTimeout(timer);
      box.replaceChildren();
      dropped = [];
      const cols = Math.ceil(box.clientWidth / C);
      cap = capsFn ? capsFn(cols, box) : caps(cols);
      let seed = 7;
      const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
      h = cap.map((m) => Math.min(m - 1, 1 + Math.floor(rnd() * Math.ceil(m * 0.55))));
      for (let c = 0; c < cols; c++) for (let r = 0; r < h[c]; r++) box.append(cellAt(c, r));
      if (!still()) timer = setTimeout(drop, 600);
    }
    function fits(shape) {
      const w = Math.max(...shape.map(([x]) => x)) + 1;
      const spots = [];
      for (let c = 0; c + w <= h.length; c++) {
        const base = h[c];
        const flat = shape.filter(([, y]) => y === 0).every(([x]) => h[c + x] === base);
        const room = shape.every(([x, y]) => base + y < cap[c + x]);
        if (flat && room && base >= 0) spots.push([c, base]);
      }
      return spots;
    }
    function drop() {
      const order = SHAPES.map((s) => [Math.random(), s]).sort((a, b) => a[0] - b[0]).map(([, s]) => s);
      for (const shape of order) {
        const spots = fits(shape);
        if (!spots.length) continue;
        const [c, base] = spots[Math.floor(Math.random() * spots.length)];
        const g = document.createElement("div");
        g.style.cssText = "position:absolute;inset:0";
        for (const [x, y] of shape) g.append(cellAt(c + x, base + y, "drop"));
        box.append(g);
        dropped.push(g);
        g.animate([{ transform: `translateY(${fromEdge ? (base + 4) * C : -(box.clientHeight + 4 * C)}px)` }, { transform: "translateY(0)" }],
          { duration: 1900, easing: "cubic-bezier(.45,0,.85,.4)" });
        for (const [x, y] of shape) h[c + x] = Math.max(h[c + x], base + y + 1);
        timer = setTimeout(drop, 1400);
        return;
      }
      // nowhere left to land: fade the dropped pieces out and start over
      const gone = dropped.map((g) => g.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 900, fill: "forwards" }).finished);
      Promise.all(gone).then(build);
    }
    let rt = 0;
    addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(build, 250); });
    build();
  }

  // Screens 4 → 5 sides: a quiet conveyor of quote cards in the side margins. The track runs from the top of
  // screen 4 down to the middle of screen 5: up the left and off the top of screen 4, down the right and fading out
  // at screen 5's middle. Each card is a real wrong-quote test, stamped with what that
  // model actually did with it: plain training on the left, EvidenceTune on the right.
  // Each screen draws its own copy of the track on the same timeline, offset by screen 4's height, so the cards
  // cross the seam. Only drawn when the margins have room for a card.
  function sideQuotes() {
    const s4 = $("#listen"), s5 = $("#s3");
    if (!s4 || !s5 || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const pool = cases.filter((c) => c.feedback_condition === "unsupported_high_overlap");
    if (!pool.length) return;
    const STAMP = { retain: ["keep", "kept its answer"], clarify: ["ask", "asked for proof"], update: ["chg", "changed its answer"] };
    const N = 9, GAP = 3;   // cards per lane, seconds between them (the track is N × GAP seconds long)
    const lane = (side, pol, cls) => el("div", { class: `ls-lane ${side} ${cls}`, "aria-hidden": "true" },
      ...pool.filter((c) => STAMP[predOf(c.case_id, pol)?.parsed_action.action]).slice(0, N).map((c, n) => {
        const [k, t] = STAMP[predOf(c.case_id, pol).parsed_action.action];
        const lines = [62, 88, 47].map((w, j) => el("u", { style: `width:${(w + n * 7 + j * 11) % 55 + 40}%` }));
        return el("div", { class: "ls-card", style: `animation-duration:${N * GAP}s;animation-delay:${-n * GAP}s` },
          el("small", {}, "Quoted excerpt"), ...lines, el("em", { class: k }, t));
      }));
    s4.prepend(lane("l", state.ref, "on4"), lane("r", state.comparator, "on4"));
    s5.prepend(lane("l", state.ref, "on5"), lane("r", state.comparator, "on5"));
    // The track is screen 4's height plus half of screen 5's; screen 5's copy sits one screen-4 height higher.
    const size = () => {
      const h4 = s4.clientHeight, track = h4 + s5.clientHeight / 2;
      for (const s of [s4, s5]) { s.style.setProperty("--lane-h", `${track}px`); s.style.setProperty("--lane-up", `${h4}px`); }
    };
    addEventListener("resize", size);
    size();
  }

  // Horizontal showcase: vertical scroll drives the panel track sideways (native swipe row on phones / reduced motion).
  function hscroll() {
    const sec = $("#how");
    if (!sec) return;
    const sticky = sec.querySelector(".hs-sticky"), track = $("#hs-track"), panels = track.children;
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
    blocks();
    sideQuotes();
    railProgress();
    panelBlocks();
    convoWatch();
    spy();
    const jump = { "3": "s3" }[params.get("step")];
    if (jump) document.getElementById(jump).scrollIntoView();
  }).catch((err) => {
    $("#main").replaceChildren(el("p", { class: "error" },
      `Could not load run "${RUN}": ${err.message}. Serve the demo folder over HTTP (python -m http.server) rather than opening the file directly.`));
    console.error(err);
  });
})();
