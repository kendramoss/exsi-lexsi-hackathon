// Verify pinned merged evidence and frontend wiring (Node built-ins only).
// Actual Playwright interaction coverage: check-release-page.test.cjs.
// Set REQUIRE_MERGED_BROWSER=1 to require that suite in this command too.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const root = resolve(process.argv[2] || new URL("..", import.meta.url).pathname);
const require = createRequire(import.meta.url);
const read = rel => readFileSync(join(root, rel));
const sha256 = data => createHash("sha256").update(data).digest("hex");

const PAYLOAD_PATH = "data/results/merged-alpha-075/merged.json";
const PINNED = {
  payload: "6e98f3d5e1980e667484602dc3ae2690e46cc8ac1df14b552b67a76572202ad7",
  adapter: "a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335",
  selection: "e5e177ade09c53285eeb78c7a3a7cd45f47498a245fdf1c8bc416238fbd29c4b",
  frozenSummary: "3598cf8cdfa3e0783944e0bbbcd81788ef5f15131ab8e1ee811fc63cc2184d7d",
};
const CONDITIONS = ["valid", "unsupported_toward", "unsupported_away", "pressure_away", "solo"];
const ARMS = ["baseline_v7", "merge_alpha_0.75"];
const EXPECTED = {
  semantic_frozen_test: { cases: 48, rows: 240, baseline_v7: [213, 29], "merge_alpha_0.75": [222, 35] },
  v8_targeted_frozen_test: { cases: 54, rows: 270, baseline_v7: [247, 40], "merge_alpha_0.75": [253, 43] },
};
const DISCLOSURES = ["synthetic", "not human-validated", "broad natural-domain"];

const failures = [];
let passed = 0;
function check(name, fn) {
  try { fn(); passed += 1; console.log(`PASS ${name}`); }
  catch (error) { failures.push(`${name}: ${error.message}`); console.error(`FAIL ${name}: ${error.message}`); }
}
const equal = (actual, expected, message) => {
  if (actual !== expected) throw new Error(`${message || "mismatch"}: got ${JSON.stringify(actual)}, expected ${JSON.stringify(expected)}`);
};
const ok = (value, message) => { if (!value) throw new Error(message); };

let payload;
check("payload file is the pinned, byte-verified merged evidence", () => {
  const bytes = read(PAYLOAD_PATH);
  payload = JSON.parse(bytes.toString("utf8"));
  equal(sha256(bytes), PINNED.payload, "payload sha256");
});
if (!payload) { console.error("Cannot continue without a parseable payload."); process.exit(1); }

check("recorded-only scope and claim limits are stated", () => {
  equal(payload.recorded_only, true, "recorded_only");
  equal(payload.illustration && payload.illustration.case_id, "sc-01-25", "illustrated case");
  const scope = String(payload.claim_scope || "").toLowerCase();
  for (const phrase of DISCLOSURES) ok(scope.includes(phrase), `claim_scope must say "${phrase}"`);
  ok(/local apple mps/i.test(payload.backend || ""), "backend must name the local MPS run");
});

check("provenance hashes match pinned adapter, selection, and frozen summary", () => {
  equal(payload.model.adapter_sha256, PINNED.adapter, "adapter sha256");
  equal(payload.selection.selection_sha256, PINNED.selection, "selection sha256");
  equal(payload.selection.frozen_summary_sha256, PINNED.frozenSummary, "frozen summary sha256");
  equal(payload.selection.frozen_test_used_for_selection, false, "frozen test must not drive selection");
  ok(Array.isArray(payload.source_artifacts) && payload.source_artifacts.length > 0, "source_artifacts missing");
  for (const artifact of payload.source_artifacts) ok(/^[0-9a-f]{64}$/.test(artifact.sha256 || ""), `bad artifact hash for ${artifact.path}`);
});

check("five conditions in saved order, both arms, input/output hashes and labels intact", () => {
  const records = payload.illustration.records;
  equal(records.length, 5, "record count");
  records.forEach((record, index) => {
    equal(record.condition, CONDITIONS[index], "condition order");
    equal(sha256(record.input), record.input_sha256, `${record.condition} input hash`);
    for (const arm of ARMS) {
      const output = record.outputs[arm];
      ok(output, `${record.condition}/${arm} missing`);
      equal(sha256(output.raw_output), output.raw_output_sha256, `${record.condition}/${arm} raw_output hash`);
      equal(output.backend, payload.backend, `${record.condition}/${arm} backend`);
      equal(output.evaluation.expected_answer, record.metadata.answer, `${record.condition}/${arm} expected_answer label`);
      equal(typeof output.evaluation.task_success, "boolean", `${record.condition}/${arm} task_success type`);
    }
  });
});

check("both frozen scoreboards keep exact counts, denominators, and ratios", () => {
  for (const [view, spec] of Object.entries(EXPECTED)) {
    const board = payload.scoreboards[view];
    equal(board.cases, spec.cases, `${view} cases`);
    equal(board.rows_per_arm, spec.rows, `${view} rows_per_arm`);
    for (const arm of ARMS) {
      const row = board.arms[arm];
      equal(row.backend, payload.backend, `${view}/${arm} backend`);
      equal(row.rows, spec.rows, `${view}/${arm} rows`);
      equal(row.cases, spec.cases, `${view}/${arm} cases`);
      equal(row.task_success, spec[arm][0] / spec.rows, `${view}/${arm} task_success`);
      equal(row.all_five_task_success, spec[arm][1] / spec.cases, `${view}/${arm} all_five_task_success`);
    }
  }
});

check("merged-data.js maps every condition/arm without altering input, output, or evaluation", () => {
  const api = require(join(root, "merged-data.js"));
  const run = api.createMergedRun(payload);
  equal(run.cases.length, 5, "mapped cases");
  equal(run.predictions.length, 10, "mapped predictions");
  payload.illustration.records.forEach((record, index) => {
    equal(run.cases[index].input, record.input, "mapped input");
    equal(run.cases[index].feedback_condition, record.condition, "mapped condition");
    for (const arm of ARMS) {
      const prediction = run.predictions.find(item => item.case_id === run.cases[index].case_id && item.policy === arm);
      ok(prediction, `${record.condition}/${arm} prediction missing`);
      equal(prediction.raw_output, record.outputs[arm].raw_output, "mapped raw_output");
      equal(prediction.raw_output_sha256, record.outputs[arm].raw_output_sha256, "mapped raw_output hash");
      equal(JSON.stringify(prediction.evaluation), JSON.stringify(record.outputs[arm].evaluation), "mapped evaluation");
      equal(prediction.final_answer, record.outputs[arm].evaluation.parsed_answer, "mapped final answer");
    }
  });
  for (const [view, spec] of Object.entries(EXPECTED)) {
    const metrics = api.mergedMetrics(payload, view);
    for (const arm of ARMS) {
      const comparator = metrics.comparators.find(item => item.id === arm);
      equal(comparator.metrics.task_success.count, spec[arm][0], `${view}/${arm} task_success count`);
      equal(comparator.metrics.all_five_task_success.count, spec[arm][1], `${view}/${arm} all-five count`);
    }
  }
});

check("default frontend wires the merged payload and its adapter", () => {
  const index = read("index.html").toString("utf8");
  const renderer = read("merged-app.js").toString("utf8");
  ok(/merged-data\.js/.test(index), "index.html must load merged-data.js");
  ok(/merged-app\.js/.test(index), "index.html must load merged-app.js");
  ok(/merged-alpha-075/.test(renderer) && /merged\.json/.test(renderer), "merged renderer must read the recorded release payload");
  ok(/createMergedRun/.test(renderer), "merged renderer must use the existing verified adapter");
});

if (failures.length) {
  console.error(`\nFAILED ${failures.length} check(s), ${passed} passed:\n- ${failures.join("\n- ")}`);
  process.exit(1);
}
console.log(`\nPASS: ${passed} merged evidence and frontend wiring checks`);
if (process.env.REQUIRE_MERGED_BROWSER === "1") {
  const browserEnv = { ...process.env, EVTUNE_DEMO_ROOT: root };
  // A verifier invoked by node:test must start a new test runner, not inherit
  // its parent's child-context marker and silently skip all browser tests.
  delete browserEnv.NODE_TEST_CONTEXT;
  const result = spawnSync(process.execPath, ["--test", join(dirname(fileURLToPath(import.meta.url)), "check-release-page.test.cjs")], {
    stdio: "inherit", env: browserEnv,
  });
  if (result.error) { console.error(result.error.message); process.exit(1); }
  process.exit(result.status ?? 1);
}
console.log("Browser interactions are a separate required check: node --test demo/tests/check-release-page.test.cjs (actual Playwright). This data-only command does not claim browser coverage.");
