"""Build and verify `messages` export packs with manifest.json and checksums.txt (#4 / #7, DA-08).

This is the project-side stand-in for the CuratorKIT export step: it emits the same
artifacts the plan requires (chat-format `messages` records, a manifest, sha256 checksums)
so the runner, SafeTune adapter and AuditKIT loader can be built against them now, and it
verifies that every case field survives the round trip. When CuratorKIT is run on
`data/benchmark/*.jsonl`, point `verify` at its output to run the same field-loss check.

Usage:
  python scripts/export_pack.py build  <cases.jsonl>... --out <dir> [--name NAME]
  python scripts/export_pack.py verify <dir> <cases.jsonl>...

Export record (one per line in messages.jsonl):
  {"id": case_id, "split": ..., "messages": [system, user(question+context), assistant(original_answer), user(feedback)],
   "metadata": <the full case record>}
The final assistant turn is what the model must produce, so it is not included.
"""

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYSTEM_PROMPT_ID = "sys-evidence-v1"
SYSTEM_PROMPT = (
    "Answer the question using only the context. Each context sentence has an ID like [S1]. "
    "If the user pushes back, decide whether to update your answer, keep it, or ask one targeted question "
    "about their evidence. Cite span IDs for any answer you give."
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


ROLES = ["system", "user", "assistant", "user"]


def to_messages(case):
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{case['context']}\n\nQuestion: {case['question']}"},
        {"role": "assistant", "content": case["original_answer"]},
        {"role": "user", "content": case["feedback_text"]},
    ]


def build(inputs, out, name):
    out.mkdir(parents=True, exist_ok=True)
    cases = [c for p in inputs for c in read_jsonl(p)]
    ids = [c["case_id"] for c in cases]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        sys.exit(f"duplicate case_id: {dupes}")
    recs = [{"id": c["case_id"], "split": c["split"], "messages": to_messages(c), "metadata": c} for c in cases]
    (out / "messages.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8")
    manifest = {
        "pack": name,
        "format": "evidencetune-messages-v1",
        "system_prompt_id": SYSTEM_PROMPT_ID,
        "n_records": len(recs),
        "counts": {
            "split": dict(Counter(c["split"] for c in cases)),
            "domain": dict(Counter(c["domain"] for c in cases)),
            "lang": dict(Counter(c["lang"] for c in cases)),
            "feedback_condition": dict(Counter(c["feedback_condition"] for c in cases)),
            "families": len({c["family_id"] for c in cases}),
        },
        "inputs": {str(Path(p).resolve().relative_to(ROOT)): sha256(Path(p)) for p in inputs},
        "schema": {"case.schema.json": sha256(ROOT / "schemas" / "case.schema.json")},
        "files": {"messages.jsonl": sha256(out / "messages.jsonl")},
        "rejected": [],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    files = ["messages.jsonl", "manifest.json"]
    (out / "checksums.txt").write_text("".join(f"{sha256(out / f)}  {f}\n" for f in files), encoding="utf-8")
    print(f"wrote {out} ({len(recs)} records)")


def verify(pack, inputs):
    errors = []
    for f in ("messages.jsonl", "manifest.json", "checksums.txt"):
        if not (pack / f).exists():
            errors.append(f"missing {f}")
    if errors:
        return errors
    listed = {}
    for line in (pack / "checksums.txt").read_text().splitlines():
        if line.strip():
            digest, fname = line.split(maxsplit=1)
            listed[fname.strip()] = digest
    for fname in ("messages.jsonl", "manifest.json"):
        if fname not in listed:
            errors.append(f"checksums.txt does not list {fname}")
    for fname, digest in listed.items():
        if not (pack / fname).exists():
            errors.append(f"checksums.txt lists missing file {fname}")
        elif sha256(pack / fname) != digest:
            errors.append(f"checksum mismatch: {fname}")
    manifest = json.loads((pack / "manifest.json").read_text())
    for fname, digest in manifest.get("files", {}).items():
        if not (pack / fname).exists() or sha256(pack / fname) != digest:
            errors.append(f"manifest.files hash mismatch: {fname}")
    if "messages.jsonl" not in manifest.get("files", {}):
        errors.append("manifest.files does not list messages.jsonl")
    for rel_path, digest in manifest.get("inputs", {}).items():
        p = ROOT / rel_path
        if p.exists() and sha256(p) != digest:
            errors.append(f"input changed since export: {rel_path}")
    exported = {r["id"]: r for r in read_jsonl(pack / "messages.jsonl")}
    source = {c["case_id"]: c for p in inputs for c in read_jsonl(p)}
    if manifest.get("n_records") != len(exported):
        errors.append(f"manifest n_records {manifest.get('n_records')} != {len(exported)}")
    for cid in sorted(source.keys() - exported.keys()):
        errors.append(f"{cid}: missing from export")
    for cid in sorted(exported.keys() - source.keys()):
        errors.append(f"{cid}: in export but not in source")
    for cid in sorted(source.keys() & exported.keys()):
        src, rec = source[cid], exported[cid]
        meta = rec.get("metadata", {})
        for k, v in src.items():
            if k not in meta:
                errors.append(f"{cid}: field lost: {k}")
            elif meta[k] != v:
                errors.append(f"{cid}: field changed: {k}")
        msgs = rec.get("messages", [])
        if [m.get("role") for m in msgs] != ROLES:
            errors.append(f"{cid}: message roles {[m.get('role') for m in msgs]} != {ROLES}")
        elif msgs != to_messages(src):
            errors.append(f"{cid}: messages differ from the ones built from the source case")
        text = "\n".join(m.get("content", "") for m in msgs)
        for k in ("question", "context", "feedback_text", "original_answer"):
            if src[k] not in text:
                errors.append(f"{cid}: {k} not present in messages")
    print(f"verified {len(exported)} records against {len(source)} source cases")
    return errors


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("inputs", nargs="+")
    b.add_argument("--out", required=True, type=Path)
    b.add_argument("--name", default=None)
    v = sub.add_parser("verify")
    v.add_argument("pack", type=Path)
    v.add_argument("inputs", nargs="+")
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.inputs, a.out, a.name or a.out.name)
        return 0
    errs = verify(a.pack, a.inputs)
    for e in errs:
        print("FAIL", e)
    print("OK" if not errs else f"{len(errs)} error(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
