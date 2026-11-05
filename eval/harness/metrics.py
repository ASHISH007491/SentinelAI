"""Evaluation metrics: ranking, classification, per-CWE, cost variance, significance.

Every metric here is deterministic and hand-tested (see eval/tests/test_metrics.py) so
the numbers reported in the dissertation can be audited independently of any model.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


# --- ranking -----------------------------------------------------------------
def _dcg(gains: list[float]) -> float:
    """Discounted cumulative gain: gain_i / log2(i + 1), 1-indexed."""
    return sum(g / math.log2(i + 1) for i, g in enumerate(gains, start=1))


def ndcg_at_k(order: list[str], relevance: dict[str, float], k: int | None = None) -> float:
    """Normalised DCG of `order` against `relevance`. Returns 0.0 when nothing is relevant."""
    cut = len(order) if k is None else max(0, k)
    gains = [float(relevance.get(item, 0.0)) for item in order[:cut]]
    ideal = sorted((float(v) for v in relevance.values()), reverse=True)[:cut]
    idcg = _dcg(ideal)
    if idcg <= 0.0:
        return 0.0
    return _dcg(gains) / idcg


def _rank_map(order: list[str], keep: set[str]) -> dict[str, int]:
    """Position of each kept item within `order` (0-based, ties impossible)."""
    return {item: i for i, item in enumerate([x for x in order if x in keep])}


def spearman(a: list[str], b: list[str]) -> float:
    """Rank correlation over the items the two orderings share.

    Items present in only one ordering are ignored, so a system that omits or invents
    entries is scored on the overlap rather than being silently penalised or rewarded.
    Fewer than two shared items is vacuous and returns 1.0.
    """
    shared = set(a) & set(b)
    n = len(shared)
    if n < 2:
        return 1.0
    ra, rb = _rank_map(a, shared), _rank_map(b, shared)
    d2 = sum((ra[item] - rb[item]) ** 2 for item in shared)
    return 1.0 - (6.0 * d2) / (n * (n * n - 1))


def _average_ranks(scores: dict[str, float], keys: list[str]) -> list[float]:
    """Descending ranks (1 = highest score) with ties sharing their average rank."""
    ordered = sorted(keys, key=lambda k: scores[k], reverse=True)
    ranks: dict[str, float] = {}
    i = 0
    while i < len(ordered):
        j = i
        while j + 1 < len(ordered) and scores[ordered[j + 1]] == scores[ordered[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0          # positions i..j share this average rank
        for t in range(i, j + 1):
            ranks[ordered[t]] = avg
        i = j + 1
    return [ranks[k] for k in keys]


def _pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return 1.0
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0.0 or dy == 0.0:
        return 1.0 if xs == ys else 0.0
    return num / (dx * dy)


def spearman_from_scores(a: dict[str, float], b: dict[str, float]) -> float:
    """Tie-aware Spearman between two score maps, computed over their shared keys."""
    keys = sorted(set(a) & set(b))
    if len(keys) < 2:
        return 1.0
    return _pearson(_average_ranks(a, keys), _average_ranks(b, keys))


# --- classification ----------------------------------------------------------
@dataclass
class ConfusionMatrix:
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        d = self.tp + self.fp
        return self.tp / d if d else 0.0

    @property
    def recall(self) -> float:
        d = self.tp + self.fn
        return self.tp / d if d else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    @property
    def fpr(self) -> float:
        """False-positive rate — the analyst-time metric that matters most in triage."""
        d = self.fp + self.tn
        return self.fp / d if d else 0.0

    @property
    def accuracy(self) -> float:
        d = self.tp + self.fp + self.tn + self.fn
        return (self.tp + self.tn) / d if d else 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "tp": float(self.tp), "fp": float(self.fp),
            "tn": float(self.tn), "fn": float(self.fn),
            "precision": self.precision, "recall": self.recall,
            "f1": self.f1, "fpr": self.fpr, "accuracy": self.accuracy,
        }


def confusion(y_true: list[bool], y_pred: list[bool]) -> ConfusionMatrix:
    if len(y_true) != len(y_pred):
        raise ValueError(
            f"y_true and y_pred must be the same length ({len(y_true)} != {len(y_pred)})"
        )
    cm = ConfusionMatrix()
    for truth, pred in zip(y_true, y_pred, strict=True):
        if truth and pred:
            cm.tp += 1
        elif truth and not pred:
            cm.fn += 1
        elif not truth and pred:
            cm.fp += 1
        else:
            cm.tn += 1
    return cm


# --- per-CWE -----------------------------------------------------------------
def per_cwe_detection(detections: list[tuple[str, bool]]) -> dict[str, float]:
    """Detection rate per CWE: of the vulnerable cases of this CWE, what fraction were caught?"""
    totals: dict[str, int] = {}
    hits: dict[str, int] = {}
    for cwe, detected in detections:
        totals[cwe] = totals.get(cwe, 0) + 1
        hits[cwe] = hits.get(cwe, 0) + int(bool(detected))
    return {cwe: hits[cwe] / totals[cwe] for cwe in totals}


# --- cost / variance ---------------------------------------------------------
def mean_std(values: list[float]) -> tuple[float, float]:
    """Mean and *sample* standard deviation (ddof=1); (0,0) for empty, std 0 for one value."""
    n = len(values)
    if n == 0:
        return 0.0, 0.0
    mean = sum(values) / n
    if n == 1:
        return mean, 0.0
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return mean, math.sqrt(var)


def summarise_runs(runs: list[dict], keys: list[str]) -> dict[str, dict[str, float]]:
    """Mean/std for each metric across repeated runs."""
    out: dict[str, dict[str, float]] = {}
    for key in keys:
        vals = [float(r[key]) for r in runs if key in r]
        mean, std = mean_std(vals)
        out[key] = {"mean": mean, "std": std}
    return out


# --- significance ------------------------------------------------------------
@dataclass
class SignificanceResult:
    statistic: float = 0.0
    p_value: float = 1.0
    n: int = 0
    significant: bool = False
    method: str = "wilcoxon-normal-approx"


def _normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def wilcoxon_signed_rank(a: list[float], b: list[float], alpha: float = 0.05) -> SignificanceResult:
    """Paired Wilcoxon signed-rank test via the normal approximation.

    Non-parametric and paired, which suits small numbers of repeated runs where the
    differences are not assumed normal. Zero differences are dropped, as is standard.
    """
    pairs = [(x - y) for x, y in zip(a, b, strict=False) if (x - y) != 0.0]
    n = len(pairs)
    if n == 0:
        return SignificanceResult(statistic=0.0, p_value=1.0, n=0, significant=False)

    magnitudes = {i: abs(d) for i, d in enumerate(pairs)}
    # _average_ranks ranks descending (largest |d| first); invert each rank so the
    # smallest |d| carries rank 1, as the signed-rank test requires. Ties keep their
    # averaged rank under the inversion.
    desc = _average_ranks(magnitudes, list(range(n)))
    ranks = [n + 1 - r for r in desc]
    w_pos = sum(r for r, d in zip(ranks, pairs, strict=True) if d > 0)
    w_neg = sum(r for r, d in zip(ranks, pairs, strict=True) if d < 0)
    w = min(w_pos, w_neg)

    mu = n * (n + 1) / 4.0
    sigma = math.sqrt(n * (n + 1) * (2 * n + 1) / 24.0)
    if sigma == 0.0:
        return SignificanceResult(statistic=w, p_value=1.0, n=n, significant=False)
    # Continuity correction: the statistic is discrete, the normal curve is not.
    z = (abs(w - mu) - 0.5) / sigma
    p = 2.0 * (1.0 - _normal_cdf(max(0.0, z)))
    p = min(1.0, max(0.0, p))
    return SignificanceResult(statistic=w, p_value=p, n=n, significant=p < alpha)
