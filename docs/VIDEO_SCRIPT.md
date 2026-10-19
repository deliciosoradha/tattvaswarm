# Video script — TattvaSwarm (< 3 minutes, English audio or EN subtitles)

> Target length: **2:45–2:55**. Judges see the first 30 seconds first — make
> them count. All commands are copy-pasteable; run them once as a rehearsal.
>
> **Recording hygiene:** clean terminal (`clear`), neutral prompt, no `.env`
> contents on screen, no personal paths in the status bar. If your prompt
> shows your name/hostname, switch to a minimal prompt for the take:
> `export PS1='$ '`.

## Storyboard

### 0:00 – 0:20 · The problem (talking head or title card)

> "Personal AI today means renting someone else's servers. Your memories,
> your notes, your thinking — all of it sits in a cloud you don't control.
> TattvaSwarm is a personal AI that is sovereign by construction: local-first
> memory, a tiered router that only sends what you allow — to open NVIDIA
> Nemotron models on Nebius Token Factory."

On screen: `README.md` top, then the architecture block from
`docs/ARCHITECTURE.md`.

### 0:20 – 0:45 · What it is

> "One CLI. A deterministic router. Five tiers: small answers locally, never
> touching the network. Normal, reasoning and heavy tiers route to Nemotron
> Nano, Super and Ultra on Nebius Token Factory. And underneath, a logical
> swarm engine — millions of workers as state machines, not processes."

### 0:45 – 1:35 · Demo 1 — the router + Token Factory (live)

```bash
tattva doctor          # shows: key present, tiers, backend OK (28 models, 5 Nemotron)
tattva route "Say hello in one short line."
```

Show the JSON: `"model": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"`, latency,
token usage. Then a reasoning call:

```bash
tattva route "List three concrete trade-offs of local-first AI. Be brief." --tier reasoning
```

Show `nvidia/nemotron-3-super-120b-a12b`. Then:

```bash
tail -2 ~/.tattva/usage.jsonl   # local ledger: every outbound call, on your disk
```

### 1:35 – 1:55 · Demo 2 — memory that stays home

```bash
tattva memory add "The router prefers Nano for everyday calls" --kind note
tattva memory search Nano
```

> "Persistent memory, SQLite + full-text search, on this machine. Nothing
> syncs anywhere — there is nowhere to sync to."

### 1:55 – 2:35 · Demo 3 — the swarm conductor (the money shot)

```bash
python3 demos/demo_swarm_research.py
```

> "One goal, three parallel workers on Nemotron, a verifier pass, and a
> synthesis by Nemotron Ultra. Watch the verdicts — VERIFIED — and the total:
> under three thousand tokens for the whole run."

(If short on time: cut the 1M engine line; keep the conductor.)

Optional 10-second insert — the mass engine:

```bash
python3 demos/demo_mass_swarm.py   # shows 100k/1M logical workers + checksum
```

> "Same design, measured at 108 million logical workers in 5.8 seconds on one
> A100 — the numbers are in the repo, with conditions and checksums."

### 2:35 – 2:55 · Close

> "Apache-2.0, one pip-free core, sixty seconds to verify yourself:
> the repo has the evidence, the sovereignty policy, and the exact commands.
> TattvaSwarm — a personal AI you actually own. Built with NVIDIA Nemotron on
> Nebius Token Factory."

On screen: repo URL + demo URL (see `docs/SUBMISSION.md`).

## Subtitle skeleton (SRT, paste timings after recording)

```
1
00:00:00,000 --> 00:00:08,000
Personal AI today means renting someone else's servers.

2
00:00:08,000 --> 00:00:16,000
Your memories and your thinking sit in a cloud you don't control.

3
00:00:16,000 --> 00:00:24,000
TattvaSwarm is a personal AI that is sovereign by construction.

4
00:00:24,000 --> 00:00:34,000
Local-first memory, a deterministic tiered router,
and NVIDIA Nemotron models on Nebius Token Factory.

5
00:00:34,000 --> 00:00:45,000
Small answers run locally and never touch the network.
Normal, reasoning and heavy tiers route to Nemotron
Nano, Super and Ultra.

6
00:00:45,000 --> 00:01:00,000
tattva doctor — the backend is live: 28 models, 5 Nemotron.

7
00:01:00,000 --> 00:01:15,000
tattva route — everyday calls go to Nemotron Nano.

8
00:01:15,000 --> 00:01:30,000
Reasoning calls go to Nemotron Super. Every call lands
in a local usage ledger — on this machine only.

9
00:01:30,000 --> 00:01:45,000
Memory is SQLite and full-text search, stored locally.
Nothing syncs anywhere, because there is nowhere to sync to.

10
00:01:45,000 --> 00:02:20,000
One goal, three parallel workers, a verifier pass, and a
synthesis by Nemotron Ultra — under three thousand tokens.

11
00:02:20,000 --> 00:02:40,000
The same design measured 108 million logical workers in
5.8 seconds on one A100 — evidence with checksums in the repo.

12
00:02:40,000 --> 00:02:55,000
Apache-2.0. TattvaSwarm — a personal AI you actually own.
Built with NVIDIA Nemotron on Nebius Token Factory.
```

## Checklist before upload

- [ ] Duration < 3:00
- [ ] No API key, no personal paths, no internal hosts on screen
- [ ] English audio **or** EN subtitles burned/attached
- [ ] Repo URL + demo URL visible at the end
- [ ] Uploaded to YouTube as **Public** (not unlisted) — keep the link for the form
