#!/usr/bin/env python3
"""Submit and monitor a supervised fine-tuning (LoRA) job on Nebius Token Factory.

Zero third-party dependencies (stdlib urllib only). The API key is read from the
NEBIUS_API_KEY environment variable and is never printed; only public
identifiers (file ids, job ids, status) appear in output.

Usage:
    export NEBIUS_API_KEY=<key>
    # 1) upload datasets + create the job
    python3 training/tf_post_train.py --model Qwen/Qwen3-0.6B \
        --train training/router_sft/train.jsonl \
        --val training/router_sft/val.jsonl \
        --suffix tattva-router-v1
    # 2) poll an existing job
    python3 training/tf_post_train.py --poll <job_id>
    # 3) list recent events for a job
    python3 training/tf_post_train.py --events <job_id>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BASE_URL = os.environ.get("TATTVA_TF_BASE_URL", "https://api.tokenfactory.nebius.com/v1")


def _key() -> str:
    key = os.environ.get("NEBIUS_API_KEY", "").strip()
    if not key:
        sys.exit("NEBIUS_API_KEY is not set (export it first; it is never printed by this tool)")
    return key


def _request(method: str, path: str, *, data: bytes | None = None, headers: dict | None = None) -> dict:
    req = urllib.request.Request(BASE_URL + path, data=data, method=method)
    req.add_header("Authorization", f"Bearer {_key()}")
    req.add_header("Accept", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        sys.exit(f"HTTP {exc.code} on {method} {path}: {detail}")
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"network error on {method} {path}: {type(exc).__name__}: {exc}")


def upload_file(path: Path, purpose: str = "fine-tune") -> str:
    boundary = "----tattva" + uuid.uuid4().hex
    body = b"".join(
        [
            f'--{boundary}\r\nContent-Disposition: form-data; name="purpose"\r\n\r\n{purpose}\r\n'.encode(),
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
            f"Content-Type: application/jsonl\r\n\r\n".encode(),
            path.read_bytes(),
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    out = _request(
        "POST",
        "/files",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    return out["id"]


def create_job(args: argparse.Namespace) -> dict:
    train_id = args.train_file_id or upload_file(Path(args.train))
    val_id = args.val_file_id or (upload_file(Path(args.val)) if args.val else None)
    hyper = {
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "n_epochs": args.epochs,
        "lora": True,
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_r,
        "lora_dropout": 0.05,
        "packing": True,
        "context_length": args.context,
        "warmup_ratio": 0.1,
        "max_grad_norm": 1.0,
    }
    payload = {
        "model": args.model,
        "suffix": args.suffix,
        "training_file": train_id,
        "hyperparameters": hyper,
        "seed": 42,
    }
    if val_id:
        payload["validation_file"] = val_id
    job = _request(
        "POST", "/fine_tuning/jobs", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}
    )
    return {
        "training_file": train_id,
        "validation_file": val_id,
        "job_id": job.get("id"),
        "status": job.get("status"),
        "model": job.get("model"),
        "suffix": job.get("suffix"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="Qwen/Qwen3-0.6B")
    parser.add_argument("--train", default="training/router_sft/train.jsonl")
    parser.add_argument("--val", default="training/router_sft/val.jsonl")
    parser.add_argument("--suffix", default="tattva-router-v1")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--context", type=int, default=8192)  # API enforces >= 8192
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--poll", metavar="JOB_ID")
    parser.add_argument("--events", metavar="JOB_ID")
    parser.add_argument("--out", metavar="FILE", help="write the full job JSON to this file")
    parser.add_argument("--train-file-id", help="reuse an already uploaded training file id")
    parser.add_argument("--val-file-id", help="reuse an already uploaded validation file id")
    args = parser.parse_args()

    if args.poll:
        job = _request("GET", f"/fine_tuning/jobs/{args.poll}")
        keep = ("id", "status", "model", "trained_tokens", "trained_steps", "total_steps", "error", "suffix")
        print(json.dumps({k: job.get(k) for k in keep}, indent=2))
        return 0

    if args.events:
        ev = _request("GET", f"/fine_tuning/jobs/{args.events}/events?limit=50")
        for e in ev.get("data", []):
            print(e.get("created_at"), e.get("level"), "-", e.get("message"))
        return 0

    summary = create_job(args)
    if args.out:
        Path(args.out).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
