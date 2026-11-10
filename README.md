# EvidenceTune — Lexsi Hackathon Track 2

A three-person project building a lexical-controlled safety benchmark and SafeTune-trained Aya adapter for evidence-sensitive correction.

EvidenceTune teaches and evaluates when a model should accept supported feedback, resist unsupported correction, or request clarification while preserving final task utility.

**Official fit:** Track 2a #2 (safety benchmark), with Track 2b #5 (safety-hardened versus ordinary fine-tuning) as the secondary comparison.

**Pipeline:** CuratorKIT → SafeTune → AuditKIT.

## See the demo live

**[Open the live demo →](https://raw.githack.com/kendramoss/exsi-lexsi-hackathon/feat/demo-redesign/demo/index.html)**

No install needed: this link serves `demo/` straight from the `feat/demo-redesign` branch, so it always shows the latest pushed design and layout (allow a few minutes after a push for it to refresh). The default is the verified, recorded-only merged α=0.75 comparison in `demo/data/results/merged-alpha-075/merged.json`. The separate historical mock is available explicitly with `?run=mock-smoke` and is invented, not current model evidence.

To run it on your own machine instead:

```sh
cd demo
python -m http.server 8000
# then open http://localhost:8000
```

## Project documents

- [Research specification](SPEC.md)
- [Written execution plan](PLAN.md)
- [Task backlog](BACKLOG.md)

### Task categories

- **Data & Annotation** — sources, counterfactuals, independent labels, Arabic quality, and CuratorKIT.
- **ML & Evaluation** — Aya runners, SafeTune, baselines, AuditKIT, and analysis.
- **Frontend & Design** — demo experience, visual communication, and presentation.
