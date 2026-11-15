# Continuous chapters and conversation autoplay

- [x] Branch from current main in an isolated worktree.
- [x] Move the real document continuously between desktop chapters.
- [x] Autoplay the five-stage recorded conversation with typing and reading pauses.
- [x] Preserve delivered message nodes and add Pause/Play, Replay, and manual steps.
- [x] Keep page navigation independent of playback and cancel timers on departure.
- [x] Fix momentum suppression, reversals, tall-content boundaries, and offset chapter detection.
- [x] Let wheel input interrupt automatic alignment without restarting playback.
- [x] Preserve native, mobile, short-window, and reduced-motion fallbacks.
- [x] Verify browser behavior and add targeted regression coverage.

## Validation

- 13 controller regressions and 13 recorded-data regressions pass (26 total).
- JavaScript syntax, Python regression-file compilation, and diff checks pass.
- Browser-checked complete autoplay with unchanged scroll position, both navigation directions, typing, pause/resume, replay, focus offsets, and mobile transcript layout.
- The Python browser suite was expanded but was not run in this session.
- Saved responses and scores are unchanged. Existing work in the original checkout remains untouched.
