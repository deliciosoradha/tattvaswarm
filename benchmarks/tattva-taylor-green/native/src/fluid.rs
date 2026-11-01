//! 2-D incompressible Navier-Stokes benchmark: Taylor-Green vortex.
//!
//! This replaces the old 1-D chain with a real 2-D vorticity-streamfunction
//! solve on a periodic `[0, 2π) × [0, 2π)` domain:
//!
//!   1. Start from the Taylor-Green vortex
//!        ψ(x,y,0) = sin(x) sin(y) + ε sin(2x) sin(3y)
//!        u =  ∂ψ/∂y,   v = -∂ψ/∂x
//!        ω =  ∂v/∂x - ∂u/∂y
//!      The small ε term breaks the exact 4-fold symmetry, so the field is
//!      not a single uniform mode and cannot collapse to a zero-vorticity
//!      "trivial solve".
//!   2. Solve the streamfunction Poisson equation ∇²ψ = -ω with Jacobi
//!      iterations (warm-started from the previous step).
//!   3. Recover u,v from ψ and advance the vorticity transport equation
//!        ∂ω/∂t + u·∇ω = ν∇²ω
//!      with first-order upwind advection and explicit diffusion.
//!
//! The implementation is intentionally dependency-free (std only) and uses
//! `f32` field storage so the 108M-cell Colab run stays within RAM.  Scalars
//! and evidence metrics are accumulated in `f64`.
//!
//! Honesty note: this is a CPU solver.  It does not claim to run on Nebius
//! GPUs.  The validation script can separately attest an LLM call on NVIDIA
//! NIM / Nebius Token Factory; that attestation is labelled separately.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FluidCell {
    pub id: usize,
    pub density: f64,
    pub pressure: f64,
    pub velocity_x: f64,
    pub velocity_y: f64,
    pub vorticity: f64,
    pub inflow: f64,
    pub outflow: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FluidState {
    pub step: usize,
    pub total_mass: f64,
    pub mass_residual: f64,
    pub kinetic_energy: f64,
    pub enstrophy: f64,
    pub max_vorticity: f64,
    pub max_velocity: f64,
    pub divergence_residual: f64,
    pub poisson_residual: f64,
    pub cells_solved: usize,
    pub grid_nx: usize,
    pub grid_ny: usize,
    pub dx: f64,
    pub dy: f64,
    pub dt: f64,
    pub time: f64,
    pub reynolds: f64,
    pub cfl: f64,
    pub initial_max_vorticity: f64,
    pub initial_enstrophy: f64,
    pub initial_kinetic_energy: f64,
    pub vorticity_retention: f64,
}

pub struct FluidSolver {
    pub viscosity: f64,
    pub dt_max: f64,
    pub dx: f64,
    pub dy: f64,
    pub nx: usize,
    pub ny: usize,
    /// Small grids keep a per-cell view for backwards compatibility.  Large
    /// grids leave this empty to avoid a 64-byte-per-cell allocation.
    pub cells: Vec<FluidCell>,

    px: usize,
    omega: Vec<f32>,
    psi: Vec<f32>,
    psi_tmp: Vec<f32>,
    u: Vec<f32>,
    v: Vec<f32>,
    omega_next: Vec<f32>,

    step_count: usize,
    time: f64,
    last_dt: f64,
    initial_mass: f64,
    initial_ke: f64,
    initial_enstrophy: f64,
    initial_max_vort: f64,
    poisson_iters: usize,
}

impl FluidSolver {
    /// Build a Taylor-Green solve.  `cell_count` is factored into the closest
    /// square-ish grid; the domain is always `[0, 2π)²`.
    ///
    /// `viscosity` is ν; the Reynolds number reported is `U0·L/ν` with
    /// U0 = L = 1.  `dt` is an upper bound on the adaptive time step.
    /// `_dx_hint` is accepted for source compatibility with the old API and
    /// ignored: dx/dy are derived from the grid and the 2π domain.
    pub fn new(cell_count: usize, viscosity: f64, dt: f64, _dx_hint: f64) -> Self {
        let n = cell_count.max(1);
        let (nx, ny) = grid_dims(n);
        let px = nx + 2;
        let len = px * (ny + 2);
        let cells = if nx * ny <= 1_000_000 {
            vec![
                FluidCell {
                    id: 0,
                    density: 1.0,
                    pressure: 101_325.0,
                    velocity_x: 0.0,
                    velocity_y: 0.0,
                    vorticity: 0.0,
                    inflow: 0.0,
                    outflow: 0.0,
                };
                nx * ny
            ]
        } else {
            Vec::new()
        };

        let poisson_iters = if n <= 200_000 {
            60
        } else if n <= 2_000_000 {
            30
        } else if n <= 20_000_000 {
            15
        } else {
            6
        };

        let mut solver = Self {
            viscosity: viscosity.max(0.0),
            dt_max: if dt > 0.0 { dt } else { 1.0e-3 },
            dx: 2.0 * std::f64::consts::PI / nx as f64,
            dy: 2.0 * std::f64::consts::PI / ny as f64,
            nx,
            ny,
            cells,
            px,
            omega: vec![0.0; len],
            psi: vec![0.0; len],
            psi_tmp: vec![0.0; len],
            u: vec![0.0; len],
            v: vec![0.0; len],
            omega_next: vec![0.0; len],
            step_count: 0,
            time: 0.0,
            last_dt: if dt > 0.0 { dt } else { 1.0e-3 },
            initial_mass: 0.0,
            initial_ke: 0.0,
            initial_enstrophy: 0.0,
            initial_max_vort: 0.0,
            poisson_iters,
        };
        solver.initialize_taylor_green();
        solver
    }

    /// Advance `steps` time steps and return a consistent final state.
    pub fn run(&mut self, steps: usize) -> FluidState {
        for _ in 0..steps {
            self.advance();
        }
        self.refresh_fields();
        self.sync_cells();
        self.metrics()
    }

    /// One public step, with a final streamfunction/velocity refresh.
    pub fn step(&mut self) -> FluidState {
        self.advance();
        self.refresh_fields();
        self.sync_cells();
        self.metrics()
    }

    /// Non-destructive diagnostics for the current field.
    pub fn metrics(&self) -> FluidState {
        let nx = self.nx;
        let ny = self.ny;
        let px = self.px;
        let inv_2dx = 0.5 / self.dx;
        let inv_2dy = 0.5 / self.dy;
        let inv_dx2 = 1.0 / (self.dx * self.dx);
        let inv_dy2 = 1.0 / (self.dy * self.dy);
        let cell_area = self.dx * self.dy;

        let mut kinetic_energy = 0.0;
        let mut enstrophy = 0.0;
        let mut max_vorticity = 0.0_f64;
        let mut max_velocity = 0.0_f64;
        let mut divergence_residual = 0.0_f64;
        let mut poisson_residual = 0.0_f64;

        for j in 1..=ny {
            let row = j * px;
            for i in 1..=nx {
                let idx = row + i;
                let om = self.omega[idx] as f64;
                let uu = self.u[idx] as f64;
                let vv = self.v[idx] as f64;
                let speed2 = uu * uu + vv * vv;

                kinetic_energy += 0.5 * speed2 * cell_area;
                enstrophy += 0.5 * om * om * cell_area;
                max_vorticity = max_vorticity.max(om.abs());
                max_velocity = max_velocity.max(speed2.sqrt());

                let du_dx = (self.u[idx + 1] as f64 - self.u[idx - 1] as f64) * inv_2dx;
                let dv_dy = (self.v[idx + px] as f64 - self.v[idx - px] as f64) * inv_2dy;
                divergence_residual = divergence_residual.max((du_dx + dv_dy).abs());

                let lap_psi = (self.psi[idx + 1] as f64
                    - 2.0 * self.psi[idx] as f64
                    + self.psi[idx - 1] as f64)
                    * inv_dx2
                    + (self.psi[idx + px] as f64
                        - 2.0 * self.psi[idx] as f64
                        + self.psi[idx - px] as f64)
                        * inv_dy2;
                poisson_residual = poisson_residual.max((lap_psi + om).abs());
            }
        }

        let total_mass = (nx * ny) as f64;
        let mass_residual = if self.initial_mass > 0.0 {
            ((total_mass - self.initial_mass) / self.initial_mass).abs()
        } else {
            0.0
        };
        let reynolds = if self.viscosity > 0.0 {
            1.0 / self.viscosity
        } else {
            0.0
        };
        let cfl = self.last_dt * max_velocity * (1.0 / self.dx + 1.0 / self.dy);
        let vorticity_retention = if self.initial_max_vort > 0.0 {
            max_vorticity / self.initial_max_vort
        } else {
            0.0
        };

        FluidState {
            step: self.step_count,
            total_mass,
            mass_residual,
            kinetic_energy,
            enstrophy,
            max_vorticity,
            max_velocity,
            divergence_residual,
            poisson_residual,
            cells_solved: nx * ny,
            grid_nx: nx,
            grid_ny: ny,
            dx: self.dx,
            dy: self.dy,
            dt: self.last_dt,
            time: self.time,
            reynolds,
            cfl,
            initial_max_vorticity: self.initial_max_vort,
            initial_enstrophy: self.initial_enstrophy,
            initial_kinetic_energy: self.initial_ke,
            vorticity_retention,
        }
    }

    fn initialize_taylor_green(&mut self) {
        // ε perturbation: divergence-free because it is also generated from a
        // streamfunction.  It breaks the exact Taylor-Green symmetry.
        let eps = 0.03_f64;
        let nx = self.nx;
        let ny = self.ny;
        let px = self.px;
        for j in 1..=ny {
            let y = 2.0 * std::f64::consts::PI * j as f64 / ny as f64;
            let row = j * px;
            for i in 1..=nx {
                let x = 2.0 * std::f64::consts::PI * i as f64 / nx as f64;
                let psi = x.sin() * y.sin() + eps * (2.0 * x).sin() * (3.0 * y).sin();
                let u = x.sin() * y.cos()
                    + eps * 3.0 * (2.0 * x).sin() * (3.0 * y).cos();
                let v = -x.cos() * y.sin()
                    - eps * 2.0 * (2.0 * x).cos() * (3.0 * y).sin();
                let idx = row + i;
                self.psi[idx] = psi as f32;
                self.u[idx] = u as f32;
                self.v[idx] = v as f32;
            }
        }
        fill_ghosts(&mut self.psi, nx, ny);
        fill_ghosts(&mut self.u, nx, ny);
        fill_ghosts(&mut self.v, nx, ny);

        for j in 1..=ny {
            let row = j * px;
            for i in 1..=nx {
                let idx = row + i;
                let dv_dx = (self.v[idx + 1] as f64 - self.v[idx - 1] as f64)
                    * 0.5
                    / self.dx;
                let du_dy = (self.u[idx + px] as f64 - self.u[idx - px] as f64)
                    * 0.5
                    / self.dy;
                self.omega[idx] = (dv_dx - du_dy) as f32;
            }
        }
        fill_ghosts(&mut self.omega, nx, ny);
        self.remove_mean_omega();

        self.initial_mass = (nx * ny) as f64;
        self.initial_ke = self.kinetic_energy();
        self.initial_enstrophy = self.enstrophy();
        self.initial_max_vort = self.max_abs_omega();
        self.sync_cells();
    }

    fn advance(&mut self) {
        if self.nx == 0 || self.ny == 0 {
            return;
        }
        let dt = self.compute_dt();
        self.last_dt = dt;

        self.solve_psi(self.poisson_iters);
        self.velocity_from_psi();
        fill_ghosts(&mut self.omega, self.nx, self.ny);
        fill_ghosts(&mut self.u, self.nx, self.ny);
        fill_ghosts(&mut self.v, self.nx, self.ny);

        let nx = self.nx;
        let ny = self.ny;
        let px = self.px;
        let inv_dx = 1.0_f32 / self.dx as f32;
        let inv_dy = 1.0_f32 / self.dy as f32;
        let inv_dx2 = inv_dx * inv_dx;
        let inv_dy2 = inv_dy * inv_dy;
        let dtf = dt as f32;
        let visc = self.viscosity as f32;

        {
            let omega = &self.omega;
            let u = &self.u;
            let v = &self.v;
            let omega_next = &mut self.omega_next;
            for j in 1..=ny {
                let row = j * px;
                for i in 1..=nx {
                    let idx = row + i;
                    let uu = u[idx];
                    let vv = v[idx];

                    // First-order upwind advection: stable at the CFL values
                    // used here and monotone for the sharp vortex core.
                    let domega_dx = if uu >= 0.0 {
                        (omega[idx] - omega[idx - 1]) * inv_dx
                    } else {
                        (omega[idx + 1] - omega[idx]) * inv_dx
                    };
                    let domega_dy = if vv >= 0.0 {
                        (omega[idx] - omega[idx - px]) * inv_dy
                    } else {
                        (omega[idx + px] - omega[idx]) * inv_dy
                    };
                    let laplacian = (omega[idx + 1] - 2.0 * omega[idx] + omega[idx - 1])
                        * inv_dx2
                        + (omega[idx + px] - 2.0 * omega[idx] + omega[idx - px]) * inv_dy2;

                    omega_next[idx] = omega[idx]
                        + dtf * (-uu * domega_dx - vv * domega_dy + visc * laplacian);
                }
            }
            fill_ghosts(omega_next, nx, ny);
        }

        std::mem::swap(&mut self.omega, &mut self.omega_next);
        self.remove_mean_omega();
        self.step_count += 1;
        self.time += dt;
    }

    fn refresh_fields(&mut self) {
        self.solve_psi(self.poisson_iters);
        self.velocity_from_psi();
        fill_ghosts(&mut self.omega, self.nx, self.ny);
        fill_ghosts(&mut self.u, self.nx, self.ny);
        fill_ghosts(&mut self.v, self.nx, self.ny);
    }

    fn solve_psi(&mut self, iters: usize) {
        if iters == 0 {
            return;
        }
        let nx = self.nx;
        let ny = self.ny;
        let px = self.px;
        let inv_dx2 = 1.0 / (self.dx * self.dx);
        let inv_dy2 = 1.0 / (self.dy * self.dy);
        let denom = 2.0 * (inv_dx2 + inv_dy2);

        {
            let omega = &self.omega;
            let psi = &mut self.psi;
            let psi_tmp = &mut self.psi_tmp;
            for _ in 0..iters {
                for j in 1..=ny {
                    let row = j * px;
                    for i in 1..=nx {
                        let idx = row + i;
                        let east = psi[idx + 1] as f64;
                        let west = psi[idx - 1] as f64;
                        let north = psi[idx + px] as f64;
                        let south = psi[idx - px] as f64;
                        let rhs = omega[idx] as f64;
                        let value =
                            ((east + west) * inv_dx2 + (north + south) * inv_dy2 + rhs) / denom;
                        psi_tmp[idx] = value as f32;
                    }
                }
                fill_ghosts(psi_tmp, nx, ny);
                std::mem::swap(psi, psi_tmp);
            }
        }
    }

    fn velocity_from_psi(&mut self) {
        let nx = self.nx;
        let ny = self.ny;
        let px = self.px;
        let inv_2dx = 0.5 / self.dx;
        let inv_2dy = 0.5 / self.dy;
        {
            let psi = &self.psi;
            let u = &mut self.u;
            let v = &mut self.v;
            for j in 1..=ny {
                let row = j * px;
                for i in 1..=nx {
                    let idx = row + i;
                    u[idx] = (((psi[idx + px] as f64) - (psi[idx - px] as f64)) * inv_2dy)
                        as f32;
                    v[idx] = -(((psi[idx + 1] as f64) - (psi[idx - 1] as f64)) * inv_2dx)
                        as f32;
                }
            }
        }
        fill_ghosts(&mut self.u, nx, ny);
        fill_ghosts(&mut self.v, nx, ny);
    }

    fn compute_dt(&self) -> f64 {
        let max_vel = self.max_velocity().max(1.0e-9);
        let min_dx = self.dx.min(self.dy);
        let advective = 0.25 * min_dx / max_vel;
        let diffusive = if self.viscosity > 0.0 {
            let inv_dx2 = 1.0 / (self.dx * self.dx);
            let inv_dy2 = 1.0 / (self.dy * self.dy);
            0.2 / (self.viscosity * (inv_dx2 + inv_dy2))
        } else {
            f64::INFINITY
        };
        self.dt_max.min(advective).min(diffusive)
    }

    fn remove_mean_omega(&mut self) {
        let nx = self.nx;
        let ny = self.ny;
        let px = self.px;
        let n = (nx * ny) as f64;
        let mut sum = 0.0;
        for j in 1..=ny {
            let row = j * px;
            for i in 1..=nx {
                sum += self.omega[row + i] as f64;
            }
        }
        let mean = (sum / n) as f32;
        for j in 1..=ny {
            let row = j * px;
            for i in 1..=nx {
                self.omega[row + i] -= mean;
            }
        }
        fill_ghosts(&mut self.omega, nx, ny);
    }

    fn kinetic_energy(&self) -> f64 {
        let cell_area = self.dx * self.dy;
        let mut value = 0.0;
        for j in 1..=self.ny {
            let row = j * self.px;
            for i in 1..=self.nx {
                let idx = row + i;
                let uu = self.u[idx] as f64;
                let vv = self.v[idx] as f64;
                value += 0.5 * (uu * uu + vv * vv) * cell_area;
            }
        }
        value
    }

    fn enstrophy(&self) -> f64 {
        let cell_area = self.dx * self.dy;
        let mut value = 0.0;
        for j in 1..=self.ny {
            let row = j * self.px;
            for i in 1..=self.nx {
                let om = self.omega[row + i] as f64;
                value += 0.5 * om * om * cell_area;
            }
        }
        value
    }

    fn max_abs_omega(&self) -> f64 {
        let mut value = 0.0_f64;
        for j in 1..=self.ny {
            let row = j * self.px;
            for i in 1..=self.nx {
                value = value.max((self.omega[row + i] as f64).abs());
            }
        }
        value
    }

    fn max_velocity(&self) -> f64 {
        let mut value = 0.0_f64;
        for j in 1..=self.ny {
            let row = j * self.px;
            for i in 1..=self.nx {
                let idx = row + i;
                let uu = self.u[idx] as f64;
                let vv = self.v[idx] as f64;
                value = value.max((uu * uu + vv * vv).sqrt());
            }
        }
        value
    }

    fn sync_cells(&mut self) {
        if self.cells.is_empty() {
            return;
        }
        let nx = self.nx;
        let px = self.px;
        let u = &self.u;
        let v = &self.v;
        let omega = &self.omega;
        for (id, cell) in self.cells.iter_mut().enumerate() {
            let i = id % nx + 1;
            let j = id / nx + 1;
            let idx = i + px * j;
            let uu = u[idx] as f64;
            let vv = v[idx] as f64;
            cell.id = id;
            cell.density = 1.0;
            // Diagnostic Bernoulli surface pressure; not a solved Poisson
            // pressure field.  It is never used by the solver.
            cell.pressure = 101_325.0 - 0.5 * (uu * uu + vv * vv);
            cell.velocity_x = uu;
            cell.velocity_y = vv;
            cell.vorticity = omega[idx] as f64;
            cell.inflow = 0.0;
            cell.outflow = 0.0;
        }
    }
}

/// Factor `n` into the divisor pair closest to a square.  Exact factors keep
/// `cells_solved == n`; prime counts become a 1×n chain.
fn grid_dims(n: usize) -> (usize, usize) {
    let n = n.max(1);
    let mut best = (1, n);
    let mut best_ratio = f64::INFINITY;
    let mut d = 1;
    while d * d <= n {
        if n % d == 0 {
            let e = n / d;
            let ratio = e as f64 / d as f64;
            if ratio < best_ratio {
                best_ratio = ratio;
                best = (d, e);
            }
        }
        d += 1;
    }
    best
}

/// Periodic ghost-cell fill for a padded `(nx+2) × (ny+2)` array.
#[inline]
fn fill_ghosts(field: &mut [f32], nx: usize, ny: usize) {
    let px = nx + 2;
    for j in 1..=ny {
        let row = j * px;
        field[row] = field[row + nx];
        field[row + nx + 1] = field[row + 1];
    }
    let last = ny * px;
    for i in 1..=nx {
        field[i] = field[last + i];
        field[(ny + 1) * px + i] = field[px + i];
    }
    field[0] = field[last + nx];
    field[nx + 1] = field[last + 1];
    field[(ny + 1) * px] = field[px + nx];
    field[(ny + 1) * px + nx + 1] = field[px + 1];
}
