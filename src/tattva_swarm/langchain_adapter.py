"""Optional LangChain adapter — TattvaSwarm as a chat model + tools.

This module lives in the core package but imports ``langchain-core`` lazily:
the base install stays zero-dependency; LangChain users install the extra::

    pip install "tattva-swarm[langchain]"

Exposed pieces:

* ``ChatTattvaSwarm`` — a ``BaseChatModel`` whose replies come from the tiered
  Nemotron router on Nebius Token Factory (honest failures: backend errors are
  raised, never fabricated).
* ``get_tools()`` — LangChain ``StructuredTool`` objects mirroring the MCP
  surface: ``tattva_route``, ``tattva_memory_add``, ``tattva_memory_search``,
  ``tattva_swarm_run``, ``tattva_code_run``.
"""

from __future__ import annotations

import json
from typing import Any

try:  # pragma: no cover - exercised implicitly by the test suite
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_core.tools import StructuredTool

    LANGCHAIN_AVAILABLE = True
except ImportError:  # pragma: no cover - core install without the extra
    LANGCHAIN_AVAILABLE = False

from .router import route

MISSING_HINT = (
    "langchain-core is not installed. Install the optional extra:\n"
    '    pip install "tattva-swarm[langchain]"'
)


def _message_text(message: Any) -> str:
    """Best-effort text extraction from a LangChain message content value."""
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text", "")))
            else:
                parts.append(str(block))
        return "\n".join(p for p in parts if p)
    return str(content)


def _prompt_from_messages(messages: list[Any]) -> str:
    for message in reversed(messages):
        if message.__class__.__name__ == "HumanMessage":
            return _message_text(message)
    return "\n".join(_message_text(m) for m in messages if _message_text(m))


if LANGCHAIN_AVAILABLE:

    class ChatTattvaSwarm(BaseChatModel):
        """Chat model backed by the tiered TattvaSwarm router (Token Factory)."""

        tier: str = "auto"
        temperature: float = 0.0
        max_tokens: int | None = None

        @property
        def _llm_type(self) -> str:
            return "tattva-swarm"

        @property
        def _identifying_params(self) -> dict[str, Any]:
            return {"tier": self.tier, "temperature": self.temperature, "max_tokens": self.max_tokens}

        def _generate(
            self,
            messages: list[Any],
            stop: list[str] | None = None,
            run_manager: Any = None,
            **kwargs: Any,
        ) -> "ChatResult":
            prompt = _prompt_from_messages(messages)
            result = route(
                prompt,
                tier=self.tier,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            if result.get("status") != "ok":
                raise RuntimeError(
                    "tattva route failed: "
                    f"{result.get('error')} (tier={result.get('tier')}, "
                    f"http_status={result.get('http_status')})"
                )
            message = AIMessage(
                content=result.get("reply", ""),
                additional_kwargs={
                    "tattva": {
                        "tier": result.get("tier"),
                        "model": result.get("model"),
                        "usage": result.get("usage"),
                        "latency_s": result.get("latency_s"),
                    }
                },
            )
            return ChatResult(generations=[ChatGeneration(message=message)])

else:  # pragma: no cover - only imported when the extra is absent

    class ChatTattvaSwarm:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError(MISSING_HINT)


# ---------------------------------------------------------------------------
# tools (same surface as the MCP server)
# ---------------------------------------------------------------------------


def _tool_route(prompt: str, tier: str = "auto") -> str:
    """Route one prompt through the tiered Nemotron router."""
    return json.dumps(route(prompt, tier=tier), ensure_ascii=False)


def _tool_memory_add(text: str, kind: str = "note", tags: list[str] | None = None) -> str:
    """Store a note in the local memory (SQLite + FTS5). Never leaves the machine."""
    from .memory import Memory

    mem = Memory()
    try:
        entry_id = mem.add(text, kind=kind, source="langchain", tags=tags or None)
        return json.dumps({"status": "ok", "id": entry_id})
    finally:
        mem.close()


def _tool_memory_search(query: str, limit: int = 5) -> str:
    """Full-text search over the local memory."""
    from .memory import Memory

    mem = Memory()
    try:
        rows = mem.search(query, limit=limit)
        return json.dumps({"status": "ok", "count": len(rows), "results": rows}, ensure_ascii=False)
    finally:
        mem.close()


def _tool_swarm_run(workers: int = 100_000, steps: int = 6, seed: int = 7) -> str:
    """Run the deterministic logical swarm (Rust core when built)."""
    import subprocess

    from .sandbox import find_engine_binary

    engine = find_engine_binary()
    if engine:
        proc = subprocess.run(
            [engine, "run-swarm", "--workers", str(workers), "--steps", str(steps), "--seed", str(seed)],
            capture_output=True,
            text=True,
            timeout=600,
        )
        payload = json.loads([ln for ln in proc.stdout.strip().splitlines() if ln.strip()][-1])
        payload["implementation"] = "rust"
        return json.dumps(payload)

    from .engine import SwarmConfig, run_swarm

    report = run_swarm(SwarmConfig(workers=workers, steps=steps, seed=seed))
    payload = report.to_dict()
    payload["implementation"] = "python"
    return json.dumps(payload)


def _tool_code_run(command: str, timeout_s: float = 30.0) -> str:
    """Run one command in the hardened Docker sandbox (no network by default)."""
    from .sandbox import CodeEngineError, run_code

    try:
        result = run_code(command, timeout_s=timeout_s)
        return json.dumps(result.to_dict(), ensure_ascii=False)
    except CodeEngineError as exc:
        return json.dumps({"status": "error", "error": str(exc)})


def get_tools() -> list[Any]:
    """Return the TattvaSwarm tools as LangChain ``StructuredTool`` objects."""
    if not LANGCHAIN_AVAILABLE:
        raise RuntimeError(MISSING_HINT)
    return [
        StructuredTool.from_function(
            func=_tool_route,
            name="tattva_route",
            description="Route one prompt through the tiered NVIDIA Nemotron router (Nebius Token Factory).",
        ),
        StructuredTool.from_function(
            func=_tool_memory_add,
            name="tattva_memory_add",
            description="Store a note in the local persistent memory (SQLite + FTS5).",
        ),
        StructuredTool.from_function(
            func=_tool_memory_search,
            name="tattva_memory_search",
            description="Full-text search over the local memory.",
        ),
        StructuredTool.from_function(
            func=_tool_swarm_run,
            name="tattva_swarm_run",
            description="Run the deterministic logical swarm engine (Rust core when built, python reference otherwise).",
        ),
        StructuredTool.from_function(
            func=_tool_code_run,
            name="tattva_code_run",
            description="Run one command inside the hardened Docker sandbox (no network, caps, timeout).",
        ),
    ]
