# Jayah Real MVP & Blackwell SM120 — Reproducible Case Study

Reproducible harness (`jayah_real_mvp_and_sm120_case_study.py`) and case-study
document (`CASE_STUDY_BLACKWELL_SM120.md`) for the Jayah Sentinel MVP
(Meru-Pingala + TattvaSwarm + Shiva-Wonder + x402 Evidence Passport).

Run it:

```bash
python3 jayah_real_mvp_and_sm120_case_study.py --export-json jayah_real_mvp_evidence.json
```

## Independent reproduction (Mica, 2026-11-17, CPU-only VM)

Environment: Python 3.12.3, numpy 1.26.4, no torch/triton/GPU
(`nvidia-smi` unavailable — CPU FP64/FP32 verification only).
Evidence: `jayah_real_mvp_evidence.mica-repro.json`,
passport `sha256:4cbc7ee7ee5ea2edd3962fa7e41b76c8082625f313900ea17ba579cfd0a72642`.

- Workload 1 (2,073,600 cells, 20x240x432): 1D norm max abs err **8.811e-08**,
  3D norm max abs err **8.811e-08**; 3D timing 147.59 ± 15.50 ms (5 runs,
  this VM — hardware-dependent).
- Workload 2 (OstiumVault, Arbitrum): stale $0.916 vs true $1.036 USDC/share,
  +63,226.05 excess oUSDC on a $500,000 deposit, $59,055.12 LP dilution
  (+11.81%), accounting residual 0.000e+00. Arithmetic reproduces exactly.

## Notes on scope (read before citing)

- The GPU tables in the case study (0.8597 ms 1D, 1.385 ms 3D Z-tiled,
  torch.compile baselines) are documented SM120 measurements from the paper,
  NOT measured by this script. The script measures CPU FP64/FP32 on the
  2.07M-cell validation grid and packages the documented tables.
- The script's measured errors (8.81e-08 for both 1D and 3D) differ slightly
  from the paper's 9.51e-08 / 2.13e-07. All are ~1e-07, at FP32 rounding
  scale; the exact mantissa varies with grid and initial conditions.
- The Ostium simulation is closed-form arithmetic on assumed vault state
  ($5M TVL, stale PnL +$420k, true PnL -$180k). It verifies the stale-price
  mechanism exactly, but it performs no live RPC reads. Live on-chain
  verification of a tx is the `/trace/tx` x402 endpoint.
- Mean Richardson number in this configuration is ~4578, dominated by
  near-zero-shear cells, so the buoyancy damping f_B(Ri) is ~0 in most cells
  and the Smagorinsky term is barely exercised. Median Ri is the better
  diagnostic for the physics check.
