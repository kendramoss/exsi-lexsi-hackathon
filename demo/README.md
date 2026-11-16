---
title: EvidenceTune
emoji: 🧾
colorFrom: indigo
colorTo: yellow
sdk: static
app_file: index.html
pinned: false
license: apache-2.0
short_description: When should a model accept a correction?
---

# EvidenceTune recorded release frontend

The default route showcases the selected **EvidenceTune merged α=0.75** adapter:
**75% v7 + 25% v8**. It reads `data/results/merged-alpha-075/merged.json`, validated
by its pinned payload, input, output, and adapter hashes. It does not run a model.

## Run locally

```sh
cd demo
python3 -m http.server 8000
```

Open [localhost:8000](http://localhost:8000/). The current development preview also
runs at [localhost:8877](http://localhost:8877/). Use HTTP rather than opening the
HTML file directly. No build or remote assets are needed: fonts and all evidence
used by the page are local.

## Evidence and routes

| Route | Evidence and purpose |
|---|---|
| `/` or `?run=merged-alpha-075` | Released merged adapter versus its v7 parent; exact paired recorded responses and separate frozen semantic/targeted scoreboards. |
| `?run=final-fresh` | Explicitly historical v5 plain training versus EvidenceTune v6, on that run's own 544 pushbacks. These are not merged-model outputs. |
| `?run=mock-smoke` | Explicitly invented layout-testing data; not model evidence. |
| `?condition=valid` | Default release condition. Also accepts `unsupported_toward`, `unsupported_away`, `pressure_away`, and `solo`. The condition selector changes both the comparison and story. |
| `?instant` | Static motion fallback and complete readable transcript. |
| `?step=3` | Direct navigation to the test explanation. Section hashes work too. |

The release replay bundles only two arms: `baseline_v7` and `merge_alpha_0.75`,
using local Apple MPS bf16 Transformers. The later post-selection raw-base
comparison is not bundled and is not added to this replay.

| Frozen task-contract metric | v7 parent | Merged α=0.75 |
|---|---:|---:|
| Semantic task success | 213/240 (88.75%) | 222/240 (92.50%) |
| Targeted task success | 247/270 (91.48%) | 253/270 (93.70%) |
| Semantic all-five-condition case success | 29/48 (60.42%) | 35/48 (72.92%) |
| Targeted all-five-condition case success | 40/54 (74.07%) | 43/54 (79.63%) |

Task success includes output-format, action, and working-answer contract checks;
it is not general accuracy. Five rows from one case are correlated. Semantic and
targeted suites, dev selection, frozen confirmation, and conditional resolution
are separate analyses. The default frontend shows the frozen tables; it links to
the model card for the other analyses rather than inventing missing denominators.

The illustration is the first case in saved semantic frozen-test order,
`sc-01-25`, with all five conditions in saved order. **Both models pass all five
illustrated rows.** Their exact raw responses differ, but the example is not a
baseline-fails/merged-wins demonstration. Supplied prior answers are task context,
not generated assistant turns. No clarification follow-up dialogue is bundled.

Scope: contract-v2 synthetic construction-proxy evaluation; no independent human
sufficiency annotation, human validation, or broad natural-domain evidence.
The modal exposes frozen denominators, exact selected input, hashes, selection
scope, and source-artifact references. Raw prediction files are retained outside
the static demo, not silently substituted or regenerated.

Adapter SHA-256:
`a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335`.
See [the model card](https://huggingface.co/Mizore66/evidencetune-merged-alpha-0.75),
[the public recorded release demo](https://mizore66-evidencetune-merged-demo.static.hf.space/index.html),
and [the evidence contract](../MERGED-DEMO.md).

## Presentation

The PR #37 presentation is preserved: self-hosted Instrument Sans headings and
IBM Plex Sans body text, cobalt/cream panels, textual comparisons, and native
continuous document scrolling. Wheel events are never prevented or converted
into section jumps. Explicit section links and story step controls may animate
to their target positions and are interruptible by native input.

Desktop readers scroll through the selected saved input and outputs, in either
direction. Mobile, short windows, reduced motion, and `?instant` show the complete
selected-condition transcript with page scrolling and no clipped inner scroller.
The five conditions are independent recorded rows, not successive dialogue turns.

## Verification

```sh
node --test demo/tests/merged-data.test.cjs demo/tests/check-merged-page.test.cjs
node demo/tests/check-merged-page.mjs
node --test demo/tests/check-release-page.test.cjs
node demo/tests/check-historical-page.mjs
python3 demo/tests/check-scroll-story.py
python3 -m unittest discover -s demo/tests -p test_merged_demo.py -v
```

Run these from the repository root (the command paths above include `demo/`).
Playwright suites require an existing Playwright installation and Chromium;
`CHROME_BIN` can select a local compatible executable. `NODE_PATH` can select an
existing Node Playwright installation. `REQUIRE_MERGED_BROWSER=1` makes the merged
payload checker require the actual browser suite as well. Raw-evidence Python
checks additionally use `EVTUNE_DEMO_RAW_ROOT`; see the evidence contract. Pure
payload tests do not require model weights or generation.

## Files

| File | Responsibility |
|---|---|
| `index.html` | Shared release shell and hidden historical template, selected only by explicit run routes. |
| `merged-app.js` | Hash-checked release loading, release narrative, frozen tables, native navigation, and reversible story. |
| `merged-data.js` | Existing recorded-payload adapter and separate frozen-suite metric mappings. |
| `app.js` | PR #37 historical/invented run rendering with explicit route disclosures. |
| `style.css` | PR #37 base design, fonts, responsive layout, and 80% desktop scale. |
| `merged-style.css` | Scoped content-layout adaptations for exact raw text, source disclosures, and frozen scoreboards. |
| `data/results/` | Unchanged recorded/invented evidence, separated by run. |

Publication is a separate action. This integration does not change hosting or deployment settings.
