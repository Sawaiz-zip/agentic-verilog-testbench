# 7. Us vs AutoBench

The question you will definitely be asked: **"Did you beat them?"**

The correct answer is **no, and we do not claim to** — followed by what we did contribute.
This document gives you both halves.

---

## 7.1 The short answer

> We did not outperform AutoBench, and the comparison is not clean enough to try. Different
> model, different circuit sample, and our Eval2 is measuring something theirs is not. What we
> contribute is methodological rigour their evaluation lacks — a control arm, a measured
> localiser, and a variance floor — plus a finding about their own approach: the mechanism
> that gave them their largest gain no longer fires against current models.

---

## 7.2 Side by side

| | **AutoBench** | **This work** |
|---|---|---|
| Model | GPT-4-turbo | Claude Sonnet 4.5 and gpt-4o-mini |
| Circuits | 156 VerilogEval | 12 ours + 20 VerilogEval |
| Runs | not stated per configuration | 220 |
| Testbench style | hybrid: Verilog driver + Python checker | self-checking Verilog |
| Generates the circuit? | **no** (deliberately) | **yes** |
| Parses the Verilog? | **no** | **yes** — six AST checks |
| Control arm in ablation? | **no** | **yes** (`retry_only`) |
| Error bars? | **no** | Wilson intervals + Fisher tests |
| Eval0 | 95.7% (SEQ 97.3%) | 95–100% |
| Eval2 | 44.8% | 82% — **not comparable** |

---

## 7.3 Why the Eval2 comparison is void

**Our number looks better and means nothing.** You must be able to explain this, because it
looks like our strongest result and it is actually our weakest measurement.

Our testbenches caught **189 of 190 mutants — 99.5%**.

That is a **ceiling**. When almost everything scores full marks, the test is too easy. It does
not distinguish a good testbench from a mediocre one, and it cannot distinguish our five
configurations from each other either.

AutoBench's 44.8% suggests **much harder mutants**. Their bar is also different — they require
catching ≥80% of mutants to count as a pass, whereas we report the raw fraction.

**So:** our 82% vs their 44.8% is comparing two different instruments, and ours is the blunter
one. We report Eval2 **as a limitation**, in the threats-to-validity section, not as a result.

> If asked *"your Eval2 beat theirs"* — say: "That comparison doesn't hold. Our mutants were
> too easy; we caught 99.5% of them, which is a ceiling effect. It tells you about our mutant
> generator, not about our testbenches. Fixing it with deterministic mutation operators is in
> our future work."

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

We added `retry_only` — one extra generation, zero information. And the result was
uncomfortable for us: `hybrid` 40.9% vs `retry_only` 29.5%, **p = 0.372**. Not significant.

Without that arm we would have reported "+14 points over baseline" and been wrong to.

### 2. A measured localiser rather than an asserted one

They assert their mechanisms work and show end-to-end gains. We measured our tool directly by
injecting 215 faults of known identity: **93% detection, 93% localisation, 0 false alarms**.

That measurement is what makes our *null* result meaningful. Without it, "we found nothing"
could just mean "our tool is broken."

### 3. A variance floor

Three of our configurations executed identical code and scored **33 points apart**. Twice.

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

Our equivalent check, `missing_fdisplay`, fired **zero times in 314 analyses**. Our
deterministic standardiser found essentially nothing to standardise.

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
- **Better mutants.** Their Eval2 at 44.8% is a discriminating measurement. Ours is not.

---

## 7.8 The paragraph to memorise

> We build directly on AutoBench and do not claim to outperform it — different model,
> different circuit sample, and an Eval2 that is not comparable because ours sits at a 99.5%
> ceiling. What we add is methodological. Their ablation has no control for the extra
> generation attempts each mechanism triggers, so their reported gains cannot separate the
> value of a diagnosis from the value of a retry. We added that control and found that no
> configuration in our study beats it at conventional significance. We also measured our
> localiser directly by fault injection rather than asserting that it works, and we measured
> the variance floor at 33 points, which is larger than the gains prior work reports without
> error bars. And we found that the mechanism responsible for their single largest improvement
> — a script inserting missing print statements — no longer fires at all against current
> models. The technique did not stop working; the defect it corrects stopped occurring.

---

**Next:** [8. Presentation Q&A](08-viva-questions.md)
