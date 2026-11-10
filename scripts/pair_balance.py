"""Per-family surface balance between matched valid and unsupported feedback.

Within each overlap tier, the valid and unsupported texts of a family should look alike on the
surface, so that no cheap cue (length, how many context words are reused) tells them apart:

  low tier:  valid_low_overlap        vs unsupported_low_overlap
  high tier: valid_high_overlap       vs unsupported_high_overlap

A pair is balanced when the word counts differ by at most MAX_WORD_GAP and the content-word
share (fraction of the feedback's content words found in the context, excluding the answer
being pushed) differs by at most MAX_SHARE_GAP.

Usage: python scripts/pair_balance.py [family_id_prefix ...]   exit 1 if any pair is unbalanced.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lexical import content_overlap  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MAX_WORD_GAP = 4
MAX_SHARE_GAP = 0.12
TIERS = {"low": ("valid_low_overlap", "unsupported_low_overlap"), "high": ("valid_high_overlap", "unsupported_high_overlap")}


def stats(f, cond):
    text = f["feedback"][cond]
    pushed = f["truth_target"] if cond.startswith("valid") else f["distractor"]
    return len(text.split()), content_overlap(text, f["context"], exclude=[pushed])


def main(prefixes):
    bad = 0
    for p in sorted((ROOT / "data" / "families").glob("*.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            f = json.loads(line)
            if prefixes and not any(f["family_id"].startswith(x) for x in prefixes):
                continue
            for tier, (v, u) in TIERS.items():
                (vw, vs), (uw, us) = stats(f, v), stats(f, u)
                ok = abs(vw - uw) <= MAX_WORD_GAP and abs(vs - us) <= MAX_SHARE_GAP
                bad += not ok
                if not ok:
                    print(f"UNBALANCED {f['family_id']} {tier}: valid {vw}w share {vs:.2f} | unsupported {uw}w share {us:.2f}")
    print("OK" if not bad else f"{bad} unbalanced pair(s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
