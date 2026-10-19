//! tattva-engine — the Rust core of TattvaSwarm.
//!
//! Two engines in one static binary, both std-only (builds offline):
//!
//! * `run-swarm` — the **logical swarm engine**: millions of deterministic
//!   worker state-machines executed across all cores. Same math as the
//!   pure-Python reference (`src/tattva_swarm/engine.py`): identical solves
//!   and checksums for identical configs — cross-checkable.
//!
//! * `exec` — the **code engine**: runs one command inside a hardened,
//!   network-less Docker sandbox with a wall-clock timeout, resource caps and
//!   captured/truncated output. Callable by agents (MCP, LangChain) or humans.

use std::env;
use std::fmt::Write as _;
use std::io::Read;
use std::process::{Command, Stdio};
use std::thread;
use std::time::{Duration, Instant};

const VERSION: &str = "0.1.0";

// Deterministic 64-bit LCG (Knuth constants) — must match engine.py exactly.
const A: u64 = 6364136223846793005;
const C: u64 = 1442695040888963407;

fn usage() -> ! {
    eprintln!("tattva-engine {VERSION} (rust core)");
    eprintln!("usage:");
    eprintln!("  tattva-engine run-swarm --workers N [--steps K] [--seed S] [--modulus M] [--threads T] [--json]");
    eprintln!("  tattva-engine exec --cmd \"...\" [--image IMG] [--timeout SECS] [--memory 256m] [--cpus 1]");
    eprintln!("                    [--allow-network] [--workdir DIR] [--cap BYTES] [--json]");
    eprintln!("  tattva-engine version");
    std::process::exit(2);
}

fn arg_value(args: &[String], name: &str) -> Option<String> {
    args.iter()
        .position(|a| a == name)
        .and_then(|i| args.get(i + 1))
        .cloned()
}

fn arg_flag(args: &[String], name: &str) -> bool {
    args.iter().any(|a| a == name)
}

fn arg_u64(args: &[String], name: &str, default: u64) -> u64 {
    arg_value(args, name)
        .and_then(|v| v.parse::<u64>().ok())
        .unwrap_or(default)
}

fn arg_f64(args: &[String], name: &str, default: f64) -> f64 {
    arg_value(args, name)
        .and_then(|v| v.parse::<f64>().ok())
        .unwrap_or(default)
}

// ---------------------------------------------------------------------------
// run-swarm
// ---------------------------------------------------------------------------

fn worker_start(seed: u64, w: u64) -> u64 {
    seed.wrapping_mul(A).wrapping_add(C).wrapping_add(w)
}

fn run_range(seed: u64, steps: u64, modulus: u64, start: u64, end: u64) -> (u64, u64, u64) {
    let mut solves: u64 = 0;
    let mut converged: u64 = 0;
    let mut checksum: u64 = 0;
    for w in start..end {
        let mut state = worker_start(seed, w);
        let mut hit = false;
        let mut step = 0;
        while step < steps {
            state = state.wrapping_mul(A).wrapping_add(C);
            if state % modulus == 0 {
                hit = true;
                solves += 1;
                break;
            }
            step += 1;
        }
        if hit {
            converged += 1;
        }
        checksum ^= state;
    }
    (solves, converged, checksum)
}

fn run_swarm(workers: u64, steps: u64, seed: u64, modulus: u64, threads: u64) -> String {
    let t0 = Instant::now();
    let nthreads = threads.max(1);
    let chunk = workers.div_ceil(nthreads);

    let mut handles = Vec::new();
    let mut t = 0u64;
    while t < nthreads {
        let start = t * chunk;
        let end = ((t + 1) * chunk).min(workers);
        if start >= end {
            break;
        }
        handles.push(thread::spawn(move || {
            run_range(seed, steps, modulus, start, end)
        }));
        t += 1;
    }

    let (mut solves, mut converged, mut checksum) = (0u64, 0u64, 0u64);
    for h in handles {
        let (s, c, x) = h.join().unwrap_or((0, 0, 0));
        solves += s;
        converged += c;
        checksum ^= x;
    }

    let elapsed = t0.elapsed().as_secs_f64();
    let workers_f = workers as f64;
    format!(
        r#"{{"engine":"rust","workers":{workers},"steps":{steps},"solves":{solves},"converged":{converged},"residual":{},"elapsed_s":{elapsed:.4},"workers_per_s":{:.1},"solves_per_s":{:.1},"checksum":"{checksum:016x}","threads":{nt},"deterministic":true}}"#,
        workers - converged,
        workers_f / elapsed.max(1e-9),
        solves as f64 / elapsed.max(1e-9),
        nt = nthreads,
    )
}

// ---------------------------------------------------------------------------
// exec (code engine)
// ---------------------------------------------------------------------------

fn json_escape(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 16);
    for ch in s.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => {
                let _ = write!(out, "\\u{:04x}", c as u32);
            }
            c => out.push(c),
        }
    }
    out
}

fn read_capped<R: Read>(mut r: R, cap: usize) -> (String, bool) {
    let mut buf: Vec<u8> = Vec::new();
    let mut truncated = false;
    let mut chunk = [0u8; 8192];
    loop {
        match r.read(&mut chunk) {
            Ok(0) => break,
            Ok(n) => {
                if buf.len() < cap {
                    let take = n.min(cap - buf.len());
                    buf.extend_from_slice(&chunk[..take]);
                }
                if buf.len() >= cap {
                    truncated = true;
                }
            }
            Err(_) => break,
        }
    }
    (String::from_utf8_lossy(&buf).into_owned(), truncated)
}

struct ExecOutcome {
    exit_code: i64,
    timed_out: bool,
    wall_s: f64,
    stdout: String,
    stderr: String,
    stdout_truncated: bool,
    stderr_truncated: bool,
}

#[allow(clippy::too_many_arguments)]
fn run_exec(
    cmdline: &str,
    image: &str,
    timeout_s: f64,
    memory: &str,
    cpus: &str,
    allow_network: bool,
    workdir: Option<&str>,
    cap: usize,
) -> Result<ExecOutcome, String> {
    let name = format!("tattva-exec-{}", std::process::id());
    let t0 = Instant::now();

    let mut cmd = Command::new("docker");
    cmd.arg("run")
        .arg("--rm")
        .args(["--name", &name])
        .args(["--memory", memory])
        .args(["--cpus", cpus])
        .args(["--pids-limit", "128"]);
    if !allow_network {
        cmd.args(["--network", "none"]);
    }
    if let Some(wd) = workdir {
        cmd.args(["-v", &format!("{wd}:/work")]).args(["-w", "/work"]);
    } else {
        cmd.args(["-w", "/tmp"]);
    }
    cmd.args(["--tmpfs", "/tmp:rw,size=64m"])
        .arg(image)
        .args(["/bin/sh", "-lc", cmdline])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    let mut child = cmd.spawn().map_err(|e| format!("failed to spawn docker: {e}"))?;

    let stdout_pipe = child.stdout.take().ok_or("no stdout pipe")?;
    let stderr_pipe = child.stderr.take().ok_or("no stderr pipe")?;
    let cap_out = cap;
    let cap_err = cap;
    let h_out = thread::spawn(move || read_capped(stdout_pipe, cap_out));
    let h_err = thread::spawn(move || read_capped(stderr_pipe, cap_err));

    let deadline = t0 + Duration::from_secs_f64(timeout_s.max(0.1));
    let mut timed_out = false;
    let exit_code;
    loop {
        match child.try_wait() {
            Ok(Some(status)) => {
                exit_code = status.code().unwrap_or(-1) as i64;
                break;
            }
            Ok(None) => {
                if Instant::now() >= deadline {
                    timed_out = true;
                    let _ = child.kill();
                    // also stop the container itself (killing the CLI client is not enough)
                    let _ = Command::new("docker").args(["kill", &name]).output();
                    let _ = child.wait();
                    exit_code = 124;
                    break;
                }
                thread::sleep(Duration::from_millis(50));
            }
            Err(e) => return Err(format!("wait failed: {e}")),
        }
    }

    let (stdout, stdout_truncated) = h_out.join().unwrap_or((String::new(), true));
    let (stderr, stderr_truncated) = h_err.join().unwrap_or((String::new(), true));

    Ok(ExecOutcome {
        exit_code,
        timed_out,
        wall_s: t0.elapsed().as_secs_f64(),
        stdout,
        stderr,
        stdout_truncated,
        stderr_truncated,
    })
}

// ---------------------------------------------------------------------------

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.is_empty() {
        usage();
    }

    match args[0].as_str() {
        "run-swarm" => {
            let workers = arg_u64(&args, "--workers", 1_000_000).max(1);
            let steps = arg_u64(&args, "--steps", 6).max(1);
            let seed = arg_u64(&args, "--seed", 7);
            let modulus = arg_u64(&args, "--modulus", 97).max(2);
            let default_threads = thread::available_parallelism().map(|n| n.get() as u64).unwrap_or(1);
            let threads = arg_u64(&args, "--threads", default_threads).max(1);
            let report = run_swarm(workers, steps, seed, modulus, threads);
            // JSON is the canonical output for this subcommand.
            println!("{report}");
        }
        "exec" => {
            let cmdline = match arg_value(&args, "--cmd") {
                Some(c) => c,
                None => usage(),
            };
            let image = arg_value(&args, "--image").unwrap_or_else(|| {
                env::var("TATTVA_SANDBOX_IMAGE").unwrap_or_else(|_| "python:3.12-slim".into())
            });
            let timeout_s = arg_f64(&args, "--timeout", 30.0);
            let memory = arg_value(&args, "--memory").unwrap_or_else(|| "256m".into());
            let cpus = arg_value(&args, "--cpus").unwrap_or_else(|| "1".into());
            let allow_network = arg_flag(&args, "--allow-network");
            let workdir = arg_value(&args, "--workdir");
            let cap = arg_u64(&args, "--cap", 65_536) as usize;
            let json = arg_flag(&args, "--json");

            match run_exec(
                &cmdline,
                &image,
                timeout_s,
                &memory,
                &cpus,
                allow_network,
                workdir.as_deref(),
                cap,
            ) {
                Ok(out) => {
                    if json {
                        println!(
                            r#"{{"engine":"rust","image":"{}","command":"{}","exit_code":{},"timed_out":{},"wall_s":{:.3},"stdout":"{}","stderr":"{}","stdout_truncated":{},"stderr_truncated":{}}}"#,
                            json_escape(&image),
                            json_escape(&cmdline),
                            out.exit_code,
                            out.timed_out,
                            out.wall_s,
                            json_escape(&out.stdout),
                            json_escape(&out.stderr),
                            out.stdout_truncated,
                            out.stderr_truncated,
                        );
                    } else {
                        print!("{}", out.stdout);
                        if !out.stderr.is_empty() {
                            eprint!("{}", out.stderr);
                        }
                        eprintln!(
                            "[tattva-engine] exit={} timed_out={} wall={:.3}s",
                            out.exit_code, out.timed_out, out.wall_s
                        );
                    }
                    std::process::exit(out.exit_code as i32);
                }
                Err(e) => {
                    if json {
                        println!(
                            r#"{{"engine":"rust","error":"{}"}}"#,
                            json_escape(&e)
                        );
                    } else {
                        eprintln!("[tattva-engine] error: {e}");
                    }
                    std::process::exit(2);
                }
            }
        }
        "version" | "--version" | "-V" => println!("tattva-engine {VERSION}"),
        _ => usage(),
    }
}
