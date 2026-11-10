"""CuratorKIT: validate and export the train and eval packs with manifests/checksums."""
import json
from pathlib import Path

from curatorkit import Curator, CuratorConfig

ROOT = Path(__file__).parent
for name, n in (("train", 80), ("eval", 16)):
    out = ROOT / "curated" / name
    res = Curator(CuratorConfig(
        dataset=str(ROOT / "data" / f"{name}_source.jsonl"), format="alpaca", clean=True,
        dedup="none", min_tokens=1, export_formats=["alpaca"], output_dir=str(out),
        name=f"evidencetune_smoke_{name}", write_hf_readme=True,
    )).run()
    export = out / "sft_alpaca.jsonl"
    rows = [json.loads(line) for line in export.open()]
    src = [json.loads(line) for line in (ROOT / "data" / f"{name}_source.jsonl").open()]
    assert len(res.passed) == len(rows) == n, (name, len(res.passed), len(rows))
    # CuratorKIT must not alter the text the labels are keyed on.
    assert sorted(r["input"] for r in rows) == sorted(r["input"] for r in src), name
    assert (out / "lexsi_provenance.json").exists() and (out / "checksums.txt").exists()
    print(name, "passed", len(rows), sorted(p.name for p in out.iterdir()))
