# EvidenceTune — Lexsi Hackathon Track 2

A three-person project building a lexical-controlled safety benchmark and SafeTune-trained Aya adapter for evidence-sensitive correction.

EvidenceTune teaches and evaluates when a model should accept supported feedback, resist unsupported correction, or request clarification while preserving final task utility.

**Official fit:** Track 2a #2 (safety benchmark), with Track 2b #5 (safety-hardened versus ordinary fine-tuning) as the secondary comparison.

**Pipeline:** CuratorKIT → SafeTune → AuditKIT.

## Project documents

- [Research specification](SPEC.md)
- [Written execution plan](PLAN.md)
- [Task backlog](BACKLOG.md)

### Task categories

- **Data & Annotation** — sources, counterfactuals, independent labels, Arabic quality, and CuratorKIT.
- **ML & Evaluation** — Aya runners, SafeTune, baselines, AuditKIT, and analysis.
- **Frontend & Design** — demo experience, visual communication, and presentation.
