// Desktop chapter navigation moves the real document continuously.
// Conversation playback is independent; page gestures always navigate chapters.
(() => {
  "use strict";

  window.createChapterScroll = ({ sections, navPx, enterStory, leaveStory, cancelScroll }) => {
    const root = document.documentElement;
    const media = matchMedia("(min-width: 901px) and (min-height: 641px) and (pointer: fine) and (prefers-reduced-motion: no-preference)");
    const params = new URLSearchParams(location.search);
    const allowed = !params.has("instant") && params.get("scroll") !== "native";
    const enabled = () => allowed && media.matches;
    const GESTURE_GAP = 180, THRESHOLD = 34;
    let busy = false, frame = 0, lastWheel = -Infinity, lastMagnitude = 0;
    let consumed = false, distance = 0, direction = 0, settleTimer = 0;
    let rearmAt = 0, boundaryUntil = 0, settledSection = null, pendingDirection = 0;

    const topOf = (section) => Math.max(0, section.getBoundingClientRect().top + scrollY - navPx());
    const sceneHeight = () => innerHeight - navPx();
    const bottomOf = (section) => {
      const overflow = section.getBoundingClientRect().height - sceneHeight();
      return topOf(section) + (overflow > 24 ? overflow : 0);
    };
    const currentIndex = () => {
      // Focus, browser hash margins, and scrollbar movement can leave a chapter
      // a few pixels away from its exact anchor. Navigate the visible chapter,
      // rather than misclassifying it as the previous one until its top crosses.
      const middle = navPx() + sceneHeight() / 2;
      const index = sections.findIndex((section) => {
        const rect = section.getBoundingClientRect();
        return rect.top <= middle && rect.top + rect.height > middle;
      });
      return index < 0 ? 0 : index;
    };
    const scroll = (y) => scrollTo({ top: y, behavior: "instant" });
    const activate = (section) => {
      if (section === settledSection) return;
      if (settledSection?.id === "s1") leaveStory();
      settledSection = section;
      if (section.id === "s1") enterStory();
    };
    const clearMotion = () => {
      cancelAnimationFrame(frame);
      frame = 0;
      busy = false;
      root.dataset.chapterTransition = "idle";
    };
    const ease = (t) => t < .5 ? 16 * t ** 5 : 1 - (-2 * t + 2) ** 5 / 2;
    function move(y, duration, done, phase = "travel") {
      cancelScroll();
      clearTimeout(settleTimer);
      busy = true;
      root.dataset.chapterTransition = phase;
      const from = scrollY, start = performance.now();
      const tick = (now) => {
        const t = Math.min(1, (now - start) / duration);
        scroll(from + (y - from) * ease(t));
        if (t < 1) frame = requestAnimationFrame(tick);
        else {
          scroll(y);
          clearMotion();
          rearmAt = now + 100;
          done();
        }
      };
      frame = requestAnimationFrame(tick);
    }
    const focusSection = (section) => {
      const heading = section.querySelector("h1, h2");
      if (!heading) return;
      heading.setAttribute("tabindex", "-1");
      heading.focus({ preventScroll: true });
      heading.addEventListener("blur", () => heading.removeAttribute("tabindex"), { once: true });
    };

    function go(section, { focus = false, position = topOf(section), settling = false } = {}) {
      if (!enabled() || !sections.includes(section)) return false;
      // An explicit navigation link may change the destination mid-transition.
      if (busy) clearMotion();
      const arrive = () => {
        activate(section);
        history.replaceState(null, "", `#${section.id}`);
        if (focus) focusSection(section);
      };
      if (Math.abs(position - scrollY) < 3) { arrive(); return true; }
      consumed = true;
      if (settledSection?.id === "s1" && section !== settledSection) { leaveStory(); settledSection = null; }
      const duration = Math.min(1400, 1000 + Math.abs(position - scrollY) * .055);
      move(position, duration, arrive, settling ? "settle" : "travel");
      return true;
    }

    function advance(dir, { focus = false } = {}) {
      if (busy) return false;
      const index = currentIndex(), section = sections[index];
      const limit = dir > 0 ? bottomOf(section) : topOf(section);
      if (bottomOf(section) - topOf(section) > 24 && dir * (limit - scrollY) > 3) {
        return go(section, { focus, position: scrollY + dir * Math.min(sceneHeight() * .8, Math.abs(limit - scrollY)) });
      }
      const next = sections[index + dir];
      return next ? go(next, { focus }) : false;
    }

    const editable = (target) => target instanceof Element && target.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="textbox"], [role="slider"]');
    const nestedScroller = (target, dx, dy) => {
      for (let node = target instanceof Element ? target : null; node && node !== document.body; node = node.parentElement) {
        const css = getComputedStyle(node);
        if (Math.abs(dx) > Math.abs(dy) && /(auto|scroll)/.test(css.overflowX) && node.scrollWidth > node.clientWidth) return true;
        if (/(auto|scroll)/.test(css.overflowY) && node.scrollHeight > node.clientHeight + 2 &&
            (dy > 0 ? node.scrollTop + node.clientHeight < node.scrollHeight - 2 : node.scrollTop > 2)) return true;
      }
      return false;
    };

    addEventListener("wheel", (event) => {
      if (!enabled() || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey ||
          document.querySelector("dialog[open]") || editable(event.target) ||
          Math.abs(event.deltaX) > Math.abs(event.deltaY) || !event.deltaY || nestedScroller(event.target, event.deltaX, event.deltaY)) return;
      event.preventDefault();
      clearTimeout(settleTimer);
      // Browser focus/Find can start a gentle alignment. User input takes
      // priority over that correction, so it never creates an invisible lock.
      if (busy && root.dataset.chapterTransition === "settle") {
        clearMotion(); consumed = false; distance = 0;
      }
      const now = performance.now();
      const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? sceneHeight() : 1);
      const magnitude = Math.abs(delta), dir = Math.sign(delta);
      const reversed = direction !== 0 && dir !== direction;
      const gap = now - lastWheel;
      const freshImpulse = now >= rearmAt && (
        (magnitude >= 12 && magnitude > lastMagnitude * 1.6) ||
        (magnitude >= THRESHOLD && gap >= 65 && magnitude >= lastMagnitude)
      );
      // Inspect intent BEFORE suppression. Tiny inertial tails stay suppressed,
      // but a reversal or a fresh impulse can never leave the page latched shut.
      if (gap > GESTURE_GAP || reversed || (!busy && pendingDirection === dir) || (!busy && consumed && freshImpulse)) {
        consumed = false; distance = 0;
      }
      lastWheel = now;
      lastMagnitude = magnitude;
      direction = dir;
      if (busy) {
        if (reversed) pendingDirection = dir;
        consumed = true;
        distance = 0;
        return;
      }
      pendingDirection = 0;
      if (consumed) return;
      const section = sections[currentIndex()];
      const limit = dir > 0 ? bottomOf(section) : topOf(section);
      if (bottomOf(section) - topOf(section) > 24 && dir * (limit - scrollY) > 3) {
        const next = scrollY + dir * Math.min(magnitude, Math.abs(limit - scrollY));
        scroll(next);
        distance = 0;
        // Reaching a tall section's edge is not a consumed chapter gesture.
        // A brief boundary pause avoids a tail-driven jump but permits reversal.
        if (Math.abs(next - limit) < 3) boundaryUntil = now + 100;
        return;
      }
      if (!reversed && now < boundaryUntil) return;
      distance += magnitude;
      if (distance < THRESHOLD) return;
      distance = 0;
      if (advance(dir)) consumed = true;
    }, { passive: false });

    addEventListener("keydown", (event) => {
      if (!enabled() || event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey ||
          document.querySelector("dialog[open]") || editable(event.target) ||
          event.target.closest('button, a[href], summary, [role="button"], [role="tab"]')) return;
      const dir = { ArrowDown: 1, ArrowUp: -1, PageDown: 1, PageUp: -1, " ": event.shiftKey ? -1 : 1 }[event.key];
      if (!dir && !["Home", "End"].includes(event.key)) return;
      event.preventDefault();
      if (event.repeat || busy) return;
      if (dir) advance(dir, { focus: true });
      else go(event.key === "Home" ? sections[0] : sections.at(-1), { focus: true });
    });

    addEventListener("scroll", () => {
      clearTimeout(settleTimer);
      if (!enabled() || busy) return;
      settleTimer = setTimeout(() => {
        if (busy || document.querySelector("dialog[open]")) return;
        const section = sections[currentIndex()], top = topOf(section), bottom = bottomOf(section);
        if (scrollY >= top - 3 && scrollY <= bottom + 3) { activate(section); return; }
        go(section, { position: scrollY < top ? top : bottom, settling: true });
      }, GESTURE_GAP);
    }, { passive: true });

    const layout = () => {
      clearTimeout(settleTimer);
      clearMotion();
      cancelScroll();
      consumed = false; distance = 0; direction = 0;
      lastWheel = -Infinity; boundaryUntil = 0; pendingDirection = 0;
      root.dataset.chapterScroll = enabled() ? "on" : "native";
      if (!enabled()) {
        if (settledSection?.id === "s1") leaveStory();
        settledSection = null;
      } else requestAnimationFrame(() => { if (!busy && enabled()) activate(sections[currentIndex()]); });
    };
    media.addEventListener("change", layout);
    addEventListener("resize", layout);
    layout();
    const initialTarget = sections.find((section) => `#${section.id}` === location.hash);
    if (initialTarget) document.fonts.ready.then(() => requestAnimationFrame(() => {
      if (enabled() && !busy && location.hash === `#${initialTarget.id}`) {
        scroll(topOf(initialTarget));
        activate(initialTarget);
      }
    }));
    return { get active() { return enabled(); }, go };
  };
})();
