"""Validate cases / predictions / metrics against the JSON Schemas in schemas/.

Usage:
  python scripts/validate.py                       # examples + demo mock run
  python scripts/validate.py results/<run_id>      # a run dir with cases.jsonl, predictions.jsonl, metrics.json
  python scripts/validate.py --cases path/to/cases.jsonl

Exit code 1 if anything fails. Needs: pip install jsonschema
"""

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "schemas"
BASE = "https://github.com/kendramoss/exsi-lexsi-hackathon/schemas/"


def load_registry():
    reg = Registry()
    for p in SCHEMAS.glob("*.schema.json"):
        reg = reg.with_resource(BASE + p.name, Resource.from_contents(json.loads(p.read_text(encoding="utf-8"))))
    return reg


REGISTRY = load_registry()


def validator(name):
    schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
    return Draft202012Validator(schema, registry=REGISTRY, format_checker=FormatChecker())


def rel(path):
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path


def read_jsonl(path):
    out = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            out.append((i, json.loads(line)))
    return out


def check_records(path, schema_name):
    v = validator(schema_name)
    errors = []
    for line, rec in read_jsonl(path):
        for e in v.iter_errors(rec):
            loc = "/".join(str(x) for x in e.absolute_path) or "(root)"
            errors.append(f"{rel(path)}:{line} {loc}: {e.message}")
    return errors


def check_run(run_dir):
    errors = []
    cases_p, preds_p, metrics_p = run_dir / "cases.jsonl", run_dir / "predictions.jsonl", run_dir / "metrics.json"
    if cases_p.exists():
        errors += check_records(cases_p, "case.schema.json")
    errors += check_records(preds_p, "run.schema.json")
    metrics = json.loads(metrics_p.read_text(encoding="utf-8"))
    errors += [f"{rel(metrics_p)} {'/'.join(map(str, e.absolute_path))}: {e.message}"
               for e in validator("metrics.schema.json").iter_errors(metrics)]

    # Cross-file checks the schemas can't express.
    preds = [r for _, r in read_jsonl(preds_p)]
    policies = {c["id"] for c in metrics.get("comparators", [])}
    for r in preds:
        if r.get("policy") not in policies:
            errors.append(f"predictions: policy {r.get('policy')!r} has no comparator in metrics.json")
        if r.get("run_id") != metrics.get("run_id"):
            errors.append(f"predictions: run_id {r.get('run_id')!r} != metrics run_id {metrics.get('run_id')!r}")
    if cases_p.exists():
        ids = {c["case_id"] for _, c in read_jsonl(cases_p)}
        errors += [f"predictions: unknown case_id {r['case_id']!r}" for r in preds if r["case_id"] not in ids]
        for _, c in read_jsonl(cases_p):
            if c["case_id"] != f"{c['family_id']}__{c['feedback_condition']}":
                errors.append(f"cases: {c['case_id']} does not follow <family_id>__<feedback_condition>")
    return errors


def main(argv):
    errors = []
    if not argv:
        errors += check_records(SCHEMAS / "examples" / "cases.example.jsonl", "case.schema.json")
        errors += check_records(SCHEMAS / "examples" / "predictions.example.jsonl", "run.schema.json")
        errors += check_run(ROOT / "demo" / "data" / "results" / "mock-smoke")
    elif argv[0] == "--cases":
        errors += check_records(Path(argv[1]).resolve(), "case.schema.json")
    else:
        errors += check_run(Path(argv[0]).resolve())
    for e in errors:
        print("FAIL", e)
    print("OK" if not errors else f"{len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
