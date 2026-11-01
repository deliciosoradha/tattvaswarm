#!/usr/bin/env python3
"""
deposit_zenodo_all.py
Automatizacion completa de deposito y publicacion de los 5 papers de Tattva-Swarm en Zenodo.
Usa Zenodo REST API v1.
"""

import os
import sys
import json
import requests
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SUBMISSIONS_DIR = REPO_ROOT / "docs" / "submissions"
MANIFEST_FILE = SUBMISSIONS_DIR / "package_manifest.json"

PAPERS_METADATA = [
    {
        "id": "paper_100b_crown_resilience",
        "title": "Sub-Second Global Systemic Resilience Analysis of 100 Billion Coupled Urban-Financial Nodes via Meru-Piṅgala Hypercube Stratification",
        "upload_type": "publication",
        "publication_type": "preprint",
        "description": (
            "Evaluating coupled non-linear physical and financial stress across macroeconomic networks traditionally "
            "scales with catastrophic memory complexity O(N^2) due to explicit adjacency matrices. In this work, we present "
            "a deterministic, matrix-free streaming formulation based on ancient Indian Meru-Pingala combinatorics mapped onto "
            "a 36-dimensional hypercube (Q_36, spanning 68.7 billion discrete strata). By coupling non-linear Burgers-KPZ "
            "continuum hydrodynamic shock propagation with frustrated spin-glass counterparty dissipation directly inside "
            "GPU register files via 64-bit Gray code transformations and SWAR popcounts, our fused Triton kernel evaluates "
            "100,000,000,000 (100 Billion) coupled entities with zero atomic memory collisions and strictly bounded O(1) "
            "intermediate VRAM overhead. Executed on the state-of-the-art NVIDIA RTX PRO 6000 Blackwell Server Edition "
            "(94.97 GB VRAM, 188 SMs, sm_120), the engine evaluated the complete 100 Billion scale in 140.6495 seconds, "
            "sustaining a throughput of 710,987,320.32 entities/second with an asymptotic telescopic conservation residual of -1.97989e-9."
        ),
        "keywords": [
            "Meru-Pingala", "Blackwell GPU", "Triton Kernel", "Systemic Resilience",
            "Burgers-KPZ", "High Performance Computing", "O(1) VRAM", "Hypercube Stratification"
        ],
        "pdf": REPO_ROOT / "paper" / "paper_100b_crown_resilience.pdf",
        "zip": SUBMISSIONS_DIR / "zenodo_paper_100b_crown_resilience.zip",
    },
    {
        "id": "paper_earth2_cupti_blackwell",
        "title": "Subgrid-Scale Turbulence Closure and 44.01× Speedup on Blackwell SM120: Matrix-Free Fused Triton Kernels for High-Resolution Global Climate Modeling",
        "upload_type": "publication",
        "publication_type": "preprint",
        "description": (
            "High-resolution atmospheric modeling frameworks encounter severe memory bottlenecks when evaluating non-linear subgrid "
            "turbulence closures across global meshes (such as ERA5 with 103.8 million 3D points). Standard deep learning frameworks "
            "(PyTorch Eager) dispatch multiple disjoint kernels, causing effective throughput to drop below 50 GB/s. We present a "
            "register-fused, matrix-free subgrid turbulence closure operator in Triton coupling Smagorinsky eddy dissipation, advective "
            "shocks, and Coriolis dispersion. On an NVIDIA RTX PRO 6000 Blackwell Server Edition GPU (94.97 GB VRAM, 188 SMs, sm_120), "
            "the kernel achieves 0.8597 ms latency versus 37.84 ms for PyTorch Eager—delivering a measured 44.01x end-to-end speedup "
            "and sustaining 1,449.14 GB/s of high-bandwidth memory (HBM) throughput. Low-level compiler SASS telemetry confirmed optimal "
            "occupancy: 40 registers per thread, zero spills to local memory, and 100% coalesced global memory access."
        ),
        "keywords": [
            "Earth-2", "Blackwell SM120", "Triton Kernel", "Subgrid Turbulence",
            "Climate Modeling", "CUPTI", "SASS Profiling", "ERA5"
        ],
        "pdf": REPO_ROOT / "paper" / "paper_earth2_cupti_blackwell.pdf",
        "zip": SUBMISSIONS_DIR / "zenodo_paper_earth2_cupti_blackwell.zip",
    },
    {
        "id": "paper_defi_mainnet_sentinel",
        "title": "Sub-Millisecond Mainnet Financial Contagion Sentinel: Detecting High-Frequency Liquidity Cascades at 1,546 GB/s via Fused Hypercube Tensor Kernels",
        "upload_type": "publication",
        "publication_type": "preprint",
        "description": (
            "Decentralized Finance (DeFi) ecosystems on high-throughput layer-1/layer-2 networks face catastrophic systemic risks from "
            "flash-loan exploits, recursive liquidations, and cross-pool contagion. Conventional monitoring architectures rely on indexing "
            "subgraphs or off-chain event pollers, introducing multi-second observation latencies (500–2000 ms) that fail against atomic "
            "transaction bundles. In this work, we introduce the Mainnet Financial Contagion Sentinel, a specialized high-performance tensor "
            "engine that projects decentralized automated market maker (AMM) liquidity states onto a discrete combinatorial Meru-Pingala "
            "hypercube. By formulating non-linear pool balance depletion and counterparty spillover as a register-fused non-linear "
            "advective-diffusive shock operator with regularized adjoint state reversal (hindcasting), our Triton kernel evaluates "
            "10,800,000 active pool states in 0.0838 milliseconds (83.8 microseconds) on an NVIDIA RTX PRO 6000 Blackwell Server Edition "
            "GPU (94.97 GB VRAM, 188 SMs, sm_120). This achieves a sustained memory bandwidth of 1,546.39 GB/s."
        ),
        "keywords": [
            "DeFi Sentinel", "Financial Contagion", "High-Frequency Risk", "Blackwell GPU",
            "Triton", "Liquidity Cascades", "Adjoint Inversion", "Hindcasting"
        ],
        "pdf": REPO_ROOT / "paper" / "paper_defi_mainnet_sentinel.pdf",
        "zip": SUBMISSIONS_DIR / "zenodo_paper_defi_mainnet_sentinel.zip",
    },
    {
        "id": "paper_aerospace_hypersonic_shield",
        "title": "Aerothermal Hypersonic Reentry Simulation at Mach 15: Non-Linear PICA-X Thermal Shield Diffusion at 2,564 GB/s on NVIDIA Blackwell",
        "upload_type": "publication",
        "publication_type": "preprint",
        "description": (
            "Predicting localized aerothermal heat flux and thermal degradation in hypersonic vehicles during atmospheric re-entry "
            "(Mach 15+) requires resolving non-linear diffusion, radiative boundary conditions, and material pyrolysis across millions of "
            "composite volumetric cells. Classical computational fluid dynamics (CFD) and material response codes (e.g., FIAT, CHAR) are "
            "bottlenecked by memory latency and distributed message-passing overheads, restricting real-time on-board trajectory adaptation. "
            "In this paper, we present an ultra-fast, register-fused non-linear thermal diffusion operator implemented in OpenAI Triton to "
            "simulate aerothermal response in Phenolic-Impregnated Carbon Ablator (PICA-X) heat shields. Tested across 10,800,000 spatial "
            "finite volumes on an NVIDIA RTX PRO 6000 Blackwell Server Edition GPU (94.97 GB VRAM, 188 SMs, sm_120), the engine computes "
            "complete non-linear temperature progression, peak thermal shock localization, and regularized adjoint thermal state inversion "
            "in 0.0505 milliseconds (50.5 microseconds). This delivers an unprecedented sustained memory throughput of 2,564.91 GB/s."
        ),
        "keywords": [
            "Hypersonic Aerothermal", "Mach 15", "PICA-X", "Heat Shield",
            "Non-linear Diffusion", "Triton", "Blackwell GPU", "CFD"
        ],
        "pdf": REPO_ROOT / "paper" / "paper_aerospace_hypersonic_shield.pdf",
        "zip": SUBMISSIONS_DIR / "zenodo_paper_aerospace_hypersonic_shield.zip",
    },
    {
        "id": "paper_taylor_green_vortex",
        "title": "High-Fidelity Taylor-Green Vortex Hydrodynamic State Assimilation and Regularized Adjoint Inversion at 2,967 GB/s on NVIDIA Blackwell",
        "upload_type": "publication",
        "publication_type": "preprint",
        "description": (
            "Turbulent flow state estimation and parameter inversion are central challenges in computational fluid dynamics and geophysical "
            "data assimilation. We investigate the canonical Taylor-Green vortex at high Reynolds numbers, formulating a regularized "
            "adjoint state inversion operator executed entirely within streaming multiprocessor register files using custom Triton kernels. "
            "Evaluated across 10,800,000 degrees of freedom on the NVIDIA RTX PRO 6000 Blackwell Server Edition (sm_120), the fused "
            "operator resolves enstrophy dissipation and reconstructs boundary initial conditions in 0.0436 ms, sustaining an unprecedented "
            "2,967.82 GB/s effective memory throughput."
        ),
        "keywords": [
            "Taylor-Green Vortex", "Hydrodynamic Assimilation", "Adjoint Inversion",
            "Turbulence", "Blackwell GPU", "Triton Kernel", "Enstrophy Dissipation"
        ],
        "pdf": REPO_ROOT / "paper" / "paper_taylor_green_vortex.pdf",
        "zip": SUBMISSIONS_DIR / "zenodo_paper_taylor_green_vortex.zip",
    },
]

def get_token():
    # 1. Environment variable
    token = os.environ.get("ZENODO_TOKEN")
    if token:
        return token.strip()
    # 2. File ~/.zenodo_token
    token_file = Path.home() / ".zenodo_token"
    if token_file.exists():
        return token_file.read_text().strip()
    return None

def deposit_paper(session, base_url, paper, existing_depos=None, publish=False):
    print(f"\n==========================================")
    print(f"[*] Procesando: {paper['id']}")
    print(f"[*] Titulo: {paper['title']}")
    
    # 1. Buscar si ya existe una deposicion no enviada con este titulo
    dep = None
    if existing_depos:
        for ed in existing_depos:
            if ed.get("title") == paper["title"] and not ed.get("submitted", False):
                full_r = session.get(f"{base_url}/api/deposit/depositions/{ed['id']}")
                if full_r.status_code == 200:
                    dep = full_r.json()
                    print(f"[+] Reutilizando deposicion existente ID: {dep['id']}")
                    break

    if not dep:
        url = f"{base_url}/api/deposit/depositions"
        r = session.post(url, json={})
        if r.status_code not in (200, 201):
            print(f"[!] Error creando deposicion: {r.status_code} - {r.text}")
            return None
        dep = r.json()
        print(f"[+] Deposicion creada ID: {dep['id']}")

    dep_id = dep["id"]
    bucket_url = dep.get("links", {}).get("bucket")
    if not bucket_url:
        print(f"[!] Error: no se encontro bucket URL para dep ID {dep_id}")
        return None
    print(f"[+] Bucket URL: {bucket_url}")

    # 2. Subir PDF con Content-Type: application/octet-stream
    upload_headers = {"Content-Type": "application/octet-stream"}
    pdf_path = paper["pdf"]
    if pdf_path.exists():
        print(f"[*] Subiendo PDF: {pdf_path.name} ({pdf_path.stat().st_size:,} bytes)...")
        with open(pdf_path, "rb") as f:
            upload_r = session.put(f"{bucket_url}/{pdf_path.name}", data=f, headers=upload_headers)
            if upload_r.status_code in (200, 201):
                print(f"[+] PDF subido con exito.")
            else:
                print(f"[!] Error subiendo PDF: {upload_r.status_code} - {upload_r.text}")
    else:
        print(f"[!] ADVERTENCIA: No se encontro el archivo PDF en {pdf_path}")

    # 3. Subir ZIP release bundle con Content-Type: application/octet-stream
    zip_path = paper["zip"]
    if zip_path.exists():
        print(f"[*] Subiendo ZIP bundle: {zip_path.name} ({zip_path.stat().st_size:,} bytes)...")
        with open(zip_path, "rb") as f:
            upload_r = session.put(f"{bucket_url}/{zip_path.name}", data=f, headers=upload_headers)
            if upload_r.status_code in (200, 201):
                print(f"[+] ZIP bundle subido con exito.")
            else:
                print(f"[!] Error subiendo ZIP: {upload_r.status_code} - {upload_r.text}")
    else:
        print(f"[!] ADVERTENCIA: No se encontro el archivo ZIP en {zip_path}")

    # 4. Actualizar metadatos
    metadata_payload = {
        "metadata": {
            "title": paper["title"],
            "upload_type": paper["upload_type"],
            "publication_type": paper["publication_type"],
            "description": paper["description"],
            "creators": [
                {
                    "name": "Padilla Arriaga, Axel Domingo",
                    "affiliation": "RadhikaChain Sovereign Infrastructure & Autonomous Research Swarm"
                }
            ],
            "access_right": "open",
            "license": "cc-by-4.0",
            "keywords": paper["keywords"],
            "related_identifiers": [
                {
                    "identifier": "https://github.com/deliciosoradha/tattvaswarm",
                    "relation": "isSupplementTo",
                    "scheme": "url"
                }
            ]
        }
    }
    meta_r = session.put(f"{base_url}/api/deposit/depositions/{dep_id}", json=metadata_payload)
    if meta_r.status_code == 200:
        updated_dep = meta_r.json()
        prereserved_doi = updated_dep.get("metadata", {}).get("prereserved_doi", {}).get("doi", "N/A")
        print(f"[+] Metadatos registrados exitosamente.")
        print(f"[+] DOI Prereservado: {prereserved_doi}")
    else:
        print(f"[!] Error actualizando metadatos: {meta_r.status_code} - {meta_r.text}")
        return dep

    # 5. Publicar si se especifica
    if publish:
        print(f"[*] Publicando deposicion ID {dep_id}...")
        pub_r = session.post(f"{base_url}/api/deposit/depositions/{dep_id}/actions/publish")
        if pub_r.status_code in (200, 201, 202):
            published = pub_r.json()
            doi = published.get("doi", prereserved_doi)
            print(f"[✓] PAPER PUBLICADO CON EXITO EN ZENODO!")
            print(f"[✓] DOI OFICIAL: https://doi.org/{doi}")
            return published
        else:
            print(f"[!] Error al publicar ({pub_r.status_code}): {pub_r.text}")
            return updated_dep
    else:
        print(f"[*] Deposicion guardada como BORRADOR (Draft) listo para revision final o publicacion con 1-clic.")
        return updated_dep

def main():
    token = get_token()
    if not token:
        print("[!] ERROR: No se encontro el Personal Access Token de Zenodo.")
        print("    Por favor crealo en https://zenodo.org/account/settings/applications/tokens/new/")
        print("    con permisos 'deposit:actions' y 'deposit:write', y guardalo en ~/.zenodo_token")
        print("    o pasalo como variable de entorno ZENODO_TOKEN.")
        sys.exit(1)

    base_url = "https://zenodo.org"
    publish_now = "--publish" in sys.argv

    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    })

    # Verificar token
    test_r = session.get(f"{base_url}/api/deposit/depositions")
    if test_r.status_code != 200:
        print(f"[!] ERROR de autenticacion con Zenodo: {test_r.status_code} - {test_r.text}")
        sys.exit(1)

    print(f"[✓] Autenticacion exitosa con Zenodo REST API. Total deposiciones existentes: {len(test_r.json())}")
    
    existing_depos = test_r.json()
    results = []
    for paper in PAPERS_METADATA:
        res = deposit_paper(session, base_url, paper, existing_depos=existing_depos, publish=publish_now)
        if res:
            results.append({
                "id": paper["id"],
                "dep_id": res.get("id"),
                "doi": res.get("doi") or res.get("metadata", {}).get("prereserved_doi", {}).get("doi"),
                "url": res.get("links", {}).get("html")
            })

    # Guardar reporte de DOIs
    report_file = SUBMISSIONS_DIR / "zenodo_registration_report.json"
    with open(report_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[✓] Registro completo guardado en {report_file}")
    for item in results:
        print(f"  - {item['id']}: DOI={item['doi']} URL={item['url']}")

if __name__ == "__main__":
    main()
