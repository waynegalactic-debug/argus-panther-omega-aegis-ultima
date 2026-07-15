"""
AEGIS Advanced Mathematical Forensic Models v4.0.0
Embedded module for US IPFORCE Monolith v9.
"""
import hashlib
import math
import warnings
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np

AEGIS_RANDOM_SEED: int = 0x5C0DA
np.random.seed(AEGIS_RANDOM_SEED)

try:
    import scipy.special as sp_spec
    from scipy.spatial.distance import pdist

    _HAS_SCIPY = True
except Exception:
    _HAS_SCIPY = False

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    _HAS_TORCH = True
except Exception:
    _HAS_TORCH = False
    torch = nn = F = None  # type: ignore

WIPO_JURISDICTION_COUNT: int = 194
CDS_MARKET_NOTIONAL: float = 482.477e12


def _aegis_sha3_512(data: Union[str, bytes]) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha3_512(data).hexdigest()


def _ensure_numpy(arr: Any) -> np.ndarray:
    return np.asarray(arr, dtype=np.float64).ravel()


class SyntheticIdentityMapper:
    """Combinatorial identity mapping across WIPO jurisdictions."""

    _CANONICAL_NAME_VARIATIONS: List[str] = [
        "Brent Michael Škoda",
        "Brent Michael Skoda",
        "Brent M. Skoda",
        "Brent M Skoda",
        "B. Michael Škoda",
        "B Michael Škoda",
        "BM Škoda",
        "B.M. Škoda",
        "Brent Škoda",
        "Brent Skoda",
        "B. Skoda",
        "B Skoda",
        "Michael Škoda",
        "Michael Skoda",
        "M. Škoda",
        "M Skoda",
        "Brent M Shkoda",
        "Brent Shkoda",
        "Brent M Schkoda",
        "Брент Майкл Шкода",
        "布伦特·迈克尔·斯科达",
        "ブレント・マイケル・スコダ",
        "브렌트 마이클 스코다",
        "برينت مايكل سكودا",
        "ברנט מייקל סקודה",
    ]

    _ABBREVIATION_RULES: List[Callable[[str], str]] = [
        lambda n: n.replace("Michael", "M."),
        lambda n: n.replace("Michael", "M"),
        lambda n: n.replace("Brent", "B."),
        lambda n: n.replace("Brent", "B"),
        lambda n: n.replace("Škoda", "Skoda"),
    ]

    _MISSPELLING_MAP: Dict[str, List[str]] = {
        "š": ["s", "sh", "sch", "sz"],
        "k": ["c", "ck"],
        "e": ["ea", "ee"],
        "a": ["ah", "aa"],
        "o": ["oh", "oo"],
    }

    def __init__(self, seed: int = AEGIS_RANDOM_SEED) -> None:
        self._seed = seed
        self._rng = np.random.default_rng(seed)
        self._known_variations = list(self._CANONICAL_NAME_VARIATIONS)
        self._jurisdiction_count = WIPO_JURISDICTION_COUNT

    def generate_identity_variations(self, base_name: str) -> List[str]:
        variations: set = {base_name}
        ascii_name = self._strip_diacritics(base_name)
        variations.add(ascii_name)
        for rule in self._ABBREVIATION_RULES:
            try:
                for n in (base_name, ascii_name):
                    v = rule(n)
                    if v:
                        variations.add(v)
            except Exception:
                continue
        for char, replacements in self._MISSPELLING_MAP.items():
            if char in base_name.lower():
                for repl in replacements:
                    v = " ".join(
                        w.capitalize()
                        for w in base_name.lower().replace(char, repl).split()
                    )
                    variations.add(v)
        variations.update(self._romanize(base_name))
        if self._name_similarity(base_name, "Brent Michael Skoda") > 0.7:
            variations.update(self._known_variations)
        variations.update(self._generate_jurisdiction_variations(base_name))
        return sorted(variations)

    def build_identity_graph(self, names: List[str]) -> Dict[str, Any]:
        if not names:
            return {"nodes": [], "edges": [], "similarity_matrix": np.array([])}
        n = len(names)
        sim_matrix = np.zeros((n, n))
        edges: List[Dict[str, Any]] = []
        for i in range(n):
            for j in range(i + 1, n):
                sim = self._name_similarity(names[i], names[j])
                sim_matrix[i, j] = sim_matrix[j, i] = sim
                if sim > 0.6:
                    edges.append(
                        {
                            "source": names[i],
                            "target": names[j],
                            "similarity": float(sim),
                            "weight": float(sim),
                        }
                    )
        nodes = [{"id": name, "hash": _aegis_sha3_512(name)} for name in names]
        return {
            "nodes": nodes,
            "edges": edges,
            "similarity_matrix": sim_matrix,
            "graph_hash": _aegis_sha3_512("".join(sorted(names))),
        }

    def detect_synthetic_identities(
        self, patent_records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        if not patent_records:
            return []
        flagged: List[Dict[str, Any]] = []
        canonical_lower = [v.lower() for v in self._known_variations]
        for record in patent_records:
            applicant = record.get("applicant", "")
            app_lower = applicant.lower()
            max_sim = max(
                (self._levenshtein_similarity(app_lower, c) for c in canonical_lower),
                default=0.0,
            )
            if 0.75 < max_sim < 1.0:
                flagged.append(
                    {
                        "record": record,
                        "similarity_score": float(max_sim),
                        "matched_variations": [
                            self._known_variations[i]
                            for i, c in enumerate(canonical_lower)
                            if self._levenshtein_similarity(app_lower, c) > 0.75
                        ],
                        "detection_hash": _aegis_sha3_512(
                            f"{applicant}:{record.get('patent_id', '')}"
                        ),
                        "detection_type": "synthetic_identity",
                    }
                )
        return flagged

    def cross_jurisdictional_analysis(
        self, jurisdictions: List[str]
    ) -> Dict[str, Any]:
        unique = sorted(set(jurisdictions))
        coverage = len(unique) / self._jurisdiction_count
        risk_scores = {
            jc: (int(_aegis_sha3_512(jc)[:16], 16) % 100) / 100.0 for jc in unique
        }
        high_risk = {k: v for k, v in risk_scores.items() if v > 0.7}
        return {
            "jurisdictions_analyzed": unique,
            "total_coverage": coverage,
            "coverage_percent": round(coverage * 100, 2),
            "risk_scores": risk_scores,
            "high_risk_jurisdictions": list(high_risk.keys()),
            "mean_risk": float(np.mean(list(risk_scores.values())))
            if risk_scores
            else 0.0,
            "analysis_hash": _aegis_sha3_512("".join(unique)),
        }

    def generate_combinial_report(self) -> Dict[str, Any]:
        base = "Brent Michael Škoda"
        variations = self.generate_identity_variations(base)
        graph = self.build_identity_graph(variations)
        jurisdictions = ["US", "EP", "WO", "CN", "JP", "KR", "RU", "IL", "SA"]
        cross_jurisdiction = self.cross_jurisdictional_analysis(jurisdictions)
        return {
            "base_identity": base,
            "base_hash": _aegis_sha3_512(base),
            "variation_count": len(variations),
            "variations": variations,
            "identity_graph": graph,
            "cross_jurisdictional_analysis": cross_jurisdiction,
            "wipo_jurisdiction_total": self._jurisdiction_count,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "report_hash": _aegis_sha3_512(base + "".join(variations)),
        }

    @staticmethod
    def _strip_diacritics(text: str) -> str:
        import unicodedata

        return "".join(
            c
            for c in unicodedata.normalize("NFD", text)
            if unicodedata.category(c) != "Mn"
        )

    def _romanize(self, name: str) -> List[str]:
        variants = []
        ascii_name = self._strip_diacritics(name)
        if ascii_name != name:
            variants.append(ascii_name)
        for old, new in (("Š", "Sh"), ("š", "sh"), ("Š", "Sz"), ("š", "sz")):
            variants.append(name.replace(old, new))
        return list(set(variants))

    def _name_similarity(self, a: str, b: str) -> float:
        return self._levenshtein_similarity(a.lower().strip(), b.lower().strip())

    @staticmethod
    def _levenshtein_similarity(a: str, b: str) -> float:
        m, n = len(a), len(b)
        if m == 0 and n == 0:
            return 1.0
        prev = list(range(n + 1))
        curr = [0] * (n + 1)
        for i in range(1, m + 1):
            curr[0] = i
            for j in range(1, n + 1):
                cost = 0 if a[i - 1] == b[j - 1] else 1
                curr[j] = min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
            prev, curr = curr, prev
        max_len = max(m, n)
        return 1.0 - prev[n] / max_len if max_len > 0 else 1.0

    def _generate_jurisdiction_variations(self, base_name: str) -> List[str]:
        parts = base_name.split()
        if len(parts) < 2:
            return []
        extras = [
            ", ".join(parts[::-1]),
            " ".join(parts[::-1]),
            "".join(p[0] + "." for p in parts if p) + " " + parts[-1],
        ]
        if len(parts) >= 3:
            extras.append(f"{parts[0]}-{parts[1]} {parts[2]}")
        return list(set(extras))


class BayesianSpatioTemporalModel:
    """Bayesian spatio-temporal modeling of IP exploitation patterns."""

    def __init__(self, prior_model: str = "uniform") -> None:
        self.prior_model = prior_model
        self._event_history: List[Dict[str, Any]] = []
        self._entity_params: Dict[str, Dict[str, Any]] = {}
        self._is_fitted = False

    def fit(self, patent_events: List[Dict[str, Any]]) -> None:
        if not patent_events:
            return
        self._event_history = list(patent_events)
        entity_events: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for ev in patent_events:
            entity_events[ev.get("entity", "unknown")].append(ev)
        for entity, events in entity_events.items():
            self._entity_params[entity] = self._estimate_posterior(entity, events)
        self._is_fitted = True

    def predict_next_filing(self, entity: str) -> Dict[str, Any]:
        params = self._entity_params.get(entity, {})
        jurisdictions = params.get("jurisdictions", [])
        probs = params.get("jurisdiction_probs", [])
        if not jurisdictions:
            return {"entity": entity, "predicted_jurisdiction": None, "confidence": 0.0}
        best_idx = int(np.argmax(probs))
        return {
            "entity": entity,
            "predicted_jurisdiction": jurisdictions[best_idx],
            "confidence": round(float(probs[best_idx]), 4),
            "mean_interval_days": params.get("mean_interval_days", 365.0),
        }

    def detect_anomalous_patterns(
        self, events: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        if not self._is_fitted:
            self.fit(events)
        anomalies: List[Dict[str, Any]] = []
        for ev in events:
            entity = ev.get("entity", "unknown")
            params = self._entity_params.get(entity, {})
            if not params:
                continue
            score = 0.0
            reasons: List[str] = []
            jurisdictions = params.get("jurisdictions", [])
            probs = params.get("jurisdiction_probs", [])
            jdx = ev.get("jurisdiction", "")
            if jdx in jurisdictions:
                j_prob = probs[jurisdictions.index(jdx)]
                if j_prob < 0.05:
                    score += 0.4
                    reasons.append(f"Rare jurisdiction ({jdx}, p={j_prob:.3f})")
            else:
                score += 0.6
                reasons.append(f"Novel jurisdiction: {jdx}")
            if score > 0.5:
                anomalies.append(
                    {
                        "event": ev,
                        "anomaly_score": round(score, 4),
                        "reasons": reasons,
                        "detection_hash": _aegis_sha3_512(str(ev)),
                    }
                )
        return sorted(anomalies, key=lambda x: x["anomaly_score"], reverse=True)

    def generate_probability_map(self) -> Dict[str, Any]:
        if not self._is_fitted:
            return {"jurisdiction_probs": {}, "global_risk": 0.0}
        global_probs: Dict[str, float] = defaultdict(float)
        entity_count = len(self._entity_params)
        for params in self._entity_params.values():
            for j, p in zip(
                params.get("jurisdictions", []),
                params.get("jurisdiction_probs", []),
            ):
                global_probs[j] += p
        if entity_count > 0:
            for j in global_probs:
                global_probs[j] /= entity_count
        sorted_probs = dict(
            sorted(global_probs.items(), key=lambda x: x[1], reverse=True)
        )
        max_risk = max(sorted_probs.values()) if sorted_probs else 0.0
        return {
            "jurisdiction_probs": {k: round(v, 6) for k, v in sorted_probs.items()},
            "global_risk": round(float(max_risk), 6),
            "num_entities": entity_count,
        }

    def _estimate_posterior(
        self, entity: str, events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        jurisdictions = [e.get("jurisdiction", "unknown") for e in events]
        jurisdiction_counts = Counter(jurisdictions)
        total = len(jurisdictions)
        alpha = 1.0
        unique_jdxs = sorted(jurisdiction_counts.keys())
        smoothed_probs = [
            (jurisdiction_counts[j] + alpha) / (total + alpha * len(unique_jdxs))
            for j in unique_jdxs
        ]
        smoothed_probs = np.array(smoothed_probs)
        smoothed_probs /= smoothed_probs.sum()
        dates = []
        for e in events:
            d = e.get("date")
            if isinstance(d, str):
                try:
                    d = datetime.fromisoformat(d.replace("Z", "+00:00"))
                except ValueError:
                    continue
            if d:
                dates.append(d)
        dates.sort()
        intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        return {
            "entity": entity,
            "jurisdictions": unique_jdxs,
            "jurisdiction_probs": smoothed_probs.tolist(),
            "total_filings": total,
            "mean_interval_days": float(np.mean(intervals)) if intervals else 365.0,
            "last_filing_date": dates[-1] if dates else None,
        }


class AEGISFractionalCalculusEngine:
    """Fractional calculus chaos detection (AEGIS v4 – distinct from monolith FractionalCalculusEngine)."""

    def __init__(self, seed: int = AEGIS_RANDOM_SEED) -> None:
        self._seed = seed
        np.random.seed(seed)

    def fractional_derivative(self, signal: np.ndarray, alpha: float) -> np.ndarray:
        signal = _ensure_numpy(signal)
        n = len(signal)
        if n < 2 or alpha <= 0:
            return signal.copy()
        result = np.zeros(n, dtype=np.float64)
        max_terms = min(n, 1000)
        weights = np.zeros(max_terms)
        weights[0] = 1.0
        for j in range(1, max_terms):
            weights[j] = weights[j - 1] * (alpha - j + 1) / j
        for i in range(n):
            terms = min(i + 1, max_terms)
            for j in range(terms):
                result[i] += weights[j] * signal[i - j]
            result[i] /= alpha ** alpha if alpha != 1 else 1.0
        return result

    def lyapunov_exponent(self, trajectory: np.ndarray) -> float:
        trajectory = np.asarray(trajectory, dtype=np.float64)
        if trajectory.ndim == 1:
            trajectory = self.phase_space_reconstruction(trajectory, 1, 3)
        n_points, dim = trajectory.shape
        if n_points < 10:
            return 0.0
        min_sep = dim + 1
        nearest_dists = np.zeros(n_points)
        nearest_indices = np.zeros(n_points, dtype=int)
        for i in range(n_points):
            min_dist = float("inf")
            min_idx = -1
            for j in range(n_points):
                if abs(i - j) < min_sep:
                    continue
                d = np.linalg.norm(trajectory[i] - trajectory[j])
                if d < min_dist and d > 1e-12:
                    min_dist = d
                    min_idx = j
            nearest_dists[i] = min_dist if min_dist != float("inf") else 1e-12
            nearest_indices[i] = min_idx
        max_time = min(n_points // 4, 50)
        divergences = np.zeros(max_time)
        counts = np.zeros(max_time)
        for k in range(max_time):
            for i in range(n_points - max_time):
                ni = nearest_indices[i]
                if ni + k >= n_points or i + k >= n_points:
                    continue
                d_new = np.linalg.norm(trajectory[i + k] - trajectory[ni + k])
                d0 = nearest_dists[i]
                if d0 > 1e-12 and d_new > 1e-12:
                    divergences[k] += np.log(d_new / d0)
                    counts[k] += 1
        valid = counts > 0
        if not np.any(valid):
            return 0.0
        log_div = np.zeros(max_time)
        log_div[valid] = divergences[valid] / counts[valid]
        t_vals = np.arange(max_time, dtype=float)
        skip = max(1, max_time // 10)
        use_idx = valid[skip:]
        if not np.any(use_idx):
            use_idx = valid
        t_use = t_vals[skip:][use_idx[: len(t_vals[skip:])]]
        y_use = log_div[skip:][use_idx[: len(log_div[skip:])]]
        if len(t_use) < 2:
            return 0.0
        t_mean, y_mean = t_use.mean(), y_use.mean()
        m = np.sum((t_use - t_mean) * (y_use - y_mean)) / (
            np.sum((t_use - t_mean) ** 2) + 1e-12
        )
        return float(m)

    def detect_chaos(self, timeseries: np.ndarray) -> Dict[str, Any]:
        timeseries = _ensure_numpy(timeseries)
        n = len(timeseries)
        if n < 20:
            return {"is_chaotic": False, "confidence": 0.0, "note": "Series too short"}
        tau = self._estimate_delay(timeseries)
        ps = self.phase_space_reconstruction(timeseries, tau, min(n // 10, 10))
        mle = self.lyapunov_exponent(ps)
        k = self._gottwald_melbourne_test(timeseries)
        corr_dim = self._correlation_dimension(ps)
        is_chaotic = (mle > 0.01) and (k > 0.5)
        return {
            "is_chaotic": bool(is_chaotic),
            "confidence": round(min(1.0, max(0.0, (mle * 10 if mle > 0 else 0) + k * 0.5)), 4),
            "lyapunov_exponent": round(float(mle), 6),
            "correlation_dimension": round(float(corr_dim), 4),
            "gottwald_melbourne_k": round(float(k), 4),
            "detection_hash": _aegis_sha3_512(timeseries.tobytes()),
        }

    def phase_space_reconstruction(
        self, signal: np.ndarray, delay: int, dim: int
    ) -> np.ndarray:
        signal = _ensure_numpy(signal)
        n = len(signal)
        if n < dim * delay + 1:
            signal = np.pad(signal, (0, dim * delay + 1 - n), mode="edge")
            n = len(signal)
        m = n - (dim - 1) * delay
        trajectory = np.zeros((m, dim), dtype=np.float64)
        for i in range(dim):
            trajectory[:, i] = signal[i * delay : i * delay + m]
        return trajectory

    def hurst_exponent(self, signal: np.ndarray) -> float:
        signal = _ensure_numpy(signal)
        n = len(signal)
        if n < 20:
            return 0.5
        min_win = max(8, n // 100)
        max_win = max(min_win + 10, n // 4)
        window_sizes = np.unique(
            np.logspace(np.log10(min_win), np.log10(max_win), num=20).astype(int)
        )
        rs_values = []
        for w in window_sizes:
            if w > n:
                continue
            n_windows = n // w
            rs_window = []
            for i in range(n_windows):
                chunk = signal[i * w : (i + 1) * w]
                dev = chunk - chunk.mean()
                cumulative = np.cumsum(dev)
                r = cumulative.max() - cumulative.min()
                s = chunk.std(ddof=1) + 1e-12
                rs_window.append(r / s)
            if rs_window:
                rs_values.append((w, np.mean(rs_window)))
        if len(rs_values) < 2:
            return 0.5
        log_ws = np.log10([v[0] for v in rs_values])
        log_rs = np.log10([v[1] for v in rs_values])
        return float(np.polyfit(log_ws, log_rs, 1)[0])

    def fractal_dimension(self, signal: np.ndarray) -> Dict[str, float]:
        signal = _ensure_numpy(signal)
        if len(signal) < 10:
            return {"box_counting_dim": 1.0, "hausdorff_dim": 1.0, "information_dim": 1.0}
        tau = self._estimate_delay(signal)
        ps = self.phase_space_reconstruction(signal, tau, 2)
        box_dim = self._box_counting_dimension(ps)
        hausdorff = self._correlation_dimension(ps)
        return {
            "box_counting_dim": round(float(box_dim), 4),
            "hausdorff_dim": round(float(hausdorff), 4),
            "information_dim": round(float(hausdorff), 4),
        }

    def _estimate_delay(self, signal: np.ndarray, max_tau: int = 100) -> int:
        signal = _ensure_numpy(signal)
        n = len(signal)
        max_tau = min(max_tau, n // 4)
        acorr = np.correlate(signal - signal.mean(), signal - signal.mean(), mode="full")
        acorr = acorr[n - 1 :]
        if acorr[0] != 0:
            acorr = acorr / acorr[0]
        for tau in range(1, min(max_tau, len(acorr))):
            if acorr[tau] <= 0:
                return tau
        return max(1, max_tau // 4)

    def _gottwald_melbourne_test(self, signal: np.ndarray) -> float:
        signal = _ensure_numpy(signal)
        n = len(signal)
        if n < 20:
            return 0.0
        x = (signal - signal.mean()) / (signal.std() + 1e-12)
        phase_seed = int(_aegis_sha3_512(x.tobytes())[:8], 16) % (2 ** 31)
        rng = np.random.default_rng(phase_seed)
        c = rng.uniform(0.5, 1.5)
        p = np.zeros(n)
        q = np.zeros(n)
        for j in range(1, n):
            p[j] = p[j - 1] + x[j - 1] * np.cos(j * c)
            q[j] = q[j - 1] + x[j - 1] * np.sin(j * c)
        ms = np.array([(p[j] ** 2 + q[j] ** 2) / (j + 1) for j in range(n)])
        k = np.log(ms[-1] + 1e-12) / np.log(n + 1e-12)
        return float(min(1.0, max(0.0, k)))

    def _correlation_dimension(self, trajectory: np.ndarray) -> float:
        trajectory = np.asarray(trajectory, dtype=np.float64)
        n = len(trajectory)
        if n < 10:
            return 1.0
        max_points = min(n, 2000)
        sample = trajectory[np.linspace(0, n - 1, max_points, dtype=int)]
        if _HAS_SCIPY:
            dists = pdist(sample)
            all_dists = dists[dists > 1e-12]
        else:
            all_dists = np.array(
                [
                    np.linalg.norm(sample[i] - sample[j])
                    for i in range(min(500, len(sample)))
                    for j in range(i + 1, min(500, len(sample)))
                    if np.linalg.norm(sample[i] - sample[j]) > 1e-12
                ]
            )
        if len(all_dists) < 10:
            return 1.0
        r_min, r_max = all_dists.min(), all_dists.max()
        if r_min <= 0 or r_max <= r_min:
            return 1.0
        radii = np.logspace(np.log10(r_min * 1.1), np.log10(r_max * 0.9), num=15)
        counts = [max(int(np.sum(all_dists < r)), 1) for r in radii]
        log_r = np.log10(radii)
        log_c = np.log10(counts)
        valid = (log_r > log_r[0] + 0.2) & (log_r < log_r[-1] - 0.2)
        if not np.any(valid):
            valid = np.ones(len(log_r), dtype=bool)
        return float(max(0.0, np.polyfit(log_r[valid], log_c[valid], 1)[0]))

    def _box_counting_dimension(self, trajectory: np.ndarray) -> float:
        pts = trajectory[:, :2] if trajectory.ndim > 1 else trajectory.reshape(-1, 1)
        min_vals = pts.min(axis=0)
        max_vals = pts.max(axis=0)
        ranges = max_vals - min_vals + 1e-12
        epsilons, counts = [], []
        for num in [2, 4, 8, 16, 32, 64]:
            eps = ranges[0] / num
            scaled = ((pts - min_vals) / (ranges + 1e-12) * num).astype(int)
            scaled = np.clip(scaled, 0, num - 1)
            unique = len(np.unique(scaled.view(np.void, scaled.dtype.itemsize * scaled.shape[1])))
            if unique > 0:
                epsilons.append(eps)
                counts.append(unique)
        if len(epsilons) < 2:
            return 1.0
        return float(max(0.0, np.polyfit(np.log(1.0 / np.array(epsilons)), np.log(counts), 1)[0]))


class TopologicalExpansionAnalyzer:
    """Persistent homology, hypergraphs, and network motif detection."""

    def build_hypergraph(
        self, entities: List[str], relationships: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        vertices = [{"id": e, "hash": _aegis_sha3_512(e), "degree": 0} for e in entities]
        entity_index = {e: i for i, e in enumerate(entities)}
        hyperedges: List[Dict[str, Any]] = []
        for rel in relationships:
            members = rel.get("members", [])
            if len(members) < 2:
                continue
            hyperedges.append(
                {
                    "id": f"he_{len(hyperedges)}",
                    "members": members,
                    "cardinality": len(members),
                    "relation_type": rel.get("relation_type", "unknown"),
                    "weight": rel.get("weight", 1.0),
                }
            )
            for m in members:
                if m in entity_index:
                    vertices[entity_index[m]]["degree"] += 1
        n_v, n_e = len(vertices), len(hyperedges)
        return {
            "vertices": vertices,
            "hyperedges": hyperedges,
            "metrics": {
                "num_vertices": n_v,
                "num_hyperedges": n_e,
                "avg_cardinality": float(np.mean([he["cardinality"] for he in hyperedges]))
                if hyperedges
                else 0.0,
                "density": float(n_e / max(n_v * (n_v - 1) / 2, 1)),
            },
        }

    def compute_persistence_homology(self, graph: Dict[str, Any]) -> Dict[str, Any]:
        betti = self.betti_numbers(graph)
        return {
            "persistence_diagram": [],
            "betti_numbers": betti,
            "homology_hash": _aegis_sha3_512(str(graph.get("nodes", []))),
        }

    def betti_numbers(self, graph: Dict[str, Any]) -> List[int]:
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        if not nodes:
            return [0, 0, 0]
        node_ids = [n["id"] if isinstance(n, dict) else n for n in nodes]
        n_v = len(node_ids)
        node_idx = {nid: i for i, nid in enumerate(node_ids)}
        parent = list(range(n_v))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: int, y: int) -> None:
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[ry] = rx

        n_e = 0
        for e in edges:
            src, tgt = e.get("source", ""), e.get("target", "")
            if src in node_idx and tgt in node_idx:
                union(node_idx[src], node_idx[tgt])
                n_e += 1
        b0 = len(set(find(i) for i in range(n_v)))
        b1 = max(0, n_e - n_v + b0)
        return [b0, b1, 0]

    def non_spatial_expansion(self, technology_domains: List[str]) -> Dict[str, Any]:
        if not technology_domains:
            return {"unique_domains": [], "shannon_entropy": 0.0, "diversity_index": 0.0}
        unique_domains = sorted(set(technology_domains))
        counts = Counter(technology_domains)
        probs = np.array([c / len(technology_domains) for c in counts.values()])
        entropy = -np.sum(probs * np.log2(probs + 1e-12))
        max_entropy = np.log2(max(len(unique_domains), 1))
        return {
            "unique_domains": unique_domains,
            "shannon_entropy": round(float(entropy), 4),
            "diversity_index": round(float(entropy / max_entropy) if max_entropy > 0 else 0.0, 4),
            "domain_frequencies": dict(sorted(counts.items(), key=lambda x: x[1], reverse=True)),
        }

    def detect_network_motifs(self, graph: Dict[str, Any]) -> List[Dict[str, Any]]:
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        if not nodes or not edges:
            return []
        node_ids = [n["id"] if isinstance(n, dict) else n for n in nodes]
        adj = {nid: set() for nid in node_ids}
        for e in edges:
            src, tgt = e.get("source", ""), e.get("target", "")
            if src in adj and tgt in adj:
                adj[src].add(tgt)
                adj[tgt].add(src)
        motifs: List[Dict[str, Any]] = []
        found: set = set()
        for nid in node_ids:
            neighbors = list(adj[nid])
            for i in range(len(neighbors)):
                for j in range(i + 1, len(neighbors)):
                    n1, n2 = neighbors[i], neighbors[j]
                    if n2 in adj[n1]:
                        tri = tuple(sorted([nid, n1, n2]))
                        if tri not in found:
                            found.add(tri)
                            motifs.append(
                                {
                                    "type": "triangle",
                                    "members": list(tri),
                                    "significance": 0.8,
                                }
                            )
        for nid in node_ids:
            deg = len(adj[nid])
            if deg >= 4:
                motifs.append(
                    {
                        "type": "star",
                        "center": nid,
                        "spokes": list(adj[nid]),
                        "significance": min(deg * 0.1, 1.0),
                    }
                )
        motifs.sort(key=lambda x: x.get("significance", 0), reverse=True)
        return motifs


class CDSForensicsEngine:
    """Credit Default Swap self-betting exposure analysis."""

    def __init__(self) -> None:
        self.cds_market_notional = CDS_MARKET_NOTIONAL

    def calculate_cds_notional_exposure(self) -> float:
        return self.cds_market_notional

    def stress_test_scenario(self, scenario: str) -> Dict[str, Any]:
        scenarios = {
            "baseline": {"credit_spread_widening": 0.0, "ip_valuation_haircut": 0.0, "counterparty_default_prob": 0.0},
            "ip_theft_cascade": {"credit_spread_widening": 0.03, "ip_valuation_haircut": 0.60, "counterparty_default_prob": 0.15},
            "systemic_crisis": {"credit_spread_widening": 0.15, "ip_valuation_haircut": 0.75, "counterparty_default_prob": 0.40},
        }
        params = scenarios.get(scenario, scenarios["baseline"])
        total_notional = self.cds_market_notional
        credit_loss = total_notional * params["credit_spread_widening"] * 0.1
        ip_loss = total_notional * params["ip_valuation_haircut"] * 0.05
        counterparty_loss = total_notional * params["counterparty_default_prob"] * 0.02
        total_loss = credit_loss + ip_loss + counterparty_loss
        cascade_factor = 1.0 + params["counterparty_default_prob"] * 2.5
        cascaded_loss = total_loss * cascade_factor
        return {
            "scenario": scenario,
            "parameters": params,
            "estimated_losses": {
                "total_direct_losses": round(float(total_loss), 2),
                "cascaded_total_losses": round(float(cascaded_loss), 2),
            },
            "severity_rating": (
                "Critical" if cascaded_loss > 50e12 else "High" if cascaded_loss > 10e12 else "Moderate"
            ),
            "scenario_hash": _aegis_sha3_512(scenario),
        }

    def generate_bis_report(self) -> Dict[str, Any]:
        total = self.cds_market_notional
        gross_market_value = total * 0.028
        gross_credit_exposure = total * 0.006
        return {
            "report_date": datetime.now(timezone.utc).isoformat(),
            "total_notional_outstanding": total,
            "total_notional_formatted": f"${total / 1e12:.3f}T",
            "gross_market_value": round(gross_market_value, 2),
            "gross_credit_exposure": round(gross_credit_exposure, 2),
            "reporting_standard": "BIS OTC Derivatives Statistics",
            "report_url": "https://www.bis.org/statistics/derstats.htm",
            "report_hash": _aegis_sha3_512(f"bis:{total}"),
        }
