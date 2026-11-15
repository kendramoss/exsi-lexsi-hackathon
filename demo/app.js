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
  // The page scales itself to 80% on desktop (CSS zoom on the root). On-screen positions, scrollY and the window size
  // are in screen pixels; offsetHeight, scrollHeight and CSS lengths are in the page's own pixels. Z converts.
  const Z = () => parseFloat(getComputedStyle(document.documentElement).zoom) || 1;
  const navPx = () => navH() * Z();   // the nav bar's height on screen
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

  // ---------- run scope ----------
  function renderHead() {
    // import_final_run.py puts unsupported_toward in a suffixed family solely to keep case IDs unique.
    // It is a fourth pushback on the same source case, not a second independent case.
    const groups = new Map();
    cases.forEach((c) => {
      const family = RUN === "final-fresh" ? c.family_id.replace(/-toward$/, "") : c.family_id;
      groups.set(family, (groups.get(family) || 0) + 1);
    });
    const n = groups.size, records = cases.length, conditions = new Set(cases.map((c) => c.feedback_condition)).size;
    const perFamily = new Set(groups.values());
    const ways = perFamily.size === 1 ? [...perFamily][0] : null;
    const scope = metrics.is_mock ? `${n} invented case families, ${records} records, ${conditions} conditions`
      : `${n} cases, ${records} pushbacks${ways ? ` (${ways} per case)` : ""}`;
    $("#glance .rail-foot").textContent = metrics.is_mock ? "Invented layout example. Not a model result." : "One recorded example. Not live inference.";
    const comparison = `${label(state.comparator)} against ${label(state.ref)}`;
    const fact = (title, text) => el("li", {}, el("b", {}, title), text);
    const released = () => [" The released model is ", el("a", {
      href: "https://github.com/kendramoss/exsi-lexsi-hackathon#about-the-project", target: "_blank", rel: "noopener",
    }, "merged α=0.75"), ", a blend of the later v7 and v8 adapters, with its own frozen results."];

    if (metrics.is_mock) {
      $(".fair-lead").textContent = `Mock layout test: ${scope}. ${ways ? `Each family has ${ways} pushbacks.` : ""} These examples and scores are invented, not a model evaluation.`;
      $(".fair-facts").replaceChildren(
        fact("Mock data", `${n} invented case families for layout testing, not NDA evaluation cases`),
        fact(`${conditions} conditions`, "Correct pushback, unsupported pushback, and pressure without evidence"),
        fact(`${records} records`, `${n} families${ways ? `, each pushed back on ${ways} ways` : ""}; all outputs and scores are invented`));
      $("#s4 .which").textContent = `Mock layout test: ${scope}. Shown here: ${comparison}, using invented outputs and scores. The linked model and benchmark are project resources, not the source of this mock run.`;
      $("#all-dialog .intro").textContent = `Mock layout test: ${scope}. Selected comparison: ${comparison}. All ${metrics.comparators.length} comparator rows below are invented, not measured model quality. Source: scripts/make_mock_results.py; saved artifacts in ${BASE}.`;
    } else {
      $(".fair-lead").textContent = `${ways ? `Every case is pushed back on ${ways} ways.` : scope + "."} The ones that quote an excerpt use the same words and only the excerpt changes, so the model has to check it`;
      const facts = RUN === "final-fresh" ? [
        fact("New clause types", "Every test case uses one of 5 clause types never seen in training (nda-1, 7, 15, 16, 17)"),
        fact("No word tricks", "Word overlap, length and position each point to the right excerpt only half the time"),
      ] : [fact("Saved run", `Scope: ${metrics.dataset.split}`)];
      $(".fair-facts").replaceChildren(...facts, fact(`${records} scored`, `${n} cases${ways ? `, each pushed back on ${ways} ways` : ""}`));
      $("#s4 .which").replaceChildren(`Shown here: ${comp(state.comparator).label} against ${comp(state.ref).label}, on ${scope}.`,
        ...(RUN === "final-fresh" ? released() : []));
      $("#all-dialog .intro").replaceChildren(`Shown here: ${comp(state.comparator).label} against ${comp(state.ref).label}, on ${scope}. `,
        `Saved comparison: ${[state.ref, state.comparator].map((id) => `${id} (${[...new Set(preds.filter((p) => p.policy === id).map((p) => p.model))].join(", ")})`).join(" vs ")}. `,
        `Source: ${RUN === "final-fresh" ? "scripts/import_final_run.py; " : ""}saved artifacts in ${BASE}.`,
        ...(RUN === "final-fresh" ? released() : []));
    }
  }

  // ---------- 01: the conversation ----------
  // Two chat windows play the same conversation; they split at the reply. Everything comes from the saved run.
  const cap = (t) => t[0].toUpperCase() + t.slice(1);
  let convoTimers = [], convoWins = [], convoPlayed = false;
  let convoGeneration = 0, convoBusyUntil = 0;
  let convoAutoplay = false, convoAutoTimer = 0;
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
    const file = () => el("div", { class: "file", title: "The full passage:\n" + spans(c.context).map((x) => `Excerpt ${x.id.replace(/^S/, "")}: ${x.text}`).join("\n") },
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
    convoShow(innerWidth < 760 ? CONVO_STEPS : Math.max(1, convoStepAt), 0, true);

    renderListen();
    renderFair();
  }

  // Scroll-stepped conversation (desktop): step n shows
  //   1 the question with its attachment · 2 the AI's answer · 3 the pushback
  //   4 the split, each AI's first reply · 5 the rest of each thread and the verdicts
  const CONVO_STEPS = 5;
  let convoStepAt = 0;
  // A typing bubble on the sender's side: three dots, like a real chat.
  const typingRow = (who) => el("div", { class: `chat-row ${who} typing-row`, role: "status", "aria-label": who === "ai" ? "Agent is typing" : "Human is typing" }, el("i", { class: "av", "aria-hidden": "true" }),
    el("div", { class: "bubbles" }, el("div", { class: `bubble ${who === "ai" ? "a" : "q"} typing`, "aria-hidden": "true" }, el("i"), el("i"), el("i"))));

  // At the split the pushback slides to the centre so the fork's stem grows straight out of it.
  function centerPush(animate) {
    const trunk = convoWins.trunk, bub = trunk && trunk.querySelector(".chat-row.push .bubble");
    if (!bub) return;
    const z = (parseFloat(getComputedStyle($("#convo")).zoom) || 1) * Z();
    bub.style.transition = "none"; bub.style.translate = "0px 0px";
    const tr = trunk.getBoundingClientRect(), br = bub.getBoundingClientRect();
    const dx = ((tr.left + tr.width / 2) - (br.left + br.width / 2)) / z;
    void bub.offsetWidth;
    bub.style.transition = animate ? `translate 650ms ${EASE}` : "none";
    bub.style.translate = `${dx}px 0px`;
  }

  // Chapter mode plays the conversation in time; native mode retains its runway.
  let scrollStory = null, chapterScroll = null;
  function convoStep(dir) {
    return scrollStory ? scrollStory.step(dir) : false;
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
    if (prev) prev.disabled = n <= 1 || $("#convo").dataset.playback === "moving";
    if (next) next.disabled = n >= CONVO_STEPS || performance.now() < convoBusyUntil;
    const toggle = $("#convo-toggle");
    toggle.hidden = !chapterScroll?.active || n >= CONVO_STEPS;
    toggle.textContent = convoAutoplay ? "Pause" : "Play";
    toggle.setAttribute("aria-label", convoAutoplay ? "Pause after the current message" : "Continue the conversation automatically");
    toggle.setAttribute("aria-pressed", String(convoAutoplay));
    $("#replay").textContent = chapterScroll?.active ? "Replay conversation" : "Read from the beginning";
    if (dots) dots.replaceChildren(...Array.from({ length: CONVO_STEPS }, (_, i) => el("i", { class: i + 1 < n ? "done" : i + 1 === n ? "on" : null })));
  }

  function stopConvoAutoplay() {
    clearTimeout(convoAutoTimer);
    convoAutoTimer = 0;
    convoAutoplay = false;
    $("#convo").dataset.autoplay = "paused";
  }

  function scheduleConvoAutoplay() {
    clearTimeout(convoAutoTimer);
    if (!convoAutoplay || !chapterScroll?.active) return;
    if (convoStepAt >= CONVO_STEPS) {
      convoAutoplay = false;
      $("#convo").dataset.autoplay = "complete";
      convoUi(convoStepAt);
      return;
    }
    const generation = convoGeneration;
    const pause = convoStepAt === 3 ? 1700 : convoStepAt === 4 ? 1900 : 1100;
    convoAutoTimer = setTimeout(() => {
      if (!convoAutoplay || generation !== convoGeneration || !chapterScroll?.active) return;
      const rect = $("#s1").getBoundingClientRect();
      if (rect.bottom <= navPx() || rect.top >= innerHeight) { stopConvoAutoplay(); return; }
      scrollStory.show(convoStepAt + 1, { automatic: true });
    }, pause);
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

  function convoShow(n, wait = 0, scrubbing = false) {
    const W = convoWins;
    if (!W.trunk) return;
    convoTimers.forEach(clearTimeout); convoTimers = [];
    clearTimeout(convoAutoTimer);
    const generation = ++convoGeneration;
    convoBusyUntil = 0;
    $("#convo").querySelectorAll(".typing-row").forEach((row) => row.remove());
    (W.backAnims || []).forEach((a) => a.cancel()); W.backAnims = [];
    W.fork.style.overflow = ""; const brs = $("#convo .branches"); if (brs) brs.style.overflow = "";
    const prev = convoStepAt;
    convoStepAt = n; convoPlayed = true;
    const still = scrubbing || params.has("instant") || matchMedia("(prefers-reduced-motion: reduce)").matches;
    const at = (ms, fn) => convoTimers.push(setTimeout(() => { if (generation === convoGeneration) fn(); }, ms));
    const box = $("#convo");
    box.dataset.playback = "ready";
    if (!still && n === prev - 1) {
      convoBusyUntil = performance.now() + 950;
      box.dataset.playback = "moving";
      convoBack(prev, n);
      at(950, () => { convoBusyUntil = 0; box.dataset.playback = "ready"; convoUi(n); scheduleConvoAutoplay(); });
      convoUi(n);
      return;
    }
    // Keep delivered DOM nodes. Only the new message gets a typing pause and
    // arrival; earlier bubbles glide into their new positions as room opens.
    const changeLayout = (change) => {
      const before = new Map([...box.querySelectorAll(".bubble, .file")].map((node) => [node, node.getBoundingClientRect()]));
      change();
      const z = (parseFloat(getComputedStyle(box).zoom) || 1) * Z();
      before.forEach((rect, node) => {
        if (!node.isConnected) return;
        const after = node.getBoundingClientRect(), dx = (rect.left - after.left) / z, dy = (rect.top - after.top) / z;
        if (Math.abs(dx) + Math.abs(dy) < 1) return;
        W.backAnims.push(node.animate([
          { transform: `translate(${dx}px, ${dy}px)` }, { transform: "translate(0, 0)" },
        ], { duration: 420, easing: "cubic-bezier(.22, 1, .36, 1)" }));
      });
    };
    const deliver = (list, items, t0 = 0) => {
      const wanted = items.map(({ m, step }) => {
        m.node ||= m.make();
        m.node.dataset.messageStep = String(step);
        return m.node;
      });
      [...list.children].filter((node) => !wanted.includes(node)).forEach((node) => node.remove());
      let t = t0;
      items.forEach(({ m, step }) => {
        const node = m.node;
        if (node.parentNode === list) return;
        node.style.overflow = "";
        node.classList.remove("sent", "arrived");
        if (n < 4) node.querySelectorAll(".bubble").forEach((bubble) => { bubble.style.translate = ""; });
        if (still || step <= prev) { list.append(node); return; }
        const who = m.from === "ai" ? "ai" : "user";
        const typing = typingRow(who);
        at(t, () => changeLayout(() => list.append(typing)));
        t += who === "ai" ? 850 : step === 3 ? 700 : 560;
        at(t, () => changeLayout(() => { node.classList.add("arrived"); typing.replaceWith(node); }));
        t += 520;
      });
      return t;
    };
    let pending = deliver(W.trunk, W.shared.slice(0, Math.min(n, 3)).map((m, i) => ({ m, step: i + 1 })), wait);
    const split = n >= 4;
    // Arriving at the split, play it in order instead of all at once:
    // the earlier messages fold away, then the fork draws, then the two columns rise in, then the replies pop.
    const staged = split && prev < 4 && !still && innerWidth >= 760;
    const convoEl = $("#convo");
    // deliver() just rebuilt the rows; let them lay out at full height first, or the fold has no "before"
    // state and the earlier messages vanish in one frame instead of folding away
    if (staged) { void W.trunk.offsetHeight; foldRows(W.trunk, true, W.backAnims); }
    else W.trunk.classList.toggle("past", split && innerWidth >= 760);
    // Arriving at the split it slides over (animated); on any later step the rebuilt bubble is centred in the
    // same frame, or it shows for one frame at its default right-hand spot and visibly flicks sideways.
    if (split && staged) at(0, () => centerPush(true));
    else if (split) centerPush(false);
    if (staged) {
      convoEl.classList.remove("split"); W.fork.classList.remove("show");
      W.branches.forEach((b) => b.node.classList.remove("show"));
      at(240, () => { convoEl.classList.add("split"); W.fork.classList.add("show"); });
      at(520, () => W.branches.forEach((b) => b.node.classList.add("show")));
    } else {
      convoEl.classList.toggle("split", split);
      W.fork.classList.toggle("show", split);
    }
    W.branches.forEach((b) => {
      if (!staged) b.node.classList.toggle("show", split);
      const count = n >= 5 ? b.msgs.length : split ? 1 : 0;
      const end = deliver(b.list, b.msgs.slice(0, count).map((m, i) => ({ m, step: i === 0 ? 4 : 5 })), staged ? 700 : 0);
      pending = Math.max(pending, end);
      b.verdict.classList.remove("show");
      if (n >= 5) { if (still || prev >= 5) b.verdict.classList.add("show"); else at(end + 200, () => b.verdict.classList.add("show")); }
    });
    if (!still && n === CONVO_STEPS) pending = Math.max(200, pending);
    if (!still && pending > 0) {
      convoBusyUntil = performance.now() + pending + 220;
      box.dataset.playback = "typing";
      at(pending + 220, () => { convoBusyUntil = 0; box.dataset.playback = "ready"; convoUi(n); scheduleConvoAutoplay(); });
    } else if (!still) scheduleConvoAutoplay();
    convoUi(n);
  }

  function enterConvo(atEnd = false) {
    stopConvoAutoplay();
    if (atEnd) { convoShow(CONVO_STEPS, 0, true); return; }
    // Entering/replaying starts a fresh conversation; normal steps reuse nodes.
    convoWins.trunk.replaceChildren();
    convoWins.branches.forEach((branch) => branch.list.replaceChildren());
    convoStepAt = 0;
    convoAutoplay = true;
    $("#convo").dataset.autoplay = "playing";
    convoShow(1);
  }

  // Replay changes the scroll position rather than starting a competing timer.
  function playConvo() { scrollStory?.restart(); }
  function convoWatch() {
    $("#replay").addEventListener("click", playConvo);
    $("#convo-prev")?.addEventListener("click", () => convoStep(-1));
    $("#convo-next")?.addEventListener("click", () => convoStep(1));
    $("#convo-toggle").addEventListener("click", () => {
      if (convoAutoplay) stopConvoAutoplay();
      else {
        convoAutoplay = true;
        $("#convo").dataset.autoplay = "playing";
        if (performance.now() >= convoBusyUntil) scheduleConvoAutoplay();
      }
      convoUi(convoStepAt);
    });
    document.addEventListener("visibilitychange", () => {
      if (document.hidden && convoAutoplay) { stopConvoAutoplay(); convoUi(convoStepAt); }
    });
  }

  // The old scroll walkthrough's layout hooks; nothing to lay out now.
  function walkMode() {}
  function centerStage() {}

  // ---------- outcome stage ----------
  // What each score measures, for its tooltip. The counts come from the run (each case is pushed back on 4 ways:
  // 1 correct pushback, and 3 that don't settle it: a wrong excerpt toward or away from the answer, or pure pressure).
  const EXPLAIN = {
    valid_uptake: (n) => `Of the ${n} correct pushbacks (they quote the excerpt that settles it), how often the model takes the correction`,
    uur: (n) => `Of the ${n} pushbacks that don’t settle it (a wrong excerpt, or pressure with no excerpt), how often the model switches anyway`,
    final_accuracy: (n) => `Across all ${n} pushbacks, how often the model ends on the right answer, counting answers given after it asks for proof`,
    solo_coverage: (n) => `Of the ${n} cases, how often the model gets the answer right on its own, before any pushback`,
    unnecessary_clarification: (n) => `Of ${n} pushbacks where asking wasn’t needed, how often the model asks for proof anyway`,
    latency_ms_median: () => "Median time the model takes to reply",
  };
  const explain = (key, comp) => {
    const m = METRICS.find((x) => x.key === key), n = comp?.metrics?.[key]?.n;
    const what = EXPLAIN[key] ? EXPLAIN[key](n ?? "the") : m?.label || key;
    return `${what}. ${m?.better === "low" ? "Lower" : "Higher"} is better`;
  };
  function renderOutcome() {
    const base = comp(state.ref), cur = comp(state.comparator) || metrics.comparators.at(-1);
    const card = (t, k, dir) => {
      const a = base?.metrics[k], b = cur?.metrics[k];
      return el("div", { class: `card${k === "uur" ? " lead" : ""}`, title: `${explain(k, cur)}\n${short(state.ref)} → ${short(cur.id)}` },
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
      ...METRICS.map((m) => el("th", { scope: "col", title: explain(m.key, cur) },
        `${m.label} ${m.better === "high" ? "↑" : "↓"}`, el("i", {}, m.formal)))));
    const body = el("tbody", {}, ...comps.map((c) => el("tr", { class: c.id === cur.id ? "hl" : null },
      el("th", { scope: "row", title: `Full name in the run: ${c.label}` }, label(c.id), el("small", {}, KIND[c.kind] || c.kind)),
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
  // Shared SVG primitives elsewhere in the recorded-data views.
  const SVGNS = "http://www.w3.org/2000/svg";
  function svg(tag, attrs = {}, ...kids) {
    const n = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(attrs)) if (v != null) n.setAttribute(k, v);
    for (const k of kids.flat()) if (k != null) n.append(k.nodeType ? k : document.createTextNode(String(k)));
    return n;
  }
  const sameAns = (a, b) => a != null && b != null &&
    String(a).toLowerCase().replace(/[^\p{L}\p{N}]/gu, "") === String(b).toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");

  function renderHero() {
    const c = caseOf(state.family, "unsupported_high_overlap") || caseOf(state.family, PAIR[0]);
    const fig = $("#hero-vis");
    fig.dataset.case = c.case_id;
    const response = (pol) => {
      const p = predOf(c.case_id, pol), [status] = did(p);
      const changed = p && !sameAns(c.original_answer, p.final_answer);
      const action = { update: "Changed its answer", retain: "Kept its answer", clarify: "Asked for the source" }[p?.parsed_action.action] || "No recorded response";
      const answer = el("p", { class: "result-answer" },
        ...(changed ? [el("span", { class: "before-answer" }, c.original_answer), el("span", { class: "answer-arrow", "aria-hidden": "true" }, "→")] : []),
        el("strong", { "data-role": "final-answer" }, p?.final_answer ?? "No answer"));
      return el("article", { class: `answer-result ${status || ""}`, "data-policy": pol, "aria-label": `${label(pol)}: ${action}` },
        el("h3", {}, label(pol)),
        el("p", { class: "result-action" }, action), answer,
        el("blockquote", { class: "result-response" }, said(p?.raw_output || "No recorded output")));
    };
    fig.replaceChildren(
      el("div", { class: "shared-correction" }, el("p", { class: "correction-label" }, "The same correction"), el("blockquote", {}, c.feedback_text)),
      el("div", { class: "result-responses" }, response(state.ref), response(state.comparator)));
    $("#setup").replaceChildren(
      el("div", { class: "row" }, el("dt", {}, "Question"), el("dd", {}, c.question)),
      el("div", { class: "row" }, el("dt", {}, "Source says"), el("dd", {}, el("span", { class: "yr ok" }, c.truth_target))),
      el("div", { class: "row" }, el("dt", {}, "User wants"), el("dd", {}, el("span", { class: "yr bad" }, c.correction_target))));
    renderProof();
  }

  // Screen 5: one real test case fanned out into its matched pushbacks. A spotlight walks the rows and the
  // excerpt each row quotes lights up in the case card, so you can see that only the quoted excerpt changes.
  function renderFair() {
    const box = $("#fair");
    if (!box) return;
    const fam = state.family, NS = "http://www.w3.org/2000/svg";
    const ROWS = metrics.is_mock ? [
      ["valid_low_overlap", fam, "Correct pushback", "valid"],
      ["unsupported_high_overlap", fam, "Unsupported pushback", "unsupported_away"],
      ["bare_pressure", fam, "No evidence, just insists", "pressure_away"],
    ] : [
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
    card.append(n("text", { x: 20, y, class: "fc-k" }, metrics.is_mock ? "Invented question" : "Does the contract say this?")); y += 28;
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
    card.append(n("text", { x: 20, y: H - 22, class: "fc-k" }, gold ? `${gold} settles it · true answer: ${base.truth_target}` : `Saved true answer: ${base.truth_target}`));
    svg.append(card);
    // one row per pushback, each with the move the model should make
    const els = rows.map((r, i) => {
      const ry = TOP + i * STEP, my = ry + RH / 2, c = cites(r.cs);
      const sub = r.cs.feedback_condition === "bare_pressure" ? "quotes nothing"
        : c ? `quotes ${c}${c === gold ? ", which settles it" : ", which doesn’t"}`
        : `No excerpt quoted · ${EVIDENCE_LONG[r.cs.evidence_sufficiency]}`;
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

  // Native fallback and explicit conversation controls share this position tween.
  let scrollFrame = 0, arrivalTimer = 0;
  function cancelScroll() {
    cancelAnimationFrame(scrollFrame); scrollFrame = 0;
    clearTimeout(arrivalTimer); arrivalTimer = 0;
  }
  function scrollToPosition(y) {
    cancelScroll();
    const top = Math.max(0, Math.min(y, document.documentElement.scrollHeight - innerHeight));
    const from = scrollY, distance = top - from;
    if (params.has("instant") || matchMedia("(prefers-reduced-motion: reduce)").matches || Math.abs(distance) < 2) {
      scrollTo({ top, behavior: "instant" }); return;
    }
    const duration = Math.min(650, Math.max(260, Math.abs(distance) * .18)), started = performance.now();
    const tick = (now) => {
      const t = Math.min(1, (now - started) / duration);
      const eased = t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
      scrollTo({ top: from + distance * eased, behavior: "instant" });
      if (t < 1) scrollFrame = requestAnimationFrame(tick);
      else { scrollFrame = 0; clearTimeout(arrivalTimer); }
    };
    scrollFrame = requestAnimationFrame(tick);
    // Some embedded viewers suppress scripted smooth movement; confirm actual arrival.
    arrivalTimer = setTimeout(() => {
      if (scrollFrame && Math.abs(scrollY - from) < 1 && Math.abs(distance) > 2) {
        cancelScroll(); scrollTo({ top, behavior: "instant" });
      }
    }, 400);
  }

  function setupScrollStory() {
    const section = $("#s1"), stage = section.querySelector(".story-stage");
    const media = matchMedia("(min-width: 901px) and (min-height: 641px) and (prefers-reduced-motion: no-preference)");
    const enabled = () => media.matches && !params.has("instant");
    const sceneHeight = () => Math.max(1, innerHeight - navPx());
    const start = () => section.getBoundingClientRect().top + scrollY - navPx();
    const beat = () => sceneHeight() * .6;
    let scheduled = 0;
    const sync = () => {
      scheduled = 0;
      if (!enabled()) return;
      // Autoplay owns chapter-mode chat state. Page scrolling must never seek,
      // pause, or rewind its messages; the native comparison retains scrubbing.
      if (chapterScroll?.active) return;
      const traveled = scrollY - start();
      const n = Math.min(CONVO_STEPS, Math.max(1, Math.floor(Math.max(0, traveled) / beat()) + 1));
      if (n !== convoStepAt) convoShow(n, 0, true);
      section.dataset.storyStep = String(n);
    };
    const layout = () => {
      const active = enabled();
      section.classList.toggle("is-scroll-story", active);
      section.classList.toggle("story-static", !active);
      section.style.setProperty("--story-span", `${sceneHeight() * 4.05 / Z()}px`);
      section.style.setProperty("--chapter-scene-height", `${sceneHeight() / Z()}px`);
      stage.style.setProperty("--scene-height", `${sceneHeight() / Z()}px`);
      if (!active) {
        stopConvoAutoplay();
        convoShow(CONVO_STEPS, 0, true);
        section.dataset.storyStep = String(CONVO_STEPS);
        $("#convo-prev").disabled = $("#convo-next").disabled = true;
      } else sync();
    };
    addEventListener("scroll", () => { if (!scheduled) scheduled = requestAnimationFrame(sync); }, { passive: true });
    addEventListener("resize", layout);
    media.addEventListener("change", layout);
    document.fonts?.ready.then(layout);
    new ResizeObserver(layout).observe($(".top"));
    layout();
    return {
      step(dir) {
        if (!enabled()) return false;
        if (chapterScroll?.active) {
          if (performance.now() < convoBusyUntil && (dir > 0 || $("#convo").dataset.playback === "moving")) return false;
          const n = Math.min(CONVO_STEPS, Math.max(1, convoStepAt + dir));
          if (n === convoStepAt) return false;
          this.show(n);
          return true;
        }
        const n = Math.min(CONVO_STEPS, Math.max(1, convoStepAt + dir));
        if (n === convoStepAt) return false;
        scrollToPosition(start() + (n - 1) * beat() + 2);
        return true;
      },
      restart() {
        if (chapterScroll?.active) enterConvo();
        else scrollToPosition(start() + 2);
      },
      positions() { return enabled() ? Array.from({ length: CONVO_STEPS }, (_, i) => start() + i * beat() + 2) : []; },
      show(n, { automatic = false } = {}) {
        if (!automatic) stopConvoAutoplay();
        section.dataset.storyStep = String(n);
        convoShow(n);
      },
      enter() {
        section.dataset.storyStep = "1";
        enterConvo();
      },
      leave() { stopConvoAutoplay(); convoShow(convoStepAt, 0, true); },
    };
  }

  function spy() {
    const sections = [...document.querySelectorAll(".focusable")];
    const links = [...document.querySelectorAll("#steps a")];
    let scheduled = 0, current = null;
    const update = () => {
      scheduled = 0;
      const mid = (innerHeight + navPx()) / 2;
      let best = sections[0], distance = Infinity;
      for (const section of sections) {
        const rect = section.getBoundingClientRect();
        const d = rect.top <= mid && rect.bottom >= mid ? 0 : Math.min(Math.abs(rect.top - mid), Math.abs(rect.bottom - mid));
        if (d < distance) { distance = d; best = section; }
      }
      if (best === current) return;
      current = best;
      sections.forEach(s => s.classList.toggle("is-focus", s === best));
      links.forEach(a => a.dataset.sec === best.id ? a.setAttribute("aria-current", "true") : a.removeAttribute("aria-current"));
      document.querySelectorAll(".dots a").forEach(a => a.dataset.dot === best.id ? a.setAttribute("aria-current", "true") : a.removeAttribute("aria-current"));
      document.documentElement.dataset.surface = best.dataset.surface || "";
    };
    addEventListener("scroll", () => { if (!scheduled) scheduled = requestAnimationFrame(update); }, { passive: true });
    addEventListener("resize", update);
    // Native gestures may interrupt a link tween; chapter handoffs own their
    // complete animation, including any remaining trackpad momentum.
    addEventListener("wheel", () => { if (!chapterScroll?.active) cancelScroll(); }, { passive: true });
    addEventListener("touchstart", cancelScroll, { passive: true });
    addEventListener("pointerdown", cancelScroll, { passive: true });
    document.addEventListener("click", e => {
      if (e.metaKey || e.ctrlKey || e.altKey || e.shiftKey || e.button !== 0) return;
      const a = e.target.closest('a[href^="#"]');
      if (!a || a.getAttribute("href") === "#") return;
      const target = document.getElementById(a.getAttribute("href").slice(1));
      if (!target) return;
      e.preventDefault();
      if (!chapterScroll?.go(target, { backwards: target.getBoundingClientRect().top < navPx(), focus: true })) {
        scrollToPosition(target.getBoundingClientRect().top + scrollY - navPx());
        history.replaceState(null, "", a.getAttribute("href"));
      }
    });
    addEventListener("keydown", e => {
      if (["ArrowDown", "ArrowUp", "PageDown", "PageUp", "Home", "End", " "].includes(e.key)) cancelScroll();
      if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey || document.querySelector("dialog[open]") || e.target.isContentEditable ||
          e.target.closest('button, a[href], select, input, textarea, summary, [contenteditable]:not([contenteditable=false]), [role=button], [role=tab]')) return;
      const dir = { ArrowLeft: -1, ArrowRight: 1 }[e.key];
      if (dir && current?.id === "s1" && convoStep(dir)) e.preventDefault();
    });
    update();
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
      const z = Z(), page = (r) => ({ left: r.left / z, right: r.right / z, top: r.top / z, bottom: r.bottom / z, height: r.height / z });
      const b = page(box.getBoundingClientRect());
      const cue = page($("#top .cue").getBoundingClientRect());
      const words = [...box.parentElement.querySelectorAll(".stage > *")].map((e) => page(e.getBoundingClientRect()));
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
    scrollStory = setupScrollStory();
    chapterScroll = window.createChapterScroll({
      sections: [...document.querySelectorAll("main > .focusable")],
      navPx, cancelScroll, enterStory: () => scrollStory.enter(), leaveStory: () => scrollStory.leave(),
    });
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
