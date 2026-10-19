"""Tiered router — deterministic intent classification mapped to model tiers.

Contract (aligned with the verified deployment of the original system):

    small     -> local deterministic handling (no LLM call)
    normal    -> fast tier  (Nemotron Nano class) for everyday calls
    reasoning -> serious reasoning tier (Nemotron Super class)
    heavy     -> long-synthesis tier
    research  -> external search tool (Tavily), when configured

Honesty rule: when a tier has no backend (missing key / model id / tool), the
router returns a structured error carrying the exact reason. It NEVER
fabricates an answer.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .nebius import BackendError, TokenFactoryClient, load_env_file

TIERS = ("small", "normal", "reasoning", "heavy", "research")

_REASONING_HINTS = (
    "analyze", "analiza", "analyse", "compare", "compara", "why", "por que", "por qué",
    "step by step", "paso a paso", "prove", "demuestra", "evaluate", "evalúa", "evalua",
    "diagnose", "diagnostica", "reason", "razona", "trade-off", "tradeoff", "debug",
)
_HEAVY_HINTS = (
    "synthesize", "sintetiza", "whitepaper", "full report", "informe completo",
    "long document", "documento largo", "plan completo", "estrategia completa", "deep dive",
)
_RESEARCH_HINTS = (
    "search the web", "busca en la web", "latest news", "últimas noticias", "ultimas noticias",
    "current price", "precio actual", "investiga en", "look up online", "search online",
)


@dataclass
class Decision:
    tier: str
    reason: str


def classify(prompt: str) -> Decision:
    """Deterministic classification. Same input -> same tier, always."""
    p = prompt.lower()
    if any(h in p for h in _RESEARCH_HINTS):
        return Decision("research", "external information requested")
    if any(h in p for h in _HEAVY_HINTS) or len(prompt) > 4000:
        return Decision("heavy", "long synthesis requested")
    if any(h in p for h in _REASONING_HINTS) or len(prompt) > 1200:
        return Decision("reasoning", "reasoning cues or long prompt")
    return Decision("normal", "everyday call (default tier)")


def tier_models() -> dict[str, str]:
    """Model id per tier, from the environment (.env). Empty string = not configured."""
    fast = os.environ.get("TATTVA_MODEL_FAST", "").strip()
    reasoning = os.environ.get("TATTVA_MODEL_REASONING", "").strip()
    heavy = os.environ.get("TATTVA_MODEL_HEAVY", "").strip() or reasoning
    return {"normal": fast, "reasoning": reasoning, "heavy": heavy}


def research(prompt: str, *, timeout: int = 30) -> dict[str, Any]:
    """External research via Tavily (only if TAVILY_API_KEY is configured)."""
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key:
        raise BackendError("research backend not configured (TAVILY_API_KEY missing)")
    payload = json.dumps(
        {"api_key": key, "query": prompt, "max_results": 5, "search_depth": "basic"}
    ).encode("utf-8")
    req = urllib.request.Request("https://api.tavily.com/search", data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise BackendError(f"tavily search failed (HTTP {exc.code})", status=exc.code, detail=detail) from exc
    except Exception as exc:  # noqa: BLE001
        raise BackendError(f"tavily network error: {type(exc).__name__}: {exc}") from exc
    results = [
        {"title": r.get("title"), "url": r.get("url")}
        for r in (body.get("results") or [])
    ]
    return {"answer": body.get("answer", ""), "results": results, "latency_s": round(time.monotonic() - t0, 3)}


def route(
    prompt: str,
    *,
    tier: str = "auto",
    client: TokenFactoryClient | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    extra_messages: list[dict] | None = None,
) -> dict[str, Any]:
    """Route one prompt. Returns a JSON-serializable dict; never raises on backend failure."""
    load_env_file()
    if tier == "auto":
        decision = classify(prompt)
    else:
        if tier not in TIERS:
            return {"status": "error", "tier": tier, "error": f"unknown tier {tier!r}; valid: {TIERS}"}
        decision = Decision(tier, "forced by caller")

    out: dict[str, Any] = {"tier": decision.tier, "classification": decision.reason}
    try:
        if decision.tier == "small":
            out.update(
                status="ok",
                model=None,
                reply=f"[small] handled locally without an LLM call. Prompt length: {len(prompt)} chars.",
                usage={},
                latency_s=0.0,
            )
            return out

        if decision.tier == "research":
            res = research(prompt)
            out.update(
                status="ok",
                model="tavily-search",
                reply=res["answer"] or "(no synthesized answer — see results)",
                results=res["results"],
                usage={},
                latency_s=res["latency_s"],
            )
            return out

        model = tier_models().get(decision.tier, "")
        client = client or TokenFactoryClient()
        messages = list(extra_messages or []) + [{"role": "user", "content": prompt}]
        result = client.chat(messages, model, temperature=temperature, max_tokens=max_tokens)
        out.update(
            status="ok",
            model=result.model,
            reply=result.text,
            usage=result.usage,
            latency_s=result.latency_s,
        )
        return out
    except BackendError as exc:
        out.update(
            status="error",
            error=str(exc),
            http_status=exc.status,
            detail=exc.detail,
            model=tier_models().get(decision.tier, ""),
        )
        return out
