# EvidenceTune

**Does a model change its answer for the right reason?** EvidenceTune teaches Tiny Aya Global to change its answer only when the evidence says so: it takes a correction that quotes the part of a document that settles the question, and asks for proof when the quote settles nothing.

**[▶ Open the demo](https://kendramoss.github.io/exsi-lexsi-hackathon/demo/?run=final-fresh)** &nbsp;·&nbsp; [Run it locally](#2-run-the-demo-on-your-computer) &nbsp;·&nbsp; [Model, data and code](#4-model-data-and-code) &nbsp;·&nbsp; [Results](#about-the-project)

Lexsi Hackathon, Track 2a #2 (safety benchmark) with Track 2b #5. Pipeline: CuratorKIT → SafeTune → AuditKIT.

## Contents

1. [Watch the demo](#1-watch-the-demo) · 1 click
2. [Run the demo on your computer](#2-run-the-demo-on-your-computer) · about 5 minutes
3. [Host your own copy](#3-host-your-own-copy) · about 10 minutes
4. [Model, data and code](#4-model-data-and-code)
5. [Reproduce the results](#5-reproduce-the-results)
6. [Troubleshooting](#6-troubleshooting)
7. [About the project](#about-the-project): the model, results, limits and documents

## 1. Watch the demo

**[Open the demo →](https://kendramoss.github.io/exsi-lexsi-hackathon/demo/?run=final-fresh)** Nothing to install; it works in any browser.

Scroll, or use the tabs at the top, to move through the six screens. The demo replays answers the model already gave during testing, so it doesn't run the model live and always shows the same results. An earlier version that replays the merged α=0.75 model is on [Hugging Face](https://mizore66-evidencetune-merged-demo.static.hf.space/index.html).

## 2. Run the demo on your computer

You only need **Python**, which most computers already have.

**Step 1 · Open a terminal**

| Windows | Mac |
|---|---|
| Press the **Windows key**, type `cmd`, press **Enter** | Press **Cmd + Space**, type `Terminal`, press **Enter** |

**Step 2 · Check Python**

```sh
python --version
```

Anything starting with `Python 3` works. If you get an error, try `py --version` (Windows) or `python3 --version` (Mac) and use that word instead of `python` below. If nothing works, install it from [python.org/downloads](https://www.python.org/downloads/); on Windows, tick **Add python.exe to PATH** in the installer.

**Step 3 · Download the project**

Click the green **`<> Code`** button at the top of this page, then **Download ZIP**, and unzip it (Windows: right-click → **Extract All**; Mac: double-click). You get a folder called `exsi-lexsi-hackathon-main`. With Git, you can run `git clone https://github.com/kendramoss/exsi-lexsi-hackathon.git` instead.

**Step 4 · Go into the `demo` folder**

| Windows | Mac |
|---|---|
| Open the `demo` folder, click the address bar, type `cmd`, press **Enter** | Right-click the `demo` folder → **New Terminal at Folder** |

Or type `cd` and the path, for example `cd Downloads/exsi-lexsi-hackathon-main/demo`.

**Step 5 · Start it**

```sh
python -m http.server 8000
```

Leave this window open, then go to **[localhost:8000/?run=final-fresh](http://localhost:8000/?run=final-fresh)** in your browser.

**Step 6 · Stop it** by pressing **Ctrl + C** in the terminal.

## 3. Host your own copy

The `demo` folder is a plain website with no server code, so any free static host can serve it.

| Host | Steps |
|---|---|
| **Hugging Face Space** (recommended) | Go to [huggingface.co/new-space](https://huggingface.co/new-space), choose the **Static** SDK, create it, then **Files → Add file → Upload files** and drop in everything *inside* `demo`. The Space settings are already in `demo/README.md`. |
| **Netlify Drop** | Drag the `demo` folder onto [app.netlify.com/drop](https://app.netlify.com/drop). You get a link in seconds; no account needed to try. |
| **GitHub Pages** | **Fork** this repo, then **Settings → Pages → Deploy from a branch → `main`, `/ (root)` → Save**. It goes live at `https://<you>.github.io/exsi-lexsi-hackathon/demo/`. |

Whichever you use, open the demo through its web address. Double-clicking `index.html` shows a blank page.

## 4. Model, data and code

| What | Link |
|---|---|
| The model | [Merged α=0.75 adapter](https://huggingface.co/Mizore66/evidencetune-merged-alpha-0.75) |
| The test cases and evidence | [Merged model data and evidence](https://huggingface.co/datasets/Mizore66/evidencetune-merged-data-alpha-0.75) |
| Everything together | [Hugging Face collection](https://huggingface.co/collections/Mizore66/evidencetune-merged-alpha-075-6af247b1e0ea2081369d1b08) |
| The write-up | [Submission draft](SUBMISSION-DRAFT.md) · [Full write-up](WRITEUP.md) |
| The code | This repository: training, scoring and analysis, plus the demo in [`demo/`](demo/) |

## 5. Reproduce the results

For a deeper check, if you're comfortable with Python and a terminal:

- [Release tooling](release/README.md) builds and verifies the release package.
- The [reproduction guide](release/REPRODUCE.md) verifies the adapter, replays selection and the frozen metrics from saved records, and rebuilds the demo data. Its commands use the author's own folder paths; swap in yours.

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| `python` isn't recognised | Use `py` (Windows) or `python3` (Mac), or [install Python](https://www.python.org/downloads/) |
| A blank page | Start it with Step 5 and open the `localhost` address; don't double-click `index.html` |
| "Address already in use" | Run `python -m http.server 8080` and open `localhost:8080/?run=final-fresh` |
| "Could not load run" | The terminal isn't in the `demo` folder. Stop it, redo Step 4, start again |
| The page looks too small | Your browser is zoomed out. The page scales itself, so press **Ctrl + 0** (Mac: **Cmd + 0**) |
| Old version after an update | Hard refresh: **Ctrl + Shift + R** (Mac: **Cmd + Shift + R**) |
| Scrolling jumps a whole screen | On purpose: each scroll moves one screen. Use the tabs or the dots to jump anywhere |

## About the project

### Current merged-model submission

**Selected release (10 Nov 2026): `merge_alpha_0.75`**, a CPU-only interpolation of **75% v7 semantic-contrast + 25% v8 targeted/two-turn LoRA weights**. The merge performed no additional training.

Adapter SHA-256: `a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335`.

The repository demo replays the frozen `final-fresh` evaluation (plain training v5 vs EvidenceTune v6). The recorded-only merged α=0.75 comparison is in `demo/data/results/merged-alpha-075/merged.json` and is replayed by the [Hugging Face demo](https://mizore66-evidencetune-merged-demo.static.hf.space/index.html). The separate historical mock (`?run=mock-smoke`) is invented, not current model evidence.

#### Public artifacts

- [Merged alpha=0.75 model](https://huggingface.co/Mizore66/evidencetune-merged-alpha-0.75)
- [Merged model data and evidence](https://huggingface.co/datasets/Mizore66/evidencetune-merged-data-alpha-0.75)
- [Hugging Face collection](https://huggingface.co/collections/Mizore66/evidencetune-merged-alpha-075-6af247b1e0ea2081369d1b08)
- [Recorded-only demo](https://mizore66-evidencetune-merged-demo.static.hf.space/index.html) — replays saved predictions; it does not run a model.

#### Frozen confirmation results

Selection used **dev data only**; the frozen suite was confirmation-only and did not change the selected model. Both arms below ran on the same **Apple MPS bf16 Transformers** backend.

| Frozen metric | v7 | **Merged α=0.75** | Delta |
|---|---:|---:|---:|
| Semantic task success | 88.75% | **92.50%** | +3.75pp |
| Targeted task success | 91.48% | **93.70%** | +2.22pp |
| Semantic all-five-condition case success | 60.42% | **72.92%** | +12.50pp |
| Targeted all-five-condition case success | 74.07% | **79.63%** | +5.56pp |

Semantic evaluation contains 48 cases / 240 rows per arm; targeted evaluation contains 54 cases / 270 rows per arm. All 1,020 frozen raw records were independently checked. These are **contract-v2 synthetic construction-proxy results**, not human validation or broad natural-domain evidence.

#### Evidence and reproducibility

- [Submission draft](SUBMISSION-DRAFT.md) and [full write-up](WRITEUP.md) document selection, results, negative results, and claim boundaries.
- [Release tooling](release/README.md) and [reproduction instructions](release/REPRODUCE.md) cover package verification, saved-record replay, adapter interpolation, and demo regeneration. The supported evidence path is raw-record replay, not a promise to recover missing original selection-code bytes.
- [Curated merged-model evidence](results/merged/) contains summaries and locked selection/confirmation metadata without raw prediction dumps.
- [Demo integration contract](MERGED-DEMO.md), [recorded payload](demo_merged_data.json), and [payload builder](demo/build_merged_demo.py) define the current recorded-only comparison. The [historical v6 demo](DEMO.md) is separate and must not be relabelled or mixed into the merged-model scoreboard.

#### Licenses and limitations

Original EvidenceTune code is [MIT licensed](LICENSE); the merged adapter is [CC BY-NC 4.0](LICENSE-MODEL). Dataset, prompt, base-model, and Lexsi toolkit terms remain separate; see the [license decision](LICENSE-DECISION.md) and [third-party notices](NOTICE.md).

- Current merged/MPS scores use EvidenceTune's custom contract-v2/native scorers, **not AuditKIT**. CircuitKIT evidence is historical v6 compatibility smoke only.
- Current Apple MPS bf16 results are not directly comparable with historical v6 Kaggle fp16/RTX/vLLM results.
- Raw base Tiny Aya was not evaluated on the current contract-v2 suites, so base→merged correction improvement is unmeasured. Five rows from one case are correlated, and current resolution rates have different conditional follow-up denominators.
- Contradiction and Arabic weaknesses remain; the small Arabic proxy is not native-speaker validation. DPO and natural SciFact training were rejected. Historical v6 safety-retention results are not merged-model safety evidence.

### Project documents

- [Research specification](SPEC.md)
- [Written execution plan](PLAN.md)
- [Task backlog](BACKLOG.md)

#### Task categories

- **Data & Annotation** — sources, counterfactuals, independent labels, Arabic quality, and CuratorKIT.
- **ML & Evaluation** — Aya runners, SafeTune, baselines, AuditKIT, and analysis.
- **Frontend & Design** — demo experience, visual communication, and presentation.
