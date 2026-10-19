# Sandboxes (Contree) — isolated code execution backend

Status: CLI install **VERIFIED** (`contree-cli 0.9.4` via `uv tool`); profile
registration + quickstart **BLOCKED** on the Token Factory project ID
(operator action) — possibly followed by Sandboxes project activation.
Mapped to kanban H-026 (engine backend), H-031 (CLI build), H-032..H-034
(cookbook), H-035 (MCP).

Nebius Token Factory Sandboxes give applications and AI agents an isolated
environment to **execute code, evaluate results, and work with files**. In
TattvaSwarm they are the remote backend of the code engine (local Docker is
the offline fallback, see `docs/SANDBOX.md`) and the execution substrate for
the cookbook workflows below.

## Install (uv)

```bash
uv tool install "contree-cli==0.9.4"
contree --version        # contree-cli/0.9.4 Python/3.14.6 ...
```

`uv tool` puts the binary in `~/.local/bin/contree` (make sure that is on
`PATH`). Project source: `https://github.com/nebius/contree-cli`.

## Authenticate (one-time profile)

The CLI reads the token + project ID from the environment and saves a profile
to `~/.config/contree/auth.ini` (mode `0600`). Secrets never go into the repo,
docs, or process listings — the operator keeps them in `~/.tattva/`.

```bash
export NEBIUS_API_KEY=...      # from ~/.tattva/ (never printed)
export NEBIUS_AI_PROJECT=...   # Token Factory → Project settings (format e00…)
contree auth -y                # fully non-interactive
contree auth ls                # status must be `ok`
```

Profile probe status (from the official docs):

| Status | Meaning | Action |
|---|---|---|
| `ok` | Probe OK, Sandboxes permission present | continue |
| `inactive` | Token accepted but the Sandboxes permission is missing | project activation / access (contree@nebius.com) |
| `timeout` | 2-second probe timed out | check network, retry |
| `error` | Invalid credentials or other API error | recheck key + project |

## Quickstart (official, CLI 0.9.4)

```bash
contree images --prefix=ubuntu          # note the immutable UUID (first column)
export CONTREE_SESSION="tattva-$USER-$$"
contree use tag:ubuntu:latest

# retained run (no -D): advances the session image
contree run -- sh -c 'printf "ready\n" > /tmp/quickstart.txt'
contree run -D -- cat /tmp/quickstart.txt          # expected: ready

# disposable run (-D): must NOT advance the session
contree run -D -- sh -c 'printf "temporary\n" > /tmp/disposable.txt'
contree run -D -- test ! -e /tmp/disposable.txt    # exit 0 == stayed disposable
```

Each run starts fresh compute; the session only carries the selected image,
working directory, staged files, and history.

## JavaScript (Node) smoke

Sandboxes run arbitrary Linux images, so any runtime — including Node.js —
can be exercised or baked into a reusable image. Smoke once `auth` is `ok`:

```bash
contree run -D -- node --version                       # if the image ships node
contree run -D -- sh -lc 'node -e "console.log(\"js-ok\")"'
```

If the base image ships no Node, either install it once in a retained session
(`contree run -- apt-get update && apt-get install -y nodejs` style) or build
a reusable image with the supported Dockerfile subset (see
`build-reusable-custom-environment` in the cookbook).

## Cookbook (9 recipes → H-032..H-034)

Prepare and reuse
- `prepare-once-reuse-safely` — save one prepared image, reuse in independent runs
- `build-reusable-custom-environment` — Dockerfile subset build, immutable UUID, rebuild after a change

Run and observe
- `stream-a-build-or-test-run` — SSE stdout/stderr, reconnect, check the result
- `interact-with-a-process` — spawn a child, send two lines + EOF, collect response
- `generate-and-download-binary-artifact` — gzip artifact, download, check digest

Test and recover
- `try-two-coding-fixes` — two isolated patches, keep the passing branch
- `verify-with-networking-disabled` — prepared input verified with no guest network
- `run-bounded-evaluation-batch` — pass/fail/cancelled classification, cancel only your own work
- `recover-from-known-good-image` — retry corrected work from a recorded checkpoint

Docs base: `https://docs.tokenfactory.nebius.com/sandboxes/cookbook/<recipe>`.

## MCP (agent integration)

`contree-mcp` (via `uvx`) shares `~/.config/contree/auth.ini` with the CLI, so
one login covers both. 15 tools (`run`, `rsync`, `upload`, `download`,
`list_images`, `wait_operations`, …). Configure in any MCP client
(OpenCode/Claude/Codex) — tracked as H-035.

## Security notes

- API key + project ID live only in `~/.tattva/` and the CLI profile (0600).
- Tokens are never passed as command flags (visible in process listings).
- Sandbox inputs/outputs are treated as untrusted: no secrets in uploaded
  files; downloads verified before use.
