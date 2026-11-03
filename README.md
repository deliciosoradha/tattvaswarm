## 🏆 Meta Global AI Developer Hackathon (Oct 27 – Nov 4, 2026) — Submission Manifest

### Track & Problem Statement
* **Primary Problem Statement:** Push the Frontier (Accelerating Scientific Experiments & Physical System Control with Verifiable Multi-Agent Orchestration).
* **Bonus Prize Nominations:**
  1. **Best Build on Meta Open Weight Models:** Powered by `meta-models/muse-spark-open-1026` and `Muse Glimmer`.
  2. **Best Agentic Use-Case:** Deterministic *Shiva Router* coordinating multi-step PDE verification and invariant checking.
  3. **Most Viral Project:** 3-min demo video published on X + YouTube/Loom.

### Clear Identification of New Hackathon Work vs. Pre-Existing Baseline
In strict compliance with Section 4 (*Hackathon Rules — New work only*), we explicitly delineate the work built during the Hackathon building period (Oct 27 – Nov 4, 2026) from our pre-existing open-source physics kernels:

| Component / Directory | Status | Description |
| :--- | :--- | :--- |
| `meta_hackathon_2026/shiva_muse_router.py` | **NEW (Built Oct 27 – Nov 4)** | Deterministic Meru-Piṅgala router integrating `Muse Spark`, `meta-models/muse-spark-open-1026`, `Muse Glimmer`, `SAM 3.1`, `Muse Wonder`, and `Muse Voice Transcribe` with a strict $100/$50 credit guardrail. |
| `meta_hackathon_2026/sam31_physics_injector.py` | **NEW (Built Oct 27 – Nov 4)** | Pipeline converting `SAM 3.1` segmentation masks of atmospheric vortices and thermal shields into boundary tensors for Triton GPU kernels. |
| `meta_hackathon_2026/verifiable_agent_harness.py` | **NEW (Built Oct 27 – Nov 4)** | Cryptographic invariant verifier implementing *Agents 102* verifiable reasoning certificates over `meta-models/muse-spark-open-1026`. |
| `meta_hackathon_2026/paper_shiva_muse_verification.tex` | **NEW (Built Oct 27 – Nov 4)** | Formal verification paper benchmarking Meta Muse open-weight and frontier models coupled with GPU physics engines. |
| `benchmarks/` & Core Triton Kernels | **PRE-EXISTING BASELINE** | Foundational matrix-free Triton kernels on NVIDIA Blackwell SM120 (44.01× Earth-2 speedup, 100B node $Q_{36}$ engine). |

### Budget Guardrail ($100 Active / $50 Reserve)
* Set **Spend Limit = $100.00** in Meta Model API Billing.
* Distribution: $45 Spark (reasoning) / $30 SAM 3.1 / $15 Wonder-Image / $10 Voice / $0 swarm overflow to Baseten + Modal.
* Every dispatch appends to `logs/meta_credit_ledger.json` (`cumulative_spend_usd <= 100.00`).

### Quickstart
```bash
python3 meta_hackathon_2026/shiva_muse_router.py
python3 meta_hackathon_2026/sam31_physics_injector.py
python3 meta_hackathon_2026/verifiable_agent_harness.py
# Paper:
tectonic meta_hackathon_2026/paper_shiva_muse_verification.tex
```

### Env Vars
`META_API_KEY`, `BASETEN_API_KEY`, `META_MODEL_API_URL`, `BASETEN_API_URL`.

---
*Tattva Swarm × Shiva Router — Push the Frontier submission. Pre-existing Triton kernels are baseline only; all files under `meta_hackathon_2026/` are new hackathon work.*
