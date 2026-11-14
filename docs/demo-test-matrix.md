# Demo test matrix

What each demo check covers, and what it does not. Node 22 and, for the browser suite, a local Chrome (`CHROME_BIN` overrides the macOS default path). Set `TMPDIR` to a scratch directory. No network, no installs.

## Two payloads, two responsibilities

| | Historical run | Merged alpha=0.75 payload |
|---|---|---|
| Data | `demo/data/results/final-fresh` | `demo/data/results/merged-alpha-075/merged.json` |
| Shown by `demo/index.html` | Yes, the default route | No. The page does not read it (see `demo/README.md`) |
| Browser check | `demo/tests/check-historical-page.mjs` | None. No standalone merged renderer exists in this repository |
| Data check | `scripts/validate.py` | `demo/tests/check-merged-page.mjs`, `merged-data.test.cjs`, `test_merged_demo.py` |

## Commands

Run from the repository root.

| Command | Covers | Exit |
|---|---|---|
| `node demo/tests/check-historical-page.mjs` | Shipped page in Chrome: nine groups, including phone layout, keyboard handling, and mock-run isolation | 0 pass, non-zero fail |
| `node demo/tests/check-merged-page.mjs` | Merged payload: pinned payload sha256, adapter/selection/frozen-summary hashes, input and raw-output hashes, labels, exact score counts and denominators, claim limits, `merged-data.js` mapping, and a check that the shipped page still does not read the payload | 0 data pass (browser check skipped, stated on stdout), 1 fail, 2 skip refused |
| `REQUIRE_MERGED_BROWSER=1 node demo/tests/check-merged-page.mjs` | Same, but a skipped browser check is not accepted | 2 until a merged renderer and browser check exist |
| `node --test demo/tests/check-merged-page.test.cjs` | The script itself: passes on the real tree, reports the skip, and fails on each of eight tampered copies (output, score, label, provenance hash, claim scope, renderer premise, missing payload) | 0 pass |
| `node --test demo/tests/merged-data.test.cjs` | `merged-data.js` mapping and validation | 0 pass |
| `python -I -B -m unittest discover -s demo/tests -v` | Payload build and verification, including tamper rejection | 0 pass |

## Skipped on purpose

Rendering the merged payload in a browser is skipped, and the script says so on every run. It is not counted as passed. The earlier version of this script expected a "Recorded only" badge and a five-condition inspector in `demo/index.html`; the page deliberately no longer has them.

If a page ever loads `merged-data.js` or the merged payload, the premise check fails. That is the signal to restore a browser check for it, not to delete the premise check.
