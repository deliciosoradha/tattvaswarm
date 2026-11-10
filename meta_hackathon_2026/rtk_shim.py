#!/usr/bin/env python3
"""
RTK Shim — optimiza calls y privacidad (Shiva Router).

NEW WORK — Meta Global AI Developer Hackathon, Oct 27 - Nov 4, 2026.
Comprime prompts de forma determinista (dedup de líneas, truncado
por presupuesto) y redacta secretos antes de cualquier dispatch.
Sin dependencias externas.
"""
from __future__ import annotations
import hashlib, re
from typing import Dict

_SECRET = re.compile(r"(?i)(api[_-]?key|bearer|token|secret|password)\s*[:=]\s*\S+")
_UUID_PAT = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
_KEYLIKE = re.compile(rf"\b(sk-[A-Za-z0-9\-_]{{8,}}|(?!(?:{_UUID_PAT})\b)[A-Za-z0-9_\-]{{32,}})\b")


def redact(text: str) -> str:
    t = _SECRET.sub(lambda m: m.group(0).split("=")[0].split(":")[0] + "=[REDACTED]", text or "")
    return _KEYLIKE.sub("[REDACTED]", t)


def compress(prompt: str, max_chars: int = 4000) -> Dict:
    raw = redact(prompt or "")
    lines, seen, kept = raw.splitlines(), set(), []
    for ln in lines:
        k = ln.strip()
        if k and k not in seen:
            seen.add(k); kept.append(ln)
    out = "\n".join(kept)
    truncated = len(out) > max_chars
    if truncated:
        out = out[:max_chars]
    return {"text": out, "orig_chars": len(prompt or ""), "sent_chars": len(out),
            "saved_ratio": round(1 - len(out) / max(len(prompt or ""), 1), 4),
            "sha256": hashlib.sha256(out.encode()).hexdigest(), "truncated": truncated}


if __name__ == "__main__":
    print(compress("hola\nhola\napi_key=sk-1234567890abcdef seguir"))
