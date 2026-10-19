# Code engine — the hardened sandbox

The code engine runs agent-authored commands in a **hardened container**. Code
never executes on the host.

Two interchangeable backends, auto-selected per call:

| Backend | Selected when | What it is |
|---|---|---|
| `rust` (preferred) | the `tattva-engine` binary is found (repo build, `TATTVA_ENGINE_BIN`, PATH) | The Rust core in `engine/`. Hardening flags, watchdog and output caps are implemented natively. |
| `docker` (fallback) | Docker CLI is available | `docker run` with the same hardening flags, so the engine works before the Rust core is built. |

Hardening applied by both backends:

- **no network** by default (`--network none`; opt-in with `allow_network=True`),
- memory cap (`256m`), CPU cap (`--cpus 1`), pids cap (`--pids-limit 128`),
- `/tmp` as a small 64 MiB tmpfs,
- **wall-clock timeout** with hard kill (exit code 124, `timed_out: true`),
- output capped at 64 KiB per stream (`stdout_truncated` / `stderr_truncated`).

## Usage

Python:

```python
from tattva_swarm.sandbox import run_code, backend_status

backend_status()
# {'rust_engine': '.../tattva-engine', 'docker_cli': True, 'image': 'python:3.12-slim', 'selected': 'rust'}

res = run_code("echo hello && head -1 /etc/os-release", timeout_s=10)
res.exit_code, res.stdout, res.timed_out
res.to_dict()          # JSON-ready — this is what the MCP tool returns
```

CLI:

```bash
PYTHONPATH=src python3 -m tattva_swarm.sandbox --cmd 'python3 -c "print(2+2)"' --json
```

Environment:

- `TATTVA_SANDBOX_IMAGE` — container image (default `python:3.12-slim`),
- `TATTVA_ENGINE_BIN` — explicit path to the Rust core binary.

## Verified evidence (2026-10-19, backend `rust`)

| Check | Result |
|---|---|
| `exec` echo + `head -1 /etc/os-release` | exit 0 · image `python:3.12-slim` · 4.8 s |
| `exec` `sleep 30` with timeout 3 s | exit 124 · `timed_out: true` · hard kill at 3.7 s |
| Determinism of the core | identical checksums vs the Python reference at 100k and 1M workers |

Full numbers: [`EVIDENCE.md`](EVIDENCE.md) §5.

## Swapping in a cloud sandbox provider

`run_code()` is the single choke point — the MCP tool (`tattva_code_run`), the
LangChain tool and the CLI all call it, and the result shape is
`SandboxResult.to_dict()`. Offloading execution to a cloud sandbox means adding
one adapter with the same contract, selected before the Docker fallback.

That adapter does **not exist yet** (state: PLANNED). Candidate: **Nebius
Sandboxes** (Contree). Honest current state: the Sandboxes API answers health
and `whoami` calls, but the permissions come back inactive until the Token
Factory project is activated for Sandboxes (the operator is requesting the real
project ID and activation). Until then, the local hardened backends above are
what runs — nothing about them is aspirational: every row in the table was
measured.
