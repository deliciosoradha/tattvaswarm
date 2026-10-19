#!/usr/bin/env python3
"""Generate the TattvaSwarm router SFT dataset (deterministic, zero-dependency).

This script distills the *deterministic* tier classifier
(`tattva_swarm.router.classify`) into a chat-format JSONL dataset that can be
used for post-training on Nebius Token Factory (conversational format: one
`messages` array per line, last message from the assistant).

Guarantees:
- Deterministic: same seed -> byte-identical output.
- Parity: every assistant label is produced by calling the real `classify()`
  and asserted against the intended tier, so the dataset can never drift from
  the runtime router.
- Clean: no secrets, no PII, no internal hostnames.

Usage:
    python3 training/gen_router_sft.py [--out training/router_sft] [--seed 7]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from tattva_swarm.router import classify  # noqa: E402

SYSTEM = (
    "You are the TattvaSwarm tier router. Classify the user request into exactly one tier: "
    "normal, reasoning, heavy, or research. Reply with a single compact JSON object: "
    '{"tier": "<tier>", "reason": "<short reason>"}. '
    "normal = everyday short calls; reasoning = analysis, comparison, step-by-step work, debugging; "
    "heavy = long synthesis such as full reports, whitepapers, complete strategies; "
    "research = requests that need external or web lookup."
)

# ---- template material (public, synthetic, no PII) --------------------------

NORMAL_TOPICS = [
    "the weekly team update", "tomorrow's grocery list", "the onboarding checklist",
    "a thank-you note to a colleague", "the meeting notes from this morning",
    "a short product changelog entry", "the office lunch order", "a birthday wish message",
    "the packing list for a weekend trip", "a one-line commit message",
    "the summary of this article", "a polite reminder about the deadline",
]

NORMAL_TEMPLATES = [
    "Draft {topic}.",
    "Summarize {topic} in one line.",
    "Rewrite {topic} to be friendlier.",
    "Give me three ideas for {topic}.",
    "Fix the typos in {topic}.",
    "Shorten {topic} by half.",
]

REASONING_TOPICS = [
    "why the build times increased after the last dependency upgrade",
    "the trade-offs between caching and recomputing this metric",
    "two designs for the retry logic in the payment worker",
    "the root cause of the intermittent test failures",
    "the performance difference between the two query shapes",
    "the risks of rolling out the schema change this week",
    "the cost impact of the new instance type",
    "the failure modes of the leader election",
]

REASONING_TEMPLATES = [
    "Analyze {topic}.",
    "Compare {topic}.",
    "Why {topic}?",
    "Walk through step by step {topic}.",
    "Evaluate {topic}.",
    "Diagnose {topic}.",
    "Debug {topic}.",
]

HEAVY_TOPICS = [
    "the quarterly reliability program",
    "a platform migration plan",
    "the security review for the new service",
    "the data retention policy",
    "the incident postmortem process",
    "the roadmap for the next two quarters",
    "the observability stack consolidation",
]

HEAVY_TEMPLATES = [
    "Write a full report on {topic}.",
    "Synthesize a complete strategy for {topic}.",
    "Create a whitepaper about {topic}.",
    "Draft a deep dive into {topic}.",
    "Prepare a long document covering {topic}.",
]

RESEARCH_TOPICS = [
    "the latest news about small language models",
    "the current price of GPU instances",
    "the newest releases of vector databases",
    "recent papers on mixture-of-experts routing",
    "the current status of the open-source license change",
    "today's exchange rate for the euro",
]

RESEARCH_TEMPLATES = [
    "Search the web for {topic}.",
    "Look up online {topic}.",
    "Search online for {topic}.",
    "Busca en la web {topic}.",
    "Find the latest info about {topic} online.",
]

SUFFIXES = ["", "", "", " Please.", " Thanks!", " — keep it short.", " (concise)"]

TIER_MATERIAL = {
    "normal": (NORMAL_TEMPLATES, NORMAL_TOPICS, 60),
    "reasoning": (REASONING_TEMPLATES, REASONING_TOPICS, 60),
    "heavy": (HEAVY_TEMPLATES, HEAVY_TOPICS, 40),
    "research": (RESEARCH_TEMPLATES, RESEARCH_TOPICS, 40),
}


def build_examples(seed: int) -> list[dict]:
    rng = random.Random(seed)
    examples: list[dict] = []
    for tier, (templates, topics, count) in TIER_MATERIAL.items():
        made = 0
        guard = 0
        while made < count and guard < count * 50:
            guard += 1
            prompt = rng.choice(templates).format(topic=rng.choice(topics))
            prompt += rng.choice(SUFFIXES)
            decision = classify(prompt)
            if decision.tier != tier:
                # A template drifted into another tier; keep only exact matches
                # so the dataset mirrors the runtime router 1:1.
                continue
            assistant = json.dumps(
                {"tier": decision.tier, "reason": decision.reason}, ensure_ascii=False
            )
            example = {
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": assistant},
                ]
            }
            examples.append(example)
            made += 1
    rng.shuffle(examples)
    return examples


def write_jsonl(path: Path, rows: list[dict]) -> str:
    payload = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    path.write_text(payload, encoding="utf-8")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(REPO_ROOT / "training" / "router_sft"))
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    examples = build_examples(args.seed)
    split = int(len(examples) * 0.8)
    train, val = examples[:split], examples[split:]

    train_hash = write_jsonl(out_dir / "train.jsonl", train)
    val_hash = write_jsonl(out_dir / "val.jsonl", val)

    manifest = {
        "seed": args.seed,
        "counts": {"train": len(train), "val": len(val), "total": len(examples)},
        "sha256": {"train.jsonl": train_hash, "val.jsonl": val_hash},
        "format": "conversational (messages), last message assistant",
        "source": "tattva_swarm.router.classify (deterministic parity)",
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
