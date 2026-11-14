# Storyboard and recording checklist

Status: **video pending.** Stills were captured from the local runtime in headless Chrome and viewed; they sit in the git-ignored `.verification/jobtmp/stills/` of the authoring worktree and are not committed. No audio and no video have been recorded.

## Which source for which beat

- Beats S1, S2, S3 and S5 use the **local runtime** (`demo/`). Its default run, `final-fresh`, is the **historical** plain-training (v5) vs EvidenceTune v6 comparison: 136 underlying cases, 544 pushbacks. The local page does **not** show merged alpha=0.75 outputs; its own text says the released model "has its own frozen results".
- Beat S4 uses the **standalone Hugging Face recorded merged demo** (URL in [`MERGED-DEMO.md`](../../MERGED-DEMO.md)), because that is the page that replays merged outputs. The local repo ships `demo/data/results/merged-alpha-075/merged.json`, but the local page does not read it (`demo/README.md`). Make the switch of page visible to the viewer.
- Label S2 on screen: "Historical: plain training vs EvidenceTune v6". Label S4 on screen: "Released model: merged alpha=0.75 (recorded replay)".

## Timeline

| Time | Scene | Screen | On-screen overlay | Still | Narration |
|---|---|---|---|---|---|
| 0:00-0:07 | S1 | Local, screen 1 Why | none | `01-top.png` | [`scenes.json`](scenes.json) S1 |
| 0:07-0:21 | S2 | Local, screen 2 The result | "Historical: plain training vs EvidenceTune v6" | `02-glance.png` | S2 |
| 0:21-0:31 | S3 | Local, screen 3 Watch it, last step | "One chosen example, recorded" | `03-s1.png` | S3 |
| 0:31-0:47 | S4 | Standalone HF merged demo | "Released model: merged alpha=0.75. Recorded replay, synthetic proxy tests, local Apple MPS" | none (needs network, not captured) | S4 |
| 0:47-1:00 | S5 | Local, screen 6 See the work | Scope card (below) | `06-s4.png` | S5 |

Scope card, on screen for the whole of S5 at readable size:

> Synthetic proxy evaluation only. No human validation. Teacher labels, no human audit (team decision). No claims about safety, natural text, Arabic, or model superiority.

## Exact click and recording checklist (macOS, manual)

1. Close other apps and silence notifications. Browser at 100% (Cmd+0), 1920x1080 window.
2. Terminal: `cd demo && python3 -m http.server 8765`. Open `http://127.0.0.1:8765/?run=final-fresh`. Do not open `index.html` as a file (blank page).
3. Open the HF merged demo in a second tab and let it load fully before recording.
4. Start your own screen recorder (QuickTime: File > New Screen Recording). macOS will ask for Screen Recording permission; a person must grant it.
5. S1 (0:00): stay on screen 1. Hold 7 s.
6. S2 (0:07): click tab **02 The result**. Let the gauges settle, point at 80/272 and 208/272. Hold to 0:21.
7. S3 (0:21): click tab **03 Watch it**. The chat plays itself; press the right arrow to reach "The two AIs split". Hold to 0:31.
8. S4 (0:31): switch to the HF tab. Show the semantic and targeted scoreboards. Keep the recorded-replay, synthetic-proxy and same-local-backend overlay readable for the entire scene, through 0:47.
9. S5 (0:47): back to the local tab, click tab **06 See the work**. Add the scope card overlay. Hold to 1:00.
10. Stop. Confirm duration is about 60 s, then add [`captions.srt`](captions.srt).

## Remaining manual step

Record narration audio and the screen capture (steps 4 to 10), then export. Nothing in this kit is a finished video.
