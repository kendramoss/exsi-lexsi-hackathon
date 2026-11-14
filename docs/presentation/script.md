# 60-second spoken script

Spoken text only. [`scenes.json`](scenes.json) is the source of truth; [`check_kit.py`](check_kit.py) verifies the word count and timings. About 122 words, about 2 words a second.

| Time | Say |
|---|---|
| 0:00-0:07 | AI models give in when you argue. EvidenceTune changes its answer only when the quoted evidence supports it. |
| 0:07-0:21 | First, a historical comparison: plain training against EvidenceTune version six. Shown a wrong quote, plain training asked for the source 80 times out of 272. EvidenceTune asked 208 times. |
| 0:21-0:31 | In this chosen example, the quote is about returning copies, not rights. Plain training switches. EvidenceTune holds. |
| 0:31-0:47 | The released model is a later merge, alpha point seven five. On frozen proxy tests, recorded, it passes 222 of 240 semantic rows and 253 of 270 targeted rows, against 213 and 247 for version seven. |
| 0:47-1:00 | Scope: synthetic proxy tests only. Teacher labels had no human audit, by team decision. No safety, natural-text, Arabic, or general superiority claims. |

Delivery notes: "alpha point seven five" is spoken for alpha = 0.75. Say "version six" and "version seven" in full. Do not add numbers that are not in [`claims-sources.md`](claims-sources.md).

Status: no narration has been recorded. This is text only. No audio or video exists yet.
