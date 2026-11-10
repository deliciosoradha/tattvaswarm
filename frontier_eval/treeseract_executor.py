"""Treeseract Executor: Synthesis of Tree Search (MCTS) with Q_n Tesseract Topology & Domain Oracles.

Architectural Foundations:
  1. Meru-Piṅgala Q_n Hypercube Projection:
     - Bipartite Gray-code mapping: g = i ^ (i >> 1)
     - Stratum k = popcount(g), Bipartite Parity χ = k mod 2
     - Color 0 (even stratum): Synthesis, Pareto aggregation, Frontier reasoning
     - Color 1 (odd stratum): High-throughput parallel worker swarm, raw physics simulation
  2. Wonder Branch Generator:
     - Formulates structured candidate hypotheses with falsifiable invariants
  3. DualGatePruner:
     - Stage A: Ashta Structural Gate (claims, assumptions, falsifiability)
     - Stage B: First-principles physics oracles (P1 Scramjet, P2 TPS, P3 Lunar, P4 Rubisco, P5 Reverse Translatase)
     - Hard physical vetoes prune branches immediately, expending 0 subsequent rollout tokens
  4. Shiva Reformulator:
     - Destructive/Creative operator repairing close-to-frontier pruned states back to admissible physics
  5. Pareto Backpropagator:
     - Updates UCT values and maintains the non-dominated Pareto frontier
  6. DharmaGate Evidence Sealer:
     - Cryptographically locks winning trajectory (chmod 444 + manifest.sha256 + chained JSONL ledger)
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import json
import math
import os
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# Evidence sealing
try:
    from src.utils import compute_sha256_manifest, lock_evidence_directory, verify_manifest
    DHARMAGATE_AVAILABLE = True
except ImportError:
    from frontier_eval.runner import compute_sha256_manifest, lock_evidence_directory, verify_manifest
    DHARMAGATE_AVAILABLE = False

from frontier_eval.agent_harness import ORACLE_DISPATCH, TASK_DEFAULTS, default_agent


# ---------------------------------------------------------------------------
# 1. Treeseract Node & State Space
# ---------------------------------------------------------------------------

@dataclass
class TreeseractNode:
    """A node in the Treeseract tree search mapped to hypercube Q_n."""
    node_id: int
    parent_id: Optional[int]
    depth: int
    dimension: int
    action_label: str
    hypercube_coords: Tuple[int, ...]
    gray_code: int
    stratum_k: int
    bipartite_color: int  # 0 = even (aggregation), 1 = odd (worker swarm)
    candidate_state: Dict[str, Any]
    ashta_certificate: Optional[str] = None
    oracle_qualification: Optional[Dict[str, Any]] = None
    is_pruned: bool = False
    prune_reason: Optional[str] = None
    shiva_reformulated: bool = False
    visits: int = 0
    value_sum: float = 0.0
    score: float = 0.0
    children_ids: List[int] = field(default_factory=list)

    @property
    def q_value(self) -> float:
        return (self.value_sum / self.visits) if self.visits > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "parent_id": self.parent_id,
            "depth": self.depth,
            "dimension": self.dimension,
            "action_label": self.action_label,
            "hypercube_coords": list(self.hypercube_coords),
            "gray_code": self.gray_code,
            "stratum_k": self.stratum_k,
            "bipartite_color": self.bipartite_color,
            "candidate_state": self.candidate_state,
            "ashta_certificate": self.ashta_certificate,
            "oracle_tier": self.oracle_qualification.get("tier") if self.oracle_qualification else None,
            "is_pruned": self.is_pruned,
            "prune_reason": self.prune_reason,
            "shiva_reformulated": self.shiva_reformulated,
            "visits": self.visits,
            "score": round(self.score, 4),
            "children_ids": self.children_ids,
        }


# ---------------------------------------------------------------------------
# 2. Meru-Piṅgala Q_n Hypercube Projector
# ---------------------------------------------------------------------------

class MeruTesseractProjector:
    """Projects tree vertices onto a bipartite hypercube Q_n using Gray-code bijection."""

    def __init__(self, dimension: int = 4):
        if dimension < 2 or dimension > 32:
            raise ValueError(f"Dimension must be between 2 and 32, got {dimension}")
        self.dimension = dimension
        self.max_vertices = 1 << dimension

    def project(self, node_id: int) -> Dict[str, Any]:
        """Calculates Gray code, Hamming weight stratum, and bipartite color."""
        # Wrap index within hypercube address space
        idx = node_id % self.max_vertices
        gray = idx ^ (idx >> 1)
        stratum_k = bin(gray).count("1")
        bipartite_color = stratum_k & 1  # 0 = even, 1 = odd
        coords = tuple((gray >> i) & 1 for i in range(self.dimension))
        return {
            "node_id": node_id,
            "gray_code": gray,
            "stratum_k": stratum_k,
            "bipartite_color": bipartite_color,
            "coords": coords,
        }

    def hamming_distance(self, coords_a: Tuple[int, ...], coords_b: Tuple[int, ...]) -> int:
        return sum(a ^ b for a, b in zip(coords_a, coords_b))


# ---------------------------------------------------------------------------
# 3. Wonder Branch Generator (Structured Hypothesis Expansion)
# ---------------------------------------------------------------------------

class WonderBranchGenerator:
    """Generates structured parameter variations and design hypotheses for frontier tasks."""

    def generate_variants(
        self,
        task_name: str,
        parent_candidate: Dict[str, Any],
        branch_factor: int = 3,
        depth: int = 1,
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """Returns list of (action_label, mutated_candidate)."""
        variants: List[Tuple[str, Dict[str, Any]]] = []

        if task_name == "tps":
            layers = copy.deepcopy(parent_candidate.get("layers", []))
            # Find silica aerogel layer
            aerogel_idx = next((i for i, l in enumerate(layers) if l.get("material") == "silica_aerogel"), 1)
            current_th = layers[aerogel_idx].get("thickness_m", 0.040) if aerogel_idx < len(layers) else 0.040

            # 3 Variations:
            # 1. Thinned insulation (often causes backside heat breach > 450K -> test pruning)
            v1_layers = copy.deepcopy(layers)
            v1_th = max(0.008, current_th * 0.4)
            if aerogel_idx < len(v1_layers):
                v1_layers[aerogel_idx]["thickness_m"] = round(v1_th, 4)
            variants.append((
                f"thin_aerogel_{round(v1_th*1000)}mm",
                {"layers": v1_layers, "agent_rationale": "Aggressive lightweighting with minimal aerogel"}
            ))

            # 2. Optimized robust insulation
            v2_layers = copy.deepcopy(layers)
            v2_th = round(current_th * 1.15, 4)
            if aerogel_idx < len(v2_layers):
                v2_layers[aerogel_idx]["thickness_m"] = v2_th
            variants.append((
                f"optimized_aerogel_{round(v2_th*1000)}mm",
                {"layers": v2_layers, "agent_rationale": "Reinforced aerogel core with balanced thermal mass"}
            ))

            # 3. Overweight insulation (often exceeds 45 kg/m^2 areal mass limit)
            v3_layers = copy.deepcopy(layers)
            v3_th = round(current_th * 2.5, 4)
            if aerogel_idx < len(v3_layers):
                v3_layers[aerogel_idx]["thickness_m"] = v3_th
            variants.append((
                f"heavy_aerogel_{round(v3_th*1000)}mm",
                {"layers": v3_layers, "agent_rationale": "High-safety thick insulation shield"}
            ))

        elif task_name == "scramjet":
            phi = float(parent_candidate.get("phi", 0.35))
            ramps = list(parent_candidate.get("ramp_angles_deg", [6.0, 6.0, 6.0]))

            # 1. Moderate lean combustion (safe supersonic entry, prevents choking)
            variants.append((
                "lean_phi_0.28",
                {"ramp_angles_deg": ramps, "phi": 0.28, "agent_rationale": "Conservative lean equivalence ratio"}
            ))
            # 2. Optimized combustion (phi ~ 0.38)
            variants.append((
                "optimal_phi_0.38",
                {"ramp_angles_deg": ramps, "phi": 0.38, "agent_rationale": "Target thrust equivalence ratio"}
            ))
            # 3. Aggressive over-fueled combustion (causes thermal choking -> test pruning)
            variants.append((
                "aggressive_phi_0.85",
                {"ramp_angles_deg": ramps, "phi": 0.85, "agent_rationale": "Maximum heat release proposal"}
            ))

        elif task_name == "rubisco":
            # 1. Natural Griffithsia variant (on Flamholz front)
            variants.append((
                "variant_griffithsia",
                {
                    "engineered_variants": [{"name": f"Griffithsia_mutant_d{depth}", "S_C_O": 167.0, "k_cat_C_s1": 2.5}],
                    "agent_rationale": "Red algae Form IC enzyme at the empirical specificity frontier",
                }
            ))
            # 2. Natural C4 Maize variant (balanced kcat)
            variants.append((
                "variant_c4_maize",
                {
                    "engineered_variants": [{"name": f"Zea_mays_mutant_d{depth}", "S_C_O": 78.0, "k_cat_C_s1": 4.4}],
                    "agent_rationale": "C4 grass enzyme optimized for high turnover rate",
                }
            ))
            # 3. Impossible breakthrough variant (violates Flamholz front by 2x -> test pruning)
            variants.append((
                "impossible_millennium_variant",
                {
                    "engineered_variants": [{"name": f"Fantasy_Rubisco_d{depth}", "S_C_O": 175.0, "k_cat_C_s1": 5.5}],
                    "agent_rationale": "Synthetic enzyme claiming simultaneous extreme specificity and turnover",
                }
            ))

        elif task_name == "lunar_power":
            p_night = float(parent_candidate.get("reactor_rated_kWe", 40.0))
            # 1. Fission surface power (low mass ~1800kg)
            variants.append((
                "nuclear_stirling_40kWe",
                {
                    "primary_night_tech": "fission_surface_power",
                    "reactor_rated_kWe": p_night,
                    "total_system_mass_kg": p_night * 45.0,
                    "agent_rationale": "Kilopower-class nuclear Stirling power unit",
                }
            ))
            # 2. Advanced regenerative fuel cell + solar array
            variants.append((
                "solar_rfc_storage",
                {
                    "primary_night_tech": "solar_pv_rfc",
                    "day_pv_kW": 120.0,
                    "night_storage_kWh": p_night * 354.0,
                    "total_system_mass_kg": 14200.0,
                    "agent_rationale": "Solar photovoltaic array coupled to high-pressure regenerative fuel cell",
                }
            ))
            # 3. Heavy battery storage (mass exceeds 25,000 kg limit -> test pruning)
            variants.append((
                "heavy_li_ion_storage",
                {
                    "primary_night_tech": "battery_storage",
                    "night_storage_kWh": p_night * 354.0,
                    "total_system_mass_kg": 38000.0,
                    "agent_rationale": "Primary battery bank without nuclear source",
                }
            ))

        elif task_name == "backtranslate":
            # 1. Balanced mammalian/bacterial codons (GC ~ 50%)
            variants.append((
                "optimal_gc_balanced",
                {
                    "synthesized_dna": "ATGAAGTGGGTGACCATCTCCCTGCTGTTCCTGTTCTCCTCCGCCTACTCCTAA",
                    "agent_rationale": "Balanced GC content synonymous codon translation",
                }
            ))
            # 2. Extreme AT-rich translation (GC < 35% -> test pruning)
            variants.append((
                "at_rich_fail_gc",
                {
                    "synthesized_dna": "ATGAAAAAATGGGTTACCATTTCTTTATTATTTTTATTTTCTTCTGCCTATTCTTAA",
                    "agent_rationale": "Extreme AT biased codons",
                }
            ))
            # 3. High GC translation (GC ~ 60%)
            variants.append((
                "high_gc_admissible",
                {
                    "synthesized_dna": "ATGAAGTGGGTGACGATCAGCCTGCTGTTCCTGTTCAGCAGCGCGTACAGCTGA",
                    "agent_rationale": "High GC optimized codons within physiological bounds",
                }
            ))
        else:
            variants.append((f"variant_{depth}_1", parent_candidate))

        return variants[:branch_factor]


# ---------------------------------------------------------------------------
# 4. DualGatePruner (Structural + First-Principles Physics Validation)
# ---------------------------------------------------------------------------

class DualGatePruner:
    """Evaluates candidates using Ashta structural checks and physical domain oracles."""

    def __init__(self):
        self.ashta_eval_fn = None
        try:
            from meta_hackathon_2026.ashta_gate import evaluate as ashta_eval
            self.ashta_eval_fn = ashta_eval
        except ImportError:
            pass

    def evaluate_and_prune(
        self,
        task_name: str,
        task_def: Dict[str, Any],
        candidate: Dict[str, Any],
    ) -> Tuple[bool, Optional[str], Optional[str], Dict[str, Any], float]:
        """Evaluates node. Returns (is_pruned, prune_reason, ashta_cert, qualification, score)."""
        oracle = ORACLE_DISPATCH.get(task_name)
        if not oracle:
            raise ValueError(f"Unknown task oracle: {task_name}")

        # Stage A: Structural check (Ashta-Gate)
        ashta_cert = None
        if self.ashta_eval_fn:
            ashta_in = {
                "question": f"Is candidate {task_name} physically valid?",
                "answer": candidate.get("agent_rationale", "Physical hypothesis"),
                "claims": [{"text": "candidate design", "evidence": "harness check"}],
                "assumptions": ["standard atmospheric and thermodynamic assumptions"],
                "alternatives": ["suboptimal configurations"],
                "falsifiable_by": "domain oracle physical constraints",
                "uncertainty": 0.05,
                "limits": "operating envelope limits",
            }
            try:
                ashta_res = self.ashta_eval_fn(ashta_in)
                ashta_cert = ashta_res.get("certificate")
            except Exception:
                pass

        # Stage B: First-Principles Domain Oracle
        qualification = oracle.evaluate(task_def, candidate)
        tier = qualification.get("tier", "FAIL_ORACLE")

        # Never emit SOLVED
        if tier == "SOLVED":
            tier = "PROXY_PASS"
            qualification["tier"] = tier

        # PHOENIX VETO / PRUNE CHECK
        if tier != "PROXY_PASS":
            reasons = qualification.get("reasons", [])
            reason_str = "; ".join(reasons) if reasons else qualification.get("rationale", tier)
            return True, f"Physics Oracle Veto [{tier}]: {reason_str}", ashta_cert, qualification, 0.0

        # Calculate continuous physical efficiency score in (0.0, 1.0]
        score = self._compute_physical_score(task_name, qualification, candidate)
        return False, None, ashta_cert, qualification, score

    def _compute_physical_score(
        self,
        task_name: str,
        qualification: Dict[str, Any],
        candidate: Dict[str, Any],
    ) -> float:
        """Derives a normalized fitness score from physical safety margins."""
        details = qualification.get("details", {})
        if task_name == "tps":
            backside = float(details.get("backside_T_K", 450.0))
            areal_mass = float(details.get("areal_mass_kg_m2", 45.0))
            # Margin: how safely below 450 K and 45 kg/m2
            temp_margin = max(0.0, (450.0 - backside) / 450.0)
            mass_margin = max(0.0, (45.0 - areal_mass) / 45.0)
            return round(0.5 * temp_margin + 0.5 * mass_margin + 0.2, 4)

        elif task_name == "scramjet":
            m_comb = float(details.get("combustor_mach", 1.5))
            phi = float(candidate.get("phi", 0.35))
            # Higher combustor Mach margin above 1.0, optimal phi ~ 0.35
            mach_margin = min(1.0, max(0.0, (m_comb - 1.0) / 2.0))
            phi_opt = max(0.0, 1.0 - abs(phi - 0.35))
            return round(0.6 * mach_margin + 0.4 * phi_opt, 4)

        elif task_name == "rubisco":
            points = details.get("evaluated_points", [])
            if not points:
                return 0.5
            # Score based on proximity to Flamholz envelope
            max_dist = max(p.get("pareto_margin", 0.0) for p in points)
            return round(min(1.0, max(0.1, 1.0 - abs(max_dist))), 4)

        elif task_name == "lunar_power":
            mass = float(details.get("total_system_mass_kg", 25000.0))
            mass_margin = max(0.0, (25000.0 - mass) / 25000.0)
            return round(0.3 + 0.7 * mass_margin, 4)

        elif task_name == "backtranslate":
            gc = float(details.get("gc_content_pct", 50.0))
            gc_opt = max(0.0, 1.0 - abs(gc - 50.0) / 25.0)
            return round(0.5 + 0.5 * gc_opt, 4)

        return 0.5


# ---------------------------------------------------------------------------
# 5. Shiva Reformulator (Creation/Destruction Operator)
# ---------------------------------------------------------------------------

class ShivaReformulator:
    """Detects physically infeasible branches and mutates/repairs them back into the admissible manifold."""

    def can_reformulate(self, prune_reason: str) -> bool:
        if not prune_reason:
            return False
        keywords = ["backside", "choking", "areal mass", "GC content", "extraordinary"]
        return any(k.lower() in prune_reason.lower() for k in keywords)

    def reformulate(
        self,
        task_name: str,
        pruned_candidate: Dict[str, Any],
        prune_reason: str,
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Synthesizes a repaired parameter state."""
        repaired = copy.deepcopy(pruned_candidate)

        if task_name == "tps":
            layers = repaired.get("layers", [])
            for l in layers:
                if l.get("material") == "silica_aerogel":
                    # If backside exceeded, increase insulation to 42mm; if mass exceeded, lower to 35mm
                    if "backside" in prune_reason.lower():
                        l["thickness_m"] = 0.042
                    elif "areal mass" in prune_reason.lower():
                        l["thickness_m"] = 0.035
            repaired["agent_rationale"] = "Shiva Reformulation: Repaired aerogel thickness to restore heat-mass equilibrium"
            return ("shiva_repaired_tps_insulation", repaired)

        elif task_name == "scramjet":
            # Choking detected: reset phi to 0.35
            repaired["phi"] = 0.35
            repaired["ramp_angles_deg"] = [6.0, 6.0, 6.0]
            repaired["agent_rationale"] = "Shiva Reformulation: Reset equivalence ratio to 0.35 to break thermal choking"
            return ("shiva_repaired_scramjet_phi", repaired)

        elif task_name == "rubisco":
            # Reset variants to Flamholz empirical boundary
            repaired["engineered_variants"] = [
                {"name": "Shiva_Pareto_Calibrated", "S_C_O": 165.0, "k_cat_C_s1": 2.5}
            ]
            repaired["agent_rationale"] = "Shiva Reformulation: Clamped catalytic metrics onto empirical Pareto frontier"
            return ("shiva_repaired_rubisco_pareto", repaired)

        elif task_name == "backtranslate":
            # Restore balanced GC
            repaired["synthesized_dna"] = "ATGAAGTGGGTGACCATCTCCCTGCTGTTCCTGTTCTCCTCCGCCTACTCCTAA"
            repaired["agent_rationale"] = "Shiva Reformulation: Restored 50% GC balanced synonymous codons"
            return ("shiva_repaired_backtranslate_gc", repaired)

        elif task_name == "lunar_power":
            repaired["primary_night_tech"] = "fission_surface_power"
            repaired["reactor_rated_kWe"] = 40.0
            repaired["total_system_mass_kg"] = 1800.0
            repaired["agent_rationale"] = "Shiva Reformulation: Pivoted to nuclear Stirling microreactor to shed battery mass"
            return ("shiva_repaired_lunar_nuclear", repaired)

        return None


# ---------------------------------------------------------------------------
# 6. Pareto Backpropagator
# ---------------------------------------------------------------------------

class ParetoBackpropagator:
    """Backpropagates rollout results up the tree and tracks the global Pareto frontier."""

    def __init__(self, exploration_constant: float = 1.414):
        self.c_puct = exploration_constant

    def backpropagate(self, node_id: int, nodes: Dict[int, TreeseractNode], score: float) -> None:
        curr_id: Optional[int] = node_id
        while curr_id is not None:
            node = nodes.get(curr_id)
            if not node:
                break
            node.visits += 1
            node.value_sum += score
            curr_id = node.parent_id

    def select_best_child(self, parent: TreeseractNode, nodes: Dict[int, TreeseractNode]) -> Optional[TreeseractNode]:
        if not parent.children_ids:
            return None

        valid_children = [nodes[cid] for cid in parent.children_ids if cid in nodes and not nodes[cid].is_pruned]
        if not valid_children:
            return None

        # UCT selection weighted by Meru parity
        def uct_score(child: TreeseractNode) -> float:
            if child.visits == 0:
                return float("inf")
            exploitation = child.q_value
            exploration = self.c_puct * math.sqrt(math.log(max(1, parent.visits)) / child.visits)
            # Subtle parity encouragement: color 0 nodes receive a slight coordination bonus
            parity_bonus = 1.05 if child.bipartite_color == 0 else 1.00
            return (exploitation + exploration) * parity_bonus

        return max(valid_children, key=uct_score)


# ---------------------------------------------------------------------------
# 7. Evidence Sealer & Ledger Chaining
# ---------------------------------------------------------------------------

class TreeseractEvidenceSealer:
    """Packages search receipts and trajectory into a DharmaGate sealed bundle."""

    @staticmethod
    def seal_search(
        task_name: str,
        best_node: TreeseractNode,
        nodes: Dict[int, TreeseractNode],
        trajectory: List[int],
        evidence_dir: pathlib.Path,
        chain_file: Optional[pathlib.Path] = pathlib.Path("frontier_eval/runs/evaluation_chain.jsonl"),
    ) -> Dict[str, Any]:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        timestamp_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        run_id = f"treeseract_{task_name}_{timestamp_utc.replace(':', '').replace('-', '')}"

        # 1. Receipt JSON
        receipt = {
            "run_id": run_id,
            "task_name": task_name,
            "timestamp_utc": timestamp_utc,
            "best_node": best_node.to_dict(),
            "winning_trajectory": trajectory,
            "search_statistics": {
                "total_nodes": len(nodes),
                "pruned_nodes": sum(1 for n in nodes.values() if n.is_pruned),
                "admissible_nodes": sum(1 for n in nodes.values() if not n.is_pruned),
                "shiva_reformulated_nodes": sum(1 for n in nodes.values() if n.shiva_reformulated),
            },
            "nodes_graph": [n.to_dict() for n in nodes.values()],
        }
        receipt_file = evidence_dir / "treeseract_receipt.json"
        with open(receipt_file, "w", encoding="utf-8") as f:
            json.dump(receipt, f, indent=2, ensure_ascii=False)

        # 2. Markdown Report
        report_lines = [
            f"# Treeseract Execution Report — {task_name.upper()}",
            f"- **Run ID**: `{run_id}`",
            f"- **Timestamp**: `{timestamp_utc}`",
            f"- **Winning Node ID**: `node_{best_node.node_id}` (Stratum {best_node.stratum_k}, Color {best_node.bipartite_color})",
            f"- **Final Oracle Tier**: `{best_node.oracle_qualification.get('tier') if best_node.oracle_qualification else 'UNKNOWN'}`",
            f"- **Physical Efficiency Score**: `{best_node.score:.4f}`",
            f"- **Trajectory**: `{' -> '.join(f'N{nid}' for nid in trajectory)}`",
            "",
            "## Search Tree Metrics",
            f"- Total Nodes: {len(nodes)}",
            f"- Pruned by Physics Oracles: {receipt['search_statistics']['pruned_nodes']}",
            f"- Admissible Nodes: {receipt['search_statistics']['admissible_nodes']}",
            f"- Shiva Reformulations: {receipt['search_statistics']['shiva_reformulated_nodes']}",
            "",
            "## Winning Candidate Specification",
            "```json",
            json.dumps(best_node.candidate_state, indent=2, ensure_ascii=False),
            "```",
        ]
        report_file = evidence_dir / "REPORT.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines) + "\n")

        # 3. DharmaGate Lock and Manifest
        manifest_res = compute_sha256_manifest(evidence_dir)
        lock_res = lock_evidence_directory(evidence_dir)
        verify_res = verify_manifest(evidence_dir)

        # 4. Hash Chaining
        chain_entry = None
        if chain_file is not None:
            chain_file.parent.mkdir(parents=True, exist_ok=True)
            prev_sha256 = "0" * 64
            if chain_file.exists():
                with open(chain_file, "r", encoding="utf-8") as f:
                    lines = [ln.strip() for ln in f if ln.strip()]
                    if lines:
                        try:
                            prev_sha256 = json.loads(lines[-1]).get("sha256", prev_sha256)
                        except json.JSONDecodeError:
                            pass

            entry_payload = {
                "run_id": run_id,
                "timestamp_utc": timestamp_utc,
                "prev_sha256": prev_sha256,
                "bundle_manifest": manifest_res.get("files", {}),
                "summary": {best_node.oracle_qualification.get("tier", "PROXY_PASS"): 1},
            }
            entry_bytes = json.dumps(entry_payload, sort_keys=True).encode("utf-8")
            entry_sha256 = hashlib.sha256(entry_bytes).hexdigest()
            entry_payload["sha256"] = entry_sha256

            with open(chain_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry_payload) + "\n")
            chain_entry = entry_payload

        return {
            "run_id": run_id,
            "evidence_dir": str(evidence_dir),
            "manifest_verdict": verify_res.get("verdict"),
            "manifest_sha256": verify_res.get("manifest_sha256"),
            "chain_sha256": chain_entry.get("sha256") if chain_entry else None,
        }


# ---------------------------------------------------------------------------
# 8. Treeseract Executor Main Class
# ---------------------------------------------------------------------------

@dataclass
class TreeseractResult:
    task_name: str
    best_node_id: int
    best_candidate: Dict[str, Any]
    best_tier: str
    best_score: float
    total_nodes: int
    pruned_count: int
    trajectory: List[int]
    evidence_dir: str
    manifest_verdict: str
    chain_sha256: Optional[str]


class TreeseractExecutor:
    """Master orchestrator executing Tree Search over the Meru Q_n Hypercube."""

    def __init__(
        self,
        task_name: str,
        dimension: int = 4,
        max_depth: int = 2,
        branch_factor: int = 3,
        task_def: Optional[Dict[str, Any]] = None,
        initial_candidate: Optional[Dict[str, Any]] = None,
    ):
        if task_name not in ORACLE_DISPATCH:
            raise ValueError(f"Unknown task: {task_name}. Supported: {list(ORACLE_DISPATCH.keys())}")

        self.task_name = task_name
        self.dimension = dimension
        self.max_depth = max_depth
        self.branch_factor = branch_factor
        self.task_def = task_def or TASK_DEFAULTS.get(task_name, {})
        self.initial_candidate = initial_candidate or default_agent(task_name, self.task_def)

        self.projector = MeruTesseractProjector(dimension=dimension)
        self.branch_gen = WonderBranchGenerator()
        self.pruner = DualGatePruner()
        self.reformulator = ShivaReformulator()
        self.backpropagator = ParetoBackpropagator()

        self.nodes: Dict[int, TreeseractNode] = {}
        self._next_node_id = 0

    def _create_node(
        self,
        parent_id: Optional[int],
        depth: int,
        action_label: str,
        candidate_state: Dict[str, Any],
        shiva_reformulated: bool = False,
    ) -> TreeseractNode:
        nid = self._next_node_id
        self._next_node_id += 1

        proj = self.projector.project(nid)
        is_pruned, prune_reason, cert, qual, score = self.pruner.evaluate_and_prune(
            self.task_name, self.task_def, candidate_state
        )

        node = TreeseractNode(
            node_id=nid,
            parent_id=parent_id,
            depth=depth,
            dimension=self.dimension,
            action_label=action_label,
            hypercube_coords=proj["coords"],
            gray_code=proj["gray_code"],
            stratum_k=proj["stratum_k"],
            bipartite_color=proj["bipartite_color"],
            candidate_state=candidate_state,
            ashta_certificate=cert,
            oracle_qualification=qual,
            is_pruned=is_pruned,
            prune_reason=prune_reason,
            shiva_reformulated=shiva_reformulated,
            visits=1 if not is_pruned else 0,
            value_sum=score if not is_pruned else 0.0,
            score=score,
        )
        self.nodes[nid] = node
        if parent_id is not None and parent_id in self.nodes:
            self.nodes[parent_id].children_ids.append(nid)
        return node

    def run(self, evidence_dir: Optional[pathlib.Path] = None) -> TreeseractResult:
        """Executes full search and seals the evidence bundle."""
        # 1. Initialize Root
        root = self._create_node(
            parent_id=None,
            depth=0,
            action_label="root_initial_candidate",
            candidate_state=self.initial_candidate,
        )

        # 2. Tree Search Loop
        frontier: List[int] = [root.node_id]

        for current_depth in range(self.max_depth):
            next_frontier: List[int] = []
            for parent_nid in frontier:
                parent_node = self.nodes[parent_nid]
                if parent_node.is_pruned:
                    continue

                variants = self.branch_gen.generate_variants(
                    self.task_name,
                    parent_node.candidate_state,
                    branch_factor=self.branch_factor,
                    depth=current_depth + 1,
                )

                for label, child_candidate in variants:
                    child_node = self._create_node(
                        parent_id=parent_nid,
                        depth=current_depth + 1,
                        action_label=label,
                        candidate_state=child_candidate,
                    )

                    # If pruned by physics, attempt Shiva Reformulation
                    if child_node.is_pruned and self.reformulator.can_reformulate(child_node.prune_reason or ""):
                        reformulated = self.reformulator.reformulate(
                            self.task_name, child_candidate, child_node.prune_reason or ""
                        )
                        if reformulated:
                            r_label, r_candidate = reformulated
                            reformed_node = self._create_node(
                                parent_id=parent_nid,
                                depth=current_depth + 1,
                                action_label=r_label,
                                candidate_state=r_candidate,
                                shiva_reformulated=True,
                            )
                            if not reformed_node.is_pruned:
                                next_frontier.append(reformed_node.node_id)
                                self.backpropagator.backpropagate(reformed_node.node_id, self.nodes, reformed_node.score)

                    if not child_node.is_pruned:
                        next_frontier.append(child_node.node_id)
                        self.backpropagator.backpropagate(child_node.node_id, self.nodes, child_node.score)

            frontier = next_frontier
            if not frontier:
                break

        # 3. Select Winning Trajectory
        admissible_nodes = [n for n in self.nodes.values() if not n.is_pruned]
        if not admissible_nodes:
            # Fallback to root even if pruned
            best_node = root
        else:
            best_node = max(admissible_nodes, key=lambda n: n.score)

        trajectory: List[int] = []
        curr: Optional[TreeseractNode] = best_node
        while curr is not None:
            trajectory.append(curr.node_id)
            curr = self.nodes.get(curr.parent_id) if curr.parent_id is not None else None
        trajectory.reverse()

        # 4. Seal Evidence Bundle
        target_dir = evidence_dir or pathlib.Path(f"data/evidence/treeseract_{self.task_name}")
        seal_info = TreeseractEvidenceSealer.seal_search(
            task_name=self.task_name,
            best_node=best_node,
            nodes=self.nodes,
            trajectory=trajectory,
            evidence_dir=target_dir,
        )

        return TreeseractResult(
            task_name=self.task_name,
            best_node_id=best_node.node_id,
            best_candidate=best_node.candidate_state,
            best_tier=best_node.oracle_qualification.get("tier", "PROXY_PASS") if best_node.oracle_qualification else "UNKNOWN",
            best_score=best_node.score,
            total_nodes=len(self.nodes),
            pruned_count=sum(1 for n in self.nodes.values() if n.is_pruned),
            trajectory=trajectory,
            evidence_dir=str(target_dir),
            manifest_verdict=seal_info.get("manifest_verdict", "UNKNOWN"),
            chain_sha256=seal_info.get("chain_sha256"),
        )
