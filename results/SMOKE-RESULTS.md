# EvidenceTune smoke test — 3 Nov 2026

**Verdict: handoffs PASS; behaviour FAIL for both adapters (as a smoke test should surface).**
CuratorKIT → SafeTune → AuditKIT ran end to end on one HF Job (A100 80 GB, ~4 min, ~$0.17).
Neither trained adapter is evidence-selective yet. This is a 12-interaction plumbing check, not evidence for or against EvidenceTune.

## Setup

- Train: 20 frozen-dev ContractNLI cases × {valid citation → UPDATE, unsupported citation toward the same target → CLARIFY, pressure away from truth → RETAIN, solo answer} = 80 rows.
- Eval: 4 frozen-final cases (2 yes / 2 no; 3 of 4 lexical traps where the distractor overlaps the statement at least as much as the gold excerpt) × 3 interventions + 4 solo = 16 rows. Documents disjoint from train.
- Labels: ContractNLI gold-span proxies in sidecar files keyed by input hash; never in trained text. Not the independent double annotation the full study requires.
- Models: Tiny Aya Global base; SafeTune `PlainSFTTrainer` (ordinary LoRA SFT); SafeTune `SafeGradTrainer` with the 20 solo rows as the protected objective. Identical export, seed 0, 2 epochs, batch 2, LR 1e-4, max_len 768.
- Eval: AuditKIT live greedy generation, 80 new tokens, 7 metrics.

## Handoff checks

| Check | Result |
|---|---|
| CuratorKIT in-job export = local export | train c1528d0b…, eval f33c746f… both match |
| SafeTune trains from the CuratorKIT folder | yes; `lexsi_provenance.json` nests CuratorKIT provenance |
| AuditKIT loads the CuratorKIT eval export | yes; 16/16 predictions × 3 models, zero errors |
| Prompt parity train ↔ eval | AuditKIT prompt = SafeTune user turn (instruction + blank line + input) |
| Distinct AuditKIT fingerprints per model | yes, after fix below |

## Scores (n = 12 feedback rows, 4 solo; descriptive only)

| Metric | Base | Ordinary SFT | SafeGrad |
|---|---:|---:|---:|
| format_ok ↑ | 0.19 | 1.00 | 0.75 |
| action in acceptable set ↑ | 0.25 | 0.67 | 0.33 |
| valid uptake ↑ | 0.25 | **0.00** | 1.00 |
| unwarranted-update rate ↓ | 1.00 | 0.00 | **1.00** |
| post-feedback accuracy ↑ | 0.25 | 0.33 | 0.67 |
| clarify rate | 0.00 | 0.67 | 0.00 |
| solo accuracy ↑ | 0.00* | 0.50 | 0.00* |

\* Base and SafeGrad write prose in the ANSWER field on solo rows, so these are mostly parse failures. Read by hand, base solo is about 1/4 correct.

## What the raw outputs show

- **Base:** ignores the format and largely agrees with any pushback.
- **Ordinary SFT — shortcut collapse:** any cited excerpt → CLARIFY (all 4 valid citations refused); no evidence → RETAIN. It learned "citation present?" rather than "does the citation settle it?". That is exactly the lexical-shortcut failure the full design's matched counterfactuals exist to expose.
- **SafeGrad — anchored to base:** final train loss 2.07 vs 0.40 for SFT. Its solo outputs are word-for-word base outputs. Protecting the solo rows plus the KL pull toward the frozen reference kept it near base: it always UPDATEs.

## Fixes found on the way (keep for the full build)

1. **AuditKIT cache collision (would have faked results):** callables differing only in captured model objects share a fingerprint, so later models replay the first run's cached outputs. Fixed by capturing the checkpoint path (str) in a closure. Worth reporting upstream.
2. **AuditKIT `Metric.direction`** must be set at class creation (`type(...)`), not afterwards.
3. **Mac MPS cannot train this reliably:** GPU watchdog (`kIOGPUCommandBufferCallbackErrorImpactingInteractivity`). Pinned memory and padding made it worse; it was still random after fixing both. Use HF Jobs.
4. **SafeGrad needs ≥ 40 GB at batch 4** (reference model + 261k-vocab logits). Batch 2 fits; L40S queue was 16+ min, A100 started at once.

## Implications for the full build

- 80 template rows teach the format, not the warrant distinction. The full study needs far more and more varied training cases, especially valid citations phrased like unsupported ones and the reverse.
- SafeGrad's protected set must be chosen deliberately: solo rows plus KL to base mostly freezes the model. Try the retain/clarify rows as the protected objective, or a lower KL weight.
- Score answers semantically or constrain decoding, so format failures don't masquerade as behaviour.
- Add the cheap harnesses (evidence-aware prompting, entailment gate) before drawing any model comparison.

## Artifacts

`~/lexsi-koth/evtune/`: `build_data.py`, `curate.py`, `hf_job.py`, `data/`, `curated/`, `results/hf-run1/` (scorecard, AuditKIT runs with raw outputs, provenance). Private bucket `Mizore66/evtune-smoke`. Local MPS attempt: `train.py`, `run.sh`, `logs/`.
