# Architecture Decisions

**S6.ReKI.1** · Muhammad Sawaiz Naveed · TU Ilmenau

A short log of the design decisions that shape how the current results should be read.
These are the choices most relevant to a supervisor update — ordered by how much they
affect the reported metrics. Each entry: **what** we decided, **why**, and its
**status**. (This is a decisions log, not a full architecture description — see
`CLAUDE.md` §6 for the whole pipeline.)

---

## A. Decisions that affect how the results should be interpreted

These directly change what the Eval0/1/2 numbers mean, so they need to be stated up
front.

### AD-1 — Generate the DUT from the description; do not feed the golden design in

**Decision.** The pipeline synthesises its own design-under-test (DUT) from the
natural-language description, then generates and tests a testbench for *that* design.
The known-correct "golden" design is **not** given as an input to generation.

**Why.** This tests the realistic end-to-end flow (description → design → testbench),
and it keeps the evaluation honest: the testbench is not built with privileged access
to the reference answer.

**Status.** ✅ Locked. Applies to every run.

---

### AD-2 — Two-DUT separation with strict boundaries

**Decision.** Two designs exist in every run, with non-overlapping roles:
- **Generated DUT** — used only in generation/analysis: spec extraction, driver port
  references, and Pyverilog static analysis.
- **Golden DUT** — used **only** at the evaluation node, purely to grade Eval0/1/2. It
  never influences generation or repair.
- **Classification** uses neither design — it runs on the description alone.

Every run records `eval_dut_source` so it is auditable which design was used for
grading.

**Why.** Prevents any leakage of the reference design into the parts of the pipeline
that are supposed to be judged. Makes the fairness of the evaluation checkable after
the fact, not just asserted.

**Status.** ✅ Locked.

---

### AD-3 — Metrics use the *best* repair iteration, not the last one

**Decision.** The repair loop regenerates the entire testbench each iteration, so a
later iteration can be *worse* than an earlier one. We now keep a best-so-far snapshot
and report the **highest-scoring evaluated testbench**, not whichever one happened to
be produced last. (Routing decisions still use the current iteration's result; only
the *reported* result is best-so-far.)

**Why.** Correctness of the metrics. Without this, "more repair" could paradoxically
score *below* "less repair" simply because the final iteration regressed — which would
make the ablation comparison misleading.

**Status.** ✅ Fixed and in effect. Covered by unit tests. This changed reported
numbers versus the earlier (last-iteration) behaviour.

---

## B. Supporting decisions (configuration & portability)

Relevant, but they do not change the research claims.

### AD-4 — Temperature 0.7 default, with a separate temp=0 controlled sweep

**Decision.** Sampling temperature defaults to **0.7** (the supervisor's chosen
setting). A separate **temperature = 0** sweep is run as the deterministic control.
Temperature is configurable via `LLM_TEMPERATURE`, not hardcoded.

**Why.** Honours the supervisor's setting for the main results, while the temp=0
control lets us separate "the pipeline works" from "the sample got lucky."

**Status.** ✅ In effect. Main results reported at 0.7.

---

### AD-5 — Model routing by node

**Decision.** A **cheap** model (gpt-4o-mini) handles classification, scenario
generation, and mutant generation; a **strong** model (Claude Sonnet 4.5) handles DUT,
spec, driver, checker, error-reasoning, and repair. Deterministic nodes (standardiser,
Pyverilog analysis, merge, evaluate) use **no** LLM.

**Why.** Spend model capability where it matters (code and reasoning) and save cost on
the light, structured tasks.

**Status.** ✅ In effect.

---

### AD-6 — Provider-agnostic, OpenAI-compatible abstraction

**Decision.** The LLM layer targets any OpenAI-compatible provider. Currently
**OpenRouter**; Groq / Anthropic / OpenAI also work by configuration alone.

**Why.** Avoids vendor lock-in and enables a cross-model study — AutoBench tested only
GPT-4, so provider-flexibility is a concrete advantage we can exploit later.

**Status.** ✅ In effect. Cross-model comparison is future work.

---

## Summary

| ID | Decision | Impact |
|---|---|---|
| AD-1 | Generate DUT from description (golden not an input) | Evaluation realism |
| AD-2 | Two-DUT separation; golden used only for grading | Evaluation fairness |
| AD-3 | Report best repair iteration, not the last | Metric correctness |
| AD-4 | Temp 0.7 default + temp=0 control | Reproducibility |
| AD-5 | Model routing by node | Cost / quality |
| AD-6 | Provider-agnostic LLM layer | Portability / cross-model |