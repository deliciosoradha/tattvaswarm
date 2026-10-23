# Sovereignty — what leaves your machine, and what does not

TattvaSwarm is local-first **by policy, not by promise**. This document is the
policy, and it is testable.

## Stays on your machine (always)

| Data | Where |
|---|---|
| Persistent memory (notes, assistant logs) | `$TATTVA_HOME/memory.sqlite3` |
| Per-call usage ledger | `$TATTVA_HOME/usage.jsonl` |
| Task graphs, run logs | `$TATTVA_HOME/` |
| API keys | `$TATTVA_HOME/nebius.env` (never inside the repository) |
| Everything else | your disk — there is no server component |

No telemetry. No analytics. No phone-home. The repository ships **synthetic
examples only** — no personal data, no real records.

## Leaves your machine (explicit allowlist)

| What | When | To whom |
|---|---|---|
| the prompt text of a routed call, plus system/context messages you pass | only for tiers `normal` / `reasoning` / `heavy` | `api.tokenfactory.nebius.com` |
| a search query | only when the `research` tier is selected **and** `TAVILY_API_KEY` is set | `api.tavily.com` |

Nothing else. If you configure no key, the system still runs — and answers
honestly that the backend is unavailable (`small` tier keeps working fully
locally, and every remote tier returns a structured error rather than
pretending).

> Note: this allowlist is a **documented policy table**, not a runtime
> firewall. The code sends prompts to the hosts above when those tiers are
> selected; there is no network-level blocklist. Removing the key is the
> kill switch (see guarantee 3).

## Your guarantees as the operator

1. **Read the ledger.** `$TATTVA_HOME/usage.jsonl` records every outbound call:
   model, token usage, latency, timestamp. If an entry is not in the ledger,
   it did not happen.
2. **Inspect before you commit.** `scripts/sanitize_check.sh` scans the repo
   for secrets, PII patterns, private paths and wallet addresses before any
   push.
3. **Kill switch by configuration.** Remove the key → remote tiers stop
   working immediately, with exact-reason errors. No silent fallback.

## Design consequences

- The router classifies deterministically (same input → same tier) so you can
  predict — and audit — which calls are eligible to leave the machine.
- `small`-tier handling never calls the network.
- Memory has no synchronization path — there is nothing to sync *to*.
