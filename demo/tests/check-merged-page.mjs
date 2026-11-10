import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { extname, join, resolve } from "node:path";

const root = resolve(process.argv[2] || new URL("..", import.meta.url).pathname);
const screenshotDir = process.argv[3] ? resolve(process.argv[3]) : null;
const payload = JSON.parse(await readFile(join(root, "data/results/merged-alpha-075/merged.json"), "utf8"));
const chromePath = process.env.CHROME_BIN || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const profile = await mkdtemp(join(tmpdir(), "exsi-merged-chrome-"));
let chrome;
let cdp;
let server;

const sleep = ms => new Promise(done => setTimeout(done, ms));
const mime = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml" };

class CDP {
  constructor(socket) {
    this.socket = socket;
    this.nextId = 0;
    this.pending = new Map();
    this.listeners = new Map();
    socket.addEventListener("message", event => {
      const message = JSON.parse(event.data);
      if (message.id) {
        const pending = this.pending.get(message.id);
        if (!pending) return;
        this.pending.delete(message.id);
        if (message.error) pending.reject(new Error(JSON.stringify(message.error)));
        else pending.resolve(message.result);
      } else {
        for (const listener of this.listeners.get(message.method) || []) listener(message.params);
      }
    });
  }
  static async connect(url) {
    const socket = new WebSocket(url);
    await new Promise((done, reject) => {
      socket.addEventListener("open", done, { once: true });
      socket.addEventListener("error", reject, { once: true });
    });
    return new CDP(socket);
  }
  call(method, params = {}, sessionId) {
    const id = ++this.nextId;
    return new Promise((done, reject) => {
      this.pending.set(id, { resolve: done, reject });
      this.socket.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
    });
  }
  on(method, listener) {
    const listeners = this.listeners.get(method) || [];
    listeners.push(listener);
    this.listeners.set(method, listeners);
  }
}

async function evaluate(sessionId, expression) {
  const result = await cdp.call("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true }, sessionId);
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}

async function waitFor(sessionId, expression, description) {
  for (let attempt = 0; attempt < 200; attempt += 1) {
    if (await evaluate(sessionId, expression)) return;
    await sleep(25);
  }
  throw new Error(`Timed out waiting for ${description}`);
}

async function capture(sessionId, name) {
  if (!screenshotDir) return;
  await mkdir(screenshotDir, { recursive: true });
  const screenshot = await cdp.call("Page.captureScreenshot", { format: "png", captureBeyondViewport: false }, sessionId);
  await writeFile(join(screenshotDir, `${name}.png`), Buffer.from(screenshot.data, "base64"));
}

async function press(sessionId, key, code, virtualKey) {
  const text = key === "Enter" ? "\r" : key === " " ? " " : undefined;
  await cdp.call("Input.dispatchKeyEvent", { type: "keyDown", key, code, text, windowsVirtualKeyCode: virtualKey, nativeVirtualKeyCode: virtualKey }, sessionId);
  await cdp.call("Input.dispatchKeyEvent", { type: "keyUp", key, code, windowsVirtualKeyCode: virtualKey, nativeVirtualKeyCode: virtualKey }, sessionId);
  await sleep(60);
}

async function visibilitySnapshot(sessionId, selector) {
  return evaluate(sessionId, `(() => {
    const el = document.querySelector(${JSON.stringify(selector)});
    if (!el) return { missing: true };
    el.scrollIntoView({ block: "center", behavior: "instant" });
    const textNode = el.firstChild && el.firstChild.nodeType === Node.TEXT_NODE ? el.firstChild : null;
    const range = document.createRange();
    if (textNode) {
      const newline = textNode.textContent.indexOf("\\n");
      const end = newline > 0 ? newline : textNode.textContent.length;
      range.setStart(textNode, 0); range.setEnd(textNode, end);
    }
    const first = textNode ? range.getBoundingClientRect() : el.getBoundingClientRect();
    const rect = el.getBoundingClientRect(), style = getComputedStyle(el), convo = document.getElementById("convo");
    const convoStyle = getComputedStyle(convo);
    const x = Math.max(0, Math.min(innerWidth - 1, first.left + Math.min(8, first.width / 2)));
    const y = Math.max(0, Math.min(innerHeight - 1, first.top + Math.min(8, first.height / 2)));
    return {
      missing: false, display: style.display, visibility: style.visibility, opacity: Number(style.opacity),
      insideConvo: !!el.closest("#convo"),
      top: rect.top, bottom: rect.bottom, firstTop: first.top, firstBottom: first.bottom,
      hit: !!document.elementFromPoint(x, y)?.closest(el.id ? "#" + el.id : el.classList.contains("raw-output") ? ".raw-output" : "[data-arm]"),
      convoOverflow: convoStyle.overflow, convoMask: convoStyle.maskImage || convoStyle.webkitMaskImage,
      convoHeight: convo.clientHeight, convoContent: convo.scrollHeight, convoScrollTop: convo.scrollTop,
      width: rect.width, scrollWidth: el.scrollWidth, clientWidth: el.clientWidth,
    };
  })()`);
}

function assertReachable(snapshot, description) {
  assert.equal(snapshot.missing, false, `${description}: element missing`);
  assert.notEqual(snapshot.display, "none", `${description}: display none`);
  assert.equal(snapshot.visibility, "visible", `${description}: not visible`);
  assert.ok(snapshot.opacity > 0, `${description}: transparent`);
  assert.ok(snapshot.bottom > 0 && snapshot.top < 844, `${description}: outside viewport after page scroll (${snapshot.top}…${snapshot.bottom})`);
  assert.ok(snapshot.firstBottom > 0 && snapshot.firstTop < 844, `${description}: first output line clipped`);
  assert.equal(snapshot.hit, true, `${description}: first line is not hit-test visible`);
  if (snapshot.insideConvo) {
    assert.ok(!["hidden", "clip", "auto", "scroll"].includes(snapshot.convoOverflow), `${description}: chat clips or separately scrolls (${snapshot.convoOverflow})`);
    assert.ok(snapshot.convoMask === "none" || !snapshot.convoMask, `${description}: chat mask remains`);
    assert.ok(snapshot.convoContent <= snapshot.convoHeight + 2, `${description}: chat content is clipped (${snapshot.convoContent} > ${snapshot.convoHeight})`);
    assert.equal(snapshot.convoScrollTop, 0, `${description}: evidence requires inner chat scrolling`);
  }
  assert.ok(snapshot.scrollWidth <= snapshot.clientWidth + 2, `${description}: horizontal text clipping`);
}

try {
  server = createServer(async (request, response) => {
    try {
      const pathname = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
      const relative = pathname === "/" ? "index.html" : pathname.replace(/^\/+/, "");
      const path = resolve(root, relative);
      if (!path.startsWith(`${root}/`)) throw new Error("invalid path");
      const body = await readFile(path);
      response.writeHead(200, { "Content-Type": mime[extname(path)] || "application/octet-stream", "Cache-Control": "no-store" });
      response.end(body);
    } catch {
      response.writeHead(404);
      response.end("Not found");
    }
  });
  await new Promise(done => server.listen(0, "127.0.0.1", done));
  const origin = `http://127.0.0.1:${server.address().port}`;

  chrome = spawn(chromePath, [
    "--headless=new", "--disable-gpu", "--disable-background-networking", "--disable-component-update",
    "--disable-default-apps", "--disable-sync", "--no-first-run", "--no-default-browser-check",
    "--password-store=basic", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe"] });
  const browserSocket = await new Promise((done, reject) => {
    let stderr = "";
    const timeout = setTimeout(() => reject(new Error(`Chrome startup timed out: ${stderr}`)), 15000);
    chrome.stderr.on("data", chunk => {
      stderr += chunk.toString();
      const match = stderr.match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (match) { clearTimeout(timeout); done(match[1]); }
    });
    chrome.once("error", reject);
    chrome.once("exit", code => { clearTimeout(timeout); reject(new Error(`Chrome exited before startup (${code}): ${stderr}`)); });
  });
  cdp = await CDP.connect(browserSocket);
  const { targetId } = await cdp.call("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await cdp.call("Target.attachToTarget", { targetId, flatten: true });
  const requests = [];
  const exceptions = [];
  cdp.on("Network.requestWillBeSent", params => requests.push(params.request.url));
  cdp.on("Runtime.exceptionThrown", params => exceptions.push(params.exceptionDetails));
  await cdp.call("Page.enable", {}, sessionId);
  await cdp.call("Runtime.enable", {}, sessionId);
  await cdp.call("Network.enable", {}, sessionId);
  await cdp.call("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] }, sessionId);
  await cdp.call("Emulation.setDeviceMetricsOverride", { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false }, sessionId);
  await cdp.call("Page.navigate", { url: `${origin}/index.html?instant` }, sessionId);
  await waitFor(sessionId, 'document.readyState === "complete" && document.querySelector("#convo.flow")', "merged app load");

  assert.match(await evaluate(sessionId, 'document.getElementById("mock-badge").textContent'), /Recorded only/i);
  assert.equal(await evaluate(sessionId, 'document.querySelectorAll("#bands [data-condition]").length'), 5);
  assert.equal(await evaluate(sessionId, 'document.getElementById("bands").dataset.case'), "sc-01-25");

  for (const record of payload.illustration.records) {
    await evaluate(sessionId, `document.querySelector('#bands [data-condition="${record.condition}"]').click()`);
    await evaluate(sessionId, 'document.getElementById("replay").click()');
    assert.equal(await evaluate(sessionId, 'document.querySelector("#bands [aria-pressed=true]").dataset.condition'), record.condition);
    assert.equal(await evaluate(sessionId, 'document.querySelector("#convo .file").title'), record.input);
    for (const arm of ["baseline_v7", "merge_alpha_0.75"]) {
      const output = record.outputs[arm];
      const branch = `#convo [data-arm="${arm}"]`;
      assert.equal(await evaluate(sessionId, `document.querySelector('${branch} .raw-output').textContent`), output.raw_output);
      for (const [key, value] of Object.entries(output.evaluation)) {
        assert.equal(await evaluate(sessionId, `document.querySelector('${branch} [data-eval="${key}"]').textContent`), String(value), `${record.condition}/${arm}/${key}`);
      }
    }
    if (record.condition === "valid") {
      await evaluate(sessionId, 'document.getElementById("s1").scrollIntoView({block:"center"})');
      await sleep(100);
      await capture(sessionId, "merged-chat-desktop");
    }
  }

  const expected = {
    semantic_frozen_test: {
      baseline_v7: { task_success: ["88.75%", "213 / 240 rows"], all_five_task_success: ["60.4167%", "29 / 48 cases"] },
      "merge_alpha_0.75": { task_success: ["92.50%", "222 / 240 rows"], all_five_task_success: ["72.9167%", "35 / 48 cases"] },
    },
    v8_targeted_frozen_test: {
      baseline_v7: { task_success: ["91.4815%", "247 / 270 rows"], all_five_task_success: ["74.0741%", "40 / 54 cases"] },
      "merge_alpha_0.75": { task_success: ["93.7037%", "253 / 270 rows"], all_five_task_success: ["79.6296%", "43 / 54 cases"] },
    },
  };
  await evaluate(sessionId, 'document.getElementById("open-all").click()');
  for (const [view, arms] of Object.entries(expected)) {
    await evaluate(sessionId, `document.querySelector('[data-view="${view}"]').click()`);
    if (view === "semantic_frozen_test") await capture(sessionId, "merged-scores-desktop");
    for (const [arm, metrics] of Object.entries(arms)) {
      for (const [metric, values] of Object.entries(metrics)) {
        const selector = `#scoreboard td[data-view="${view}"][data-arm="${arm}"][data-metric="${metric}"]`;
        const text = await evaluate(sessionId, `document.querySelector('${selector}').textContent.replace(/\\s+/g, " ").trim()`);
        for (const value of values) assert.ok(text.includes(value), `${view}/${arm}/${metric}: ${text} must include ${value}`);
      }
    }
  }
  await evaluate(sessionId, 'document.getElementById("close-all").click()');

  const text = await evaluate(sessionId, "document.body.innerText");
  for (const disclosure of [
    "No live inference", "Apple MPS bf16", "custom EvidenceTune contract-v2 scorers, not AuditKIT",
    "synthetic", "proxy labels", "Dev-only selection", "frozen confirmation",
    "Earlier v7/v8 frozen runs existed but were not used for merged-model selection",
    "No human validation", "base→merged improvement is unmeasured", "broad natural",
  ]) assert.ok(text.toLowerCase().includes(disclosure.toLowerCase()), `Missing disclosure: ${disclosure}`);

  const reviewFailures = [];
  const regression = async (name, check) => {
    try { await check(); } catch (error) { reviewFailures.push(`${name}: ${error.message}`); }
  };
  const headings = {
    valid: "A supported correction. Does it switch?",
    unsupported_toward: "An unsupported correction. Does it switch?",
    unsupported_away: "An unsupported correction. Does it switch?",
    pressure_away: "Pressure without evidence. Does it switch?",
    solo: "No earlier answer or pushback. What does it answer?",
  };

  for (const record of payload.illustration.records) {
    await evaluate(sessionId, `document.querySelector('#bands [data-condition="${record.condition}"]').click()`);
    await evaluate(sessionId, 'document.getElementById("replay").click()');
    await regression(`${record.condition} gauge and heading`, async () => {
      assert.equal(await evaluate(sessionId, 'document.getElementById("glance-title").textContent'), headings[record.condition]);
      const clocks = await evaluate(sessionId, '[...document.querySelectorAll("#hero-vis .clockcol")].map(el => el.textContent)');
      const aria = await evaluate(sessionId, 'document.getElementById("hero-vis").getAttribute("aria-label")');
      assert.ok(!/wrong/i.test(aria), aria);
      assert.ok(aria.includes(headings[record.condition]), aria);
      for (const clock of clocks) {
        assert.ok(!/wrong/i.test(clock), clock);
        assert.ok(clock.includes("evidence"), clock);
        assert.ok(clock.includes(record.metadata.answer), clock);
        if (record.condition !== "solo") {
          assert.ok(clock.includes("requested"), clock);
          assert.ok(clock.includes(record.metadata.target), clock);
        }
      }
      const tagOverlap = await evaluate(sessionId, `[...document.querySelectorAll('#hero-vis .clock.gauge')].some(svg => {
        const truth = svg.querySelector('.c-tag.truth'), push = svg.querySelector('.c-tag.push');
        if (!truth || !push) return false;
        const a = truth.getBoundingClientRect(), b = push.getBoundingClientRect();
        return a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
      })`);
      assert.equal(tagOverlap, false, 'gauge labels must not overlap');
    });
    await regression(`${record.condition} exact accessible input`, async () => {
      assert.equal(await evaluate(sessionId, 'document.getElementById("saved-input").hidden'), false);
      await evaluate(sessionId, 'document.getElementById("saved-input").open = true');
      assert.equal(await evaluate(sessionId, 'document.getElementById("saved-input-text").textContent'), record.input);
      const readable = await evaluate(sessionId, `(() => { const el = document.getElementById("saved-input-text"), style = getComputedStyle(el); return { whiteSpace: style.whiteSpace, overflow: style.overflow, clipped: el.scrollHeight > el.clientHeight + 2 }; })()`);
      assert.match(readable.whiteSpace, /pre-wrap/);
      assert.ok(!["hidden", "clip", "auto", "scroll"].includes(readable.overflow));
      assert.equal(readable.clipped, false);
      assertReachable(await visibilitySnapshot(sessionId, "#saved-input-text"), `${record.condition} full input`);
    });
  }

  await regression("Space activates a condition and preserves focus", async () => {
    await evaluate(sessionId, 'document.querySelector("#bands [data-condition=valid]").focus()');
    await press(sessionId, " ", "Space", 32);
    assert.equal(await evaluate(sessionId, 'document.querySelector("#bands [aria-pressed=true]").dataset.condition'), "valid");
    assert.equal(await evaluate(sessionId, "document.activeElement.dataset.condition"), "valid");
  });
  await regression("Enter activates a condition and preserves focus", async () => {
    await evaluate(sessionId, 'document.querySelector("#bands [data-condition=unsupported_toward]").focus()');
    await press(sessionId, "Enter", "Enter", 13);
    assert.equal(await evaluate(sessionId, 'document.querySelector("#bands [aria-pressed=true]").dataset.condition'), "unsupported_toward");
    assert.equal(await evaluate(sessionId, "document.activeElement.dataset.condition"), "unsupported_toward");
  });
  await regression("Arrow keys do not activate conditions or steal focus", async () => {
    await evaluate(sessionId, 'document.querySelector("#bands [data-condition=pressure_away]").focus()');
    const selected = await evaluate(sessionId, 'document.querySelector("#bands [aria-pressed=true]").dataset.condition');
    await press(sessionId, "ArrowRight", "ArrowRight", 39);
    await press(sessionId, "ArrowDown", "ArrowDown", 40);
    assert.equal(await evaluate(sessionId, "document.activeElement.dataset.condition"), "pressure_away");
    assert.equal(await evaluate(sessionId, 'document.querySelector("#bands [aria-pressed=true]").dataset.condition'), selected);
  });
  await regression("Space toggles full input natively and preserves summary focus", async () => {
    await evaluate(sessionId, 'document.getElementById("saved-input").open = false; document.querySelector("#saved-input summary").focus()');
    await press(sessionId, " ", "Space", 32);
    assert.equal(await evaluate(sessionId, 'document.getElementById("saved-input").open'), true);
    assert.equal(await evaluate(sessionId, "document.activeElement.tagName"), "SUMMARY");
  });

  await cdp.call("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true }, sessionId);
  await sleep(100);
  assert.equal(await evaluate(sessionId, "document.documentElement.scrollWidth <= window.innerWidth"), true, "mobile page must not overflow horizontally");
  for (const record of payload.illustration.records) {
    await evaluate(sessionId, `document.querySelector('#bands [data-condition="${record.condition}"]').click()`);
    await evaluate(sessionId, 'document.getElementById("replay").click()');
    for (const arm of ["baseline_v7", "merge_alpha_0.75"]) {
      await regression(`${record.condition}/${arm} mobile raw-output visibility`, async () => {
        assertReachable(await visibilitySnapshot(sessionId, `#convo [data-arm="${arm}"] .raw-output`), `${record.condition}/${arm} raw output`);
      });
      await regression(`${record.condition}/${arm} mobile evaluation visibility`, async () => {
        assertReachable(await visibilitySnapshot(sessionId, `#convo [data-arm="${arm}"] [data-eval="whole_window_answer_ok"]`), `${record.condition}/${arm} evaluation`);
      });
    }
    await regression(`${record.condition} mobile full-input visibility`, async () => {
      await evaluate(sessionId, 'document.getElementById("saved-input").open = true');
      assert.equal(await evaluate(sessionId, 'document.getElementById("saved-input-text").textContent'), record.input);
      assertReachable(await visibilitySnapshot(sessionId, "#saved-input-text"), `${record.condition} mobile full input`);
    });
    if (record.condition === "valid" || record.condition === "solo") await capture(sessionId, `merged-chat-${record.condition}-mobile`);
  }
  assert.deepEqual(reviewFailures, [], "review regression checks");
  await cdp.call("Page.navigate", { url: `${origin}/index.html?run=mock-smoke&instant` }, sessionId);
  await waitFor(sessionId, 'document.querySelector("#convo.flow")', "historical mock replay");
  assert.equal(await evaluate(sessionId, 'document.getElementById("mock-badge").textContent'), "Mock data");
  assert.deepEqual(exceptions, [], "browser JavaScript exceptions");
  assert.deepEqual(requests.filter(url => /^https?:/i.test(url) && !url.startsWith(origin)), [], "external network dependencies");
  console.log("PASS: 5 conditions × 2 arms with exact raw outputs/evaluations; 8 exact score cells; 5 condition label sets; 5 exact accessible inputs; 4 keyboard checks; 25 mobile visibility checks; both suites; disclosures; historical mock; no external requests; no browser exceptions");
} finally {
  if (cdp) cdp.socket.close();
  if (chrome && chrome.exitCode === null) {
    chrome.kill("SIGTERM");
    await Promise.race([new Promise(done => chrome.once("exit", done)), sleep(2000).then(() => chrome.kill("SIGKILL"))]);
  }
  if (server) await new Promise(done => server.close(done));
  await rm(profile, { recursive: true, force: true });
}
