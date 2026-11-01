#!/usr/bin/env python3
"""Validate the Tattva Taylor-Green benchmark and emit Devpost evidence.

The script is deliberately stdlib-only.  It:

  1. runs `shiva tattva-benchmark --json` (or reuses a captured JSON run),
  2. verifies that the field is non-trivial: non-zero vorticity, enstrophy
     and kinetic energy, bounded divergence/Poisson residuals, mass balance,
  3. records the exact command, logs, environment, license and commit,
  4. writes a SHA-256 manifest and a human-readable report,
  5. optionally attests one small LLM call on Nebius Token Factory /
     NVIDIA NIM.  The cloud attestation is separate from the CPU solver and
     is never used to claim that the solver itself ran on a GPU.

Secrets are read from the environment, `.env`, or `$TATTVA_HOME/nebius.env`
and are never printed or written to the evidence files.

Usage:
  python3 scripts/validate_tattva_benchmark.py --n 108000 --steps 40
  python3 scripts/validate_tattva_benchmark.py --cloud --provider auto
  python3 scripts/validate_tattva_benchmark.py --input-json /path/to/run.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "tattva-benchmark-evidence/v1"
DEFAULT_NEBIUS_BASE = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"
DEFAULT_NEBIUS_MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
DEFAULT_NVIDIA_MODEL = "nvidia/nemotron-3.5-lightning-30b-a3b"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8", errors="replace"))


def redact(text: str, secret: str) -> str:
    if secret:
        text = text.replace(secret, "<redacted>")
    return text[:1200]


def load_env_file(path: Path) -> None:
    """Small .env loader that never overrides an existing environment var."""
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_private_env() -> None:
    # Look in common, non-repo locations.  The key itself is never logged.
    load_env_file(Path.cwd() / ".env")
    tattva_home = Path(os.environ.get("TATTVA_HOME", str(Path.home() / ".tattva")))
    load_env_file(tattva_home / "nebius.env")


def git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=20,
        ).strip()
    except Exception:
        return ""


def detect_license(root: Path) -> dict:
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md"):
        path = root / name
        if not path.is_file():
            continue
        head = path.read_text(encoding="utf-8", errors="replace")[:4096]
        lowered = head.lower()
        if "apache license" in lowered and "version 2.0" in lowered:
            spdx = "Apache-2.0"
        elif "mit license" in lowered:
            spdx = "MIT"
        elif "gnu general public license" in lowered:
            spdx = "GPL-3.0-or-later"
        else:
            spdx = "UNKNOWN"
        return {
            "file": name,
            "spdx": spdx,
            "sha256": sha256_file(path),
            "first_line": head.splitlines()[0].strip() if head.splitlines() else "",
        }
    return {"file": None, "spdx": None, "sha256": None, "first_line": ""}


def run_benchmark(binary: Path, n: int, steps: int, reynolds: float, timeout: int, root: Path) -> tuple[dict, dict]:
    try:
        binary_arg = str(binary.relative_to(root))
    except ValueError:
        binary_arg = str(binary)
    cmd = [
        binary_arg,
        "tattva-benchmark",
        str(n),
        "--steps",
        str(steps),
        "--re",
        str(reynolds),
        "--json",
    ]
    started = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        elapsed = time.monotonic() - started
        stdout, stderr, rc = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - started
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        rc = 124

    parsed: dict = {}
    parse_error = ""
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError as exc:
        parse_error = f"{type(exc).__name__}: {exc}"

    record = {
        "command": cmd,
        "cwd": ".",
        "started_at": utc_now(),
        "elapsed_s": round(elapsed, 4),
        "exit_code": rc,
        "stdout_sha256": sha256_text(stdout),
        "stderr_sha256": sha256_text(stderr),
        "stdout": stdout,
        "stderr": stderr,
        "json_parse_error": parse_error,
    }
    return parsed, record


def normalize_value(value) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def make_check(check_id: str, status: str, detail: str) -> dict:
    return {"id": check_id, "status": status, "detail": detail}


def validate_metrics(report: dict, n: int) -> tuple[list[dict], dict]:
    fluid = report.get("fluid") or {}
    initial = report.get("initial") or {}
    checks: list[dict] = []

    def number(obj: dict, key: str) -> float | None:
        value = obj.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        return None

    cells = number(fluid, "cells_solved")
    grid_nx = number(fluid, "grid_nx")
    grid_ny = number(fluid, "grid_ny")
    max_vort = number(fluid, "max_vorticity")
    init_vort = number(initial, "max_vorticity")
    enstrophy = number(fluid, "enstrophy")
    ke = number(fluid, "kinetic_energy")
    mass_res = number(fluid, "mass_residual")
    div_res = number(fluid, "divergence_residual")
    poisson_res = number(fluid, "poisson_residual")
    cfl = number(fluid, "cfl")

    if cells is None or grid_nx is None or grid_ny is None:
        checks.append(make_check("grid", "FAIL", "fluid grid/cells fields missing"))
    elif int(cells) != int(grid_nx * grid_ny):
        checks.append(make_check("grid", "FAIL", f"cells_solved={cells} != nx*ny={grid_nx * grid_ny}"))
    elif int(cells) < n:
        checks.append(make_check("grid", "FAIL", f"cells_solved={cells} < requested n={n}"))
    else:
        checks.append(make_check("grid", "PASS", f"{int(grid_nx)} x {int(grid_ny)} = {int(cells)} cells"))

    if max_vort is None or init_vort is None:
        checks.append(make_check("vorticity", "FAIL", "vorticity fields missing"))
    elif max_vort < 0.1 or init_vort < 0.1:
        checks.append(
            make_check(
                "vorticity",
                "FAIL",
                f"max_vorticity={max_vort} / initial={init_vort} (expected >= 0.1; avoids a zero-field solve)",
            )
        )
    else:
        checks.append(
            make_check(
                "vorticity",
                "PASS",
                f"initial={init_vort:.6g}, final={max_vort:.6g} s^-1 (non-trivial Taylor-Green field)",
            )
        )

    if ke is None or ke <= 1e-9:
        checks.append(make_check("kinetic_energy", "FAIL", f"kinetic_energy={ke}"))
    else:
        checks.append(make_check("kinetic_energy", "PASS", f"{ke:.6g} (∫ ½ρ|u|² dA)"))

    if enstrophy is None or enstrophy <= 1e-9:
        checks.append(make_check("enstrophy", "FAIL", f"enstrophy={enstrophy}"))
    else:
        checks.append(make_check("enstrophy", "PASS", f"{enstrophy:.6g} (½∫ω² dA)"))

    if mass_res is None or abs(mass_res) > 1e-9:
        checks.append(make_check("mass_balance", "FAIL", f"mass_residual={mass_res}"))
    else:
        checks.append(make_check("mass_balance", "PASS", f"relative residual={mass_res:.3e}"))

    if div_res is None or div_res > 0.1:
        checks.append(make_check("divergence", "FAIL", f"divergence_residual={div_res} (expected <= 0.1)"))
    else:
        checks.append(make_check("divergence", "PASS", f"{div_res:.3e} s^-1"))

    if poisson_res is None or poisson_res > 1.0:
        checks.append(make_check("poisson", "FAIL", f"poisson_residual={poisson_res} (expected <= 1.0)"))
    else:
        checks.append(make_check("poisson", "PASS", f"{poisson_res:.3e}"))

    if cfl is None or cfl >= 1.0:
        checks.append(make_check("cfl", "FAIL", f"cfl={cfl} (expected < 1.0)"))
    else:
        checks.append(make_check("cfl", "PASS", f"{cfl:.4g}"))

    summary = {
        "grid_nx": int(grid_nx) if grid_nx is not None else None,
        "grid_ny": int(grid_ny) if grid_ny is not None else None,
        "cells_solved": int(cells) if cells is not None else None,
        "initial_max_vorticity": init_vort,
        "max_vorticity": max_vort,
        "kinetic_energy": ke,
        "enstrophy": enstrophy,
        "mass_residual": mass_res,
        "divergence_residual": div_res,
        "poisson_residual": poisson_res,
        "cfl": cfl,
    }
    return checks, summary


def api_chat(base_url: str, key: str, model: str, prompt: str, timeout: int) -> dict:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 256,
        "temperature": 0,
    }
    # NVIDIA Nemotron 3.x models reason by default; the audit only needs a
    # short verdict.  Disabling thinking also avoids burning the whole
    # completion budget on reasoning_content (content=null).
    if "nvidia" in base_url.lower() and "nemotron" in model.lower():
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("Authorization", f"Bearer {key}")
    request.add_header("Content-Type", "application/json")
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            status = response.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    except Exception as exc:  # noqa: BLE001 - surface the exact failure, honestly
        return {
            "http_status": -1,
            "latency_s": round(time.monotonic() - started, 4),
            "error": redact(f"{type(exc).__name__}: {exc}", key),
            "body": "",
        }
    latency = round(time.monotonic() - started, 4)
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        parsed = None
    result = {
        "http_status": status,
        "latency_s": latency,
        "body_sha256": sha256_text(body),
        "body": redact(body, key),
    }
    if isinstance(parsed, dict):
        choices = parsed.get("choices") or []
        message = choices[0].get("message", {}) if choices else {}
        content = (
            message.get("content")
            or message.get("reasoning_content")
            or ""
        )
        upper = content.upper()
        result.update(
            {
                "request_id": parsed.get("id"),
                "model": parsed.get("model"),
                "usage": parsed.get("usage"),
                "reply": content[:1200],
                "reply_sha256": sha256_text(content),
                "verdict_pass": "VERDICT=PASS" in upper and "VERDICT=FAIL" not in upper,
            }
        )
    return result


def cloud_attestation(args: argparse.Namespace, summary: dict) -> dict:
    if not args.cloud:
        return {"status": "SKIPPED", "reason": "--cloud not requested; no credits consumed"}

    load_private_env()
    compact = {
        "grid": f"{summary.get('grid_nx')}x{summary.get('grid_ny')}",
        "cells": summary.get("cells_solved"),
        "initial_max_vorticity": summary.get("initial_max_vorticity"),
        "max_vorticity": summary.get("max_vorticity"),
        "enstrophy": summary.get("enstrophy"),
        "kinetic_energy": summary.get("kinetic_energy"),
        "divergence_residual": summary.get("divergence_residual"),
        "mass_residual": summary.get("mass_residual"),
    }
    prompt = (
        "Audit this 2-D Taylor-Green vortex benchmark result. "
        f"Metrics: {json.dumps(compact, sort_keys=True)}. "
        "Reply exactly with VERDICT=PASS or VERDICT=FAIL followed by one short reason. "
        "PASS means the field is non-trivial: non-zero vorticity and enstrophy, "
        "zero mass residual, bounded divergence."
    )

    attempts: list[dict] = []
    providers: list[tuple[str, str, str, str]] = []
    if args.provider in ("auto", "nebius"):
        nebius_base = (
            args.base_url
            or os.environ.get("NEBIUS_BASE_URL", "").strip()
            or DEFAULT_NEBIUS_BASE
        )
        # The operator's private env may point NEBIUS_BASE_URL at NVIDIA NIM
        # (the recorded fallback).  Pick a model that exists on that base.
        nebius_default_model = (
            DEFAULT_NVIDIA_MODEL if "nvidia" in nebius_base.lower() else DEFAULT_NEBIUS_MODEL
        )
        provider_name = "nvidia" if "nvidia" in nebius_base.lower() else "nebius"
        providers.append(
            (
                provider_name,
                nebius_base,
                os.environ.get("NEBIUS_API_KEY", "").strip(),
                args.model
                or os.environ.get("TATTVA_MODEL_FAST", "").strip()
                or nebius_default_model,
            )
        )
    if args.provider in ("auto", "nvidia"):
        providers.append(
            (
                "nvidia",
                args.nvidia_base_url or os.environ.get("NVIDIA_BASE_URL", "").strip() or DEFAULT_NVIDIA_BASE,
                os.environ.get("NVIDIA_API_KEY", "").strip() or os.environ.get("NVIDIA_NIM_API_KEY", "").strip(),
                args.nvidia_model or os.environ.get("NVIDIA_MODEL", "").strip() or DEFAULT_NVIDIA_MODEL,
            )
        )

    if not any(key for _, _, key, _ in providers):
        return {
            "status": "SKIPPED_NO_CREDENTIALS",
            "reason": "no NEBIUS_API_KEY / NVIDIA_API_KEY in env, .env or ~/.tattva/nebius.env",
            "attempts": [],
        }

    for provider, base_url, key, model in providers:
        if not key:
            attempts.append(
                {
                    "provider": provider,
                    "status": "SKIPPED_NO_KEY",
                    "base_url": base_url,
                    "model": model,
                }
            )
            continue
        attempt = api_chat(base_url, key, model, prompt, args.cloud_timeout)
        provider_kind = "nvidia-compatible" if "nvidia" in base_url.lower() else "nebius-token-factory"
        attempt.update(
            {
                "provider": provider,
                "provider_kind": provider_kind,
                "base_url": base_url,
                "model_requested": model,
            }
        )
        if attempt.get("http_status") == 200 and attempt.get("verdict_pass"):
            attempt["status"] = "PASS"
            attempts.append(attempt)
            return {
                "status": "PASS",
                "provider_used": provider,
                "attempts": attempts,
                "note": "This is a separate LLM audit call; the solver itself ran on CPU.",
            }
        attempt["status"] = "FAIL"
        attempts.append(attempt)
        if args.provider != "auto":
            break

    attempted = [item for item in attempts if item.get("status") == "FAIL"]
    last = attempted[-1] if attempted else (attempts[-1] if attempts else {})
    reason = "no successful cloud attestation"
    if last.get("http_status") == 402:
        reason = "HTTP 402 from the provider: no credits/quota available; no usage consumed"
    elif last.get("http_status") == -1:
        reason = f"transport error: {last.get('error', 'unknown')}"
    elif last.get("http_status") is not None and last.get("http_status") != 200:
        reason = f"provider returned HTTP {last.get('http_status')}"
    return {"status": "FAIL", "reason": reason, "attempts": attempts}


def write_manifest(root: Path, out_dir: Path) -> Path:
    paths: list[Path] = [
        root / "native" / "src" / "fluid.rs",
        root / "native" / "src" / "main.rs",
        root / "native" / "target" / "release" / "shiva",
        root / "scripts" / "validate_tattva_benchmark.py",
        root / "LICENSE",
        root / "README.md",
    ]
    paths.extend(sorted(out_dir.glob("*")))
    manifest = out_dir / "MANIFEST.sha256"
    lines = []
    seen: set[str] = set()
    for path in paths:
        if not path.is_file() or path.resolve() == manifest.resolve():
            continue
        try:
            relative = str(path.resolve().relative_to(root.resolve()))
        except ValueError:
            relative = str(path.resolve())
        if relative in seen:
            continue
        seen.add(relative)
        lines.append(f"{sha256_file(path)}  {relative}")
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


def render_markdown(report: dict) -> str:
    benchmark = report.get("benchmark") or {}
    fluid = benchmark.get("fluid") or report.get("fluid") or {}
    initial = benchmark.get("initial") or report.get("initial") or {}
    timing = benchmark.get("timing") or report.get("timing") or {}
    checks = report.get("checks") or []
    cloud = report.get("cloud_attestation") or {}
    lines = [
        "# Tattva Taylor-Green benchmark — validation report",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Schema: `{report['schema']}`",
        "",
        "## Project",
        "",
        f"- Repo root: `{report['repo']['root']}`",
        f"- Commit: `{report['repo']['commit'] or 'NOT_A_GIT_REPO'}`",
        f"- Dirty working tree: `{report['repo']['dirty']}`",
        f"- Remote: `{report['repo']['remote'] or 'NOT_CONFIGURED'}`",
        f"- License: `{report['license']['spdx'] or 'MISSING'}` ({report['license']['file'] or 'no LICENSE file'})",
        f"- Binary SHA-256: `{report['binary']['sha256']}`",
        "",
        "## Command",
        "",
        "```bash",
        " ".join(report["command"]),
        "```",
        "",
        "## Metrics",
        "",
        "| Metric | Initial | Final |",
        "|---|---:|---:|",
        f"| Max vorticity (s^-1) | {normalize_value(initial.get('max_vorticity'))} | {normalize_value(fluid.get('max_vorticity'))} |",
        f"| Enstrophy | {normalize_value(initial.get('enstrophy'))} | {normalize_value(fluid.get('enstrophy'))} |",
        f"| Kinetic energy | {normalize_value(initial.get('kinetic_energy'))} | {normalize_value(fluid.get('kinetic_energy'))} |",
        f"| Grid | — | {fluid.get('grid_nx')} x {fluid.get('grid_ny')} |",
        f"| Steps | — | {fluid.get('step')} |",
        f"| Time step (s) | — | {normalize_value(fluid.get('dt'))} |",
        f"| Simulation time (s) | — | {normalize_value(fluid.get('time'))} |",
        f"| CFL | — | {normalize_value(fluid.get('cfl'))} |",
        f"| Mass residual | — | {normalize_value(fluid.get('mass_residual'))} |",
        f"| Divergence residual | — | {normalize_value(fluid.get('divergence_residual'))} |",
        f"| Poisson residual | — | {normalize_value(fluid.get('poisson_residual'))} |",
        f"| Vorticity retention | — | {normalize_value(fluid.get('vorticity_retention'))} |",
        "",
        f"Wall-clock: `{timing.get('elapsed_s')}` s; throughput: `{timing.get('solves_per_sec')}` cell-steps/s.",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "|---|---|---|",
    ]
    for check in checks:
        lines.append(f"| {check['id']} | **{check['status']}** | {check['detail']} |")
    lines.extend(["", "## Cloud attestation (separate from the CPU solver)", ""])
    if cloud.get("status") == "SKIPPED":
        lines.append(f"SKIPPED — {cloud.get('reason')}")
    elif cloud.get("status") == "SKIPPED_NO_CREDENTIALS":
        lines.append(f"SKIPPED — {cloud.get('reason')}")
    else:
        lines.append(f"Status: **{cloud.get('status')}**")
        if cloud.get("provider_used"):
            lines.append(f"Provider used: `{cloud.get('provider_used')}`")
        if cloud.get("reason"):
            lines.append(f"Reason: {cloud.get('reason')}")
        for attempt in cloud.get("attempts", []):
            lines.append(
                f"- `{attempt.get('provider')}` / `{attempt.get('provider_kind')}` / "
                f"`{attempt.get('model_requested')}`: HTTP `{attempt.get('http_status')}`, "
                f"status `{attempt.get('status')}`, latency `{attempt.get('latency_s')}` s"
            )
            if attempt.get("reply"):
                lines.append(f"  - reply: {attempt['reply'][:240]}")
            if attempt.get("usage"):
                lines.append(f"  - usage: `{json.dumps(attempt['usage'], sort_keys=True)}`")
    lines.extend(
        [
            "",
            "## Honesty notes",
            "",
            "- The solver is a CPU implementation of a 2-D Taylor-Green vortex. It does not claim GPU or Nebius execution.",
            "- The initial condition includes a divergence-free 3% perturbation, so the field is not a single symmetric mode.",
            "- The cloud attestation, when present, is one small LLM audit call to Nebius Token Factory or NVIDIA NIM. It is not evidence that the PDE solve ran in the cloud.",
            "- HTTP 402 means the provider had no credits/quota; the report records it as a failure and does not claim usage.",
            "",
            "## Artifacts",
            "",
            "- `benchmark.json` — parsed benchmark output",
            "- `run.log` — exact command, stdout and stderr",
            "- `environment.json` — host/toolchain/git snapshot",
            "- `validation-report.json` — machine-readable report",
            "- `validation-report.md` — this file",
            "- `cloud-attestation.json` — optional provider call (if attempted)",
            "- `MANIFEST.sha256` — SHA-256 of source, binary and evidence",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the Tattva Taylor-Green benchmark and emit Devpost evidence")
    parser.add_argument("--n", type=int, default=108_000, help="requested cell count (default 108000)")
    parser.add_argument("--steps", type=int, default=40, help="time steps (default 40)")
    parser.add_argument("--re", type=float, default=100.0, help="Reynolds number (default 100)")
    parser.add_argument("--binary", default="native/target/release/shiva", help="path to the shiva binary")
    parser.add_argument("--out-dir", default="devpost-evidence", help="evidence output directory")
    parser.add_argument("--timeout", type=int, default=300, help="benchmark timeout in seconds")
    parser.add_argument("--input-json", default="", help="reuse a captured benchmark JSON instead of running")
    parser.add_argument("--cloud", action="store_true", help="attempt one small cloud LLM audit call")
    parser.add_argument("--require-cloud", action="store_true", help="fail if the cloud attestation fails")
    parser.add_argument("--provider", choices=("auto", "nebius", "nvidia"), default="auto")
    parser.add_argument("--model", default="", help="Nebius model override")
    parser.add_argument("--base-url", default="", help="Nebius base URL override")
    parser.add_argument("--nvidia-model", default="", help="NVIDIA NIM model override")
    parser.add_argument("--nvidia-base-url", default="", help="NVIDIA NIM base URL override")
    parser.add_argument("--cloud-timeout", type=int, default=60)
    args = parser.parse_args()

    root = Path.cwd().resolve()
    binary = (root / args.binary).resolve()
    out_dir = (root / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.input_json:
        input_path = Path(args.input_json).resolve()
        try:
            report = json.loads(input_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] cannot read --input-json: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
        run_record = {
            "command": ["<reused>", str(input_path)],
            "cwd": str(root),
            "started_at": utc_now(),
            "elapsed_s": 0.0,
            "exit_code": 0,
            "stdout_sha256": sha256_text(input_path.read_text(encoding="utf-8", errors="replace")),
            "stderr_sha256": sha256_text(""),
            "stdout": input_path.read_text(encoding="utf-8", errors="replace"),
            "stderr": "",
            "json_parse_error": "",
            "reused": True,
        }
    else:
        if not binary.is_file():
            print(f"[FAIL] binary not found: {binary}", file=sys.stderr)
            print("       run: (cd native && cargo build --release -j 2)", file=sys.stderr)
            return 2
        report, run_record = run_benchmark(binary, args.n, args.steps, args.re, args.timeout, root)

    checks, summary = validate_metrics(report, args.n)
    license_info = detect_license(root)
    if license_info["spdx"] in ("Apache-2.0", "MIT", "GPL-3.0-or-later"):
        checks.insert(0, make_check("license", "PASS", f"{license_info['spdx']} ({license_info['file']})"))
    else:
        checks.insert(0, make_check("license", "FAIL", "no recognized LICENSE file (Apache-2.0/MIT/GPL)"))

    remote = git(root, "remote", "get-url", "origin")
    if remote and ("github.com" in remote or "gitlab.com" in remote):
        checks.insert(1, make_check("public_remote", "PASS", remote))
    else:
        checks.insert(
            1,
            make_check(
                "public_remote",
                "WARN",
                "no public origin remote configured; push to GitHub/GitLab before claiming a public repo",
            ),
        )

    cloud = cloud_attestation(args, summary)
    if args.require_cloud:
        checks.append(
            make_check(
                "cloud_attestation",
                "PASS" if cloud.get("status") == "PASS" else "FAIL",
                f"status={cloud.get('status')}",
            )
        )
    elif cloud.get("status") in ("PASS", "FAIL"):
        checks.append(
            make_check(
                "cloud_attestation",
                "WARN" if cloud.get("status") == "FAIL" else "PASS",
                f"status={cloud.get('status')}; optional unless --require-cloud",
            )
        )

    env = {
        "generated_at": utc_now(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "processor_count": os.cpu_count(),
        "rustc": (subprocess.run(["rustc", "--version"], capture_output=True, text=True).stdout.strip()
                  if shutil.which("rustc") else "NOT_FOUND"),
        "kernel": platform.release(),
    }
    try:
        meminfo = Path("/proc/meminfo").read_text(encoding="utf-8", errors="replace")
        for line in meminfo.splitlines():
            if line.startswith("MemTotal:"):
                env["mem_total_kb"] = int(line.split()[1])
                break
    except OSError:
        pass

    try:
        out_rel = out_dir.resolve().relative_to(root.resolve())
        dirty = bool(
            git(
                root,
                "status",
                "--porcelain",
                "--",
                ".",
                f":(exclude){out_rel}",
            )
        )
    except ValueError:
        dirty = bool(git(root, "status", "--porcelain"))
    def display_path(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(root.resolve()))
        except ValueError:
            return str(path)

    repo_info = {
        "root": ".",
        "commit": git(root, "rev-parse", "HEAD"),
        "dirty": dirty,
        "remote": git(root, "remote", "get-url", "origin"),
    }
    binary_info = {
        "path": display_path(binary),
        "exists": binary.is_file(),
        "sha256": sha256_file(binary) if binary.is_file() else None,
        "size_bytes": binary.stat().st_size if binary.is_file() else None,
    }
    result = {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "repo": repo_info,
        "license": license_info,
        "binary": binary_info,
        "command": run_record["command"],
        "run": run_record,
        "benchmark": report,
        "summary": summary,
        "checks": checks,
        "cloud_attestation": cloud,
        "artifacts": {},
    }

    # Write raw evidence first, then the report, then the manifest.
    (out_dir / "benchmark.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "environment.json").write_text(json.dumps(env, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out_dir / "cloud-attestation.json").write_text(json.dumps(cloud, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    run_log = [
        f"command: {' '.join(str(part) for part in run_record['command'])}",
        f"cwd: {run_record['cwd']}",
        f"started_at: {run_record['started_at']}",
        f"elapsed_s: {run_record['elapsed_s']}",
        f"exit_code: {run_record['exit_code']}",
        "",
        "--- stdout ---",
        run_record["stdout"],
        "--- stderr ---",
        run_record["stderr"],
        "",
    ]
    (out_dir / "run.log").write_text("\n".join(run_log), encoding="utf-8")

    report_json = out_dir / "validation-report.json"
    report_md = out_dir / "validation-report.md"
    result["artifacts"] = {
        "benchmark_json": display_path(out_dir / "benchmark.json"),
        "run_log": display_path(out_dir / "run.log"),
        "environment_json": display_path(out_dir / "environment.json"),
        "validation_report_json": display_path(report_json),
        "validation_report_md": display_path(report_md),
        "cloud_attestation_json": display_path(out_dir / "cloud-attestation.json"),
        "manifest": display_path(out_dir / "MANIFEST.sha256"),
    }
    report_json.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report_md.write_text(render_markdown(result), encoding="utf-8")
    manifest = write_manifest(root, out_dir)

    failed = [check for check in checks if check["status"] == "FAIL"]
    print(f"[report] {report_json}")
    print(f"[report] {report_md}")
    print(f"[manifest] {manifest}")
    for check in checks:
        print(f"[{check['status']}] {check['id']}: {check['detail']}")
    print(f"[cloud] {cloud.get('status')}: {cloud.get('reason', '')}")
    if failed:
        print(f"[FAIL] {len(failed)} required check(s) failed", file=sys.stderr)
        return 1
    print("[PASS] benchmark evidence is non-trivial and internally consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
