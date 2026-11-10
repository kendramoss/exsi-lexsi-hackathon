# EvidenceTune — final frozen evaluation — 3 Nov 2026

**Result: on 136 fresh cases from 5 statement types never seen in training, the VitaminC-augmented adapter (v6) handles 115/136 matched correction pairs (85%) vs 102/136 (75%) for the contracts-only adapter (v5) and 95/136 (70%) for the word-overlap rule. v6 beats v5 on paired cases 15 to 2 (exact McNemar p = 0.002). On the 41 fresh lexical traps, where word overlap always points to the wrong excerpt, v6 gets 31/41 (76%) vs v5 27/41.**

Run: HF Job `evtune-final` (RTX PRO 6000, ~55 min, ~$2.50). Single seed. Test set frozen before the run: `data_final/FREEZE.json` (source sha256 a466a482…, labels 6bb50b55…).

## Test set

- Every eligible ContractNLI case (test + dev splits) for held-out templates nda-1/7/15/16/17: 204 cases × 5 matched rows. **Fresh** = 136 cases never used for any decision; the other 68 were used to choose v6 (reported as secondary).
- Fresh labels are imbalanced (124 Entailment / 12 Contradiction); the matched-pair metric is symmetric within each case.
- Same matched-pair construction, response formats and CuratorKIT cleaning as training data; 48-token greedy replies.

## Results — fresh (primary)

| | v5 (12 contract templates) | **v6 (+ VitaminC)** | Word-overlap rule |
|---|---:|---:|---:|
| Matched pairs handled | 102/136 (75%) | **115/136 (85%)** | 95/136 (70%) |
| — lexical traps | 27/41 | **31/41** | 0/41 |
| — non-traps | 75/95 | **84/95** | 95/95 |
| Valid corrections taken | 110/136 | **121/136** | |
| Unwarranted change on cited pushback | 35/272 | **29/272** | |
| Bare pressure resisted | 136/136 | 136/136 | |
| Solo accuracy | 112/136 | 112/136 | |
| Asks for evidence on unsupported citation | 80/272 | **208/272** | |

Paired v5→v6: 15 cases only v6 gets right, 2 only v5 (p = 0.002); traps 5–1 (p = 0.22); non-traps 10–1 (p = 0.012).

All 204 cases (secondary): v5 150, v6 171, overlap rule 144; paired 23–2 (p < 0.001); traps v5 36/60, v6 42/60 (p = 0.07).

## Correction to the v5 write-up

V5-HELDOUT-RESULTS.md said v5's citation judgement on unseen templates was "at chance on traps (8/18)". On this larger frozen set v5 handles 27/41 fresh traps (66%). The 18-case estimate was too small: v5 transfers partially, and VitaminC data improves it.

## Claims this supports

1. Fine-tuning Tiny Aya on matched counterfactual corrections teaches update/retain/clarify behaviour that transfers to unseen clause types: pressure resistance 100%, unwarranted changes ~11%, and citation judgement well above the word-overlap shortcut.
2. Mixing in topic-diverse contrastive evidence (VitaminC) significantly improves held-out transfer (p = 0.002) and shifts unsupported-citation behaviour from silent retention to asking for evidence.
3. Training does not reduce safety on public multilingual red-team prompts (V4).

Limits: one seed; ContractNLI/VitaminC proxy labels, not independent annotation; English only; fresh set mostly Entailment.

## Artifacts (private bucket `Mizore66/evtune-smoke/final/`, local `results/final/`)

`adapter_v6/` (LoRA, 121 MB), `audit/final_{v5,v6}.json` (raw predictions + AuditKIT scores), `curated/` (CuratorKIT exports + manifests), `safetune/` (provenance), `scorecard.json`. Scripts: `build_final.py`, `hf_job_final.py`.
