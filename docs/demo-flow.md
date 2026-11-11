# 60-second demo script

For demo day and the recorded fallback video (#13). Six screens, one scroll each, about 10 seconds a screen. Open the [demo](https://kendramoss.github.io/exsi-lexsi-hackathon/demo/?run=final-fresh) with the browser at 100%. Move with the scroll wheel, the ↓ key or the tabs. Every number below comes from the saved `final-fresh` run (plain training v5 vs EvidenceTune v6, 136 cases × 4 pushbacks); recheck them if the run changes.

| Time | Screen | On screen | Say |
|---|---|---|---|
| 0:00–0:07 | **1 · Why** | "Does the model change its answer for the right reason?" | "AI models give in when you argue. We taught ours to change its answer only when the evidence says so." |
| 0:07–0:17 | **2 · The result** | Two gauges on one wrong pushback; below, 80 vs 208 out of 272 | "Same contract, same wrong pushback. Plain training switches to the wrong answer. EvidenceTune stays right. Across all 272 wrong quotes, it asks for the source 2.6 times as often." |
| 0:17–0:32 | **3 · Watch it** | The chat plays itself: question with the contract, first answer, the pushback with its quote highlighted, then the split | "Here's the actual chat. The user quotes excerpt 3, but excerpt 3 is about returning copies, not about rights. Plain training says 'my answer is now no.' EvidenceTune says the excerpt doesn't establish it, and asks what text does." |
| 0:32–0:42 | **4 · Under pressure** | Two stacked bars: kept, asked for proof, changed | "Every wrong quote, every case. Plain training asks for proof 29% of the time. EvidenceTune: 76%." |
| 0:42–0:53 | **5 · The test** | One case, four pushbacks, what the model should do for each | "Is the test fair? Every case gets four pushbacks. The ones that quote an excerpt use the same words, and only the excerpt changes, so the model can't pass on word overlap. And every test case uses clause types it never saw in training." |
| 0:53–1:00 | **6 · See the work** | The model, test cases and code; "See all the numbers" | "The model, the benchmark and the code are all public. Every number is in the full table." |

## Before you present

- Browser at **100%** (Ctrl + 0 / Cmd + 0). The page scales itself; zooming out shrinks it twice.
- Load the page once beforehand so the fonts and data are cached.
- Screen 3 plays itself on arrival. Wait for "Only EvidenceTune holds" before moving on, or press → to skip ahead.
- On screen 2 the two gauges take turns being highlighted. Talk over it; no need to wait.

## Claim boundaries

- These are the **historical v5 vs v6** results on the 136-case `final-fresh` set, not the merged α=0.75 model. Say "EvidenceTune v6" if asked which model.
- "Asks for proof" counts the saved `clarify` actions; "switches" counts `update`. Nothing is recomputed live.
- If the demo moves to the merged α=0.75 data, rewrite the numbers on screens 2 and 4 before presenting.
