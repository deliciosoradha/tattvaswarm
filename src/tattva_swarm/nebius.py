"""Nebius Token Factory client (OpenAI-compatible) — stdlib only.

Design rules:
  - local-first: every call is logged to a local usage ledger (JSONL)
  - honest failures: `BackendError` is raised; callers must surface it,
    never fabricate an answer when the backend fails.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"


def _load_env_into(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_env_file(path: Path | None = None) -> None:
    """Load environment for TattvaSwarm.

    Order (first value wins; the real process environment always wins):

      1. repo ``.env`` (or an explicit ``path``)
      2. ``$TATTVA_HOME/nebius.env`` — private per-user file for secrets,
         so your API key never needs to live inside the repository

    Never overrides variables already set in the process environment.
    """
    _load_env_into(path or Path(".env"))
    if path is None:
        _load_env_into(tattva_home() / "nebius.env")


def tattva_home() -> Path:
    """Local sovereign home for memory, tasks and ledgers. Nothing here leaves the machine."""
    home = Path(os.environ.get("TATTVA_HOME", "~/.tattva")).expanduser()
    home.mkdir(parents=True, exist_ok=True)
    return home


class BackendError(RuntimeError):
    """The backend could not serve the request.

    Callers must surface this error with its exact reason — TattvaSwarm never
    invents an answer when the backend is unavailable.
    """

    def __init__(self, reason: str, *, status: int | None = None, detail: str = ""):
        super().__init__(reason)
        self.reason = reason
        self.status = status
        self.detail = detail


@dataclass
class ChatResult:
    text: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    latency_s: float = 0.0


class TokenFactoryClient:
    """Minimal OpenAI-compatible client for Nebius Token Factory."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or os.environ.get("NEBIUS_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = (api_key if api_key is not None else os.environ.get("NEBIUS_API_KEY", "")).strip()
        self._ledger = tattva_home() / "usage.jsonl"

    # -- low level ---------------------------------------------------------
    def _request(self, endpoint: str, payload: dict | None = None, *, timeout: int = 120) -> tuple[int, Any]:
        url = f"{self.base_url}{endpoint}"
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return exc.code, {"error_body": body[:800]}
        except Exception as exc:  # noqa: BLE001 — surface exact failure
            raise BackendError(f"network error: {type(exc).__name__}: {exc}") from exc

    # -- public API --------------------------------------------------------
    def list_models(self) -> list[str]:
        if not self.api_key:
            raise BackendError("NEBIUS_API_KEY is not set")
        status, body = self._request("/models", timeout=30)
        if status != 200 or not isinstance(body, dict):
            raise BackendError(f"GET /models failed (HTTP {status})", status=status, detail=str(body)[:300])
        return sorted(m.get("id", "?") for m in body.get("data", []))

    def chat(
        self,
        messages: list[dict],
        model: str,
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout: int = 180,
    ) -> ChatResult:
        if not model:
            raise BackendError("model id is empty (set TATTVA_MODEL_* in .env or pass --model)")
        if not self.api_key:
            raise BackendError("NEBIUS_API_KEY is not set")
        payload: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature}
        if max_tokens:
            payload["max_tokens"] = max_tokens
        t0 = time.monotonic()
        status, body = self._request("/chat/completions", payload, timeout=timeout)
        latency = round(time.monotonic() - t0, 3)
        if status != 200 or not isinstance(body, dict) or "choices" not in body:
            raise BackendError(
                f"POST /chat/completions failed (HTTP {status})",
                status=status,
                detail=str(body)[:300],
            )
        result = ChatResult(
            text=body["choices"][0].get("message", {}).get("content", ""),
            model=body.get("model", model),
            usage=body.get("usage", {}) or {},
            latency_s=latency,
        )
        self._log_usage(
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "model": result.model,
                "usage": result.usage,
                "latency_s": latency,
            }
        )
        return result

    def _log_usage(self, entry: dict) -> None:
        """Best-effort local usage ledger — never breaks a run."""
        try:
            with self._ledger.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass
