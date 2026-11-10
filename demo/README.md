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

# EvidenceTune demo

A static web page that replays saved model answers. It shows, in six screens, whether a model changes its answer for the right reason: when a pushback quotes the part of the document that settles the question, and not when it quotes something that settles nothing. There are no live model calls, and the page recomputes no metrics: every number on screen is counted from the saved run.

**[Open it online →](https://kendramoss.github.io/exsi-lexsi-hackathon/demo/?run=final-fresh)** · New to running it yourself? The [step-by-step guide](../README.md#run-the-demo-on-your-computer) in the main README walks through it.

## The six screens

Scroll, use the tabs at the top, or click the dots on the right. Each scroll moves one whole screen.

| # | Tab | What it shows |
|---|---|---|
| 1 | **Why** | The question: *Does the model change its answer for the right reason?* |
| 2 | **The result** | One wrong pushback on one case, as two gauges: plain training switches to the wrong answer, EvidenceTune stays on the right one. Below them, across all 272 pushbacks that quote an excerpt that doesn't settle it: EvidenceTune asks for the source 208 times, plain training 80 times (2.6× as often). |
| 3 | **Watch it** | The same case as a chat that plays itself: the question with the contract attached, the first answer, the wrong pushback (its quoted excerpt highlighted), then the two models split. Plain training switches; EvidenceTune asks what text supports the change. ‹ › or ← → step through it. |
| 4 | **Under pressure** | What each model does with every wrong quote, as one stacked bar each: kept its answer, asked for proof, changed its answer. EvidenceTune asks for proof 76% of the time, up from 29%. Real quote cards drift along the side margins, stamped with what each model did. |
| 5 | **The test** | *Is the test fair?* One case and its four pushbacks (right excerpt, two kinds of wrong excerpt, pressure with no excerpt), what the model should do for each, and three facts: new clause types never seen in training, no word tricks, 544 pushbacks scored. |
| 6 | **See the work** | Links to the model, the test cases and the code, and **See all the numbers**: every score for every model, with what each score measures in its tooltip. |

## Run it on your computer

```sh
cd demo
python -m http.server 8000
# then open http://localhost:8000/?run=final-fresh
```

It has to be opened through `http://`. Opening `index.html` as a file shows a blank page, because browsers block the data files that way. If `python` isn't found, try `py` (Windows) or `python3` (Mac).

## Put it online

The folder is a plain static site, so any static host works:

- **Hugging Face Space:** the front-matter at the top of this file is the Space's settings. Create a **Static** Space and upload everything inside this folder.
- **GitHub Pages:** this repo already serves it at the link above, from `main`. It republishes about a minute after each push.
- **Netlify Drop:** drag this folder onto [app.netlify.com/drop](https://app.netlify.com/drop).

The main README has [click-by-click steps](../README.md#host-your-own-copy) for each.

## Display scale

The page was designed at 80% browser zoom, so on desktop (901px and wider) it scales itself to 80% and looks right at the browser's normal 100%. Viewport units in `style.css` are written as `var(--vh)` / `var(--vw)` so full-screen sections still fill the window, and breakpoints above 900px are 0.8× their design values. Phones aren't scaled. If the page looks too small, the browser is probably zoomed out too: press **Ctrl + 0** (or **Cmd + 0**).

## Options in the address

| Add to the address | What it does |
|---|---|
| `?run=final-fresh` | The run to show (the default). Mizore66's frozen final evaluation: 136 fresh NDA cases × 4 kinds of pushback, plain training (v5) vs EvidenceTune (v6), imported by `scripts/import_final_run.py`. |
| `?run=mock-smoke` | An **invented** example run, for layout testing only. A "Mock data" badge appears. Made by `scripts/make_mock_results.py`. |
| `&family=<family_id>` | Picks the example case on screens 2, 3 and 5. The default is the first case where plain training gives in to the wrong pushback and EvidenceTune doesn't. |
| `&step=3` | Opens straight on screen 5. |
| `&instant` | Screen 4 shows both bars side by side instead of taking turns. |

People who turn on "reduce motion" in their system settings get the still version of every animation.

## Data

```
data/results/<run_id>/
  cases.jsonl        # schemas/case.schema.json
  predictions.jsonl  # schemas/run.schema.json
  metrics.json       # schemas/metrics.schema.json
```

A new run drops in as a new folder. Check it first with `python scripts/validate.py demo/data/results/<run_id>`.

What the page needs from a run:

- At least one case family with both a `valid_low_overlap` and an `unsupported_high_overlap` case.
- Predictions for two policies: the comparator (`safetune`) and a reference (`base` if present, otherwise another comparator).
- A `score` block on each prediction; the verdicts come from it.
- `metrics.json` comparators whose `id` values match the predictions' `policy` values.

`data/results/merged-alpha-075/merged.json` is the merged α=0.75 payload used by Mizore66's merged-model demo (`build_merged_demo.py`, `merged-data.js`). It is a different shape and this page doesn't read it.

## Files

| File | What it is |
|---|---|
| `index.html` | The six screens' markup, the nav and the "All the numbers" dialog |
| `app.js` | Loads a run, builds every screen from it, and handles paging, tabs and the chat |
| `style.css` | All styling |
| `assets/` | Favicon, link-card previews and logo explorations |
| `data/results/` | Saved runs |
