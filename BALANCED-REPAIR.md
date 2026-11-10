# Balanced dialogue-repair spike — 11 Nov 2026

**Decision: KILL_KEEP_MERGED. Retain merged alpha=0.75.** The balanced candidate still over-clarified and failed all three early-stop limits. No frozen evaluation, full-dev selection, or public model replacement occurred.

## Protocol

- 40 Contradiction cases / 200 rows, 40 Entailment cases / 200 rows (16 new + 12 replay + 12 other training controls), and the complete v8 training-only two-turn projection of 32 rows across four case families.
- Exact roster SHA-256: `e542fcbad26844d1ddca60be4d40010b1519cdaaa0f38a258289f38f16bfe017`. Four semantically invalid candidates were excluded; replacement `sc-05-11` passed exact-roster review.
- Freshness/deduplication passed and deterministic rebuild matched all 432 rows and labels. Labels remain synthetic proxies.
- Started from merged alpha=0.75 (`a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335`). PlainSFT, seed 0, one epoch, lr 5e-5, batch 1, accumulation 4, max length 1,024, fp16, gradient checkpointing.
- Kaggle script `368124540` completed 108/108 optimizer steps. Total runtime: 2,620.755 seconds (43m41s).
- Candidate adapter SHA-256: `cca5c7b900a834c73d617188bbc211930f0c0b000f4cbb5e018e317797321f28`.

## Early-gate results

| Metric | Limit | Candidate | Result |
|---|---:|---:|---|
| Unnecessary clarification | <=6.25% | **12.50% (4/32)** | FAIL |
| Follow-up model calls | <=28 | **62** | FAIL |
| Unsupported-citation clarification | <=18.75% | **48.4375% (31/64)** | FAIL |

Resolution records: 128/128 complete, zero errors. Resolution overall was 46/62 = 74.1935%, final dialogue task accuracy 101/128 = 78.90625%, and fully resolved cases 9/32. The early KILL correctly prevented full semantic/targeted dev evaluation; no baseline-comparison deltas were computed.

## Interpretation

Adding balanced Entailment data and the small two-turn replay set did not correct over-clarification. The candidate still produces many more follow-ups with weaker dialogue utility. Do not proceed to independent confirmation and do not replace the public adapter.

## Evidence

Artifacts under `.balanced_spike/run/368124540/`:

- `metrics_digest.json` — early/full gate status and candidate metrics
- `artifact_hashes.json` — downloaded artifact hashes
- `status.json` — terminal worker state
- `run/version3_final.log` — worker log
- Preregistration SHA-256: `ab3a628ab5af149bd487a92a96de0d013ed26d17e5d0a7b989b1f37bf97dc015`

Final adapter and raw resolution records remain. Generated full-model/optimizer duplicates may be removed for disk thinning without affecting this evidence.
