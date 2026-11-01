//! Minimal, reproducible harness for the Tattva Taylor-Green benchmark.
//! It uses the same `fluid.rs` and `scheduler.rs` as the full shiva CLI,
//! without the network/vault/worker subsystems that the benchmark doesn't need.

mod fluid;
mod scheduler;

use std::fmt::Write as _;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.get(1).map(String::as_str) != Some("tattva-benchmark") {
        eprintln!("usage: shiva tattva-benchmark [N] [--steps S] [--re RE] [--json]");
        std::process::exit(2);
    }

    let mut n: usize = 108_000;
    let mut steps: Option<usize> = None;
    let mut reynolds: f64 = 100.0;
    let mut json = false;
    let mut i = 2;
    while i < args.len() {
        match args[i].as_str() {
            "--json" => json = true,
            "--steps" => {
                i += 1;
                if let Some(v) = args.get(i).and_then(|s| s.parse().ok()) {
                    steps = Some(v);
                }
            }
            "--re" => {
                i += 1;
                if let Some(v) = args.get(i).and_then(|s| s.parse().ok()) {
                    if v > 0.0 {
                        reynolds = v;
                    }
                }
            }
            other => {
                if let Ok(v) = other.parse() {
                    n = v;
                }
            }
        }
        i += 1;
    }
    let steps = steps.unwrap_or(if n > 20_000_000 { 1 } else { 100 });

    let mut human = String::new();
    writeln!(human, "============================================================").unwrap();
    writeln!(human, "  TATTVA-SWARM: Taylor-Green Navier-Stokes & Pingala Wave   ").unwrap();
    writeln!(human, "============================================================").unwrap();
    writeln!(human, "[*] Initializing Meru-Pingala Scheduler for {} agents...", n).unwrap();
    let scheduler = scheduler::PingalaScheduler::new(18, n);
    let plan = scheduler.build_schedule();
    writeln!(
        human,
        "[+] Schedule plan generated: {} cohorts, max cohort size: {}",
        plan.num_cohorts, plan.max_cohort_size
    )
    .unwrap();

    writeln!(
        human,
        "[*] Initializing Taylor-Green vortex solver (Re={:.1})...",
        reynolds
    )
    .unwrap();
    let mut solver = fluid::FluidSolver::new(n, 1.0 / reynolds, 1.0e-3, 0.0);
    let initial = solver.metrics();
    writeln!(
        human,
        "[*] Grid: {} x {} = {} cells; {} step(s)",
        initial.grid_nx, initial.grid_ny, initial.cells_solved, steps
    )
    .unwrap();

    writeln!(human, "[*] Executing time-dependent vortex simulation...").unwrap();
    let start = std::time::Instant::now();
    let wave_metrics = scheduler.execute_wave(&plan);
    let fluid_state = solver.run(steps);
    let elapsed = start.elapsed();
    let solves_per_sec =
        (fluid_state.cells_solved as f64 * steps as f64) / elapsed.as_secs_f64().max(1.0e-12);

    writeln!(human, "\n=== SIMULATION RESULTS ===").unwrap();
    writeln!(human, "Execution Time:          {:.4} s", elapsed.as_secs_f64()).unwrap();
    writeln!(human, "Agents Dispatched:       {}", wave_metrics.agents_dispatched).unwrap();
    writeln!(human, "Cohorts Executed:        {}", wave_metrics.waves_executed).unwrap();
    writeln!(human, "Schedule Conflicts:      {}", wave_metrics.conflicts_detected).unwrap();
    writeln!(human, "Grid:                    {} x {}", fluid_state.grid_nx, fluid_state.grid_ny).unwrap();
    writeln!(human, "Reynolds Number:         {:.1}", fluid_state.reynolds).unwrap();
    writeln!(human, "Time Step:               {:.6e} s", fluid_state.dt).unwrap();
    writeln!(human, "Simulation Time:         {:.6e} s", fluid_state.time).unwrap();
    writeln!(human, "CFL:                     {:.4}", fluid_state.cfl).unwrap();
    writeln!(human, "Total Conserved Mass:    {:.6}", fluid_state.total_mass).unwrap();
    writeln!(human, "Mass Residual ||dW/dt||: {:e}", fluid_state.mass_residual).unwrap();
    writeln!(human, "Initial Kinetic Energy:  {:.6}", initial.kinetic_energy).unwrap();
    writeln!(human, "Kinetic Energy:          {:.6}", fluid_state.kinetic_energy).unwrap();
    writeln!(human, "Initial Enstrophy:       {:.6}", initial.enstrophy).unwrap();
    writeln!(human, "Enstrophy:               {:.6}", fluid_state.enstrophy).unwrap();
    writeln!(human, "Initial Max Vorticity:   {:.6} s^-1", initial.max_vorticity).unwrap();
    writeln!(human, "Max Vorticity:           {:.6} s^-1", fluid_state.max_vorticity).unwrap();
    writeln!(human, "Vorticity Retention:     {:.6}", fluid_state.vorticity_retention).unwrap();
    writeln!(human, "Divergence Residual:     {:.6e}", fluid_state.divergence_residual).unwrap();
    writeln!(human, "Poisson Residual:        {:.6e}", fluid_state.poisson_residual).unwrap();
    writeln!(human, "============================================================\n").unwrap();

    let report = serde_json::json!({
        "benchmark": "tattva-taylor-green-v1",
        "n_requested": n,
        "steps_requested": steps,
        "reynolds": reynolds,
        "scheduler": {
            "agents_dispatched": wave_metrics.agents_dispatched,
            "cohorts_executed": wave_metrics.waves_executed,
            "conflicts_detected": wave_metrics.conflicts_detected,
            "schedule_plan_cohorts": plan.num_cohorts,
            "max_cohort_size": plan.max_cohort_size,
        },
        "initial": &initial,
        "fluid": &fluid_state,
        "timing": {
            "elapsed_s": elapsed.as_secs_f64(),
            "solves_per_sec": solves_per_sec,
        },
    });

    if json {
        eprintln!("{}", human);
        match serde_json::to_string_pretty(&report) {
            Ok(serialized) => println!("{}", serialized),
            Err(err) => {
                eprintln!("[!] JSON serialization failed: {err}");
                std::process::exit(1);
            }
        }
    } else {
        print!("{}", human);
    }
}
