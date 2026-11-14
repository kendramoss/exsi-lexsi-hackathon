// Node 22 + local Chrome only. TMPDIR and optional screenshots must point to a local scratch directory.
// Catches: phone chat clipping, pager stealing control keys, and historical claims leaking into mock runs.
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { extname, join, resolve } from "node:path";

const root = resolve(process.argv[2] || new URL("..", import.meta.url).pathname);
const screenshots = process.argv[3] && resolve(process.argv[3]);
const profile = await mkdtemp(join(tmpdir(), "evtune-historical-"));
const sleep = ms => new Promise(done => setTimeout(done, ms));
const failures = [], checks = [], external = [], exceptions = [], requests = [];
let chrome, socket, server;
let sequence = 0;
const pending = new Map(), listeners = new Map();
function call(method, params = {}, sessionId) {
  const id = ++sequence;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)); }, 15000);
    pending.set(id, { resolve: value => { clearTimeout(timer); resolve(value); }, reject: error => { clearTimeout(timer); reject(error); } });
    socket.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
  });
}
const on = (name, fn) => listeners.set(name, [...(listeners.get(name) || []), fn]);
async function check(name, fn) {
  if (process.env.CASE && !name.startsWith(process.env.CASE)) return;
  try { await fn(); checks.push(name); console.log(`PASS ${name}`); }
  catch (error) { failures.push(`${name}: ${error.message}`); console.error(`FAIL ${failures.at(-1)}`); }
}

try {
  if (screenshots) await mkdir(screenshots, { recursive: true });
  const mime = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".svg": "image/svg+xml" };
  server = createServer(async (request, response) => {
    try {
      const path = resolve(root, "." + new URL(request.url, "http://localhost").pathname.replace(/\/$/, "/index.html"));
      if (!path.startsWith(root + "/")) throw new Error("outside root");
      response.setHeader("Content-Type", mime[extname(path)] || "application/octet-stream");
      response.end(await readFile(path));
    } catch { response.writeHead(404); response.end("Not found"); }
  });
  await new Promise(done => server.listen(0, "127.0.0.1", done));
  const origin = `http://127.0.0.1:${server.address().port}`;
  chrome = spawn(process.env.CHROME_BIN || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", [
    "--headless=new", "--disable-gpu", "--disable-background-networking", "--disable-component-update",
    "--disable-default-apps", "--disable-sync", "--no-first-run", "--no-default-browser-check",
    "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
    "--password-store=basic", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank",
  ], { stdio: ["ignore", "ignore", "pipe"] });
  const url = await new Promise((resolve, reject) => {
    let stderr = "";
    const timer = setTimeout(() => reject(new Error(`Chrome startup timeout: ${stderr}`)), 15000);
    chrome.stderr.on("data", chunk => {
      stderr += chunk;
      const found = stderr.match(/DevTools listening on (ws:\/\/\S+)/);
      if (found) { clearTimeout(timer); resolve(found[1]); }
    });
    chrome.once("error", reject);
    chrome.once("exit", code => { clearTimeout(timer); reject(new Error(`Chrome exited ${code}`)); });
  });
  socket = new WebSocket(url);
  await new Promise((done, reject) => { socket.addEventListener("open", done, { once: true }); socket.addEventListener("error", reject, { once: true }); });
  socket.addEventListener("message", event => {
    const message = JSON.parse(event.data);
    if (message.id) {
      const task = pending.get(message.id); pending.delete(message.id);
      if (message.error) task?.reject(new Error(JSON.stringify(message.error))); else task?.resolve(message.result);
    } else for (const fn of listeners.get(message.method) || []) fn(message.params, message.sessionId);
  });
  const { targetId } = await call("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await call("Target.attachToTarget", { targetId, flatten: true });
  const evaluate = async expression => {
    if (process.env.DEBUG_BROWSER) console.error(expression.slice(0, 240));
    const result = await call("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true }, sessionId);
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  };
  const waitFor = async expression => {
    for (let i = 0; i < 240; i++) { if (await evaluate(expression)) return; await sleep(25); }
    throw new Error(`Timed out: ${expression}`);
  };
  const capture = async name => {
    if (!screenshots) return;
    await mkdir(screenshots, { recursive: true });
    const { data } = await call("Page.captureScreenshot", { format: "png" }, sessionId);
    await writeFile(join(screenshots, name + ".png"), Buffer.from(data, "base64"));
  };
  const metrics = async mobile => call("Emulation.setDeviceMetricsOverride", mobile
    ? { width: 390, height: 844, deviceScaleFactor: 1, mobile: true }
    : { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false }, sessionId);
  let loadCount = 0;
  on("Page.loadEventFired", () => loadCount++);
  const nav = async (run = "") => {
    const previousLoad = loadCount;
    await call("Page.navigate", { url: `${origin}/index.html?instant${run ? `&run=${run}` : ""}` }, sessionId);
    for (let i = 0; loadCount === previousLoad && i < 240; i++) await sleep(25);
    assert.ok(loadCount > previousLoad, "new document must load, not the prior page context");
    await waitFor('document.readyState === "complete" && document.querySelector("#convo.flow") && document.querySelector(".gp-claim")');
  };
  const go = async id => {
    await evaluate(`document.querySelector('a[data-sec="${id}"]').click()`);
    await waitFor(`document.querySelector('#steps [aria-current]')?.dataset.sec === '${id}'`);
    await sleep(200);
  };
  const press = async (key, code, virtualKey) => {
    await call("Input.dispatchKeyEvent", { type: "keyDown", key, code, windowsVirtualKeyCode: virtualKey, text: key === " " ? " " : key === "Enter" ? "\r" : undefined }, sessionId);
    await call("Input.dispatchKeyEvent", { type: "keyUp", key, code, windowsVirtualKeyCode: virtualKey }, sessionId);
    await sleep(420);
  };
  const focused = () => evaluate('document.activeElement.id');
  const section = () => evaluate('document.querySelector("#steps [aria-current]")?.dataset.sec');
  on("Runtime.exceptionThrown", data => exceptions.push(data.exceptionDetails));
  on("Network.requestWillBeSent", data => requests.push(data.request.url));
  // Reject any non-local request before it is sent; assert no attempts, not just no successful responses.
  on("Fetch.requestPaused", (data, session) => {
    const local = data.request.url.startsWith(origin + "/");
    if (!local) external.push(data.request.url);
    call(local ? "Fetch.continueRequest" : "Fetch.failRequest", local ? { requestId: data.requestId } : { requestId: data.requestId, errorReason: "BlockedByClient" }, session).catch(error => failures.push(error.message));
  });
  await call("Page.enable", {}, sessionId);
  await call("Runtime.enable", {}, sessionId);
  await call("Network.enable", {}, sessionId);
  await call("Fetch.enable", { patterns: [{ urlPattern: "*" }] }, sessionId);
  await call("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] }, sessionId);
  await metrics(false);

  await check("keyboard: Space and Enter open numbers; focus returns", async () => {
    await nav(); await go("s4");
    for (const [key, code, vk] of [[" ", "Space", 32], ["Enter", "Enter", 13]]) {
      await evaluate('document.querySelector("#open-all").focus()');
      await press(key, code, vk);
      assert.equal(await evaluate('document.querySelector("#all-dialog").open'), true, `${code} opens numbers`);
      assert.equal(await section(), "s4");
      await press("Escape", "Escape", 27);
      assert.equal(await evaluate('document.querySelector("#all-dialog").open'), false);
      assert.equal(await focused(), "open-all");
    }
  });
  await check("keyboard: chat controls retain native keys and focus", async () => {
    await nav(); await go("s1");
    await evaluate('document.querySelector("#convo-next").focus()');
    await press(" ", "Space", 32);
    assert.equal(await evaluate('document.querySelector("#convo-step").textContent'), "Step 2 of 5");
    assert.equal(await focused(), "convo-next"); assert.equal(await section(), "s1");
    await press("Enter", "Enter", 13);
    assert.equal(await evaluate('document.querySelector("#convo-step").textContent'), "Step 3 of 5");
    await evaluate('document.querySelector("#convo-prev").focus()'); await press(" ", "Space", 32);
    assert.equal(await evaluate('document.querySelector("#convo-step").textContent'), "Step 2 of 5");
    assert.equal(await focused(), "convo-prev"); assert.equal(await section(), "s1");
    await press("Enter", "Enter", 13);
    assert.equal(await evaluate('document.querySelector("#convo-step").textContent'), "Step 1 of 5");
    await evaluate('document.activeElement.blur()'); await press("ArrowRight", "ArrowRight", 39);
    assert.equal(await evaluate('document.querySelector("#convo-step").textContent'), "Step 2 of 5");
    await evaluate('document.querySelector("#convo-next").focus()'); await press("ArrowRight", "ArrowRight", 39);
    assert.equal(await evaluate('document.querySelector("#convo-step").textContent'), "Step 2 of 5", "focused controls own arrow keys too");
  });
  await check("keyboard: editable targets and links do not trigger paging; body still pages", async () => {
    await nav(); await go("s1");
    await evaluate(`(() => { const editor = document.createElement('div'); editor.id = 'keyboard-editor'; editor.contentEditable = 'true'; editor.textContent = 'Editable'; editor.style.cssText = 'position:fixed;top:100px;left:20px;z-index:100'; document.body.append(editor); editor.focus(); })()`);
    await call("Input.dispatchKeyEvent", { type: "rawKeyDown", key: " ", code: "Space", windowsVirtualKeyCode: 32 }, sessionId);
    await call("Input.dispatchKeyEvent", { type: "keyUp", key: " ", code: "Space", windowsVirtualKeyCode: 32 }, sessionId);
    assert.equal(await section(), "s1");
    assert.equal(await focused(), "keyboard-editor");
    await evaluate('document.querySelector("#keyboard-editor").remove()');
    await evaluate('document.querySelector("#steps a[data-sec=s1]").focus({preventScroll:true})');
    await press("ArrowDown", "ArrowDown", 40); assert.equal(await section(), "s1");
    await evaluate('document.activeElement.blur()'); await go("top"); await evaluate('document.activeElement.blur()');
    await press(" ", "Space", 32); assert.equal(await section(), "glance");
    await press("PageDown", "PageDown", 34); assert.equal(await section(), "s1");
  });

  for (const run of ["final-fresh", "mock-smoke"]) {
    await check(`mobile: ${run} full conversation is reachable by page scrolling`, async () => {
      await metrics(true); await nav(run);
      await evaluate('document.querySelector("#s1").scrollIntoView({block:"start", behavior:"instant"})');
      await waitFor('!!document.querySelector("#convo .branch-list .chat-row")');
      const selectors = await evaluate(`(() => {
        const nodes = [...document.querySelectorAll('#convo .bubble, #convo .file-page p, #convo .file-meta, #convo .cw-verdict')];
        nodes.forEach((node, index) => node.dataset.reach = index);
        return nodes.map(node => '[data-reach="' + node.dataset.reach + '"]');
      })()`);
      assert.ok(selectors.length >= 8, "full question, source, prior, pushback, both replies and verdicts");
      for (const selector of selectors) {
        const view = await evaluate(`(() => {
          const node = document.querySelector(${JSON.stringify(selector)});
          node.scrollIntoView({block:'center', behavior:'instant'});
          const rect = node.getBoundingClientRect(), style = getComputedStyle(node);
          const box = document.querySelector('#convo'), chat = getComputedStyle(box);
          const range = document.createRange(); range.selectNodeContents(node);
          const lines = [...range.getClientRects()].filter(r => r.width > 1 && r.height > 1);
          const first = lines[0] || rect;
          const hit = document.elementFromPoint(first.left + Math.min(4, first.width / 2), first.top + Math.min(4, first.height / 2));
          return {opacity: +style.opacity, height:rect.height, top:rect.top, bottom:rect.bottom,
            hit: !!hit && node.contains(hit), overflow:chat.overflow, mask:chat.maskImage,
            clipped:box.scrollHeight > box.clientHeight + 2, innerScroll:box.scrollTop,
            horizontal:node.scrollWidth > node.clientWidth + 2};
        })()`);
        assert.ok(view.height > 0 && view.opacity > 0, `${selector} visible: ${JSON.stringify(view)}`);
        assert.ok(view.top >= 49 && view.bottom <= 844, `${selector} reachable below nav: ${JSON.stringify(view)}`);
        assert.equal(view.hit, true, `${selector} hit-test visible`);
        assert.equal(view.overflow, "visible", "conversation must use page scrolling");
        assert.equal(view.mask, "none"); assert.equal(view.clipped, false);
        assert.equal(view.innerScroll, 0); assert.equal(view.horizontal, false);
      }
      await evaluate('document.querySelector("#convo .trunk").scrollIntoView({block:"start", behavior:"instant"})');
      await capture(`${run}-question-mobile`);
      await evaluate('document.querySelector("#convo .branches").scrollIntoView({block:"center", behavior:"instant"})');
      await capture(`${run}-replies-mobile`);
      await evaluate('document.querySelector("#replay").click()');
      assert.equal(await evaluate('getComputedStyle(document.querySelector("#convo")).overflow'), "visible");
      assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'), true);
    });
  }

  await check("mobile: animated replay keeps the question and source after the split", async () => {
    await metrics(true); await nav("final-fresh");
    await call("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "no-preference" }] }, sessionId);
    await evaluate('document.querySelector("#replay").click()');
    await waitFor('document.querySelectorAll("#convo .cw-verdict.show").length === 2');
    assert.equal(await evaluate('getComputedStyle(document.querySelector("#convo .trunk > .chat-row")).opacity'), "1", "earlier messages must not fold away on phones");
    assert.ok(await evaluate('document.querySelector("#convo .trunk > .chat-row").getBoundingClientRect().height > 100'));
    await call("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] }, sessionId);
  });

  for (const [run, expected] of [["mock-smoke", { families: 2, records: 6, conditions: 3, comparators: 5, mock: true }], ["final-fresh", { families: 136, records: 544, conditions: 3, comparators: 2, mock: false }]]) {
    await check(`provenance: ${run} scope and displayed scores match saved run`, async () => {
      await metrics(false); await nav(run);
      const rows = (await readFile(join(root, `data/results/${run}/cases.jsonl`), "utf8")).trim().split("\n").map(JSON.parse);
      const saved = JSON.parse(await readFile(join(root, `data/results/${run}/metrics.json`), "utf8"));
      assert.equal(rows.length, expected.records); assert.equal(saved.comparators.length, expected.comparators);
      const facts = await evaluate(`({fair:document.querySelector('#s3').innerText,work:document.querySelector('#s4 .which').innerText,
        intro:document.querySelector('#all-dialog .intro').textContent,path:document.querySelector('#src-path').textContent,
        lead:document.querySelector('.fair-lead').textContent,badgeHidden:document.querySelector('#mock-badge').hidden,
        titles:[...document.querySelectorAll('#scoreboard tbody th')].map(node => node.title),
        scores:[...document.querySelectorAll('#scoreboard tbody tr')].map(row => [...row.querySelectorAll('td .v')].map(node => node.textContent))})`);
      assert.equal(facts.path, `data/results/${run}/`); assert.equal(facts.badgeHidden, !expected.mock);
      assert.equal(facts.scores.length, expected.comparators);
      for (let index = 0; index < saved.comparators.length; index++) {
        const comparator = saved.comparators[index];
        assert.ok(facts.titles[index].includes(comparator.label));
        for (const [col, key] of ["valid_uptake", "uur", "final_accuracy", "solo_coverage", "unnecessary_clarification"].entries())
          assert.equal(facts.scores[index][col], `${Math.round(comparator.metrics[key].value * 100)}%`, `${comparator.id}/${key}`);
      }
      for (const text of [facts.fair, facts.work, facts.intro]) {
        assert.match(text, new RegExp(`\\b${expected.families} (?:invented )?(?:case )?families|\\b${expected.families} cases`), text);
        assert.match(text, new RegExp(`\\b${expected.records} (?:scored|pushbacks|records)`), text);
        if (expected.mock) {
          assert.match(text, /mock|invented/i);
          assert.doesNotMatch(text, /136|544|v6|5 clause types|nda-1|never seen in training|null settles|quotes null|Does the contract say/i);
        }
      }
      if (expected.mock) {
        assert.match(facts.lead, /3/); assert.match(facts.fair, /3 conditions/);
        assert.match(facts.work, /Currently/); assert.match(facts.work, /With EvidenceTune/);
        assert.match(facts.intro, /scripts\/make_mock_results\.py/);
        assert.match(facts.intro, /not.*(?:evaluation|model quality)|layout testing/i);
      } else {
        assert.match(facts.lead, /4/); assert.match(facts.work, /v6/);
        assert.match(facts.work, /0\.75/); assert.match(facts.fair, /5 clause types/);
        assert.match(facts.intro, /ordinary_sft|v5/); assert.match(facts.intro, /safetune|v6/);
        assert.doesNotMatch([facts.fair, facts.work, facts.intro].join(" "), /272 (?:case )?families/);
      }
      await go("s3"); await capture(`${run}-test-desktop`);
      await go("s4"); await capture(`${run}-work-desktop`);
      await evaluate('document.querySelector("#open-all").click()'); await capture(`${run}-numbers-desktop`);
      await evaluate('document.querySelector("#all-dialog").close()');
    });
  }
  await check("offline: tracked routes request only local artifacts and have no browser exceptions", async () => {
    assert.deepEqual(exceptions, []);
    assert.deepEqual(external, [], "no remote font or other service requests");
    assert.ok(requests.some(url => url.includes("/final-fresh/predictions.jsonl")));
    assert.ok(requests.some(url => url.includes("/mock-smoke/predictions.jsonl")));
    assert.equal(requests.some(url => url.includes("/merged-alpha-075/")), false, "historical routes must stay historical");
  });
  if (screenshots) await writeFile(join(screenshots, "browser-results.json"), JSON.stringify({ checks, failures, external, exceptions }, null, 2));
  assert.deepEqual(failures, [], "historical demo browser regressions");
  console.log(`PASS ${checks.length} browser regression groups`);
} finally {
  if (socket) socket.close();
  if (chrome && chrome.exitCode === null) {
    chrome.kill("SIGTERM");
    await Promise.race([new Promise(done => chrome.once("exit", done)), sleep(2000).then(() => { if (chrome.exitCode === null) chrome.kill("SIGKILL"); })]);
  }
  if (server) { server.closeAllConnections(); await new Promise(done => server.close(done)); }
  await rm(profile, { recursive: true, force: true });
}
