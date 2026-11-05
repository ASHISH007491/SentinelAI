"""Tests for the injection-attack taxonomy + transferability analysis."""
from pathlib import Path

from eval.datasets.adversarial import (
    TAXONOMY,
    AttackType,
    adversarial_code_by_type,
    adversarial_emails_by_type,
)
from eval.harness.reference import InjectableLLM
from eval.harness.runner import ExperimentRunner
from eval.harness.scoring import score_robustness_by_type
from eval.systems.guarded import GuardedSystem
from eval.systems.multi_agent import MultiAgentSystem


def test_taxonomy_covers_all_attack_types_for_both_targets():
    assert set(TAXONOMY) == set(AttackType)
    for atype in AttackType:
        assert TAXONOMY[atype]["phish"] and TAXONOMY[atype]["code"]


def test_adversarial_groups_preserve_true_labels():
    for cases in adversarial_emails_by_type().values():
        assert cases and all(e.label.value == "phish" for e in cases)
    for cases in adversarial_code_by_type().values():
        assert cases and all(c.vulnerable for c in cases)


def test_guard_defends_overt_attacks_but_obfuscation_evades():
    llm = InjectableLLM()
    guarded = GuardedSystem(MultiAgentSystem(llm))
    by_type = score_robustness_by_type(guarded, "email")
    # Overt injection styles are neutralised by the pattern guard...
    for overt in ("direct_override", "authority_spoof", "roleplay", "context_termination"):
        assert by_type[overt].asr == 0.0
    # ...but obfuscated attacks still get through (the key robustness finding).
    assert by_type["obfuscated"].asr > 0.0


def test_obfuscated_attack_steers_the_victim_model():
    # The vulnerable model obeys even spaced/hyphenated injections a regex would miss.
    un = score_robustness_by_type(MultiAgentSystem(InjectableLLM()), "email")
    assert un["obfuscated"].asr > 0.0


def test_run_transferability_writes_csv(tmp_path: Path):
    llm = InjectableLLM()
    runner = ExperimentRunner(results_root=tmp_path)
    out = runner.run_transferability(MultiAgentSystem(llm), GuardedSystem(MultiAgentSystem(llm)))
    assert "email" in out and "obfuscated" in out["email"]
    csvs = list(tmp_path.rglob("transferability.csv"))
    assert csvs and "attack_type" in csvs[0].read_text()
