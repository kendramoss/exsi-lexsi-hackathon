// EvidenceTune demo. Reads saved artifacts only:
//   data/results/<run_id>/cases.jsonl, predictions.jsonl, metrics.json
// ?run=<run_id> (default mock-smoke), ?step=2|3 jumps to a section. Never recomputes metrics: per-case verdicts
// come from the `score` block in predictions.jsonl, and every claim on screen is conditional on it.

(() => {
  "use strict";

  const params = new URLSearchParams(location.search);
  const RUN = (params.get("run") || "mock-smoke").replace(/[^a-z0-9_.-]/gi, "");
  const BASE = `data/results/${RUN}/`;
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
    const c = laneCase();
    const [, bt] = did(predOf(c.case_id, "base")), [, tt] = did(predOf(c.case_id, state.comparator));
    $("#s1-title").innerHTML = `${esc(short("base"))} ${esc(bt)},<br><em>${esc(short(state.comparator))} ${esc(tt)}</em>`;
    $("#s2-lead").textContent = `One example could be luck. Here is every model on all ${metrics.dataset.n_cases} test cases. Read each row across: a model that never changes its answer never gives in, but it also ignores correct pushback.`;
  }

  // ---------- compare stage ----------
  function renderPassage() {
    const c = laneCase();
    const cited = new Set(["base", state.comparator].flatMap((pol) => citedIds(predOf(c.case_id, pol))));
    $("#passage").replaceChildren(
      el("h2", {}, c.question),
      ...spans(c.context).map((s) => el("div", { class: `span${cited.has(s.id) ? " cited" : ""}` },
        s.id ? el("b", { title: `Line ${s.id.slice(1)} of the passage` }, s.id) : null,
        el("span", { class: "span-text" }, s.text))),
    );
  }

  function renderPush() {
    const L = currentLane(), c = laneCase();
    $("#pushseg").replaceChildren(...LANES.filter((l) => caseOf(state.family, l.cond)).map((l) =>
      el("button", { type: "button", role: "tab", "aria-selected": String(l.key === L.key), "data-lane": l.key }, l.label)));
    const ov = overlap(c.feedback_text, c.context);
    const [evCls, evText] = EVIDENCE[c.evidence_sufficiency] || ["", c.evidence_sufficiency];
    $("#push").replaceChildren(
      el("p", { class: "msg prior" }, "First answer ", el("b", {}, c.original_answer)),
      el("div", { class: "msg user" }, el("small", {}, "User"), el("span", { html: ov.html })),
      el("div", { class: "chips" },
        el("span", { class: `chip ${ov.share >= 0.5 ? "unsup" : "valid"}`, title: "Highlighted words also appear in the passage" }, `${pct(ov.share)} copied`),
        el("span", { class: `chip ${evCls}` }, evText)),
    );
  }

  function reply(pol) {
    const c = laneCase(), p = predOf(c.case_id, pol);
    const box = el("article", { class: "win" });
    box.append(el("div", { class: "win-bar" }, el("i", { "aria-hidden": "true" }), el("i", { "aria-hidden": "true" }), el("i", { "aria-hidden": "true" }),
      el("span", {}, label(pol))));
    const body = el("div", { class: "win-body" });
    if (!p) {
      body.append(el("p", { class: "error" }, `No result for ${label(pol)} on this case.`));
    } else {
      body.append(el("div", { class: "msg model" }, el("span", { html: cites(p.raw_output) })));
      if (p.clarification_turn) {
        body.append(
          el("div", { class: "msg user" }, el("small", {}, "User"), p.clarification_turn.user_reply ?? "(no reply)"),
          el("div", { class: "msg model" }, el("span", { html: cites(p.clarification_turn.raw_output) })),
        );
      }
      const ok = p.score ? p.score.final_correct : null;
      body.append(el("p", { class: `final ${ok === false ? "ko" : ok ? "ok" : ""}` }, "Final ", el("b", {}, p.final_answer ?? "none"), ok == null ? "" : ok ? " ✓" : " ✗"));
      const [pc, pk, pt] = pin(p);
      box.append(el("span", { class: "pin", style: `--c:var(--${pc})` }, el("span", { class: "k" }, pk)));
      if (p.error) body.append(el("p", { class: "error" }, p.error));
    }
    box.append(body);
    return box;
  }

  // Decorative stepped pixel band: column heights from a tiny seeded generator, so it is stable per example.
  function renderPixels() {
    const box = $("#pixels"), cols = innerWidth < 760 ? 16 : 40, rows = 3;
    let seed = [...state.family].reduce((a, ch) => (a * 31 + ch.charCodeAt(0)) >>> 0, 7);
    const rnd = () => ((seed = (seed * 1103515245 + 12345) >>> 0) / 4294967296);
    let h = 1;
    const cells = [];
    for (let c = 0; c < cols; c++) {
      h = Math.max(0, Math.min(rows, h + Math.round(rnd() * 2 - 1)));
      for (let r = 0; r < rows; r++) cells.push(r >= rows - h ? 1 : rnd() < 0.06 ? 1 : 0);
    }
    box.style.setProperty("--cols", cols);
    box.replaceChildren(...cells.map((on, i) => el("i", { class: on ? "on" : null, style: `grid-column:${(i / rows | 0) + 1};grid-row:${(i % rows) + 1}` })));
  }

  function renderCompare() {
    renderPassage();
    renderPush();
    renderPixels();
    $("#pair").replaceChildren(reply("base"), reply(state.comparator));
    renderScorecard();
  }

  // Scorecard for this example: every pushback type, both models, plus the facts for the selected one.
  function renderScorecard() {
    const rows = LANES.filter((l) => caseOf(state.family, l.cond)), L = currentLane(), c = laneCase();
    const cellFor = (cs, pol) => { const [k, t] = did(predOf(cs.case_id, pol)); return el("td", { class: k }, `${k === "ok" ? "✓" : k === "ko" ? "✗" : ""} ${t}`); };
    const table = el("table", { class: "mini" },
      el("thead", {}, el("tr", {}, el("th", { scope: "col" }, "Pushback"),
        el("th", { scope: "col" }, short("base")), el("th", { scope: "col" }, short(state.comparator)))),
      el("tbody", {}, ...rows.map((l) => {
        const cs = caseOf(state.family, l.cond);
        return el("tr", { class: l.key === L.key ? "hl" : null, "data-lane": l.key, tabindex: "0", "aria-selected": String(l.key === L.key) },
          el("th", { scope: "row" }, l.label),
          cellFor(cs, "base"), cellFor(cs, state.comparator));
      })));
    const row = (k, v) => el("div", { class: "row" }, el("span", {}, k), el("span", { class: "val" }, v));
    $("#inspector").replaceChildren(
      el("div", { class: "score" }, el("h4", {}, "All pushbacks"), el("div", { class: "table-scroll" }, table)),
      el("div", {}, el("h4", {}, "Answer key"),
        row("Passage says", c.truth_target),
        row("Pushback claims", c.correction_target ?? "nothing specific"),
        row("Good responses", c.acceptable_actions.map((a) => ACTION_SHORT[a] || a).join(" or "))),
    );
  }

  // ---------- outcome stage ----------
  function renderOutcome() {
    const base = comp("base"), cur = comp(state.comparator) || metrics.comparators.at(-1);
    const card = (t, k, dir) => {
      const a = base?.metrics[k], b = cur?.metrics[k];
      return el("div", { class: "card" }, el("small", {}, t), el("b", {}, a && b ? `${pct(a.value)} → ${pct(b.value)}` : "n/a"),
        el("p", {}, `${dir} is better`));
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
      ...METRICS.map((m) => el("td", {}, cell(c.metrics[m.key], m, ext[m.key]))))));
    $("#scoreboard").replaceChildren(head, body);
    $("#table-path").textContent = `${BASE}metrics.json`;
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
  function renderAll() { renderHead(); renderCompare(); renderOutcome(); }

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
      links.forEach((a) => { if (a.dataset.sec === best.id) a.setAttribute("aria-current", "true"); else a.removeAttribute("aria-current"); });
    };
    // Sections taller than the screen snap to their top instead of the centre.
    const sizes = () => secs.forEach((s) => s.classList.toggle("tall", s.scrollHeight > innerHeight - 49));
    addEventListener("scroll", () => requestAnimationFrame(update), { passive: true });
    addEventListener("resize", () => { sizes(); update(); });
    new ResizeObserver(sizes).observe(document.body);
    sizes();
    update();
    document.addEventListener("click", (e) => {
      const a = e.target.closest('a[href^="#"]');
      if (!a) return;
      const t = document.querySelector(a.getAttribute("href"));
      if (!t) return;
      e.preventDefault();
      const tall = t.offsetHeight > innerHeight - 49;
      t.scrollIntoView({ block: tall ? "start" : "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
      history.replaceState(null, "", a.getAttribute("href"));
    });
  }
  function selectors() {
    const fams = [...new Set(cases.map((c) => c.family_id))].filter((f) => PAIR.every((c) => caseOf(f, c)));
    state.family = fams[0];
    $("#family").replaceChildren(...fams.map((f) => {
      const c = caseOf(f, PAIR[0]);
      return el("option", { value: f }, `${DOMAIN[c.domain] || c.domain} · ${c.question}`);
    }));
    const comps = metrics.comparators.filter((c) => c.id !== "base");
    if (!comps.some((c) => c.id === state.comparator)) state.comparator = comps.at(-1).id;
    $("#comparator").replaceChildren(...comps.map((c) => el("option", { value: c.id, selected: c.id === state.comparator }, c.label)));
  }
  function bind() {
    $("#family").addEventListener("change", (e) => { state.family = e.target.value; renderAll(); });
    $("#comparator").addEventListener("change", (e) => { state.comparator = e.target.value; renderAll(); });
    const pick = (e) => {
      const t = e.target.closest("[data-lane]");
      if (!t) return;
      state.lane = t.dataset.lane; renderHead(); renderCompare();
    };
    $("#stage-pair").addEventListener("click", pick);
    $("#stage-pair").addEventListener("keydown", (e) => { if ((e.key === "Enter" || e.key === " ") && e.target.closest("tr[data-lane]")) { e.preventDefault(); pick(e); } });
  }

  // Horizontal showcase: vertical scroll drives the panel track sideways (native swipe row on phones / reduced motion).
  function hscroll() {
    const sec = $("#how"), sticky = sec.querySelector(".hs-sticky"), track = $("#hs-track"), panels = track.children;
    const native = () => innerWidth < 760 || matchMedia("(prefers-reduced-motion: reduce)").matches;
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
    addEventListener("resize", layout);
    track.querySelectorAll("img").forEach((img) => img.addEventListener("load", layout));
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
