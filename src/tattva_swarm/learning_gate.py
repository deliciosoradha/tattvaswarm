"""Recursive self-improvement — the learning gate (sovereign edition). stdlib only.

The gate turns *lived* episodes into *supervised* training pairs — and only when
the system genuinely learned something it could **not** resolve at first:

    unresolved attempt(s)  →  real resolution  →  non-trivial  →  novel  →  within policy

Everything lives under ``$TATTVA_HOME/private/<identity>/`` (0700/0600): training
stays **private and dedicated to each identity** — a person, a company or a
project. Nothing is shared, nothing syncs, and secrets are refused: if a
resolution looks like it contains a key or a token, the gate skips it.

The emitted pairs use exactly the chat-pairs schema the router post-training
already consumes (``training/router_sft/*.jsonl``), so the same supervised
pipeline — and the same merge recipe — applies unchanged.

CLI:

    python3 -m tattva_swarm.learning_gate status --identity acme
    python3 -m tattva_swarm.learning_gate record --identity acme --json '<episode>'
    python3 -m tattva_swarm.learning_gate gate   --identity acme
    python3 -m tattva_swarm.learning_gate emit   --identity acme
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from hashlib import sha256
from pathlib import Path

FAILED_STATUSES = frozenset({"failed", "refused", "unresolved", "error", "timeout"})

DEFAULT_SYSTEM_PROMPT = (
    "You are a private personal assistant running under the TattvaSwarm "
    "sovereignty policy. Use what you have verified; if you cannot answer, "
    "say so exactly — never invent."
)

DEFAULT_POLICY: dict = {
    "min_failed_attempts": 1,      # the system must have failed at least once
    "min_resolution_chars": 24,    # a resolution shorter than this teaches nothing
    "max_question_chars": 4000,    # keep training data bounded
    "max_question_similarity": 0.85,  # jaccard vs existing/candidate questions
    "max_pairs_per_day": 200,      # anti-saturation: hard daily ceiling
    "system_prompt": DEFAULT_SYSTEM_PROMPT,
}

_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),              # OpenAI-style keys
    re.compile(r"\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*\S{8,}", re.I),
    re.compile(r"\b[0-9a-fA-F]{40,}\b"),                    # long hex blobs
    re.compile(r"\b[A-Za-z0-9+/]{48,}={0,2}\b"),            # long base64-ish blobs
)


def tattva_home() -> Path:
    return Path(os.environ.get("TATTVA_HOME", "~/.tattva")).expanduser()


def _slug(identity: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", (identity or "").strip().lower()).strip("-")
    return slug or "default"


def private_dir(identity: str) -> Path:
    """Per-identity private workspace. Created 0700 - never shared."""
    path = tattva_home() / "private" / _slug(identity)
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:  # non-POSIX filesystems — best effort, still private by path
        pass
    return path


def _append_private(path: Path, records: list[dict]) -> None:
    existed = path.exists()
    with open(path, "a", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    if not existed:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def episode_id(episode: dict) -> str:
    """Episode identity = hash of the question. The resolution may arrive
    later: re-recording the same question updates the episode in place."""
    basis = json.dumps({"q": episode.get("question", "")}, ensure_ascii=False, sort_keys=True)
    return sha256(basis.encode("utf-8")).hexdigest()[:12]


def record_episode(identity: str, episode: dict) -> dict:
    """Store one episode. Idempotent by episode id (= the question): a resolved
    version arriving later *completes the episode in place*; identical content
    is a no-op."""
    if not isinstance(episode, dict) or not str(episode.get("question", "")).strip():
        raise ValueError("episode needs a non-empty 'question'")
    ep = dict(episode)
    ep["id"] = ep.get("id") or episode_id(ep)
    ep.setdefault("ts", time.time())
    path = private_dir(identity) / "episodes.jsonl"
    existing = _load_jsonl(path)
    for i, old in enumerate(existing):
        if old.get("id") == ep["id"]:
            if ep.get("resolution") and ep.get("resolution") != old.get("resolution"):
                existing[i] = {**old, **ep}
                _rewrite(path, existing)
                return {"id": ep["id"], "updated": True}
            return {"id": ep["id"], "duplicate": True}
    _append_private(path, [ep])
    return {"id": ep["id"], "stored": True}


def _rewrite(path: Path, records: list[dict]) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def load_episodes(identity: str) -> list[dict]:
    return _load_jsonl(private_dir(identity) / "episodes.jsonl")


def load_pairs(identity: str) -> list[dict]:
    return _load_jsonl(private_dir(identity) / "pairs.jsonl")


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _looks_like_secret(text: str) -> bool:
    return any(p.search(text or "") for p in _SECRET_PATTERNS)


def gate_episode(ep: dict, seen_questions: list[set[str]], policy: dict) -> tuple[str, str]:
    """Decide one episode: ('train' | 'skip', reason). Pure and deterministic."""
    question = str(ep.get("question", "") or "")
    resolution = str(ep.get("resolution", "") or "")
    if not question.strip() or not resolution.strip():
        return "skip", "missing_fields"
    if len(resolution) < int(policy["min_resolution_chars"]):
        return "skip", "resolution_too_short"
    failed = [a for a in (ep.get("attempts") or [])
              if str((a or {}).get("status", "")).lower() in FAILED_STATUSES]
    if len(failed) < int(policy["min_failed_attempts"]) and not ep.get("initially_unresolved"):
        return "skip", "no_learning_event"
    q_norm = " ".join(question.lower().split())
    r_norm = " ".join(resolution.lower().split())
    if q_norm and (r_norm == q_norm or r_norm.startswith(q_norm)):
        return "skip", "trivial_echo"
    if _looks_like_secret(question) or _looks_like_secret(resolution):
        return "skip", "possible_secret"
    if len(question) > int(policy["max_question_chars"]):
        return "skip", "question_too_long"
    q_tokens = _tokens(question)
    for seen in seen_questions:
        if _jaccard(q_tokens, seen) >= float(policy["max_question_similarity"]):
            return "skip", "duplicate_question"
    return "train", "unresolved -> resolved, novel, within policy"


def _day_key(ts: float) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(ts))


def run_gate(identity: str, policy: dict | None = None) -> dict:
    """Evaluate every not-yet-emitted episode. Returns eligible + skipped."""
    policy = {**DEFAULT_POLICY, **(policy or {})}
    episodes = load_episodes(identity)
    pairs = load_pairs(identity)
    emitted = {p.get("episode_id") for p in pairs}
    today = _day_key(time.time())
    today_count = sum(1 for p in pairs if _day_key(float(p.get("ts", 0))) == today)
    seen = [_tokens((p.get("messages") or [{}, {}])[1].get("content", "")) for p in pairs]
    eligible: list[dict] = []
    skipped: list[dict] = []
    for ep in episodes:
        if ep.get("id") in emitted:
            continue
        decision, reason = gate_episode(ep, seen, policy)
        if decision == "train":
            if today_count + len(eligible) >= int(policy["max_pairs_per_day"]):
                skipped.append({"episode_id": ep.get("id"), "reason": "daily_cap_reached"})
                continue
            eligible.append(ep)
            seen.append(_tokens(ep.get("question", "")))
        else:
            skipped.append({"episode_id": ep.get("id"), "reason": reason})
    return {
        "identity": _slug(identity),
        "episodes": len(episodes),
        "pairs": len(pairs),
        "eligible": eligible,
        "skipped": skipped,
        "policy": {k: v for k, v in policy.items() if k != "system_prompt"},
    }


def emit_pairs(identity: str, policy: dict | None = None) -> dict:
    """Gate, then append the eligible episodes as supervised chat pairs."""
    policy = {**DEFAULT_POLICY, **(policy or {})}
    result = run_gate(identity, policy)
    path = private_dir(identity) / "pairs.jsonl"
    now = time.time()
    records = []
    for ep in result["eligible"]:
        records.append({
            "messages": [
                {"role": "system", "content": policy["system_prompt"]},
                {"role": "user", "content": ep["question"]},
                {"role": "assistant", "content": ep["resolution"]},
            ],
            "episode_id": ep["id"],
            "identity": _slug(identity),
            "ts": now,
            "source": "learning-gate/v1",
        })
    if records:
        _append_private(path, records)
    return {
        "identity": result["identity"],
        "emitted": len(records),
        "skipped": result["skipped"],
        "pairs_file": str(path),
    }


def status(identity: str) -> dict:
    info = run_gate(identity)
    reasons: dict[str, int] = {}
    for item in info["skipped"]:
        reasons[item["reason"]] = reasons.get(item["reason"], 0) + 1
    return {
        "identity": info["identity"],
        "private_dir": str(private_dir(identity)),
        "episodes": info["episodes"],
        "pairs": info["pairs"],
        "eligible_now": len(info["eligible"]),
        "skipped_now": reasons,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tattva_swarm.learning_gate",
        description="Recursive self-improvement gate (private, per-identity).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("status", "gate", "emit"):
        p = sub.add_parser(name)
        p.add_argument("--identity", required=True)
        p.add_argument("--json", action="store_true")
    rec = sub.add_parser("record")
    rec.add_argument("--identity", required=True)
    rec.add_argument("--json", action="store_true")
    rec.add_argument("payload", nargs="?", default=None,
                     help="episode JSON (omit to read from stdin)")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "record":
            raw = args.payload if args.payload is not None else sys.stdin.read()
            out = record_episode(args.identity, json.loads(raw))
        elif args.cmd == "gate":
            out = run_gate(args.identity)
            out["eligible"] = [e.get("id") for e in out["eligible"]]
        elif args.cmd == "emit":
            out = emit_pairs(args.identity)
        else:
            out = status(args.identity)
    except (ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
