"""Run the SentinelAI evaluation against a real local model (Ollama).

Multi-agent vs single-LLM baseline across Tracks A/B/C, plus Track D (prompt-injection
robustness, guardrail on vs off) — all on the SAME local model. Tune for slow hardware
with --timeout (per-call seconds) and --limit (cap cases per track for a fast first run).

Examples (from the repo root):
    # quick smoke: phishing only, 3 emails, generous timeout
    python -m eval.run_experiment --model llama3.2 --tracks B --limit 3 --timeout 300
    # fuller run once you trust it
    python -m eval.run_experiment --model llama3.2 --repeats 3 --timeout 300
"""
from __future__ import annotations

import argparse

from eval.harness.runner import ExperimentRunner
from eval.systems.baseline import SingleLLMBaseline
from eval.systems.guarded import GuardedSystem
from eval.systems.multi_agent import MultiAgentSystem
from eval.systems.ollama import OllamaLLM


def main() -> None:
    ap = argparse.ArgumentParser(description="SentinelAI evaluation on a local Ollama model")
    ap.add_argument("--model", default="llama3.2", help="Ollama model name")
    ap.add_argument("--repeats", type=int, default=1, help="repeats per track (variance)")
    ap.add_argument("--timeout", type=float, default=300.0, help="per-call timeout seconds")
    ap.add_argument("--limit", type=int, default=None, help="cap cases per track (fast runs)")
    ap.add_argument("--temperature", type=float, default=0.0,
                    help="sampling temperature; >0 gives run-to-run variance for significance")
    ap.add_argument("--transferability", action="store_true",
                    help="also compute per-attack-type ASR (writes transferability.csv)")
    ap.add_argument("--tracks", default="A,B,C,D",
                    help="comma list: A=vuln B=phishing C=code D=robustness")
    ap.add_argument("--host", default="http://localhost:11434")
    args = ap.parse_args()

    llm = OllamaLLM(model=args.model, host=args.host, timeout=args.timeout,
                    temperature=args.temperature)
    if not llm.ping():
        raise SystemExit(
            f"Ollama not reachable at {args.host}. Start it (open the Ollama app or "
            f"`ollama serve`) and pull the model (`ollama pull {args.model}`), then re-run."
        )

    tracks = [t.strip().upper() for t in args.tracks.split(",") if t.strip()]
    quality = [t for t in tracks if t in ("A", "B", "C")]
    runner = ExperimentRunner(repeats=args.repeats)

    if quality:
        print(f"\n=== Quality: multi-agent vs single-LLM baseline "
              f"({args.model}, {args.repeats} repeat(s), temp={args.temperature}, "
              f"limit={args.limit}) ===")
        cmp = runner.run_comparison(
            MultiAgentSystem(llm, timeout_s=args.timeout),
            SingleLLMBaseline(llm),
            tracks=tuple(quality), limit=args.limit,
        )
        primary = {"A": "ndcg", "B": "f1", "C": "f1"}
        for t in quality:
            s = cmp.significance[t]
            pm = primary[t]
            ma = cmp.summary[t]["multi_agent"][pm]
            bl = cmp.summary[t]["single_llm_baseline"][pm]
            print(f"  Track {t} [{pm}]: multi={ma['mean']:.3f}+/-{ma['std']:.3f}  "
                  f"baseline={bl['mean']:.3f}+/-{bl['std']:.3f}  p={s.p_value:.4f}")
        print(f"  -> CSVs: {cmp.out_dir}")

    if "D" in tracks:
        print("\n=== Track D: prompt-injection robustness (guardrail off vs on) ===")
        rob = runner.run_robustness(
            MultiAgentSystem(llm, timeout_s=args.timeout),
            GuardedSystem(MultiAgentSystem(llm, timeout_s=args.timeout)),
        )
        for kind, r in rob.items():
            print(f"  {kind:6s}: ASR unguarded={r['asr_unguarded']:.0%}  "
                  f"guarded={r['asr_guarded']:.0%}  (n={int(r['attacks'])})")

        if args.transferability:
            print("\n=== Track D: transferability (ASR guarded, per attack type) ===")
            by = runner.run_transferability(
                MultiAgentSystem(llm, timeout_s=args.timeout),
                GuardedSystem(MultiAgentSystem(llm, timeout_s=args.timeout)),
            )
            for kind, cats in by.items():
                for atype, r in cats.items():
                    print(f"  {kind:6s} {atype:20s} unguarded={r['asr_unguarded']:.0%} "
                          f"guarded={r['asr_guarded']:.0%}")

    print("\nDone. See summary.csv / significance.csv / robustness.csv under eval/results/.")


if __name__ == "__main__":
    main()
