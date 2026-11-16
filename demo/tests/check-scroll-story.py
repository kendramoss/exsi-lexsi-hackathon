"""Playwright regressions for the approved native-scroll EvidenceTune walkthrough.

Run with an environment containing playwright and its chromium-headless-shell
browser (or set CHROME_BIN to an allowed test browser). Uses a temporary local
server, real wheel/keyboard events, and the unchanged recorded run payloads.
"""
import functools
import http.server
import json
import os
from pathlib import Path
import re
import threading
import unittest

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
SHOTS = Path(os.environ.get('EVTUNE_STORY_SCREENSHOTS', '/tmp/evidencetune-scroll-story'))


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class ScrollStoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        SHOTS.mkdir(parents=True, exist_ok=True)
        cls.server = http.server.ThreadingHTTPServer(
            ('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT)))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = f'http://127.0.0.1:{cls.server.server_port}'
        cls.pw = sync_playwright().start()

    @classmethod
    def tearDownClass(cls):
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        options = {'headless': True, 'args': ['--disable-gpu']}
        if os.environ.get('CHROME_BIN'):
            options['executable_path'] = os.environ['CHROME_BIN']
        self.browser = self.pw.chromium.launch(**options)
        self.context = self.browser.new_context(viewport={'width': 1440, 'height': 1000}, color_scheme='light')
        self.context.set_default_timeout(6000)
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))

    def tearDown(self):
        if self.browser.is_connected():
            self.browser.close()

    def load(self, run='final-fresh'):
        self.page.goto(f'{self.origin}/?run={run}', wait_until='networkidle')
        self.page.wait_for_selector('#setup .row')
        self.page.evaluate('document.fonts.ready')

    def position(self, section):
        return self.page.eval_on_selector(section, '(s) => s.getBoundingClientRect().top + scrollY - document.querySelector(".top").getBoundingClientRect().height')

    def jump(self, y):
        self.page.evaluate('(y) => window.scrollTo({top:y, behavior:"instant"})', y)
        self.page.wait_for_timeout(100)  # Observe the next scroll/rAF commit, not app readiness.

    def active(self):
        return self.page.locator('#steps a[aria-current]').get_attribute('data-sec')

    def chat_step(self):
        return int(re.search(r'Step (\d)', self.page.locator('#convo-step').inner_text()).group(1))

    def test_chosen_fonts_really_load_from_local_files(self):
        self.load()
        faces = self.page.evaluate('''async () => ({
            display: (await document.fonts.load('400 36px "Instrument Sans"')).length,
            body: (await document.fonts.load('400 16px "IBM Plex Sans"')).length,
            family: getComputedStyle(document.body).fontFamily,
            heading: getComputedStyle(document.querySelector('h1')).fontFamily
        })''')
        self.assertGreater(faces['display'], 0)
        self.assertGreater(faces['body'], 0)
        self.assertIn('IBM Plex Sans', faces['family'])
        self.assertIn('Instrument Sans', faces['heading'])

    def test_small_wheel_does_not_jump_a_whole_screen(self):
        self.load()
        self.page.mouse.move(400, 500)
        self.page.mouse.wheel(0, 45)
        self.page.wait_for_timeout(900)  # Observe settled browser wheel movement.
        y = self.page.evaluate('scrollY')
        self.assertGreater(y, 0)
        self.assertLess(y, 130, '45px wheel gesture must not become a screen-sized jump')
        self.assertEqual(self.active(), 'top')

    def test_trackpad_tail_does_not_queue_section_jumps(self):
        self.load()
        self.page.mouse.move(400, 500)
        for dy in (24, 18, 12, 8, 5, 3, 1):
            self.page.mouse.wheel(0, dy)
            self.page.wait_for_timeout(24)
        self.page.wait_for_timeout(1000)
        self.assertLess(self.page.evaluate('scrollY'), 180)
        self.assertEqual(self.active(), 'top')
        opacity = self.page.locator('#glance').evaluate('(s) => Number(getComputedStyle(s).opacity)')
        self.assertEqual(opacity, 1, 'entering sections must not flash from dim to opaque')

    def test_result_uses_exact_saved_responses_instead_of_gauges(self):
        for run in ('final-fresh', 'mock-smoke'):
            self.load(run)
            expect(self.page.locator('#hero-vis .answer-result')).to_have_count(2)
            self.assertEqual(self.page.locator('#hero-vis svg.clock').count(), 0)
            case_id = self.page.locator('#hero-vis').get_attribute('data-case')
            records = [json.loads(s) for s in (ROOT / 'data/results' / run / 'predictions.jsonl').read_text().splitlines() if s.strip()]
            for result in self.page.locator('#hero-vis .answer-result').all():
                policy = result.get_attribute('data-policy')
                saved = next(r for r in records if r['case_id'] == case_id and r['policy'] == policy)
                self.assertEqual(result.locator('[data-role="final-answer"]').inner_text(), str(saved['final_answer']))
                expected = ' '.join(s for s in saved['raw_output'].splitlines() if not re.match(r'^\s*(ACTION|ANSWER)\s*:', s, re.I)).strip() or saved['raw_output']
                self.assertEqual(result.locator('.result-response').inner_text(), expected)
            self.assertFalse(self.errors)

    def test_scrolling_walks_each_chat_stage_before_next_section(self):
        self.load()
        span = self.page.locator('#s1').evaluate('(s) => s.getBoundingClientRect().height')
        self.assertGreater(span, 3000, 'desktop chat needs a real scroll runway, not a wheel lock')
        self.jump(self.position('#s1') + 1)
        self.assertEqual(self.chat_step(), 1)
        self.page.wait_for_timeout(3300)
        self.assertEqual(self.chat_step(), 1, 'the journey must follow the reader, not an autoplay timer')
        self.page.mouse.move(350, 600)
        self.page.mouse.wheel(0, 120)
        self.page.wait_for_timeout(200)
        self.assertEqual(self.active(), 's1')
        seen = {self.chat_step()}
        for _ in range(20):
            self.page.mouse.wheel(0, 250)
            self.page.wait_for_timeout(90)
            seen.add(self.chat_step())
            if self.active() == 'listen':
                break
        self.assertEqual(seen, {1, 2, 3, 4, 5})
        self.assertEqual(self.active(), 'listen')
        self.page.screenshot(path=str(SHOTS / '04-after-complete-journey.png'))

    def test_story_is_pinned_and_reversible(self):
        self.load()
        start = self.position('#s1')
        expect(self.page.locator('#s1 .story-stage')).to_have_count(1)
        self.jump(start + 800)
        top_a = self.page.locator('.story-stage').bounding_box()['y']
        n = self.chat_step()
        self.assertGreater(n, 1)
        self.jump(start + 2200)
        top_b = self.page.locator('.story-stage').bounding_box()['y']
        self.assertAlmostEqual(top_a, top_b, delta=3)
        self.assertGreater(self.chat_step(), n)
        self.jump(start + 50)
        self.assertEqual(self.chat_step(), 1)
        self.assertEqual(self.active(), 's1')

    def test_controls_and_direct_navigation_are_not_scroll_traps(self):
        self.load()
        self.jump(self.position('#s1') + 1)
        self.page.locator('#convo-next').click()
        self.page.wait_for_function('document.querySelector("#convo-step").textContent.includes("Step 2")')
        self.page.evaluate('document.activeElement.blur()')  # Global arrows apply outside native controls.
        self.page.keyboard.press('ArrowRight')
        self.page.wait_for_function('document.querySelector("#convo-step").textContent.includes("Step 3")')
        self.page.locator('#steps a[data-sec="s4"]').click()
        self.page.wait_for_function('document.querySelector("#steps a[aria-current]")?.dataset.sec === "s4"')
        self.page.locator('#open-all').click()
        expect(self.page.locator('#all-dialog')).to_be_visible()
        self.page.keyboard.press('Escape')
        expect(self.page.locator('#all-dialog')).not_to_be_visible()

    def test_reduced_motion_and_mobile_show_complete_readable_transcript(self):
        for viewport, reduced in (({'width': 1440, 'height': 1000}, 'reduce'), ({'width': 390, 'height': 844}, 'no-preference')):
            self.page.set_viewport_size(viewport)
            self.page.emulate_media(reduced_motion=reduced)
            self.load()
            story = self.page.locator('#s1')
            self.assertFalse(story.evaluate('(s) => s.classList.contains("is-scroll-story")'))
            self.assertEqual(self.chat_step(), 5)
            self.assertEqual(self.page.locator('#convo .branch').count(), 2)
            for selector in ('#convo .file', '#convo .push', '#convo .branch.base', '#convo .branch.tuned'):
                self.page.locator(selector).scroll_into_view_if_needed()
                expect(self.page.locator(selector)).to_be_visible()
            self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), viewport['width'])
            self.page.screenshot(path=str(SHOTS / ('reduced-motion.png' if reduced == 'reduce' else 'mobile-transcript.png')), full_page=True)
            self.assertFalse(self.errors)


if __name__ == '__main__':
    unittest.main(verbosity=2)
