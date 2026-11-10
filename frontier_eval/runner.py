"""Frontier Scientific Contract Runner & Sealed Evidence Generator.

Integrates:
  - 5 Physical Domain Oracles (P1 scramjet, P2 TPS, P3 lunar night, P4 Rubisco Pareto, P5 backtranslate)
  - Strict 4-Tier Classification (PROXY_PASS, FAIL_ORACLE, UNSUPPORTED_EXTRAORDINARY, UNPARSEABLE)
  - DharmaGate-Agentic-Shield (evidence sealing: chmod 444, manifest.sha256, tampering detection)
  - Chained cryptographic ledger (UUIDv7 + SHA-256 hash chaining)
  - Automatic markdown diagnostic reporting (REPORT.md)

Never emits the word "SOLVED" — all successes are strictly classified as PROXY_PASS.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import stat
import sys
from typing import Any, Dict, List, Optional, Tuple

# Attempt import from DharmaGate-Agentic-Shield workspace
DHARMAGATE_ROOT = pathlib.Path("/home/antigravity/deliciosoradha/DharmaGate-Agentic-Shield")
if DHARMAGATE_ROOT.exists() and str(DHARMAGATE_ROOT) not in sys.path:
    sys.path.insert(0, str(DHARMAGATE_ROOT))

try:
    from src.utils import compute_sha256_manifest, lock_evidence_directory, verify_manifest
    DHARMAGATE_AVAILABLE = True
except ImportError:
    DHARMAGATE_AVAILABLE = False

    def compute_sha256_manifest(evidence_dir: Optional[pathlib.Path] = None) -> dict:
        target = evidence_dir or pathlib.Path(".")
        manifest = {}
        for f in sorted(target.iterdir()):
            if f.is_file() and f.name != ".gitkeep" and f.name != "manifest.sha256":
                h = hashlib.sha256()
                h.update(f.read_bytes())
                manifest[f.name] = h.hexdigest()
        manifest_path = target / "manifest.sha256"
        lines = [f"{digest}  {name}\n" for name, digest in manifest.items()]
        manifest_path.write_text("".join(lines), encoding="utf-8")
        return {"manifest": manifest, "count": len(manifest), "manifest_path": str(manifest_path)}

    def lock_evidence_directory(evidence_dir: Optional[pathlib.Path] = None) -> dict:
        target = evidence_dir or pathlib.Path(".")
        results = []
        for f in target.iterdir():
            if f.is_file() and f.name != ".gitkeep":
                readonly = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
                os.chmod(f, readonly)
                results.append({"file": f.name, "locked": True})
        return {"evidence_dir": str(target), "files_locked": len(results), "files": results}

    def verify_manifest(evidence_dir: Optional[pathlib.Path] = None) -> dict:
        target = evidence_dir or pathlib.Path(".")
        manifest_path = target / "manifest.sha256"
        if not manifest_path.exists():
            return {"verdict": "ERROR", "error": "No manifest.sha256 found"}
        stored = {}
        for line in manifest_path.read_text().strip().split("\n"):
            if line.strip():
                parts = line.split("  ", 1)
                if len(parts) == 2:
                    stored[parts[1]] = parts[0]
        results = {}
        all_valid = True
        for name, expected_digest in stored.items():
            fpath = target / name
            if not fpath.exists():
                results[name] = {"status": "MISSING", "expected": expected_digest}
                all_valid = False
                continue
            h = hashlib.sha256()
            h.update(fpath.read_bytes())
            actual = h.hexdigest()
            if actual == expected_digest:
                results[name] = {"status": "VERIFIED", "sha256": actual}
            else:
                results[name] = {"status": "TAMPERED", "expected": expected_digest, "actual": actual}
                all_valid = False
        verdict = "INTEGRITY_OK" if all_valid else "TAMPERING_DETECTED"
        return {"verdict": verdict, "files": results}

from frontier_eval.oracles import scramjet, tps, lunar_power, rubisco, backtranslate

ORACLE_DISPATCH = {
    "P1_scramjet": scramjet,
    "P2_tps": tps,
    "P3_lunar_power": lunar_power,
    "P4_rubisco": rubisco,
    "P5_backtranslate": backtranslate,
}

TASK_FILES = {
    "P1_scramjet": "P1_scramjet.json",
    "P2_tps": "P2_tps.json",
    "P3_lunar_power": "P3_lunar_power.json",
    "P4_rubisco": "P4_rubisco.json",
    "P5_backtranslate": "P5_backtranslate.json",
}


def load_task_definitions(tasks_dir: pathlib.Path) -> Dict[str, Dict[str, Any]]:
    tasks = {}
    for task_id, fname in TASK_FILES.items():
        fpath = tasks_dir / fname
        if fpath.exists():
            tasks[task_id] = json.loads(fpath.read_text(encoding="utf-8"))
        else:
            tasks[task_id] = {"task_id": task_id, "warning": "definition_file_missing"}
    return tasks


def run_evaluation(
    tasks_dir: pathlib.Path,
    answers_path: pathlib.Path,
    output_dir: pathlib.Path,
    chain_file: Optional[pathlib.Path] = None,
) -> Dict[str, Any]:
    tasks = load_task_definitions(tasks_dir)
    answers = json.loads(answers_path.read_text(encoding="utf-8"))

    run_id = f"run_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
    timestamp_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

    results_by_task: Dict[str, Any] = {}
    summary_counts: Dict[str, int] = {
        "PROXY_PASS": 0,
        "FAIL_ORACLE": 0,
        "UNSUPPORTED_EXTRAORDINARY": 0,
        "UNPARSEABLE": 0,
    }

    for task_id, oracle_mod in ORACLE_DISPATCH.items():
        task = tasks.get(task_id, {})
        ans = answers.get(task_id)
        if ans is None:
            tier = "FAIL_ORACLE"
            eval_result = {"tier": tier, "reasons": ["No answer provided for task"]}
        else:
            try:
                eval_result = oracle_mod.evaluate(task, ans)
                tier = eval_result.get("tier", "FAIL_ORACLE")
            except Exception as exc:
                tier = "UNPARSEABLE"
                eval_result = {"tier": tier, "reasons": [f"Oracle evaluation crash: {exc}"]}

        # Safety check: Never emit the word SOLVED
        if tier == "SOLVED":
            tier = "PROXY_PASS"
            eval_result["tier"] = tier

        results_by_task[task_id] = {
            "task_id": task_id,
            "domain": task.get("domain", "unspecified"),
            "tier": tier,
            "oracle_output": eval_result,
        }
        summary_counts[tier] = summary_counts.get(tier, 0) + 1

    # Format Evidence Bundle
    bundle_dir = output_dir / run_id
    bundle_dir.mkdir(parents=True, exist_ok=True)

    contract_data = {
        "run_id": run_id,
        "timestamp_utc": timestamp_utc,
        "dharmagate_available": DHARMAGATE_AVAILABLE,
        "summary": summary_counts,
        "tasks_evaluated": results_by_task,
    }
    (bundle_dir / "contract_results.json").write_text(json.dumps(contract_data, indent=2) + "\n", encoding="utf-8")

    # Generate REPORT.md
    report_lines = [
        f"# Frontier Scientific Contract Evaluation Report — {run_id}",
        "",
        f"- **Timestamp (UTC)**: {timestamp_utc}",
        f"- **Total Tasks**: {len(results_by_task)}",
        f"- **Pass Rate (PROXY_PASS)**: {summary_counts['PROXY_PASS']}/{len(results_by_task)} ({summary_counts['PROXY_PASS']/len(results_by_task)*100:.1f}%)",
        f"- **Extraordinary Claims Blocked**: {summary_counts['UNSUPPORTED_EXTRAORDINARY']}",
        f"- **Oracle Rejections (FAIL_ORACLE)**: {summary_counts['FAIL_ORACLE']}",
        f"- **Unparseable**: {summary_counts['UNPARSEABLE']}",
        f"- **DharmaGate Engine**: {'Connected (DharmaGate-Agentic-Shield)' if DHARMAGATE_AVAILABLE else 'Standalone fallback'}",
        "",
        "## Summary by Task",
        "",
        "| Task ID | Domain | Tier | Reasons / Diagnostics |",
        "|---|---|---|---|",
    ]
    for tid, res in results_by_task.items():
        reasons = "; ".join(res["oracle_output"].get("reasons", [])) or "All physical constraints satisfied"
        # Sanitize markdown pipes
        reasons_clean = reasons.replace("|", "/")
        report_lines.append(f"| `{tid}` | {res['domain']} | **`{res['tier']}`** | {reasons_clean} |")

    report_lines.extend([
        "",
        "## Integrity Note",
        "> [!IMPORTANT]",
        "> A tier of `PROXY_PASS` indicates physical self-consistency at the computational proxy level only.",
        "> It does NOT signify a solved wet-lab or manufactured flight system.",
        "",
    ])
    (bundle_dir / "REPORT.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    # Compute manifest and lock evidence using DharmaGate
    manifest_res = compute_sha256_manifest(bundle_dir)
    lock_res = lock_evidence_directory(bundle_dir)

    # Chained cryptographic ledger entry
    if chain_file is not None:
        chain_file.parent.mkdir(parents=True, exist_ok=True)
        prev_sha = "0" * 64
        if chain_file.exists() and chain_file.stat().st_size > 0:
            last_line = chain_file.read_text(encoding="utf-8").strip().split("\n")[-1]
            try:
                prev_record = json.loads(last_line)
                prev_sha = prev_record.get("sha256", prev_sha)
            except Exception:
                pass

        record_data = {
            "run_id": run_id,
            "timestamp_utc": timestamp_utc,
            "prev_sha256": prev_sha,
            "bundle_manifest": manifest_res.get("manifest", {}),
            "summary": summary_counts,
        }
        record_bytes = json.dumps(record_data, sort_keys=True).encode("utf-8")
        record_hash = hashlib.sha256(record_bytes).hexdigest()
        record_data["sha256"] = record_hash

        with chain_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record_data) + "\n")

    return {
        "run_id": run_id,
        "bundle_dir": str(bundle_dir),
        "summary": summary_counts,
        "manifest": manifest_res.get("manifest", {}),
        "locked_files": lock_res.get("files_locked", 0),
    }


def main():
    parser = argparse.ArgumentParser(description="Frontier Scientific Contract Evaluator")
    subparsers = parser.add_subparsers(dest="command")

    # Evaluate command
    eval_parser = subparsers.add_parser("evaluate", help="Run oracle evaluation against answers")
    eval_parser.add_argument("--tasks-dir", default="frontier_eval/tasks", help="Tasks directory")
    eval_parser.add_argument("--answers", default="frontier_eval/tasks/answers_reference.json", help="Answers JSON")
    eval_parser.add_argument("--output-dir", default="frontier_eval/evidence_bundles", help="Evidence bundle dir")
    eval_parser.add_argument("--chain-file", default="frontier_eval/runs/evaluation_chain.jsonl", help="Ledger chain file")

    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify integrity of an evidence bundle")
    verify_parser.add_argument("bundle_dir", help="Path to evidence bundle directory")

    args = parser.parse_args()

    if args.command == "verify":
        target = pathlib.Path(args.bundle_dir)
        print(f"[*] Verifying integrity of evidence bundle: {target}")
        res = verify_manifest(target)
        print(f"[Result] Verdict: {res.get('verdict')}")
        for fname, info in res.get("files", {}).items():
            print(f"  - {fname}: {info.get('status')}")
        if res.get("verdict") != "INTEGRITY_OK":
            sys.exit(1)
        return

    # Default to evaluate
    tasks_dir = pathlib.Path(getattr(args, "tasks_dir", "frontier_eval/tasks"))
    answers_path = pathlib.Path(getattr(args, "answers", "frontier_eval/tasks/answers_reference.json"))
    output_dir = pathlib.Path(getattr(args, "output_dir", "frontier_eval/evidence_bundles"))
    chain_file = pathlib.Path(getattr(args, "chain_file", "frontier_eval/runs/evaluation_chain.jsonl"))

    print(f"[*] Starting Frontier Contract Evaluation...")
    print(f"    Tasks dir: {tasks_dir}")
    print(f"    Answers:   {answers_path}")
    print(f"    DharmaGate: {'Connected' if DHARMAGATE_AVAILABLE else 'Fallback'}")

    res = run_evaluation(tasks_dir, answers_path, output_dir, chain_file)
    print(f"\n[OK] Run Complete: {res['run_id']}")
    print(f"     Bundle Dir:   {res['bundle_dir']}")
    print(f"     Summary:      {res['summary']}")
    print(f"     Locked Files: {res['locked_files']}")


if __name__ == "__main__":
    main()
