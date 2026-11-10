"""Single-copy LZMA packaging for the complete code-and-data notebook."""
from __future__ import annotations

import base64
import hashlib
import json
import lzma

from . import kaggle_flow


def compress_embedded_payload(embedded):
    canonical = json.dumps(embedded, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(lzma.compress(canonical, preset=9)).decode("ascii")


def materialize_compressed_payload(encoded, working_root):
    embedded = json.loads(lzma.decompress(base64.b64decode(encoded)).decode("utf-8"))
    return kaggle_flow.materialize_embedded_code(embedded, working_root)


def build_notebook():
    notebook = flow_build_notebook()
    embedded = notebook["metadata"].pop("balanced_spike_embedded")
    compressed = compress_embedded_payload(embedded)
    original_setup = "".join(notebook["cells"][0]["source"])
    marker = "for name, record in EMBEDDED.items():"
    _, suffix = original_setup.split(marker, 1)
    setup = '''import os, sys, base64, hashlib, json, lzma
from pathlib import Path
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
EMBEDDED_LZMA_B64 = ''' + json.dumps(compressed) + '''
EMBEDDED = json.loads(lzma.decompress(base64.b64decode(EMBEDDED_LZMA_B64)).decode("utf-8"))
for name, record in EMBEDDED.items():''' + suffix
    notebook["cells"][0]["source"] = setup.splitlines(True)
    metadata = notebook["metadata"]
    metadata.update({
        "balanced_spike_embedded_file_count": len(embedded),
        "balanced_spike_embedded_raw_bytes": sum(len(base64.b64decode(record["base64"])) for record in embedded.values()),
        "balanced_spike_compressed_sha256": hashlib.sha256(base64.b64decode(compressed)).hexdigest(),
    })
    return notebook


def flow_build_notebook():
    return __import__("balanced_spike.kaggle_flow", fromlist=["build_notebook"]).build_notebook()
