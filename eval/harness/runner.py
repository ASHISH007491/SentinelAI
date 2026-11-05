"""Experiment runner: repeated runs, aggregation, paired significance, CSV/trace output.

Runs both architectures over the same dataset through the SystemUnderTest protocol, so
the only thing that differs between conditions is the architecture. Every run is repeated
so variance is measurable and the comparison can be significance-tested rather than
asserted from a single lucky execution.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from eval.datasets.loaders import load_code, load_cves, load_emails
from eval.harness.metrics import SignificanceResult, summarise_runs, wilcoxon_signed_rank
from eval.harness.scoring import (
    SCORERS,
    TrackResult,
    score_robustness,
    score_robustness_by_type,
)
from eval.systems.contracts import SystemUnderTest

DEFAULT_RESULTS_ROOT = Path(__file__).resolve().parents[1] / "results"
LOADERS = {"A": load_cves, "B": load_emails, "C": load_code}
TRACK_CHOICES = tuple(LOADERS)


# --- single-track evaluation --------------------------------------------------
def load_track(track: str, limit: int | None = None) -> list:
    """Load the dataset for a track, optionally capped for fast runs."""
    if track not in LOADERS:
        raise ValueError(f"unknown track: {track}")
    cases = LOADERS[track]()
    return cases[:limit] if limit else cases


def evaluate(
    sut: SystemUnderTest, track: str, repeats: int = 1, limit: int | None = None
) -> list[TrackResult]:
    """Run one system on one track `repeats` times and return each run's result."""
    cases = load_track(track, limit)
    scorer = SCORERS[track]
    return [scorer(sut, cases) for _ in range(repeats)]


def aggregate(runs: list[TrackResult]) -> dict[str, dict[str, float]]:
    """Mean/std for every metric across repeated runs."""
    if not runs:
        return {}
    keys: list[str] = []
    for r in runs:
        for k in r.metrics:
            if k not in keys:
                keys.append(k)
    return summarise_runs([r.metrics for r in runs], keys)


def significance(
    system_runs: list[TrackResult], baseline_runs: list[TrackResult], track: str
) -> SignificanceResult:
    """Paired Wilcoxon over per-case scores, averaged across repeats.

    Repeats of the same case are not independent observations, so each case is
    first averaged over its repeats and the test is paired case-by-case. Pooling
    every (case, repeat) pair instead would inflate n and overstate significance.
    """
    def by_case(runs: list[TrackResult]) -> list[float]:
        if not runs:
            return []
        width = min(len(r.per_case) for r in runs)
        return [sum(r.per_case[i] for r in runs) / len(runs) for i in range(width)]

    a, b = by_case(system_runs), by_case(baseline_runs)
    n = min(len(a), len(b))
    return wilcoxon_signed_rank(a[:n], b[:n])


# --- comparison ---------------------------------------------------------------
@dataclass
class Comparison:
    out_dir: Path
    summary: dict[str, dict[str, dict[str, dict[str, float]]]] = field(default_factory=dict)
    significance: dict[str, SignificanceResult] = field(default_factory=dict)


class ExperimentRunner:
    """Owns repeats, output location, and writing auditable results to disk."""

    def __init__(self, repeats: int = 1, results_root: Path | None = None) -> None:
        self.repeats = max(1, int(repeats))
        self.results_root = Path(results_root) if results_root else DEFAULT_RESULTS_ROOT

    def _new_out_dir(self) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        out = self.results_root / stamp
        out.mkdir(parents=True, exist_ok=True)
        return out

    # --- Tracks A/B/C ---------------------------------------------------------
    def run_comparison(
        self,
        system: SystemUnderTest,
        baseline: SystemUnderTest,
        tracks: tuple[str, ...] = ("A", "B", "C"),
        limit: int | None = None,
        out_dir: Path | None = None,
    ) -> Comparison:
        out_dir = out_dir or self._new_out_dir()
        cmp = Comparison(out_dir=out_dir)

        for track in tracks:
            sys_runs = evaluate(system, track, self.repeats, limit)
            base_runs = evaluate(baseline, track, self.repeats, limit)

            cmp.summary[track] = {
                system.name: aggregate(sys_runs),
                baseline.name: aggregate(base_runs),
            }
            cmp.significance[track] = significance(sys_runs, base_runs, track)

            self._write_traces(out_dir, system.name, track, sys_runs)
            self._write_traces(out_dir, baseline.name, track, base_runs)

        self._write_summary_csv(out_dir, cmp)
        self._write_significance_csv(out_dir, cmp)
        return cmp

    @staticmethod
    def _write_traces(out_dir: Path, name: str, track: str, runs: list[TrackResult]) -> None:
        payload = [{"run": i, "metrics": r.metrics, "traces": r.traces}
                   for i, r in enumerate(runs)]
        (out_dir / f"traces_{name}_{track}.json").write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _write_summary_csv(out_dir: Path, cmp: Comparison) -> None:
        with (out_dir / "summary.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["track", "system", "metric", "mean", "std"])
            for track, systems in cmp.summary.items():
                for sys_name, metrics in systems.items():
                    for metric, ms in metrics.items():
                        w.writerow([track, sys_name, metric,
                                    f"{ms['mean']:.4f}", f"{ms['std']:.4f}"])

    @staticmethod
    def _write_significance_csv(out_dir: Path, cmp: Comparison) -> None:
        with (out_dir / "significance.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["track", "statistic", "p_value", "n", "significant", "method"])
            for track, s in cmp.significance.items():
                w.writerow([track, f"{s.statistic:.3f}", f"{s.p_value:.4f}",
                            s.n, s.significant, s.method])

    # --- Track D --------------------------------------------------------------
    def run_robustness(
        self,
        unguarded: SystemUnderTest,
        guarded: SystemUnderTest,
        out_dir: Path | None = None,
    ) -> dict[str, dict[str, float]]:
        out_dir = out_dir or self._new_out_dir()
        results: dict[str, dict[str, float]] = {}
        for kind in ("email", "code"):
            u = score_robustness(unguarded, kind)
            g = score_robustness(guarded, kind)
            results[kind] = {
                "attacks": float(u.attacks),
                "asr_unguarded": u.asr,
                "asr_guarded": g.asr,
                "reduction": u.asr - g.asr,
            }
        with (out_dir / "robustness.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["kind", "attacks", "asr_unguarded", "asr_guarded", "reduction"])
            for kind, r in results.items():
                w.writerow([kind, int(r["attacks"]), f"{r['asr_unguarded']:.3f}",
                            f"{r['asr_guarded']:.3f}", f"{r['reduction']:.3f}"])
        return results

    def run_transferability(
        self,
        unguarded: SystemUnderTest,
        guarded: SystemUnderTest,
        out_dir: Path | None = None,
    ) -> dict[str, dict[str, dict[str, float]]]:
        """Per-attack-type ASR: does the guardrail generalise, or only block known patterns?"""
        out_dir = out_dir or self._new_out_dir()
        out: dict[str, dict[str, dict[str, float]]] = {}
        for kind in ("email", "code"):
            u = score_robustness_by_type(unguarded, kind)
            g = score_robustness_by_type(guarded, kind)
            out[kind] = {
                atype: {
                    "attacks": float(res.attacks),
                    "asr_unguarded": res.asr,
                    "asr_guarded": g[atype].asr if atype in g else 0.0,
                }
                for atype, res in u.items()
            }
        with (out_dir / "transferability.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["kind", "attack_type", "attacks", "asr_unguarded", "asr_guarded"])
            for kind, cats in out.items():
                for atype, r in cats.items():
                    w.writerow([kind, atype, int(r["attacks"]),
                                f"{r['asr_unguarded']:.3f}", f"{r['asr_guarded']:.3f}"])
        return out

    # --- full matrix -------------------------------------------------------
    def run_all(self, limit: int | None = None) -> Path:
        """Run every track (A/B/C accuracy + efficiency, D robustness) into one dir.

        This is the Phase 8 experiment matrix: `--repeats` runs per condition,
        one timestamped results directory, every table the dissertation needs.
        """
        from eval.harness.reference import HeuristicLLM, InjectableLLM
        from eval.systems.baseline import SingleLLMBaseline
        from eval.systems.guarded import GuardedSystem
        from eval.systems.multi_agent import MultiAgentSystem

        out_dir = self._new_out_dir()
        self.run_comparison(
            MultiAgentSystem(HeuristicLLM()),
            SingleLLMBaseline(HeuristicLLM()),
            tracks=("A", "B", "C"),
            limit=limit,
            out_dir=out_dir,
        )
        self.run_robustness(
            MultiAgentSystem(InjectableLLM()),
            GuardedSystem(MultiAgentSystem(InjectableLLM())),
            out_dir=out_dir,
        )
        return out_dir


def main() -> None:
    import argparse

    from eval.harness.reference import HeuristicLLM, InjectableLLM
    from eval.systems.baseline import SingleLLMBaseline
    from eval.systems.guarded import GuardedSystem
    from eval.systems.multi_agent import MultiAgentSystem

    parser = argparse.ArgumentParser(
        description="Run multi-agent vs single-LLM-baseline (or guardrail on/off) and "
                     "write results to disk."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--track", choices=(*TRACK_CHOICES, "D"),
                        help="A=prioritisation, B=phishing, C=code review, "
                             "D=guardrail attack-success-rate (on vs off).")
    group.add_argument("--all", action="store_true",
                        help="Run the full matrix (A, B, C and D) into one results dir.")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if args.all:
        out_dir = ExperimentRunner(repeats=args.repeats).run_all(limit=args.limit)
        print(f"Wrote full experiment matrix to {out_dir}")
        return

    if args.track == "D":
        # Track D needs a genuinely injectable reference LLM -- HeuristicLLM never obeys
        # injected instructions, so it can't demonstrate the guardrail doing anything.
        unguarded = MultiAgentSystem(InjectableLLM())
        guarded = GuardedSystem(MultiAgentSystem(InjectableLLM()))
        results = ExperimentRunner(repeats=args.repeats).run_robustness(unguarded, guarded)
        for kind, r in results.items():
            print(f"{kind}: attacks={int(r['attacks'])} asr_unguarded={r['asr_unguarded']:.3f} "
                  f"asr_guarded={r['asr_guarded']:.3f} reduction={r['reduction']:.3f}")
        return

    system = MultiAgentSystem(HeuristicLLM())
    baseline = SingleLLMBaseline(HeuristicLLM())
    cmp = ExperimentRunner(repeats=args.repeats).run_comparison(
        system, baseline, tracks=(args.track,), limit=args.limit
    )
    print(f"Wrote results to {cmp.out_dir}")


if __name__ == "__main__":
    main()
