const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = readFileSync(join(__dirname, '..', 'chapter-scroll.js'), 'utf8');

// Exercise the shipped controller with screen-pixel geometry and a deterministic
// event loop. No controller logic is copied into the harness.
function setup({ tallResult = false } = {}) {
  let now = 0, nextId = 0, y = 0, autoPlaying = false;
  const tasks = new Map(), listeners = new Map(), samples = [], arrivals = [];
  let enters = 0, leaves = 0;
  const schedule = (fn, delay, raf = false) => {
    const id = ++nextId;
    tasks.set(id, { at: now + delay, fn, raf });
    return id;
  };
  const advance = (ms) => {
    const until = now + ms;
    for (;;) {
      const pending = [...tasks].filter(([, task]) => task.at <= until)
        .sort((a, b) => a[1].at - b[1].at || a[0] - b[0])[0];
      if (!pending) break;
      const [id, task] = pending;
      tasks.delete(id);
      now = task.at;
      task.fn(task.raf ? now : undefined);
    }
    now = until;
  };
  const emit = (name, event = {}) => {
    for (const fn of listeners.get(name) || []) fn(event);
  };
  class Element {
    closest() { return null; }
  }
  const body = new Element();
  const root = { dataset: {} };
  let documentTop = 50;
  const sections = ['top', 'glance', 's1', 'listen', 's3', 's4'].map((id) => {
    const top = documentTop;
    const height = id === 'glance' && tallResult ? 1400 : 1000;
    documentTop += height;
    return {
      id,
      getBoundingClientRect: () => ({ top: top - y, height, bottom: top + height - y }),
      querySelector: () => null,
    };
  });
  const sandbox = {
    window: {}, Element, URLSearchParams,
    document: { documentElement: root, body, querySelector: () => null },
    location: { search: '', hash: '' },
    history: { replaceState: (_state, _unused, hash) => arrivals.push(hash) },
    performance: { now: () => now }, innerHeight: 1050,
    matchMedia: () => ({ matches: true, addEventListener() {} }),
    getComputedStyle: () => ({ overflowX: 'visible', overflowY: 'visible' }),
    addEventListener: (name, fn) => listeners.set(name, [...(listeners.get(name) || []), fn]),
    requestAnimationFrame: (fn) => schedule(fn, 16, true),
    cancelAnimationFrame: (id) => tasks.delete(id),
    setTimeout: (fn, delay) => schedule(fn, delay),
    clearTimeout: (id) => tasks.delete(id),
    scrollTo: ({ top }) => {
      const next = Math.max(0, Math.min(top, documentTop - 1050));
      if (next === y) return;
      y = next;
      samples.push({ at: now, y });
      emit('scroll');
    },
  };
  Object.defineProperty(sandbox, 'scrollY', { get: () => y });
  vm.runInNewContext(source, sandbox, { filename: 'chapter-scroll.js' });
  const controller = sandbox.window.createChapterScroll({
    sections, navPx: () => 50, cancelScroll() {},
    enterStory() { enters++; autoPlaying = true; },
    leaveStory() { leaves++; autoPlaying = false; },
  });
  const wheel = (delta) => {
    const event = {
      target: body, deltaX: 0, deltaY: delta, deltaMode: 0,
      preventDefault() { this.defaultPrevented = true; },
    };
    emit('wheel', event);
    assert.equal(event.defaultPrevented, true, 'desktop wheel must be handled');
  };
  advance(16); // Initial layout activation.
  return {
    advance, wheel, controller, sections, root, samples, arrivals,
    jump: (top) => sandbox.scrollTo({ top }),
    get y() { return y; }, get enters() { return enters; },
    get leaves() { return leaves; }, get autoPlaying() { return autoPlaying; },
  };
}

function tailThroughTravel(h) {
  // Keep gaps below 180ms both during and after the page movement. A long
  // inertial tail must not be mistaken for another deliberate gesture.
  for (let i = 0; i < 40; i++) {
    h.advance(40);
    h.wheel(Math.max(1, 24 * .86 ** i));
  }
}

test('a continuous decaying tail finishes one chapter without queuing another', () => {
  const h = setup();
  h.wheel(120);
  tailThroughTravel(h);
  h.advance(200);
  assert.equal(h.y, 1000);
  assert.equal(h.root.dataset.chapterTransition, 'idle');
  assert.deepEqual(h.arrivals, ['#glance']);
  assert.equal(h.enters, 0);
  const traveling = h.samples.map((sample) => sample.y);
  assert.ok(new Set(traveling).size > 10, 'real scroll traverses intermediate positions');
  assert.ok(traveling.every((value, i) => i === 0 || value >= traveling[i - 1]));
});

test('a strong but continuously decaying tail is not a fresh impulse after arrival', () => {
  const h = setup();
  h.wheel(120);
  for (let i = 0; i < 40; i++) {
    h.advance(40);
    h.wheel(80 * .98 ** i);
  }
  h.advance(1500);
  assert.equal(h.y, 1000, 'magnitude alone must not rearm a still-decaying gesture');
  assert.deepEqual(h.arrivals, ['#glance']);
});

test('an intent reset during travel does not queue its remaining tail after arrival', () => {
  const h = setup();
  h.wheel(120);
  h.advance(250); // Another burst begins while the first transition is busy.
  for (let i = 0; i < 35; i++) {
    h.wheel(20 * .995 ** i);
    h.advance(40);
  }
  h.advance(1500);
  assert.equal(h.y, 1000, 'ignored input during travel must remain consumed afterward');
  assert.deepEqual(h.arrivals, ['#glance']);
});

test('a tall Result boundary permits immediate reversal without a quiet gap', () => {
  const h = setup({ tallResult: true });
  h.controller.go(h.sections[1]);
  h.advance(1500);
  h.wheel(1000);
  assert.equal(h.y, 1400, 'scroll the remaining Result content to its edge');
  h.advance(40);
  h.wheel(-80);
  assert.equal(h.y, 1320, 'reverse within the same gesture instead of remaining latched');
  h.advance(40);
  h.wheel(80);
  assert.equal(h.y, 1400, 'both directions remain available');
});

test('reversing after chapter travel works while the old tail is still arriving', () => {
  const h = setup();
  h.wheel(120);
  tailThroughTravel(h);
  assert.equal(h.y, 1000);
  h.advance(40);
  h.wheel(-120);
  assert.equal(h.root.dataset.chapterTransition, 'travel');
  h.advance(1500);
  assert.equal(h.y, 0);
  assert.deepEqual(h.arrivals, ['#glance', '#top']);
});

test('a fresh substantial impulse rearms without 180ms of silence', () => {
  const h = setup();
  h.wheel(120);
  tailThroughTravel(h);
  h.advance(40);
  h.wheel(120);
  assert.equal(h.root.dataset.chapterTransition, 'travel');
  h.advance(1500);
  assert.equal(h.y, 2000);
  assert.equal(h.enters, 1);
  assert.equal(h.autoPlaying, true);
});

test('spaced constant mouse-wheel pulses can advance without a long quiet gap', () => {
  const h = setup();
  h.wheel(120);
  for (let i = 0; i < 31; i++) {
    h.advance(80); // Mechanical wheel pulses, rather than a decaying trackpad tail.
    h.wheel(120);
  }
  h.advance(1500);
  assert.ok(h.y >= 2000, 'continued deliberate wheel input must not remain latched at Result');
  assert.equal(h.root.dataset.chapterTransition, 'idle');
  assert.ok(h.arrivals.includes('#s1'));
});

test('Watch autoplay cannot lock wheel navigation out of its chapter', () => {
  const h = setup();
  h.controller.go(h.sections[2]);
  h.advance(1500);
  assert.equal(h.enters, 1);
  assert.equal(h.autoPlaying, true, 'playback deliberately never completes in this harness');
  h.wheel(120);
  assert.equal(h.leaves, 1);
  h.advance(1500);
  assert.equal(h.y, 3000);
  assert.equal(h.root.dataset.chapterTransition, 'idle');
});

test('a Watch view offset before its anchor exits forward on the first gesture', () => {
  const h = setup();
  h.controller.go(h.sections[2]);
  h.advance(1500);
  h.jump(1940); // Browser focus/scrollIntoView leaves Watch 60px before its anchor.
  h.advance(20); // Interact before the controller's scrollbar-settle timer fires.
  h.wheel(120);
  h.advance(1500);
  assert.equal(h.y, 3000, 'the gesture must reach Listen, not merely realign Watch');
  assert.deepEqual(h.arrivals, ['#s1', '#listen']);
  assert.equal(h.enters, 1, 'the offset must not cause an accidental Watch re-entry');
  assert.equal(h.leaves, 1);
});

test('a Watch view offset before its anchor exits backward on the first gesture', () => {
  const h = setup();
  h.controller.go(h.sections[2]);
  h.advance(1500);
  h.jump(1940);
  h.advance(20);
  h.wheel(-120);
  h.advance(1500);
  assert.equal(h.y, 1000, 'the gesture must reach Result, not consume an alignment-only move');
  assert.deepEqual(h.arrivals, ['#s1', '#glance']);
  assert.equal(h.enters, 1);
  assert.equal(h.leaves, 1);
});

test('wheel navigation interrupts Watch alignment without replaying its conversation', () => {
  const h = setup();
  h.controller.go(h.sections[2]);
  h.advance(1500);
  h.jump(2275); // A focused chat control scrolls Watch below its intended anchor.
  h.advance(200);
  assert.equal(h.root.dataset.chapterTransition, 'settle');
  assert.equal(h.enters, 1);
  assert.equal(h.leaves, 0, 'aligning the same chapter must keep its playback running');
  h.wheel(120);
  assert.equal(h.root.dataset.chapterTransition, 'travel');
  h.advance(1500);
  assert.equal(h.y, 3000, 'one wheel gesture must cancel alignment and reach Listen');
  assert.equal(h.root.dataset.chapterTransition, 'idle');
  assert.equal(h.enters, 1);
  assert.equal(h.leaves, 1);
});

test('letting Watch alignment finish preserves the existing autoplay session', () => {
  const h = setup();
  h.controller.go(h.sections[2]);
  h.advance(1500);
  h.jump(2275);
  h.advance(200);
  assert.equal(h.root.dataset.chapterTransition, 'settle');
  h.advance(1500);
  assert.equal(h.y, 2000);
  assert.equal(h.root.dataset.chapterTransition, 'idle');
  assert.equal(h.enters, 1, 'alignment must not restart the conversation');
  assert.equal(h.leaves, 0);
  assert.equal(h.autoPlaying, true);
});

test('explicit navigation replaces an unfinished destination and releases busy state', () => {
  const h = setup();
  h.wheel(120);
  h.advance(300);
  assert.ok(h.y > 0 && h.y < 1000);
  h.controller.go(h.sections[5]);
  h.advance(1500);
  assert.equal(h.y, 5000);
  assert.equal(h.root.dataset.chapterTransition, 'idle');
  assert.deepEqual(h.arrivals, ['#s4'], 'the cancelled arrival callback must not run');
  h.wheel(-120);
  h.advance(1500);
  assert.equal(h.y, 4000, 'wheel navigation works after the replacement completes');
});
