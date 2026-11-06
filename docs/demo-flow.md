# 60-second demo flow (draft for #6, needs team approval)

One scrolling page in three sections that each answer the question the last one raises. Each beat is one snap of the scroll (or a click on the nav).

| Time | On screen | Say |
|---|---|---|
| 0:00–0:08 | **Top**: "Does the model change its answer for the right reason?" and the 01 → 02 → 03 map | "Small models flip when you push back. We test whether safety fine-tuning fixes that, in three steps." |
| 0:08–0:30 | **01 One example**, *Wrong pushback* selected. Pushback copies the passage (93% copied, passage disagrees). Left: Base Tiny Aya "Gave in", final 1998 ✗. Right: EvidenceTune "Asked for a source", final 2001 ✓. Click *Correct pushback*: both accept it. | "Same passage, same pushback. The wrong one copies the passage's words to sound convincing. Base Aya gives in. EvidenceTune asks for a source and keeps the right answer. And it still accepts a pushback that's actually correct." |
| 0:30–0:45 | **02 Every case**: "Is it a fluke?" Cards, then the never-update row, then the EvidenceTune row. | "One example could be luck, so here's every model on every case. Never-update looks perfect on giving in, but it ignores correct pushback too. The claim is fewer give-ins *without* losing accuracy, against the strongest prompt baseline." |
| 0:45–0:60 | **03 How we tested**: "Is the test fair?" Scroll the panels sideways to the pipeline. | "CuratorKIT seals the test set before any results, SafeTune trains on the training split only, and AuditKIT scores every model on the same sealed cases." |

## Claim labels (must match frozen results before going live)

- The section 01 headline ("Base Tiny Aya gives in, EvidenceTune asks for a source") is generated from the saved scores, so it changes with the real run. Rehearse on the frozen results, not the mock. If the harness wins (SPEC stop condition 4), the heading switches to the harness and the claim becomes a benchmark result.
- The scoreboard shows every comparator, intervals included. Nothing is hidden for being unflattering.

## Open questions

1. Is "Evidence-aware prompt" the right strongest cheap baseline to show, or TF-IDF gate (#8)?
2. Should bare pressure get its own lane? It's in the data and the metrics but not on screen.
3. Which pair goes first in the live demo: the document question or the table arithmetic one?

## Visual assets (#13)

| Asset | Files | Use |
|---|---|---|
| Pipeline diagram | `docs/assets/pipeline.svg` (follows light/dark), `pipeline.png` / `pipeline-dark.png` (2600×1080) | HF Article, slides, and the demo's "How it's built" section (`demo/assets/pipeline.svg`) |

Its main point is that the eval pack goes straight from CuratorKIT to AuditKIT and never through training. If the pipeline changes, edit the SVG in `demo/assets/`, copy it to `docs/assets/`, and re-export the PNGs.
