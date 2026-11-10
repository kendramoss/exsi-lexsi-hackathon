# EvidenceTune v2 — scaled, shortcut-balanced data — 3 Nov 2026

**Verdict: ordinary SFT now separates valid from unsupported citations on held-out documents (61/64 matched pairs, 31/32 lexical traps), but a per-template bag-of-words control gets 55/64. Most of the lift is template-clause recognition, not yet general evidence-sensitivity. SafeGrad (solo rows protected) collapses to RETAIN.**

Run: HF Job `evtune-v2` (A100 80 GB, ~70 min, ~$2.90). Outputs: `results/hf-v2/`, private bucket `Mizore66/evtune-smoke`.

## Data (build_data_v2.py)

- Train: ContractNLI **train** split, 208 Entailment + 208 Contradiction cases × 5 matched rows = 2,080 rows. Documents whose opening text matches a dev/test document are excluded; verbatim-template duplicates deduplicated.
- Dev: ContractNLI **test** split, 32 + 32 cases × 5 = 320 rows (≤2 cases per document). Smoke eval (16 rows, dev split) kept for continuity.
- Rows per case: valid citation → UPDATE; unsupported citation toward truth → CLARIFY; unsupported citation away from truth → RETAIN; bare pressure away → RETAIN; solo answer. The valid/unsupported pair shares one sampled surface form (number citation, quote, or both) and target; only the cited excerpt differs. 3–4 response phrasings per action.
- **Shortcut audit (shortcut_audit.py):** before balancing, TF-IDF overlap picked the valid citation 73% and excerpt length 69%. After stratified sampling and alternating excerpt order, overlap, length and position each pick it exactly 50% on train and dev. Dev has 32/64 lexical-trap cases.
- Limits: labels are ContractNLI gold-span proxies; one domain (NDAs); **dev shares all 17 statement templates with train** (only documents are disjoint).

## Training

SafeTune, identical export/seed/hparams: 2 epochs, batch 4, LR 1e-4, max_len 1024, LoRA r16.
- PlainSFT: final loss ~0.06, stable, 11.5 min.
- SafeGrad (416 solo rows protected, KL to frozen base): loss ~2.0 throughout, gradient norms 277–1,178, 27 min.

## Dev results (64 cases, 320 rows; descriptive, one seed)

| | Base | Ordinary SFT | SafeGrad |
|---|---:|---:|---:|
| Matched pairs handled (valid→UPDATE and unsupported→CLARIFY/RETAIN) | 1/64 | **61/64** | 2/64 |
| — lexical-trap pairs | 1/32 | 31/32 | 1/32 |
| Valid uptake | 25/64 UPDATE* | 63/64 | 2/64 |
| Unwarranted change (unsupported toward / away / pressure) | 64 / 64 / 64 | 3 / 3 / 0 | 15 / 18 / 30 |
| Solo accuracy | 10/64* | 56/64 | 8/64 |
| Format followed | 13% | 100% | 83% |

\* Base mostly ignores the format (writes `ACTION: ANSWER` and prose), but it changes its answer in every feedback row.

Ordinary SFT on unsupported citations: 43 RETAIN + 18 CLARIFY toward the truth. It prefers RETAIN where the design's gold label is CLARIFY; both are in the acceptable set.

Smoke eval (16 rows): base identical to the smoke run (deterministic); SFT 12/12 acceptable actions, 4/4 solo.

## Control that tempers the result (template_control.py)

A TF-IDF + logistic regression classifier on (statement template id + cited excerpt words), trained on the same train pairs, picks the valid citation in **55/64** dev pairs. Ordinary SFT beats it by 6 pairs. ContractNLI's 17 fixed templates let a model learn which clause vocabulary settles each template. That is real domain skill, but not yet the generalisable "does this evidence settle it?" behaviour EvidenceTune claims.

## What this changes

1. **Scale fixed the smoke-test collapse.** With shortcut-balanced matched pairs, SFT stopped refusing every citation and became selective, including on lexical traps.
2. **Next decisive test: held-out templates.** Train on ~12 statement templates, evaluate on ~5 unseen ones, and keep the template bag-of-words control as a required baseline. The brief already requires splits disjoint by source document and hypothesis template.
3. **SafeGrad must be redesigned before it means anything.** With the solo rows protected and KL to base it does not learn the task (loss stuck ~2, huge gradient norms) and collapses to RETAIN. Options: protect the RETAIN/CLARIFY rows instead, lower `rho`/KL temperature, or use a different SafeTune harden method.
4. Batched left-padded generation changes Aya outputs (hybrid sliding-window cache); evaluation stays one prompt at a time.

## Files

`build_data_v2.py`, `shortcut_audit.py`, `hf_job_v2.py`, `analyze_v2.py`, `template_control.py`, `data_v2/`, `jobpack2/`, `results/hf-v2/`.
