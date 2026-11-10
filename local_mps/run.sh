#!/bin/zsh
# Retry train.py until it writes ckpt/<method>.json (it resumes from its last checkpoint).
method=$1
for attempt in {1..25}; do
  [[ -f ckpt/$method.json ]] && exit 0
  echo "[run.sh] $method attempt $attempt $(date +%T)"
  HF_HUB_OFFLINE=1 .venv/bin/python train.py $method
done
[[ -f ckpt/$method.json ]]
