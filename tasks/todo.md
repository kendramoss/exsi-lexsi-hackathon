# Released merged-model evidence integration

- [x] Inspect repository state, payload schema, adapter/tests, README, model card, and public recorded demo.
- [x] Verify source-file availability and hashes without changing or regenerating recorded evidence.
- [x] Add and demonstrate failing tests for the merged default and evidence boundaries.
- [x] Restore PR #37 native continuous scrolling and reversible desktop story; retain readable mobile/reduced-motion transcripts.
- [x] Integrate the merged payload throughout the default narrative, outputs, frozen results, modal, links, and provenance.
- [x] Keep explicit historical final-fresh and invented mock-smoke routes.
- [x] Show an early localhost preview and screenshots.
- [x] Run payload/adapter tests, existing historical checks, and actual Playwright browser regressions.
- [x] Report exact comparisons/sources, limitations, and file availability; leave all changes uncommitted.

## Evidence boundaries

- Two bundled arms: baseline_v7 and merge_alpha_0.75, on local Apple MPS bf16 Transformers.
- Semantic frozen: 213/240 vs 222/240 task success; 29/48 vs 35/48 all-five success.
- Targeted frozen: 247/270 vs 253/270 task success; 40/54 vs 43/54 all-five success.
- All five illustrated rows from sc-01-25 pass for both arms. No invented divergence, earlier generated answer, or clarification follow-up.
- Supplied prior answers are task context, not saved assistant dialogue. Working-answer contract success is not general factual accuracy.
- Referenced source evidence exists in the configured external evidence root with matching pinned hashes; no required evidence is missing.
- No inference, training, teacher calls, paid services, or deployment-setting changes. The user subsequently approved committing and merging the validated integration.

## Final verification

- RED observed first: default Playwright request assertion and static renderer-wiring assertion failed before implementation.
- GREEN: 14 Node payload/wiring/tampering tests; 10 actual Playwright release tests; 8 PR #37 native-scroll browser tests; 9 historical CDP regression groups; 6 Python payload/raw-source tests.
- Actual Playwright used the existing cached Chromium headless shell. The installed Chrome.app had a platform GPU/display-link disconnect; the stable cached executable passed all affected tests without a browser download.
- Browser screenshots cover release hero, exact responses, desktop story, frozen modal, full mobile transcript, and reduced-motion transcript. A 1280×720 final-story check confirmed both raw outputs and task evaluations fit in the panel with no horizontal overflow.
- The bundled payload remains byte-identical to the root payload and public recorded demo (SHA-256 6e98f3d5e1980e667484602dc3ae2690e46cc8ac1df14b552b67a76572202ad7).
- All eight referenced source artifacts and the adapter exist under /Users/anasqumhiyeh/lexsi-koth/evtune with matching hashes. No required evidence files were missing; none were regenerated.
- Local preview: http://127.0.0.1:8877/. Explicit historical and mock routes remain available. No hosting settings or recorded data were changed.
- Implementation was validated on codex/merged-release-frontend before commit/merge approval. Recorded evidence and hosting settings are unchanged; no inference occurred.

## Approved commit and merge identity

The user approved commit and merge after reviewing the localhost integration. Use Mizore66 and 123628501+Mizore66@users.noreply.github.com for BOTH author and committer, including the merge commit.
