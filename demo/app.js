// EvidenceTune demo. Reads saved artifacts only:
//   data/results/<run_id>/cases.jsonl, predictions.jsonl, metrics.json
// Pick a run with ?run=<run_id> (default: mock-smoke). Never recomputes headline metrics;
// per-case verdicts come from the `score` block the metric suite writes into predictions.jsonl.

(() => {
  "use strict";

  const params = new URLSearchParams(location.search);
  const RUN = (params.get("run") || "mock-smoke").replace(/[^a-z0-9_.-]/gi, "");
  const BASE = `data/results/${RUN}/`;
  const PAIR = ["valid_low_overlap", "unsupported_high_overlap"];
  const LANE = {
    valid_low_overlap: { cls: "valid", title: "Valid correction", sub: "low word overlap, backed by the passage" },
    unsupported_high_overlap: { cls: "unsup", title: "Unsupported correction", sub: "high word overlap, contradicted by the passage" },
  };
  const DOMAIN = { document: "Document", multihop_table_arith: "Table / arithmetic", arabic_comprehension: "Arabic" };
  const METRICS = [
    { key: "valid_uptake", label: "Valid uptake", dir: "↑", better: "high" },
    { key: "uur", label: "Unwarranted-update rate", dir: "↓", better: "low" },
    { key: "final_accuracy", label: "Final accuracy", dir: "↑", better: "high" },
    { key: "solo_coverage", label: "Solo coverage", dir: "↑", better: "high" },
    { key: "unnecessary_clarification", label: "Unnecessary clarification", dir: "↓", better: "low" },
    { key: "latency_ms_median", label: "Median latency", dir: "↓", better: "low", ms: true },
  ];
  const STOP = new Set("a an the and or but so of to in on at for by with from as is are was were be been it its this that these those you your i my me we our they their he she his her not no yes do does did have has had what which who when where how than then there here just also very".split(" "));

  const $ = (sel) => document.querySelector(sel);
  const state = { step: 0, family: null, comparator: "safetune" };
  let cases = [], preds = [], metrics = null;

  // ---------- data ----------
  async function getText(name) {
    const r = await fetch(BASE + name, { cache: "no-store" });
    if (!r.ok) throw new Error(`${BASE + name}: HTTP ${r.status}`);
    return r.text();
  }
  const parseJsonl = (t) => t.split(/\r?\n/).filter((l) => l.trim()).map((l) => JSON.parse(l));

  async function load() {
    const [c, p, m] = await Promise.all([getText("cases.jsonl"), getText("predictions.jsonl"), getText("metrics.json")]);
    cases = parseJsonl(c);
    preds = parseJsonl(p);
    metrics = JSON.parse(m);
  }

  const caseOf = (family, cond) => cases.find((c) => c.family_id === family && c.feedback_condition === cond);
  const predOf = (caseId, policy) => preds.find((r) => r.case_id === caseId && r.policy === policy);
  const comparatorLabel = (id) => (metrics.comparators.find((c) => c.id === id) || { label: id }).label;

  // ---------- helpers ----------
  function el(tag, attrs = {}, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === "class") n.className = v;
      else if (k === "html") n.innerHTML = v;
      else n.setAttribute(k, v === true ? "" : v);
    }
    for (const k of kids.flat()) if (k != null) n.append(k.nodeType ? k : document.createTextNode(String(k)));
    return n;
  }
  const esc = (s) => String(s).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
  const norm = (w) => w.toLowerCase().replace(/(\d),(\d)/g, "$1$2");
  const tokens = (s) => (norm(s).match(/[\p{L}\p{N}]+/gu) || []).filter((w) => !STOP.has(w));
  const pct = (v) => `${Math.round(v * 100)}%`;

  // Display aid only (not a metric): share of the feedback's content words that also appear in the passage.
  function overlap(feedback, context) {
    const ctx = new Set(tokens(context.replace(/\[S\d+\]/g, " ")));
    const fb = tokens(feedback);
    const hits = fb.filter((w) => ctx.has(w)).length;
    const html = esc(feedback).replace(/[\p{L}\p{N}][\p{L}\p{N},]*/gu, (w) => {
      const t = norm(w).replace(/,$/, "");
      return !STOP.has(t) && ctx.has(t) ? `<mark>${w}</mark>` : w;
    });
    return { share: fb.length ? hits / fb.length : 0, html };
  }

  function contextSpans(text) {
    const parts = text.split(/\[(S\d+)\]\s*/).slice(1);
    const out = [];
    for (let i = 0; i < parts.length; i += 2) out.push({ id: parts[i], text: parts[i + 1].trim() });
    return out.length ? out : [{ id: "", text }];
  }

  // ---------- verdicts (from saved score, never recomputed) ----------
  function verdict(pred, c) {
    const a = pred.parsed_action.action, s = pred.score || {};
    if (a === "update") return s.unwarranted_update ? ["ko", "Unwarranted update"] : ["ok", "Warranted update"];
    if (a === "retain") return s.action_acceptable ? ["ok", "Kept its answer"] : ["ko", "Missed a valid correction"];
    if (s.unnecessary_clarification) return ["ko", "Unnecessary clarification"];
    if (s.clarification_resolved === true) return ["ok", "Asked for evidence, then resolved"];
    if (s.clarification_resolved === false) return ["ko", "Asked for evidence, never resolved"];
    return ["", "Asked for evidence"];
  }

  // ---------- render ----------
  function renderMeta() {
    const dl = $("#run-meta");
    dl.replaceChildren(
      el("dt", {}, "run"), el("dd", {}, metrics.run_id),
      el("dt", {}, "split"), el("dd", {}, `${metrics.dataset.split} · ${metrics.dataset.n_cases} cases`),
      el("dt", {}, "manifest"), el("dd", {}, metrics.dataset.manifest_sha256 ? metrics.dataset.manifest_sha256.slice(0, 12) : "none"),
    );
    $("#mock-banner").hidden = !metrics.is_mock;
    $("#src-path").textContent = BASE;
  }

  function renderSelectors() {
    const families = [...new Set(cases.map((c) => c.family_id))].filter((f) => PAIR.every((cond) => caseOf(f, cond)));
    state.family = state.family && families.includes(state.family) ? state.family : families[0];
    $("#family").replaceChildren(...families.map((f) => {
      const c = caseOf(f, PAIR[0]);
      return el("option", { value: f, selected: f === state.family }, `${DOMAIN[c.domain] || c.domain}: ${c.question}`);
    }));
    const comps = metrics.comparators.filter((c) => c.id !== "base");
    if (!comps.some((c) => c.id === state.comparator)) state.comparator = comps.at(-1).id;
    $("#comparator").replaceChildren(...comps.map((c) => el("option", { value: c.id, selected: c.id === state.comparator }, c.label)));
  }

  function renderTask() {
    const c = caseOf(state.family, PAIR[0]);
    $("#question").textContent = c.question;
    $("#context").replaceChildren(...contextSpans(c.context).map((s) =>
      el("div", { class: "span", "data-span": s.id }, s.id ? el("span", { class: "span-id" }, s.id) : null, el("span", {}, s.text))));
  }

  function lane(cond, policy) {
    const c = caseOf(state.family, cond);
    const p = predOf(c.case_id, policy);
    const meta = LANE[cond];
    const box = el("article", { class: `lane ${meta.cls}` });
    const ov = overlap(c.feedback_text, c.context);
    box.append(
      el("div", { class: "lane-head" },
        el("span", { class: "lane-title" }, meta.title),
        el("span", { class: "overlap", title: "Share of the correction's content words that also appear in the passage (display aid, not a metric)" },
          "word overlap ", el("b", {}, pct(ov.share)))),
      el("div", { class: "msg prior" }, el("span", { class: "who" }, "Model, first answer"), c.original_answer),
      el("div", { class: "msg user" }, el("span", { class: "who" }, `User · ${meta.sub}`), el("span", { html: ov.html })),
    );
    if (!p) {
      box.append(el("p", { class: "error" }, `No prediction for ${policy} on ${c.case_id}.`));
      return box;
    }
    box.append(el("div", { class: "msg model" }, el("span", { class: "who" }, comparatorLabel(policy)), p.raw_output));
    if (p.clarification_turn) {
      box.append(
        el("div", { class: "msg user" }, el("span", { class: "who" }, "User replies"), p.clarification_turn.user_reply ?? "(no reply)"),
        el("div", { class: "msg model" }, el("span", { class: "who" }, comparatorLabel(policy)), p.clarification_turn.raw_output),
      );
    }
    const [cls, text] = verdict(p, c);
    const a = p.parsed_action;
    const correct = p.score ? p.score.final_correct : null;
    box.append(
      el("div", { class: "verdict" },
        el("span", { class: `chip ${a.action}` }, a.action),
        a.citation ? el("span", { class: "chip retain" }, `cites ${a.citation}`) : null,
        el("span", { class: cls }, `${cls === "ok" ? "✓" : cls === "ko" ? "✗" : ""} ${text}`)),
      el("div", { class: "final" }, "Final answer ", el("b", {}, p.final_answer ?? "none"),
        correct == null ? "" : correct ? el("span", { class: "ok" }, " ✓ correct") : el("span", { class: "ko" }, ` ✗ passage says ${c.truth_target}`)),
    );
    if (p.error) box.append(el("p", { class: "error" }, p.error));
    return box;
  }

  function renderPairs() {
    $("#pair-base").replaceChildren(...PAIR.map((cond) => lane(cond, "base")));
    $("#pair-tuned").replaceChildren(...PAIR.map((cond) => lane(cond, state.comparator)));
    $("#p1-title").textContent = state.comparator === "safetune"
      ? "EvidenceTune updates on evidence and asks when the evidence is missing"
      : `${comparatorLabel(state.comparator)} on the same pair`;
  }

  function renderScoreboard() {
    const comps = metrics.comparators;
    const vals = (m) => comps.map((c) => (m.ms ? c.metrics[m.key] : c.metrics[m.key]?.value)).filter((v) => v != null);
    const extremes = Object.fromEntries(METRICS.map((m) => {
      const v = vals(m);
      const best = m.better === "high" ? Math.max(...v) : Math.min(...v);
      const worst = m.better === "high" ? Math.min(...v) : Math.max(...v);
      return [m.key, { best, worst, distinct: best !== worst }];
    }));
    const thead = el("thead", {}, el("tr", {}, el("th", { scope: "col" }, "Comparator"),
      ...METRICS.map((m) => el("th", { scope: "col" }, m.label, el("span", { class: "dir" }, m.better === "high" ? "↑ higher is better" : "↓ lower is better")))));
    const tbody = el("tbody", {}, ...comps.map((c) => el("tr", { class: c.id === state.comparator || c.id === "base" ? "hl" : null },
      el("th", { scope: "row" }, c.label, el("small", {}, c.kind.replace("_", " "))),
      ...METRICS.map((m) => el("td", {}, cell(c.metrics[m.key], m, extremes[m.key]))))));
    $("#scoreboard").replaceChildren(thead, tbody);
    const n = comps[0].metrics.valid_uptake?.n;
    $("#score-note").textContent =
      `Bars show 95% intervals. Green marks the best value in each column, red the worst. n is small (valid corrections per comparator: ${n}), so the intervals are wide.`;
  }

  function cell(metric, m, ex) {
    if (metric == null) return el("span", { class: "cell" }, "n/a");
    const v = m.ms ? metric : metric.value;
    const isBest = ex.distinct && v === ex.best, isWorst = ex.distinct && v === ex.worst;
    const box = el("div", { class: `cell${isWorst ? " warn" : ""}` });
    const txt = m.ms ? `${Math.round(v).toLocaleString()} ms` : pct(v);
    box.append(el("span", { class: `v${isBest ? " best" : ""}` }, txt));
    if (!m.ms && metric.ci_low != null) {
      box.append(el("div", { class: "ci", role: "img", "aria-label": `95% interval ${pct(metric.ci_low)} to ${pct(metric.ci_high)}, n=${metric.n}` },
        el("span", { class: "range", style: `left:${metric.ci_low * 100}%;width:${(metric.ci_high - metric.ci_low) * 100}%` }),
        el("span", { class: "pt", style: `left:calc(${v * 100}% - 1px)` })));
    }
    return box;
  }

  function setStep(i) {
    state.step = Math.max(0, Math.min(2, i));
    document.querySelectorAll("[data-panel]").forEach((p) => p.classList.toggle("active", +p.dataset.panel === state.step));
    document.querySelectorAll("#steps button").forEach((b) => {
      if (+b.dataset.step === state.step) b.setAttribute("aria-current", "step");
      else b.removeAttribute("aria-current");
    });
    $("#prev").disabled = state.step === 0;
    $("#next").disabled = state.step === 2;
  }

  function renderAll() {
    renderTask();
    renderPairs();
    renderScoreboard();
  }

  // ---------- wire up ----------
  function bind() {
    document.querySelectorAll("#steps button").forEach((b) => b.addEventListener("click", () => setStep(+b.dataset.step)));
    $("#prev").addEventListener("click", () => setStep(state.step - 1));
    $("#next").addEventListener("click", () => setStep(state.step + 1));
    $("#show-all").addEventListener("change", (e) => document.body.classList.toggle("show-all", e.target.checked));
    $("#family").addEventListener("change", (e) => { state.family = e.target.value; renderAll(); });
    $("#comparator").addEventListener("change", (e) => { state.comparator = e.target.value; renderPairs(); renderScoreboard(); });
    document.addEventListener("keydown", (e) => {
      if (e.target.closest("select, input, textarea")) return;
      if (e.key === "ArrowRight") setStep(state.step + 1);
      if (e.key === "ArrowLeft") setStep(state.step - 1);
    });
  }

  load().then(() => {
    renderMeta();
    renderSelectors();
    renderAll();
    bind();
    if (params.get("all") === "1") { $("#show-all").checked = true; document.body.classList.add("show-all"); }
    setStep((parseInt(params.get("step"), 10) || 1) - 1);
  }).catch((err) => {
    $("#stage").replaceChildren(el("p", { class: "error" },
      `Could not load run "${RUN}": ${err.message}. Serve the demo folder over HTTP (python -m http.server) rather than opening the file directly.`));
    console.error(err);
  });
})();
