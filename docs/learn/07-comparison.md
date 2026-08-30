# 7. Us vs AutoBench

The question you will definitely be asked: **"Did you beat them?"**

The correct answer is **no, and we do not claim to** — followed by what we did contribute.
This document gives you both halves.

---

## 7.1 The short answer

> We are in the same range as AutoBench and do not claim to beat them. On the hardest 20
> problems of their own benchmark, with a newer model, we reach 50% Eval1 against their 37%
> sequential figure, and 20% Eval2 against their 26%. But our model is two years newer, our
> sample is 20 circuits with a confidence interval from 30% to 70%, and they have retry
> mechanisms we don't — so no ranking is established. What we contribute is methodological
> rigour their evaluation lacks — a control arm, a measured localiser, and a variance floor —
> plus a finding about their own approach: the mechanism that gave them their largest gain no
> longer fires against current models.

---

## 7.2 Side by side

| | **AutoBench** | **This work** |
|---|---|---|
| Model | GPT-4-turbo | Claude Sonnet 4.5 and gpt-4o-mini |
| Circuits | 156 VerilogEval | 12 ours + 20 VerilogEval |
| Runs | not stated per configuration | 280 |
| Testbench style | hybrid: Verilog driver + Python checker | self-checking Verilog |
| Generates the circuit? | **no** (deliberately) | **yes** |
| Parses the Verilog? | **no** | **yes** — six AST checks |
| Control arm in ablation? | **no** | **yes** (`retry_only`) |
| Error bars? | **no** | Wilson intervals + Fisher tests |
| Eval0 | 95.7% (SEQ 97.3%) | 95–100% |
| Eval1 | 51.47% (SEQ 37.07%) | **50%** on their benchmark's hardest 20 (strong model) |
| Eval2 | 44.81% (SEQ 26.00%) | **20%** under their rule; 66.7% raw detection |

---

## 7.3 Why the Eval2 comparison is void

**Our number looks better and means nothing.** You must be able to explain this, because it
looks like our strongest result and it is actually our weakest measurement.

Our testbenches caught **324 of 335 mutants — 97%**. AutoBench reports 44.81%.

That 97% is a **ceiling**. When almost everything scores full marks the test is too easy: it
cannot separate a good testbench from a mediocre one, nor our five configurations from each
other.

### We tested the obvious explanation, and it was wrong

The natural answer is "our mutants were too easy." We checked it properly rather than
assuming, and it is not the cause:

| what changed | caught |
|---|---|
| our circuits, original mutants | 96.7% |
| our circuits, **better** mutants (strong model, AutoBench's own prompt, equivalent ones filtered) | **97.4%** |
| **the benchmark circuits**, AutoBench's own published mutants | **53.8%** |

Better mutants moved it **one point**. Different circuits moved it **forty-four**.

**The cause is that our fixture circuits are too small.** A `dff` has one input bit — a bug has
nowhere to hide. On real benchmark circuits the *same testbenches* catch only 53.8%.

### Two other reasons the raw comparison is void

- **Different measurement.** Theirs is not a detection rate. A problem passes their Eval2 when
  the testbench's verdicts *agree with the golden testbench* on ≥80% of mutants, counted over
  all 156 problems. Ours is a raw fraction of mutants detected.
- **Applying their rule to us** gives 4 of 20 circuits clearing 80% with the strong model — **20%**, not 97%. (With the weak model it was 10%.)

> **If asked "your Eval2 beat theirs"** — say: "It doesn't, and the comparison is void twice
> over. First, they measure agreement with a golden testbench at an 80% threshold across all
> 156 problems; we measure raw detection. Applying *their* rule to our runs gives 20%, not
> 97% — against their 26% on sequential circuits, which is the fair comparison since ours are
> 75% sequential. Second, our 97% is a ceiling caused by our fixture circuits being too small — we tested
> that by regenerating the mutants with a stronger model and their own prompt, and the score
> moved by one point. On real benchmark circuits with their published mutants, the same
> testbenches score 53.8%. So our Eval2 measures our choice of circuits, not our testbenches."

---

## 7.4 Why the Eval0 comparison is only weak

Ours is 95–100%, theirs 95.7%. Tempting, but two problems:

1. **Different circuits.** Ours includes 12 we designed ourselves.
2. **Different model.** Sonnet 4.5 is two years newer than GPT-4-turbo. Any gap is probably
   *model progress*, not pipeline design.

The fairest statement: on the 20 benchmark circuits we share with them, our Eval0 was 90–95%
with a *weaker* model than theirs. Roughly comparable, nothing more.

---

## 7.5 What we genuinely add

### 1. A control arm

**Their ablation cannot separate "the feedback helped" from "it got another try."** Disabling
auto-debug also removes the regeneration it triggers, so their +8% and +10% are ambiguous.

We added `retry_only` — one extra generation, zero information. Two things came out of it.

**The uncomfortable half:** `hybrid` 40.9% vs `retry_only` 29.5%, **p = 0.372**. Not
significant. Without that arm we would have reported "+14 points over baseline" and been wrong
to.

**The useful half:** `retry_only` never beats `baseline` either — **p = 1.000 in both
samples**. The bare extra attempt is worth nothing. Since `hybrid` also gets that attempt,
whatever separates them is *the diagnosis*, not the resampling. That is the attribution the
arm was built to make, and a two-arm study cannot make it.

### 2. A measured localiser rather than an asserted one

They assert their mechanisms work and show end-to-end gains. We measured our tool directly by
injecting 215 faults of known identity: **93% detection, 93% localisation, 0 false alarms**.

That measurement is what makes our *null* result meaningful. Without it, "we found nothing"
could just mean "our tool is broken."

### 3. A variance floor

Three of our configurations executed identical code and scored **33 points apart** — twice,
at twelve circuits per arm. Over the pooled forty-four runs, two identical arms differ by
**6.8 points**. Quote whichever matches the sample size being discussed.

This bears directly on their reporting: single-run pass@1 comparisons with 8–10% claimed gains,
no error bars, at a variance that would swamp them.

### 4. Cross-model evidence

They tested one model and list it as a limitation. We tested two, plus two circuit sets.

### 5. The shelf-life finding

Covered next — it is the most interesting thing we found.

---

## 7.6 The shelf-life finding

**This is the insight that makes the project interesting rather than merely honest.**

AutoBench's largest single improvement was **code standardisation** — a script inserting
missing `$fdisplay` statements. Sequential Eval0 went from **55.47% to 97.33%**. Forty-two
percentage points, from a deterministic script.

That is **the same category of technique as our contribution**: a mechanical, pre-simulation
fix for a structural defect.

Our equivalent check, `missing_fdisplay`, fired **zero times in 237 analyses**. Our
deterministic standardiser had something to insert in **3 of 220 ablation runs** — and in the other 137
sequential runs it was handed a testbench that already observed every output.

**The technique did not stop working. The defect it corrects stopped occurring.**

GPT-4-turbo forgot `$fdisplay` often enough to make a script worth 42 points. Current models
do not forget.

### Why this generalises

> Auxiliary tooling built to compensate for an AI's weaknesses is calibrated against a
> particular generation of models. As those weaknesses get trained away, the tooling's value
> decays — silently.

A team inheriting AutoBench's standardisation step today would carry a component that costs
maintenance and returns nothing, **with no way of knowing**. The measurement, not the
mechanism, is the transferable part.

That is a genuine contribution to how the field should think about this class of tool.

---

## 7.7 Where they are ahead of us

Be straightforward about this — it makes the rest more credible.

- **Scale.** 156 problems vs our 32 circuits.
- **Peer review.** Published at MLCAD 2024.
- **A working end-to-end improvement.** They demonstrably improved testbench quality. Our
  headline result is a null.
- **Better-chosen circuits for Eval2.** Their Eval2 at 44.81% discriminates between systems.
  Ours cannot, because our fixtures are too small — which is a flaw in our experimental
  design, not in our mutants.

---

## 7.8 The paragraph to memorise

> We build directly on AutoBench and do not claim to outperform it — different model,
> different circuit sample, and an Eval2 that is not comparable because ours sits at a 97%
> ceiling caused by our fixture circuits being too small. What we add is methodological. Their ablation has no control for the extra
> generation attempts each mechanism triggers, so their reported gains cannot separate the
> value of a diagnosis from the value of a retry. We added that control and found that no
> configuration in our study beats it at conventional significance. We also measured our
> localiser directly by fault injection rather than asserting that it works, and we measured
> the variance floor — 33 points between identical configurations at twelve circuits per arm,
> and 6.8 points over the pooled forty-four — which is larger than the gains prior work reports
> without error bars. And we found that the mechanism responsible for their single largest improvement
> — a script inserting missing print statements — no longer fires at all against current
> models. The technique did not stop working; the defect it corrects stopped occurring.

---

**Next:** [8. Presentation Q&A](08-viva-questions.md)
