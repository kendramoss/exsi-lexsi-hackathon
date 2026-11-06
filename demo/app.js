// EvidenceTune demo. Reads saved artifacts only:
//   data/results/<run_id>/cases.jsonl, predictions.jsonl, metrics.json
// ?run=<run_id> (default mock-smoke), ?step=1|2|3, ?all=1. Never recomputes metrics: per-case verdicts
// come from the `score` block in predictions.jsonl, and every claim on screen is conditional on it.

(() => {
  "use strict";

  const params = new URLSearchParams(location.search);
  const RUN = (params.get("run") || "mock-smoke").replace(/[^a-z0-9_.-]/gi, "");
  const BASE = `data/results/${RUN}/`;
  const PAIR = ["valid_low_overlap", "unsupported_high_overlap"];
  const LANES = [
    { cond: "valid_low_overlap", key: "valid", label: "Valid", title: "Valid correction", tone: "low overlap" },
    { cond: "unsupported_high_overlap", key: "unsup", label: "Unsupported", title: "Unsupported correction", tone: "high overlap" },
    { cond: "bare_pressure", key: "pressure", label: "Pressure", title: "Bare pressure", tone: "no evidence" },
  ];
  const DOMAIN = { document: "Document", multihop_table_arith: "Table / arithmetic", arabic_comprehension: "Arabic" };
  const EVIDENCE = { supported: ["valid", "supported"], contradicted: ["unsup", "contradicted"], insufficient: ["unsup", "insufficient"], absent: ["", "no evidence"] };
  const METRICS = [
    { key: "valid_uptake", label: "Valid uptake", better: "high" },
    { key: "uur", label: "Unwarranted updates", better: "low" },
    { key: "final_accuracy", label: "Final accuracy", better: "high" },
    { key: "solo_coverage", label: "Solo coverage", better: "high" },
    { key: "unnecessary_clarification", label: "Unnecessary clarify", better: "low" },
    { key: "latency_ms_median", label: "Latency", better: "low", ms: true },
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
  const policy = () => (state.step === 0 ? "base" : state.comparator);

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
  function pin(p) {
    const a = p.parsed_action.action, s = p.score || {}, cite = citedIds(p).join(" ");
    if (a === "update" && s.unwarranted_update) return ["bad", "Caved", ""];
    if (a === "update" && cite) return ["valid", "Updated", `cites ${cite}`];
    if (a === "update") return ["unsup", "Updated", "no citation"];
    if (a === "clarify" && s.clarification_resolved) return ["clarify", "Asked", "resolved"];
    if (a === "clarify") return ["bad", "Asked", s.unnecessary_clarification ? "unneeded" : "unresolved"];
    if (a === "retain" && s.action_acceptable) return ["valid", "Held", cite ? `cites ${cite}` : ""];
    return ["bad", "Missed", ""];
  }

  // ---------- head ----------
  function renderHead() {
    const fam = state.family, pol = policy();
    const [v, u] = PAIR.map((c) => predOf(caseOf(fam, c).case_id, pol));
    const h = $("#headline");
    if (state.step === 2) {
      h.innerHTML = "Read the columns <em>together</em>";
      return;
    }
    if (state.step === 0) {
      const both = v && u && v.parsed_action.action === "update" && u.parsed_action.action === "update";
      h.innerHTML = both ? "Base Tiny Aya <em>gives in to both</em>" : "Base Tiny Aya <em>on the same pair</em>";
      return;
    }
    const good = v && u && v.score?.action_acceptable && u.score?.action_acceptable && v.parsed_action.action === "update";
    if (good && u.parsed_action.action === "clarify") h.innerHTML = "Cites the evidence,<br><em>asks when there&rsquo;s none</em>";
    else if (good) h.innerHTML = "Cites the evidence,<br><em>holds when there&rsquo;s none</em>";
    else h.innerHTML = `${esc(label(pol))}<br><em>on the same pair</em>`;
  }

  // ---------- pair stage ----------
  function renderPassage() {
    const c = caseOf(state.family, PAIR[0]);
    const shown = PAIR.map((cond) => predOf(caseOf(state.family, cond).case_id, policy()));
    const cited = new Set(shown.flatMap(citedIds));
    $("#passage").replaceChildren(
      el("h2", {}, c.question),
      ...spans(c.context).map((s) => el("div", { class: `span${cited.has(s.id) ? " cited" : ""}` },
        s.id ? el("b", {}, s.id) : null,
        el("span", { class: "span-text" }, s.text))),
    );
  }

  function lane(L) {
    const c = caseOf(state.family, L.cond);
    const p = predOf(c.case_id, policy());
    const ov = overlap(c.feedback_text, c.context);
    const [evCls, evText] = EVIDENCE[c.evidence_sufficiency] || ["", c.evidence_sufficiency];
    const box = el("article", { class: "win lane", role: "button", tabindex: "0", "aria-pressed": String(state.lane === L.key), "data-lane": L.key, "aria-label": `${L.title}: show in inspector` });
    const body = el("div", { class: "win-body" },
      el("h3", {}, L.title),
      el("div", { class: "chips" }, el("span", { class: `chip ${ov.share >= 0.5 ? "unsup" : "valid"}` }, `${pct(ov.share)} overlap`), el("span", { class: `chip ${evCls}` }, evText)),
      el("p", { class: "msg prior" }, "Before ", el("b", {}, c.original_answer)),
      el("div", { class: "msg user" }, el("small", {}, "User"), el("span", { html: ov.html })),
    );
    if (!p) {
      body.append(el("p", { class: "error" }, `No prediction for ${policy()} on ${c.case_id}.`));
    } else {
      body.append(el("div", { class: "msg model" }, el("small", {}, label(policy())), el("span", { html: cites(p.raw_output) })));
      if (p.clarification_turn) {
        body.append(
          el("div", { class: "msg user" }, el("small", {}, "User replies"), p.clarification_turn.user_reply ?? "(no reply)"),
          el("div", { class: "msg model" }, el("small", {}, label(policy())), el("span", { html: cites(p.clarification_turn.raw_output) })),
        );
      }
      const ok = p.score ? p.score.final_correct : null;
      body.append(el("p", { class: `final ${ok === false ? "ko" : ok ? "ok" : ""}` }, "After ", el("b", {}, p.final_answer ?? "none"), ok == null ? "" : ok ? " ✓" : " ✗"));
      const [pc, pk, pt] = pin(p);
      box.append(el("span", { class: "pin", style: `--c:var(--${pc})` }, el("span", { class: "k" }, pk), pt || null));
      if (p.error) body.append(el("p", { class: "error" }, p.error));
    }
    box.prepend(el("div", { class: "win-bar", "aria-hidden": "true" }, el("i"), el("i"), el("i")));
    box.append(body);
    return box;
  }

  // Decorative stepped pixel band: column heights from a tiny seeded generator, so it is stable per pair.
  function renderPixels() {
    const box = $("#pixels"), cols = 24, rows = 4;
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

  function renderPair() {
    renderPixels();
    $("#pair").replaceChildren(...LANES.filter((L) => PAIR.includes(L.cond)).map(lane));
    const pol = policy();
    const [v, u] = PAIR.map((c) => predOf(caseOf(state.family, c).case_id, pol));
    const note = $("#note");
    note.hidden = true;
    if (state.step === 0 && v && u && v.parsed_action.action === "update" && u.parsed_action.action === "update") {
      note.textContent = "same reflex both times"; note.style.color = "var(--blue)"; note.hidden = false;
    } else if (state.step === 1 && u && u.parsed_action.action === "clarify" && u.score?.clarification_resolved) {
      note.textContent = "asks instead of caving ↑"; note.style.color = ""; note.hidden = false;
    }
  }

  function renderInspector() {
    const L = LANES.find((l) => l.key === state.lane) || LANES[1];
    const c = caseOf(state.family, L.cond);
    const ins = $("#inspector");
    const seg = el("div", { class: "seg", role: "group", "aria-label": "Choose case" },
      ...LANES.filter((l) => caseOf(state.family, l.cond)).map((l) =>
        el("button", { type: "button", "aria-pressed": String(l.key === L.key), "data-lane": l.key }, l.label)));
    if (!c) { ins.replaceChildren(seg); return; }
    const p = predOf(c.case_id, policy());
    const row = (k, v, cls) => el("div", { class: "row" }, el("span", {}, k), typeof v === "string" ? el("code", { class: cls || null }, v) : v);
    const yes = (b, t, f) => el("span", { class: `val ${b ? "ok" : "ko"}` }, b ? `✓ ${t}` : `✗ ${f}`);
    const parts = [
      seg,
      el("div", {}, el("h4", {}, "Answer key"),
        row("truth", c.truth_target), row("pushed toward", c.correction_target ?? "none"),
        row("evidence", c.evidence_sufficiency, c.evidence_sufficiency === "supported" ? "ok" : c.evidence_sufficiency === "contradicted" ? "ko" : ""),
        row("acceptable", c.acceptable_actions.join(" · "))),
    ];
    if (p) {
      const s = p.score || {};
      const did = el("div", {}, el("h4", {}, label(policy())),
        row("action", "action_acceptable" in s ? yes(s.action_acceptable, p.parsed_action.action, p.parsed_action.action) : p.parsed_action.action));
      if ("final_correct" in s) did.append(row("final", yes(s.final_correct, p.final_answer, p.final_answer)));
      did.append(row("latency", `${Math.round(p.latency_ms).toLocaleString()} ms`));
      parts.push(did);
      parts.push(el("div", { class: "hash" }, `${c.case_id}`, el("br"), `${p.model} · ${p.run_id}`));
    }
    ins.replaceChildren(...parts);
  }

  // ---------- outcome stage ----------
  function renderOutcome() {
    const base = comp("base"), cur = comp(state.comparator) || metrics.comparators.at(-1);
    const card = (t, k) => {
      const a = base?.metrics[k], b = cur?.metrics[k];
      return el("div", { class: "card" }, el("small", {}, t), el("b", {}, a && b ? `${pct(a.value)} → ${pct(b.value)}` : "n/a"));
    };
    $("#cards").replaceChildren(card("Caving", "uur"), card("Valid uptake", "valid_uptake"), card("Final accuracy", "final_accuracy"));

    const comps = metrics.comparators;
    const ext = Object.fromEntries(METRICS.map((m) => {
      const vals = comps.map((c) => (m.ms ? c.metrics[m.key] : c.metrics[m.key]?.value)).filter((v) => v != null);
      const best = m.better === "high" ? Math.max(...vals) : Math.min(...vals);
      const worst = m.better === "high" ? Math.min(...vals) : Math.max(...vals);
      return [m.key, { best, worst, distinct: best !== worst }];
    }));
    const head = el("thead", {}, el("tr", {}, el("th", { scope: "col" }, "Comparator"),
      ...METRICS.map((m) => el("th", { scope: "col" }, `${m.label} ${m.better === "high" ? "↑" : "↓"}`))));
    const body = el("tbody", {}, ...comps.map((c) => el("tr", { class: c.id === cur.id ? "hl" : null },
      el("th", { scope: "row" }, c.label),
      ...METRICS.map((m) => el("td", {}, cell(c.metrics[m.key], m, ext[m.key]))))));
    $("#scoreboard").replaceChildren(head, body);
    $("#table-path").textContent = `${BASE}metrics.json`;
    const n = comps[0].metrics.valid_uptake?.n;
    $("#score-note").textContent = `Bars: 95% intervals · n = ${n} valid corrections each`;

  }
  function cell(metric, m, ex) {
    if (metric == null) return el("span", {}, "n/a");
    const v = m.ms ? metric : metric.value;
    const cls = ex.distinct && v === ex.best ? " best" : ex.distinct && v === ex.worst ? " worst" : "";
    const box = el("div", {}, el("span", { class: `v${cls}` }, m.ms ? `${Math.round(v).toLocaleString()} ms` : pct(v)));
    if (!m.ms && metric.ci_low != null) {
      box.append(el("div", { class: "ci", role: "img", "aria-label": `95% interval ${pct(metric.ci_low)} to ${pct(metric.ci_high)}, n=${metric.n}` },
        el("span", { class: "r", style: `left:${metric.ci_low * 100}%;width:${(metric.ci_high - metric.ci_low) * 100}%` }),
        el("span", { class: "p", style: `left:calc(${v * 100}% - 1px)` })));
    }
    return box;
  }

  // ---------- step + wiring ----------
  function renderAll() { renderHead(); renderPassage(); renderPair(); renderInspector(); renderOutcome(); }
  function setStep(i) {
    state.step = Math.max(0, Math.min(2, i));
    $("#stage-pair").classList.toggle("active", state.step < 2);
    $("#stage-outcome").classList.toggle("active", state.step === 2);
    document.querySelectorAll("#steps button").forEach((b) => {
      if (+b.dataset.step === state.step) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current");
    });
    const all = document.body.classList.contains("show-all");
    $("#comparator-wrap").hidden = state.step === 0 && !all;
    $("#family").closest("label").hidden = state.step === 2 && !all;
    $("#prev").disabled = state.step === 0;
    $("#next").disabled = state.step === 2;
    renderAll();
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
    document.querySelectorAll("#steps button").forEach((b) => b.addEventListener("click", () => setStep(+b.dataset.step)));
    $("#prev").addEventListener("click", () => setStep(state.step - 1));
    $("#next").addEventListener("click", () => setStep(state.step + 1));
    $("#family").addEventListener("change", (e) => { state.family = e.target.value; renderAll(); });
    $("#comparator").addEventListener("change", (e) => { state.comparator = e.target.value; renderAll(); });
    const pick = (e) => {
      const t = e.target.closest("[data-lane]");
      if (!t) return;
      state.lane = t.dataset.lane; renderPair(); renderInspector();
    };
    $("#pair").addEventListener("click", pick);
    $("#pair").addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(e); } });
    $("#inspector").addEventListener("click", pick);
    document.addEventListener("keydown", (e) => {
      if (e.target.closest("select, input, textarea, [role=button]")) return;
      if (e.key === "ArrowRight") setStep(state.step + 1);
      if (e.key === "ArrowLeft") setStep(state.step - 1);
    });
  }

  load().then(() => {
    $("#mock-badge").hidden = !metrics.is_mock;
    $("#src-path").textContent = BASE;
    selectors();
    bind();
    if (params.get("all") === "1") document.body.classList.add("show-all");
    setStep((parseInt(params.get("step"), 10) || 1) - 1);
  }).catch((err) => {
    $("#main").replaceChildren(el("p", { class: "error" },
      `Could not load run "${RUN}": ${err.message}. Serve the demo folder over HTTP (python -m http.server) rather than opening the file directly.`));
    console.error(err);
  });
})();
