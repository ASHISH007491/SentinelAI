# SentinelAI Evaluation

First-class deliverable: multi-agent vs. single-agent baseline.

- `datasets/`  — curated/synthetic inputs + ground-truth labels (public/synthetic only)
- `harness/`   — experiment runner that consumes orchestrator run traces
- `notebooks/` — analysis (stats, tables, figures), reproducible
- `results/`   — raw metric outputs (gitignored except samples)

Metrics: accuracy, prioritisation quality, false-positive rate, latency, token cost.
