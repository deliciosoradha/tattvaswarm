#!/usr/bin/env bash
# Deploy del demo TattvaSwarm como endpoint CPU serverless de Nebius.
# Patrón verificado del cookbook oficial (agents/openclaw: CPU endpoint + Token Factory).
#
# Prerrequisitos (una vez; ver OPERATOR-NEXT.md):
#   - nebius CLI instalado y perfil configurado  ->  `nebius profile list`
#   - NEBIUS_API_KEY disponible (env o ~/.tattva/nebius.env). Nunca se imprime.
#
# Uso:  bash deploy_nebius.sh
# Var. opcionales: NAME, PRESET, SUBNET_ID, TATTVA_REPO_TARBALL
set -euo pipefail

NAME="${NAME:-tattvaswarm-demo}"
PRESET="${PRESET:-4vcpu-16gb}"
TARBALL="${TATTVA_REPO_TARBALL:-https://gitlab.com/radhikatmosphere/tattvaswarm/-/archive/main/tattvaswarm-main.tar.gz}"

# --- key (sin imprimirla jamás) ---
if [ -z "${NEBIUS_API_KEY:-}" ] && [ -f "$HOME/.tattva/nebius.env" ]; then
  set -a; . "$HOME/.tattva/nebius.env"; set +a
fi
: "${NEBIUS_API_KEY:?NEBIUS_API_KEY no disponible (ponla en ~/.tattva/nebius.env)}"

# --- subnet del proyecto ---
if [ -z "${SUBNET_ID:-}" ]; then
  SUBNET_ID=$(nebius vpc subnet list --format jsonpath='{.items[0].metadata.id}')
fi
[ -n "$SUBNET_ID" ] || { echo "[deploy] no hay subnet utilizable en el proyecto"; exit 1; }

CMD="pip install --no-cache-dir ${TARBALL} && python -m tattva_swarm.demo_server --host 0.0.0.0 --port 8000"

echo "[deploy] creando endpoint '$NAME' (platform cpu-d3, preset $PRESET)..."
nebius ai endpoint create \
  --name "$NAME" \
  --image python:3.12-slim \
  --container-command bash \
  --args "-lc '${CMD}'" \
  --container-port 8000 \
  --platform cpu-d3 \
  --preset "$PRESET" \
  --public \
  --subnet-id "$SUBNET_ID" \
  --env "NEBIUS_API_KEY=${NEBIUS_API_KEY}" \
  --env "TATTVA_MODEL_FAST=nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B" \
  --env "TATTVA_MODEL_REASONING=nvidia/nemotron-3-super-120b-a12b" \
  --env "TATTVA_MODEL_HEAVY=nvidia/Nemotron-3-Ultra-550b-a55b"

echo "[deploy] esperando estado RUNNING (el pull de la imagen tarda unos minutos)..."
STATE=""
for i in $(seq 1 40); do
  STATE=$(nebius ai endpoint get-by-name --name "$NAME" --format jsonpath='{.status.state}' 2>/dev/null || true)
  echo "  estado: ${STATE:-?} (intento $i/40)"
  [ "$STATE" = "RUNNING" ] && break
  sleep 15
done

ENDPOINT_ID=$(nebius ai endpoint get-by-name --name "$NAME" --format jsonpath='{.metadata.id}' 2>/dev/null || true)
IP=$(nebius ai endpoint get-by-name --name "$NAME" --format jsonpath='{.status.public_endpoints[0]}' 2>/dev/null || true)

echo
echo "== RESULTADO =="
echo "estado    : ${STATE:-?}"
echo "demo URL  : http://${IP:-?}/"
echo "health    : http://${IP:-?}/healthz"
echo "prueba    : curl -s http://${IP:-?}/healthz"
echo "logs      : nebius ai endpoint logs ${ENDPOINT_ID:-<id>} --follow"
echo "borrar    : nebius ai endpoint delete ${ENDPOINT_ID:-<id>}   (hacerlo al terminar el judging)"
