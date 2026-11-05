# Addendum — Architecture rationale & alternatives (draft for review)

Responds to Rishiraj Bhattacharyya's demonstration feedback: *"highlight your
contribution, in particular the architecture choice involving a multi-agent system,
and compare with the alternatives you considered."*

Two inserts. **A** is a new subsection for Chapter 4 (suggest placing it as **4.2,
"Design Rationale: The Multi-Agent Choice and the Alternatives Considered"**, pushing
the current 4.2–4.5 down by one). **B** replaces the first sentence of §1.5 so the
architecture choice is named as a contribution up front.

---

## A. New Chapter 4 subsection — Design Rationale: The Multi-Agent Choice and the Alternatives Considered

The central architectural decision in SentinelAI is to decompose each triage task
across a small set of cooperating, single-purpose agents rather than to solve it in one
step. This choice is the treatment under test in the evaluation, so it is worth stating
plainly what was considered, what was rejected, and why — not least because the results
in Chapter 5 are mixed, and a design choice is only defensible if it was made for reasons
that survive an honest result.

Four architectures were weighed. The first, and the one retained as the experimental
baseline, is a **single monolithic prompt**: one language-model call that receives the
whole task and returns the whole answer. Its virtues are real — it is the cheapest option
in tokens and latency, it has no orchestration to build or maintain, and it is the obvious
default. Its weaknesses are equally real for a *defensive* assistant. A single prompt
couples every sub-decision into one opaque inference, so there is no seam at which to
inspect, test or intervene; when it is wrong there is no way to attribute the error to a
stage; and, most consequentially here, there is no natural point at which to insert a
guardrail over untrusted input, because the untrusted content and the reasoning share one
prompt. Rather than discard this option, I kept it as the baseline, so that the cost of
decomposition could be measured against it fairly rather than assumed away.

The second alternative is a **single tool-using agent in a reasoning-and-acting loop**
(the ReAct pattern), where one model iteratively decides which tool to call next. This is
the dominant pattern in the offensive systems surveyed in Chapter 2, and it is powerful
where the sequence of steps cannot be known in advance. For SentinelAI's three tasks it
was rejected for two reasons. First, the tasks have a *known, short* structure — extract
then judge, scan then confirm, assess then rank — so the open-ended flexibility of a
free-running loop buys little while introducing the very failure mode the benchmarking
literature warns of: models that lose track of state and wander over long, self-directed
trajectories. Second, and decisively, a single agent that plans its own actions offers no
stable, auditable boundary between untrusted data and control flow; the injection defence
that is this project's main contribution is far harder to guarantee when the model can
re-plan around it. A fixed decomposition trades autonomy I did not need for control I did.

The third alternative is a **fine-tuned single model per task**, trained to emit the
required decision directly. In principle this could match or beat a prompted pipeline on
quality and would be cheaper at inference. It was rejected on grounds that go to the heart
of the project's constraints and aims. Fine-tuning demands labelled training data at a
scale I did not have and could not ethically source for phishing and vulnerable code; it
would have to be redone per task and per model, undermining the free, locally hosted,
reproducible-on-any-machine footprint that §1.5 claims as a contribution; and it would
convert the system into an opaque weight update, foreclosing the per-stage inspection and
the guardrail-insertion points that motivated decomposition in the first place. The
comparison I wanted to make — architecture against architecture, on identical inputs and a
constant model — is only clean if the model is held fixed, which fine-tuning by definition
does not do.

The fourth alternative is a **purely deterministic, rule-based pipeline** — regular
expressions and heuristics mapping findings to CWE identifiers, with no language model at
all. This is fast, free, perfectly reproducible and immune to prompt injection by
construction, and for exactly those reasons it was not discarded but *retained as a
fallback layer*: when no model server is available the application degrades to it, which
is what keeps the full test suite runnable offline and in continuous integration. It was
rejected as the *primary* design because it cannot do the thing the project is about. Rules
cannot weigh the real-world exploitation signals that separate an urgent CVE from a merely
severe one, cannot read the social-engineering nuance that distinguishes a crafted phish
from a blunt one, and cannot generalise beyond the patterns their author anticipated. It is
the floor of the system, not its ceiling.

Against these, the **fixed multi-agent decomposition** was chosen because it aligns the
architecture with the shape of the problem and with the project's defensive aim. Each agent
owns one sub-decision behind a strict, JSON-only contract, which makes every stage
independently promptable, unit-testable and replaceable, and gives error attribution a
natural home. The decomposition creates explicit seams, and it is precisely at one of those
seams — before any untrusted content reaches an agent — that the PromptGuard guardrail is
inserted, which is what makes the robustness result of Chapter 6 architecturally possible
rather than bolted on. A capability registry decouples the orchestrator from concrete agent
classes, so the design extends by registration rather than modification. The honest cost of
this choice, quantified in Chapter 5, is roughly 1.7 times the baseline's token
consumption and additional latency; and the honest benefit is uneven — decomposition helped
markedly on phishing, where the sub-decisions genuinely separate, and not at all on ranking
or code review, where they do not. That the architecture was chosen as a *hypothesis to be
tested* rather than an assumed good is what allows this dissertation to report where it
fails as confidently as where it succeeds.

---

## B. Revised opening of §1.5 Contributions (replace the first two sentences)

> This work makes four contributions. **First, it makes and defends a specific
> architectural choice: it decomposes security triage across a small set of cooperating,
> single-purpose agents behind strict output contracts, and — rather than asserting that
> multi-agent design is superior — it treats that choice as a hypothesis, weighing it
> explicitly against a monolithic single prompt, a single tool-using (ReAct) agent, a
> fine-tuned per-task model, and a purely rule-based pipeline, and then measuring it against
> a fair single-model baseline. The decomposition is not incidental: its seams are what make
> per-stage testing, error attribution and, above all, the insertion of an injection
> guardrail possible.** Second, it contributes a reproducible evaluation harness that
> compares the multi-agent system against that baseline on objective ground truth, with
> repeated runs and paired significance testing, rather than on anecdote or a single run.
> Third, and most novel, it treats adversarial robustness as a measured property of a
> defensive assistant [...unchanged...].

*(The original "First…" sentence about the free, locally hosted system folds into the new
first contribution or moves to become a fifth; keeping four is cleaner — the local-infra
point already recurs in §7.1.)*
