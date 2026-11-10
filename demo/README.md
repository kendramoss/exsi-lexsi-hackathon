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

A static web page that replays saved model answers, in six screens, to show whether a model changes its answer for the right reason. There are no live model calls, and every number on screen is counted from the saved run.

**[▶ Open it online](https://kendramoss.github.io/exsi-lexsi-hackathon/demo/?run=final-fresh)** &nbsp;·&nbsp; [Step-by-step setup](../README.md#2-run-the-demo-on-your-computer) in the main README

## Contents

1. [The six screens](#1-the-six-screens)
2. [Run it](#2-run-it)
3. [Put it online](#3-put-it-online)
4. [Display scale](#4-display-scale)
5. [Options in the address](#5-options-in-the-address)
6. [Data](#6-data)
7. [Files](#7-files)

## 1. The six screens

Scroll, use the tabs at the top, or click the dots on the right. Each scroll moves one whole screen.

| # | Tab | What it shows |
|---|---|---|
| 1 | **Why** | The question: *Does the model change its answer for the right reason?* |
| 2 | **The result** | One wrong pushback, as two gauges: plain training switches to the wrong answer, EvidenceTune stays right. Across all 272 pushbacks that quote an excerpt that doesn't settle it, EvidenceTune asks for the source 208 times and plain training 80 (2.6× as often). |
| 3 | **Watch it** | The same case as a chat that plays itself, up to where the two models split. Plain training switches; EvidenceTune asks what text supports the change. ‹ › or ← → step through it. |
| 4 | **Under pressure** | What each model does with every wrong quote: kept its answer, asked for proof, or changed it. EvidenceTune asks for proof 76% of the time, up from 29%. |
| 5 | **The test** | *Is the test fair?* One case, its four pushbacks and the right move for each, plus three facts: unseen clause types, no word tricks, 544 pushbacks scored. |
| 6 | **See the work** | Links to the model, the test cases and the code, and **See all the numbers** for every score. |

## 2. Run it

```sh
cd demo
python -m http.server 8000
```

Then open **[localhost:8000/?run=final-fresh](http://localhost:8000/?run=final-fresh)**. Open it through `http://`; double-clicking `index.html` shows a blank page. If `python` isn't found, try `py` (Windows) or `python3` (Mac).

## 3. Put it online

| Host | How |
|---|---|
| **Hugging Face Space** | Create a **Static** Space and upload everything inside this folder. The front-matter at the top of this file is the Space's settings. |
| **GitHub Pages** | Already live at the link above, served from `main`. It republishes about a minute after each push. |
| **Netlify Drop** | Drag this folder onto [app.netlify.com/drop](https://app.netlify.com/drop). |

## 4. Display scale

The page was designed at 80% browser zoom, so on desktop (901px and wider) it scales itself to 80% and looks right at the browser's normal 100%. If it looks too small, the browser is zoomed out too: press **Ctrl + 0** (Mac: **Cmd + 0**).

For developers: viewport units in `style.css` are written as `var(--vh)` and `var(--vw)` so full-screen sections still fill the window, and breakpoints above 900px are 0.8× their design values. Phones aren't scaled.

## 5. Options in the address

| Add | What it does |
|---|---|
| `?run=final-fresh` | The default run: Mizore66's frozen final evaluation, 136 fresh NDA cases × 4 kinds of pushback, plain training (v5) vs EvidenceTune (v6). Imported by `scripts/import_final_run.py`. |
| `?run=mock-smoke` | An **invented** run for layout testing. A "Mock data" badge appears. Made by `scripts/make_mock_results.py`. |
| `&family=<family_id>` | Picks the example case on screens 2, 3 and 5. By default it's the first case where plain training gives in and EvidenceTune doesn't. |
| `&step=3` | Opens on screen 5. |
| `&instant` | Screen 4 shows both bars side by side instead of taking turns. |

With "reduce motion" turned on in system settings, every animation shows its still version.

## 6. Data

```
data/results/<run_id>/
  cases.jsonl        # schemas/case.schema.json
  predictions.jsonl  # schemas/run.schema.json
  metrics.json       # schemas/metrics.schema.json
```

A new run drops in as a new folder; check it first with `python scripts/validate.py demo/data/results/<run_id>`. The page needs:

- At least one case family with both a `valid_low_overlap` and an `unsupported_high_overlap` case.
- Predictions for the comparator (`safetune`) and a reference (`base` if present, otherwise another comparator).
- A `score` block on each prediction; the verdicts come from it.
- `metrics.json` comparators whose `id` values match the predictions' `policy` values.

`data/results/merged-alpha-075/merged.json` is the merged α=0.75 payload for Mizore66's merged-model demo (`build_merged_demo.py`, `merged-data.js`). It's a different format, and this page doesn't read it.

## 7. Files

| File | What it is |
|---|---|
| `index.html` | The six screens, the nav and the "All the numbers" dialog |
| `app.js` | Loads a run, builds every screen from it, and handles paging, tabs and the chat |
| `style.css` | All styling, including the 80% scale |
| `assets/` | Favicon, link-card previews and logo explorations |
| `data/results/` | Saved runs |
