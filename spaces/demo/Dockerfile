# TattvaSwarm live demo — Hugging Face Space (Docker SDK)
#
# NOTE: this Dockerfile is written for the *staged* layout (app.py and the
# package at the build root), which is how spaces/deploy_hf.sh assembles the
# Space repository. Keep it in sync with that script.

FROM python:3.12-slim

WORKDIR /app

COPY app.py ./app.py
COPY tattva_swarm ./tattva_swarm

ENV NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1/ \
    TATTVA_MODEL_FAST=nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B \
    TATTVA_MODEL_REASONING=nvidia/nemotron-3-super-120b-a12b \
    TATTVA_MODEL_HEAVY=nvidia/Nemotron-3-Ultra-550b-a55b \
    TATTVA_HOME=/data/tattva

RUN mkdir -p /data/tattva && useradd -m demo && chown -R demo /data
USER demo

EXPOSE 7860

# NEBIUS_API_KEY comes from the Space secret (never baked into the image)
CMD ["python3", "app.py"]
