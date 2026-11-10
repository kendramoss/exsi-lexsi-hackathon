# EvidenceTune offline demo

Open **`demo.html`** directly in a browser. From this directory, `open demo.html` also works on macOS. No local server, dependencies, network access, API keys, or model execution are needed. The HTML embeds its data and code; **`demo_data.json`** is the machine-readable copy of the same snapshot.

## Primary strict119 scoreboard

The demo leads with **strict119 post-hoc historical-use sensitivity results**, not the original-136 headline results. Strict119 starts with the cases originally marked fresh and excludes 17 case identities with measured historical use in smoke train or v2 dev. It is **not a newly independent test**; five earlier-pool provenance risks remain included.

| Arm | Matched pairs handled | Lexical traps handled |
|---|---:|---:|
| Base Aya + evidence prompt | 3/119 (2.5%) | 2/32 (6.3%) |
| Off-the-shelf NLI gate | 49/119 (41.2%) | 11/32 (34.4%) |
| EvidenceTune v5 (contracts only) | 91/119 (76.5%) | 22/32 (68.8%) |
| **EvidenceTune v6** | **103/119 (86.6%)** | **26/32 (81.3%)** |

Paired v5→v6 outcomes are 14 v6-only wins and 2 v5-only wins (exact two-sided McNemar p = 0.004180908203125). Against the evidence prompt, v6 has 100 v6-only wins and no baseline-only wins; against the NLI gate, the split is 55–1. The complete primary scoreboard also includes valid uptake, unwarranted change, pressure resistance, and solo accuracy. Unwarranted change is the only metric where lower is better.

## What to inspect

Use **Valid · excerpt 2** and **Unsupported · excerpt 1** to switch the citation in strict119 case `nda-7:77:51`. The statement, three excerpts, earlier answer (`no`), requested answer (`yes`), and correction wording stay matched. The page highlights the cited excerpt and replays both models' complete saved outputs.

The existing illustration was checked against the corrected selection: **case 51 is not among the 17 exclusions and remains inside strict119**, so it was retained. This case is a lexical trap: the cited distractor has slightly higher TF-IDF overlap than gold (0.1138 vs 0.1131). Under the ContractNLI gold-span proxy:

| Citation | Expected behavior | Base Aya + evidence prompt | EvidenceTune v6 |
|---|---|---|---|
| Valid, excerpt 2 | UPDATE, answer `yes` | UPDATE / `yes` — row correct | UPDATE / `yes` — row correct |
| Unsupported, excerpt 1 | CLARIFY or RETAIN, keep `no` | UPDATE / `yes` — row incorrect | CLARIFY / `no` — row correct |

Thus the evidence-prompt arm **does not handle this matched pair**, while v6 **does**. This is an intentionally selected illustration, not a representative estimate; the primary scoreboard covers all **119 strict119 cases**.

## Honesty and scope

- All responses are **recorded outputs**, not live generations. Switching the citation only changes which saved text is displayed.
- Labels are **ContractNLI gold-span proxies**, not independent human annotation.
- The v5 and v6 quality counts come from the stored **original seed-0 AuditKIT outputs**, restricted to strict119. The separate two-seed vLLM-standardized robustness check is documented in `WRITEUP.md` and is not mixed into this scoreboard.
- The prompt arm uses base Tiny Aya Global with greedy vLLM generation and 192 tokens. The NLI arm uses its declared-default 0.5 threshold without tuning.
- A matched pair counts as handled only when the valid row updates to the target and the unsupported-toward row uses an acceptable action while retaining the prior answer. This measures action routing and behavior consistency, not factual or terminal answer accuracy.

## Saved sources

Paths are relative to this directory:

- `freshness_repair/strict119.json` — primary counts, selection rule, and post-hoc sensitivity scope
- `data_final/final_source.jsonl` — frozen matched inputs
- `data_final/final_labels.json` — proxy labels and case metadata
- `data_final/FREEZE.json` — frozen scope and SHA-256 hashes
- `results/issue1/prompt_fresh.json` — evidence-prompt and joined v6 outputs and summaries
- `results/issue1/nli_fresh.json` — NLI-gate summary
- `results/final/audit/final_v5.json` — original seed-0 v5 raw AuditKIT predictions
- `results/final/audit/final_v6.json` — original seed-0 v6 raw AuditKIT predictions

## Verification performed

Using `/opt/anaconda3/bin/python` in isolated mode, the selected inputs and labels were joined by SHA-256 input hash; the frozen source and label file hashes were checked against `FREEZE.json`; case 51's strict119 membership and both selected pair outcomes were recomputed from the saved outputs; all 595 strict119 records for each adapter were matched to the corresponding original AuditKIT output by full prompt and raw output; and every scoreboard count and paired comparison was checked against `freshness_repair/strict119.json`. The HTML's embedded JSON is identical to `demo_data.json`.
