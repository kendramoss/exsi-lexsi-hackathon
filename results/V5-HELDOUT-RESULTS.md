# EvidenceTune v5 — held-out statement templates — 3 Nov 2026

**Verdict: partial transfer. Behaviour that doesn't depend on the clause transfers fully: following the format, resisting bare pressure (68/68), and not flipping on uncited pushback. Telling a valid citation from an unsupported one does NOT transfer: on the 5 unseen statement types, ordinary SFT (49/68 pairs) does no better than a plain word-overlap rule (50/68), and gets lexical-trap pairs right only at chance (8/18). In-template it was 61/64 with 31/32 traps.**

Run: HF Job `evtune-v5` (RTX PRO 6000, 20 min, ~$1). Outputs `results/hf-v5/`.

## Setup

- Train: 12 ContractNLI templates, train split, 106 + 106 cases × 5 matched rows = 1,060 rows; TF-IDF/length/position cues balanced to 50%.
- Held-out: templates nda-1, nda-7, nda-15, nda-16, nda-17 (never in training), test split.
  - `dev`: 20 cases, cues balanced (10 lexical traps).
  - `devwide`: 48 more cases, label-balanced only (8 traps; overlap rule picks valid in 40/48).
- Ordinary SFT via SafeTune PlainSFT, same hparams as v2; base Tiny Aya Global; AuditKIT live eval.

## Results (68 held-out cases)

| | Base | SFT (held-out templates) | Word-overlap rule | Template bag-of-words | SFT in-template (v2, for reference) |
|---|---:|---:|---:|---:|---:|
| Matched pairs handled | 0/68 | 49/68 (72%) | 50/68 (74%) | 37/68 | 61/64 (95%) |
| — lexical traps | 0/18 | **8/18 (44%)** | 0/18 by construction | — | 31/32 |
| — non-traps | 0/50 | 41/50 (82%) | 50/50 | — | 30/32 |
| Valid uptake | 13/68 UPDATE* | 51/68 | | | 63/64 |
| Unwarranted change on cited pushback | 136/136 | 24/136 (18%) | | | 6/128 (5%) |
| Bare pressure resisted | 0/68 | **68/68** | | | 64/64 |
| Solo accuracy | 2/68* | 47/68 (69%) | | | 56/64 |

\* Base mostly ignores the format.

## Reading

- **Transfers:** answer format, resisting pressure with no evidence (100%), and a large drop in unwarranted changes vs base (100% → 18%). Solo reading improves from 2/68 to 47/68.
- **Doesn't transfer:** judging *whether a citation settles an unfamiliar clause type*. On unseen templates the model's choices track word overlap. It's right when the gold excerpt overlaps more (41/50) and at chance when the distractor does (8/18). In-template, its 95% was largely learned clause vocabulary per template; the bag-of-words control there got 86%.
- So the trained adapter's evidence-sensitivity is **domain-bound**. The benchmark is what exposes this: its balanced trap split separates the two cases cleanly.

## Implications for the submission

- The **benchmark + finding** is strong for brief #2. "Fine-tuning Aya on matched counterfactuals teaches pressure resistance that transfers to unseen clause types, but citation judgement collapses to lexical overlap; the trap split detects it, and accuracy on an unbalanced set would hide it (devwide overlap rule 83%)."
- Any "evidence-sensitive adapter" claim must be scoped to in-template / in-domain.
- Ways to try for real transfer (each ~$1–3): (1) add contrastive evidence data from other sources, e.g. VitaminC-style claim/evidence pairs, so clause vocabulary can't be memorised; (2) train the model to quote the deciding phrase before answering; (3) more statement diversity by paraphrasing templates with Aya Expanse.

## Files

`build_data_v5.py`, `hf_job_v5.py`, `jobpack5/`, `results/hf-v5/`; `analyze_v2.py` and `template_control.py` now take `EVTUNE_LABELS`/`EVTUNE_PREFIX` and `EVTUNE_DATA`.
