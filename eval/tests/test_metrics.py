"""Hand-worked tests for every evaluation metric."""
import math

import pytest
from eval.harness.metrics import (
    confusion,
    mean_std,
    ndcg_at_k,
    per_cwe_detection,
    spearman,
    summarise_runs,
)

REL = {"A": 3.0, "B": 2.0, "C": 1.0}


# --- ranking -----------------------------------------------------------------
def test_ndcg_perfect_order_is_one():
    assert ndcg_at_k(["A", "B", "C"], REL) == pytest.approx(1.0)


def test_ndcg_reversed_order_known_value():
    # DCG[C,B,A] = 1/1 + 2/log2(3) + 3/log2(4) = 1 + 1.26186 + 1.5 = 3.76186
    # IDCG       = 3/1 + 2/log2(3) + 1/log2(4) = 3 + 1.26186 + 0.5 = 4.76186
    assert ndcg_at_k(["C", "B", "A"], REL) == pytest.approx(3.76186 / 4.76186, abs=1e-4)


def test_ndcg_at_k_truncates():
    # only first item counts at k=1: gain 3 / idcg(3) = 1.0 (best item first)
    assert ndcg_at_k(["A", "B", "C"], REL, k=1) == pytest.approx(1.0)
    # worst item first at k=1: gain 1 vs ideal gain 3 -> 1/3
    assert ndcg_at_k(["C", "A", "B"], REL, k=1) == pytest.approx(1.0 / 3.0)


def test_ndcg_zero_when_no_relevance():
    assert ndcg_at_k(["A", "B"], {"A": 0.0, "B": 0.0}) == 0.0


def test_spearman_identical_and_reversed():
    assert spearman(["A", "B", "C"], ["A", "B", "C"]) == pytest.approx(1.0)
    assert spearman(["A", "B", "C"], ["C", "B", "A"]) == pytest.approx(-1.0)


def test_spearman_short_input_is_vacuous():
    assert spearman(["A"], ["A"]) == 1.0


# --- classification ----------------------------------------------------------
def test_confusion_hand_worked():
    yt = [True, True, False, False, True]
    yp = [True, False, False, True, True]
    cm = confusion(yt, yp)
    assert (cm.tp, cm.fp, cm.tn, cm.fn) == (2, 1, 1, 1)
    assert cm.precision == pytest.approx(2 / 3)
    assert cm.recall == pytest.approx(2 / 3)
    assert cm.f1 == pytest.approx(2 / 3)
    assert cm.fpr == pytest.approx(0.5)
    assert cm.accuracy == pytest.approx(0.6)


def test_confusion_perfect_and_empty_guards():
    cm = confusion([True, False], [True, False])
    assert cm.precision == 1.0 and cm.recall == 1.0 and cm.f1 == 1.0 and cm.fpr == 0.0
    empty = confusion([], [])
    assert empty.f1 == 0.0 and empty.accuracy == 0.0


def test_confusion_length_mismatch_raises():
    with pytest.raises(ValueError):
        confusion([True], [True, False])


# --- per-CWE -----------------------------------------------------------------
def test_per_cwe_detection_rates():
    dets = [("CWE-89", True), ("CWE-89", False), ("CWE-78", True), ("CWE-79", False)]
    rates = per_cwe_detection(dets)
    assert rates == {"CWE-89": 0.5, "CWE-78": 1.0, "CWE-79": 0.0}


# --- cost / variance ---------------------------------------------------------
def test_mean_std_sample_stddev():
    mean, std = mean_std([1.0, 2.0, 3.0])  # variance = (1+0+1)/2 = 1
    assert mean == pytest.approx(2.0) and std == pytest.approx(1.0)


def test_mean_std_single_and_empty():
    assert mean_std([5.0]) == (5.0, 0.0)
    assert mean_std([]) == (0.0, 0.0)


def test_summarise_runs():
    runs = [{"tokens": 100, "latency_s": 1.0}, {"tokens": 200, "latency_s": 3.0}]
    out = summarise_runs(runs, ["tokens", "latency_s"])
    assert out["tokens"]["mean"] == pytest.approx(150.0)
    assert out["latency_s"]["mean"] == pytest.approx(2.0)
    # sample std of [1,3] = sqrt(((1)+(1))/1) = sqrt(2)
    assert out["latency_s"]["std"] == pytest.approx(math.sqrt(2.0))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


# --- P29 additions: tie-aware spearman + intersection + significance ---------
def test_spearman_intersection_correct():
    from eval.harness.metrics import spearman
    # B is missing X and adds Z; correlation is computed over the shared {A,B,C}
    a = ["A", "B", "C", "X"]
    b = ["A", "B", "C", "Z"]
    assert spearman(a, b) == pytest.approx(1.0)
    # reversed shared order -> -1 regardless of the non-shared extras
    assert spearman(["A", "B", "C", "X"], ["C", "B", "A", "Z"]) == pytest.approx(-1.0)


def test_spearman_from_scores_handles_ties():
    from eval.harness.metrics import spearman_from_scores
    a = {"p": 3.0, "q": 1.0, "r": 1.0}     # q,r tied
    assert spearman_from_scores(a, a) == pytest.approx(1.0)
    b = {"p": 1.0, "q": 3.0, "r": 3.0}     # perfectly anti-correlated with ties
    assert spearman_from_scores(a, b) == pytest.approx(-1.0)


def test_wilcoxon_no_difference_is_not_significant():
    from eval.harness.metrics import wilcoxon_signed_rank
    xs = [0.5, 0.6, 0.7, 0.8, 0.9]
    res = wilcoxon_signed_rank(xs, xs)
    assert res.n == 0 and res.p_value == 1.0 and res.significant is False


def test_wilcoxon_consistent_improvement_is_significant():
    from eval.harness.metrics import wilcoxon_signed_rank
    a = [0.80, 0.82, 0.79, 0.85, 0.83, 0.81, 0.84, 0.86, 0.80, 0.82, 0.88, 0.79]
    b = [0.60, 0.61, 0.59, 0.62, 0.63, 0.60, 0.64, 0.61, 0.58, 0.62, 0.65, 0.60]
    res = wilcoxon_signed_rank(a, b)   # A consistently beats B on every pair
    assert res.significant is True and res.p_value < 0.05 and res.n == 12
