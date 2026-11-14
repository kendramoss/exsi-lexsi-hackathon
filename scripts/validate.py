"""Validate cases / predictions / metrics against the JSON Schemas in schemas/.

Usage:
  python scripts/validate.py                       # examples + demo mock run
  python scripts/validate.py results/<run_id>      # a run dir with cases.jsonl, predictions.jsonl, metrics.json
  python scripts/validate.py --cases path/to/cases.jsonl

Exit code 1 if anything fails. Needs: pip install jsonschema
"""

import json
import sys
from collections import Counter
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
    for path in (cases_p, preds_p, metrics_p):
        if not path.is_file():
            errors.append(f"{rel(run_dir)}: missing required file: {path.name}")
    if errors:
        return errors

    errors += check_records(cases_p, "case.schema.json")
    errors += check_records(preds_p, "run.schema.json")
    metrics = json.loads(metrics_p.read_text(encoding="utf-8"))
    errors += [f"{rel(metrics_p)} {'/'.join(map(str, e.absolute_path))}: {e.message}"
               for e in validator("metrics.schema.json").iter_errors(metrics)]
    if errors:
        # Cross-file checks below rely on schema-valid keys and values.
        return errors

    # A completed run has exactly one prediction per declared case and policy.
    cases = [r for _, r in read_jsonl(cases_p)]
    preds = [r for _, r in read_jsonl(preds_p)]
    case_counts = Counter(c["case_id"] for c in cases)
    policy_counts = Counter(c["id"] for c in metrics["comparators"])
    ids, policies = set(case_counts), set(policy_counts)
    errors += [f"cases: duplicate case_id {key!r}" for key, n in case_counts.items() if n > 1]
    errors += [f"metrics: duplicate comparator {key!r}" for key, n in policy_counts.items() if n > 1]
    if metrics["dataset"]["n_cases"] != len(cases):
        errors.append(f"metrics: dataset.n_cases {metrics['dataset']['n_cases']} != cases count {len(cases)}")
    if not preds:
        errors.append("predictions: no records in completed run")
    expected_count = len(cases) * len(policies)
    if len(preds) != expected_count:
        errors.append(f"predictions: count {len(preds)} != cases x comparators {expected_count}")

    keys = Counter((r["case_id"], r["policy"]) for r in preds)
    errors += [f"predictions: duplicate case/policy {key!r}" for key, n in keys.items() if n > 1]
    coverage = {policy: set() for policy in policies}
    for r in preds:
        if r["policy"] not in policies:
            errors.append(f"predictions: policy {r['policy']!r} has no comparator in metrics.json")
        else:
            coverage[r["policy"]].add(r["case_id"])
        if r["run_id"] != metrics["run_id"]:
            errors.append(f"predictions: run_id {r['run_id']!r} != metrics run_id {metrics['run_id']!r}")
        if r["case_id"] not in ids:
            errors.append(f"predictions: unknown case_id {r['case_id']!r}")
    for policy in sorted(policies):
        missing = ids - coverage[policy]
        if missing:
            errors.append(f"predictions: policy {policy!r} missing {len(missing)} case(s): {sorted(missing)!r}")
    for c in cases:
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
