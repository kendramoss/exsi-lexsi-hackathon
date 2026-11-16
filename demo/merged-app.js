// Recorded release presentation. No inference, score recomputation, or historical fallback.
(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  if ((params.get("run") || "merged-alpha-075") !== "merged-alpha-075") return;
  const SOURCE = "data/results/merged-alpha-075/merged.json";
  const PAYLOAD_SHA = "6e98f3d5e1980e667484602dc3ae2690e46cc8ac1df14b552b67a76572202ad7";
  const ADAPTER_SHA = "a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335";
  const MODEL_URL = "https://huggingface.co/Mizore66/evidencetune-merged-alpha-0.75";
  const DATA_URL = "https://huggingface.co/datasets/Mizore66/evidencetune-merged-data-alpha-0.75";
  const ARMS = ["baseline_v7", "merge_alpha_0.75"];
  const NAMES = { baseline_v7: "v7 parent", "merge_alpha_0.75": "Merged α=0.75" };
  const CONDITIONS = {
    valid: "Valid citation", unsupported_toward: "Insufficient citation · toward", unsupported_away: "Insufficient citation · away",
    pressure_away: "Bare pressure", solo: "No pushback (solo)",
  };
  const VIEWS = { semantic_frozen_test: "Semantic frozen test", v8_targeted_frozen_test: "Targeted frozen test" };
  const $ = (s) => document.querySelector(s);
  const e = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const el = (tag, attrs = {}, ...kids) => {
    const node = document.createElement(tag);
    Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
    kids.flat().forEach((kid) => node.append(kid?.nodeType ? kid : document.createTextNode(String(kid))));
    return node;
  };
  const Z = () => parseFloat(getComputedStyle(document.documentElement).zoom) || 1;
  const navPx = () => $(".top").getBoundingClientRect().height;
  const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches || params.has("instant");
  const percent = (value) => `${(value * 100).toFixed(2)}%`;
  let payload, run, condition, storyStep = 1, stageCount = 5, storyLayout = () => {}, scrollFrame = 0;
  document.body.dataset.run = "merged-alpha-075";
  document.body.dataset.evidenceSource = SOURCE;
  if (params.has("instant")) document.documentElement.dataset.instant = "";

  const sha = async (bytes) => [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))].map((v) => v.toString(16).padStart(2, "0")).join("");
  async function load() {
    const response = await fetch(SOURCE, { cache: "no-store" });
    if (!response.ok) throw new Error(`${SOURCE}: HTTP ${response.status}. The recorded release payload is required.`);
    const bytes = await response.arrayBuffer();
    if (await sha(bytes) !== PAYLOAD_SHA) throw new Error("Recorded release payload SHA-256 does not match its pinned identity.");
    payload = JSON.parse(new TextDecoder().decode(bytes));
    if (payload.model.adapter_sha256 !== ADAPTER_SHA) throw new Error("Released adapter identity mismatch.");
    run = window.EvidenceTuneMerged.createMergedRun(payload);
    const encoder = new TextEncoder();
    for (const record of payload.illustration.records) {
      if (await sha(encoder.encode(record.input)) !== record.input_sha256) throw new Error(`Saved input hash mismatch: ${record.condition}`);
      for (const arm of ARMS) {
        const output = record.outputs[arm];
        if (await sha(encoder.encode(output.raw_output)) !== output.raw_output_sha256) throw new Error(`Saved output hash mismatch: ${record.condition}/${arm}`);
      }
    }
    condition = Object.hasOwn(CONDITIONS, params.get("condition")) ? params.get("condition") : "valid";
  }

  const score = (view, arm, key) => window.EvidenceTuneMerged.mergedMetrics(payload, view).comparators.find((c) => c.id === arm).metrics[key];
  const record = () => payload.illustration.records.find((r) => r.condition === condition);
  function parts(r) {
    const prior = r.input.indexOf("\n\nYour earlier answer: "), user = r.input.indexOf("\n\nUser: ");
    return {
      context: prior < 0 ? r.input : r.input.slice(0, prior),
      feedback: user < 0 ? null : r.input.slice(user + "\n\nUser: ".length),
      prior: prior < 0 ? null : r.metadata.prior,
    };
  }
  const outputMarkup = (r, arm, conversation = false) => {
    const output = r.outputs[arm], evaluation = output.evaluation;
    return `<article class="answer-result ${conversation ? "branch show" : ""}" data-policy="${arm}">
      <h3>${e(NAMES[arm])}</h3><p class="result-action">Saved action: ${e(evaluation.parsed_action || "Solo answer")}</p>
      <p class="result-answer"><span class="answer-kind">Working answer</span><strong>${e(evaluation.parsed_answer)}</strong></p>
      <pre class="result-response ${conversation ? "recorded-output" : ""}" data-policy="${arm}">${e(output.raw_output)}</pre>
      <details class="output-hash"><summary>Output SHA-256</summary><code>${e(output.raw_output_sha256)}</code></details></article>`;
  };
  function table(view) {
    return `<div class="table-win release-table" data-view="${view}"><h4>${VIEWS[view]}</h4>
      <p>${payload.scoreboards[view].cases} cases · ${payload.scoreboards[view].rows_per_arm} rows per arm · frozen confirmation</p>
      <div class="table-scroll"><table class="scoreboard"><caption>Saved task-contract scores; both arms use the same named local Apple MPS bf16 backend.</caption>
      <thead><tr><th scope="col">Metric</th>${ARMS.map((arm) => `<th scope="col">${e(NAMES[arm])}</th>`).join("")}</tr></thead><tbody>
      ${[ ["task_success", "Task success", "rows"], ["all_five_task_success", "All-five-condition success", "cases"] ].map(([key, label, unit]) => `<tr><th scope="row">${label}</th>${ARMS.map((arm) => {
        const m = score(view, arm, key);
        return `<td data-view="${view}" data-policy="${arm}" data-arm="${arm}" data-metric="${key}" data-count="${m.count}" data-n="${m.n}">${percent(m.value)}<small>${m.count}/${m.n} ${unit}</small></td>`;
      }).join("")}</tr>`).join("")}</tbody></table></div></div>`;
  }
  function chart(view) {
    return `<figure class="release-score" data-view="${view}"><figcaption>${VIEWS[view]}<small>${payload.scoreboards[view].cases} cases · task success over ${payload.scoreboards[view].rows_per_arm} rows per arm</small></figcaption>
      ${ARMS.map((arm) => { const m = score(view, arm, "task_success"); return `<div class="release-score-row" data-policy="${arm}" data-view="${view}" data-arm="${arm}" data-metric="task_success" data-count="${m.count}" data-n="${m.n}">
      <span>${e(NAMES[arm])}</span><span class="release-score-track" aria-hidden="true"><i class="${arm === ARMS[1] ? "merged" : "parent"}" style="width:${m.value * 100}%"></i></span><strong>${m.count}/${m.n}<small>${percent(m.value)}</small></strong></div>`; }).join("")}</figure>`;
  }
  function render() {
    $("#main").innerHTML = `
      <section class="ch ch-light ch-stage focusable" id="top" aria-labelledby="hero-title"><div class="blocks" aria-hidden="true"></div><div class="stage">
        <p class="release-identity">EvidenceTune · Selected release α=0.75</p>
        <h1 id="hero-title">Does the model change its answer <em>for the right reason?</em></h1>
        <p>75% v7 + 25% v8. Recorded evidence from the released adapter.</p>
        <p class="release-summary">Frozen task success: <b>222/240 · 92.50%</b> semantic · <b>253/270 · 93.70%</b> targeted.</p>
        <p class="release-scope">Synthetic proxy evaluation. Recorded only; no live inference.</p>
        <a class="cue" href="#glance">Inspect the saved responses <span aria-hidden="true">↓</span></a></div></section>
      <section class="ch ch-light ch-rail focusable" id="glance" aria-labelledby="glance-title"><div class="rail">
        <h2 id="glance-title">Same pushback.<br>Two saved responses.</h2>
        <label class="condition-label" for="merged-condition">Recorded condition</label><select id="merged-condition">${Object.entries(CONDITIONS).map(([id, name]) => `<option value="${id}">${e(name)}</option>`).join("")}</select>
        <dl class="setup" id="setup"></dl><p class="rail-foot">sc-01-25 · first case in saved semantic frozen-test order. Both arms pass all five illustrated rows.</p>
        </div><div class="panel panel-blue"><div class="answer-comparison" id="hero-vis" role="group" aria-label="Exact recorded v7 and merged responses"></div><p id="g-proof" class="release-proof"></p></div></section>
      <section class="ch ch-light scroll-story focusable" id="s1" aria-labelledby="s1-title"><div class="story-stage ch-rail"><div class="rail">
        <h2 id="s1-title">One recorded example</h2><p class="rail-lead" id="walk-lead">Read the saved task context and correction, then compare the two recorded responses.</p>
        <ol class="timeline" id="convo-tl" aria-label="Stages of the recorded example"></ol><p class="rail-foot release-record-note">The earlier answer is supplied task context, not a generated assistant turn. No follow-up clarification dialogue is bundled.</p>
        <span class="rail-foot convo-hint" id="convo-step" aria-live="polite"></span></div><div class="panel panel-blue"><div class="ch-chat">
        <div class="convo flow release-convo" id="convo"></div><div class="convo-foot"><div class="convo-ctl" role="group" aria-label="Step through the saved example"><button class="ckey" id="convo-prev" type="button" aria-label="Previous step">‹</button><span class="cdots" id="convo-dots" aria-hidden="true"></span><button class="ckey" id="convo-next" type="button" aria-label="Next step">›</button></div><button class="replay" id="replay" type="button">Back to the beginning</button></div>
        </div></div></div></section>
      <section class="ch ch-light focusable" id="listen" aria-labelledby="listen-title"><div class="ls-inner"><h2 id="listen-title">Frozen task success</h2>
        <p class="ls-why">v7 parent → selected merged release. Separate suites, separate denominators.</p>
        <div id="ls-chart">${Object.keys(VIEWS).map(chart).join("")}</div><p class="release-caption">Strict contract-v2 task success includes output format, action, and working-answer checks. It is not general model accuracy.</p></div></section>
      <section class="ch ch-light focusable" id="s3" aria-labelledby="s3-title"><div class="release-test"><h2 id="s3-title">What does the test measure?</h2>
        <p>One policy case, five matched conditions. The model must respond to the evidence available under the saved task contract.</p>
        <ol class="release-conditions">${Object.values(CONDITIONS).map((name) => `<li>${e(name)}</li>`).join("")}</ol>
        <div class="release-method"><p><b>Frozen confirmation</b>Semantic: 48 cases / 240 rows. Targeted: 54 cases / 270 rows per arm. Five rows from a case are correlated.</p><p><b>Dev-only selection</b>The merge was selected on dev data; frozen results are confirmation. Earlier source-model frozen runs existed but were not used to select this merge.</p><p><b>Scope and limits</b>Custom EvidenceTune contract-v2 scorers. Synthetic construction-proxy labels; no independent human sufficiency annotation or broad natural-domain validation.</p></div>
        <p class="release-caption">Dev selection and conditional resolution are separate analyses, not these frozen task-success rates. <a href="${MODEL_URL}#evaluation" target="_blank" rel="noopener">Read the model card</a>.</p></div></section>
      <section class="ch ch-blue focusable" id="s4" data-surface="blue" aria-labelledby="s4-title"><div class="s4-shapes" aria-hidden="true"><i class="q1"></i><i class="c1"></i><i class="sq"></i><i class="q2"></i></div>
        <header class="end-head"><h2 id="s4-title">See the work</h2><p class="which">Shown throughout: v7 parent versus EvidenceTune merged α=0.75. Both arms use the same named local Apple MPS bf16 Transformers backend.</p></header>
        <div class="tiles">${[[MODEL_URL, "Model", "Released merged adapter", "huggingface.co/Mizore66/evidencetune-merged-alpha-0.75"], [SOURCE, "Evidence", "Exact recorded payload", SOURCE], ["https://github.com/kendramoss/exsi-lexsi-hackathon", "Code", "Training and scoring", "github.com/kendramoss/exsi-lexsi-hackathon"]].map(([href, label, title, url], i) => `<a class="tile ${["model", "data", "code"][i]}" href="${href}" target="_blank" rel="noopener"><span class="front"><i aria-hidden="true"></i><small>${label}</small><b>${title} <span aria-hidden="true">↗</span></b><span class="url">${url}</span></span></a>`).join("")}</div>
        <div class="end-actions"><p class="credit">Recorded only · <a href="${DATA_URL}" target="_blank" rel="noopener">Merged data and evidence</a></p><span>Frozen scoreboards, exact input, and provenance</span><button class="all-btn" id="open-all" type="button">Inspect the evidence</button></div>
        <p class="release-route-links"><a href="?run=final-fresh">Historical v5/v6 view</a> · <a href="?run=mock-smoke">Invented layout-testing view</a></p></section>
      <dialog class="all" id="all-dialog" aria-labelledby="all-title"><div class="all-head"><h3 id="all-title">Recorded release evidence</h3><button class="replay" id="close-all" type="button">Close</button></div>
        <p class="intro">${e(payload.claim_scope)} These are saved task-contract results, not general accuracy. Both comparison arms use ${e(payload.backend)}.</p>
        <div id="scoreboards">${Object.keys(VIEWS).map(table).join("")}</div>
        <p>All-five success counts a case only when all five matched rows pass. It differs from row-level task success. Dev selection and conditional resolution are not included in these frozen tables.</p>
        <details id="input-details"><summary>Exact saved input for the selected condition</summary><pre id="recorded-input"></pre></details>
        <h4>Identity and provenance</h4><dl class="release-provenance"><dt>Adapter</dt><dd>75% v7 + 25% v8 · <a href="${MODEL_URL}" target="_blank" rel="noopener">Release model card</a></dd>
        <dt>Adapter SHA-256</dt><dd><code id="adapter-sha256">${e(payload.model.adapter_sha256)}</code></dd><dt>Payload SHA-256</dt><dd><code>${PAYLOAD_SHA}</code></dd><dt>Selection SHA-256</dt><dd><code>${e(payload.selection.selection_sha256)}</code></dd><dt>Frozen summary SHA-256</dt><dd><code>${e(payload.selection.frozen_summary_sha256)}</code></dd>
        <dt>Selection</dt><dd>dev_only · frozen_test_used_for_selection: false</dd><dt>Illustration</dt><dd>${e(payload.illustration.selection_rule)}</dd><dt>Labels</dt><dd>${e(payload.illustration.label_status)}</dd></dl>
        <details><summary>Referenced source artifacts and hashes</summary><ul class="release-artifacts">${payload.source_artifacts.map((a) => `<li><code>${e(a.path)}</code><br>${e(a.role)}${a.rows ? ` · ${a.rows} rows` : ""}<br><code>${e(a.sha256)}</code></li>`).join("")}</ul></details>
        <p class="fine">Source raw files are retained outside this static demo and are not redistributed here. The bundled replay contains five illustrated rows and aggregate scoreboards, not all frozen predictions.</p>
        <p class="fine">Exact source: <a href="${SOURCE}"><code id="src-path">${SOURCE}</code></a>. <a href="${MODEL_URL}" target="_blank" rel="noopener">Public release</a> · <a href="https://mizore66-evidencetune-merged-demo.static.hf.space/index.html" target="_blank" rel="noopener">Public recorded demo</a>.</p></dialog>`;
    $("#merged-condition").value = condition;
    $("#merged-condition").addEventListener("change", (event) => {
      condition = event.target.value;
      renderRecord();
      storyLayout();
    });
    $("#open-all").addEventListener("click", () => $("#all-dialog").showModal());
    $("#close-all").addEventListener("click", () => $("#all-dialog").close());
    $("#all-dialog").addEventListener("click", (event) => { if (event.target === $("#all-dialog")) event.target.close(); });
    renderRecord();
  }

  function renderRecord() {
    const r = record(), p = parts(r), evaluation = r.outputs[ARMS[1]].evaluation;
    $("#hero-vis").dataset.case = payload.illustration.case_id;
    $("#hero-vis").dataset.condition = condition;
    $("#hero-vis").innerHTML = `<div class="shared-correction"><p class="correction-label">${e(CONDITIONS[condition])} · exact saved ${p.feedback ? "user correction" : "solo input"}</p><blockquote>${e(p.feedback || p.context)}</blockquote></div><div class="result-responses">${ARMS.map((arm) => outputMarkup(r, arm)).join("")}</div>`;
    $("#setup").innerHTML = `<dt>Policy statement</dt><dd>${e(p.context.split("\n")[0].replace(/^Policy statement: /, ""))}</dd>${p.prior ? `<dt>Supplied prior</dt><dd>${e(p.prior)}</dd>` : ""}<dt>Expected working answer</dt><dd>${e(evaluation.expected_answer)}</dd><dt>Expected action</dt><dd>${e(r.metadata.acceptable_actions.join(" or ") || "Not applicable to solo")}</dd>`;
    $("#g-proof").textContent = "Both recorded models pass this row’s saved task-contract checks. This illustration does not demonstrate a baseline failure or measure general accuracy.";
    $("#recorded-input").textContent = r.input;
    $("#recorded-input").dataset.sha256 = r.input_sha256;
    const stages = p.feedback ? ["Policy and excerpts", "Supplied prior answer", "Saved user correction", "Two saved outputs", "Saved task checks"] : ["Policy and excerpts", "Two saved outputs", "Saved task checks"];
    stageCount = stages.length;
    $("#convo-tl").innerHTML = stages.map((text, i) => `<li data-step="${i + 1}">${text}</li>`).join("");
    $("#convo").innerHTML = `<div class="release-record-coordinate">${e(payload.illustration.case_id)} · ${e(CONDITIONS[condition])} · recorded only</div>
      <div class="release-story-part release-context"><p class="release-message-label">Exact saved task context</p><pre>${e(p.context)}</pre></div>
      ${p.prior ? `<div class="release-story-part release-prior"><p class="release-message-label">Supplied earlier answer · task context</p><div class="bubble a">${e(p.prior)}</div></div>` : ""}
      ${p.feedback ? `<div class="release-story-part release-feedback chat-row user"><p class="release-message-label">Exact saved user correction</p><div class="bubble q">${e(p.feedback)}</div></div>` : ""}
      <div class="release-story-part release-outputs"><div class="result-responses">${ARMS.map((arm) => outputMarkup(r, arm, true)).join("")}</div></div>
      <div class="release-story-part release-evaluations"><p>Saved task-contract checks</p>${ARMS.map((arm) => {
        const v = r.outputs[arm].evaluation;
        return `<p data-policy="${arm}">${e(NAMES[arm])}: ${v.task_success ? "passes" : "does not pass"} · format ${v.format_ok ? "passes" : "fails"}${v.action_ok === null ? "" : ` · action ${v.action_ok ? "passes" : "fails"}`} · working answer ${v.answer_ok ? "passes" : "fails"}</p>`;
      }).join("")}<p class="release-small">A working answer under this contract is not a claim of terminal factual correctness. No follow-up resolution is recorded here.</p></div>`;
    showStep(Math.min(storyStep, stageCount));
  }

  function showStep(n, complete = false) {
    storyStep = n;
    const solo = condition === "solo", outputAt = solo ? 2 : 4;
    const visible = { ".release-context": complete || n <= (solo ? 1 : 2), ".release-prior": complete || (n >= 2 && n <= 3), ".release-feedback": complete || n >= 3, ".release-outputs": complete || n >= outputAt, ".release-evaluations": complete || n >= stageCount };
    for (const [selector, shown] of Object.entries(visible)) { const node = $("#convo").querySelector(selector); if (node) node.hidden = !shown; }
    $("#convo").dataset.step = String(n);
    $("#s1").dataset.storyStep = String(n);
    $("#convo-step").textContent = complete ? "Complete recorded input and outputs" : `Step ${n} of ${stageCount}`;
    document.querySelectorAll("#convo-tl li").forEach((li, i) => { li.classList.toggle("now", i + 1 === n); li.classList.toggle("done", i + 1 < n); if (i + 1 === n) li.setAttribute("aria-current", "step"); else li.removeAttribute("aria-current"); });
    $("#convo-prev").disabled = complete || n <= 1;
    $("#convo-next").disabled = complete || n >= stageCount;
    $("#convo-dots").replaceChildren(...Array.from({ length: stageCount }, (_, i) => el("i", { class: i + 1 === n ? "on" : i + 1 < n ? "done" : "" })));
  }

  const cancelScroll = () => { cancelAnimationFrame(scrollFrame); scrollFrame = 0; };
  function scrollToPosition(y, instant = false) {
    cancelScroll();
    const target = Math.max(0, Math.min(y, document.documentElement.scrollHeight - innerHeight)), from = scrollY;
    if (instant || reduced()) { scrollTo({ top: target, behavior: "instant" }); return; }
    const start = performance.now(), duration = Math.min(650, Math.max(260, Math.abs(target - from) * .18));
    const tick = (now) => { const t = Math.min(1, (now - start) / duration), eased = t < .5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2;
      scrollTo({ top: from + (target - from) * eased, behavior: "instant" });
      if (t < 1) scrollFrame = requestAnimationFrame(tick); else scrollFrame = 0;
    };
    scrollFrame = requestAnimationFrame(tick);
  }
  function presentation() {
    const section = $("#s1"), stage = $("#s1 .story-stage");
    const media = matchMedia("(min-width: 901px) and (min-height: 641px) and (prefers-reduced-motion: no-preference)");
    const enabled = () => media.matches && !params.has("instant");
    const scene = () => innerHeight - navPx(), start = () => section.getBoundingClientRect().top + scrollY - navPx(), beat = () => scene() * .6;
    let scheduled = 0;
    const sync = () => { scheduled = 0; if (!enabled()) return; const n = Math.max(1, Math.min(stageCount, Math.floor(Math.max(0, scrollY - start()) / beat()) + 1)); if (n !== storyStep) showStep(n); };
    storyLayout = () => {
      section.classList.toggle("is-scroll-story", enabled()); section.classList.toggle("story-static", !enabled());
      section.style.setProperty("--story-span", `${scene() * (1.65 + .6 * (stageCount - 1)) / Z()}px`);
      stage.style.setProperty("--scene-height", `${scene() / Z()}px`);
      if (enabled()) { showStep(storyStep); sync(); } else showStep(stageCount, true);
    };
    const step = (dir) => { if (!enabled()) return false; const n = Math.min(stageCount, Math.max(1, storyStep + dir)); if (n === storyStep) return false; scrollToPosition(start() + (n - 1) * beat() + 2); return true; };
    $("#convo-prev").addEventListener("click", () => step(-1)); $("#convo-next").addEventListener("click", () => step(1));
    $("#replay").addEventListener("click", () => scrollToPosition(start() + 2));
    addEventListener("scroll", () => { if (!scheduled) scheduled = requestAnimationFrame(sync); }, { passive: true });
    addEventListener("resize", storyLayout); media.addEventListener("change", storyLayout); document.fonts.ready.then(storyLayout); new ResizeObserver(storyLayout).observe($(".top"));
    storyLayout();
    const sections = [...document.querySelectorAll("main > .focusable")];
    const spy = () => {
      const middle = (innerHeight + navPx()) / 2;
      const best = sections.find((s) => { const r = s.getBoundingClientRect(); return r.top <= middle && r.bottom >= middle; }) || sections.at(-1);
      sections.forEach((s) => s.classList.toggle("is-focus", s === best));
      document.querySelectorAll("#steps a, .dots a").forEach((a) => { if ((a.dataset.sec || a.dataset.dot) === best.id) a.setAttribute("aria-current", "true"); else a.removeAttribute("aria-current"); });
      document.documentElement.dataset.surface = best.dataset.surface || "";
    };
    addEventListener("scroll", spy, { passive: true }); addEventListener("resize", spy); spy();
    addEventListener("wheel", cancelScroll, { passive: true }); addEventListener("touchstart", cancelScroll, { passive: true }); addEventListener("pointerdown", cancelScroll, { passive: true });
    document.addEventListener("click", (event) => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return;
      const a = event.target.closest('a[href^="#"]'); if (!a) return;
      const target = document.getElementById(a.getAttribute("href").slice(1)); if (!target) return;
      event.preventDefault(); scrollToPosition(target.getBoundingClientRect().top + scrollY - navPx()); history.replaceState(null, "", a.getAttribute("href"));
    });
    addEventListener("keydown", (event) => {
      if (["ArrowDown", "ArrowUp", "PageDown", "PageUp", "Home", "End", " "].includes(event.key)) cancelScroll();
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey || $("dialog[open]") || event.target.closest('button, a[href], input, select, textarea, summary, [contenteditable]')) return;
      const dir = { ArrowLeft: -1, ArrowRight: 1 }[event.key];
      if (dir && section.classList.contains("is-focus") && step(dir)) event.preventDefault();
    });
    const jump = document.getElementById(location.hash.slice(1) || ({ "3": "s3" }[params.get("step")] || ""));
    if (jump) document.fonts.ready.then(() => scrollToPosition(jump.getBoundingClientRect().top + scrollY - navPx(), true));
  }

  load().then(() => { render(); presentation(); blocks(); panelBlocks(); document.body.dataset.ready = "true"; }).catch((error) => {
    $("#main").replaceChildren(el("p", { class: "error", role: "alert" }, `Could not load recorded merged release evidence: ${error.message} No historical run has been substituted.`));
    console.error(error);
  });

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


})();
