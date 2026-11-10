"""Teacher-model labelling and validation for EvidenceTune task.v2 kits.

EvidenceTune distills the judgement of frontier "teacher" models (Claude Fable, Claude Opus)
into a small student (Tiny Aya). This module produces and validates the teacher labels:

  1. label     every blind kit row is labelled by each teacher model, several samples each,
               under the kit's own annotation guide, with structured (JSON-schema) output;
  2. gate      every label must pass the kit's deterministic task.v2 contract
               (annotation_lib.validate_annotation); failures are kept and counted, never used;
  3. agree     teachers' modal labels are compared field by field (agreement, Cohen's kappa)
               and each teacher's self-consistency across samples is measured;
  4. judge     rows where teachers disagree go to a judge model that must pick one of the
               candidate labels or declare the row ambiguous;
  5. tier      every row ends as teacher_consensus, teacher_adjudicated or needs_human;
  6. audit     a seeded, stratified sample is labelled blind by humans; audit_score reports
               how often the teacher labels match, with Wilson 95% intervals, per tier.

Provenance is always truthful: label_origin names the teacher process and human_attestation
is false. Labels on evaluation-only kits are marked evaluation_only and the training export
refuses them.
"""

from __future__ import annotations

import collections
import hashlib
import json
import math
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "annotation"))
from annotation_lib import (  # noqa: E402
    ACTIONS, ANSWERABILITY_VALUES, CITATION_STATUSES, COMPARE_FIELDS, TARGET_VALUES,
    TRUTH_VALUES, validate_annotation,
)

DEFAULT_TEACHERS = ("claude-fable-5-2", "claude-opus-5-5")
DEFAULT_JUDGE = "claude-fable-5-2"
PIPELINE_VERSION = "teacher-v1"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
LABEL_FIELDS = COMPARE_FIELDS + ("acceptable_actions",)

# JSON schema for one teacher label. cited_excerpt stays a free string here (the valid IDs differ
# per row, and a per-row schema would break prompt caching); the contract gate checks it.
LABEL_SCHEMA = {
    "type": "object",
    "properties": {
        "statement_truth": {"type": "string", "enum": list(TRUTH_VALUES)},
        "requested_target": {"type": "string", "enum": list(TARGET_VALUES)},
        "cited_excerpt": {"type": "string"},
        "citation_status": {"type": "string", "enum": list(CITATION_STATUSES)},
        "answerability": {"type": "string", "enum": list(ANSWERABILITY_VALUES)},
        "acceptable_actions": {"type": "array", "items": {"type": "string", "enum": list(ACTIONS)}},
        "rationale": {"type": "string"},
    },
    "required": ["statement_truth", "requested_target", "cited_excerpt", "citation_status",
                 "answerability", "acceptable_actions", "rationale"],
    "additionalProperties": False,
}

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "choice": {"type": "string", "description": "A candidate letter (A, B, ...) or AMBIGUOUS."},
        "rationale": {"type": "string"},
    },
    "required": ["choice", "rationale"],
    "additionalProperties": False,
}

LABEL_INSTRUCTIONS = """You are a careful annotator labelling one blind row of an evaluation kit.
Follow the annotation guide below exactly; where this note and the guide differ, the guide wins.
Judge only the visible statement and excerpts. The prior answer and the user's feedback are
dialogue context, not evidence. Return one label as JSON. In `rationale`, name the excerpt(s)
that decide each judgement in two to five sentences; it is stored as the annotation's notes.

ANNOTATION GUIDE
================
"""

JUDGE_INSTRUCTIONS = """You are adjudicating a disagreement between annotators on one blind row.
Follow the annotation guide below. Read the row, then the candidate labels and their rationales.
Choose the single candidate that the guide and the visible text support. If no candidate is
clearly supported, or the row itself is ambiguous, answer AMBIGUOUS: a human will decide.

ANNOTATION GUIDE
================
"""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Kit:
    """A blind task.v2 kit: items.json, its manifest and its annotation guide."""
    items_doc: dict
    manifest: dict
    guide: str
    path: Path

    @classmethod
    def load(cls, kit_dir: Path, guide: Path | None = None) -> "Kit":
        kit_dir = Path(kit_dir)
        items_doc = json.loads((kit_dir / "items.json").read_text(encoding="utf-8"))
        manifest_path = kit_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        guide_path = Path(guide) if guide else kit_dir / "ANNOTATION-GUIDE.md"
        if not guide_path.exists():
            guide_path = kit_dir.parent / "ANNOTATION-GUIDE.md"
        return cls(items_doc, manifest, guide_path.read_text(encoding="utf-8"), kit_dir)

    @property
    def items(self) -> list[dict]:
        return self.items_doc["items"]

    @property
    def dataset_id(self) -> str:
        return self.items_doc["dataset_id"]

    @property
    def evaluation_only(self) -> bool:
        return bool(self.manifest.get("evaluation_only") or self.items_doc.get("fresh"))


def render_item(item: dict) -> str:
    lines = [f"Row: {item['row_id']}", "", f"Statement: {item['statement']}", "", "Excerpts:"]
    lines += [f"[{e['number']}] {e['text']}" for e in item["excerpts"]]
    lines += ["", f"Earlier answer: {item['prior_answer']}", f"User feedback: {item['user_feedback']}"]
    return "\n".join(lines)


def to_annotation(row_id: str, label: dict) -> dict:
    """Map a teacher label to the kit's annotation shape (rationale becomes notes)."""
    out = {k: label[k] for k in LABEL_FIELDS}
    out["row_id"] = row_id
    out["notes"] = (label.get("rationale") or "")[:4000]
    return out


def label_key(annotation: dict) -> tuple:
    return tuple(annotation[f] for f in COMPARE_FIELDS) + (tuple(sorted(annotation["acceptable_actions"])),)


# --------------------------------------------------------------------------- model calls

def call_model(client, model: str, system: str, user: str, schema: dict, effort: str,
               fallbacks: bool) -> dict:
    """One structured-output request. Returns what the record needs, including the served model."""
    kwargs = dict(
        model=model,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    if fallbacks:
        stream = client.beta.messages.stream(betas=[FALLBACK_BETA], fallbacks="default", **kwargs)
    else:
        stream = client.messages.stream(**kwargs)
    with stream as s:
        msg = s.get_final_message()
    text = next((b.text for b in msg.content if getattr(b, "type", None) == "text"), "")
    return {
        "served_model": getattr(msg, "model", model),
        "stop_reason": msg.stop_reason,
        "request_id": getattr(msg, "_request_id", None),
        "raw_text": text,
        "usage": {k: getattr(msg.usage, k, None) for k in ("input_tokens", "output_tokens",
                                                          "cache_read_input_tokens")},
    }


def label_rows(kit: Kit, client, teachers=DEFAULT_TEACHERS, samples: int = 2, effort: str = "high",
               fallbacks: bool = True, done: set | None = None, log=print):
    """Yield one raw record per (row, teacher, sample). Skips keys already in `done`."""
    system = LABEL_INSTRUCTIONS + kit.guide
    guide_sha = sha256_text(kit.guide)
    for item in kit.items:
        user = render_item(item)
        for model in teachers:
            for k in range(samples):
                key = f"{item['row_id']}|{model}|{k}"
                if done and key in done:
                    continue
                rec = {"key": key, "kind": "label", "row_id": item["row_id"], "teacher": model,
                       "sample": k, "dataset_id": kit.dataset_id, "pipeline": PIPELINE_VERSION,
                       "guide_sha256": guide_sha, "prompt_sha256": sha256_text(system + "\n" + user),
                       "created_at": now()}
                try:
                    rec.update(call_model(client, model, system, user, LABEL_SCHEMA, effort, fallbacks))
                except Exception as e:  # recorded, not fatal: a failed call is an invalid sample
                    rec.update({"error": f"{type(e).__name__}: {e}"})
                rec.update(gate(rec, item))
                log(f"{key}: {'ok' if rec['valid'] else 'INVALID ' + rec['invalid_reason']}")
                yield rec


def gate(rec: dict, item: dict) -> dict:
    """Parse and run the deterministic task.v2 contract on one raw record."""
    if rec.get("error"):
        return {"valid": False, "invalid_reason": "call failed", "annotation": None}
    if rec.get("stop_reason") == "refusal":
        return {"valid": False, "invalid_reason": "refusal", "annotation": None}
    if rec.get("stop_reason") == "max_tokens":
        return {"valid": False, "invalid_reason": "truncated", "annotation": None}
    try:
        label = json.loads(rec.get("raw_text") or "")
        annotation = validate_annotation(to_annotation(item["row_id"], label), item)
    except (ValueError, KeyError, TypeError) as e:
        return {"valid": False, "invalid_reason": f"contract: {e}", "annotation": None}
    return {"valid": True, "invalid_reason": None, "annotation": annotation}


def judge_rows(kit: Kit, client, conflicts: dict, judge: str = DEFAULT_JUDGE, effort: str = "high",
               fallbacks: bool = True, log=print):
    """Ask the judge to choose among the distinct candidate labels of each conflicting row."""
    system = JUDGE_INSTRUCTIONS + kit.guide
    items = {it["row_id"]: it for it in kit.items}
    for row_id, candidates in conflicts.items():
        letters = [chr(ord("A") + i) for i in range(len(candidates))]
        body = [render_item(items[row_id]), "", "Candidate labels:"]
        for letter, cand in zip(letters, candidates):
            shown = {k: cand["annotation"][k] for k in LABEL_FIELDS}
            body.append(f"{letter}: {json.dumps(shown)}\n   rationale: {cand['annotation']['notes']}")
        user = "\n".join(body)
        rec = {"key": f"{row_id}|judge|{judge}", "kind": "judge", "row_id": row_id, "judge": judge,
               "candidates": letters, "candidate_keys": [list(map(_jsonable, c["key"])) for c in candidates],
               "dataset_id": kit.dataset_id, "pipeline": PIPELINE_VERSION,
               "prompt_sha256": sha256_text(system + "\n" + user), "created_at": now()}
        try:
            rec.update(call_model(client, judge, system, user, JUDGE_SCHEMA, effort, fallbacks))
            out = json.loads(rec["raw_text"])
            choice = out["choice"].strip().upper()
            rec["choice"] = choice if choice in letters else "AMBIGUOUS"
            rec["rationale"] = out.get("rationale", "")
        except Exception as e:
            rec.update({"choice": "AMBIGUOUS", "error": f"{type(e).__name__}: {e}"})
        log(f"{rec['key']}: {rec['choice']}")
        yield rec


def _jsonable(v):
    return list(v) if isinstance(v, tuple) else v


# --------------------------------------------------------------------------- consensus

def kappa(a: list, b: list):
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = collections.Counter(a), collections.Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return None if pe == 1 else round((po - pe) / (1 - pe), 3)


def modal(samples: list[dict]):
    """Most common label among a teacher's valid samples, and the share of samples that agree with it."""
    keys = collections.Counter(s["key"] for s in samples)
    key, count = keys.most_common(1)[0]
    rep = next(s for s in samples if s["key"] == key)
    return rep, count / len(samples)


def consensus(kit: Kit, records: list[dict], teachers=DEFAULT_TEACHERS, min_self_consistency: float = 0.5):
    """Group raw label records by row. Returns (rows, conflicts) before judging."""
    by_row = collections.defaultdict(lambda: collections.defaultdict(list))
    invalid = collections.Counter()
    for r in records:
        if r.get("kind") != "label":
            continue
        if r["valid"]:
            by_row[r["row_id"]][r["teacher"]].append({"key": label_key(r["annotation"]), "annotation": r["annotation"]})
        else:
            invalid[(r["teacher"], r["invalid_reason"].split(":")[0])] += 1
    rows, conflicts = {}, {}
    for item in kit.items:
        rid = item["row_id"]
        per_teacher = {t: modal(by_row[rid][t]) for t in teachers if by_row[rid].get(t)}
        row = {"row_id": rid, "teachers": {t: {"self_consistency": round(sc, 3), "n_valid": len(by_row[rid][t])}
                                           for t, (_, sc) in per_teacher.items()}}
        reps = {t: rep for t, (rep, _) in per_teacher.items()}
        keys = {rep["key"] for rep in reps.values()}
        stable = all(sc >= min_self_consistency for _, sc in per_teacher.values())
        if len(per_teacher) == len(teachers) and len(keys) == 1 and stable:
            row.update(tier="teacher_consensus", annotation=next(iter(reps.values()))["annotation"],
                       unanimous=all(len({s["key"] for s in by_row[rid][t]}) == 1 for t in teachers))
        elif not per_teacher:
            row.update(tier="needs_human", annotation=None, reason="no valid teacher label")
        else:
            distinct = {}
            for t in teachers:
                for s in by_row[rid].get(t, []):
                    distinct.setdefault(s["key"], s)
            conflicts[rid] = list(distinct.values())
            row.update(tier="conflict", annotation=None,
                       reason="teachers disagree" if len(keys) > 1 else
                       ("a teacher has no valid label" if len(per_teacher) < len(teachers) else "unstable samples"))
        if row["annotation"] and (row["annotation"]["statement_truth"] == "UNDETERMINED"
                                  or row["annotation"]["answerability"] == "UNCLEAR"):
            row["low_confidence"] = True
        rows[rid] = row
    return rows, conflicts, by_row, invalid


def apply_judgements(rows: dict, conflicts: dict, judgements: list[dict]) -> None:
    by_row = {j["row_id"]: j for j in judgements if j.get("kind") == "judge"}
    for rid in conflicts:
        j = by_row.get(rid)
        row = rows[rid]
        if j and j["choice"] != "AMBIGUOUS":
            chosen = conflicts[rid][ord(j["choice"]) - ord("A")]
            row.update(tier="teacher_adjudicated", annotation=chosen["annotation"],
                       judge=j["judge"], judge_rationale=j.get("rationale", ""))
            ann = chosen["annotation"]
            if ann["statement_truth"] == "UNDETERMINED" or ann["answerability"] == "UNCLEAR":
                row["low_confidence"] = True
        else:
            row.update(tier="needs_human", reason=row.get("reason", "") + ("; judge: ambiguous" if j else "; not judged"))


def agreement_report(kit: Kit, rows: dict, by_row: dict, invalid: collections.Counter, teachers=DEFAULT_TEACHERS) -> dict:
    """Teacher-vs-teacher agreement on modal labels, self-consistency, gate failures and tiers."""
    pair = [rid for rid in rows if all(by_row[rid].get(t) for t in teachers)]
    report = {"dataset_id": kit.dataset_id, "evaluation_only": kit.evaluation_only, "rows": len(rows),
              "teachers": list(teachers), "rows_with_all_teachers": len(pair), "fields": {}}
    if len(teachers) >= 2 and pair:
        t1, t2 = teachers[0], teachers[1]
        m1 = {rid: modal(by_row[rid][t1])[0]["annotation"] for rid in pair}
        m2 = {rid: modal(by_row[rid][t2])[0]["annotation"] for rid in pair}
        for f in LABEL_FIELDS:
            a = [_hashable(m1[r][f]) for r in pair]
            b = [_hashable(m2[r][f]) for r in pair]
            report["fields"][f] = {"agreement": round(sum(x == y for x, y in zip(a, b)) / len(pair), 3),
                                   "cohens_kappa": kappa(a, b)}
        report["all_fields_agreement"] = round(sum(label_key(m1[r]) == label_key(m2[r]) for r in pair) / len(pair), 3)
    report["self_consistency"] = {t: round(_mean([rows[r]["teachers"][t]["self_consistency"] for r in rows
                                                  if t in rows[r]["teachers"]]), 3) for t in teachers}
    report["invalid_samples"] = {f"{t}/{reason}": n for (t, reason), n in sorted(invalid.items())}
    report["tiers"] = dict(collections.Counter(r["tier"] for r in rows.values()))
    report["low_confidence_rows"] = sum(bool(r.get("low_confidence")) for r in rows.values())
    return report


def _hashable(v):
    return tuple(sorted(v)) if isinstance(v, list) else v


def _mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


# --------------------------------------------------------------------------- outputs

def label_records(kit: Kit, rows: dict, teachers=DEFAULT_TEACHERS) -> list[dict]:
    """The distilled label set, with truthful provenance."""
    out = []
    for rid, row in rows.items():
        if not row.get("annotation"):
            continue
        out.append({
            "row_id": rid, "dataset_id": kit.dataset_id, "annotation": row["annotation"],
            "label_origin": row["tier"], "teachers": list(teachers), "judge": row.get("judge"),
            "unanimous": row.get("unanimous", False), "low_confidence": row.get("low_confidence", False),
            "human_attestation": False, "evaluation_only": kit.evaluation_only,
            "pipeline": PIPELINE_VERSION,
        })
    return out


def training_export(kit: Kit, labels: list[dict], tiers=("teacher_consensus",)) -> list[dict]:
    """Labels a student may be trained on. Refuses evaluation-only kits outright."""
    if kit.evaluation_only:
        raise PermissionError(f"{kit.dataset_id} is evaluation-only: its labels must not be used for training")
    return [l for l in labels if l["label_origin"] in tiers and not l["low_confidence"]]


def audit_sample(rows: dict, n_consensus: int, seed: str) -> list[str]:
    """Row ids for blind human audit: every adjudicated and needs_human row, plus a seeded random
    sample of consensus rows (low-confidence consensus rows first)."""
    rng = random.Random(seed)
    must = sorted(r for r, row in rows.items() if row["tier"] in ("teacher_adjudicated", "needs_human"))
    cons = sorted(r for r, row in rows.items() if row["tier"] == "teacher_consensus")
    low = [r for r in cons if rows[r].get("low_confidence")]
    rest = [r for r in cons if not rows[r].get("low_confidence")]
    rng.shuffle(rest)
    picked = low[:n_consensus] + rest[: max(0, n_consensus - len(low))]
    return must + sorted(picked)


MODEL_ID_HINTS = ("claude", "fable", "opus", "sonnet", "haiku", "mythos", "gpt", "gemini", "llama", "agent")


def looks_like_model(annotator_id: str) -> bool:
    """True when an annotator id names a model (e.g. the stamped AI references in annotation/ai_reference)."""
    low = (annotator_id or "").lower()
    return any(h in low for h in MODEL_ID_HINTS)


def wilson(k: int, n: int, z: float = 1.96):
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]


def audit_score(labels: list[dict], human: dict[str, dict]) -> dict:
    """Compare teacher labels with blind human audit labels, per tier and per field."""
    out = {}
    by_tier = collections.defaultdict(list)
    for l in labels:
        if l["row_id"] in human:
            by_tier[l["label_origin"]].append(l)
    for tier, ls in sorted(by_tier.items()):
        exact = sum(label_key(l["annotation"]) == label_key(human[l["row_id"]]) for l in ls)
        fields = {f: round(sum(_hashable(l["annotation"][f]) == _hashable(human[l["row_id"]][f]) for l in ls) / len(ls), 3)
                  for f in LABEL_FIELDS}
        out[tier] = {"n": len(ls), "exact_match": exact, "exact_match_rate": round(exact / len(ls), 3),
                     "exact_match_wilson95": wilson(exact, len(ls)), "field_agreement": fields}
    return out
