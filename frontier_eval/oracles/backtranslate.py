"""P5 oracle — Reverse Translatase (De-novo Peptide-to-Nucleic Acid Decoding).

Biological context:
  There is no known biological enzyme that acts as a true reverse translatase
  (reading an arbitrary post-translationally unmodified peptide and synthesizing
  its corresponding mRNA/cDNA without an existing template or tRNA adaptor matrix).

Oracle verification:
  1. The model proposes a sequence-specific reverse translation mapping.
  2. The proposed DNA/RNA sequence must translate EXACTLY back to the target peptide
     using the Standard Genetic Code (NCBI translation table 1).
  3. No internal premature stop codons (*).
  4. Codon Adaptation / GC-content within host-compatible bounds (default: 35% - 65%).
  5. The enzymatic mechanism is classified strictly as HYPOTHETICAL / THEORETICAL DESIGN,
     never certified as wet-lab functional (prevents false-positive overclaims).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

CODON_TABLE = {
    "ATA": "I", "ATC": "I", "ATT": "I", "ATG": "M",
    "ACA": "T", "ACC": "T", "ACG": "T", "ACT": "T",
    "AAC": "N", "AAT": "N", "AAA": "K", "AAG": "K",
    "AGC": "S", "AGT": "S", "AGA": "R", "AGG": "R",
    "CTA": "L", "CTC": "L", "CTG": "L", "CTT": "L",
    "CCA": "P", "CCC": "P", "CCG": "P", "CCT": "P",
    "CAC": "H", "CAT": "H", "CAA": "Q", "CAG": "Q",
    "CGA": "R", "CGC": "R", "CGG": "R", "CGT": "R",
    "GTA": "V", "GTC": "V", "GTG": "V", "GTT": "V",
    "GCA": "A", "GCC": "A", "GCG": "A", "GCT": "A",
    "GAC": "D", "GAT": "D", "GAA": "E", "GAG": "E",
    "GGA": "G", "GGC": "G", "GGG": "G", "GGT": "G",
    "TCA": "S", "TCC": "S", "TCG": "S", "TCT": "S",
    "TTC": "F", "TTT": "F", "TTA": "L", "TTG": "L",
    "TAC": "Y", "TAT": "Y", "TAA": "*", "TAG": "*",
    "TGC": "C", "TGT": "C", "TGA": "*", "TGG": "W",
}


def translate_dna(dna: str) -> str:
    """Translate DNA string in frame 0 using standard genetic code."""
    dna = dna.upper().replace("U", "T").strip()
    pep = []
    for i in range(0, len(dna) - 2, 3):
        codon = dna[i:i + 3]
        pep.append(CODON_TABLE.get(codon, "X"))
    return "".join(pep)


def evaluate(task: Dict[str, Any], answer: Dict[str, Any]) -> Dict[str, Any]:
    target_peptide = task.get("target_peptide", "MKWVTFISLLFLFSSAYS").upper().strip()
    gc_min = float(task.get("gc_min_pct", 35.0))
    gc_max = float(task.get("gc_max_pct", 65.0))
    reasons: List[str] = []

    try:
        candidate_dna = str(answer["synthesized_dna"]).upper().replace("U", "T").strip()
    except (KeyError, TypeError) as exc:
        return {"tier": "UNPARSEABLE", "reasons": [f"Missing synthesized_dna: {exc}"]}

    if len(candidate_dna) % 3 != 0:
        reasons.append(f"DNA length {len(candidate_dna)} is not a multiple of 3 (frameshift)")

    # Forward translation check
    translated = translate_dna(candidate_dna)
    clean_translated = translated.rstrip("*")

    if clean_translated != target_peptide:
        reasons.append(
            f"Forward translation mismatch: expected '{target_peptide}', got '{clean_translated}'"
        )

    if "*" in clean_translated:
        reasons.append("Premature stop codon found inside coding sequence")

    # GC content check
    gc_count = candidate_dna.count("G") + candidate_dna.count("C")
    gc_pct = (gc_count / max(len(candidate_dna), 1)) * 100.0
    if not (gc_min <= gc_pct <= gc_max):
        reasons.append(f"GC content {gc_pct:.1f}% outside standard biophysical range ({gc_min:.0f}-{gc_max:.0f}%)")

    tier = "FAIL_ORACLE" if reasons else "PROXY_PASS"
    return {
        "tier": tier,
        "reasons": reasons,
        "target_peptide": target_peptide,
        "translated_peptide": clean_translated,
        "gc_content_pct": round(gc_pct, 1),
        "mechanism_classification": "THEORETICAL_DECODING_ONLY",
    }
