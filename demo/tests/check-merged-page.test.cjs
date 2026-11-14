// Regression tests for check-merged-page.mjs: it must pass on the real tree,
// say plainly that the browser check is skipped, and fail on tampered data.
// Mutations run on a scratch copy under TMPDIR; the repository is never modified.
const test = require("node:test");
const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const { cpSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } = require("node:fs");
const { tmpdir } = require("node:os");
const { join } = require("node:path");

const DEMO = join(__dirname, "..");
const SCRIPT = join(__dirname, "check-merged-page.mjs");
const PAYLOAD = "data/results/merged-alpha-075/merged.json";

function run(root, env = {}) {
  const result = spawnSync(process.execPath, [SCRIPT, root], { encoding: "utf8", env: { ...process.env, REQUIRE_MERGED_BROWSER: "", ...env } });
  return { code: result.status, out: result.stdout, err: result.stderr };
}

function scratch(mutate) {
  const dir = mkdtempSync(join(tmpdir(), "merged-check-"));
  mkdirSync(join(dir, "data/results/merged-alpha-075"), { recursive: true });
  for (const file of ["index.html", "app.js", "merged-data.js", PAYLOAD]) cpSync(join(DEMO, file), join(dir, file));
  if (mutate) mutate(dir);
  return dir;
}

function withScratch(mutate, body) {
  const dir = scratch(mutate);
  try { return body(run(dir)); } finally { rmSync(dir, { recursive: true, force: true }); }
}

function editPayload(edit) {
  return dir => {
    const path = join(dir, PAYLOAD);
    const data = JSON.parse(readFileSync(path, "utf8"));
    edit(data);
    writeFileSync(path, JSON.stringify(data));
  };
}

test("real tree: data checks pass, exit 0, and the browser check is reported as skipped", () => {
  const { code, out, err } = run(DEMO);
  assert.equal(code, 0, err);
  assert.match(out, /PASS: 7 merged-payload data checks/);
  assert.match(out, /SKIP \(not passed\): browser rendering of the merged payload/);
  assert.doesNotMatch(out, /^PASS.*browser/im);
});

test("REQUIRE_MERGED_BROWSER=1 refuses to accept the skip (exit 2)", () => {
  const { code, err } = run(DEMO, { REQUIRE_MERGED_BROWSER: "1" });
  assert.equal(code, 2);
  assert.match(err, /skipped, so this run is not accepted/);
});

test("negative control: edited raw output is caught by the payload and output hash checks", () => {
  withScratch(editPayload(d => { d.illustration.records[0].outputs["merge_alpha_0.75"].raw_output += " tampered"; }), ({ code, err }) => {
    assert.equal(code, 1);
    assert.match(err, /FAIL payload file is the pinned/);
    assert.match(err, /raw_output hash/);
  });
});

test("negative control: changed score is caught", () => {
  withScratch(editPayload(d => { d.scoreboards.semantic_frozen_test.arms["merge_alpha_0.75"].task_success = 0.95; }), ({ code, err }) => {
    assert.equal(code, 1);
    assert.match(err, /FAIL both frozen scoreboards/);
  });
});

test("negative control: changed label is caught", () => {
  withScratch(editPayload(d => { d.illustration.records[0].outputs.baseline_v7.evaluation.expected_answer = "no"; }), ({ code, err }) => {
    assert.equal(code, 1);
    assert.match(err, /expected_answer label/);
  });
});

test("negative control: changed provenance hash is caught", () => {
  withScratch(editPayload(d => { d.model.adapter_sha256 = "0".repeat(64); }), ({ code, err }) => {
    assert.equal(code, 1);
    assert.match(err, /FAIL provenance hashes/);
  });
});

test("negative control: dropped claim limits are caught", () => {
  withScratch(editPayload(d => { d.claim_scope = "Evaluation."; }), ({ code, err }) => {
    assert.equal(code, 1);
    assert.match(err, /FAIL recorded-only scope/);
  });
});

test("negative control: a frontend that starts reading the merged payload fails the premise check", () => {
  withScratch(dir => writeFileSync(join(dir, "app.js"), readFileSync(join(dir, "app.js"), "utf8") + "\n// fetch('data/results/merged-alpha-075/merged.json')\n"), ({ code, err }) => {
    assert.equal(code, 1);
    assert.match(err, /FAIL premise/);
  });
});

test("negative control: missing payload exits non-zero", () => {
  withScratch(dir => rmSync(join(dir, PAYLOAD)), ({ code }) => assert.notEqual(code, 0));
});
