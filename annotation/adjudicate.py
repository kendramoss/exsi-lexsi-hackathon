#!/usr/bin/env python3
"""Prepare conflict-only human adjudication worksheets and merge validated decisions."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from annotation_lib import (
    ValidationError,
    decision_template,
    merge_adjudications,
    prepare_adjudication,
    prepare_output_paths,
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value, overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w" if overwrite else "x", encoding="utf-8") as handle:
        handle.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {path}")


def add_pair_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--items", type=Path, required=True, help="Blind items.json")
    parser.add_argument("--assignment-a", type=Path, required=True)
    parser.add_argument("--assignment-b", type=Path, required=True)
    parser.add_argument("--a", type=Path, required=True, help="Complete export from annotator A")
    parser.add_argument("--b", type=Path, required=True, help="Complete export from annotator B")
    parser.add_argument("--overwrite", action="store_true",
                        help="Allow replacing existing outputs; never allows input collisions")
    parser.add_argument("--allow-synthetic", action="store_true",
                        help="Synthetic unit tests only; outputs remain NOT_HUMAN")


def load_pair(args):
    return (read_json(args.a), read_json(args.b), read_json(args.items),
            read_json(args.assignment_a), read_json(args.assignment_b))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare", help="Write a disagreement queue and blank decision worksheet")
    add_pair_arguments(prepare)
    prepare.add_argument("--output", type=Path, required=True, help="Queue path inside annotation/")
    prepare.add_argument("--template-output", type=Path, required=True,
                         help="Blank decision worksheet path inside annotation/")
    merge = subparsers.add_parser("merge", help="Merge agreements with complete validated adjudications")
    add_pair_arguments(merge)
    merge.add_argument("--decisions", type=Path, required=True, help="Completed human decision worksheet")
    merge.add_argument("--output", type=Path, required=True, help="Merged output path inside annotation/")
    args = parser.parse_args()
    try:
        input_paths = [args.items, args.assignment_a, args.assignment_b, args.a, args.b]
        if args.command == "merge":
            input_paths.append(args.decisions)
        output_paths = [args.output]
        if args.command == "prepare":
            output_paths.append(args.template_output)
        resolved_outputs = prepare_output_paths(output_paths, input_paths, overwrite=args.overwrite)
        args.output = resolved_outputs[0]
        if args.command == "prepare":
            args.template_output = resolved_outputs[1]
        a, b, items, assignment_a, assignment_b = load_pair(args)
        if args.command == "prepare":
            queue = prepare_adjudication(a, b, items, assignment_a, assignment_b,
                                         allow_synthetic=args.allow_synthetic)
            write_json(args.output, queue, overwrite=args.overwrite)
            write_json(args.template_output, decision_template(queue, synthetic=args.allow_synthetic),
                       overwrite=args.overwrite)
            print(f"Disagreements requiring human adjudication: {len(queue['disagreements'])}")
            print("Fill every blank decision and rationale. For human work, set a real adjudicator ID "
                  "and change human_attestation to true only after independent human review.")
        else:
            merged = merge_adjudications(a, b, items, assignment_a, assignment_b,
                                         read_json(args.decisions), allow_synthetic=args.allow_synthetic)
            write_json(args.output, merged, overwrite=args.overwrite)
            adjudicated = sum(row["merge_provenance"] == "ADJUDICATED" for row in merged["rows"])
            print(f"Merged {len(merged['rows'])} rows: {adjudicated} adjudicated, "
                  f"{len(merged['rows']) - adjudicated} agreements. Provenance: {merged['provenance']}")
    except (ValidationError, OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Adjudication validation failed: {error}") from error


if __name__ == "__main__":
    main()
