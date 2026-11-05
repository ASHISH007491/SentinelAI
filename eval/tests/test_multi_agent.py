"""Offline tests for the multi-agent system under test (reference LLMs, no network)."""
from pathlib import Path

from eval.datasets.loaders import load_code, load_cves, load_emails
from eval.harness.reference import HeuristicLLM
from eval.harness.runner import ExperimentRunner
from eval.systems.baseline import SingleLLMBaseline
from eval.systems.contracts import SystemUnderTest
from eval.systems.multi_agent import MultiAgentSystem


def test_multi_agent_is_a_system_under_test():
    assert isinstance(MultiAgentSystem(HeuristicLLM()), SystemUnderTest)


def test_phishing_is_two_agent_decomposition():
    m = MultiAgentSystem(HeuristicLLM())
    emails = load_emails()
    phish = m.investigate_email(emails[0])      # a crafted phish
    legit = m.investigate_email(emails[10])     # a benign message
    assert phish.positive is True and legit.positive is False
    # extract -> verdict = two agents, two LLM calls recorded
    assert phish.usage.agents_invoked == 2 and phish.usage.llm_calls == 2


def test_prioritisation_is_two_agent_decomposition():
    cves = load_cves()
    rk = MultiAgentSystem(HeuristicLLM()).prioritise(cves)
    assert sorted(rk.order) == sorted(c.cve_id for c in cves)
    # risk-signal -> ranking = two agents, two LLM calls recorded
    assert rk.usage.agents_invoked == 2 and rk.usage.llm_calls == 2


def test_review_code_is_two_agent_decomposition():
    code = load_code()
    m = MultiAgentSystem(HeuristicLLM())
    vulnerable = m.review_code(code[0])
    assert vulnerable.positive is True                  # vulnerable sample
    assert m.review_code(code[1]).positive is False     # safe sample
    # pattern-scan -> confirm+fix = two agents, two LLM calls recorded
    assert vulnerable.usage.agents_invoked == 2 and vulnerable.usage.llm_calls == 2


def test_multi_agent_costs_more_than_baseline_on_phishing():
    email = load_emails()[0]
    multi = MultiAgentSystem(HeuristicLLM()).investigate_email(email)
    single = SingleLLMBaseline(HeuristicLLM()).investigate_email(email)
    # decomposition's real cost: more agents + more LLM calls (Track E finding)
    assert multi.usage.llm_calls > single.usage.llm_calls
    assert multi.usage.agents_invoked > single.usage.agents_invoked


def test_harness_compares_multi_vs_baseline(tmp_path: Path):
    system = MultiAgentSystem(HeuristicLLM())
    baseline = SingleLLMBaseline(HeuristicLLM())
    runner = ExperimentRunner(repeats=2, results_root=tmp_path)
    cmp = runner.run_comparison(system, baseline, tracks=("A", "B", "C"))
    assert (cmp.out_dir / "summary.csv").exists()
    assert set(cmp.summary["B"]) == {"multi_agent", "single_llm_baseline"}
    # every track produced finite metrics for both systems
    assert cmp.summary["A"]["multi_agent"]["ndcg"]["mean"] > 0.0
