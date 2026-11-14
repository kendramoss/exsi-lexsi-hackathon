# Parallel follow-up verification — 14 Nov 2026

## Scope and status

All four independent workflows completed and the integrated changes at `d2804aa` passed final read-only review. This branch builds on reviewed PR #34; it does not merge or deploy it.

1. Additional baseline and uncertainty evidence: published additively to the existing HF model repository at revision `093509bfc0b80096616d297b65fd8d908b04458b`. The selected adapter and all existing tensor hashes remain unchanged. The dataset and demo Space were not modified.
2. Merged-demo check: verifies seven pinned payload/data invariants and honestly reports absent merged-renderer browser coverage as **SKIP (not passed)**. Strict mode refuses the skip. The shipped historical frontend retains separate real browser tests.
3. Clean local environment: declared lightweight dependencies installed in a new venv without system site packages. See `offline-environment-2026-11-14.json` and `../offline-checks.md` for commands and input prerequisites.
4. Demo-day kit: 121 spoken words over 60 seconds, with matching scene/script/caption text, a storyboard, click checklist, and source-bound claims. No narration or video has been recorded.

## Coordinator's fresh integrated checks

| Suite | Passed tests |
|---|---:|
| Script validation, export safety and environment documentation guards | 39 |
| Teacher pipeline and resume/audit guards, fake clients only | 22 |
| Release and saved-evidence replay | 13 |
| Demo Python checks with explicit raw-evidence root | 6 |
| Presentation kit | 4 |
| Paired uncertainty | 11 |
| Raw-base analysis | 10 |
| Staging and additive-upload integrity | 18 |
| Synthetic CPU tensor interpolation | 8 |
| Annotation compatibility | 37 |
| Node payload mapping and merged-check negative controls | 13 |
| **Total** | **181** |

The shipped historical demo also passed **9 real-Chrome regression groups**, covering mobile evidence reachability, native keyboard/focus behavior, route provenance and offline requests. The standalone merged verifier passed its **7 data checks**, but its browser integration is explicitly absent and is not included as a browser pass.

The final independent reviewer separately reran focused analysis, documentation, staging, presentation and Node tests and found no blocking integration defects. They did not rerun all 181 tests as one command, remote HF downloads, or the historical Chrome suite; those checks are recorded from the coordinator and earlier independent lane reviews.

## Public verification

- All 22 uploaded files were anonymously downloaded and matched their prepared hashes.
- The remote manifest contains 768 entries and the checksum file 769 lines including the manifest.
- All six published LFS artifacts retain their recorded manifest hashes.
- The coordinator independently checked anonymous byte parity for the raw-base summary and uncertainty results, the selected-adapter lock, and HTTP 200 for cards, integrity files and both raw-base prediction files.
- Adapter SHA-256: `a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335`.
- `PUBLICATION-RESULTS.json` retains previous publication history and records the additional evidence revision.

## Limits and remaining steps

- The raw-base comparison is post-selection and descriptive, not a same-run controlled experiment or a general-capability measurement. Historical software pins are not retroactively assigned.
- Semantic all-five bootstrap and exact McNemar results are different estimands/tests; its bootstrap interval excludes zero but the exact case-level test is not conclusive. No multiplicity correction is claimed.
- Complete final raw-base predictions are public. Batch caches and most original runtime logs remain local; copied historical inventories are not claims that every listed cache was uploaded.
- One Python/macOS dependency resolution was tested; minimum-version, Windows/Linux, and air-gapped installations were not.
- No live model inference, teacher calls, training, human audit, main merge, deployment, or final form submission occurred.
- Remaining human actions: review/merge the feature PRs, record the screen/narration from `../presentation/`, and complete the final submission/freeze declaration.
