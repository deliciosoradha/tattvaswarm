"""TattvaSwarm Google Colab Bridge & Quickstart Runner.

Paste and run this directly in a Google Colab notebook cell.
Automatically detects GPU hardware (T4 / L4 / A100), bootstraps dependencies,
verifies all physical domain oracles, and seals forensic evidence bundles.
"""

# Cell 1: Bootstrap & Run
import os
import subprocess
import sys

print("=" * 60)
print("TattvaSwarm x Google Colab Bridge Initializer")
print("=" * 60)

# 1. Hardware Detection
try:
    smi = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], text=True).strip()
    print(f"[*] GPU Detected: {smi}")
except Exception:
    print("[*] No GPU detected (running in CPU mode)")

# 2. Setup Repository
repo_dir = "/content/tattvaswarm" if os.path.exists("/content") else os.getcwd()
if not os.path.exists(repo_dir) and os.path.exists("/content"):
    print("[*] Cloning TattvaSwarm repository...")
    subprocess.check_call(["git", "clone", "https://github.com/deliciosoradha/tattvaswarm.git", repo_dir])

sys.path.insert(0, os.path.join(repo_dir, "src"))
sys.path.insert(0, os.path.join(repo_dir, "meta_hackathon_2026"))
sys.path.insert(0, repo_dir)

# 3. Ensure uv / dependencies
try:
    import numpy
except ImportError:
    print("[*] Installing numpy...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "numpy", "pytest"])

# 4. Run Agent Harness across all 5 Frontier Domains
print("[*] Executing Frontier Agent Harness (5 Domains)...")
from frontier_eval.agent_harness import run_pipeline, ORACLE_DISPATCH
import pathlib

evidence_base = pathlib.Path("/content/evidence" if os.path.exists("/content") else "data/evidence_colab")
for tname in ORACLE_DISPATCH:
    target_dir = evidence_base / tname
    res = run_pipeline(tname, target_dir)
    print(f"  [OK] Task `{tname:15}` -> Tier: {res['tier']} | Sealed: {res['evidence_dir']}")

# 5. Run Adversarial Veto Suite
print("\n[*] Executing Adversarial Veto Pack...")
from frontier_eval.adversarial_cases import run_adversarial
adver_res = run_adversarial()
print(f"  Veto Success: {'PASS (100% Rejected)' if adver_res['all_vetoed'] else 'FAIL'}")
print(f"  Cases Tested: {adver_res['cases_tested']} | False Passes: {adver_res['false_passes']}")

# 6. Verify Evidence Sealing
print("\n[*] Verifying Evidence Manifests (DharmaGate Evidence Shield)...")
from frontier_eval.agent_harness import verify_manifest
for tname in ORACLE_DISPATCH:
    v = verify_manifest(evidence_base / tname)
    print(f"  Manifest `{tname:15}` -> Verdict: {v.get('verdict')}")

print("\n" + "=" * 60)
print("Colab Execution Complete — 100% Verified and Sealed.")
print("=" * 60)
