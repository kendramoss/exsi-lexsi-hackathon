// Regression tests for check-merged-page.mjs: it must pass on the real tree,
// enforce merged frontend wiring, distinguish browser execution, and reject tampered data.
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
  for (const file of ["index.html", "app.js", "merged-app.js", "merged-data.js", PAYLOAD]) cpSync(join(DEMO, file), join(dir, file));
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

test("real tree: pinned evidence and merged default frontend wiring pass", () => {
  const { code, out, err } = run(DEMO);
  assert.equal(code, 0, err);
  assert.match(out, /PASS: 7 merged evidence and frontend wiring checks/);
  assert.match(out, /actual Playwright/);
  assert.doesNotMatch(out, /No standalone merged renderer|historical final-fresh run|SKIP/);
  assert.doesNotMatch(out, /^PASS.*browser/im);
});

test("REQUIRE_MERGED_BROWSER cannot silently accept an unavailable browser runtime", () => {
  const { code, out, err } = run(DEMO, { REQUIRE_MERGED_BROWSER: "1", NODE_PATH: "", CHROME_BIN: "/missing-required-test-browser" });
  assert.notEqual(code, 0, out + err);
  assert.doesNotMatch(out, /SKIP \(not passed\)/);
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

test("negative control: a frontend that stops loading the merged adapter fails", () => {
  withScratch(dir => writeFileSync(join(dir, "index.html"), readFileSync(join(dir, "index.html"), "utf8").replaceAll("merged-data.js", "missing-adapter.js")), ({ code, err }) => {
    assert.equal(code, 1);
    assert.match(err, /FAIL default frontend wires/);
  });
});

test("negative control: a missing merged renderer fails", () => {
  withScratch(dir => rmSync(join(dir, "merged-app.js")), ({ code, err }) => {
    assert.equal(code, 1);
    assert.match(err, /FAIL default frontend wires/);
  });
});

test("negative control: missing payload exits non-zero", () => {
  withScratch(dir => rmSync(join(dir, PAYLOAD)), ({ code }) => assert.notEqual(code, 0));
});
