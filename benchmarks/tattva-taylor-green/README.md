# Taylor-Green 2-D benchmark

Status: **IMPLEMENTED + measured on CPU** (2026-10-20). This is a self-contained,
reproducible benchmark for the TattvaSwarm native solver. It replaces the earlier
1-D `solve` chain, whose maximum vorticity was about `5.8e-4 s^-1`, with a real
2-D incompressible Navier-Stokes solve.

The solver integrates the vorticity-streamfunction form of the Navier-Stokes
equations on a periodic `[0, 2π) × [0, 2π)` domain:

```
∂ω/∂t + u·∇ω = ν ∇²ω          (vorticity transport)
∇²ψ = -ω                       (streamfunction Poisson equation)
u =  ∂ψ/∂y,  v = -∂ψ/∂x        (divergence-free velocity)
```

## Initial condition

```
ψ(x,y,0) = sin(x) sin(y) + ε sin(2x) sin(3y),   ε = 0.03
u =  ∂ψ/∂y
v = -∂ψ/∂x
ω =  ∂v/∂x - ∂u/∂y
```

The `ε` term is also generated from a streamfunction, so it is divergence-free.
It breaks the exact Taylor-Green symmetry and prevents the field from being a
single uniform mode. The initial maximum vorticity is about `2 s^-1`, not
`5.8e-4 s^-1`.

## Numerical scheme

1. Solve `∇²ψ = -ω` with periodic Jacobi iterations, warm-started from the
   previous step.
2. Recover `u = ∂ψ/∂y`, `v = -∂ψ/∂x` with centered differences.
3. Advect vorticity with first-order upwind differences and add explicit
   viscous diffusion.
4. Choose `dt` from the CFL and diffusion limits; keep `ω` zero-mean so the
   periodic Poisson problem is solvable.

Fields are stored as `f32` with periodic ghost cells; diagnostics are accumulated
in `f64`. The grid is the factor pair closest to a square
(`108000 = 300 × 360`; `108000000 = 10000 × 10800`). For grids larger than
1,000,000 cells, the per-cell `FluidCell` vector is not allocated; only the
field arrays are kept.

## Run

```bash
# Build the minimal benchmark harness (standard library + serde/serde_json)
cd native
cargo build --release   # add --offline if the registry cache is populated

# Human-readable
./target/release/shiva tattva-benchmark 108000 --steps 40 --re 100

# Machine-readable (used by the validation script)
./target/release/shiva tattva-benchmark 108000 --steps 40 --re 100 --json
```

A prebuilt Linux x86-64 binary is included at
`native/target/release/shiva`; rebuild it if your platform differs.

## Validation

```bash
python3 scripts/validate_tattva_benchmark.py \
  --n 108000 --steps 40 --re 100 \
  --out-dir evidence
```

The script runs the binary, captures the exact command and logs, checks the
metrics, and writes a SHA-256 manifest. Required checks:

- Apache-2.0 license present.
- Grid matches the requested cell count.
- Maximum vorticity `>= 0.1 s^-1`.
- Enstrophy and kinetic energy are positive.
- Mass residual is zero (relative tolerance).
- Divergence and Poisson residuals are bounded.
- CFL `< 1`.

Verify the bundle:

```bash
sha256sum -c evidence/MANIFEST.sha256
```

## Measured result

Local run, 2026-10-20, grid `300 × 360`, 40 steps, `Re = 100`:

| Metric | Initial | Final |
|---|---:|---:|
| Maximum vorticity (s^-1) | 2.131138 | 2.127955 |
| Enstrophy | 20.486737 | 20.433534 |
| Kinetic energy | 9.927342 | 9.921182 |
| Mass residual | — | 0 |
| Divergence residual | — | 3.297e-6 |
| Poisson residual | — | 9.614e-3 |
| CFL | — | 0.1113 |
| Vorticity retention | — | 0.998507 |

The standalone core took 12.78 s for 40 steps on the 4-core host; the integrated
release CLI took 10.72 s in the validation run (the first manual run took 24.78 s
under host load, so wall-clock is not a solver metric). The full report is in
`evidence/validation-report.md`.

Validation result: **10/10 checks PASS** (the public-repo run also passes the
`public_remote` check), plus an optional NVIDIA NIM audit with
`VERDICT=PASS`, HTTP 200, `nvidia/nemotron-3.5-lightning-30b-a3b`, 303 total
tokens. The solver itself ran on CPU.

## Cloud attestation (optional, separate from the solver)

`--cloud` sends one small audit prompt to an OpenAI-compatible endpoint and
records the HTTP status, model, token usage, latency, and a response hash. It
never prints the API key.

- The solver itself is CPU-only. The cloud call is an **LLM audit** of the
  metrics, not a GPU execution of the solver.
- This run used **NVIDIA NIM** (`https://integrate.api.nvidia.com/v1`) because
  the available `nvapi-` key and base URL point there.
- Nebius Token Factory had returned **HTTP 402** earlier; no Token Factory
  credits are claimed. See `evidence/cloud-attestation.json` for the actual
  status.
- For Nemotron 3.x the script sends `chat_template_kwargs.enable_thinking=false`
  so the audit returns a short `content` verdict instead of spending the whole
  budget on `reasoning_content`.

## Honest limits

- The solver is CPU-only; no GPU or distributed run is claimed.
- 108M cells need about 2.2 GB for the `f32` fields plus about 0.9 GB for the
  scheduler's cohort IDs (~3 GB total). The 6.7 GB host should not run that
  size; use a VM or Colab with enough RAM.
- First-order upwind is dissipative. 40 steps at `Re=100` is a non-trivial smoke
  test, not a grid-convergence study.
- The per-cell pressure in the original `FluidCell` struct is diagnostic
  (Bernoulli), not a Poisson pressure solve; the solver does not use it.

## Source provenance

The solver core is the same `fluid.rs` and `scheduler.rs` used by the full
`shiva` CLI's `tattva-benchmark` subcommand. This bundle adds a minimal,
self-contained harness (`native/src/main.rs`) so the benchmark can be rebuilt
without the CLI's network, vault and worker subsystems. The evidence was
generated from this bundle; see `evidence/validation-report.json` for the
source commit and binary SHA-256.

## License

Apache License 2.0. See [`LICENSE`](LICENSE).
