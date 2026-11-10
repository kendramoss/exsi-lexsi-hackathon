# EvidenceTune v6 — transfer fix (VitaminC) — 3 Nov 2026

**Verdict: small, consistent improvement in the right direction, not significant on 68 cases. Adding 424 matched VitaminC claims (368 Wikipedia pages) to the 12-template ContractNLI training lifts held-out-template matched pairs from 49/68 to 52/68 and lexical traps from 8/18 to 11/18 (paired: v6 wins 5 cases, v5 wins 2; traps 3–0; p = 0.45 / 0.25). It now edges past the word-overlap rule (50/68) but citation judgement on unseen clause types is still far from in-template (61/64).**

Run: HF Job `evtune-v6` (RTX PRO 6000, ~30 min, ~$1.40; one earlier 40-s attempt stopped on the text-integrity check). Base outputs identical to v5 (same GPU type), so the comparison is clean.

## Data (build_data_v6.py)

- v5 train (1,060 ContractNLI rows, 12 templates) + 2,120 VitaminC rows (424 claims × 5 matched rows), tals/vitaminc dev split, CC BY-SA 3.0.
- VitaminC case: gold = the claim's SUPPORTS/REFUTES evidence; two distractors = other evidence sentences from the same Wikipedia page, excluding near-duplicate revisions of the gold sentence. Overlap, length and position each predict the valid citation 50%.
- CuratorKIT's TextCleaner rules (HTML strip, NFC, mojibake, whitespace) are applied before export (90 fields changed) so label hashes survive CuratorKIT unchanged.
- Eval: unchanged v5 held-out-template sets (dev 20 balanced + devwide 48).

## Results (68 held-out-template cases)

| | Base | v5 SFT (CNLI only) | **v6 SFT (+VitaminC)** | Overlap rule | Template BoW |
|---|---:|---:|---:|---:|---:|
| Matched pairs handled | 0/68 | 49/68 | **52/68** | 50/68 | 38/68 |
| — lexical traps | 0/18 | 8/18 | **11/18** | 0/18 | — |
| — non-traps | 0/50 | 41/50 | 41/50 | 50/50 | — |
| Valid uptake | — | 51/68 | **57/68** | | |
| Unwarranted change on cited pushback | 136/136 | 24/136 | 24/136 | | |
| Bare pressure resisted | 0/68 | 68/68 | 68/68 | | |
| Solo accuracy | 2/68 | 47/68 | **53/68** | | |
| Clarify on unsupported citation | — | 18/68 | 46/68 | | |

## Reading

- Every task metric moved the right way or held. The model now asks for clarification instead of silently retaining far more often (46 vs 18), which is the intended behaviour for unsupported citations.
- The transfer gap remains: 52/68 held-out vs 61/64 in-template, and traps at 61%. With 18 trap cases the gain is suggestive, not established.
- To establish it: a larger held-out-template test set (ContractNLI test has ~300 eligible held-out-template cases; we used 68), plus 2–3 seeds. Cost ~$3–5.

## Files

`build_data_v6.py`, `hf_job_v6.py`, `jobpack6/`, `results/hf-v6/`.
