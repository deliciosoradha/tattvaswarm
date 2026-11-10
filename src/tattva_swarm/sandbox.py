"""Code engine — hardened Docker sandbox for running agent code. stdlib only.

Two interchangeable backends, auto-selected:

* ``rust``   — the ``tattva-engine exec`` binary (``engine/`` crate in this
  repo; build once with ``bash engine/build.sh``). Preferred: the hardened
  flags, wall-clock timeout and output caps are implemented in the Rust core.
* ``docker`` — fallback that shells out to ``docker run`` with the same
  hardening flags, so the code engine still works before the Rust core is built.

Hardening applied in both backends: no network by default, memory cap, CPU
cap, pids cap, ``/tmp`` as a small tmpfs, wall-clock timeout, capped output.
Sandboxed code never runs on the host.

The runner interface mirrors the sandboxed-execution pattern popularised by
SWE-ReX / Open SWE (run a command in an isolated environment, return
stdout/stderr/exit code) — see ``docs/SANDBOX.md`` for how to swap in a cloud
sandbox provider.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_MEMORY = "256m"
DEFAULT_CPUS = "1"
DEFAULT_CAP = 65_536  # bytes per stream


class CodeEngineError(RuntimeError):
    """No code-engine backend could run the command (nothing was executed)."""


@dataclass
class SandboxResult:
    backend: str
    image: str
    command: str
    exit_code: int
    timed_out: bool
    wall_s: float
    stdout: str
    stderr: str
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def default_image() -> str:
    return os.environ.get("TATTVA_SANDBOX_IMAGE", "").strip() or "python:3.12-slim"


def _repo_engine_binary() -> Path | None:
    root = Path(__file__).resolve().parents[2]
    cand = root / "engine" / "target" / "release" / "tattva-engine"
    return cand if cand.is_file() else None


def find_engine_binary() -> str | None:
    """Locate the Rust core: env override, repo build, then PATH."""
    override = os.environ.get("TATTVA_ENGINE_BIN", "").strip()
    if override and Path(override).is_file():
        return override
    cand = _repo_engine_binary()
    if cand is not None:
        return str(cand)
    return shutil.which("tattva-engine")


def docker_available() -> bool:
    return shutil.which("docker") is not None


def backend_status() -> dict:
    """Honest snapshot of what the code engine can use right now."""
    engine = find_engine_binary()
    return {
        "rust_engine": engine,
        "docker_cli": docker_available(),
        "image": default_image(),
        "selected": "rust" if engine else ("docker" if docker_available() else None),
    }


def _truncate(text: str, cap: int) -> tuple[str, bool]:
    if len(text) <= cap:
        return text, False
    return text[:cap], True


def _run_rust(
    engine: str,
    command: str,
    image: str,
    timeout_s: float,
    allow_network: bool,
    workdir: str | None,
    memory: str,
    cpus: str,
    cap: int,
) -> SandboxResult:
    argv = [
        engine, "exec", "--json",
        "--cmd", command,
        "--image", image,
        "--timeout", str(timeout_s),
        "--memory", memory,
        "--cpus", cpus,
        "--cap", str(cap),
    ]
    if allow_network:
        argv.append("--allow-network")
    if workdir:
        argv += ["--workdir", str(workdir)]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s + 60)
    except FileNotFoundError as exc:
        raise CodeEngineError(f"rust engine binary vanished: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", "replace")
        return SandboxResult(
            backend="rust", image=image, command=command, exit_code=124, timed_out=True,
            wall_s=timeout_s, stdout=out, stderr="", error="rust engine watchdog fired",
        )

    lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
    if not lines:
        raise CodeEngineError(f"rust engine produced no output (rc={proc.returncode}): {proc.stderr[:300]}")
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise CodeEngineError(f"rust engine output was not JSON: {lines[-1][:300]}") from exc
    if "error" in payload:
        raise CodeEngineError(str(payload["error"]))
    return SandboxResult(
        backend="rust",
        image=str(payload.get("image", image)),
        command=command,
        exit_code=int(payload.get("exit_code", -1)),
        timed_out=bool(payload.get("timed_out", False)),
        wall_s=float(payload.get("wall_s", 0.0)),
        stdout=str(payload.get("stdout", "")),
        stderr=str(payload.get("stderr", "")),
        stdout_truncated=bool(payload.get("stdout_truncated", False)),
        stderr_truncated=bool(payload.get("stderr_truncated", False)),
    )


def _run_docker(
    command: str,
    image: str,
    timeout_s: float,
    allow_network: bool,
    workdir: str | None,
    memory: str,
    cpus: str,
    cap: int,
) -> SandboxResult:
    name = f"tattva-sandbox-{os.getpid()}"
    argv = ["docker", "run", "--rm", "--name", name,
            "--memory", memory, "--cpus", cpus, "--pids-limit", "128"]
    if not allow_network:
        argv += ["--network", "none"]
    if workdir:
        argv += ["-v", f"{workdir}:/work", "-w", "/work"]
    else:
        argv += ["-w", "/tmp"]
    argv += ["--tmpfs", "/tmp:rw,size=64m", image, "/bin/sh", "-lc", command]

    t0 = time.monotonic()
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s)
        out, err, code, timed_out = proc.stdout, proc.stderr, proc.returncode, False
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        code = 124
        subprocess.run(["docker", "kill", name], capture_output=True)
        out = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", "replace")
        err = exc.stderr if isinstance(exc.stderr, str) else (exc.stderr or b"").decode("utf-8", "replace")
    except FileNotFoundError as exc:
        raise CodeEngineError("docker CLI not found") from exc

    out, out_tr = _truncate(out or "", cap)
    err, err_tr = _truncate(err or "", cap)
    return SandboxResult(
        backend="docker", image=image, command=command, exit_code=code,
        timed_out=timed_out, wall_s=round(time.monotonic() - t0, 3),
        stdout=out, stderr=err, stdout_truncated=out_tr, stderr_truncated=err_tr,
    )


def run_code(
    command: str,
    *,
    image: str | None = None,
    timeout_s: float = 30.0,
    allow_network: bool = False,
    workdir: str | None = None,
    memory: str = DEFAULT_MEMORY,
    cpus: str = DEFAULT_CPUS,
    cap: int = DEFAULT_CAP,
) -> SandboxResult:
    """Run ``command`` inside the sandbox. Never executes on the host."""
    if not command.strip():
        raise CodeEngineError("empty command")
    image = image or default_image()
    engine = find_engine_binary()
    if engine:
        return _run_rust(engine, command, image, timeout_s, allow_network, workdir, memory, cpus, cap)
    if docker_available():
        return _run_docker(command, image, timeout_s, allow_network, workdir, memory, cpus, cap)
    raise CodeEngineError(
        "no code-engine backend available: build the Rust core (bash engine/build.sh) "
        "or install Docker"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tattva_swarm.sandbox",
                                     description="Run one command in the hardened sandbox.")
    parser.add_argument("--cmd", required=True)
    parser.add_argument("--image", default=None)
    parser.add_argument("--timeout", type=float, default=30.0, dest="timeout_s")
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--workdir", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run_code(
            args.cmd, image=args.image, timeout_s=args.timeout_s,
            allow_network=args.allow_network, workdir=args.workdir,
        )
    except CodeEngineError as exc:
        if args.json:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"[code-engine] error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        print(f"[code-engine] backend={result.backend} exit={result.exit_code} "
              f"timed_out={result.timed_out} wall={result.wall_s}s", file=sys.stderr)
    return result.exit_code if result.exit_code >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
