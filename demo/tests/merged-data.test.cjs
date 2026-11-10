const test = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { createHash } = require("node:crypto");
const { join } = require("node:path");

const ROOT = join(__dirname, "..");
const payloadPath = join(ROOT, "data/results/merged-alpha-075/merged.json");
const payload = JSON.parse(readFileSync(payloadPath, "utf8"));
const { createMergedRun, mergedMetrics } = require("../merged-data.js");

const CONDITIONS = ["valid", "unsupported_toward", "unsupported_away", "pressure_away", "solo"];
const ARMS = ["baseline_v7", "merge_alpha_0.75"];
const EXPECTED = {
  semantic_frozen_test: {
    baseline_v7: { task_success: [0.8875, 213, 240], all_five_task_success: [0.6041666666666666, 29, 48] },
    "merge_alpha_0.75": { task_success: [0.925, 222, 240], all_five_task_success: [0.7291666666666666, 35, 48] },
  },
  v8_targeted_frozen_test: {
    baseline_v7: { task_success: [0.9148148148148149, 247, 270], all_five_task_success: [0.7407407407407407, 40, 54] },
    "merge_alpha_0.75": { task_success: [0.937037037037037, 253, 270], all_five_task_success: [0.7962962962962963, 43, 54] },
  },
};

test("the bundled payload is the byte-verified merged evidence", () => {
  const digest = createHash("sha256").update(readFileSync(payloadPath)).digest("hex");
  assert.equal(digest, "6e98f3d5e1980e667484602dc3ae2690e46cc8ac1df14b552b67a76572202ad7");
  assert.equal(payload.recorded_only, true);
  assert.equal(payload.illustration.case_id, "sc-01-25");
});

test("every saved condition and arm maps without changing input, output, or evaluations", () => {
  const run = createMergedRun(payload);
  assert.deepEqual(run.cases.map(item => item.feedback_condition), CONDITIONS);
  assert.equal(run.cases.length, 5);
  assert.equal(run.predictions.length, 10);
  for (const [index, record] of payload.illustration.records.entries()) {
    const mappedCase = run.cases[index];
    assert.equal(mappedCase.input, record.input);
    assert.equal(mappedCase.metadata, record.metadata);
    for (const arm of ARMS) {
      const prediction = run.predictions.find(item => item.case_id === mappedCase.case_id && item.policy === arm);
      assert.ok(prediction, `${record.condition}/${arm} must be present`);
      assert.equal(prediction.raw_output, record.outputs[arm].raw_output);
      assert.deepEqual(prediction.evaluation, record.outputs[arm].evaluation);
      assert.equal(prediction.raw_output_sha256, record.outputs[arm].raw_output_sha256);
      assert.equal(prediction.backend, payload.backend);
      assert.equal(prediction.final_answer, record.outputs[arm].evaluation.parsed_answer);
    }
  }
});

test("both frozen scoreboards preserve exact values, counts, and denominators", () => {
  for (const [view, arms] of Object.entries(EXPECTED)) {
    const metrics = mergedMetrics(payload, view);
    assert.equal(metrics.is_mock, false);
    assert.equal(metrics.merged, true);
    assert.equal(metrics.dataset.n_cases, view === "semantic_frozen_test" ? 48 : 54);
    for (const [arm, measures] of Object.entries(arms)) {
      const comparator = metrics.comparators.find(item => item.id === arm);
      assert.ok(comparator);
      for (const [metric, [value, count, n]] of Object.entries(measures)) {
        assert.equal(comparator.metrics[metric].value, value, `${view}/${arm}/${metric}`);
        assert.equal(comparator.metrics[metric].count, count);
        assert.equal(comparator.metrics[metric].n, n);
      }
    }
  }
});

test("invalid replay scope or an incomplete matched case is rejected", () => {
  const live = structuredClone(payload);
  live.recorded_only = false;
  assert.throws(() => createMergedRun(live), /recorded-only/);
  const incomplete = structuredClone(payload);
  incomplete.illustration.records.pop();
  assert.throws(() => createMergedRun(incomplete), /five/);
  const mixed = structuredClone(payload);
  mixed.scoreboards.semantic_frozen_test.arms.baseline_v7.backend = "Kaggle fp16";
  assert.throws(() => createMergedRun(mixed), /backend/);
});
