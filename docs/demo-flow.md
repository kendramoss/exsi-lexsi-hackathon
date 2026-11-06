# 60-second demo flow (draft for #6, needs team approval)

One matched pair: same question and passage, two corrections. Each beat maps to one step of the demo (`demo/?step=N`).

| Time | On screen | Say |
|---|---|---|
| 0:00–0:10 | The task card: question + passage with spans S1–S3 | "Tiny Aya answers a question from a passage. Then a user pushes back, twice." |
| 0:10–0:25 | **Step 1**, base model. Left: valid correction (24% word overlap). Right: unsupported correction (93% overlap, highlighted). Both marked UPDATE. | "One correction is right and phrased in new words. The other copies the passage's wording but contradicts it. Base Aya apologises and flips both times. It follows pressure, not evidence." |
| 0:25–0:45 | **Step 2**, EvidenceTune. Left: updates and cites S3. Right: asks for a source, the user has none, and it keeps 2001. | "After SafeTune hardening it accepts the valid correction and cites the line. For the unsupported one it asks for a source, and the clarification counts only because the conversation resolves correctly." |
| 0:45–0:60 | **Step 3**, scoreboard. Point at the never-update row, then the EvidenceTune row. | "No single score. Never-update gets 0% unwarranted updates by refusing everything, so valid uptake drops to zero. The claim is lower UUR *without* losing valid uptake or final accuracy, against the strongest prompt baseline." |

## Claim labels (must match frozen results before going live)

- Step 2 heading claims EvidenceTune "updates on evidence and asks when the evidence is missing". This holds only if the frozen run shows it. If the harness wins (SPEC stop condition 4), the heading switches to the harness and the claim becomes a benchmark result.
- The scoreboard shows every comparator, intervals included. Nothing is hidden for being unflattering.

## Open questions

1. Is "Evidence-aware prompt" the right strongest cheap baseline to show, or TF-IDF gate (#8)?
2. Should bare pressure get its own lane? It's in the data and the metrics but not on screen.
3. Which pair goes first in the live demo: the document question or the table arithmetic one?
