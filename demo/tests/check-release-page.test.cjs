// Actual Playwright interactions for the merged release and preserved routes.
// NODE_PATH=<directory containing playwright> CHROME_BIN=<browser> node --test demo/tests/check-release-page.test.cjs
const test = require('node:test');
const assert = require('node:assert/strict');
const { createServer } = require('node:http');
const { readFile, mkdir } = require('node:fs/promises');
const { readFileSync } = require('node:fs');
const { join, resolve, extname } = require('node:path');
const { chromium } = require('playwright');

const ROOT = resolve(process.env.EVTUNE_DEMO_ROOT || join(__dirname, '..'));
const SHOTS = process.env.EVTUNE_RELEASE_SCREENSHOTS;
const PAYLOAD = JSON.parse(readFileSync(join(ROOT, 'data/results/merged-alpha-075/merged.json'), 'utf8'));
const ARMS = ['baseline_v7', 'merge_alpha_0.75'];
const HASH = 'a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335';
const BOARDS = {
  semantic_frozen_test: { rows: 240, cases: 48, baseline_v7: [213, 29], 'merge_alpha_0.75': [222, 35] },
  v8_targeted_frozen_test: { rows: 270, cases: 54, baseline_v7: [247, 40], 'merge_alpha_0.75': [253, 43] },
};
let browser, server, origin;

test.before(async () => {
  const mime = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.jsonl': 'application/x-ndjson', '.woff2': 'font/woff2', '.svg': 'image/svg+xml' };
  server = createServer(async (req, res) => {
    try {
      const relative = new URL(req.url, 'http://localhost').pathname.replace(/\/$/, '/index.html');
      const path = resolve(ROOT, '.' + relative);
      if (!path.startsWith(ROOT + '/')) throw new Error('outside demo');
      res.setHeader('Content-Type', mime[extname(path)] || 'application/octet-stream');
      res.end(await readFile(path));
    } catch { res.writeHead(404); res.end('Not found'); }
  });
  await new Promise(done => server.listen(0, '127.0.0.1', done));
  origin = `http://127.0.0.1:${server.address().port}`;
  browser = await chromium.launch({ headless: true, args: ['--disable-gpu'], ...(process.env.CHROME_BIN ? { executablePath: process.env.CHROME_BIN } : {}) });
  if (SHOTS) await mkdir(SHOTS, { recursive: true });
});

test.after(async () => {
  await browser?.close().catch(() => {});
  if (server) { server.closeAllConnections(); await new Promise(done => server.close(done)); }
});

async function visit(query = '', options = {}) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: 'light', ...options });
  const page = await context.newPage();
  page.setDefaultTimeout(6000);
  await page.addInitScript(() => {
    window.__preventedWheels = 0;
    const prevent = Event.prototype.preventDefault;
    Event.prototype.preventDefault = function () {
      if (this.type === 'wheel') window.__preventedWheels++;
      return prevent.call(this);
    };
  });
  const errors = [], external = [], failed = [], requests = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('response', response => { if (response.status() >= 400) failed.push(response.url()); });
  await context.route('**/*', route => {
    const url = route.request().url();
    requests.push(url);
    if (!url.startsWith(origin + '/')) { external.push(url); return route.abort(); }
    return route.continue();
  });
  await page.goto(origin + '/' + query, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  return { page, context, errors, external, failed, requests };
}

async function merged(query = '', options = {}) {
  const state = await visit(query, options);
  try {
    await state.page.waitForSelector('.answer-result[data-policy="merge_alpha_0.75"]');
    return state;
  } catch (error) { await state.context.close(); throw error; }
}

async function shot(page, name, fullPage = false) {
  if (SHOTS) await page.screenshot({ path: join(SHOTS, name + '.png'), fullPage });
}

async function openNumbers(page) {
  await page.locator('#steps a[data-sec="s4"]').click();
  await page.waitForFunction(() => document.querySelector('#steps a[aria-current]')?.dataset.sec === 's4');
  await page.locator('#open-all').click();
  await page.locator('#all-dialog').waitFor({ state: 'visible' });
}

test('default route loads the recorded merged release with local assets only', async () => {
  const { page, context, errors, external, failed, requests } = await visit();
  try {
    assert.ok(requests.some(url => url.endsWith('/data/results/merged-alpha-075/merged.json')));
    assert.ok(!requests.some(url => /data\/results\/(final-fresh|mock-smoke)\//.test(url)), 'default must not fetch historical or invented records');
    const text = await page.locator('body').innerText();
    assert.match(text, /recorded/i);
    assert.match(text, /75%\s*v7[\s\S]*25%\s*v8/i);
    assert.match(text, /92\.50%|92\.5%/);
    assert.match(text, /93\.70%|93\.7%/);
    assert.match(text, /task[ -]success|task[ -]contract/i);
    assert.doesNotMatch(text, /544 pushbacks|136 cases|VitaminC|nda-1, 7, 15/);
    assert.deepEqual(external, []);
    assert.deepEqual(failed, []);
    assert.deepEqual(errors, []);
    await shot(page, '01-merged-default');
  } finally { await context.close().catch(() => {}); }
});

test('response comparison displays exact saved merged and matching v7 raw outputs', async () => {
  const { page, context } = await merged();
  try {
    const rows = page.locator('#hero-vis .answer-result');
    assert.equal(await rows.count(), 2);
    const texts = [];
    for (const arm of ARMS) texts.push(await page.locator(`#hero-vis .answer-result[data-policy="${arm}"] .result-response`).textContent());
    const matching = PAYLOAD.illustration.records.find(record => ARMS.every((arm, i) => record.outputs[arm].raw_output === texts[i]));
    assert.ok(matching, 'both outputs must be one actual matched condition, verbatim including machine-readable headers');
    assert.equal(await page.locator('#hero-vis svg.clock').count(), 0);
    for (const record of PAYLOAD.illustration.records) {
      await page.locator('#merged-condition').selectOption(record.condition);
      for (const arm of ARMS) {
        assert.equal(await page.locator(`#hero-vis .answer-result[data-policy="${arm}"] .result-response`).textContent(), record.outputs[arm].raw_output);
      }
    }
    await page.locator('#steps a[data-sec="glance"]').click();
    await shot(page, '02-merged-comparison');
  } finally { await context.close().catch(() => {}); }
});

test('both frozen scoreboards preserve matching counts and metric denominators', async () => {
  const { page, context } = await merged();
  try {
    await openNumbers(page);
    for (const [view, spec] of Object.entries(BOARDS)) {
      const board = page.locator(`#scoreboards > [data-view="${view}"]`);
      assert.equal(await board.count(), 1, `one explicit frozen suite: ${view}`);
      for (const arm of ARMS) {
        const task = board.locator(`[data-arm="${arm}"][data-metric="task_success"]`);
        const allFive = board.locator(`[data-arm="${arm}"][data-metric="all_five_task_success"]`);
        assert.equal(await task.getAttribute('data-count'), String(spec[arm][0]));
        assert.equal(await task.getAttribute('data-n'), String(spec.rows));
        assert.equal(await allFive.getAttribute('data-count'), String(spec[arm][1]));
        assert.equal(await allFive.getAttribute('data-n'), String(spec.cases));
      }
    }
    assert.match(await page.locator('#all-dialog').innerText(), /task[ -]success|task[ -]contract/i);
    await shot(page, '05-merged-scoreboards');
  } finally { await context.close().catch(() => {}); }
});

test('visible provenance identifies adapter, proxy limitations, backend, and source', async () => {
  const { page, context } = await merged();
  try {
    await openNumbers(page);
    const text = await page.locator('body').innerText();
    assert.ok(text.includes(HASH));
    assert.ok(text.includes('data/results/merged-alpha-075/merged.json'));
    assert.match(text, /synthetic/i);
    assert.match(text, /not human.validated|no human validation|not.*validated.*humans/i);
    assert.match(text, /Apple MPS|MPS bf16/i);
    assert.match(text, /contract.v2/i);
    assert.match(text, /dev.only|dev data only/i);
    const hrefs = await page.locator('a[href]').evaluateAll(links => links.map(link => link.href));
    assert.ok(hrefs.some(href => href === 'https://huggingface.co/Mizore66/evidencetune-merged-alpha-0.75'));
  } finally { await context.close().catch(() => {}); }
});

test('small wheel input is native and does not jump chapters', async () => {
  const { page, context } = await merged();
  try {
    await page.mouse.move(400, 500);
    await page.mouse.wheel(0, 45);
    await page.waitForTimeout(850);
    const y = await page.evaluate(() => scrollY);
    assert.ok(y > 0 && y < 130, `45px input moved ${y}px`);
    await page.mouse.wheel(0, 120);
    await page.waitForTimeout(350);
    assert.equal(await page.evaluate(() => window.__preventedWheels), 0, 'page must never intercept wheel input');
    assert.ok(await page.evaluate(() => scrollY < 350), 'a further 120px wheel must not become a chapter jump');
    assert.equal(await page.locator('.chapter-wipe').count(), 0);
    assert.ok(!await page.locator('html').getAttribute('data-chapter-scroll') || await page.locator('html').getAttribute('data-chapter-scroll') === 'native');
  } finally { await context.close().catch(() => {}); }
});

test('desktop conversation follows scroll, reverses, and uses only saved condition outputs', async () => {
  const { page, context, errors } = await merged();
  try {
    await page.locator('#steps a[data-sec="s1"]').click();
    await page.waitForFunction(() => document.querySelector('#steps a[aria-current]')?.dataset.sec === 's1');
    const position = await page.locator('#s1').evaluate(s => s.getBoundingClientRect().top + scrollY - document.querySelector('.top').getBoundingClientRect().height);
    const span = await page.locator('#s1').evaluate(s => s.getBoundingClientRect().height);
    const scene = await page.evaluate(() => innerHeight - document.querySelector('.top').getBoundingClientRect().height);
    assert.ok(span > scene * 2, 'desktop conversation needs a real scroll runway');
    await page.evaluate(y => scrollTo({ top: y, behavior: 'instant' }), position + 2);
    await page.waitForTimeout(120);
    const first = await page.locator('#convo').getAttribute('data-step');
    await page.waitForTimeout(1800);
    assert.equal(await page.locator('#convo').getAttribute('data-step'), first, 'scroll journey must not autoplay');
    await page.evaluate(y => scrollTo({ top: y, behavior: 'instant' }), position + span - scene - 4);
    await page.waitForTimeout(160);
    assert.notEqual(await page.locator('#convo').getAttribute('data-step'), first);
    assert.equal(await page.locator('#convo .recorded-output').count(), 2);
    const condition = await page.locator('#merged-condition').inputValue();
    const record = PAYLOAD.illustration.records.find(row => row.condition === condition);
    for (const row of await page.locator('#convo .recorded-output').all()) {
      const arm = await row.getAttribute('data-policy');
      assert.equal(await row.textContent(), record.outputs[arm].raw_output);
    }
    await page.evaluate(y => scrollTo({ top: y, behavior: 'instant' }), position + 2);
    await page.waitForTimeout(160);
    assert.equal(await page.locator('#convo').getAttribute('data-step'), first);
    assert.deepEqual(errors, []);
    await shot(page, '03-merged-conversation');
  } finally { await context.close().catch(() => {}); }
});

test('keyboard controls and direct section navigation preserve native control behavior', async () => {
  const { page, context } = await merged();
  try {
    await page.locator('#steps a[data-sec="s1"]').click();
    await page.waitForFunction(() => document.querySelector('#steps a[aria-current]')?.dataset.sec === 's1');
    const next = page.locator('#convo-next');
    await next.focus();
    await page.keyboard.press('Enter');
    await page.waitForTimeout(750);
    assert.equal(await page.evaluate(() => document.activeElement.id), 'convo-next');
    await page.keyboard.press('Space');
    await page.waitForTimeout(750);
    assert.equal(await page.evaluate(() => document.activeElement.id), 'convo-next');
    await page.locator('#steps a[data-sec="s4"]').click();
    await page.locator('#open-all').click();
    assert.ok(await page.locator('#all-dialog').isVisible());
    await page.keyboard.press('Escape');
    assert.ok(!await page.locator('#all-dialog').isVisible());
  } finally { await context.close().catch(() => {}); }
});

test('mobile and reduced motion expose complete readable recorded transcripts', async () => {
  for (const options of [{ viewport: { width: 390, height: 844 } }, { reducedMotion: 'reduce' }]) {
    const { page, context, errors, external } = await merged('', options);
    try {
      for (const record of PAYLOAD.illustration.records) {
        await page.locator('#merged-condition').selectOption(record.condition);
        const outputs = page.locator('#convo .recorded-output');
        assert.equal(await outputs.count(), 2);
        for (const row of await outputs.all()) {
          const arm = await row.getAttribute('data-policy');
          assert.equal(await row.textContent(), record.outputs[arm].raw_output);
          await row.scrollIntoViewIfNeeded();
          assert.ok(await row.isVisible());
        }
      }
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      assert.deepEqual(errors, []);
      assert.deepEqual(external, []);
      await shot(page, options.reducedMotion ? '06-reduced-transcript' : '04-mobile-transcript', true);
    } finally { await context.close().catch(() => {}); }
  }
});

test('missing merged evidence is reported instead of substituting another run', async () => {
  const context = await browser.newContext();
  const page = await context.newPage();
  const requests = [];
  page.on('request', request => requests.push(request.url()));
  await context.route('**/data/results/merged-alpha-075/merged.json', route => route.fulfill({ status: 404, body: 'Missing recorded evidence' }));
  try {
    await page.goto(origin + '/', { waitUntil: 'networkidle' });
    await page.locator('.error, [role="alert"]').first().waitFor({ state: 'visible' });
    const text = await page.locator('body').innerText();
    assert.match(text, /merged|release/i);
    assert.match(text, /could not|missing|unavailable|failed/i);
    assert.equal(await page.locator('.answer-result').count(), 0);
    assert.ok(!requests.some(url => /data\/results\/(final-fresh|mock-smoke)\//.test(url)), 'missing release must not fall back to another run');
  } finally { await context.close().catch(() => {}); }
});

test('historical and invented routes remain explicit and keep exact saved responses', async () => {
  for (const run of ['final-fresh', 'mock-smoke']) {
    const { page, context, errors, requests } = await visit(`?run=${run}`);
    try {
      await page.waitForSelector('#hero-vis .answer-result');
      const text = await page.locator('body').innerText();
      assert.match(text, run === 'final-fresh' ? /historical|earlier v[56]/i : /invented|layout.testing/i);
      assert.ok(!requests.some(url => url.endsWith('/merged.json')));
      const caseId = await page.locator('#hero-vis').getAttribute('data-case');
      const saved = readFileSync(join(ROOT, `data/results/${run}/predictions.jsonl`), 'utf8').trim().split('\n').map(JSON.parse);
      for (const row of await page.locator('#hero-vis .answer-result').all()) {
        const arm = await row.getAttribute('data-policy');
        const record = saved.find(item => item.case_id === caseId && item.policy === arm);
        assert.ok(record);
        const expected = record.raw_output.split(/\r?\n/).filter(line => !/^\s*(ACTION|ANSWER)\s*:/i.test(line)).join(' ').trim() || record.raw_output;
        assert.equal(await row.locator('.result-response').innerText(), expected);
      }
      assert.deepEqual(errors, []);
    } finally { await context.close().catch(() => {}); }
  }
});
