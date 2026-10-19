#!/usr/bin/env bash
# Build the Rust core. No third-party crates (std only) → builds offline.
set -euo pipefail
cd "$(dirname "$0")"
echo "[tattva-engine] cargo build --release (nice -j2)"
nice -n 10 cargo build --release -j2
echo "[tattva-engine] binary: $(pwd)/target/release/tattva-engine"
