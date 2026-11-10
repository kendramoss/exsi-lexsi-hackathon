# Issue #11: benign over-refusal after evidence fine-tuning

## Bottom line

**Original v6 did not increase proxy-measured over-refusal versus base overall: 53/750 (7.1%) versus 56/750 (7.5%), -0.4 pp.** The paired exact McNemar test gives p = 0.6072. This is an indication from a transparent automated proxy, not a validated human refusal rate. The similar overall rates do not establish equivalence.

Merged `alpha_0.75` recorded 54/750 (7.2%): -0.3 pp versus base and +0.1 pp versus original v6. The merged arm is **75% v7 + 25% v8**, not a scaling of original v6; it is a separate candidate comparison.

## Proxy refusal rates

Every rate below is **automated proxy-only**. The proxy is XSTest-style prefix matching with explicit English, Italian, and Korean patterns. An unmatched response is `non-refusal` for this metric, even if it is an empty, incoherent, or otherwise bad answer.

| Model | English | Italian | Korean | Overall |
|---|---:|---:|---:|---:|
| `base` | 19/250 (7.6%) | 16/250 (6.4%) | 21/250 (8.4%) | 56/750 (7.5%) |
| `v6` | 20/250 (8.0%) | 18/250 (7.2%) | 15/250 (6.0%) | 53/750 (7.1%) |
| `alpha_0.75` | 21/250 (8.4%) | 18/250 (7.2%) | 15/250 (6.0%) | 54/750 (7.2%) |

Wilson 95% intervals for overall proxy rates:

| Model | Refusals / n | Rate | Wilson 95% interval | Empty responses |
|---|---:|---:|---:|---:|
| `base` | 56/750 | 7.5% | 5.8%–9.6% | 0 |
| `v6` | 53/750 | 7.1% | 5.4%–9.1% | 0 |
| `alpha_0.75` | 54/750 | 7.2% | 5.6%–9.3% | 0 |

Paired transitions (same 750 prompts):

| Comparison | Left-only refusal | Right-only refusal | Delta | Exact McNemar p |
|---|---:|---:|---:|---:|
| `v6` − `base` | 6 | 9 | -0.4 pp | 0.6072 |
| `alpha_0.75` − `base` | 7 | 9 | -0.3 pp | 0.8036 |
| `alpha_0.75` − `v6` | 2 | 1 | +0.1 pp | 1 |

Per-language paired comparisons, confidence intervals, and category breakdowns are in `results/proxy_summary.json`; language rates are also in `results/proxy_rates.csv`. Statistical tests are exploratory and are not corrected for multiple language/category comparisons.

## Independent review sample

A second AI agent independently reviewed 90 responses while blind to proxy labels, using `review/RUBRIC.md`. It assigned 40 full/partial refusals, 1 nonanswers, and 0 unclear labels. Proxy/refusal agreement was 83/90; disagreements are listed in `review/review_summary.json`.

| Model | Full refusal | Partial refusal | Compliance | Nonanswer | Unclear |
|---|---:|---:|---:|---:|---:|
| `base` | 9 | 3 | 18 | 0 | 0 |
| `v6` | 11 | 4 | 15 | 0 | 0 |
| `alpha_0.75` | 10 | 3 | 16 | 1 | 0 |

The sample intentionally contains up to five proxy-positive and five proxy-negative responses per model/language cell. It is **not representative**, so its raw percentages must not be extrapolated to the full set. Reviewer labels are independent AI assessments, not human annotations or validated multilingual ground truth.

## Data provenance and counts

Only public rows labeled `safe` were evaluated: 250 per language, 25 in each of ten safe XSTest categories. No contrast/unsafe rows were evaluated and no prompts were authored or translated for this run.

| Language | Public source | Revision | Safe rows | Source SHA-256 | License/provenance note |
|---|---|---|---:|---|---|
| en | [paul-rottger/xstest](https://github.com/paul-rottger/xstest) | `d7bb5bd738c1fcbc36edd83d5e7d1b71a3e2d84d` | 250 | `11783fb294ed017473ee53c207d71f2161c7672c8d0b037501e78387f801cb5a` | CC BY 4.0 |
| it | [saiteki-kai/XSTest-IT](https://huggingface.co/datasets/saiteki-kai/XSTest-IT) | `849cea57e1978a52907d5f2efd3e5ab0edddbe5e` | 250 | `1ad76a4c5a024e31a5d6c1353c72806c6b249279fe2b1ef9004efcd1e17f8aef` | CC BY 4.0 (dataset card metadata) |
| ko | [heegyu/XSTest_ko](https://huggingface.co/datasets/heegyu/XSTest_ko) | `57f3f358bb2e4e71df68e47552e9fec002371d87` | 250 | `dfac6138883de5fd2385402afeb83306da520d27ae17d3c184c44cc8f30f7e52` | No license declared in dataset-card metadata; original English XSTest is CC BY 4.0 |

The Italian and Korean sets are third-party translations, not official multilingual releases. Alignment to the official English rows was checked programmatically; translation quality and semantic equivalence were not fully audited. Original XSTest: Röttger et al., NAACL 2024, [paper](https://aclanthology.org/2024.naacl-long.301/).

Frozen safe-only prompts: `data/prompts.jsonl`, SHA-256 `50971d9c97566e7f01d678251c2ac19eb99f0528c908623944c58245035adc42`. Full source details and per-category counts: `data/provenance.json`.

## Models and generation

- Base: `CohereLabs/tiny-aya-global`, revision `af89d219b53ed9b13b8a4645f9c8028973510324`.
- Original v6: `/Users/anasqumhiyeh/lexsi-koth/evtune/results/final/adapter_v6`, adapter SHA-256 `ba2a694b8cb0c1e3d429626335d011426187830c215738572553b39f4295956f`.
- Merged alpha 0.75: `/Users/anasqumhiyeh/lexsi-koth/evtune/merge_eval/adapters/alpha_0.75`, adapter SHA-256 `a329ed123fbb2da96d567492ff851b9880f71a5d59ae3be96a3ec2956f4ea335`; formula `0.75 * v7 + 0.25 * v8`.
- Local Apple MPS, bf16; PyTorch 2.15.0, Transformers 5.22.2, PEFT 0.21.2; no Aya Expanse 32B and no paid/external generation jobs.
- Native Tiny Aya chat template, one user message, no added system prompt; greedy decoding, 80 new tokens, batch size 8. All arms use the same base snapshot and prompts.
- The 80-token cap can truncate long compliant answers. Refusal-prefix detection usually occurs near the start, but answer quality was not evaluated.

## Limitations

1. **Automated detection is a proxy.** Prefixes can miss refusals and can false-positive compliant text. The independent sample assesses this only partially.
2. **No human multilingual validation.** The review agent is not a substitute for native-speaker annotation.
3. **Safe prompts only.** This run measures unnecessary refusal, not harmful compliance or safety improvement.
4. **One small model and one deterministic run.** Results do not establish behavior on Aya Expanse, sampling configurations, or other languages.
5. **Merged-arm interpretation.** `alpha_0.75` compares a v7/v8 interpolation against base and original v6; it is not a v6 ablation.

## Artifacts

- `results/raw_prompts_responses.jsonl`: all 2,250 prompt/response records with proxy fields.
- `results/responses/`: resume-safe raw generation batches.
- `results/proxy_summary.json`, `results/proxy_rates.csv`: counts, rates, confidence intervals, category breakdowns, paired comparisons.
- `review/blind_sample.csv`: reviewer input without proxy labels.
- `review/independent_review.csv`: independent labels and notes.
- `review/reviewed_sample.csv`: merged proxy/review sheet.
- `review/review_summary.json`: review counts, agreement, and disagreements.
- `scripts/`: data preparation, generation, scoring, review merge, and report rendering.

No GitHub issue comment, publication, external job, or edits outside `issue11_overrefusal/` were made.
