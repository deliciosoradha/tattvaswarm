#!/usr/bin/env python3
"""
Zenodo Automated Deposit & Publication Script for Shiva-Muse Verification Paper.

Usage:
    export ZENODO_ACCESS_TOKEN="your_personal_access_token_here"
    python3 scripts/publish_zenodo.py [--publish] [--sandbox]

Or pass token directly:
    python3 scripts/publish_zenodo.py --token <TOKEN> [--publish]
"""
import os
import sys
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path

DEFAULT_PDF = Path("meta_hackathon_2026/paper_shiva_muse_verification.pdf")

METADATA = {
    "metadata": {
        "title": "Shiva-Muse: Deterministic Combinatorial Routing and Physical Invariant Verification across Meta Muse Models and SM120 GPU Kernels",
        "upload_type": "publication",
        "publication_type": "article",
        "description": (
            "<p>Formal verification paper for <b>Shiva-Muse &times; Tattva Swarm</b>, built for the Meta Global AI Developer Hackathon (Push the Frontier track). "
            "Couples Meta's frontier and open-weight model family (Muse Spark, meta-models/muse-spark-open-1026, Muse Glimmer, SAM 3.1, Muse Wonder) "
            "with register-resident matrix-free Triton GPU kernels on NVIDIA Blackwell SM120 hardware. Enforces hard physical invariants (divergence-free Navier-Stokes, "
            "CFL condition, energy conservation) with strict $100/$50 financial guardrail and RFC 9562 UUIDv7 deterministic session resumption.</p>"
        ),
        "creators": [
            {
                "name": "Padilla Arriaga, Axel Domingo",
                "affiliation": "Tattva Swarm Systems",
                "orcid": ""
            }
        ],
        "keywords": [
            "Meta Muse", "Triton", "CUDA", "GPU Kernels", "Blackwell SM120", 
            "Navier-Stokes", "Physical Invariants", "Ashta-Gate", "RFC 9562 UUIDv7", "Agentic Orchestration"
        ],
        "access_right": "open",
        "license": "CC-BY-4.0"
    }
}


def upload_to_zenodo(token: str, pdf_path: Path, publish: bool = False, sandbox: bool = False) -> dict:
    base_url = "https://sandbox.zenodo.org/api" if sandbox else "https://zenodo.org/api"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    print(f"[*] Conectando a Zenodo ({'Sandbox' if sandbox else 'Producción'})...")

    # 1. Crear deposición vacía
    req = urllib.request.Request(
        f"{base_url}/deposit/depositions",
        data=json.dumps(METADATA).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            dep = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"[X] Error creando deposición ({e.code}): {e.read().decode('utf-8')}")
        sys.exit(1)

    dep_id = dep["id"]
    bucket_url = dep["links"].get("bucket")
    doi = dep.get("metadata", {}).get("prereserve_doi", {}).get("doi", f"Pendiente (Deposition ID: {dep_id})")
    print(f"[OK] Deposición creada: ID={dep_id}")
    print(f"[OK] DOI pre-reservado: {doi}")

    # 2. Subir archivo PDF
    if not pdf_path.exists():
        print(f"[X] No se encuentra el archivo PDF en: {pdf_path}")
        sys.exit(1)

    filename = pdf_path.name
    file_bytes = pdf_path.read_bytes()
    print(f"[*] Subiendo '{filename}' ({len(file_bytes) / 1024:.1f} KB)...")

    if bucket_url:
        upload_req = urllib.request.Request(
            f"{bucket_url}/{filename}",
            data=file_bytes,
            headers={"Authorization": f"Bearer {token}"},
            method="PUT"
        )
    else:
        upload_req = urllib.request.Request(
            f"{base_url}/deposit/depositions/{dep_id}/files",
            data=file_bytes,
            headers={"Authorization": f"Bearer {token}", "Content-Disposition": f'attachment; filename="{filename}"'},
            method="POST"
        )

    try:
        with urllib.request.urlopen(upload_req) as resp:
            file_res = json.loads(resp.read().decode("utf-8"))
            print(f"[OK] Archivo subido con éxito: {file_res.get('filename', filename)} (MD5: {file_res.get('checksum')})")
    except urllib.error.HTTPError as e:
        print(f"[X] Error subiendo archivo ({e.code}): {e.read().decode('utf-8')}")
        sys.exit(1)

    # 3. Publicar (si se solicitó explícitamente)
    if publish:
        print("[*] Publicando registro formal en Zenodo...")
        pub_req = urllib.request.Request(
            f"{base_url}/deposit/depositions/{dep_id}/actions/publish",
            data=b"",
            headers=headers,
            method="POST"
        )
        try:
            with urllib.request.urlopen(pub_req) as resp:
                pub_res = json.loads(resp.read().decode("utf-8"))
                final_doi = pub_res.get("doi", doi)
                print(f"\n🎉 [ÉXITO] ¡Paper publicado formalmente en Zenodo!")
                print(f"🔗 DOI Oficial: {final_doi}")
                print(f"🔗 URL: https://doi.org/{final_doi}")
                return pub_res
        except urllib.error.HTTPError as e:
            print(f"[!] Error al publicar automáticamente ({e.code}): {e.read().decode('utf-8')}")
            print(f"[*] El borrador quedó guardado en tu cuenta. Puedes revisarlo y publicarlo en: https://zenodo.org/deposit/{dep_id}")
            return dep
    else:
        print(f"\n[OK] El registro ha sido creado como BORRADOR (seguro).")
        print(f"🔗 Revisa y publica con un clic en: https://zenodo.org/deposit/{dep_id}")
        return dep


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Subir paper a Zenodo")
    parser.add_argument("--token", default=os.environ.get("ZENODO_ACCESS_TOKEN", ""), help="Token personal de Zenodo")
    parser.add_argument("--pdf", default=str(DEFAULT_PDF), help="Ruta al PDF")
    parser.add_argument("--publish", action="store_true", help="Publicar formalmente (si no, queda en borrador)")
    parser.add_argument("--sandbox", action="store_true", help="Usar sandbox.zenodo.org para pruebas")
    args = parser.parse_args()

    if not args.token:
        print("[X] Se requiere un token de acceso a Zenodo.")
        print("    Configúralo con: export ZENODO_ACCESS_TOKEN='tu_token'")
        print("    O pásalo como argumento: python3 scripts/publish_zenodo.py --token <TOKEN>")
        sys.exit(1)

    upload_to_zenodo(args.token, Path(args.pdf), publish=args.publish, sandbox=args.sandbox)
