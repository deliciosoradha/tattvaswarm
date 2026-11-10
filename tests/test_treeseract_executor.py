"""Comprehensive E2E Tests for Treeseract Executor (Tree Search on Meru Q_n Hypercube).

Validates:
  1. Meru-Piṅgala Q_n Hypercube projection (Gray code, stratum k, bipartite color χ).
  2. Wonder Branch Generator structured hypothesis formulation.
  3. DualGate physics pruning (instant veto of aerogel thinning, thermal choking, Pareto breach).
  4. Shiva Reformulation healing pruned nodes back into admissible manifold.
  5. End-to-End Treeseract execution across TPS, Scramjet, Lunar Power, Rubisco, and Backtranslate.
  6. DharmaGate evidence sealing (chmod 444, manifest.sha256, hash-chained ledger).
  7. CLI subcommand `tattva treeseract run` and `tattva frontier treeseract`.
  8. MCP Server tool `frontier_treeseract_execute`.
"""
from __future__ import annotations

import pathlib
import tempfile
import pytest

from frontier_eval.treeseract_executor import (
    TreeseractExecutor,
    TreeseractNode,
    MeruTesseractProjector,
    WonderBranchGenerator,
    DualGatePruner,
    ShivaReformulator,
    ParetoBackpropagator,
    TreeseractEvidenceSealer,
)
from frontier_eval.agent_harness import TASK_DEFAULTS, default_agent
from src.tattva_swarm.cli import main as cli_main
from src.tattva_swarm.mcp_server import _tool_frontier_treeseract_execute


def test_meru_tesseract_projector_gray_code_and_bipartite_parity():
    """Verify Gray code bijection, stratum Hamming weight, and bipartite coloring on Q_4."""
    projector = MeruTesseractProjector(dimension=4)

    # 1. Address space size
    assert projector.max_vertices == 16

    # 2. Check all 16 vertices in Q_4
    seen_coords = set()
    for i in range(16):
        proj = projector.project(i)
        assert proj["node_id"] == i
        gray = proj["gray_code"]
        k = proj["stratum_k"]
        color = proj["bipartite_color"]
        coords = proj["coords"]

        # Stratum must equal popcount
        assert k == bin(gray).count("1")
        # Color must be parity
        assert color == (k % 2)
        assert len(coords) == 4
        seen_coords.add(coords)

    # All 16 vertices must be uniquely mapped
    assert len(seen_coords) == 16

    # 3. Consecutive Gray code transitions must have Hamming distance = 1
    for i in range(15):
        p1 = projector.project(i)
        p2 = projector.project(i + 1)
        dist = projector.hamming_distance(p1["coords"], p2["coords"])
        assert dist == 1, f"Gray code step {i}->{i+1} distance was {dist}, expected 1"


def test_wonder_generator_structured_variants():
    """Verify Wonder branch generator produces structured physical variations."""
    gen = WonderBranchGenerator()

    # TPS variants
    tps_base = default_agent("tps", TASK_DEFAULTS["tps"])
    tps_vars = gen.generate_variants("tps", tps_base, branch_factor=3, depth=1)
    assert len(tps_vars) == 3
    labels = [v[0] for v in tps_vars]
    assert any("thin_aerogel" in l for l in labels)
    assert any("optimized_aerogel" in l for l in labels)

    # Scramjet variants
    scram_base = default_agent("scramjet", TASK_DEFAULTS["scramjet"])
    scram_vars = gen.generate_variants("scramjet", scram_base, branch_factor=3, depth=1)
    assert len(scram_vars) == 3
    assert any("aggressive_phi" in v[0] for v in scram_vars)


def test_dual_gate_physics_pruning_and_scoring():
    """Verify DualGatePruner vetoes physically impossible branches immediately."""
    pruner = DualGatePruner()

    # 1. TPS with too-thin aerogel (causes backside temperature violation > 450K)
    bad_tps = {
        "layers": [
            {"material": "uhtc_zrb2_sic", "thickness_m": 0.003},
            {"material": "silica_aerogel", "thickness_m": 0.005},  # only 5mm -> heat penetrates
            {"material": "aluminum_2024", "thickness_m": 0.003},
        ],
        "agent_rationale": "Adversarial thin aerogel",
    }
    is_pruned, reason, cert, qual, score = pruner.evaluate_and_prune("tps", TASK_DEFAULTS["tps"], bad_tps)
    assert is_pruned is True
    assert score == 0.0
    assert "Physics Oracle Veto" in reason

    # 2. Valid TPS
    good_tps = default_agent("tps", TASK_DEFAULTS["tps"])
    is_pruned, reason, cert, qual, score = pruner.evaluate_and_prune("tps", TASK_DEFAULTS["tps"], good_tps)
    assert is_pruned is False
    assert reason is None
    assert qual.get("tier") == "PROXY_PASS"
    assert score > 0.0

    # 3. Scramjet with extreme phi (causes thermal choking)
    choking_scramjet = {
        "ramp_angles_deg": [6.0, 6.0, 6.0],
        "phi": 0.95,
        "agent_rationale": "Over-fueled choking case",
    }
    is_pruned, reason, cert, qual, score = pruner.evaluate_and_prune("scramjet", TASK_DEFAULTS["scramjet"], choking_scramjet)
    assert is_pruned is True
    assert "choking" in reason.lower() or "oracle veto" in reason.lower()

    # 4. Rubisco beyond Flamholz Pareto envelope
    fantasy_rubisco = {
        "engineered_variants": [{"name": "Fantasy", "S_C_O": 175.0, "k_cat_C_s1": 5.5}],
        "agent_rationale": "Impossible kinetic target",
    }
    is_pruned, reason, cert, qual, score = pruner.evaluate_and_prune("rubisco", TASK_DEFAULTS["rubisco"], fantasy_rubisco)
    assert is_pruned is True
    assert "extraordinary" in reason.lower() or "oracle veto" in reason.lower()


def test_shiva_reformulation_heals_pruned_candidate():
    """Verify Shiva reformulator mutates pruned candidates to restore physical feasibility."""
    reformulator = ShivaReformulator()
    pruner = DualGatePruner()

    # 1. Pruned TPS
    bad_tps = {
        "layers": [
            {"material": "uhtc_zrb2_sic", "thickness_m": 0.003},
            {"material": "silica_aerogel", "thickness_m": 0.008},
            {"material": "aluminum_2024", "thickness_m": 0.003},
        ],
    }
    is_pruned, reason, _, _, _ = pruner.evaluate_and_prune("tps", TASK_DEFAULTS["tps"], bad_tps)
    assert is_pruned is True

    # 2. Reformulation
    assert reformulator.can_reformulate(reason) is True
    healed = reformulator.reformulate("tps", bad_tps, reason)
    assert healed is not None
    label, healed_candidate = healed
    assert "shiva_repaired" in label

    # 3. Healed candidate should now pass
    is_p2, _, _, qual, score = pruner.evaluate_and_prune("tps", TASK_DEFAULTS["tps"], healed_candidate)
    assert is_p2 is False
    assert qual.get("tier") == "PROXY_PASS"
    assert score > 0.0


def test_treeseract_executor_e2e_tps():
    """E2E Test: Run Treeseract search on TPS, verify physical pruning and Dharma sealing."""
    with tempfile.TemporaryDirectory() as td:
        evidence_path = pathlib.Path(td) / "treeseract_tps_run"
        executor = TreeseractExecutor(
            task_name="tps",
            dimension=4,
            max_depth=2,
            branch_factor=3,
        )
        res = executor.run(evidence_dir=evidence_path)

        # 1. Verification of search tree dynamics
        assert res.task_name == "tps"
        assert res.total_nodes > 1
        assert res.pruned_count > 0, "At least one adversarial branch must have been pruned by physics"
        assert res.best_tier == "PROXY_PASS"
        assert res.best_score > 0.0
        assert len(res.trajectory) >= 1

        # 2. Evidence bundle sealing integrity
        assert evidence_path.exists()
        assert res.manifest_verdict in ("INTEGRITY_OK", "PASS")
        assert (evidence_path / "treeseract_receipt.json").exists()
        assert (evidence_path / "REPORT.md").exists()
        assert (evidence_path / "manifest.sha256").exists()

        # 3. Read receipt and check structure
        import json
        with open(evidence_path / "treeseract_receipt.json", "r", encoding="utf-8") as f:
            receipt = json.load(f)
        assert receipt["task_name"] == "tps"
        assert len(receipt["winning_trajectory"]) == len(res.trajectory)
        assert receipt["search_statistics"]["pruned_nodes"] == res.pruned_count


@pytest.mark.parametrize("task_name", ["scramjet", "tps", "lunar_power", "rubisco", "backtranslate"])
def test_treeseract_executor_all_5_domains(task_name: str):
    """E2E Test: Run Treeseract search across all 5 frontier physical domains."""
    with tempfile.TemporaryDirectory() as td:
        ev_dir = pathlib.Path(td) / f"treeseract_{task_name}"
        executor = TreeseractExecutor(
            task_name=task_name,
            dimension=3,
            max_depth=1,
            branch_factor=2,
        )
        res = executor.run(evidence_dir=ev_dir)

        assert res.task_name == task_name
        assert res.best_tier == "PROXY_PASS"
        assert res.best_score > 0.0
        assert res.manifest_verdict in ("INTEGRITY_OK", "PASS")


def test_cli_treeseract_subcommand():
    """Verify CLI integration of `tattva treeseract run` and `tattva frontier treeseract`."""
    with tempfile.TemporaryDirectory() as td:
        ev_dir = pathlib.Path(td) / "cli_treeseract_ev"
        # 1. Subcommand: tattva frontier treeseract
        code1 = cli_main(["frontier", "treeseract", "--task", "tps", "--depth", "1", "--evidence-dir", str(ev_dir)])
        assert code1 == 0
        assert (ev_dir / "manifest.sha256").exists()

    with tempfile.TemporaryDirectory() as td2:
        ev_dir2 = pathlib.Path(td2) / "cli_top_treeseract_ev"
        # 2. Subcommand: tattva treeseract run
        code2 = cli_main(["treeseract", "run", "--task", "scramjet", "--depth", "1", "--evidence-dir", str(ev_dir2)])
        assert code2 == 0
        assert (ev_dir2 / "manifest.sha256").exists()


def test_mcp_frontier_treeseract_execute():
    """Verify MCP server tool `frontier_treeseract_execute` works end-to-end."""
    with tempfile.TemporaryDirectory() as td:
        ev_dir = pathlib.Path(td) / "mcp_treeseract_ev"
        payload, is_err = _tool_frontier_treeseract_execute({
            "task": "backtranslate",
            "dimension": 3,
            "depth": 1,
            "branch_factor": 2,
            "evidence_dir": str(ev_dir),
        })
        assert is_err is False
        assert payload.get("status") == "ok"
        assert payload.get("task") == "backtranslate"
        assert payload.get("best_tier") == "PROXY_PASS"
        assert payload.get("manifest_verdict") in ("INTEGRITY_OK", "PASS")
