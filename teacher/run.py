"""Command line for the teacher-labelling pipeline (see teacher/README.md).

  python teacher/run.py label        KIT --out DIR      # teacher labels -> DIR/raw_labels.jsonl (resumable)
  python teacher/run.py judge        KIT --out DIR      # judge conflicts -> DIR/judgements.jsonl
  python teacher/run.py report       KIT --out DIR      # tiers, agreement -> labels.jsonl, report.{json,md}
  python teacher/run.py audit-sample KIT --out DIR --n 15 --seed S   # blind rows for human audit
  python teacher/run.py audit-score  KIT --out DIR --human EXPORT.json
  python teacher/run.py export-train KIT --out DIR      # refuses evaluation-only kits

KIT is a task.v2 kit directory holding items.json (and manifest.json), e.g. annotation/pilot.
`label` and `judge` run teachers through a local headless Claude Code CLI (`claude -p`), using its
existing login: no API key and no SDK. The other commands are offline.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline as P  # noqa: E402


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def append_jsonl(path: Path, recs) -> int:
    n = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for r in recs:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            fh.flush()
            n += 1
    return n


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build(kit, out: Path, teachers):
    records = read_jsonl(out / "raw_labels.jsonl")
    rows, conflicts, by_row, invalid = P.consensus(kit, records, teachers)
    P.apply_judgements(rows, conflicts, read_jsonl(out / "judgements.jsonl"))
    return rows, conflicts, by_row, invalid


def write_audit_kit(kit, ids: list[str], seed: str, audit_dir: Path) -> int:
    """A blind offline audit kit for the sampled rows: items, one assignment, the kit's own
    annotate.html and a manifest. It holds no teacher labels, tiers or rationales."""
    import random
    sys.path.insert(0, str(P.ROOT / "annotation"))
    import build_kit
    from annotation_lib import dataset_digest
    wanted = set(ids)
    items = [it for it in kit.items if it["row_id"] in wanted]
    doc = {"schema_version": kit.items_doc["schema_version"], "dataset_id": f"{kit.dataset_id}-teacher-audit",
           "dataset_sha256": dataset_digest(items), "fresh": kit.items_doc["fresh"], "items": items}
    assignments = []
    for letter in ("a", "b"):  # two independent auditors, each with their own row order
        order = [it["row_id"] for it in items]
        random.Random(f"{seed}-order-{letter}").shuffle(order)
        asg = {k: doc[k] for k in ("schema_version", "dataset_id", "dataset_sha256", "fresh")}
        asg.update(assignment_id=f"assignment-{letter}", annotator_id=f"auditor-{letter}", order=order)
        assignments.append(asg)
    manifest = {"kind": "blind human audit of teacher labels", "source_dataset_id": kit.dataset_id,
                "dataset_id": doc["dataset_id"], "rows": len(items), "seed": seed, "pipeline": P.PIPELINE_VERSION,
                "selection": "every judge-adjudicated and needs-human row plus a seeded sample of consensus rows",
                "blinding": "items only: no teacher labels, tiers or rationales"}
    artifacts = build_kit.make_artifacts(doc, assignments, manifest)
    audit_dir.mkdir(parents=True, exist_ok=True)
    for name, text in artifacts.items():
        (audit_dir / name).write_text(text, encoding="utf-8")
    return len(items)


def report_md(rep: dict) -> str:
    L = [f"# Teacher-label report: `{rep['dataset_id']}`", "",
         f"Labels by {', '.join(f'`{t}`' for t in rep['teachers'])} (pipeline `{P.PIPELINE_VERSION}`). "
         "These are **teacher-model labels, not human labels** (`human_attestation: false`)."
         + (" This kit is **evaluation-only**: its labels must not be used for training." if rep["evaluation_only"] else ""), "",
         "## Tiers", "", "| Tier | Rows |", "|---|---:|"]
    L += [f"| `{t}` | {n} |" for t, n in sorted(rep["tiers"].items())]
    L += ["", f"Low-confidence rows (UNDETERMINED truth or UNCLEAR answerability): {rep['low_confidence_rows']}.", ""]
    if rep["fields"]:
        L += ["## Teacher agreement (modal labels)", "", f"Over {rep['rows_with_all_teachers']} rows labelled by every teacher. "
              f"All fields agree on {rep['all_fields_agreement']:.1%}.", "", "| Field | Agreement | Cohen's κ |", "|---|---:|---:|"]
        L += [f"| {f} | {v['agreement']:.1%} | {'undefined' if v['cohens_kappa'] is None else v['cohens_kappa']} |"
              for f, v in rep["fields"].items()]
        L.append("")
    L += ["## Self-consistency", "", "Share of a teacher's samples that match its own modal label, averaged over rows.", ""]
    L += [f"- `{t}`: {v}" for t, v in rep["self_consistency"].items()]
    L += ["", "## Contract-gate failures", ""]
    L += [f"- {k}: {v}" for k, v in rep["invalid_samples"].items()] or ["- none"]
    if rep.get("audit"):
        L += ["", "## Blind human audit", "", "| Tier | Audited | Exact match | Wilson 95% |", "|---|---:|---:|---|"]
        L += [f"| `{t}` | {a['n']} | {a['exact_match_rate']:.1%} | {a['exact_match_wilson95']} |" for t, a in rep["audit"].items()]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["label", "judge", "report", "audit-sample", "audit-score", "export-train"])
    ap.add_argument("kit", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--guide", type=Path, help="annotation guide (default: the kit's ANNOTATION-GUIDE.md)")
    ap.add_argument("--teachers", nargs="+", default=list(P.DEFAULT_TEACHERS))
    ap.add_argument("--judge-model", default=P.DEFAULT_JUDGE)
    ap.add_argument("--samples", type=int, default=2)
    ap.add_argument("--effort", default="high", choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--workers", type=int, default=4, help="parallel claude processes")
    ap.add_argument("--limit", type=int, help="label: only the first N rows (trial runs)")
    ap.add_argument("--claude-bin", default="claude", help="path to the Claude Code CLI")
    ap.add_argument("--n", type=int, default=15, help="audit-sample: consensus rows to sample")
    ap.add_argument("--seed", default="teacher-audit-v1")
    ap.add_argument("--human", type=Path, help="audit-score: a kit export JSON with human annotations")
    ap.add_argument("--kit-out", type=Path, help="audit-sample: where to write the blind audit kit (default OUT/audit)")
    a = ap.parse_args(argv)
    kit = P.Kit.load(a.kit, a.guide)
    out = a.out
    runner = P.ClaudeCLI(a.claude_bin)

    if a.command == "label":
        # Transient failures (the call or the CLI itself failed) are dropped and retried; contract
        # failures and refusals are kept: they are real outcomes and count in the report.
        transient = ("call failed", "cli: error")
        kept = [r for r in read_jsonl(out / "raw_labels.jsonl") if r.get("invalid_reason") not in transient]
        if (out / "raw_labels.jsonl").exists():
            (out / "raw_labels.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept), encoding="utf-8")
        done = {r["key"] for r in kept}
        n = append_jsonl(out / "raw_labels.jsonl",
                         P.label_rows(kit, runner, a.teachers, a.samples, a.effort, done, a.workers, a.limit))
        print(f"{n} new label record(s) in {out / 'raw_labels.jsonl'}")
        return 0

    if a.command == "judge":
        rows, conflicts, *_ = build(kit, out, a.teachers)
        judged = {j["row_id"] for j in read_jsonl(out / "judgements.jsonl")}
        todo = {r: c for r, c in conflicts.items() if r not in judged}
        n = append_jsonl(out / "judgements.jsonl", P.judge_rows(kit, runner, todo, a.judge_model, a.effort, a.workers))
        print(f"{n} judgement(s); {len(conflicts)} conflicting row(s) in total")
        return 0

    rows, conflicts, by_row, invalid = build(kit, out, a.teachers)
    labels = P.label_records(kit, rows, a.teachers)

    if a.command == "report":
        rep = P.agreement_report(kit, rows, by_row, invalid, a.teachers)
        audit = out / "audit_score.json"
        if audit.exists():
            rep["audit"] = json.loads(audit.read_text(encoding="utf-8"))
        (out / "labels.jsonl").write_text("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in labels), encoding="utf-8")
        write_json(out / "rows.json", rows)
        write_json(out / "report.json", rep)
        (out / "report.md").write_text(report_md(rep), encoding="utf-8")
        print(report_md(rep))
        return 0

    if a.command == "audit-sample":
        ids = P.audit_sample(rows, a.n, a.seed)
        audit_dir = a.kit_out or (out / "audit")
        n = write_audit_kit(kit, ids, a.seed, audit_dir)
        print(f"{n} audit row(s) -> {audit_dir}/annotate.html (blind: items only, no teacher labels)")
        return 0

    if a.command == "audit-score":
        export = json.loads(a.human.read_text(encoding="utf-8"))
        if export.get("annotation_origin") != "human_attested" or not export.get("human_attestation"):
            sys.exit("audit-score needs a human-attested export; model labels cannot audit model labels")
        if P.looks_like_model(export.get("annotator_id", "")):
            sys.exit(f"audit-score: annotator_id {export.get('annotator_id')!r} names a model; "
                     "model labels cannot audit model labels")
        items = {it["row_id"]: it for it in kit.items}
        human = {an["row_id"]: P.validate_annotation(an, items[an["row_id"]]) for an in export["annotations"]}
        score = P.audit_score(labels, human)
        write_json(out / "audit_score.json", score)
        print(json.dumps(score, indent=2))
        return 0

    if a.command == "export-train":
        try:
            train = P.training_export(kit, labels)
        except PermissionError as e:
            print(f"REFUSED: {e}")
            return 2
        (out / "train_labels.jsonl").write_text("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in train), encoding="utf-8")
        print(f"{len(train)} training label(s) -> {out / 'train_labels.jsonl'}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
