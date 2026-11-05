"""Generate the evaluation-chapter figures from the harness result CSVs.

Scans eval/results/ for the latest summary / robustness / transferability CSVs and
produces publication-ready PNGs + a markdown summary under eval/results/figures/.
Run after a real experiment:  python -m eval.notebooks.generate_figures

Requires: matplotlib, pandas  (pip install matplotlib pandas)
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

RESULTS = Path(__file__).resolve().parent.parent / "results"
FIGURES = RESULTS / "figures"
_PRIMARY = {"A": "ndcg", "B": "f1", "C": "f1"}
_TRACK = {"A": "Vuln prioritisation", "B": "Phishing", "C": "Code review"}


def _latest(name: str) -> Path | None:
    hits = sorted(RESULTS.glob(f"*/{name}"), key=lambda p: p.stat().st_mtime, reverse=True)
    return hits[0] if hits else None


def quality_figure() -> None:
    path = _latest("summary.csv")
    if not path:
        return
    df = pd.read_csv(path)
    tracks = [t for t in ("A", "B", "C") if t in set(df["track"])]
    systems = sorted(df["system"].unique())
    fig, ax = plt.subplots(figsize=(8, 5))
    width = 0.8 / max(1, len(systems))
    for i, sysname in enumerate(systems):
        means, errs = [], []
        for t in tracks:
            row = df[(df.track == t) & (df.system == sysname) & (df.metric == _PRIMARY[t])]
            means.append(float(row["mean"].iloc[0]) if len(row) else 0.0)
            errs.append(float(row["std"].iloc[0]) if len(row) else 0.0)
        x = [j + i * width for j in range(len(tracks))]
        ax.bar(x, means, width, yerr=errs, capsize=4, label=sysname.replace("_", " "))
    ax.set_xticks([j + width * (len(systems) - 1) / 2 for j in range(len(tracks))])
    ax.set_xticklabels([f"{_TRACK[t]}\n({_PRIMARY[t]})" for t in tracks])
    ax.set_ylabel("score (mean ± std)")
    ax.set_ylim(0, 1.05)
    ax.set_title("Quality: multi-agent vs single-LLM baseline")
    ax.legend()
    _save(fig, "quality_comparison.png")


def robustness_figure() -> None:
    path = _latest("robustness.csv")
    if not path:
        return
    df = pd.read_csv(path)
    kinds = list(df["kind"])
    x = range(len(kinds))
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar([i - 0.2 for i in x], df["asr_unguarded"], 0.4, label="unguarded", color="#c0392b")
    ax.bar([i + 0.2 for i in x], df["asr_guarded"], 0.4, label="guarded", color="#27ae60")
    ax.set_xticks(list(x))
    ax.set_xticklabels(kinds)
    ax.set_ylabel("attack-success-rate")
    ax.set_ylim(0, 1.05)
    ax.set_title("Track D: prompt-injection robustness (guardrail off vs on)")
    ax.legend()
    _save(fig, "robustness_asr.png")


def transferability_figure() -> None:
    path = _latest("transferability.csv")
    if not path:
        return
    df = pd.read_csv(path)
    pivot = df.pivot_table(index="attack_type", columns="kind", values="asr_guarded")
    fig, ax = plt.subplots(figsize=(7, 5))
    im = ax.imshow(pivot.values, cmap="Reds", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([i.replace("_", " ") for i in pivot.index])
    for r in range(pivot.shape[0]):
        for c in range(pivot.shape[1]):
            ax.text(c, r, f"{pivot.values[r, c]:.0%}", ha="center", va="center")
    ax.set_title("Guarded ASR by attack type (transferability)")
    fig.colorbar(im, ax=ax, label="ASR with guardrail")
    _save(fig, "transferability_heatmap.png")


def cost_figure() -> None:
    path = _latest("summary.csv")
    if not path:
        return
    df = pd.read_csv(path)
    cost = df[df.metric == "total_tokens"]
    if cost.empty:
        return
    pivot = cost.pivot_table(index="track", columns="system", values="mean")
    fig, ax = plt.subplots(figsize=(7, 5))
    pivot.plot(kind="bar", ax=ax)
    ax.set_ylabel("total tokens")
    ax.set_title("Efficiency: token cost per track (multi-agent vs baseline)")
    ax.set_xticklabels([_TRACK.get(t, t) for t in pivot.index], rotation=0)
    _save(fig, "cost_tokens.png")


def _save(fig, name: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIGURES / name, dpi=150)
    plt.close(fig)
    print(f"  wrote {name}")


def main() -> None:
    print("Generating figures ->", FIGURES)
    quality_figure()
    robustness_figure()
    transferability_figure()
    cost_figure()
    print("Done.")


if __name__ == "__main__":
    main()
