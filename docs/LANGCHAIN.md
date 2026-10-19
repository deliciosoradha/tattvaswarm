# LangChain adapter

`tattva-swarm` works as a normal Python package with **zero dependencies**. For
LangChain users there is an optional extra that exposes TattvaSwarm as a chat
model and as a set of tools.

```bash
pip install "tattva-swarm[langchain]"   # installs langchain-core only
```

## Chat model

```python
from tattva_swarm.langchain_adapter import ChatTattvaSwarm

llm = ChatTattvaSwarm(tier="auto", max_tokens=512)
message = llm.invoke([("human", "Summarize why deterministic routing matters.")])
print(message.content)
print(message.additional_kwargs["tattva"])   # tier, model, usage, latency
```

- `tier` — `auto` (router decides), or pin one: `normal`, `reasoning`, `heavy`.
- Replies come from NVIDIA Nemotron models on Nebius Token Factory.
- **Honesty rule:** when the backend is missing or fails, the adapter raises
  `RuntimeError` carrying the real reason (`no_key`, `http_401`, …). It never
  fabricates an answer.

## Tools

```python
from tattva_swarm.langchain_adapter import get_tools

tools = get_tools()
# tattva_route · tattva_memory_add · tattva_memory_search ·
# tattva_swarm_run · tattva_code_run
```

These mirror the MCP server surface (`python3 -m tattva_swarm.mcp_server`), so
an agent gets the same capabilities through either interface:

| Tool | What it does |
|---|---|
| `tattva_route` | One prompt through the tiered Nemotron router |
| `tattva_memory_add` / `tattva_memory_search` | Local persistent memory (SQLite + FTS5), stays on the machine |
| `tattva_swarm_run` | Deterministic logical swarm (Rust core when built) |
| `tattva_code_run` | One command in the hardened Docker sandbox (no network by default) |

## Verified smoke (2026-10-19)

A live `ChatTattvaSwarm.invoke` call returned
`tattva langchain verified` from `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`
(148 tokens) — see `docs/EVIDENCE.md` §6. Unit tests mock the transport and
assert that backend errors are raised, not hidden.
