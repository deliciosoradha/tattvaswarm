#!/usr/bin/env bash
# Deploy the TattvaSwarm demo to a Hugging Face Space (Docker SDK).
#
# Prereqs (one-time, operator):
#   1. Hugging Face account + a Space created with SDK=Docker, port 7860
#   2. HF token with write access, available as HF_TOKEN (or huggingface-cli login)
#   3. In the Space settings: add secret NEBIUS_API_KEY
#
# Usage:  HF_TOKEN=... bash spaces/deploy_hf.sh <hf-user-or-org>/<space-name>
set -euo pipefail
cd "$(dirname "$0")/.."            # repo root
SPACE=${1:?usage: deploy_hf.sh <hf-user-or-org>/<space-name>}

STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

cp spaces/demo/README.md spaces/demo/Dockerfile spaces/demo/app.py "$STAGE/"
cp -r src/tattva_swarm "$STAGE/tattva_swarm"

echo "staged files:"; find "$STAGE" -maxdepth 2 -type f | sort

python3 - <<PY
import os, sys
from huggingface_hub import HfApi
api = HfApi(token=os.environ.get("HF_TOKEN"))
api.upload_folder(
    repo_id="${SPACE}",
    repo_type="space",
    folder_path="${STAGE}",
    commit_message="TattvaSwarm demo: tiered Nemotron routing",
)
print("deployed → https://huggingface.co/spaces/${SPACE}")
PY
