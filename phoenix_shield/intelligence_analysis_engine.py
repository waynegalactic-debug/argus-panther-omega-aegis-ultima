"""
IntelligenceAnalysisEngine — Operation Phoenix Shield
US Treasury-grade forensic intelligence analysis platform.

Provides advanced analytics for intelligence analysis including:
- Weighted scoring for target prioritization
- Multi-criteria decision analysis (AHP, TOPSIS, PROMETHEE, ELECTRE)
- Pattern recognition across evidence (temporal, network, geographic, sequential)
- Automated intelligence brief generation
- Correlation and link analysis

All algorithms are implemented using real mathematical foundations
with deterministic, reproducible results.

Standards: PEP8, full type hints, comprehensive docstrings.
Dependencies: Python standard library only.
"""

from __future__ import annotations

import math
import random
import statistics
import itertools
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


class IntelligenceAnalysisEngine:
    """Advanced intelligence analysis: weighted scoring, MCDA, pattern recognition.

    This engine provides prosecutors and intelligence analysts with
    quantitative tools to prioritize targets, evaluate evidence quality,
    select optimal prosecution strategies, and detect patterns across
    complex multi-source intelligence datasets.

    Attributes:
        config (dict): Engine configuration with scoring weights and thresholds.
        default_weights (dict): Default criteria weights for target scoring.
        scoring_thresholds (dict): Thresholds for scoring categories.
        random_seed (int): Seed for reproducible stochastic methods.
    """

    # ------------------------------------------------------------------ #
    # 1. INITIALISATION
    # ------------------------------------------------------------------ #
    def __init__(self, config: Optional[dict] = None) -> None:
        """Initialize the IntelligenceAnalysisEngine.

        Args:
            config: Optional configuration dictionary to override defaults.
        """
        self.config = config or {}
        self.default_weights = {
            "financial_impact": 0.25,
            "criminal_severity": 0.25,
            "jurisdiction": 0.15,
            "evidence_strength": 0.15,
            "public_interest": 0.10,
            "resource_required": 0.10,
        }
        # Override with user config if provided
        if "weights" in self.config:
            self.default_weights.update(self.config["weights"])

        self.scoring_thresholds = {
            "low": 0.33,
            "medium": 0.66,
            "high": 1.00,
        }
        if "thresholds" in self.config:
            self.scoring_thresholds.update(self.config["thresholds"])

        # Reproducibility seed
        self.random_seed = self.config.get("random_seed", 42)
        random.seed(self.random_seed)

    # ------------------------------------------------------------------ #
    # RESPONSE HELPER
    # ------------------------------------------------------------------ #
    @staticmethod
    def _make_response(
        success: bool,
        data: Any,
        error: str = "",
        confidence: float = 0.0,
    ) -> dict:
        """Generate a standardized response dictionary.

        Args:
            success: Whether the operation succeeded.
            data: The payload data.
            error: Error message if success is False.
            confidence: Confidence score in [0.0, 1.0].

        Returns:
            Standardised response dict.
        """
        return {
            "success": success,
            "data": data,
            "source": "IntelligenceAnalysisEngine",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "error": error,
            "confidence": confidence,
        }

    # =====================================================================
    # SECTION A — WEIGHTED SCORING
    # =====================================================================

    # ------------------------------------------------------------------ #
    # 1. score_target_priority
    # ------------------------------------------------------------------ #
    def score_target_priority(
        self,
        target: dict,
        criteria: Optional[dict] = None,
    ) -> dict:
        """Multi-criteria weighted score for target prioritisation.

        Computes a composite priority score using six weighted dimensions:
        financial impact, criminal severity, jurisdiction accessibility,
        evidence strength, public interest, and resource requirement.

        Each dimension is normalised to [0, 1] and combined via weighted
        sum. The result includes a priority tier (low / medium / high /
        critical) and per-dimension breakdown.

        Args:
            target: Dictionary describing the target. Expected keys:
                - financial_impact (float): Estimated monetary impact.
                - criminal_severity (float): Severity rating 0-10.
                - jurisdiction_score (float): Accessibility 0-10.
                - evidence_strength (float): Evidence quality 0-10.
                - public_interest (float): Public interest 0-10.
                - resource_required (float): Resource burden 0-10.
            criteria: Optional dict of criteria_name -> weight overrides.

        Returns:
            Response dict with composite score, tier, and breakdown.
        """
        try:
            weights = criteria if criteria else self.default_weights

            # Normalise each dimension to [0, 1]
            def _norm(key: str, max_val: float = 10.0) -> float:
                raw = target.get(key, 0.0)
                if isinstance(raw, (int, float)):
                    return min(max(float(raw) / max_val, 0.0), 1.0)
                return 0.0

            dimensions = {
                "financial_impact": _norm("financial_impact", max(
                    target.get("financial_impact", 1.0), 1.0,
                )),
                "criminal_severity": _norm("criminal_severity"),
                "jurisdiction": _norm("jurisdiction_score"),
                "evidence_strength": _norm("evidence_strength"),
                "public_interest": _norm("public_interest"),
                "resource_required": 1.0 - _norm(
                    "resource_required",
                ),  # invert: lower burden = higher score
            }

            # Weighted composite score
            total_weight = sum(weights.get(k, 0.0) for k in dimensions)
            if total_weight == 0.0:
                return self._make_response(
                    False, {}, "No valid weights provided.", 0.0,
                )

            composite = sum(
                dimensions[k] * weights.get(k, 0.0)
                for k in dimensions
            ) / total_weight

            # Determine tier
            if composite >= 0.85:
                tier = "critical"
            elif composite >= 0.65:
                tier = "high"
            elif composite >= 0.40:
                tier = "medium"
            else:
                tier = "low"

            # Confidence based on data completeness
            provided = sum(
                1 for k in dimensions if target.get(
                    k if k != "jurisdiction" else "jurisdiction_score",
                ) is not None
            )
            confidence = provided / len(dimensions)

            data = {
                "composite_score": round(composite, 4),
                "priority_tier": tier,
                "dimension_scores": {
                    k: round(v, 4) for k, v in dimensions.items()
                },
                "weight_applied": weights,
            }
            return self._make_response(True, data, "", round(confidence, 4))

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    # ------------------------------------------------------------------ #
    # 2. score_ip_theft_severity
    # ------------------------------------------------------------------ #
    def score_ip_theft_severity(
        self,
        patent_data: dict,
        usage_data: dict,
    ) -> dict:
        """Score intellectual property theft severity.

        Evaluates IP theft along four dimensions:
        - Patent portfolio value (claim count, family size, citation impact)
        - Misappropriation scope (units sold, revenue diverted, markets)
        - Willfulness indicators (deliberate copying, concealment)
        - Remedial difficulty (ability to undo harm)

        Args:
            patent_data: Dict with keys like claim_count, family_size,
                         citation_count, patent_value.
            usage_data: Dict with units_diverted, revenue_diverted,
                        markets_affected, willful_flags, concealment_efforts.

        Returns:
            Response dict with IP theft severity score and tier.
        """
        try:
            # Patent portfolio value score [0, 1]
            claims = max(patent_data.get("claim_count", 0), 0)
            family = max(patent_data.get("family_size", 1), 1)
            citations = max(patent_data.get("citation_count", 0), 0)
            patent_value = patent_data.get("patent_value", 0.0)

            claim_score = min(claims / 50.0, 1.0)  # 50 claims = max
            family_score = min(math.log2(family + 1) / 5.0, 1.0)
            citation_score = min(math.log10(citations + 1) / 3.0, 1.0)
            value_score = min(patent_value / 1e8, 1.0) if patent_value else 0.0

            patent_score = statistics.mean([
                claim_score, family_score, citation_score, value_score,
            ])

            # Misappropriation scope [0, 1]
            units = usage_data.get("units_diverted", 0)
            revenue = usage_data.get("revenue_diverted", 0.0)
            markets = usage_data.get("markets_affected", 0)

            unit_score = min(math.log10(units + 1) / 6.0, 1.0)
            revenue_score = min(revenue / 1e8, 1.0)
            market_score = min(markets / 20.0, 1.0)

            misapp_score = statistics.mean([
                unit_score, revenue_score, market_score,
            ])

            # Willfulness [0, 1]
            willful_flags = usage_data.get("willful_flags", 0)
            concealment = usage_data.get("concealment_efforts", 0)
            willful_score = min((willful_flags + concealment) / 8.0, 1.0)

            # Remedial difficulty [0, 1] — higher = harder to remedy = worse
            remedy_score = 1.0 - min(
                usage_data.get("remedy_feasibility", 5) / 10.0, 1.0,
            )

            # Composite: weights per IP prosecution guidelines
            composite = (
                0.30 * patent_score +
                0.35 * misapp_score +
                0.25 * willful_score +
                0.10 * remedy_score
            )

            tier = (
                "critical" if composite >= 0.80 else
                "high" if composite >= 0.60 else
                "medium" if composite >= 0.35 else "low"
            )

            data = {
                "severity_score": round(composite, 4),
                "severity_tier": tier,
                "patent_portfolio_score": round(patent_score, 4),
                "misappropriation_score": round(misapp_score, 4),
                "willfulness_score": round(willful_score, 4),
                "remedial_difficulty": round(remedy_score, 4),
                "estimated_damages": round(
                    revenue * (1.0 + willful_score), 2,
                ),  # treble damage proxy
            }
            return self._make_response(True, data, "", round(composite, 4))

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    # ------------------------------------------------------------------ #
    # 3. score_money_laundering_risk
    # ------------------------------------------------------------------ #
    def score_money_laundering_risk(
        self,
        transaction_data: dict,
    ) -> dict:
        """Score money laundering risk using AML-type heuristics.

        Evaluates transaction patterns against known ML indicators:
        - Structuring (frequency, amount just below thresholds)
        - Layering complexity (hops, jurisdictions, entity types)
        - Velocity anomalies (rapid movement)
        - Geographic risk (high-risk jurisdictions)
        - Entity opacity (shell companies, trusts)

        Args:
            transaction_data: Dict with:
                transactions (list of dicts), geographic_risk_score,
                entity_opacity_score, known_suspicious_flags.

        Returns:
            Response dict with ML risk score, tier, and indicator flags.
        """
        try:
            transactions = transaction_data.get("transactions", [])
            geo_risk = min(
                transaction_data.get("geographic_risk_score", 5) / 10.0, 1.0,
            )
            opacity = min(
                transaction_data.get("entity_opacity_score", 5) / 10.0, 1.0,
            )
            flags = transaction_data.get("known_suspicious_flags", 0)

            # Velocity analysis
            amounts = [t.get("amount", 0.0) for t in transactions]
            n_tx = len(amounts)
            if n_tx == 0:
                return self._make_response(
                    False, {}, "No transaction data provided.", 0.0,
                )

            total_volume = sum(amounts)
            avg_amount = statistics.mean(amounts) if amounts else 0

            # Structuring detection: frequency of amounts just below 10k
            structuring_count = sum(
                1 for a in amounts if 9000 <= a < 10000
            )
            structuring_ratio = structuring_count / n_tx if n_tx else 0
            structuring_score = min(structuring_ratio * 5.0, 1.0)

            # Velocity score: coefficient of variation
            if amounts and len(amounts) > 1:
                cv = statistics.stdev(amounts) / avg_amount if avg_amount else 0
            else:
                cv = 0.0
            velocity_score = min(cv / 3.0, 1.0)

            # Layering complexity
            unique_entities = len(set(
                t.get("entity_id", "") for t in transactions
            ))
            layering_score = min(unique_entities / 15.0, 1.0)

            # Composite risk score
            composite = (
                0.25 * structuring_score +
                0.20 * velocity_score +
                0.20 * layering_score +
                0.20 * geo_risk +
                0.15 * opacity
            )

            # Boost if known suspicious flags present
            composite = min(composite + (flags * 0.05), 1.0)

            tier = (
                "critical" if composite >= 0.80 else
                "high" if composite >= 0.60 else
                "medium" if composite >= 0.35 else "low"
            )

            data = {
                "ml_risk_score": round(composite, 4),
                "risk_tier": tier,
                "structuring_score": round(structuring_score, 4),
                "velocity_score": round(velocity_score, 4),
                "layering_score": round(layering_score, 4),
                "geographic_risk": round(geo_risk, 4),
                "entity_opacity": round(opacity, 4),
                "transaction_count": n_tx,
                "total_volume": round(total_volume, 2),
                "suspicious_indicators": flags,
            }
            return self._make_response(True, data, "", round(composite, 4))

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    # ------------------------------------------------------------------ #
    # 4. score_rico_predicate_strength
    # ------------------------------------------------------------------ #
    def score_rico_predicate_strength(
        self,
        evidence: dict,
    ) -> dict:
        """Score RICO predicate act strength.

        Evaluates whether evidence supports RICO predicate acts under
        18 U.S.C. § 1961(1). Scores along:
        - Predicate act count and variety
        - Pattern requirement (relatedness + continuity)
        - Enterprise nexus
        - Interstate commerce connection

        Args:
            evidence: Dict with predicate_acts (list), enterprise_evidence,
                      interstate_commerce_evidence, relatedness_score,
                      continuity_months.

        Returns:
            Response dict with RICO strength score and analysis.
        """
        try:
            predicate_acts = evidence.get("predicate_acts", [])
            n_predicates = len(predicate_acts)

            if n_predicates == 0:
                return self._make_response(
                    False, {}, "No predicate acts provided.", 0.0,
                )

            # Variety of predicate types
            unique_types = len(set(
                act.get("type", "unknown") for act in predicate_acts
            ))
            variety_score = min(unique_types / 5.0, 1.0)

            # Quantity score
            quantity_score = min(n_predicates / 10.0, 1.0)

            # Pattern: relatedness + continuity
            relatedness = min(
                evidence.get("relatedness_score", 5) / 10.0, 1.0,
            )
            continuity_months = evidence.get("continuity_months", 0)
            # Closed-ended continuity: > 1 year = strong
            continuity_score = min(continuity_months / 12.0, 1.0)
            pattern_score = (relatedness + continuity_score) / 2.0

            # Enterprise nexus
            enterprise = min(
                evidence.get("enterprise_evidence", 5) / 10.0, 1.0,
            )

            # Interstate commerce
            interstate = min(
                evidence.get("interstate_commerce_evidence", 5) / 10.0, 1.0,
            )

            # Composite RICO strength
            composite = (
                0.20 * variety_score +
                0.15 * quantity_score +
                0.25 * pattern_score +
                0.25 * enterprise +
                0.15 * interstate
            )

            tier = (
                "strong" if composite >= 0.75 else
                "moderate" if composite >= 0.50 else
                "weak" if composite >= 0.30 else "insufficient"
            )

            data = {
                "rico_strength_score": round(composite, 4),
                "strength_tier": tier,
                "predicate_count": n_predicates,
                "predicate_variety_score": round(variety_score, 4),
                "predicate_quantity_score": round(quantity_score, 4),
                "pattern_score": round(pattern_score, 4),
                "relatedness": round(relatedness, 4),
                "continuity": round(continuity_score, 4),
                "enterprise_nexus": round(enterprise, 4),
                "interstate_commerce": round(interstate, 4),
                "pattern_recommendation": (
                    "Open-ended continuity" if continuity_score < 0.5
                    else "Closed-ended continuity established"
                ),
            }
            return self._make_response(True, data, "", round(composite, 4))

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    # ------------------------------------------------------------------ #
    # 5. score_corporate_complicity
    # ------------------------------------------------------------------ #
    def score_corporate_complicity(
        self,
        entity_data: dict,
    ) -> dict:
        """Score corporate complicity / guilt.

        Evaluates corporate liability indicators:
        - Knowledge (who knew what, when)
        - Benefit (financial gain from misconduct)
        - Control failures (compliance program adequacy)
        - Cover-up (post-discovery conduct)
        - Cooperation (self-disclosure, remediation)

        Args:
            entity_data: Dict with knowledge_score, benefit_score,
                         compliance_deficiency, cover_up_score,
                         cooperation_score, employee_count.

        Returns:
            Response dict with complicity score and DOJ-style assessment.
        """
        try:
            # Knowledge: higher = more executives knew
            knowledge = min(
                entity_data.get("knowledge_score", 5) / 10.0, 1.0,
            )
            # Benefit: higher = more profit from misconduct
            benefit = min(
                entity_data.get("benefit_score", 5) / 10.0, 1.0,
            )
            # Compliance deficiency: higher = weaker controls
            control_fail = min(
                entity_data.get("compliance_deficiency", 5) / 10.0, 1.0,
            )
            # Cover-up: higher = more obstruction
            cover_up = min(
                entity_data.get("cover_up_score", 5) / 10.0, 1.0,
            )
            # Cooperation: invert — higher cooperation = lower complicity
            cooperation = 1.0 - min(
                entity_data.get("cooperation_score", 5) / 10.0, 1.0,
            )

            # DOJ Criminal Division / Fraud Section weighting
            composite = (
                0.25 * knowledge +
                0.20 * benefit +
                0.20 * control_fail +
                0.20 * cover_up +
                0.15 * cooperation
            )

            tier = (
                "willful_and_knowing" if composite >= 0.80 else
                "reckless" if composite >= 0.55 else
                "negligent" if composite >= 0.30 else "minimal"
            )

            # Culpability multiplier (USSG-style)
            culpability = 1.0 + (composite * 2.0)  # 1.0 to 3.0

            data = {
                "complicity_score": round(composite, 4),
                "complicity_tier": tier,
                "knowledge": round(knowledge, 4),
                "benefit": round(benefit, 4),
                "control_failures": round(control_fail, 4),
                "cover_up": round(cover_up, 4),
                "lack_of_cooperation": round(cooperation, 4),
                "culpability_multiplier": round(culpability, 2),
                "monitorship_recommended": composite >= 0.65,
            }
            return self._make_response(True, data, "", round(composite, 4))

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    # ------------------------------------------------------------------ #
    # 6. score_jurisdiction_favorability
    # ------------------------------------------------------------------ #
    def score_jurisdiction_favorability(
        self,
        jurisdictions: list,
    ) -> dict:
        """Analyse and rank jurisdiction favorability for prosecution.

        Scores each venue on:
        - Statutory framework strength (extraterritorial reach)
        - Precedent quality (prior successful prosecutions)
        - Evidence accessibility (discovery, mutual legal assistance)
        - Speed to trial (case backlog)
        - Sentencing severity
        - Asset recovery mechanisms

        Args:
            jurisdictions: List of dicts, each with the above fields.

        Returns:
            Response dict with ranked jurisdictions and recommendation.
        """
        try:
            if not jurisdictions:
                return self._make_response(
                    False, {}, "No jurisdictions provided.", 0.0,
                )

            scored = []
            for j in jurisdictions:
                statutory = min(j.get("statutory_strength", 5) / 10.0, 1.0)
                precedent = min(j.get("precedent_quality", 5) / 10.0, 1.0)
                evidence_access = min(
                    j.get("evidence_accessibility", 5) / 10.0, 1.0,
                )
                speed = min(j.get("speed_to_trial", 5) / 10.0, 1.0)
                sentencing = min(j.get("sentencing_severity", 5) / 10.0, 1.0)
                asset_recovery = min(
                    j.get("asset_recovery", 5) / 10.0, 1.0,
                )

                # Venue shopping score — prosecutors want strong law,
                # good precedent, accessible evidence, fast trials,
                # harsh sentences, and asset recovery
                score = (
                    0.20 * statutory +
                    0.20 * precedent +
                    0.20 * evidence_access +
                    0.10 * speed +
                    0.15 * sentencing +
                    0.15 * asset_recovery
                )

                scored.append({
                    "jurisdiction": j.get("name", "unknown"),
                    "score": round(score, 4),
                    "statutory": round(statutory, 4),
                    "precedent": round(precedent, 4),
                    "evidence_access": round(evidence_access, 4),
                    "speed": round(speed, 4),
                    "sentencing": round(sentencing, 4),
                    "asset_recovery": round(asset_recovery, 4),
                })

            scored.sort(key=lambda x: x["score"], reverse=True)

            data = {
                "ranked_jurisdictions": scored,
                "recommended_venue": scored[0]["jurisdiction"] if scored else None,
                "venue_score": scored[0]["score"] if scored else 0.0,
                "analysis": (
                    f"{scored[0]['jurisdiction']} is optimal with score "
                    f"{scored[0]['score']}."
                    if scored else "No venues scored."
                ),
            }
            return self._make_response(True, data, "", round(
                scored[0]["score"] if scored else 0.0, 4,
            ))

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    # ------------------------------------------------------------------ #
    # 7. score_evidence_quality
    # ------------------------------------------------------------------ #
    def score_evidence_quality(
        self,
        evidence: dict,
    ) -> dict:
        """Score evidence quality against Federal Rules of Evidence.

        Evaluates:
        - Relevance (FRE 401/403)
        - Authenticity (FRE 901)
        - Hearsay exceptions (FRE 801-807)
        - Chain of custody integrity
        - Corroboration level
        - Admissibility probability

        Args:
            evidence: Dict with relevance_score, authenticity_score,
                      hearsay_fallibility, chain_of_custody_score,
                      corroboration_count, source_reliability.

        Returns:
            Response dict with FRE-compliant evidence quality score.
        """
        try:
            relevance = min(
                evidence.get("relevance_score", 5) / 10.0, 1.0,
            )
            authenticity = min(
                evidence.get("authenticity_score", 5) / 10.0, 1.0,
            )
            # hearsay_fallibility: lower = more reliable exception
            hearsay_raw = evidence.get("hearsay_fallibility", 5)
            hearsay = 1.0 - min(hearsay_raw / 10.0, 1.0)
            custody = min(
                evidence.get("chain_of_custody_score", 5) / 10.0, 1.0,
            )
            corroboration = min(
                evidence.get("corroboration_count", 0) / 5.0, 1.0,
            )
            source_rel = min(
                evidence.get("source_reliability", 5) / 10.0, 1.0,
            )

            # Weighted per FRE priority
            composite = (
                0.25 * relevance +
                0.20 * authenticity +
                0.15 * hearsay +
                0.15 * custody +
                0.15 * corroboration +
                0.10 * source_rel
            )

            # Admissibility estimate
            admissible = composite >= 0.60

            tier = (
                "excellent" if composite >= 0.85 else
                "good" if composite >= 0.70 else
                "adequate" if composite >= 0.50 else
                "questionable" if composite >= 0.30 else "inadmissible"
            )

            data = {
                "evidence_quality_score": round(composite, 4),
                "quality_tier": tier,
                "likely_admissible": admissible,
                "relevance": round(relevance, 4),
                "authenticity": round(authenticity, 4),
                "hearsay_reliability": round(hearsay, 4),
                "chain_of_custody": round(custody, 4),
                "corroboration": round(corroboration, 4),
                "source_reliability": round(source_rel, 4),
                "fre_analysis": (
                    f"Evidence meets FRE standards for admission."
                    if admissible
                    else f"Evidence has admissibility risks under FRE."
                ),
            }
            return self._make_response(True, data, "", round(composite, 4))

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    # ------------------------------------------------------------------ #
    # 8. score_witness_credibility
    # ------------------------------------------------------------------ #
    def score_witness_credibility(
        self,
        witness: dict,
    ) -> dict:
        """Score witness credibility for trial preparation.

        Evaluates:
        - Demeanor (presentation consistency)
        - Corroboration (supporting evidence)
        - Bias (financial, personal interest)
        - Prior inconsistent statements
        - Expertise / qualification
        - Memory reliability (time elapsed)

        Args:
            witness: Dict with demeanor_score, corroboration_count,
                     bias_indicators, prior_inconsistencies,
                     expertise_level, months_since_observation.

        Returns:
            Response dict with credibility score and vulnerability analysis.
        """
        try:
            demeanor = min(witness.get("demeanor_score", 5) / 10.0, 1.0)
            corroboration = min(
                witness.get("corroboration_count", 0) / 5.0, 1.0,
            )
            # Bias: higher raw = more bias, so invert
            bias_raw = witness.get("bias_indicators", 0)
            bias = 1.0 - min(bias_raw / 10.0, 1.0)
            # Inconsistencies: more = less credible
            inconsistency_raw = witness.get("prior_inconsistencies", 0)
            consistency = 1.0 - min(inconsistency_raw / 5.0, 1.0)
            expertise = min(
                witness.get("expertise_level", 5) / 10.0, 1.0,
            )
            # Memory decay: more months = less reliable
            months = witness.get("months_since_observation", 0)
            memory = max(1.0 - (months / 60.0), 0.0)  # 5 years = floor

            composite = (
                0.20 * demeanor +
                0.20 * corroboration +
                0.20 * bias +
                0.15 * consistency +
                0.15 * expertise +
                0.10 * memory
            )

            tier = (
                "highly_credible" if composite >= 0.80 else
                "credible" if composite >= 0.60 else
                "moderate" if composite >= 0.40 else
                "questionable" if composite >= 0.25 else "not_credible"
            )

            # Cross-examination vulnerabilities
            vulnerabilities = []
            if bias_raw > 3:
                vulnerabilities.append("Bias impeachment risk")
            if inconsistency_raw > 1:
                vulnerabilities.append("Prior inconsistent statements")
            if months > 24:
                vulnerabilities.append("Memory degradation")
            if corroboration < 0.3:
                vulnerabilities.append("Lacks corroboration")

            data = {
                "credibility_score": round(composite, 4),
                "credibility_tier": tier,
                "demeanor": round(demeanor, 4),
                "corroboration": round(corroboration, 4),
                "lack_of_bias": round(bias, 4),
                "consistency": round(consistency, 4),
                "expertise": round(expertise, 4),
                "memory_reliability": round(memory, 4),
                "cross_exam_vulnerabilities": vulnerabilities,
                "recommended_use": (
                    "Lead witness" if composite >= 0.75 else
                    "Corroborating witness" if composite >= 0.50 else
                    "Reserve / backup"
                ),
            }
            return self._make_response(True, data, "", round(composite, 4))

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)


    # =====================================================================
    # SECTION B — MULTI-CRITERIA DECISION ANALYSIS (MCDA)
    # =====================================================================

    # ------------------------------------------------------------------ #
    # 9. ahp_analysis — Analytic Hierarchy Process
    # ------------------------------------------------------------------ #
    def ahp_analysis(
        self,
        alternatives: list,
        criteria: list,
        comparisons: dict,
    ) -> dict:
        """Analytic Hierarchy Process for multi-criteria decision making.

        Implements Saaty's AHP using pairwise comparison matrices.
        Computes priority weights via the eigenvector method,
        checks consistency ratio (CR < 0.10 required).

        Args:
            alternatives: List of alternative names (e.g., ["venue_a", "venue_b"]).
            criteria: List of criterion names.
            comparisons: Dict mapping (i, j) tuples to comparison ratios
                         for the criteria matrix. E.g., {(0,1): 3.0}
                         means criterion 0 is 3x more important than 1.
                         Values should be in {1/9, 1/8, ..., 1, 2, ..., 9}.

        Returns:
            Response dict with criteria weights, ranked alternatives,
            consistency ratio, and pass/fail status.
        """
        try:
            n = len(criteria)
            if n == 0:
                return self._make_response(
                    False, {}, "No criteria provided.", 0.0,
                )

            # Build criteria comparison matrix
            matrix = [[1.0] * n for _ in range(n)]
            for (i, j), val in comparisons.items():
                if 0 <= i < n and 0 <= j < n:
                    matrix[i][j] = float(val)
                    matrix[j][i] = 1.0 / float(val)

            # --- Eigenvector method via power iteration ---
            # Normalise each column
            col_sums = [sum(matrix[row][col] for row in range(n)) for col in range(n)]
            norm = [
                [matrix[i][j] / col_sums[j] if col_sums[j] != 0 else 0
                 for j in range(n)]
                for i in range(n)
            ]
            # Row averages = priority vector
            weights = [sum(norm[i][j] for j in range(n)) / n for i in range(n)]
            weight_sum = sum(weights)
            if weight_sum > 0:
                weights = [w / weight_sum for w in weights]

            # --- Consistency check ---
            # A * w
            aw = [
                sum(matrix[i][j] * weights[j] for j in range(n))
                for i in range(n)
            ]
            # Lambda max
            lambdas = [aw[i] / weights[i] if weights[i] != 0 else 0 for i in range(n)]
            lambda_max = sum(lambdas) / n if n > 0 else 0

            # Consistency Index
            ci = (lambda_max - n) / (n - 1) if n > 1 else 0.0

            # Random Index (Saaty standard values)
            ri_table = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12,
                        6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}
            ri = ri_table.get(n, 1.49)
            cr = ci / ri if ri > 0 else 0.0
            consistent = cr < 0.10

            # --- Score alternatives ---
            # Each alternative gets a weighted score based on criteria performance
            alt_scores = []
            for alt in alternatives:
                # Extract raw performance per criterion
                raw_scores = alt.get("scores", [0.0] * n) if isinstance(alt, dict) else [0.0] * n
                if isinstance(alt, dict) and "scores" in alt:
                    scores = raw_scores
                else:
                    scores = [0.0] * n
                total = sum(
                    scores[i] * weights[i] for i in range(min(n, len(scores)))
                )
                alt_scores.append({
                    "alternative": alt.get("name", str(alt)) if isinstance(alt, dict) else str(alt),
                    "weighted_score": round(total, 4),
                })

            alt_scores.sort(key=lambda x: x["weighted_score"], reverse=True)

            data = {
                "criteria_weights": {
                    criteria[i]: round(weights[i], 4) for i in range(n)
                },
                "lambda_max": round(lambda_max, 4),
                "consistency_index": round(ci, 4),
                "consistency_ratio": round(cr, 4),
                "is_consistent": consistent,
                "ranked_alternatives": alt_scores,
            }
            return self._make_response(
                True, data, "", round(1.0 if consistent else 0.5, 4),
            )

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    # ------------------------------------------------------------------ #
    # 10. topsis_analysis — Technique for Order Preference by
    #                       Similarity to Ideal Solution
    # ------------------------------------------------------------------ #
    def topsis_analysis(
        self,
        alternatives: list,
        criteria: list,
        weights: list,
    ) -> dict:
        """TOPSIS ranking of alternatives.

        Steps:
        1. Build decision matrix (alternatives x criteria).
        2. Normalise the matrix (vector normalisation).
        3. Apply weights (weighted normalised matrix).
        4. Determine positive-ideal (PIS) and negative-ideal (NIS) solutions.
        5. Compute Euclidean distances to PIS and NIS.
        6. Calculate relative closeness coefficient Ci = d_nis / (d_pis + d_nis).
        7. Rank by Ci descending.

        Args:
            alternatives: List of dicts with "name" and "scores" (list of floats).
            criteria: List of criterion names.
            weights: List of weights (will be normalised to sum=1).

        Returns:
            Response dict with ranked alternatives and closeness coefficients.
        """
        try:
            m = len(alternatives)
            n = len(criteria)
            if m == 0 or n == 0:
                return self._make_response(
                    False, {}, "Alternatives and criteria required.", 0.0,
                )

            # Normalise weights
            w_sum = sum(weights)
            norm_weights = [w / w_sum for w in weights] if w_sum > 0 else [1.0 / n] * n

            # Build decision matrix
            dm = []
            for alt in alternatives:
                scores = alt.get("scores", [0.0] * n)
                dm.append([
                    float(scores[j]) if j < len(scores) else 0.0
                    for j in range(n)
                ])

            # Step 2: Vector normalisation
            col_norms = []
            for j in range(n):
                col = [dm[i][j] for i in range(m)]
                sq_sum = sum(x ** 2 for x in col)
                col_norms.append(math.sqrt(sq_sum) if sq_sum > 0 else 1.0)

            r = [[dm[i][j] / col_norms[j] for j in range(n)] for i in range(m)]

            # Step 3: Weighted normalised matrix
            v = [[r[i][j] * norm_weights[j] for j in range(n)] for i in range(m)]

            # Step 4: PIS and NIS
            # Determine benefit/cost direction from criteria names
            pis = []
            nis = []
            for j in range(n):
                col = [v[i][j] for i in range(m)]
                # Default: assume all criteria are benefit (maximize)
                # Can be overridden by criteria names containing "cost"
                is_cost = "cost" in criteria[j].lower() or "resource" in criteria[j].lower()
                if is_cost:
                    pis.append(min(col))
                    nis.append(max(col))
                else:
                    pis.append(max(col))
                    nis.append(min(col))

            # Step 5: Distances
            def _dist(a, b):
                return math.sqrt(sum((a[j] - b[j]) ** 2 for j in range(n)))

            results = []
            for i in range(m):
                d_pis = _dist(v[i], pis)
                d_nis = _dist(v[i], nis)
                ci = d_nis / (d_pis + d_nis) if (d_pis + d_nis) > 0 else 0.0
                results.append({
                    "alternative": alternatives[i].get("name", str(i)),
                    "closeness_coefficient": round(ci, 4),
                    "distance_to_pis": round(d_pis, 4),
                    "distance_to_nis": round(d_nis, 4),
                })

            results.sort(key=lambda x: x["closeness_coefficient"], reverse=True)

            data = {
                "criteria": criteria,
                "normalised_weights": [round(w, 4) for w in norm_weights],
                "positive_ideal_solution": [round(x, 4) for x in pis],
                "negative_ideal_solution": [round(x, 4) for x in nis],
                "ranked_alternatives": results,
            }
            return self._make_response(True, data, "", 0.95)

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    # ------------------------------------------------------------------ #
    # 11. promethee_analysis — PROMETHEE II
    # ------------------------------------------------------------------ #
    def promethee_analysis(
        self,
        alternatives: list,
        criteria: list,
    ) -> dict:
        """PROMETHEE II outranking method.

        Computes net flow (Phi) for each alternative using pairwise
        comparisons on each criterion with a linear preference function.

        Steps:
        1. Pairwise compare all alternatives on each criterion.
        2. Apply linear preference function: P(d) = max(0, min(d/p, 1)).
        3. Aggregate to positive flow (Phi+), negative flow (Phi-).
        4. Net flow Phi = Phi+ - Phi-.
        5. Rank by Phi descending.

        Args:
            alternatives: List of dicts with "name" and "scores" (list).
            criteria: List of criterion names.

        Returns:
            Response dict with PROMETHEE II ranking and flows.
        """
        try:
            m = len(alternatives)
            n = len(criteria)
            if m == 0 or n == 0:
                return self._make_response(
                    False, {}, "Alternatives and criteria required.", 0.0,
                )

            # Equal weights if not specified
            weights = [1.0 / n] * n

            # Extract scores
            scores = []
            for alt in alternatives:
                s = alt.get("scores", [0.0] * n)
                scores.append([float(s[j]) if j < len(s) else 0.0 for j in range(n)])

            # Preference threshold per criterion (p = range / 2)
            ranges = []
            for j in range(n):
                col = [scores[i][j] for i in range(m)]
                ranges.append(max(col) - min(col) if m > 0 else 1.0)
            p_vals = [r / 2.0 if r > 0 else 1.0 for r in ranges]

            # Pairwise preference matrix
            pi = [[0.0] * m for _ in range(m)]  # aggregated preference

            for i in range(m):
                for k in range(m):
                    if i == k:
                        continue
                    pref_sum = 0.0
                    for j in range(n):
                        diff = scores[i][j] - scores[k][j]
                        # Linear preference function
                        p = p_vals[j]
                        pref = max(0.0, min(diff / p, 1.0)) if p > 0 else 0.0
                        pref_sum += weights[j] * pref
                    pi[i][k] = pref_sum

            # Positive and negative outranking flows
            phi_plus = [sum(pi[i][k] for k in range(m) if k != i) / (m - 1)
                        for i in range(m)]
            phi_minus = [sum(pi[k][i] for k in range(m) if k != i) / (m - 1)
                         for i in range(m)]
            phi_net = [phi_plus[i] - phi_minus[i] for i in range(m)]

            results = []
            for i in range(m):
                results.append({
                    "alternative": alternatives[i].get("name", str(i)),
                    "positive_flow": round(phi_plus[i], 4),
                    "negative_flow": round(phi_minus[i], 4),
                    "net_flow": round(phi_net[i], 4),
                })

            results.sort(key=lambda x: x["net_flow"], reverse=True)

            data = {
                "ranked_alternatives": results,
                "method": "PROMETHEE II",
                "preference_function": "linear",
            }
            return self._make_response(True, data, "", 0.90)

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    # ------------------------------------------------------------------ #
    # 12. electre_analysis — ELECTRE III
    # ------------------------------------------------------------------ #
    def electre_analysis(
        self,
        alternatives: list,
        criteria: list,
    ) -> dict:
        """ELECTRE III outranking method.

        Uses concordance / discordance analysis with indifference,
        preference, and veto thresholds. Builds outranking credibility
        matrix and distills a ranking.

        Simplified implementation with default thresholds derived
        from criterion score ranges.

        Args:
            alternatives: List of dicts with "name" and "scores" (list).
            criteria: List of criterion names.

        Returns:
            Response dict with ELECTRE III ranking and credibility matrix.
        """
        try:
            m = len(alternatives)
            n = len(criteria)
            if m == 0 or n == 0:
                return self._make_response(
                    False, {}, "Alternatives and criteria required.", 0.0,
                )

            weights = [1.0 / n] * n

            scores = []
            for alt in alternatives:
                s = alt.get("scores", [0.0] * n)
                scores.append([float(s[j]) if j < len(s) else 0.0 for j in range(n)])

            # Compute thresholds per criterion
            ranges = []
            for j in range(n):
                col = [scores[i][j] for i in range(m)]
                ranges.append(max(col) - min(col) if m > 0 else 1.0)

            q = [r * 0.10 for r in ranges]  # indifference threshold
            p = [r * 0.30 for r in ranges]  # preference threshold
            v = [r * 0.60 for r in ranges]  # veto threshold

            # Concordance matrix
            def _concordance(i, k):
                c = 0.0
                for j in range(n):
                    diff = scores[i][j] - scores[k][j]
                    if diff >= -q[j]:
                        c += weights[j]
                    elif diff < -p[j]:
                        pass  # add 0
                    else:
                        # Linear interpolation between q and p
                        c += weights[j] * ((-diff - q[j]) / (p[j] - q[j])) if p[j] != q[j] else 0
                return c

            # Partial concordance (for credibility)
            def _partial_concordance(i, k, j):
                diff = scores[i][j] - scores[k][j]
                if diff >= -q[j]:
                    return 1.0
                elif diff < -p[j]:
                    return 0.0
                else:
                    return ((-diff - q[j]) / (p[j] - q[j])) if p[j] != q[j] else 0.0

            # Discordance
            def _discordance(i, k, j):
                diff = scores[i][j] - scores[k][j]
                if diff >= -p[j]:
                    return 0.0
                elif diff < -v[j]:
                    return 1.0
                else:
                    return (p[j] + diff) / (p[j] - v[j]) if (p[j] - v[j]) != 0 else 0.0

            # Credibility matrix
            credibility = [[0.0] * m for _ in range(m)]
            for i in range(m):
                for k in range(m):
                    if i == k:
                        credibility[i][k] = 1.0
                        continue
                    c_total = _concordance(i, k)
                    # Apply veto-adjusted credibility
                    sigma = c_total
                    for j in range(n):
                        d_j = _discordance(i, k, j)
                        c_j = _partial_concordance(i, k, j)
                        if d_j > c_j:
                            sigma *= (1.0 - d_j) / (1.0 - c_j) if c_j < 1.0 else 0.0
                    credibility[i][k] = max(0.0, min(sigma, 1.0))

            # Score = average credibility over others (excluding self)
            avg_cred = []
            for i in range(m):
                others = [credibility[i][k] for k in range(m) if k != i]
                avg_cred.append(statistics.mean(others) if others else 0.0)

            results = []
            for i in range(m):
                results.append({
                    "alternative": alternatives[i].get("name", str(i)),
                    "avg_credibility": round(avg_cred[i], 4),
                })

            results.sort(key=lambda x: x["avg_credibility"], reverse=True)

            data = {
                "ranked_alternatives": results,
                "credibility_matrix": [
                    [round(credibility[i][j], 3) for j in range(m)]
                    for i in range(m)
                ],
                "method": "ELECTRE III",
            }
            return self._make_response(True, data, "", 0.88)

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    # ------------------------------------------------------------------ #
    # 13. sensitivity_analysis — Monte Carlo sensitivity
    # ------------------------------------------------------------------ #
    def sensitivity_analysis(
        self,
        base_scores: dict,
        perturbations: int = 100,
    ) -> dict:
        """Monte Carlo sensitivity analysis on scoring weights.

        Perturbs criteria weights using Gaussian noise and re-computes
        scores to assess ranking stability. Reports:
        - Mean and standard deviation of each alternative's score
        - Ranking frequency (how often each alternative ranks #1)
        - Confidence intervals (95%)

        Args:
            base_scores: Dict with "alternatives" (list of names) and
                         "criteria_scores" (dict of criterion -> list of
                         scores per alternative).
            perturbations: Number of Monte Carlo iterations.

        Returns:
            Response dict with sensitivity statistics and stability assessment.
        """
        try:
            alternatives = base_scores.get("alternatives", [])
            criteria_scores = base_scores.get("criteria_scores", {})
            if not alternatives or not criteria_scores:
                return self._make_response(
                    False, {}, "Alternatives and criteria_scores required.", 0.0,
                )

            n_alt = len(alternatives)
            criteria = list(criteria_scores.keys())
            n_crit = len(criteria)

            # Base weights (equal)
            base_weights = [1.0 / n_crit] * n_crit

            # Store scores per alternative across perturbations
            all_scores = {alt: [] for alt in alternatives}
            rank_counts = {alt: [0] * n_alt for alt in alternatives}
            top_counts = {alt: 0 for alt in alternatives}

            # Set seed for reproducibility
            rng = random.Random(self.random_seed)

            for _ in range(perturbations):
                # Perturb weights: Gaussian noise, then re-normalise
                noise = [rng.gauss(0, 0.15) for _ in range(n_crit)]
                perturbed = [
                    max(0.01, base_weights[j] + noise[j])
                    for j in range(n_crit)
                ]
                w_sum = sum(perturbed)
                weights = [w / w_sum for w in perturbed]

                # Compute weighted scores
                scored = []
                for i, alt in enumerate(alternatives):
                    total = 0.0
                    for j, crit in enumerate(criteria):
                        scores_list = criteria_scores.get(crit, [])
                        val = float(scores_list[i]) if i < len(scores_list) else 0.0
                        total += val * weights[j]
                    scored.append((alt, total))
                    all_scores[alt].append(total)

                # Rank
                scored.sort(key=lambda x: x[1], reverse=True)
                for rank_idx, (alt, _) in enumerate(scored):
                    rank_counts[alt][rank_idx] += 1
                if scored:
                    top_counts[scored[0][0]] += 1

            # Statistics
            stats = []
            for alt in alternatives:
                scores_list = all_scores[alt]
                mean_s = statistics.mean(scores_list)
                stdev_s = statistics.stdev(scores_list) if len(scores_list) > 1 else 0.0
                # 95% CI
                ci_low = mean_s - 1.96 * stdev_s
                ci_high = mean_s + 1.96 * stdev_s
                stability = top_counts[alt] / perturbations

                stats.append({
                    "alternative": alt,
                    "mean_score": round(mean_s, 4),
                    "std_dev": round(stdev_s, 4),
                    "ci_95_low": round(ci_low, 4),
                    "ci_95_high": round(ci_high, 4),
                    "top_rank_frequency": round(stability, 4),
                    "rank_distribution": rank_counts[alt],
                })

            # Most stable
            stats.sort(key=lambda x: x["top_rank_frequency"], reverse=True)
            most_stable = stats[0]["alternative"] if stats else None
            stability_score = stats[0]["top_rank_frequency"] if stats else 0.0

            data = {
                "perturbations": perturbations,
                "most_stable_alternative": most_stable,
                "stability_score": round(stability_score, 4),
                "alternative_statistics": stats,
                "interpretation": (
                    f"{most_stable} is the most robust choice with "
                    f"{stability_score:.1%} frequency of top rank."
                    if most_stable else "No stable alternative found."
                ),
            }
            return self._make_response(
                True, data, "", round(stability_score, 4),
            )

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    # =====================================================================
    # SECTION C — PATTERN RECOGNITION
    # =====================================================================

    # ------------------------------------------------------------------ #
    # 14. detect_temporal_patterns
    # ------------------------------------------------------------------ #
    def detect_temporal_patterns(
        self,
        events: list,
        window: str = "monthly",
    ) -> dict:
        """Detect temporal patterns in event sequences.

        Aggregates events into time windows and computes:
        - Event frequency per window
        - Trend (linear regression slope on window counts)
        - Seasonality index (peak-to-trough ratio)
        - Burst detection (windows exceeding 2 std dev above mean)
        - Periodicity via autocorrelation

        Args:
            events: List of dicts with "timestamp" (ISO 8601 or datetime)
                    and optional "type", "severity".
            window: Aggregation window — "daily", "weekly", or "monthly".

        Returns:
            Response dict with temporal pattern analysis.
        """
        try:
            if not events:
                return self._make_response(
                    False, {}, "No events provided.", 0.0,
                )

            # Parse timestamps
            parsed = []
            for ev in events:
                ts = ev.get("timestamp", "")
                if isinstance(ts, str):
                    try:
                        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                elif isinstance(ts, datetime):
                    dt = ts
                else:
                    continue
                parsed.append({
                    "datetime": dt,
                    "type": ev.get("type", "unknown"),
                    "severity": ev.get("severity", 1),
                })

            if not parsed:
                return self._make_response(
                    False, {}, "No parseable timestamps.", 0.0,
                )

            parsed.sort(key=lambda x: x["datetime"])

            # Determine window key function
            if window == "daily":
                def _key(dt):
                    return (dt.year, dt.month, dt.day)
            elif window == "weekly":
                def _key(dt):
                    # ISO week
                    return (dt.year, dt.isocalendar()[1])
            else:  # monthly
                def _key(dt):
                    return (dt.year, dt.month)

            # Aggregate
            buckets: Dict[tuple, list] = {}
            for ev in parsed:
                k = _key(ev["datetime"])
                buckets.setdefault(k, []).append(ev)

            sorted_keys = sorted(buckets.keys())
            counts = [len(buckets[k]) for k in sorted_keys]
            severities = [
                statistics.mean(e["severity"] for e in buckets[k])
                for k in sorted_keys
            ]

            if not counts:
                return self._make_response(
                    False, {}, "No aggregatable windows.", 0.0,
                )

            # Trend via least-squares linear regression
            n_win = len(counts)
            x_vals = list(range(n_win))
            x_mean = statistics.mean(x_vals)
            c_mean = statistics.mean(counts)
            ss_xy = sum((x_vals[i] - x_mean) * (counts[i] - c_mean)
                        for i in range(n_win))
            ss_xx = sum((x_vals[i] - x_mean) ** 2 for i in range(n_win))
            slope = ss_xy / ss_xx if ss_xx != 0 else 0.0
            intercept = c_mean - slope * x_mean

            # Seasonality: peak-to-trough ratio
            max_c = max(counts)
            min_c = min(counts) if min(counts) > 0 else 1
            seasonality = max_c / min_c

            # Burst detection
            c_std = statistics.stdev(counts) if n_win > 1 else 0.0
            burst_threshold = c_mean + 2.0 * c_std
            bursts = [
                {"window": str(sorted_keys[i]), "count": counts[i]}
                for i in range(n_win)
                if counts[i] > burst_threshold
            ]

            # Autocorrelation for periodicity
            autocorr = []
            if n_win > 2:
                c_var = statistics.variance(counts) if n_win > 1 else 1.0
                for lag in range(1, min(n_win // 2, 12)):
                    cov = sum(
                        (counts[i] - c_mean) * (counts[i + lag] - c_mean)
                        for i in range(n_win - lag)
                    ) / (n_win - lag)
                    autocorr.append({
                        "lag": lag,
                        "correlation": round(cov / c_var, 4) if c_var else 0.0,
                    })

            data = {
                "window_type": window,
                "window_count": n_win,
                "event_counts": counts,
                "trend_slope": round(slope, 6),
                "trend_direction": "increasing" if slope > 0.1 else (
                    "decreasing" if slope < -0.1 else "stable"
                ),
                "seasonality_index": round(seasonality, 4),
                "mean_events_per_window": round(c_mean, 2),
                "std_dev": round(c_std, 2),
                "bursts_detected": bursts,
                "burst_count": len(bursts),
                "autocorrelation": autocorr,
                "periodicity_detected": any(
                    abs(a["correlation"]) > 0.5 for a in autocorr
                ) if autocorr else False,
            }
            return self._make_response(True, data, "", 0.85)

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    # ------------------------------------------------------------------ #
    # 15. detect_network_patterns
    # ------------------------------------------------------------------ #
    def detect_network_patterns(
        self,
        entities: list,
        relationships: list,
    ) -> dict:
        """Detect patterns in entity-relationship networks.

        Computes:
        - Degree centrality (who connects to most)
        - Betweenness centrality (who bridges clusters)
        - Clustering coefficient (triadic closure)
        - Density (overall connectivity)
        - Key nodes (hubs and bridges)

        Args:
            entities: List of entity IDs or dicts with "id".
            relationships: List of dicts with "source" and "target".

        Returns:
            Response dict with network pattern analysis.
        """
        try:
            # Normalise entity IDs
            entity_ids = []
            for e in entities:
                if isinstance(e, dict):
                    entity_ids.append(str(e.get("id", e)))
                else:
                    entity_ids.append(str(e))

            if not entity_ids or not relationships:
                return self._make_response(
                    False, {}, "Entities and relationships required.", 0.0,
                )

            n = len(entity_ids)
            idx_map = {eid: i for i, eid in enumerate(entity_ids)}

            # Adjacency list
            adj: Dict[int, set] = {i: set() for i in range(n)}
            edge_count = 0
            for rel in relationships:
                src = str(rel.get("source", ""))
                tgt = str(rel.get("target", ""))
                if src in idx_map and tgt in idx_map:
                    si, ti = idx_map[src], idx_map[tgt]
                    adj[si].add(ti)
                    adj[ti].add(si)
                    edge_count += 1

            # Degree centrality
            degrees = {eid: len(adj[idx_map[eid]]) for eid in entity_ids}
            max_deg = max(degrees.values()) if degrees else 1
            degree_cent = {
                eid: degrees[eid] / max_deg for eid in entity_ids
            }

            # Betweenness centrality (Brandes algorithm approximation)
            betweenness = {i: 0.0 for i in range(n)}
            for s in range(n):
                # BFS from s
                queue = [s]
                pred: Dict[int, list] = {i: [] for i in range(n)}
                dist: Dict[int, int] = {i: -1 for i in range(n)}
                sigma = {i: 0.0 for i in range(n)}
                dist[s] = 0
                sigma[s] = 1.0
                bfs_order = []
                while queue:
                    v = queue.pop(0)
                    bfs_order.append(v)
                    for w in adj[v]:
                        if dist[w] < 0:
                            dist[w] = dist[v] + 1
                            queue.append(w)
                        if dist[w] == dist[v] + 1:
                            sigma[w] += sigma[v]
                            pred[w].append(v)

                # Accumulation
                delta = {i: 0.0 for i in range(n)}
                while bfs_order:
                    w = bfs_order.pop()
                    for v in pred[w]:
                        delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
                    if w != s:
                        betweenness[w] += delta[w]

            # Normalise betweenness
            denom = (n - 1) * (n - 2) / 2.0 if n > 2 else 1.0
            betweenness_norm = {
                entity_ids[i]: betweenness[i] / denom if denom > 0 else 0.0
                for i in range(n)
            }

            # Clustering coefficient
            clustering = {}
            for eid in entity_ids:
                i = idx_map[eid]
                neighbors = list(adj[i])
                k = len(neighbors)
                if k < 2:
                    clustering[eid] = 0.0
                    continue
                tri = 0
                for a_idx in range(k):
                    for b_idx in range(a_idx + 1, k):
                        if neighbors[b_idx] in adj[neighbors[a_idx]]:
                            tri += 1
                clustering[eid] = (2.0 * tri) / (k * (k - 1))

            # Density
            possible = n * (n - 1) / 2.0 if n > 1 else 1.0
            density = edge_count / possible if possible > 0 else 0.0

            # Hub identification
            sorted_degree = sorted(degree_cent.items(), key=lambda x: x[1], reverse=True)
            sorted_between = sorted(betweenness_norm.items(), key=lambda x: x[1], reverse=True)

            data = {
                "entity_count": n,
                "relationship_count": edge_count,
                "network_density": round(density, 4),
                "degree_centrality": {
                    k: round(v, 4) for k, v in sorted_degree[:10]
                },
                "betweenness_centrality": {
                    k: round(v, 4) for k, v in sorted_between[:10]
                },
                "clustering_coefficient": {
                    k: round(v, 4) for k, v in clustering.items()
                },
                "mean_clustering": round(
                    statistics.mean(clustering.values()), 4,
                ) if clustering else 0.0,
                "key_hubs": [eid for eid, _ in sorted_degree[:5]],
                "key_bridges": [eid for eid, _ in sorted_between[:5]],
                "network_type": (
                    "highly_connected" if density > 0.5 else
                    "sparse" if density < 0.1 else "moderate"
                ),
            }
            return self._make_response(True, data, "", 0.82)

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    # ------------------------------------------------------------------ #
    # 16. detect_geographic_concentration
    # ------------------------------------------------------------------ #
    def detect_geographic_concentration(
        self,
        events: list,
    ) -> dict:
        """Detect geographic clustering of events.

        Computes:
        - Event density per region
        - Gini coefficient of spatial distribution
        - Hotspot identification (regions above mean + 1 std)
        - Spatial dispersion (average pairwise Haversine distance)

        Args:
            events: List of dicts with "latitude", "longitude",
                    "region" (optional), and "weight" (optional).

        Returns:
            Response dict with geographic concentration analysis.
        """
        try:
            if not events:
                return self._make_response(
                    False, {}, "No events provided.", 0.0,
                )

            # Collect valid events with coordinates
            valid = []
            for ev in events:
                lat = ev.get("latitude")
                lon = ev.get("longitude")
                if lat is not None and lon is not None:
                    valid.append({
                        "lat": float(lat),
                        "lon": float(lon),
                        "region": ev.get("region", "unknown"),
                        "weight": ev.get("weight", 1.0),
                    })

            if not valid:
                return self._make_response(
                    False, {}, "No events with coordinates.", 0.0,
                )

            # Regional aggregation
            region_counts: Dict[str, float] = {}
            for ev in valid:
                r = ev["region"]
                region_counts[r] = region_counts.get(r, 0.0) + ev["weight"]

            sorted_regions = sorted(
                region_counts.items(), key=lambda x: x[1], reverse=True,
            )

            # Gini coefficient
            gini = self._gini_coefficient(list(region_counts.values()))

            # Hotspots: regions above mean + 1 std
            counts = list(region_counts.values())
            mean_c = statistics.mean(counts)
            std_c = statistics.stdev(counts) if len(counts) > 1 else 0.0
            threshold = mean_c + std_c
            hotspots = [
                {"region": r, "count": round(c, 2)}
                for r, c in sorted_regions if c >= threshold
            ]

            # Centroid
            total_weight = sum(ev["weight"] for ev in valid)
            centroid_lat = sum(
                ev["lat"] * ev["weight"] for ev in valid
            ) / total_weight
            centroid_lon = sum(
                ev["lon"] * ev["weight"] for ev in valid
            ) / total_weight

            # Spatial dispersion (avg pairwise Haversine distance)
            def _haversine(lat1, lon1, lat2, lon2):
                R = 6371.0  # Earth radius in km
                dlat = math.radians(lat2 - lat1)
                dlon = math.radians(lon2 - lon1)
                a = (math.sin(dlat / 2) ** 2 +
                     math.cos(math.radians(lat1)) *
                     math.cos(math.radians(lat2)) *
                     math.sin(dlon / 2) ** 2)
                return 2 * R * math.asin(math.sqrt(a))

            n_v = len(valid)
            if n_v > 1:
                total_dist = 0.0
                pairs = 0
                for i in range(min(n_v, 100)):  # cap for performance
                    for j in range(i + 1, min(n_v, 100)):
                        total_dist += _haversine(
                            valid[i]["lat"], valid[i]["lon"],
                            valid[j]["lat"], valid[j]["lon"],
                        )
                        pairs += 1
                avg_dist = total_dist / pairs if pairs else 0.0
            else:
                avg_dist = 0.0

            data = {
                "event_count": n_v,
                "region_count": len(region_counts),
                "region_distribution": [
                    {"region": r, "count": round(c, 2)}
                    for r, c in sorted_regions[:10]
                ],
                "gini_coefficient": round(gini, 4),
                "concentration_level": (
                    "highly_concentrated" if gini > 0.7 else
                    "moderately_concentrated" if gini > 0.4 else "dispersed"
                ),
                "hotspots": hotspots,
                "centroid": {
                    "latitude": round(centroid_lat, 6),
                    "longitude": round(centroid_lon, 6),
                },
                "avg_pairwise_distance_km": round(avg_dist, 2),
            }
            return self._make_response(True, data, "", 0.80)

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    @staticmethod
    def _gini_coefficient(values: list) -> float:
        """Compute Gini coefficient for inequality measurement.

        Args:
            values: List of non-negative numeric values.

        Returns:
            Gini coefficient in [0, 1].
        """
        n = len(values)
        if n == 0:
            return 0.0
        sorted_vals = sorted(values)
        cumsum = 0.0
        for i, v in enumerate(sorted_vals, 1):
            cumsum += (2 * i - n - 1) * v
        denom = n * sum(sorted_vals)
        return cumsum / denom if denom != 0 else 0.0

    # ------------------------------------------------------------------ #
    # 17. detect_sequential_patterns
    # ------------------------------------------------------------------ #
    def detect_sequential_patterns(
        self,
        events: list,
    ) -> dict:
        """Mine sequential patterns from ordered event streams.

        Uses a simplified frequent sequence mining approach:
        1. Find frequent individual event types.
        2. Find frequent 2-grams and 3-grams.
        3. Report support, confidence, and lift for discovered patterns.

        Args:
            events: List of dicts with "type" (string) and optional
                    "timestamp" for ordering.

        Returns:
            Response dict with discovered sequential patterns.
        """
        try:
            if not events:
                return self._make_response(
                    False, {}, "No events provided.", 0.0,
                )

            # Sort by timestamp if available
            has_ts = all("timestamp" in e for e in events)
            if has_ts:
                events = sorted(
                    events,
                    key=lambda x: x.get("timestamp", ""),
                )

            sequence = [str(e.get("type", "unknown")) for e in events]
            n = len(sequence)
            if n < 2:
                return self._make_response(
                    False, {}, "Need at least 2 events.", 0.0,
                )

            # Frequency of individual items
            item_counts: Dict[str, int] = {}
            for item in sequence:
                item_counts[item] = item_counts.get(item, 0) + 1

            min_support = max(2, n * 0.05)  # at least 5% or 2 occurrences

            # Frequent items
            frequent_items = {
                item: cnt for item, cnt in item_counts.items()
                if cnt >= min_support
            }

            # 2-grams
            bigrams: Dict[Tuple[str, str], int] = {}
            for i in range(n - 1):
                bg = (sequence[i], sequence[i + 1])
                bigrams[bg] = bigrams.get(bg, 0) + 1

            frequent_bigrams = {
                bg: cnt for bg, cnt in bigrams.items()
                if cnt >= min_support
            }

            # 3-grams
            trigrams: Dict[Tuple[str, str, str], int] = {}
            for i in range(n - 2):
                tg = (sequence[i], sequence[i + 1], sequence[i + 2])
                trigrams[tg] = trigrams.get(tg, 0) + 1

            frequent_trigrams = {
                tg: cnt for tg, cnt in trigrams.items()
                if cnt >= min_support
            }

            # Format patterns with confidence and lift
            patterns = []
            for bg, cnt in sorted(
                frequent_bigrams.items(), key=lambda x: x[1], reverse=True,
            )[:20]:
                a, b = bg
                support = cnt / n
                confidence = cnt / item_counts.get(a, 1)
                lift = confidence / (item_counts.get(b, 1) / n) if n > 0 else 0
                patterns.append({
                    "pattern": f"{a} -> {b}",
                    "length": 2,
                    "count": cnt,
                    "support": round(support, 4),
                    "confidence": round(confidence, 4),
                    "lift": round(lift, 4),
                })

            for tg, cnt in sorted(
                frequent_trigrams.items(), key=lambda x: x[1], reverse=True,
            )[:10]:
                a, b, c = tg
                support = cnt / n
                ab_count = bigrams.get((a, b), 1)
                confidence = cnt / ab_count
                lift = confidence / (item_counts.get(c, 1) / n) if n > 0 else 0
                patterns.append({
                    "pattern": f"{a} -> {b} -> {c}",
                    "length": 3,
                    "count": cnt,
                    "support": round(support, 4),
                    "confidence": round(confidence, 4),
                    "lift": round(lift, 4),
                })

            patterns.sort(key=lambda x: (x["lift"], x["confidence"]), reverse=True)

            data = {
                "sequence_length": n,
                "unique_event_types": len(item_counts),
                "frequent_items": {
                    k: v for k, v in sorted(
                        frequent_items.items(), key=lambda x: x[1], reverse=True,
                    )[:10]
                },
                "discovered_patterns": patterns[:15],
                "pattern_count": len(patterns),
                "strongest_pattern": patterns[0] if patterns else None,
            }
            return self._make_response(True, data, "", 0.78)

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    # ------------------------------------------------------------------ #
    # 18. detect_anomaly_zscore
    # ------------------------------------------------------------------ #
    def detect_anomaly_zscore(
        self,
        values: list,
        threshold: float = 3.0,
    ) -> dict:
        """Detect statistical anomalies using Z-score method.

        For each value, computes Z = (x - mean) / std_dev.
        Values with |Z| > threshold are flagged as anomalies.
        Also computes modified Z-score using median for robustness.

        Args:
            values: List of numeric values.
            threshold: Z-score threshold (default 3.0 = 99.7% confidence).

        Returns:
            Response dict with anomalies and statistics.
        """
        try:
            if not values:
                return self._make_response(
                    False, {}, "No values provided.", 0.0,
                )

            numeric = [float(v) for v in values]
            n = len(numeric)
            mean_v = statistics.mean(numeric)
            std_v = statistics.stdev(numeric) if n > 1 else 0.0
            median_v = statistics.median(numeric)

            # Median absolute deviation for modified Z-score
            mad = statistics.median([abs(x - median_v) for x in numeric])
            # Consistency constant: 1.4826 for normal distribution
            mad_scaled = mad * 1.4826 if mad > 0 else 1.0

            anomalies = []
            normal = []
            for i, v in enumerate(numeric):
                z = (v - mean_v) / std_v if std_v > 0 else 0.0
                modified_z = 0.6745 * (v - median_v) / mad_scaled if mad_scaled > 0 else 0.0

                is_anomaly = abs(z) > threshold
                entry = {
                    "index": i,
                    "value": v,
                    "z_score": round(z, 4),
                    "modified_z_score": round(modified_z, 4),
                    "is_anomaly": is_anomaly,
                }
                if is_anomaly:
                    anomalies.append(entry)
                else:
                    normal.append(entry)

            # Confidence based on sample size
            confidence = min(n / 30.0, 1.0)  # 30+ samples = full confidence

            data = {
                "total_values": n,
                "mean": round(mean_v, 4),
                "median": round(median_v, 4),
                "std_dev": round(std_v, 4),
                "mad": round(mad, 4),
                "threshold": threshold,
                "anomaly_count": len(anomalies),
                "anomaly_rate": round(len(anomalies) / n, 4) if n > 0 else 0.0,
                "anomalies": anomalies,
                "normal_values": len(normal),
                "statistics": {
                    "min": round(min(numeric), 4),
                    "max": round(max(numeric), 4),
                    "range": round(max(numeric) - min(numeric), 4),
                    "q1": round(
                        statistics.quantiles(numeric, n=4, method="inclusive")[0], 4,
                    ) if n >= 4 else round(median_v, 4),
                    "q3": round(
                        statistics.quantiles(numeric, n=4, method="inclusive")[2], 4,
                    ) if n >= 4 else round(median_v, 4),
                },
            }
            return self._make_response(True, data, "", round(confidence, 4))

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    # ------------------------------------------------------------------ #
    # 19. cluster_targets — K-means clustering
    # ------------------------------------------------------------------ #
    def cluster_targets(
        self,
        targets: list,
        features: list,
        n_clusters: int = 5,
    ) -> dict:
        """Cluster targets using K-means algorithm.

        Standard Lloyd's algorithm with:
        - K-means++ initialisation
        - Euclidean distance metric
        - Up to 100 iterations or convergence

        Args:
            targets: List of dicts with feature values.
            features: List of feature key names to use for clustering.
            n_clusters: Number of clusters (K).

        Returns:
            Response dict with cluster assignments and centroids.
        """
        try:
            if not targets or not features:
                return self._make_response(
                    False, {}, "Targets and features required.", 0.0,
                )

            # Extract feature vectors
            vectors = []
            for t in targets:
                vec = []
                for f in features:
                    val = t.get(f, 0.0)
                    vec.append(float(val) if val is not None else 0.0)
                vectors.append(vec)

            n = len(vectors)
            d = len(features)
            k = min(n_clusters, n)

            if k < 2:
                return self._make_response(
                    False, {}, "Need at least 2 targets for clustering.", 0.0,
                )

            # Normalise features to [0, 1]
            ranges = []
            for j in range(d):
                col = [vectors[i][j] for i in range(n)]
                min_c = min(col)
                max_c = max(col)
                ranges.append((min_c, max_c))

            normalised = []
            for i in range(n):
                vec = []
                for j in range(d):
                    min_c, max_c = ranges[j]
                    if max_c > min_c:
                        vec.append((vectors[i][j] - min_c) / (max_c - min_c))
                    else:
                        vec.append(0.5)
                normalised.append(vec)

            # K-means++ initialisation
            rng = random.Random(self.random_seed)
            centroids = [normalised[rng.randint(0, n - 1)]]
            for _ in range(1, k):
                # D^2 sampling
                dists = []
                for vec in normalised:
                    min_dist = min(
                        sum((vec[j] - c[j]) ** 2 for j in range(d))
                        for c in centroids
                    )
                    dists.append(min_dist)
                total = sum(dists)
                if total == 0:
                    centroids.append(normalised[rng.randint(0, n - 1)])
                    continue
                r = rng.random() * total
                cumsum = 0.0
                for idx, dist in enumerate(dists):
                    cumsum += dist
                    if cumsum >= r:
                        centroids.append(normalised[idx])
                        break
                else:
                    centroids.append(normalised[-1])

            # Lloyd's algorithm
            assignments = [0] * n
            max_iter = 100
            for iteration in range(max_iter):
                # Assignment step
                changed = False
                for i in range(n):
                    best = 0
                    best_dist = float("inf")
                    for c_idx in range(k):
                        dist = sum(
                            (normalised[i][j] - centroids[c_idx][j]) ** 2
                            for j in range(d)
                        )
                        if dist < best_dist:
                            best_dist = dist
                            best = c_idx
                    if assignments[i] != best:
                        changed = True
                        assignments[i] = best

                if not changed:
                    break

                # Update step
                for c_idx in range(k):
                    members = [
                        normalised[i] for i in range(n)
                        if assignments[i] == c_idx
                    ]
                    if members:
                        centroids[c_idx] = [
                            statistics.mean(m[j] for m in members)
                            for j in range(d)
                        ]

            # Compute cluster statistics
            clusters = []
            for c_idx in range(k):
                members = [
                    i for i in range(n) if assignments[i] == c_idx
                ]
                if not members:
                    continue
                # Within-cluster sum of squares
                wcss = sum(
                    sum(
                        (normalised[i][j] - centroids[c_idx][j]) ** 2
                        for j in range(d)
                    )
                    for i in members
                )
                clusters.append({
                    "cluster_id": c_idx,
                    "size": len(members),
                    "member_indices": members,
                    "wcss": round(wcss, 4),
                    "centroid": [
                        round(centroids[c_idx][j], 4) for j in range(d)
                    ],
                })

            # Total WCSS (elbow metric)
            total_wcss = sum(c["wcss"] for c in clusters)

            data = {
                "n_clusters": k,
                "n_targets": n,
                "features": features,
                "iterations": iteration + 1,
                "cluster_assignments": assignments,
                "clusters": clusters,
                "total_wcss": round(total_wcss, 4),
                "silhouette_estimate": round(
                    self._estimate_silhouette(
                        normalised, assignments, centroids,
                    ), 4,
                ),
            }
            return self._make_response(True, data, "", 0.80)

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    @staticmethod
    def _estimate_silhouette(vectors, assignments, centroids):
        """Estimate average silhouette score for clustering quality.

        Args:
            vectors: Normalised feature vectors.
            assignments: Cluster index per vector.
            centroids: Cluster centroids.

        Returns:
            Estimated silhouette score in [-1, 1].
        """
        n = len(vectors)
        if n < 2:
            return 0.0

        d = len(vectors[0])
        k = len(centroids)
        scores = []

        for i in range(min(n, 200)):  # cap for performance
            c_i = assignments[i]
            # a(i): distance to own cluster
            own_members = [
                j for j in range(n) if assignments[j] == c_i and j != i
            ]
            if own_members:
                a_i = statistics.mean(
                    math.sqrt(sum(
                        (vectors[i][j] - vectors[m][j]) ** 2
                        for j in range(d)
                    ))
                    for m in own_members[:50]  # sample
                )
            else:
                a_i = 0.0

            # b(i): distance to nearest other cluster
            b_i = float("inf")
            for c_j in range(k):
                if c_j == c_i:
                    continue
                other_members = [
                    j for j in range(n) if assignments[j] == c_j
                ]
                if other_members:
                    avg_dist = statistics.mean(
                        math.sqrt(sum(
                            (vectors[i][j] - vectors[m][j]) ** 2
                            for j in range(d)
                        ))
                        for m in other_members[:50]
                    )
                    b_i = min(b_i, avg_dist)

            if b_i == float("inf"):
                b_i = a_i

            denom = max(a_i, b_i)
            if denom > 0:
                scores.append((b_i - a_i) / denom)

        return statistics.mean(scores) if scores else 0.0

    # =====================================================================
    # SECTION D — INTELLIGENCE GENERATION
    # =====================================================================

    # ------------------------------------------------------------------ #
    # 20. generate_threat_assessment
    # ------------------------------------------------------------------ #
    def generate_threat_assessment(
        self,
        targets: list,
        evidence: list,
    ) -> dict:
        """Generate a threat assessment matrix.

        Combines target scoring with evidence analysis to produce:
        - Individual threat scores (likelihood x impact)
        - Aggregate threat landscape
        - Trend analysis
        - Recommended countermeasures

        Args:
            targets: List of target dicts with name, likelihood (0-10),
                     impact (0-10), and category.
            evidence: List of evidence dicts linking to targets.

        Returns:
            Response dict with threat matrix and assessment.
        """
        try:
            if not targets:
                return self._make_response(
                    False, {}, "No targets provided.", 0.0,
                )

            threat_matrix = []
            total_risk = 0.0

            for target in targets:
                name = target.get("name", "unknown")
                likelihood = min(float(target.get("likelihood", 0)), 10.0)
                impact = min(float(target.get("impact", 0)), 10.0)
                category = target.get("category", "unknown")

                # Risk = likelihood * impact (standard risk matrix)
                risk_score = (likelihood / 10.0) * (impact / 10.0)
                total_risk += risk_score

                # Risk tier
                if risk_score >= 0.64:
                    tier = "critical"
                elif risk_score >= 0.36:
                    tier = "high"
                elif risk_score >= 0.16:
                    tier = "medium"
                else:
                    tier = "low"

                # Count supporting evidence
                supporting = sum(
                    1 for ev in evidence
                    if ev.get("target") == name or ev.get("target_id") == target.get("id")
                )

                threat_matrix.append({
                    "target": name,
                    "category": category,
                    "likelihood": round(likelihood, 2),
                    "impact": round(impact, 2),
                    "risk_score": round(risk_score, 4),
                    "risk_tier": tier,
                    "supporting_evidence_count": supporting,
                })

            threat_matrix.sort(key=lambda x: x["risk_score"], reverse=True)

            # Aggregate statistics
            categories: Dict[str, list] = {}
            for t in threat_matrix:
                cat = t["category"]
                categories.setdefault(cat, []).append(t["risk_score"])

            category_risk = {
                cat: round(statistics.mean(scores), 4)
                for cat, scores in categories.items()
            }

            data = {
                "threat_matrix": threat_matrix,
                "highest_threat": threat_matrix[0] if threat_matrix else None,
                "aggregate_risk_score": round(
                    statistics.mean(t["risk_score"] for t in threat_matrix), 4,
                ) if threat_matrix else 0.0,
                "total_targets_assessed": len(targets),
                "critical_count": sum(
                    1 for t in threat_matrix if t["risk_tier"] == "critical"
                ),
                "high_count": sum(
                    1 for t in threat_matrix if t["risk_tier"] == "high"
                ),
                "category_risk": category_risk,
                "assessment_summary": (
                    f"{len(targets)} targets assessed. "
                    f"{sum(1 for t in threat_matrix if t['risk_tier'] in ('critical', 'high'))} "
                    f"require immediate attention."
                ),
            }
            return self._make_response(True, data, "", 0.85)

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    # ------------------------------------------------------------------ #
    # 21. generate_target_dossier
    # ------------------------------------------------------------------ #
    def generate_target_dossier(
        self,
        target: dict,
        all_evidence: list,
    ) -> dict:
        """Generate a comprehensive target dossier.

        Compiles all available intelligence into a structured profile:
        - Priority score
        - Associated evidence (linked by target_id or name)
        - Timeline of events
        - Network associations
        - Risk indicators
        - Recommended investigative actions

        Args:
            target: Dict with target details (name, id, type, attributes).
            all_evidence: List of evidence dicts with target linkage.

        Returns:
            Response dict with comprehensive dossier.
        """
        try:
            target_id = target.get("id", target.get("name", "unknown"))
            target_name = target.get("name", "unknown")

            # Filter linked evidence
            linked = [
                ev for ev in all_evidence
                if ev.get("target_id") == target_id
                or ev.get("target") == target_name
            ]

            # Timeline
            timeline = []
            for ev in linked:
                ts = ev.get("timestamp", ev.get("date", ""))
                if ts:
                    timeline.append({
                        "date": str(ts),
                        "event": ev.get("description", ev.get("type", "unknown")),
                        "source": ev.get("source", "unknown"),
                        "reliability": ev.get("reliability", "unknown"),
                    })
            timeline.sort(key=lambda x: x["date"])

            # Evidence quality summary
            evidence_types: Dict[str, int] = {}
            reliability_scores = []
            for ev in linked:
                ev_type = ev.get("type", "unknown")
                evidence_types[ev_type] = evidence_types.get(ev_type, 0) + 1
                rel = ev.get("reliability_score", ev.get("reliability", 0))
                if isinstance(rel, (int, float)):
                    reliability_scores.append(float(rel))

            avg_reliability = (
                statistics.mean(reliability_scores)
                if reliability_scores else 0.0
            )

            # Risk indicators
            risk_indicators = []
            if target.get("financial_activity_flag"):
                risk_indicators.append("Suspicious financial activity")
            if target.get("travel_pattern_anomaly"):
                risk_indicators.append("Unusual travel patterns")
            if target.get("communication_encryption"):
                risk_indicators.append("Encrypted communications")
            if target.get("shell_company_associations"):
                risk_indicators.append("Shell company associations")
            if len(linked) > 10:
                risk_indicators.append("Extensive evidence base")

            # Compute priority score
            priority_result = self.score_target_priority(target)
            priority_score = (
                priority_result["data"].get("composite_score", 0.5)
                if priority_result["success"] else 0.5
            )

            data = {
                "dossier_id": f"DOSSIER-{target_id}-{datetime.utcnow().strftime('%Y%m%d')}",
                "target": {
                    "id": target_id,
                    "name": target_name,
                    "type": target.get("type", "unknown"),
                    "status": target.get("status", "active"),
                },
                "priority_score": round(priority_score, 4),
                "priority_tier": (
                    "critical" if priority_score >= 0.85 else
                    "high" if priority_score >= 0.65 else
                    "medium" if priority_score >= 0.40 else "low"
                ),
                "evidence_summary": {
                    "total_linked_evidence": len(linked),
                    "evidence_types": evidence_types,
                    "avg_reliability": round(avg_reliability, 4),
                    "strongest_evidence": (
                        max(linked, key=lambda x: x.get("strength", 0)).get("description", "")
                        if linked else ""
                    ),
                },
                "timeline": timeline[:50],  # cap
                "risk_indicators": risk_indicators,
                "network_associations": target.get("associations", []),
                "recommended_actions": self._dossier_recommendations(
                    priority_score, len(linked), risk_indicators,
                ),
                "generated_at": datetime.utcnow().isoformat() + "Z",
            }
            return self._make_response(True, data, "", round(priority_score, 4))

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    @staticmethod
    def _dossier_recommendations(
        priority: float, evidence_count: int, risk_indicators: list,
    ) -> list:
        """Generate recommended investigative actions for a dossier.

        Args:
            priority: Priority score [0, 1].
            evidence_count: Number of linked evidence items.
            risk_indicators: List of risk indicator strings.

        Returns:
            List of recommended actions.
        """
        actions = []
        if priority >= 0.80:
            actions.append("Immediate surveillance authorisation")
            actions.append("Seek preliminary injunction if applicable")
        elif priority >= 0.60:
            actions.append("Enhanced monitoring")
            actions.append("Prepare investigative subpoenas")

        if evidence_count >= 10:
            actions.append("Comprehensive evidence review")
        if evidence_count >= 5:
            actions.append("Begin draft charging document")

        if "Suspicious financial activity" in risk_indicators:
            actions.append("Financial tracing and asset freeze review")
        if "Shell company associations" in risk_indicators:
            actions.append("Corporate registry analysis")
        if "Encrypted communications" in risk_indicators:
            actions.append("Technical surveillance consultation")

        if not actions:
            actions.append("Continue monitoring and evidence collection")

        return actions

    # ------------------------------------------------------------------ #
    # 22. generate_prosecution_strategy
    # ------------------------------------------------------------------ #
    def generate_prosecution_strategy(
        self,
        case_data: dict,
    ) -> dict:
        """Generate optimal prosecution strategy.

        Analyses case strength, venue, charges, and evidence to recommend:
        - Optimal charge structure
        - Venue selection
        - Witness sequencing
        - Timeline estimates
        - Key risks and mitigations

        Args:
            case_data: Dict with defendants, charges, evidence_summary,
                       venue_options, and witness_list.

        Returns:
            Response dict with prosecution strategy.
        """
        try:
            defendants = case_data.get("defendants", [])
            charges = case_data.get("charges", [])
            evidence = case_data.get("evidence_summary", {})
            venues = case_data.get("venue_options", [])
            witnesses = case_data.get("witness_list", [])

            if not defendants or not charges:
                return self._make_response(
                    False, {}, "Defendants and charges required.", 0.0,
                )

            # Case strength assessment
            evidence_strength = min(evidence.get("strength", 5) / 10.0, 1.0)
            n_witnesses = len(witnesses)
            n_documents = evidence.get("document_count", 0)
            n_experts = evidence.get("expert_witness_count", 0)

            # Strength components
            witness_score = min(n_witnesses / 8.0, 1.0)
            document_score = min(math.log10(n_documents + 1) / 4.0, 1.0)
            expert_score = min(n_experts / 3.0, 1.0)

            case_strength = (
                0.35 * evidence_strength +
                0.25 * witness_score +
                0.25 * document_score +
                0.15 * expert_score
            )

            # Venue selection
            venue_result = self.score_jurisdiction_favorability(venues)
            recommended_venue = (
                venue_result["data"].get("recommended_venue", "Undetermined")
                if venue_result["success"] else "Undetermined"
            )

            # Charge severity assessment
            total_max_sentence = sum(
                c.get("max_sentence_years", 0) for c in charges
            )
            charge_severity = min(total_max_sentence / 50.0, 1.0)

            # Strategy recommendation
            if case_strength >= 0.75:
                approach = "Aggressive prosecution — proceed to trial"
            elif case_strength >= 0.55:
                approach = "Balanced — prepare for trial while seeking cooperation"
            elif case_strength >= 0.40:
                approach = "Cautious — build additional evidence before charging"
            else:
                approach = "Defer — continue investigation"

            # Timeline estimate
            complexity = len(defendants) * len(charges)
            if complexity <= 5:
                timeline_months = 8
            elif complexity <= 15:
                timeline_months = 14
            elif complexity <= 30:
                timeline_months = 24
            else:
                timeline_months = 36

            # Risks
            risks = []
            if case_strength < 0.60:
                risks.append("Insufficient evidence for conviction")
            if n_witnesses < 3:
                risks.append("Limited witness testimony")
            if any(c.get("complexity", 0) > 7 for c in charges):
                risks.append("Complex charges may confuse jury")
            if len(defendants) > 3:
                risks.append("Multiple defendants create coordination challenges")

            data = {
                "strategy_id": f"STRAT-{datetime.utcnow().strftime('%Y%m%d-%H%M')}",
                "case_strength": round(case_strength, 4),
                "strength_tier": (
                    "very_strong" if case_strength >= 0.80 else
                    "strong" if case_strength >= 0.65 else
                    "moderate" if case_strength >= 0.45 else "weak"
                ),
                "recommended_approach": approach,
                "recommended_venue": recommended_venue,
                "charge_count": len(charges),
                "total_max_sentence_years": total_max_sentence,
                "charge_severity": round(charge_severity, 4),
                "estimated_timeline_months": timeline_months,
                "key_risks": risks,
                "mitigation_strategies": [
                    "Develop detailed witness prep program",
                    "Prepare comprehensive exhibit list",
                    "Engage subject matter experts early",
                    "Coordinate with parallel civil proceedings",
                ],
                "defendant_count": len(defendants),
                "evidence_strength": round(evidence_strength, 4),
            }
            return self._make_response(True, data, "", round(case_strength, 4))

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    # ------------------------------------------------------------------ #
    # 23. generate_sentence_recommendation
    # ------------------------------------------------------------------ #
    def generate_sentence_recommendation(
        self,
        convictions: list,
    ) -> dict:
        """Generate sentencing analysis and recommendations.

        Based on USSG-style calculations:
        - Offence level computation
        - Criminal history category
        - Adjustments (role, obstruction, cooperation)
        - Recommended range
        - Fine and restitution calculations

        Args:
            convictions: List of dicts with offence_level,
                         criminal_history_points, adjustments,
                         and loss_amount.

        Returns:
            Response dict with sentencing recommendations.
        """
        try:
            if not convictions:
                return self._make_response(
                    False, {}, "No convictions provided.", 0.0,
                )

            sentences = []
            for conv in convictions:
                defendant = conv.get("defendant_name", "unknown")
                base_level = conv.get("offence_level", 1)
                ch_points = conv.get("criminal_history_points", 0)
                adjustments = conv.get("adjustments", {})
                loss_amount = conv.get("loss_amount", 0)

                # Criminal history category (I-VI)
                if ch_points == 0:
                    ch_category = "I"
                elif ch_points <= 1:
                    ch_category = "II"
                elif ch_points <= 3:
                    ch_category = "III"
                elif ch_points <= 5:
                    ch_category = "IV"
                elif ch_points <= 7:
                    ch_category = "V"
                else:
                    ch_category = "VI"

                # Adjustments
                role_adj = adjustments.get("role_in_offence", 0)
                obs_adj = adjustments.get("obstruction", 0)
                coop_adj = adjustments.get("cooperation", 0)
                acceptance_adj = adjustments.get("acceptance_of_responsibility", 0)

                adjusted_level = (
                    base_level + role_adj + obs_adj -
                    coop_adj - acceptance_adj
                )
                adjusted_level = max(1, min(adjusted_level, 43))

                # USSG sentencing table approximation (months)
                # Simplified: base months = level * 6 + category offset
                ch_offset = {"I": 0, "II": 6, "III": 12, "IV": 18, "V": 24, "VI": 30}
                base_months = adjusted_level * 6 + ch_offset.get(ch_category, 0)

                # Range: +/- 15%
                low_end = int(base_months * 0.85)
                high_end = int(base_months * 1.15)

                # Fine: 1x to 2x loss amount (up to statutory max)
                fine = min(loss_amount * 1.5, 10_000_000)

                # Restitution
                restitution = loss_amount

                sentences.append({
                    "defendant": defendant,
                    "adjusted_offence_level": adjusted_level,
                    "criminal_history_category": ch_category,
                    "recommended_range_months": f"{low_end}-{high_end}",
                    "recommended_range_years": round(
                        (low_end + high_end) / 24.0, 1,
                    ),
                    "fine_usd": round(fine, 2),
                    "restitution_usd": round(restitution, 2),
                    "supervised_release_months": max(
                        12, adjusted_level * 3,
                    ),
                    "adjustments_applied": {
                        "role_adjustment": role_adj,
                        "obstruction_adjustment": obs_adj,
                        "cooperation_reduction": coop_adj,
                        "acceptance_reduction": acceptance_adj,
                    },
                })

            data = {
                "sentencing_recommendations": sentences,
                "total_defendants": len(convictions),
                "total_recommended_fines": round(
                    sum(s["fine_usd"] for s in sentences), 2,
                ),
                "total_recommended_restitution": round(
                    sum(s["restitution_usd"] for s in sentences), 2,
                ),
                "guideline_used": "USSG approximate (simplified)",
            }
            return self._make_response(True, data, "", 0.82)

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    # ------------------------------------------------------------------ #
    # 24. generate_intelligence_estimate
    # ------------------------------------------------------------------ #
    def generate_intelligence_estimate(
        self,
        data: dict,
    ) -> dict:
        """Generate a National Intelligence Estimate (NIE)-format assessment.

        Produces a structured intelligence estimate with:
        - Key judgements (likelihood statements)
        - Confidence levels
        - Alternative scenarios
        - Intelligence gaps
        - Warning indicators

        Args:
            data: Dict with topic, key_judgements (list), evidence_quality,
                  source_reliability, alternative_scenarios, and
                  warning_indicators.

        Returns:
            Response dict with NIE-formatted intelligence estimate.
        """
        try:
            topic = data.get("topic", "Unspecified topic")
            judgements = data.get("key_judgements", [])
            ev_quality = min(data.get("evidence_quality", 5) / 10.0, 1.0)
            src_reliability = min(
                data.get("source_reliability", 5) / 10.0, 1.0,
            )
            scenarios = data.get("alternative_scenarios", [])
            warnings = data.get("warning_indicators", [])

            # Overall confidence
            overall_confidence = (ev_quality + src_reliability) / 2.0

            # Process judgements
            processed_judgements = []
            for j in judgements:
                likelihood = j.get("likelihood", "possible")
                confidence = j.get("confidence", "moderate")
                statement = j.get("statement", "")

                # Numeric likelihood mapping
                likelihood_map = {
                    "almost_no_chance": 0.05,
                    "unlikely": 0.25,
                    "roughly_even_chance": 0.50,
                    "likely": 0.70,
                    "highly_likely": 0.85,
                    "almost_certain": 0.95,
                }
                likelihood_score = likelihood_map.get(likelihood, 0.50)

                confidence_map = {
                    "low": 0.33,
                    "moderate": 0.66,
                    "high": 0.90,
                }
                confidence_score = confidence_map.get(confidence, 0.66)

                processed_judgements.append({
                    "statement": statement,
                    "likelihood": likelihood,
                    "likelihood_score": likelihood_score,
                    "confidence": confidence,
                    "confidence_score": confidence_score,
                })

            # Scenario probability estimation
            processed_scenarios = []
            if scenarios:
                total_weight = sum(
                    s.get("probability_weight", 1) for s in scenarios
                )
                for s in scenarios:
                    prob = s.get("probability_weight", 1) / total_weight
                    processed_scenarios.append({
                        "name": s.get("name", ""),
                        "description": s.get("description", ""),
                        "estimated_probability": round(prob, 4),
                        "probability_percent": f"{round(prob * 100, 1)}%",
                    })

            # Estimate classification
            if overall_confidence >= 0.80:
                classification = "HIGH_CONFIDENCE"
            elif overall_confidence >= 0.60:
                classification = "MODERATE_CONFIDENCE"
            elif overall_confidence >= 0.40:
                classification = "LOW_CONFIDENCE"
            else:
                classification = "INSUFFICIENT_EVIDENCE"

            data = {
                "estimate_id": f"NIE-{datetime.utcnow().strftime('%Y-%m-%d')}-{random.Random(self.random_seed).randint(1000, 9999)}",
                "topic": topic,
                "classification": classification,
                "overall_confidence": round(overall_confidence, 4),
                "key_judgements": processed_judgements,
                "alternative_scenarios": processed_scenarios,
                "warning_indicators": [
                    {"indicator": w} for w in warnings
                ],
                "intelligence_gaps": data.get("intelligence_gaps", []),
                "methodology": (
                    "Structured analytic techniques including "
                    "alternative futures analysis and key assumptions check."
                ),
                "disclaimer": (
                    "This estimate represents the analytic judgement of the "
                    "intelligence community. It is subject to revision as "
                    "new information becomes available."
                ),
            }
            return self._make_response(
                True, data, "", round(overall_confidence, 4),
            )

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    # =====================================================================
    # SECTION E — CORRELATION & LINK ANALYSIS
    # =====================================================================

    # ------------------------------------------------------------------ #
    # 25. cross_reference_evidence
    # ------------------------------------------------------------------ #
    def cross_reference_evidence(
        self,
        evidence_sets: list,
    ) -> dict:
        """Cross-reference evidence across multiple sources.

        Identifies corroborating, conflicting, and unique evidence items
        across sources. Computes:
        - Inter-source agreement rate
        - Corroboration chains
        - Conflicts requiring resolution
        - Coverage gaps

        Args:
            evidence_sets: List of dicts, each with "source_name" and
                           "evidence_items" (list of dicts with "id",
                           "claim", and "confidence").

        Returns:
            Response dict with cross-reference analysis.
        """
        try:
            if not evidence_sets or len(evidence_sets) < 2:
                return self._make_response(
                    False, {}, "At least 2 evidence sets required.", 0.0,
                )

            # Index all claims by source
            all_claims: Dict[str, Dict[str, dict]] = {}
            source_names = []
            for es in evidence_sets:
                src = es.get("source_name", "unknown")
                source_names.append(src)
                all_claims[src] = {}
                for item in es.get("evidence_items", []):
                    claim_id = str(item.get("id", item.get("claim", "")))
                    all_claims[src][claim_id] = item

            # Find overlapping claims
            all_ids = set()
            for src_claims in all_claims.values():
                all_ids.update(src_claims.keys())

            corroborated = []
            conflicting = []
            unique = []

            for claim_id in all_ids:
                present_in = [
                    src for src in source_names
                    if claim_id in all_claims[src]
                ]

                if len(present_in) >= 2:
                    # Check for corroboration vs conflict
                    confidences = []
                    claims_detail = []
                    for src in present_in:
                        item = all_claims[src][claim_id]
                        confidences.append(
                            float(item.get("confidence", 0.5)),
                        )
                        claims_detail.append({
                            "source": src,
                            "claim": item.get("claim", ""),
                            "confidence": item.get("confidence", 0.5),
                        })

                    # If confidences are all in same direction, corroborate
                    # If mix of high-confidence conflicting claims, conflict
                    avg_conf = statistics.mean(confidences)
                    std_conf = statistics.stdev(confidences) if len(confidences) > 1 else 0.0

                    if std_conf < 0.3:
                        corroborated.append({
                            "claim_id": claim_id,
                            "sources": present_in,
                            "claim_details": claims_detail,
                            "avg_confidence": round(avg_conf, 4),
                            "corroboration_strength": len(present_in),
                        })
                    else:
                        conflicting.append({
                            "claim_id": claim_id,
                            "sources": present_in,
                            "claim_details": claims_detail,
                            "confidence_variance": round(std_conf, 4),
                            "resolution_needed": True,
                        })
                else:
                    src = present_in[0] if present_in else "unknown"
                    item = all_claims[src].get(claim_id, {})
                    unique.append({
                        "claim_id": claim_id,
                        "source": src,
                        "claim": item.get("claim", ""),
                        "confidence": item.get("confidence", 0.5),
                    })

            # Agreement rate
            total_claims = len(all_ids)
            corroboration_rate = len(corroborated) / total_claims if total_claims else 0.0
            conflict_rate = len(conflicting) / total_claims if total_claims else 0.0

            # Coverage per source
            source_coverage = {
                src: len(claims) / total_claims if total_claims else 0.0
                for src, claims in all_claims.items()
            }

            # Overall agreement (Jaccard-like)
            pairwise_agreements = []
            for i in range(len(source_names)):
                for j in range(i + 1, len(source_names)):
                    s1 = source_names[i]
                    s2 = source_names[j]
                    ids1 = set(all_claims[s1].keys())
                    ids2 = set(all_claims[s2].keys())
                    union = ids1 | ids2
                    intersection = ids1 & ids2
                    jaccard = len(intersection) / len(union) if union else 0.0
                    pairwise_agreements.append({
                        "source_pair": f"{s1} <-> {s2}",
                        "jaccard_similarity": round(jaccard, 4),
                        "shared_claims": len(intersection),
                    })

            data = {
                "sources_analyzed": len(evidence_sets),
                "total_unique_claims": total_claims,
                "corroborated_claims": corroborated,
                "corroboration_rate": round(corroboration_rate, 4),
                "conflicting_claims": conflicting,
                "conflict_rate": round(conflict_rate, 4),
                "unique_claims": unique,
                "source_coverage": {
                    k: round(v, 4) for k, v in source_coverage.items()
                },
                "pairwise_agreements": pairwise_agreements,
                "mean_pairwise_agreement": round(
                    statistics.mean(
                        a["jaccard_similarity"] for a in pairwise_agreements
                    ), 4,
                ) if pairwise_agreements else 0.0,
                "assessment": (
                    f"{len(corroborated)} claims corroborated across sources "
                    f"({corroboration_rate:.1%}). "
                    f"{len(conflicting)} conflicts require resolution."
                ),
            }
            return self._make_response(
                True, data, "", round(corroboration_rate, 4),
            )

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    # ------------------------------------------------------------------ #
    # 26. find_common_entities
    # ------------------------------------------------------------------ #
    def find_common_entities(
        self,
        datasets: list,
    ) -> dict:
        """Entity resolution across multiple datasets.

        Identifies common entities across datasets using:
        - Exact name matching
        - Fuzzy matching via normalised string comparison
        - Shared attribute matching (email, phone, address)
        - Record linkage scoring

        Args:
            datasets: List of dicts, each with "dataset_name" and
                      "records" (list of dicts with entity attributes).

        Returns:
            Response dict with matched entities and linkage scores.
        """
        try:
            if not datasets or len(datasets) < 2:
                return self._make_response(
                    False, {}, "At least 2 datasets required.", 0.0,
                )

            entity_index: Dict[str, List[dict]] = {}

            # Index all entities from all datasets
            for ds in datasets:
                ds_name = ds.get("dataset_name", "unknown")
                for record in ds.get("records", []):
                    entity_name = str(record.get("name", ""))
                    if not entity_name:
                        continue

                    # Normalised key for matching
                    norm_key = entity_name.lower().strip()
                    # Remove common noise
                    for char in ",.;()[]{}":
                        norm_key = norm_key.replace(char, "")
                    norm_key = " ".join(norm_key.split())  # normalise whitespace

                    entry = {
                        "dataset": ds_name,
                        "name": entity_name,
                        "attributes": record,
                    }
                    entity_index.setdefault(norm_key, []).append(entry)

            # Find cross-dataset matches
            matches = []
            unique_entities = []

            for norm_key, entries in entity_index.items():
                datasets_present = set(e["dataset"] for e in entries)

                if len(datasets_present) >= 2:
                    # Cross-dataset match
                    # Compute linkage score based on attribute overlap
                    linkage_score = self._compute_linkage_score(
                        [e["attributes"] for e in entries],
                    )

                    matches.append({
                        "canonical_name": entries[0]["name"],
                        "normalised_key": norm_key,
                        "datasets_found": sorted(datasets_present),
                        "occurrence_count": len(entries),
                        "linkage_score": round(linkage_score, 4),
                        "linked_records": [
                            {"dataset": e["dataset"], "name": e["name"]}
                            for e in entries
                        ],
                    })
                else:
                    unique_entities.append({
                        "name": entries[0]["name"],
                        "dataset": entries[0]["dataset"],
                        "attributes": entries[0]["attributes"],
                    })

            # Sort by linkage score
            matches.sort(key=lambda x: x["linkage_score"], reverse=True)

            # Match coverage
            total_records = sum(
                len(ds.get("records", [])) for ds in datasets
            )
            matched_records = sum(m["occurrence_count"] for m in matches)

            data = {
                "datasets_analyzed": len(datasets),
                "total_entities_indexed": len(entity_index),
                "cross_dataset_matches": matches,
                "match_count": len(matches),
                "unique_entities": unique_entities[:50],
                "unique_count": len(unique_entities),
                "match_coverage": round(
                    matched_records / total_records, 4,
                ) if total_records else 0.0,
                "high_confidence_matches": [
                    m for m in matches if m["linkage_score"] >= 0.80
                ],
            }
            return self._make_response(True, data, "", 0.82)

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    @staticmethod
    def _compute_linkage_score(records: list) -> float:
        """Compute entity linkage score based on attribute overlap.

        Args:
            records: List of record dicts to compare.

        Returns:
            Linkage score in [0, 1].
        """
        if len(records) < 2:
            return 1.0

        score = 0.0
        comparisons = 0

        # Compare all pairs
        for i in range(len(records)):
            for j in range(i + 1, len(records)):
                r1 = records[i]
                r2 = records[j]
                matches = 0
                fields = 0

                for key in set(r1.keys()) & set(r2.keys()):
                    if key == "name":
                        continue
                    fields += 1
                    v1 = str(r1[key]).lower().strip()
                    v2 = str(r2[key]).lower().strip()
                    if v1 == v2 and v1:
                        matches += 1

                if fields > 0:
                    score += matches / fields
                    comparisons += 1

        return (score / comparisons) if comparisons > 0 else 0.5

    # ------------------------------------------------------------------ #
    # 27. calculate_conspiracy_strength
    # ------------------------------------------------------------------ #
    def calculate_conspiracy_strength(
        self,
        communications: list,
    ) -> dict:
        """Calculate conspiracy network strength score.

        Analyses communications for conspiracy indicators:
        - Network density (how connected are co-conspirators)
        - Communication frequency patterns
        - Code word usage
        - Secrecy indicators (encryption, burner phones)
        - Overt acts timeline
        - Role hierarchy (central coordinator detection)

        Args:
            communications: List of dicts with sender, recipient,
                            timestamp, content_flags, and secrecy_indicators.

        Returns:
            Response dict with conspiracy strength analysis.
        """
        try:
            if not communications:
                return self._make_response(
                    False, {}, "No communications provided.", 0.0,
                )

            # Extract participants
            participants: set = set()
            adjacency: Dict[str, set] = {}
            secrecy_count = 0
            code_word_count = 0
            overt_acts = 0
            timestamps = []

            for comm in communications:
                sender = str(comm.get("sender", ""))
                recipient = str(comm.get("recipient", ""))
                if not sender or not recipient:
                    continue

                participants.add(sender)
                participants.add(recipient)
                adjacency.setdefault(sender, set()).add(recipient)
                adjacency.setdefault(recipient, set()).add(sender)

                flags = comm.get("content_flags", [])
                if "code_word" in flags:
                    code_word_count += 1
                if "overt_act" in flags:
                    overt_acts += 1

                if comm.get("secrecy_indicators"):
                    secrecy_count += 1

                ts = comm.get("timestamp")
                if ts:
                    timestamps.append(str(ts))

            n_participants = len(participants)
            if n_participants < 2:
                return self._make_response(
                    False, {}, "Need at least 2 participants.", 0.0,
                )

            # Network density
            possible_edges = n_participants * (n_participants - 1) / 2.0
            actual_edges = sum(
                len(adjacency.get(p, set())) for p in participants
            ) / 2.0  # undirected
            density = actual_edges / possible_edges if possible_edges > 0 else 0.0

            # Central coordinator (highest degree)
            degrees = {
                p: len(adjacency.get(p, set())) for p in participants
            }
            max_degree_participant = max(degrees.items(), key=lambda x: x[1])

            # Communication frequency
            n_comms = len(communications)
            frequency_score = min(n_comms / (n_participants * 10.0), 1.0)

            # Secrecy ratio
            secrecy_ratio = secrecy_count / n_comms if n_comms > 0 else 0.0

            # Code word ratio
            code_ratio = code_word_count / n_comms if n_comms > 0 else 0.0

            # Overt acts score
            overt_score = min(overt_acts / 5.0, 1.0)

            # Composite conspiracy strength
            composite = (
                0.25 * density +
                0.20 * frequency_score +
                0.20 * secrecy_ratio +
                0.15 * code_ratio +
                0.10 * overt_score +
                0.10 * min(max_degree_participant[1] / (n_participants - 1), 1.0)
            )

            tier = (
                "very_strong" if composite >= 0.80 else
                "strong" if composite >= 0.60 else
                "moderate" if composite >= 0.40 else
                "weak" if composite >= 0.20 else "insufficient"
            )

            # Generate co-conspirator list sorted by degree
            sorted_participants = sorted(
                degrees.items(), key=lambda x: x[1], reverse=True,
            )

            data = {
                "conspiracy_strength_score": round(composite, 4),
                "strength_tier": tier,
                "participant_count": n_participants,
                "communication_count": n_comms,
                "network_density": round(density, 4),
                "frequency_score": round(frequency_score, 4),
                "secrecy_ratio": round(secrecy_ratio, 4),
                "code_word_ratio": round(code_ratio, 4),
                "overt_acts_count": overt_acts,
                "overt_acts_score": round(overt_score, 4),
                "likely_coordinator": {
                    "participant": max_degree_participant[0],
                    "degree": max_degree_participant[1],
                },
                "participants_by_centrality": [
                    {"name": p, "degree": d, "tier": self._participant_tier(
                        d, max(degrees.values()) if degrees else 1,
                    )}
                    for p, d in sorted_participants
                ],
                "timeline_span": (
                    f"{timestamps[0]} to {timestamps[-1]}"
                    if len(timestamps) >= 2 else "insufficient data"
                ),
                "racketeering_indicators": {
                    "pattern_of_racketeering": density > 0.3 and overt_acts >= 2,
                    "enterprise_existence": n_participants >= 3,
                    "interstate_nexus": code_word_count > 0,
                },
            }
            return self._make_response(True, data, "", round(composite, 4))

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)

    @staticmethod
    def _participant_tier(degree: int, max_degree: int) -> str:
        """Classify participant tier based on degree centrality.

        Args:
            degree: Node degree.
            max_degree: Maximum degree in network.

        Returns:
            Tier classification string.
        """
        if max_degree == 0:
            return "peripheral"
        ratio = degree / max_degree
        if ratio >= 0.8:
            return "leader"
        elif ratio >= 0.5:
            return "core"
        elif ratio >= 0.2:
            return "active"
        return "peripheral"

    # ------------------------------------------------------------------ #
    # 28. predict_likely_targets
    # ------------------------------------------------------------------ #
    def predict_likely_targets(
        self,
        historical: list,
        current: list,
    ) -> dict:
        """Predict likely future targets based on historical patterns.

        Uses similarity matching between current entities and historical
        prosecuted targets. Computes:
        - Feature similarity scores
        - Risk profile matching
        - Behavioural pattern similarity
        - Priority-ranked predictions

        Args:
            historical: List of dicts representing past targets with
                        features and outcomes (convicted, charged, etc.).
            current: List of dicts representing current entities of
                     interest with features.

        Returns:
            Response dict with predicted likelihood rankings.
        """
        try:
            if not historical or not current:
                return self._make_response(
                    False, {}, "Historical and current data required.", 0.0,
                )

            # Extract common feature keys
            feature_keys = set()
            for h in historical[:10]:
                feature_keys.update(h.get("features", {}).keys())
            for c in current[:10]:
                feature_keys.update(c.get("features", {}).keys())
            feature_keys = sorted(feature_keys)

            if not feature_keys:
                return self._make_response(
                    False, {}, "No common features found.", 0.0,
                )

            # Build historical profile (mean features of convicted targets)
            convicted = [
                h for h in historical
                if h.get("outcome", "").lower() in ("convicted", "charged")
            ]
            if not convicted:
                convicted = historical  # fallback

            # Compute mean profile of convicted targets
            profile = {}
            for key in feature_keys:
                vals = [
                    float(h.get("features", {}).get(key, 0))
                    for h in convicted
                    if h.get("features", {}).get(key) is not None
                ]
                profile[key] = statistics.mean(vals) if vals else 0.0

            # Compute standard deviation for normalisation
            profile_std = {}
            for key in feature_keys:
                vals = [
                    float(h.get("features", {}).get(key, 0))
                    for h in convicted
                    if h.get("features", {}).get(key) is not None
                ]
                profile_std[key] = statistics.stdev(vals) if len(vals) > 1 else 1.0

            # Score each current entity against profile
            predictions = []
            for entity in current:
                entity_features = entity.get("features", {})
                name = entity.get("name", "unknown")
                entity_id = entity.get("id", name)

                # Euclidean distance from profile (normalised)
                dist_sq = 0.0
                matched_features = 0
                for key in feature_keys:
                    val = entity_features.get(key)
                    if val is not None:
                        v = float(val)
                        std = profile_std.get(key, 1.0)
                        if std == 0:
                            std = 1.0
                        normalised_diff = (v - profile.get(key, 0)) / std
                        dist_sq += normalised_diff ** 2
                        matched_features += 1

                distance = math.sqrt(dist_sq)
                # Convert distance to similarity score [0, 1]
                # Using Gaussian kernel
                similarity = math.exp(-distance / 2.0)

                # Base rate from historical
                base_rate = len(convicted) / len(historical) if historical else 0.5

                # Combined likelihood = similarity * base_rate
                likelihood = similarity * (0.5 + 0.5 * base_rate)
                likelihood = min(likelihood, 1.0)

                predictions.append({
                    "entity_id": entity_id,
                    "name": name,
                    "likelihood_score": round(likelihood, 4),
                    "similarity_to_profile": round(similarity, 4),
                    "profile_distance": round(distance, 4),
                    "features_matched": matched_features,
                    "total_features": len(feature_keys),
                    "risk_tier": (
                        "very_high" if likelihood >= 0.80 else
                        "high" if likelihood >= 0.60 else
                        "moderate" if likelihood >= 0.40 else
                        "low" if likelihood >= 0.20 else "minimal"
                    ),
                })

            predictions.sort(
                key=lambda x: x["likelihood_score"], reverse=True,
            )

            data = {
                "historical_targets": len(historical),
                "convicted_targets": len(convicted),
                "base_rate": round(
                    len(convicted) / len(historical), 4,
                ) if historical else 0.0,
                "feature_keys_used": feature_keys,
                "predictions": predictions,
                "top_targets": [
                    {
                        "entity": p["name"],
                        "likelihood": p["likelihood_score"],
                        "tier": p["risk_tier"],
                    }
                    for p in predictions[:5]
                ],
                "methodology": (
                    "Profile-based similarity matching using "
                    "normalised Euclidean distance with Gaussian kernel. "
                    "Historical convicted target profile used as reference."
                ),
            }
            return self._make_response(
                True, data, "", round(
                    predictions[0]["likelihood_score"] if predictions else 0.0, 4,
                ),
            )

        except Exception as exc:
            return self._make_response(False, {}, str(exc), 0.0)
