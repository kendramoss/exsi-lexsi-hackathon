#!/usr/bin/env python3
"""Validate two independent human exports and compute blind agreement metrics."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from annotation_lib import ValidationError, compare_exports, prepare_output_paths


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items", type=Path, required=True, help="Blind items.json")
    parser.add_argument("--assignment-a", type=Path, required=True)
    parser.add_argument("--assignment-b", type=Path, required=True)
    parser.add_argument("--a", type=Path, required=True, help="Complete export from annotator A")
    parser.add_argument("--b", type=Path, required=True, help="Complete export from annotator B")
    parser.add_argument("--output", type=Path, required=True, help="Report path inside annotation/")
    parser.add_argument("--overwrite", action="store_true",
                        help="Allow replacing an existing output; never allows input collisions")
    parser.add_argument("--allow-synthetic", action="store_true",
                        help="Synthetic unit tests only; report remains NOT_HUMAN")
    args = parser.parse_args()
    try:
        input_paths = [args.items, args.assignment_a, args.assignment_b, args.a, args.b]
        output = prepare_output_paths([args.output], input_paths, overwrite=args.overwrite)[0]
        report = compare_exports(
            read_json(args.a), read_json(args.b), read_json(args.items),
            read_json(args.assignment_a), read_json(args.assignment_b),
            allow_synthetic=args.allow_synthetic,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w" if args.overwrite else "x", encoding="utf-8") as handle:
            handle.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(f"Wrote {output}")
        print(f"Provenance: {report['provenance']}; rows: {report['row_count']}; "
              f"disagreements: {len(report['disagreement_rows'])}")
        for field in ("statement_truth", "citation_status", "answerability"):
            metric = report["fields"][field]
            kappa = "undefined" if metric["cohens_kappa"] is None else f"{metric['cohens_kappa']:.3f}"
            print(f"{field}: observed={metric['observed_agreement']:.3f}, kappa={kappa}")
        print(f"Action sets: exact={report['action_sets']['exact_agreement']:.3f}, "
              f"mean Jaccard={report['action_sets']['mean_jaccard']:.3f}")
    except (ValidationError, OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Agreement validation failed: {error}") from error


if __name__ == "__main__":
    main()
