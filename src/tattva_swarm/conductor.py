"""Kanban-style conductor: parallel workers -> verifier -> synthesizer.

Reads a JSON task graph (see ``demos/tasks_research.example.json``):

    {
      "goal": "...",
      "tasks": [{"id": "t1", "prompt": "...", "tier": "normal"}, ...],
      "verify": true,
      "synthesize": true
    }

Workers run in parallel threads, each one an LLM call through the tiered
router. Then each result is verified by a fast model and, optionally, a heavy
model synthesizes the final answer. Backend failures are surfaced honestly in
the output — never fabricated.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from .nebius import BackendError, TokenFactoryClient, load_env_file
from .router import route, tier_models

_VERIFY_PROMPT = """You are a verifier in a worker swarm.
The worker was asked:
{task}

Its answer:
{answer}

Reply with exactly `VERIFIED` if the answer addresses the task and contains no obvious fabrication,
or `REJECTED: <one-line reason>` otherwise."""

_SYNTH_PROMPT = """You are the synthesizer of a worker swarm.

Goal: {goal}

Worker results:
{results}

Write the final answer for the user. Be concise. If some workers failed or were
rejected, note the unresolved items explicitly — do not invent missing content."""


def _usage_sum(*dicts: dict | None) -> int:
    total = 0
    for d in dicts:
        if isinstance(d, dict):
            total += int(d.get("total_tokens", 0) or 0)
    return total


def _run_task(task: dict, client: TokenFactoryClient) -> dict:
    out = route(task["prompt"], tier=task.get("tier", "auto"), client=client)
    out["id"] = task.get("id", "?")
    return out


def _verify(task: dict, result: dict, client: TokenFactoryClient, fast_model: str) -> dict:
    if result.get("status") != "ok":
        return {"id": result.get("id"), "verdict": "SKIPPED", "reason": "worker failed", "usage": {}}
    if not fast_model:
        return {"id": result.get("id"), "verdict": "SKIPPED", "reason": "no fast model configured for verification", "usage": {}}
    prompt = _VERIFY_PROMPT.format(task=task.get("prompt", "")[:2000], answer=result.get("reply", "")[:4000])
    try:
        r = client.chat([{"role": "user", "content": prompt}], fast_model, temperature=0, max_tokens=600)
    except BackendError as exc:
        return {"id": result.get("id"), "verdict": "ERROR", "reason": str(exc), "usage": {}}
    verdict_text = (r.text or "").strip()
    ok = verdict_text.upper().startswith("VERIFIED")
    return {
        "id": result.get("id"),
        "verdict": "VERIFIED" if ok else "REJECTED",
        "detail": verdict_text[:300],
        "usage": r.usage,
    }


def run_graph(
    spec: dict,
    *,
    client: TokenFactoryClient | None = None,
    max_workers: int = 3,
) -> dict[str, Any]:
    """Run a task graph end-to-end. Never raises for backend failures; reports them."""
    load_env_file()
    client = client or TokenFactoryClient()
    tasks: list[dict] = list(spec.get("tasks") or [])
    if not tasks:
        return {"status": "error", "error": "spec has no tasks", "results": []}

    # 1) parallel workers
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(tasks)))) as pool:
        futures = {pool.submit(_run_task, t, client): t for t in tasks}
        for fut in as_completed(futures):
            results.append(fut.result())
    results.sort(key=lambda r: str(r.get("id")))

    # 2) verification (fast model)
    verifications: list[dict] = []
    if spec.get("verify", True):
        fast_model = tier_models().get("normal", "")
        with ThreadPoolExecutor(max_workers=max(1, min(4, len(results)))) as pool:
            futures = {pool.submit(_verify, t, r, client, fast_model): r for t, r in zip(tasks, results)}
            for fut in as_completed(futures):
                verifications.append(fut.result())
        verifications.sort(key=lambda v: str(v.get("id")))

    # 3) synthesis (heavy model)
    synthesis: dict[str, Any] | None = None
    if spec.get("synthesize", True):
        heavy_model = tier_models().get("heavy") or tier_models().get("reasoning")
        good = [r for r in results if r.get("status") == "ok"]
        if not good:
            synthesis = {"status": "error", "error": "no successful worker results to synthesize"}
        elif not heavy_model:
            synthesis = {"status": "error", "error": "no heavy/reasoning model configured"}
        else:
            joined = "\n\n".join(f"[{r['id']}]\n{r.get('reply', '')[:2500]}" for r in good)
            try:
                s = client.chat(
                    [{"role": "user", "content": _SYNTH_PROMPT.format(goal=spec.get("goal", "(no goal given)"), results=joined)}],
                    heavy_model,
                    temperature=0.2,
                    max_tokens=900,
                )
                synthesis = {"status": "ok", "model": s.model, "reply": s.text, "usage": s.usage, "latency_s": s.latency_s}
            except BackendError as exc:
                synthesis = {"status": "error", "error": str(exc)}

    usage_total = sum(_usage_sum(r.get("usage")) for r in results)
    usage_total += sum(_usage_sum(v.get("usage")) for v in verifications)
    if synthesis and synthesis.get("status") == "ok":
        usage_total += _usage_sum(synthesis.get("usage"))

    return {
        "goal": spec.get("goal", ""),
        "results": results,
        "verifications": verifications,
        "synthesis": synthesis,
        "usage_total_tokens": usage_total,
    }
