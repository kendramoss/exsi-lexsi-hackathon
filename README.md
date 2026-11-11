# EvidenceTune — Lexsi Hackathon Track 2

**Does a model change its answer for the right reason?** EvidenceTune teaches a small model to change its answer only when the evidence says so: it accepts a correction that quotes the right part of a document, and asks for proof when someone pushes back with a quote that settles nothing.

## Start here

Pick what you want to do. Each link jumps to step-by-step instructions.

| I want to… | How long | Go to |
|---|---|---|
| **See the demo right now**, nothing to install | 1 click | [Watch the demo online](#watch-the-demo-online) |
| **Open the demo on my own computer** | about 5 minutes | [Run the demo on your computer](#run-the-demo-on-your-computer) |
| **Put the demo online myself**, for free | about 10 minutes | [Host your own copy](#host-your-own-copy) |
| **Look at the model, the test cases and the code** | a few minutes | [Find the model, data and code](#find-the-model-data-and-code) |
| **Check the numbers or rebuild the results** | longer | [Check and reproduce the results](#check-and-reproduce-the-results) |
| **Fix something that didn't work** | — | [If something goes wrong](#if-something-goes-wrong) |

---

## Watch the demo online

**[Open the demo →](https://kendramoss.github.io/exsi-lexsi-hackathon/demo/?run=final-fresh)**

That's it. It opens in your browser and works on any computer.

- Scroll down, or use the tabs at the top, to move through the screens.
- The demo replays answers the model already gave during testing. It does not run the model live, so it is fast and always shows the same results.
- An earlier version that replays the merged α=0.75 model is on [Hugging Face](https://mizore66-evidencetune-merged-demo.static.hf.space/index.html).

---

## Run the demo on your computer

You only need **Python**, which most computers already have. No other installs, no accounts.

### Step 1 · Check that Python is installed

Open a terminal:

- **Windows:** press the **Windows key**, type `cmd`, press **Enter**.
- **Mac:** press **Cmd + Space**, type `Terminal`, press **Enter**.

Type this and press **Enter**:

```sh
python --version
```

You should see something like `Python 3.12.1`. Any version that starts with **3** works.

> **Saw an error instead?**
> - On Windows, try `py --version`. If that works, use `py` instead of `python` in every step below.
> - On Mac, try `python3 --version`. If that works, use `python3` instead of `python`.
> - If none of them work, install Python from [python.org/downloads](https://www.python.org/downloads/) (on Windows, tick **"Add python.exe to PATH"** on the first screen of the installer), then close and reopen the terminal.

### Step 2 · Download this project

**Easiest way (no Git needed):**

1. At the top of this page, click the green **`<> Code`** button.
2. Click **Download ZIP**.
3. Find the downloaded file (usually in your **Downloads** folder) and unzip it:
   - **Windows:** right-click the file → **Extract All…** → **Extract**.
   - **Mac:** double-click the file.

You now have a folder called `exsi-lexsi-hackathon-main`.

**If you use Git**, you can do this instead:

```sh
git clone https://github.com/kendramoss/exsi-lexsi-hackathon.git
```

### Step 3 · Open a terminal inside the `demo` folder

1. Open the project folder, then open the **`demo`** folder inside it.
2. Open a terminal right there:
   - **Windows:** click the address bar at the top of the folder window, type `cmd`, press **Enter**.
   - **Mac:** right-click the `demo` folder → **New Terminal at Folder**. (If you don't see it, turn it on in **System Settings → Keyboard → Keyboard Shortcuts → Services**.)

> **Prefer typing?** In any terminal, `cd` into the folder, for example:
> `cd Downloads/exsi-lexsi-hackathon-main/demo`

### Step 4 · Start the demo

Type this and press **Enter**:

```sh
python -m http.server 8000
```

You will see a line like `Serving HTTP on :: port 8000`. **Leave this window open** while you use the demo.

### Step 5 · Open it in your browser

Go to **[http://localhost:8000/?run=final-fresh](http://localhost:8000/?run=final-fresh)**.

The demo loads. Scroll, or use the tabs at the top, to move through it.

### Step 6 · Stop it when you're done

Go back to the terminal window and press **Ctrl + C**. You can close the window afterwards.

---

## Host your own copy

The demo is a plain website: a few HTML, CSS, JavaScript and data files in the `demo` folder, with no server code. Any free static host can serve it. Pick one:

### Option A · Hugging Face Space (recommended)

The `demo` folder is already set up for this (its `README.md` holds the Space settings).

1. Sign in at [huggingface.co](https://huggingface.co) (create a free account if you need one).
2. Go to **[huggingface.co/new-space](https://huggingface.co/new-space)**.
3. Give it a name, choose **Static** as the Space SDK, and click **Create Space**.
4. On the new Space, open the **Files** tab → **Add file** → **Upload files**.
5. Drag in **everything inside** the `demo` folder (not the folder itself), then click **Commit changes**.
6. Wait about a minute, then open the **App** tab. Your copy is live at `https://huggingface.co/spaces/<your-name>/<space-name>`.

### Option B · Netlify Drop (no account needed to try)

1. Go to **[app.netlify.com/drop](https://app.netlify.com/drop)**.
2. Drag the whole **`demo`** folder onto the page.
3. Netlify gives you a link in a few seconds. Open it, and the demo is online.

### Option C · GitHub Pages

1. Click **Fork** at the top of this page to copy the project to your account.
2. In your fork, go to **Settings → Pages**.
3. Under **Build and deployment**, set **Source** to **Deploy from a branch**, pick **`main`** and **`/ (root)`**, and click **Save**.
4. After a minute or two the demo is at `https://<your-name>.github.io/exsi-lexsi-hackathon/demo/`.

> Whatever host you use, the demo has to be opened through a web address (`http://…` or `https://…`). Double-clicking `index.html` to open it as a file shows a blank page, because browsers block the data files that way.

---

## Find the model, data and code

| What | Where | What you'll find |
|---|---|---|
| **The model** | [Merged α=0.75 model on Hugging Face](https://huggingface.co/Mizore66/evidencetune-merged-alpha-0.75) | The released adapter and its model card |
| **The test cases and evidence** | [Merged model data and evidence](https://huggingface.co/datasets/Mizore66/evidencetune-merged-data-alpha-0.75) | The cases the model was checked on, with saved outputs |
| **Everything in one place** | [Hugging Face collection](https://huggingface.co/collections/Mizore66/evidencetune-merged-alpha-075-6af247b1e0ea2081369d1b08) | The model, data and demo together |
| **The code** | [This repository](https://github.com/kendramoss/exsi-lexsi-hackathon) | Training, scoring, analysis and the demo |
| **The write-up** | [Submission draft](SUBMISSION-DRAFT.md) · [Full write-up](WRITEUP.md) | How the model was chosen, the results, what didn't work, and what we don't claim |

---

## Check and reproduce the results

These are for a deeper check and assume you are comfortable with Python and a terminal.

- **[Release tooling](release/README.md)**: how the release package is built and verified.
- **[Reproduction guide](release/REPRODUCE.md)**: verify the adapter package, replay the selection and frozen metrics from saved records, and rebuild the demo data. The commands in it use the author's own folder paths; swap in the paths on your machine.
- **[Frozen results table](#frozen-confirmation-results)**: the headline numbers, further down this page.

---

## If something goes wrong

| What you see | What to do |
|---|---|
| `python` is not recognised, or "command not found" | Use `py` (Windows) or `python3` (Mac) instead, or [install Python](https://www.python.org/downloads/). See [Step 1](#step-1--check-that-python-is-installed). |
| A blank page | You opened `index.html` as a file. Start the demo with [Step 4](#step-4--start-the-demo) and use **http://localhost:8000** instead. |
| "Address already in use" | Port 8000 is busy. Run `python -m http.server 8080` and open **http://localhost:8080**. |
| "Could not load run" on the page | The terminal wasn't started inside the `demo` folder. Stop it with **Ctrl + C**, go back to [Step 3](#step-3--open-a-terminal-inside-the-demo-folder), and start again. |
| The page looks old after an update | Hard refresh: **Ctrl + Shift + R** (Windows) or **Cmd + Shift + R** (Mac). |
| Scrolling jumps a whole screen at a time | That's on purpose: each scroll moves to the next screen. Use the tabs at the top or the dots on the right to jump anywhere. |

---

# Project details

A three-person project building a lexical-controlled safety benchmark and SafeTune-trained Aya adapter for evidence-sensitive correction.

EvidenceTune teaches and evaluates when a model should accept supported feedback, resist unsupported correction, or request clarification while preserving final task utility.

**Official fit:** Track 2a #2 (safety benchmark), with Track 2b #5 (safety-hardened versus ordinary fine-tuning) as the secondary comparison.

**Pipeline:** CuratorKIT → SafeTune → AuditKIT.

**Teacher models and distillation.** EvidenceTune distills the evidence judgement of frontier teacher models into Tiny Aya. [`teacher/`](teacher/README.md) labels blind rows with Claude Fable 5.2 and Claude Opus 5.5 through a local headless Claude Code CLI (no API key), keeps only labels that pass the task contract, compares the two teachers, sends disagreements to a judge model, and measures the result against a blind human audit sample. Provenance stays truthful: teacher labels carry `label_origin: teacher_*` and `human_attestation: false`. The merged model's training data comes from ContractNLI's human expert labels via deterministic scripts, not from teachers; the [teacher README](teacher/README.md#what-is-and-isnt-teacher-labelled-today) lists which data is teacher-labelled.

## Current merged-model submission

**Selected release (10 Nov 2026): `merge_alpha_0.75`**, a CPU-only interpolation of **75% v7 semantic-contrast + 25% v8 targeted/two-turn LoRA weights**. The merge performed no additional training.

Adapter SHA-256: `a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335`.

The repository demo defaults to the verified, recorded-only merged α=0.75 comparison in `demo/data/results/merged-alpha-075/merged.json`. The separate historical mock is available explicitly with `?run=mock-smoke` and is invented, not current model evidence.

### Public artifacts

- [Merged alpha=0.75 model](https://huggingface.co/Mizore66/evidencetune-merged-alpha-0.75)
- [Merged model data and evidence](https://huggingface.co/datasets/Mizore66/evidencetune-merged-data-alpha-0.75)
- [Hugging Face collection](https://huggingface.co/collections/Mizore66/evidencetune-merged-alpha-075-6af247b1e0ea2081369d1b08)
- [Recorded-only demo](https://mizore66-evidencetune-merged-demo.static.hf.space/index.html) — replays saved predictions; it does not run a model.

### Frozen confirmation results

Selection used **dev data only**; the frozen suite was confirmation-only and did not change the selected model. Both arms below ran on the same **Apple MPS bf16 Transformers** backend.

| Frozen metric | v7 | **Merged α=0.75** | Delta |
|---|---:|---:|---:|
| Semantic task success | 88.75% | **92.50%** | +3.75pp |
| Targeted task success | 91.48% | **93.70%** | +2.22pp |
| Semantic all-five-condition case success | 60.42% | **72.92%** | +12.50pp |
| Targeted all-five-condition case success | 74.07% | **79.63%** | +5.56pp |

Semantic evaluation contains 48 cases / 240 rows per arm; targeted evaluation contains 54 cases / 270 rows per arm. All 1,020 frozen raw records were independently checked. These are **contract-v2 synthetic construction-proxy results**, not human validation or broad natural-domain evidence.

### Evidence and reproducibility

- [Submission draft](SUBMISSION-DRAFT.md) and [full write-up](WRITEUP.md) document selection, results, negative results, and claim boundaries.
- [Release tooling](release/README.md) and [reproduction instructions](release/REPRODUCE.md) cover package verification, saved-record replay, adapter interpolation, and demo regeneration. The supported evidence path is raw-record replay, not a promise to recover missing original selection-code bytes.
- [Curated merged-model evidence](results/merged/) contains summaries and locked selection/confirmation metadata without raw prediction dumps.
- [Demo integration contract](MERGED-DEMO.md), [recorded payload](demo_merged_data.json), and [payload builder](demo/build_merged_demo.py) define the current recorded-only comparison. The [historical v6 demo](DEMO.md) is separate and must not be relabelled or mixed into the merged-model scoreboard.

### Licenses and limitations

Original EvidenceTune code is [MIT licensed](LICENSE); the merged adapter is [CC BY-NC 4.0](LICENSE-MODEL). Dataset, prompt, base-model, and Lexsi toolkit terms remain separate; see the [license decision](LICENSE-DECISION.md) and [third-party notices](NOTICE.md).

- Current merged/MPS scores use EvidenceTune's custom contract-v2/native scorers, **not AuditKIT**. CircuitKIT evidence is historical v6 compatibility smoke only.
- Current Apple MPS bf16 results are not directly comparable with historical v6 Kaggle fp16/RTX/vLLM results.
- Raw base Tiny Aya was not evaluated on the current contract-v2 suites, so base→merged correction improvement is unmeasured. Five rows from one case are correlated, and current resolution rates have different conditional follow-up denominators.
- Contradiction and Arabic weaknesses remain; the small Arabic proxy is not native-speaker validation. DPO and natural SciFact training were rejected. Historical v6 safety-retention results are not merged-model safety evidence.

## Project documents

- [Research specification](SPEC.md)
- [Written execution plan](PLAN.md)
- [Task backlog](BACKLOG.md)

### Task categories

- **Data & Annotation** — sources, counterfactuals, independent labels, Arabic quality, and CuratorKIT.
- **ML & Evaluation** — Aya runners, SafeTune, baselines, AuditKIT, and analysis.
- **Frontend & Design** — demo experience, visual communication, and presentation.
