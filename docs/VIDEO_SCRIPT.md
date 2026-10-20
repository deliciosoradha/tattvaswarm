# Video script — TattvaSwarm (final render, 2:03)

> **Final render:** 2026-10-19 · 1280×720 · 25 fps · **123.0 s** · H.264/yuv420p ·
> silent screen recording with **burned English captions**.
>
> **Files (workspace, not committed to the repo):**
> - `devpost-assets/tattvaswarm-demo.mp4` — 5,633,420 bytes,
>   SHA-256 `b8e4f035f940de95628a048fc98401778a19fa4e8cea60ace281fcd54d03d8a9`
> - `devpost-assets/tattvaswarm-demo.srt` / `.vtt` — complete English captions
> - `devpost-assets/tattvaswarm-thumbnail-1200x800.png` — Devpost 3:2 thumbnail
> - `title-card.png` (1280×720) — YouTube thumbnail candidate
>
> **Backend note (honesty):** the recording runs against **NVIDIA NIM**
> (`https://integrate.api.nvidia.com/v1`) with
> `nvidia/nemotron-3.5-lightning-30b-a3b` (normal) and
> `nvidia/nemotron-3-super-120b-a12b` (reasoning/heavy). The Nebius Token Factory
> project returned **HTTP 402** at recording time. The client is OpenAI-compatible:
> the same CLI runs on Token Factory with
> `NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1/` and a valid key.
> Earlier Token Factory runs and model IDs are in [`EVIDENCE.md`](EVIDENCE.md).
>
> **Recording hygiene:** isolated Xvfb display 1280×720, tmux pane 100×30, minimal
> `$` prompt, no `.env` contents, no hostname/status bar, no personal paths.

## Final timeline

| Time | Shot | On screen |
|---|---|---|
| 0:00–0:07 | Title card | TattvaSwarm — a sovereign personal AI swarm · “live demo · every outbound call is in a local ledger” |
| 0:07–0:21 | Doctor + memory | `tattva doctor` → NVIDIA NIM base URL, three tiers, 81 models (33 Nemotron); `tattva memory add` → `#1`; `tattva memory search "local-first"` → `#1` |
| 0:21–0:26 | Engine card | 108,000,000 logical workers · 5.8007 s on one A100-40GB · state machines, not processes · measured in `docs/EVIDENCE.md` |
| 0:26–1:56 | Ledger → swarm | `ledger` (Lightning + Super calls) → `python3 demos/demo_swarm_research.py` → t1/t2/t3 → all **VERIFIED** → synthesis → `ledger` (6 calls) |
| 1:56–2:03 | Closing card | Local-first. Tiered. Verifiable. · github.com/deliciosoradha/tattvaswarm · Apache-2.0 |

The two route calls shown in the first ledger were recorded before the take:
normal tier → `nvidia/nemotron-3.5-lightning-30b-a3b` (632 tokens, 6.054 s);
forced reasoning tier → `nvidia/nemotron-3-super-120b-a12b` (177 tokens, 5.2 s).
They are the same code path as the CLI quickstart.

## Commands in the final cut

```bash
tattva doctor
tattva memory add "The user prefers local-first tools and open models."
tattva memory search "local-first"
ledger
python3 demos/demo_swarm_research.py
ledger
```

The swarm run uses `demos/tasks_research.example.json`:

- **t1** — normal tier, two sentences on why local-first personal AI matters.
- **t2** — reasoning tier, exactly three concrete trade-offs (costs or downsides).
- **t3** — normal tier, logical worker swarms and why they scale.
- Verifier — one pass per worker; all three returned **VERIFIED**.
- Synthesis — heavy tier (`nvidia/nemotron-3-super-120b-a12b`), with a note that
  the t3 result is not directly relevant to the local-first goal.

## Narration / subtitles (complete SRT)

The MP4 carries burned captions over the terminal section; the SRT/VTT are the
canonical complete captions for YouTube.

```srt
1
00:00:07,000 --> 00:00:11,500
Personal AI today usually means renting someone else's servers.

2
00:00:11,500 --> 00:00:15,500
TattvaSwarm is sovereign by construction.

3
00:00:15,500 --> 00:00:21,000
Local memory. Deterministic routing. Only the calls you allow leave.

4
00:00:21,000 --> 00:00:26,000
The engine scales to 108 million logical workers on one A100 — measured.

5
00:00:26,000 --> 00:00:31,000
The ledger shows a normal call on Lightning and a reasoning call on Super.

6
00:00:31,000 --> 00:00:38,000
Three workers answer in parallel: two normal, one reasoning.

7
00:00:38,000 --> 00:00:46,000
The verifier checks each answer for fabrication.

8
00:00:46,000 --> 00:00:54,000
All three come back VERIFIED.

9
00:00:54,000 --> 00:01:04,000
The synthesizer merges them into one answer.

10
00:01:04,000 --> 00:01:16,000
It calls out what doesn't fit instead of inventing missing content.

11
00:01:16,000 --> 00:01:28,000
Every model call is written to the local usage ledger.

12
00:01:28,000 --> 00:01:38,000
Models, tokens, and real latency — all on the user's machine.

13
00:01:38,000 --> 00:01:46,000
No hidden cloud memory. No fabricated answers.

14
00:01:46,000 --> 00:01:52,000
Every model call is accounted for in the local ledger.

15
00:01:52,000 --> 00:01:56,000
Local-first. Tiered. Verifiable.
```

## Upload checklist

- [ ] Duration **2:03** (< 3:00); 1280×720; H.264/yuv420p.
- [ ] No API key, no `.env` contents, no hostname/status bar, no personal paths.
- [ ] English captions: burned in the MP4; upload the SRT/VTT as English captions on YouTube.
- [ ] YouTube visibility **Public** (the rules require a public video).
- [ ] Thumbnail: `title-card.png` (1280×720).
- [ ] Paste the YouTube URL into the Devpost **Video** field, replacing
      `https://youtu.be/Jm4v_h4DW7o`.
- [ ] Demo URL: this build has **no hosted interactive demo** (no cloud spend).
      Use the public repo `https://github.com/deliciosoradha/tattvaswarm` and the
      quickstart, or the YouTube URL if the form accepts the video. Do not claim a
      live hosted endpoint.

### YouTube metadata suggestion

**Title:** `TattvaSwarm — a sovereign personal AI swarm (2:03 demo)`

**Description:**

```text
TattvaSwarm is a local-first personal AI: a deterministic tiered router, SQLite/FTS5
memory that stays on the machine, a parallel → verify → synthesize conductor, and a
logical swarm engine measured at 108,000,000 workers in 5.8007 s on one A100-40GB.

The demo runs the same CLI against NVIDIA NIM with Nemotron 3.5 Lightning and
Nemotron 3 Super. The client is OpenAI-compatible; the Token Factory evidence is in
the repo.

Repo (Apache-2.0): https://github.com/deliciosoradha/tattvaswarm
Quickstart: pip install -e . && tattva doctor

Chapters:
0:00 Intro
0:07 Doctor + local memory
0:21 108M logical-worker engine
0:26 Three workers → verifier → synthesis + local ledger
1:56 Close

Built for the Nebius × NVIDIA Global AI Hackathon 2026. Silent screen recording;
English captions are burned in and supplied as SRT/VTT.
```

**Tags:** `TattvaSwarm`, `NVIDIA Nemotron`, `Nebius`, `local-first AI`, `AI agents`, `hackathon`

## Production notes

- The final terminal take was recorded on an isolated Xvfb display to avoid capturing
  the desktop, and on a 100×30 tmux pane so the ledger fits in 720p.
- The local mass-swarm benchmark was cut from the final video because a 1M run takes
  ~39 s; the measured 108M/5.8 s A100 result is shown as a card with its source.
- The route-command outputs were cut from the final video; the first ledger still
  shows both a Lightning and a Super call with their real latencies.
