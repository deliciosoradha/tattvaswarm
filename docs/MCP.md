# MCP server — the swarm as tools for any agent

TattvaSwarm ships an **MCP (Model Context Protocol) server over stdio**, pure
stdlib: no dependencies, no network unless a tool needs it.

```bash
PYTHONPATH=src python3 -m tattva_swarm.mcp_server
```

## Client configuration (Claude Desktop / any MCP client)

```json
{
  "mcpServers": {
    "tattva-swarm": {
      "command": "python3",
      "args": ["-m", "tattva_swarm.mcp_server"],
      "env": { "PYTHONPATH": "/path/to/repo/src" }
    }
  }
}
```

## Tools (6)

| Tool | Arguments | What it does |
|---|---|---|
| `tattva_status` | — | Honest snapshot: API key presence, tier models, code-engine backends. |
| `tattva_route` | `prompt` (required), `tier` (`auto`\|`small`\|`normal`\|`reasoning`\|`heavy`\|`research`) | One prompt through the tiered NVIDIA Nemotron router on Nebius Token Factory. The `small` tier is answered locally and never touches the network. |
| `tattva_memory_add` | `text` (required), `kind`, `tags[]` | Store a note in local persistent memory (SQLite + FTS5). Data never leaves the machine. |
| `tattva_memory_search` | `query` (required), `limit` (1–50, default 5) | Full-text search over local memory, operator-safe quoting. |
| `tattva_swarm_run` | `workers`, `steps`, `seed`, `modulus`, `threads` | Deterministic logical swarm (Rust core when built). Same config → same checksum. |
| `tattva_code_run` | `command` (required), `image`, `timeout_s`, `allow_network`, `workdir` | One command inside the hardened sandbox (see [`SANDBOX.md`](SANDBOX.md)). Code never runs on the host. |

## Verified smoke (2026-10-19)

```console
$ printf '<initialize + tools/list + tools/call tattva_status>' \
  | PYTHONPATH=src python3 -m tattva_swarm.mcp_server
# initialize   -> {"name": "tattvaswarm", "version": "0.1.0"}
# tools/list   -> ['tattva_status', 'tattva_route', 'tattva_memory_add',
#                  'tattva_memory_search', 'tattva_swarm_run', 'tattva_code_run']
# tools/call   -> tattva_status: {"status": "ok", "api_key": "set ...", "tiers": {...}}
# stderr       -> [tattva-mcp] serving over stdio (protocol 2024-11-05, v0.1.0)
```

## Honesty rules

- Without an API key, `tattva_route` returns a structured **error** — it never
  fabricates an answer.
- `tattva_code_run` reports the real backend (`rust` / `docker`), real exit
  codes, and `timed_out` — or a structured error if no backend is available.
- Memory tools only ever touch the local SQLite file under `TATTVA_HOME`.
