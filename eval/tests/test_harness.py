"""Offline tests for the scoring + N-run runner (FakeLLM / reference LLMs)."""
from pathlib import Path

from eval.datasets.loaders import load_cves
from eval.datasets.types import cve_ground_truth_order
from eval.harness.reference import HeuristicLLM, WeakLLM
from eval.harness.runner import ExperimentRunner, aggregate, evaluate, significance
from eval.harness.scoring import score_code, score_phishing, score_prioritisation
from eval.systems.baseline import SingleLLMBaseline
from eval.systems.contracts import Ranking, Usage


class PerfectRanker:
    """SUT that returns the exact ground-truth order — nDCG/Spearman must be ~1."""

    name = "perfect"

    def prioritise(self, cves):
        return Ranking(order=cve_ground_truth_order(cves), usage=Usage(agents_invoked=1))

    def investigate_email(self, email):  # not used here
        raise NotImplementedError

    def review_code(self, code):
        raise NotImplementedError


def test_score_prioritisation_perfect_is_one():
    res = score_prioritisation(PerfectRanker(), load_cves())
    assert res.metrics["ndcg"] > 0.999
    assert res.metrics["spearman"] > 0.999


def test_heuristic_beats_weak_on_phishing():
    good = score_phishing(SingleLLMBaseline(HeuristicLLM()), __emails())
    weak = score_phishing(SingleLLMBaseline(WeakLLM()), __emails())
    assert good.metrics["f1"] > weak.metrics["f1"]
    assert good.metrics["recall"] == 1.0          # heuristic catches all phish
    assert weak.metrics["recall"] == 0.0          # weak says legit for everything


def __emails():
    from eval.datasets.loaders import load_emails
    return load_emails()


def test_code_per_cwe_populated():
    res = score_code(SingleLLMBaseline(HeuristicLLM()), __code())
    assert res.per_cwe                              # detection rate per CWE present
    assert all(0.0 <= v <= 1.0 for v in res.per_cwe.values())


def __code():
    from eval.datasets.loaders import load_code
    return load_code()


def test_evaluate_repeats_and_aggregate():
    runs = evaluate(SingleLLMBaseline(HeuristicLLM()), "B", repeats=4)
    assert len(runs) == 4
    agg = aggregate(runs)
    assert agg["f1"]["std"] == 0.0 and agg["f1"]["mean"] > 0.9    # deterministic fake


def test_significance_detects_phishing_gap():
    sysruns = evaluate(SingleLLMBaseline(HeuristicLLM()), "B", repeats=3)
    baseruns = evaluate(SingleLLMBaseline(WeakLLM()), "B", repeats=3)
    sig = significance(sysruns, baseruns, "B")
    assert sig.significant is True and sig.p_value < 0.05


def test_run_comparison_writes_csv_and_traces(tmp_path: Path):
    system = SingleLLMBaseline(HeuristicLLM())
    system.name = "heuristic"          # type: ignore[attr-defined]
    baseline = SingleLLMBaseline(WeakLLM())
    runner = ExperimentRunner(repeats=2, results_root=tmp_path)
    cmp = runner.run_comparison(system, baseline, tracks=("B", "C"))

    assert (cmp.out_dir / "summary.csv").exists()
    assert (cmp.out_dir / "significance.csv").exists()
    assert (cmp.out_dir / "traces_heuristic_B.json").exists()
    header = (cmp.out_dir / "summary.csv").read_text().splitlines()[0]
    assert header == "track,system,metric,mean,std"
    assert "B" in cmp.summary and "C" in cmp.summary
