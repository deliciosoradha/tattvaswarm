#!/usr/bin/env python3
"""
package_submissions.py
Packages the 5 milestone papers into verified standalone distribution archives
for arXiv (tar.gz) and Zenodo (zip), complete with SHA-256 integrity checksums.
"""

import os
import tarfile
import zipfile
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PAPER_DIR = REPO_ROOT / "paper"
DOCS_SUBMISSIONS = REPO_ROOT / "docs" / "submissions"
DOCS_SUBMISSIONS.mkdir(parents=True, exist_ok=True)

PAPERS = [
    {
        "id": "paper_100b_crown_resilience",
        "title": "Sub-Second Global Systemic Resilience Analysis of 100 Billion Coupled Urban-Financial Nodes via Meru-Pingala Hypercube Stratification",
        "tex": "paper/paper_100b_crown_resilience.tex",
        "pdf": "paper/paper_100b_crown_resilience.pdf",
        "benchmark": "benchmarks/global_systemic_resilience_paper.py",
        "figures": [],
        "primary_category": "cs.DC"
    },
    {
        "id": "paper_earth2_cupti_blackwell",
        "title": "Subgrid-Scale Turbulence Closure and 44.01x Speedup on Blackwell SM120: Matrix-Free Fused Triton Kernels for High-Resolution Global Climate Modeling",
        "tex": "paper/paper_earth2_cupti_blackwell.tex",
        "pdf": "paper/paper_earth2_cupti_blackwell.pdf",
        "benchmark": "benchmarks/nsight_earth2_cupti_trace.py",
        "figures": ["docs/evidence/nsight_earth2_gpu_trace_evidence.png"],
        "primary_category": "cs.DC"
    },
    {
        "id": "paper_defi_mainnet_sentinel",
        "title": "Sub-Millisecond Mainnet Financial Contagion Sentinel: Detecting High-Frequency Liquidity Cascades at 1,546 GB/s via Fused Hypercube Tensor Kernels",
        "tex": "paper/paper_defi_mainnet_sentinel.tex",
        "pdf": "paper/paper_defi_mainnet_sentinel.pdf",
        "benchmark": "benchmarks/triple_industrial_meru_triton.py",
        "figures": [],
        "primary_category": "q-fin.CP"
    },
    {
        "id": "paper_aerospace_hypersonic_shield",
        "title": "Aerothermal Hypersonic Reentry Simulation at Mach 15: Non-Linear PICA-X Thermal Shield Diffusion at 2,564 GB/s on NVIDIA Blackwell",
        "tex": "paper/paper_aerospace_hypersonic_shield.tex",
        "pdf": "paper/paper_aerospace_hypersonic_shield.pdf",
        "benchmark": "benchmarks/triple_industrial_meru_triton.py",
        "figures": [],
        "primary_category": "physics.flu-dyn"
    },
    {
        "id": "paper_taylor_green_vortex",
        "title": "High-Fidelity Taylor-Green Vortex Hydrodynamic State Assimilation and Regularized Adjoint Inversion at 2,967 GB/s on NVIDIA Blackwell",
        "tex": "paper/paper_taylor_green_vortex.tex",
        "pdf": "paper/paper_taylor_green_vortex.pdf",
        "benchmark": "benchmarks/triple_industrial_meru_triton.py",
        "figures": [],
        "primary_category": "physics.flu-dyn"
    }
]

def sha256_file(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def make_bib(p: dict) -> str:
    return f"""@article{{{p['id']},
  author = {{Padilla Arriaga, Axel Domingo}},
  title = {{{p['title']}}},
  year = {{2026}},
  journal = {{RadhikaChain Autonomous Research Swarm Preprint}},
  url = {{https://github.com/deliciosoradha/tattvaswarm/blob/main/{p['pdf']}}}
}}
"""

def main():
    package_manifest = []

    for p in PAPERS:
        pid = p["id"]
        tex_path = REPO_ROOT / p["tex"]
        pdf_path = REPO_ROOT / p["pdf"]
        bench_path = REPO_ROOT / p["benchmark"]

        # 1. Package arXiv tar.gz
        arxiv_tar_path = DOCS_SUBMISSIONS / f"arxiv_{pid}.tar.gz"
        with tarfile.open(arxiv_tar_path, "w:gz") as tar:
            tar.add(tex_path, arcname=tex_path.name)
            for fig in p["figures"]:
                fig_path = REPO_ROOT / fig
                if fig_path.exists():
                    tar.add(fig_path, arcname=fig)

        arxiv_hash = sha256_file(arxiv_tar_path)
        arxiv_size = arxiv_tar_path.stat().st_size

        # 2. Package Zenodo zip
        zenodo_zip_path = DOCS_SUBMISSIONS / f"zenodo_{pid}.zip"
        with zipfile.ZipFile(zenodo_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(pdf_path, arcname=pdf_path.name)
            zipf.write(tex_path, arcname=tex_path.name)
            if bench_path.exists():
                zipf.write(bench_path, arcname=bench_path.name)
            for fig in p["figures"]:
                fig_path = REPO_ROOT / fig
                if fig_path.exists():
                    zipf.write(fig_path, arcname=fig)
            zipf.writestr("citation.bib", make_bib(p))

        zenodo_hash = sha256_file(zenodo_zip_path)
        zenodo_size = zenodo_zip_path.stat().st_size

        entry = {
            "id": pid,
            "title": p["title"],
            "primary_category": p["primary_category"],
            "pdf": {
                "path": str(p["pdf"]),
                "size_bytes": pdf_path.stat().st_size,
                "sha256": sha256_file(pdf_path)
            },
            "arxiv_bundle": {
                "filename": arxiv_tar_path.name,
                "rel_path": f"docs/submissions/{arxiv_tar_path.name}",
                "size_bytes": arxiv_size,
                "sha256": arxiv_hash
            },
            "zenodo_bundle": {
                "filename": zenodo_zip_path.name,
                "rel_path": f"docs/submissions/{zenodo_zip_path.name}",
                "size_bytes": zenodo_size,
                "sha256": zenodo_hash
            }
        }
        package_manifest.append(entry)
        print(f"Packed {pid}:")
        print(f"  -> arXiv:  {arxiv_tar_path.name} ({arxiv_size} B) [{arxiv_hash[:16]}...]")
        print(f"  -> Zenodo: {zenodo_zip_path.name} ({zenodo_size} B) [{zenodo_hash[:16]}...]")

    # Write manifests
    manifest_path = DOCS_SUBMISSIONS / "package_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(package_manifest, f, indent=2)

    print(f"\nManifest written to {manifest_path}")

if __name__ == "__main__":
    main()
