#!/usr/bin/env python3
"""Build us_ipforce_monolith.py from v2 base + AEGIS mathematical models v4."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "us_ip_force_monolith_v2.py"
MODELS = ROOT / "us_ipforce_mathematical_models.py"
OMEGA = ROOT / "us_ipforce_abd_maximize.py"
OUT = ROOT / "us_ipforce_monolith.py"

INSERT_MARKER = "class AEGISAdvancedForensicPipeline:"
ABD_IMPORT = "from us_ipforce_abd_maximize import ABDMaximizeIntegration"


def patch_metadata(text: str) -> str:
    replacements = [
        (
            'from typing import Any, Dict, List, Optional, Tuple',
            'from typing import Any, Dict, List, Optional, Set, Tuple',
        ),
        (
            "IP FORCE – MONOLITHIC EXECUTION SYSTEM v2026.07.07-ULTIMA-GENESIS",
            "IP FORCE MONOLITH – FULLY SELF-CONTAINED CONSOLIDATION v2026.07.11",
        ),
        (
            'VERSION = "v2026.07.07-ULTIMA-GENESIS"',
            'VERSION = "v2026.07.11-OMEGA-AEGIS-V9-CONSOLIDATED"',
        ),
        (
            'CASE_ID = "IP-FORCE-20260702-ULTIMA-GENESIS-FINAL"',
            'CASE_ID = "IP-FORCE-20260711-OMEGA-AEGIS-V9-FINAL"',
        ),
        (
            'OMEGA_AEGIS_RELEASE = "v2026.06.20-RELEASE"',
            'OMEGA_AEGIS_RELEASE = "v9.0.0-2026.07.11-CONSOLIDATED"',
        ),
        (
            '    floor = datetime(2026, 7, 7, tzinfo=timezone.utc).date()',
            '    floor = datetime(2026, 7, 11, tzinfo=timezone.utc).date()',
        ),
        (
            '    """Temporal scope floor 2026-07-07 through current UTC date (whichever is later)."""',
            '    """Temporal scope floor 2026-07-11 through current UTC date (whichever is later)."""',
        ),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def inline_abd_integration(text: str) -> str:
    if ABD_IMPORT not in text and "ABDMaximizeIntegration inlined" in text:
        return text
    omega_text = OMEGA.read_text(encoding="utf-8")
    evidence_match = re.search(
        r"(# Evidence classes.*?class ABDMaximizeIntegration:.*?)(?=\nasync def main\(\):)",
        omega_text,
        re.DOTALL,
    )
    if not evidence_match:
        raise RuntimeError("Could not extract ABD block from us_ipforce_abd_maximize.py")
    abd_full = evidence_match.group(1).strip()
    abd_full = abd_full.replace("@dataclasses.dataclass", "@dataclass")
    abd_full = re.sub(r"^from __future__ import annotations\n", "", abd_full, flags=re.MULTILINE)

    abd_preamble = '''
ABD_MAXIMIZE_RELEASE = "v18.2-IRAN-WAR-ESCALATION"
COMPLETENESS_THRESHOLD = 99.99
SEED_PATENT = {
    "country": "CZ",
    "number": "283061",
    "title": "Caffeine Vaporizer",
    "priority_date": "1997-03-15",
    "inventor": "Brent Michael Škoda",
    "us_patent": "US-5618592-A",
}
try:
    from httpx import AsyncClient as _HttpxAsyncClient
    AsyncClient = _HttpxAsyncClient
except ImportError:
    AsyncClient = None  # type: ignore

'''
    abd_section = f"""
# =============================================================================
# INLINED IP FORCE (ABD MAXIMIZE) – SELF-CONTAINED v9
# =============================================================================
{abd_preamble}
{abd_full}


"""
    if ABD_IMPORT in text:
        text = text.replace(
            ABD_IMPORT,
            "# ABDMaximizeIntegration inlined below (self-contained v9 monolith)",
        )
    if "INLINED IP FORCE" not in text:
        text = text.replace(
            "\nasync def main() -> None:",
            abd_section + "\nasync def main() -> None:",
            1,
        )
    else:
        # Replace existing inlined block
        start = text.find("# INLINED IP FORCE")
        end = text.find("\nasync def main() -> None:")
        if start != -1 and end != -1:
            text = text[:start] + abd_section.strip() + text[end:]
    return text


def insert_mathematical_models(text: str) -> str:
    if INSERT_MARKER not in text:
        raise RuntimeError(f"Insert marker not found: {INSERT_MARKER}")
    if "class SyntheticIdentityMapper:" in text:
        return text
    models = MODELS.read_text(encoding="utf-8")
    models = re.sub(r"^from __future__ import annotations\n", "", models, flags=re.MULTILINE)
    header = (
        "\n# =============================================================================\n"
        "# AEGIS ADVANCED MATHEMATICAL FORENSIC MODELS v4.0.0 (FULL IMPLEMENTATION)\n"
        "# =============================================================================\n\n"
    )
    return text.replace(INSERT_MARKER, header + models + "\n\n" + INSERT_MARKER, 1)


def enhance_aegis_pipeline(text: str) -> str:
    """Wire AEGISAdvancedForensicPipeline to full mathematical model classes."""
    old_run = """    @classmethod
    def run_synthetic_identity_analysis(
        cls, analyzer: "USIPForceAnalyzer"
    ) -> Dict[str, Any]:
        variations = list(cls.CANONICAL_NAME_VARIATIONS)"""

    new_run = """    @classmethod
    def run_synthetic_identity_analysis(
        cls, analyzer: "USIPForceAnalyzer"
    ) -> Dict[str, Any]:
        mapper = SyntheticIdentityMapper()
        base_report = mapper.generate_combinial_report()
        variations = base_report.get("variations", list(cls.CANONICAL_NAME_VARIATIONS))"""

    if old_run in text:
        text = text.replace(old_run, new_run, 1)

    # Append integration at end of run_synthetic_identity_analysis return
    old_return = """        return {
            "target_name": VICTIM_UBO,
            "variation_count": len(variations),
            "variations": variations,
            "synthetic_identities_detected": flagged[:100],
            "patent_name_overlap": len(seen_names),
            "report_hash": det_hmac_sha3_512("aegis_identity", len(flagged), CASE_ID),
        }"""

    new_return = """        patent_records = [
            {
                "applicant": (p.inventors + p.assignees)[0] if (p.inventors + p.assignees) else "",
                "patent_id": p.patent_id,
                "jurisdiction": p.jurisdiction,
                "filing_date": p.filing_date or "",
            }
            for p in analyzer.patents[:500]
            if p.inventors or p.assignees
        ]
        synthetic_from_mapper = mapper.detect_synthetic_identities(patent_records)
        flagged.extend(synthetic_from_mapper[:50])
        return {
            "target_name": VICTIM_UBO,
            "variation_count": len(variations),
            "variations": variations,
            "identity_graph": base_report.get("identity_graph", {}),
            "cross_jurisdictional": base_report.get("cross_jurisdictional_analysis", {}),
            "synthetic_identities_detected": flagged[:100],
            "patent_name_overlap": len(seen_names),
            "report_hash": det_hmac_sha3_512("aegis_identity", len(flagged), CASE_ID),
        }"""

    if old_return in text:
        text = text.replace(old_return, new_return, 1)

    old_spatio = """    @classmethod
    def run_spatio_temporal_analysis(
        cls, events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        jurisdictions: Dict[str, int] = {}"""

    new_spatio = """    @classmethod
    def run_spatio_temporal_analysis(
        cls, events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        bst = BayesianSpatioTemporalModel(prior_model="gamma")
        bst.fit(events)
        prob_map = bst.generate_probability_map()
        anomalies = bst.detect_anomalous_patterns(events)
        jurisdictions: Dict[str, int] = {}"""

    if old_spatio in text:
        text = text.replace(old_spatio, new_spatio, 1)

    old_spatio_return = """        return {
            "events_analyzed": len(events),
            "entities_analyzed": len(entities),
            "jurisdiction_probs": jurisdiction_probs,
            "top_risk_jurisdiction": top_jurisdiction,
            "anomaly_count": sum(1 for c in jurisdictions.values() if c == 1),
            "report_hash": det_hmac_sha3_512("aegis_spatio", len(events), CASE_ID),
        }"""

    new_spatio_return = """        return {
            "events_analyzed": len(events),
            "entities_analyzed": len(entities),
            "jurisdiction_probs": jurisdiction_probs,
            "probability_map": prob_map,
            "anomalies": anomalies[:50],
            "top_risk_jurisdiction": top_jurisdiction,
            "anomaly_count": len(anomalies),
            "report_hash": det_hmac_sha3_512("aegis_spatio", len(events), CASE_ID),
        }"""

    if old_spatio_return in text:
        text = text.replace(old_spatio_return, new_spatio_return, 1)

    old_chaos = """    @classmethod
    def run_chaotic_analysis(cls, analyzer: "USIPForceAnalyzer") -> Dict[str, Any]:
        timestamps = [
            tx_timestamp_float(tx) for tx in analyzer.transactions[:500]
        ]
        values = [
            float(getattr(tx, "value", 0) or 0) for tx in analyzer.transactions[:500]
        ]
        series = values if values else timestamps
        if not series:
            series = [float(BIS_DERIVATIVES_USD) / 1e15]
        fractal_dim = FractalGeometryEngine.compute_fractal_dimension(
            series, max_order=NINTH_ORDER_REGRESSION_DEPTH
        )
        frac_engine = FractionalCalculusEngine()
        frac_deriv = frac_engine.fractional_derivative(series[:120], 0.5)
        frac_anomaly = frac_engine.fractional_speed_of_light_anomaly(timestamps[:120])
        return {
            "fractal_dimension": fractal_dim,
            "fractional_anomaly_score": round(frac_anomaly, 8),
            "series_length": len(series),
            "ninth_order_depth": NINTH_ORDER_REGRESSION_DEPTH,
            "fractional_derivative_preview": frac_deriv[:10],
            "report_hash": det_hmac_sha3_512("aegis_chaos", fractal_dim, CASE_ID),
        }"""

    new_chaos = """    @classmethod
    def run_chaotic_analysis(cls, analyzer: "USIPForceAnalyzer") -> Dict[str, Any]:
        timestamps = [
            tx_timestamp_float(tx) for tx in analyzer.transactions[:500]
        ]
        values = [
            float(getattr(tx, "value", 0) or 0) for tx in analyzer.transactions[:500]
        ]
        series = np.asarray(values if values else timestamps, dtype=np.float64)
        if series.size == 0:
            series = np.array([float(BIS_DERIVATIVES_USD) / 1e15], dtype=np.float64)
        chaos_engine = AEGISFractionalCalculusEngine()
        chaos = chaos_engine.detect_chaos(series)
        fractal = chaos_engine.fractal_dimension(series)
        hurst = chaos_engine.hurst_exponent(series)
        fractal_dim = FractalGeometryEngine.compute_fractal_dimension(
            series.tolist(), max_order=NINTH_ORDER_REGRESSION_DEPTH
        )
        return {
            "chaos_detection": chaos,
            "fractal_dimensions": fractal,
            "hurst_exponent": hurst,
            "fractal_dimension": fractal_dim,
            "series_length": int(series.size),
            "ninth_order_depth": NINTH_ORDER_REGRESSION_DEPTH,
            "report_hash": det_hmac_sha3_512("aegis_chaos", fractal_dim, CASE_ID),
        }"""

    if old_chaos in text:
        text = text.replace(old_chaos, new_chaos, 1)

    old_topo = """    @classmethod
    def run_topological_analysis(cls, network: Dict[str, Any]) -> Dict[str, Any]:
        nodes = network.get("nodes", [])
        edges = network.get("edges", [])
        n_nodes = len(nodes)
        n_edges = len(edges)
        density = n_edges / max(n_nodes * (n_nodes - 1) / 2, 1)
        return {
            "num_nodes": n_nodes,
            "num_edges": n_edges,
            "density": round(density, 6),
            "technology_domains": len(set(network.get("technology_domains", []))),
            "report_hash": det_hmac_sha3_512("aegis_topo", n_nodes, n_edges, CASE_ID),
        }"""

    new_topo = """    @classmethod
    def run_topological_analysis(cls, network: Dict[str, Any]) -> Dict[str, Any]:
        topo = TopologicalExpansionAnalyzer()
        nodes = network.get("nodes", [])
        edges = network.get("edges", [])
        graph = {"nodes": nodes, "edges": edges}
        entity_names = [n["id"] if isinstance(n, dict) else str(n) for n in nodes]
        relationships = network.get("relationships", [])
        if not relationships and edges:
            relationships = [
                {"members": [e["source"], e["target"]], "relation_type": "edge", "weight": e.get("weight", 1.0)}
                for e in edges
            ]
        hypergraph = topo.build_hypergraph(entity_names, relationships)
        persistence = topo.compute_persistence_homology(graph)
        betti = topo.betti_numbers(graph)
        motifs = topo.detect_network_motifs(graph)
        non_spatial = topo.non_spatial_expansion(network.get("technology_domains", []))
        n_nodes = len(nodes)
        n_edges = len(edges)
        density = n_edges / max(n_nodes * (n_nodes - 1) / 2, 1)
        return {
            "num_nodes": n_nodes,
            "num_edges": n_edges,
            "density": round(density, 6),
            "hypergraph_metrics": hypergraph.get("metrics", {}),
            "persistence_homology": {"betti_numbers": betti, "pairs": len(persistence.get("persistence_diagram", []))},
            "motifs": motifs[:20],
            "non_spatial_expansion": non_spatial,
            "technology_domains": len(set(network.get("technology_domains", []))),
            "report_hash": det_hmac_sha3_512("aegis_topo", n_nodes, n_edges, CASE_ID),
        }"""

    if old_topo in text:
        text = text.replace(old_topo, new_topo, 1)

    old_cds = """    @classmethod
    def run_cds_forensics(
        cls, bis_report: Dict[str, Any]
    ) -> Dict[str, Any]:
        raw_bis = bis_report.get("scale", {}).get(
            "bis_derivatives_usd", str(BIS_DERIVATIVES_USD)
        )
        if isinstance(raw_bis, str):
            raw_bis = raw_bis.replace("$", "").replace(",", "")
        try:
            bis_notional = float(raw_bis)
        except (TypeError, ValueError):
            bis_notional = float(BIS_DERIVATIVES_USD)
        non_bis = float(NON_BIS_SHADOW_USD)
        return {
            "cds_market_notional": cls.CDS_MARKET_NOTIONAL,
            "bis_derivatives_usd": bis_notional,
            "non_bis_shadow_usd": non_bis,
            "combined_systemic_risk_usd": bis_notional + non_bis,
            "instrument_cross_links": bis_report.get("instrument_linkage", {}).get(
                "total_cross_links", 0
            ),
            "ninth_order_complete": bis_report.get("ninth_order_regression", {}).get(
                "orders_computed"
            )
            == NINTH_ORDER_REGRESSION_DEPTH,
            "report_hash": det_hmac_sha3_512("aegis_cds", bis_notional, CASE_ID),
        }"""

    new_cds = """    @classmethod
    def run_cds_forensics(
        cls, bis_report: Dict[str, Any]
    ) -> Dict[str, Any]:
        cds = CDSForensicsEngine()
        bis_report_cds = cds.generate_bis_report()
        stress = {
            sc: cds.stress_test_scenario(sc)
            for sc in ("baseline", "ip_theft_cascade", "systemic_crisis")
        }
        raw_bis = bis_report.get("scale", {}).get(
            "bis_derivatives_usd", str(BIS_DERIVATIVES_USD)
        )
        if isinstance(raw_bis, str):
            raw_bis = raw_bis.replace("$", "").replace(",", "")
        try:
            bis_notional = float(raw_bis)
        except (TypeError, ValueError):
            bis_notional = float(BIS_DERIVATIVES_USD)
        non_bis = float(NON_BIS_SHADOW_USD)
        return {
            "cds_market_notional": cds.calculate_cds_notional_exposure(),
            "bis_derivatives_report": bis_report_cds,
            "stress_tests": stress,
            "bis_derivatives_usd": bis_notional,
            "non_bis_shadow_usd": non_bis,
            "combined_systemic_risk_usd": bis_notional + non_bis,
            "instrument_cross_links": bis_report.get("instrument_linkage", {}).get(
                "total_cross_links", 0
            ),
            "ninth_order_complete": bis_report.get("ninth_order_regression", {}).get(
                "orders_computed"
            )
            == NINTH_ORDER_REGRESSION_DEPTH,
            "report_hash": det_hmac_sha3_512("aegis_cds", bis_notional, CASE_ID),
        }"""

    if old_cds in text:
        text = text.replace(old_cds, new_cds, 1)

    return text


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"Missing source: {SRC}")
    if not MODELS.exists():
        raise SystemExit(f"Missing models: {MODELS}")

    text = SRC.read_text(encoding="utf-8")
    text = patch_metadata(text)
    text = insert_mathematical_models(text)
    text = enhance_aegis_pipeline(text)
    text = inline_abd_integration(text)

    doc_addition = (
        "\nSELF-CONTAINED: This file consolidates us_ip_force_monolith_v2.py, "
        "us_ipforce_abd_maximize.py, and AEGIS Advanced Mathematical Forensic Models v4.0.0.\n"
        "Run: python3 us_ipforce_monolith.py\n"
    )
    if "SELF-CONTAINED:" not in text:
        text = text.replace('"""', '"""' + doc_addition, 1)

    OUT.write_text(text, encoding="utf-8")
    print(f"Built {OUT} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
