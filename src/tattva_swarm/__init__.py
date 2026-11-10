"""TattvaSwarm — a sovereign personal AI swarm (local-first) bridged with Shiva-Muse.

Tiered NVIDIA Nemotron routing on Nebius Token Factory, Meta Muse Meru-Pingala
hypercube routing (`ShivaMuseRouter`), Ashta-Gate 8-aspect reasoning verification,
Wonder Dream manifestation, persistent local memory, and compact logical worker swarms.
"""

from .muse_bridge import DEFAULT_MUSE_SESSION_ID, MuseSwarmAdapter
from .router import SwarmRouter, classify, route

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "DEFAULT_MUSE_SESSION_ID",
    "MuseSwarmAdapter",
    "SwarmRouter",
    "classify",
    "route",
]
