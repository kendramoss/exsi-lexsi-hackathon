"""SafeTune: train on the CuratorKIT export. usage: train.py {plain|safegrad}

plain    = PlainSFTTrainer (ordinary LoRA SFT comparator)
safegrad = SafeGradTrainer with the solo-answer rows as the protected (utility) objective
Both see the identical 80-row train export, seed, epochs, batch size and LR.
"""
import json
import sys
import time
from pathlib import Path

import safetune
from datasets import load_dataset
from safetune.runner import harden
from safetune.runner.harden import _base

# Pinned dataloader memory trips the MPS GPU watchdog on step 0 (transformers 5.22,
# M2 Pro); SafeTune's standard TrainingArguments do not expose the flag.
_orig_args = _base._standard_args
_base._standard_args = lambda *a, **k: {**_orig_args(*a, **k), "dataloader_pin_memory": False,
                                         "save_strategy": "steps", "save_steps": 5,
                                         "save_total_limit": 1}

# The watchdog still fires at random (about once per 20-30 steps while the desktop is in
# use). Checkpoint every 10 steps and resume from the latest one; run.sh retries the process.
import transformers
from transformers.trainer_utils import get_last_checkpoint

_orig_train = transformers.Trainer.train


def _train_resuming(self, resume_from_checkpoint=None, **kw):
    if resume_from_checkpoint is None and Path(self.args.output_dir).is_dir():
        resume_from_checkpoint = get_last_checkpoint(self.args.output_dir)
        if resume_from_checkpoint:
            print(f"[evtune] resuming from {resume_from_checkpoint}", flush=True)
    return _orig_train(self, resume_from_checkpoint=resume_from_checkpoint, **kw)


transformers.Trainer.train = _train_resuming

# SafeTune pads every row to max_len; padded attention masks push MPS onto a slow masked
# path whose step exceeds the GPU watchdog. With batch_size=1 no padding is needed, so trim
# each row to its real tokens after SafeTune has tokenized (and recorded provenance for) it.
_orig_prepare = _base._HardenBase._prepare_dataset


def _trim(row):
    keep = [i for i, m in enumerate(row["attention_mask"]) if m == 1]
    return {k: [row[k][i] for i in keep] for k in ("input_ids", "attention_mask", "labels")}


def _prepare_unpadded(self, dataset, config=None, split=None):
    ds = _orig_prepare(self, dataset, config, split)
    ds = ds.map(_trim)
    assert all(any(l != -100 for l in r) for r in ds["labels"]), "a row lost its supervised tokens"
    return ds


_base._HardenBase._prepare_dataset = _prepare_unpadded

ROOT = Path(__file__).parent
MODEL = "CohereLabs/tiny-aya-global"
EXPORT = ROOT / "curated" / "train"
HP = dict(epochs=2, batch_size=1, lr=1e-4, logging_steps=10)

method = sys.argv[1]
safetune.configure(device="mps", seed=0, max_len=768)
out = ROOT / "ckpt" / method
t0 = time.time()
if method == "plain":
    trainer = harden.PlainSFTTrainer(model_id=MODEL, **HP)
    path = trainer.train(str(EXPORT), out_dir=str(out), dataset_config="sft_alpaca")
elif method == "safegrad":
    solo = load_dataset("json", data_files=str(EXPORT / "sft_alpaca.jsonl"), split="train")
    solo = solo.filter(lambda r: "When the user" not in r["instruction"])
    assert len(solo) == 20, len(solo)
    trainer = harden.SafeGradTrainer(model_id=MODEL, **HP)
    path = trainer.train(str(EXPORT), out_dir=str(out), dataset_config="sft_alpaca",
                         safety_dataset=solo)
else:
    raise SystemExit(__doc__)
info = {"method": method, "checkpoint": path, "seconds": round(time.time() - t0),
        "hparams": HP, "model": MODEL, "train_export": str(EXPORT)}
(ROOT / "ckpt" / f"{method}.json").write_text(json.dumps(info, indent=1))
print(json.dumps(info))
