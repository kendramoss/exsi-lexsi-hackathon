# EvidenceTune v3 — SafeGrad fixed — 3 Nov 2026

**Verdict: SafeGrad collapsed because of a scaling bug in SafeTune's KL alignment loss, not because of its method. With the loss fixed and SafeTune's refusal set protected, SafeGrad matches ordinary SFT on the task (61/64 matched pairs). Whether it preserves Aya's refusals better than SFT, which is the point of using it, is not yet measured.**

Run: HF Job `evtune-v3` (A100, ~64 min, ~$2.70). Same v2 data, seed and hparams; base and SFT rows come from the v2 run (generation is deterministic across jobs). Outputs: `results/hf-v3/`.

## Root cause (safegrad_fix.py)

SafeTune 0.1.8 `safegrad_kl_alignment_loss` calls `F.kl_div(..., reduction="batchmean")` on `(batch, seq, vocab)` logits. `batchmean` divides by batch size only, so KL is **summed over every position, padding included**. Unit check: original loss = per-token KL × seq_len exactly. Against a per-token-mean task loss with `rho=1`, the alignment gradient was ~1,000× too large at max_len 1024. After clipping it erased the task signal (v2: loss stuck ~2, grad norms 277–1,178).

Fix (monkeypatch in our job; SafeTune repo untouched): KL averaged over non-pad tokens. Training is now healthy: task loss 0.75 → 0.05, grad norms < 1.1, KL to reference 0.045 → 0.011 (solo set) and 0.008 → 0.001 (refusal set).

**Upstream report candidate:** affects every SafeGrad KL-mode user; worse with longer `max_len`.

## Dev results (64 held-out cases, 320 rows; one seed)

| | Base | Ordinary SFT | SafeGrad, solo protected (fixed) | SafeGrad, refusal protected (fixed) |
|---|---:|---:|---:|---:|
| Matched pairs handled | 1/64 | 61/64 | 44/64 | **61/64** |
| — lexical traps | 1/32 | 31/32 | 19/32 | 30/32 |
| Valid uptake | — | 63/64 | 53/64 | 63/64 |
| Unwarranted change (toward / away / pressure) | 64/64/64 | 3/3/0 | 15/14/0 | 3/2/0 |
| Solo accuracy | 10/64 | 56/64 | 40/64 | 56/64 |
| Format followed | 13% | 100% | 96% | 100% |

v2 SafeGrad (unfixed, solo protected): 2/64 pairs, all RETAIN.

## Reading

- **The fix works:** solo-protected SafeGrad went from 2/64 to 44/64 pairs.
- **The protected set matters:** keeping base Aya's own solo behaviour (wrong format, 10/64 correct) still drags the task down. That's a bad thing to protect, and it's dropped.
- **Refusal-protected SafeGrad ties SFT on the task** (61/64 both, solo 56/64 both, unwarranted changes 5 vs 6 of 192). So the hardening has no task cost here.
- The same in-template caveat as v2 applies: a per-template bag-of-words control gets 55/64.

## What's still missing for the "hardened vs ordinary fine-tuning" claim (brief #5)

A retention eval: refusal/safety behaviour on a **public** multilingual red-team set (CohereLabs/aya_redteaming is cached locally; no new harmful prompts authored) for base vs SFT vs SafeGrad-refusal. If SFT erodes Aya's refusals and SafeGrad doesn't, SafeTune earns its place in the chain. If both preserve them, SafeGrad is a no-cost safeguard but not a measured win.

## Files

`safegrad_fix.py` (patch + unit check), `hf_job_v3.py`, `jobpack3/`, `results/hf-v3/`, `analyze_v2.py` (now takes run dir and model list).
