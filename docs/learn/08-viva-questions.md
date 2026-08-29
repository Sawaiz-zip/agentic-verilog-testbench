# 8. Presentation Q&A

Questions your professor is likely to ask, grouped by how uncomfortable they are.

**General advice:** the strongest position in this project is honesty. Every awkward question
has a good answer *because* you measured carefully. Do not oversell — the rigour is the
contribution.

---

## A. Basics you must not fumble

**Q: What is a testbench?**
A Verilog program that tests a circuit. It creates signals, plugs the circuit in, drives the
inputs with test values, and checks the outputs. It is never built into hardware — it only
runs in a simulator.

**Q: What is a DUT? A golden DUT?**
DUT = Design Under Test, the circuit being tested. The golden DUT is a *known-correct* version,
used only for marking. Our AI never sees it while writing the testbench — that would be like
giving a student the answer key.

**Q: Combinational vs sequential?**
Combinational output depends only on current inputs — no memory, like an adder. Sequential
has memory and needs a clock, updating on the rising edge — like a counter. Sequential is
harder for AI models and is where most failures are.

**Q: What is Eval0, Eval1, Eval2?**
Eval0: does it compile. Eval1: does it pass against the correct circuit — a failure means the
*testbench* is wrong. Eval2: does it catch deliberately introduced bugs — because a testbench
that checks nothing passes Eval1.

**Q: What is a mutant?**
A copy of the circuit with exactly one small bug — a flipped operator, a changed constant. We
make 5 per testbench with a cheap model. A good testbench should notice.

**Q: What is Pyverilog? Icarus?**
Pyverilog reads Verilog and gives you a syntax tree, without running it — that is how we
inspect structure. Icarus Verilog compiles and runs Verilog — that is how we get ground truth
for Eval0 and Eval1.

**Q: Where does your data come from?**
VerilogEval — 156 problems from HDLBits, published by NVIDIA researchers, the same benchmark
AutoBench used. It is in `data/verilog_eval/problems/`. We used 20 of them, plus 12 circuits
we wrote ourselves.

---

## B. About the method

**Q: Why LangGraph and not a normal script?**
A script is fine until you add a repair loop. Once a later step can jump back to an earlier
one, the conditions controlling that jump get scattered through the code. With a graph every
transition is a small named function. That matters for our research specifically: our five
experimental configurations differ *only* in what three of those functions return, so we could
**verify** the arms are genuinely distinct instead of assuming it.

**Q: Why do you generate the circuit? AutoBench doesn't.**
Two reasons. It is the realistic flow — description, then design, then test. And it keeps the
evaluation honest: if the AI could see the correct circuit while writing the test, it could
copy the answer. The golden circuit is used only at marking time, and every run records which
circuit it was scored against.

**Q: Why is your standardiser Python instead of an LLM?**
Inserting a monitor statement is mechanical — there is exactly one correct answer. A model
would be slower, cost tokens, and can decline in ways that are tedious to detect. AutoBench's
equivalent is partly LLM-driven; ours is not.

**Q: What is `retry_only` and why does it exist?**
It regenerates the testbench once, told nothing about what was wrong. It exists because every
repairing configuration gets a second attempt that `baseline` does not. Without it, a gain
over baseline cannot distinguish "the feedback helped" from "trying twice helped." AutoBench
has no such arm, which is why their +8% and +10% are ambiguous.

**Q: Why temperature 0.7 and not 0?**
It reflects realistic use, and it was the agreed setting. The cost is randomness, which we then
measured: configurations running identical code scored 33 points apart. That measurement is
itself one of our findings.

---

## C. The uncomfortable ones

**Q: Your main result is that your tool found nothing. Isn't that a failed project?**

> No — it is a measured result, and the measurement is the contribution. We first proved the
> tool works: 93% detection on 215 injected faults, zero false alarms, and 30 of 33 faults
> that neither the compiler nor the simulator can find. Then we showed it has almost nothing
> to find in practice, and we ruled out the three obvious explanations — a weaker model, harder
> circuits, and a broken detector. The finding is that AI models write structurally correct
> testbenches that test the wrong things, and structural analysis cannot reach the wrong
> things. That is useful to know, and nobody had measured it.

**Q: Maybe your circuits were too easy?**

> That was our first suspicion, so we tested it. We took 20 circuits from VerilogEval — the
> benchmark AutoBench used — and selected them by structural complexity *before* running
> anything: port counts 6 to 12, fifteen of the twenty sequential, complexity well above the
> benchmark median. One finding in 153 analyses. We deliberately biased the sample toward
> conditions where our tool could succeed, and it still found nothing. That makes the null
> result stronger, not weaker.

**Q: Why not run all 156 problems?**

> Budget. The full sweep would have cost around $50 at the stronger model tier and we had
> roughly $16. We ran 20, chosen by a stated structural criterion before any run, which is
> the defensible way to subsample. Running all 156 and reporting the 20 that produced findings
> would have been selecting on the outcome.

**Q: Your model was too good. A weaker one would make these mistakes.**

> We tested that too. We reran the identical circuits with gpt-4o-mini. It is far worse at the
> task — Eval1 fell from 67% to 17% — but structurally just as tidy. Static findings went from
> zero to one. Capability affects whether the testbench is *right*. It does not appear to
> affect whether it is *well-formed*.

**Q: Can you claim hybrid is better?**

> No, and we say so in the report. Hybrid scores highest at 40.9% against 29.5% for the
> control, but the p-value is 0.372 — nowhere near significance. The reason is our measured
> variance: configurations running identical code differ by 33 points at twelve circuits per
> arm, and by 6.8 points over the pooled forty-four. Against that 6.8, our 11.4-point gap is
> only about 1.7x the noise. Resolving it needs more circuits or more repeats, and we costed
> both in the future work section.

**Q: Your Eval2 is 97% and AutoBench got 44.81%. You beat them.**

> That comparison doesn't hold, and I would not make it. It fails for two separate reasons.
>
> First, we are not measuring the same thing. Their Eval2 counts a problem as a pass when the
> testbench's verdicts agree with the golden testbench on at least 80% of mutants, across all
> 156 problems. Ours is a raw detection rate. Applying their rule to our runs gives 10%, not
> 97%.
>
> Second, our 97% is a ceiling, and we established why rather than assuming. The obvious
> explanation is that our mutants were too easy, so we regenerated them with a stronger model
> using AutoBench's own prompt and filtered out the equivalent ones — the score moved from
> 96.7% to 97.4%. One point. Then we scored the same testbenches against AutoBench's published
> mutants on the benchmark circuits and got 53.8%. So it isn't the mutants; it's that our
> fixture circuits are too small for a bug to hide in. Our `dff` has one input bit.
>
> That's a flaw in our experimental design, which we report in threats to validity, and using
> larger circuits for Eval2 is in future work.

**Q: So how good are your testbenches, really?**

> On realistic circuits, they detect a bit over half of planted bugs — 43 of 80 of AutoBench's
> published mutants. And that is only counting the testbenches that work at all: 67 of our 220
> runs passed Eval1, about 30%, and only 10% on the benchmark circuits. So the honest summary
> is that the pipeline produces a usable testbench roughly a third of the time, and those
> testbenches catch about half of subtle bugs. The 97% figure measures our fixtures, not our
> testbenches.

**Q: Your repair loop — does it actually work?**

> Rarely, and we can say exactly how rarely. 23 runs performed a repair informed by a
> diagnosis; 3 of them went on to pass. That is 13%. It also decomposes our headline: hybrid's
> 18 passes are 15 that passed first time — against baseline's 12 from an identical process,
> so that difference is noise — plus 3 genuinely rescued by repair. The repair mechanism is
> worth about 6.8 points, not the 13.6-point raw gap.
>
> We also characterised *why* it fails, which prior work doesn't report. Of the 20 failures,
> 7 regenerated a testbench that failed the identical scenario set — the model didn't act on
> the diagnosis. The other 13 exhausted the iteration budget with a *different* error
> signature every time: each repair fixes the scenario we complained about and breaks another.
> Across 14 multi-iteration runs, not one signature ever repeated. And ten of seventeen ended
> just one or two scenarios short of passing.

**Q: Did you beat AutoBench?**

> No, and we don't claim to. Different model, different circuit sample, non-comparable Eval2.
> What we add is methodological — a control arm they lack, a localiser measured by fault
> injection rather than asserted, and a variance floor showing that gains of the size they
> report cannot be established from single runs. And one finding about their approach: the
> mechanism behind their largest gain no longer fires against current models.

**Q: So is static analysis useless?**

> Not in general, and I would be careful with that word. Three qualifications. Both findings we
> did get were port-binding errors, and the one on the benchmark occurred on the most port-dense
> circuit tested — so structural faults became rare and concentrated rather than disappearing;
> larger designs may bring them back. Smaller locally-hosted models are untested and are the
> likely case where the checks still earn their place. And the layer costs essentially nothing
> — `pyverilog_only` used 2% fewer tokens than baseline. What our result rules out is treating
> it as a *primary* defence against frontier-model output.

---

## D. Detail questions

**Q: How did you make the testbenches faulty?**

> Eight injectors, applied to testbenches that already passed. Six target a specific check —
> rename a port so it does not exist, delete a port connection, narrow a signal's declared
> width, redirect an input's assignments so it is never driven, remove an output from the
> comparisons, delete the clock generator. Two are negative controls that are deliberately
> undetectable: replacing every `@(posedge clk)` with a bare delay, and swapping two same-width
> inputs so every connection stays legal and only the meaning is wrong.

**Q: How do you know the injectors didn't just break the Verilog?**

> That was a real risk and we guarded against it. An injector that emits a syntax error would
> score as "the compiler caught it" for a defect the injector itself created. So mutations must
> produce legal Verilog — the undriven-input injector redirects assignments to a dummy register
> rather than deleting statements, because deleting can empty an `if` branch. Injectors that
> cannot mutate cleanly decline, and those cases are excluded from the denominator.

**Q: What is the difference between mutants and fault injection?**

> Opposite directions. Mutants break the **circuit** to test whether the **testbench** notices
> — that is Eval2. Fault injection breaks the **testbench** to test whether **our analyser**
> notices. 335 mutants, 215 injected faults.

**Q: You removed one of your own checks. Why?**

> `sensitivity_list_error` looked for edge-triggered `always` blocks in the testbench. But AI
> testbenches drive from `initial` blocks and synchronise with `@(posedge clk)` — they do not
> use that style. It caught 0 of 5 injected faults built specifically for it, and produced the
> only false alarm on a correct testbench. A check with no recall and false alarms is worse
> than no check, because it wastes the repair budget. We removed it and recorded the resulting
> blind spot in a test so it is not rediscovered as a bug.

**Q: Did you find bugs in your own code?**

> Several, and they are in the report. Two suppressed detection: a missing trailing newline
> broke every Pyverilog parse and returned an empty report, which is indistinguishable from a
> clean one — our static arm was silently identical to baseline for a whole round. And checks
> that searched raw text treated string literals as code, so a scenario named
> `addition_boundary_overflow` made an unchecked `overflow` output look observed; detection for
> that class went from 47% to 100% once fixed. Three more were in the measurement harness and
> would have *inflated* our numbers.

**Q: How much did this cost?**

> About $9.20 in API calls for all 220 runs plus the pilots. The injection study was free —
> entirely offline.

---

## E. If you get stuck

Three sentences that work almost anywhere:

1. *"We measured that rather than assuming it — let me give you the number."*
2. *"That was one of the alternative explanations we tested, and here is what happened."*
3. *"I don't want to overclaim there; what the data supports is …"*

And if you genuinely do not know: **"I don't know — that would need an experiment we didn't
run."** That is a perfectly good answer in research, and far better than guessing.

---

## F. The 60-second summary

> Verification eats about half of chip design effort, and writing testbenches is a big part of
> that. AI can write them, but they are often syntactically valid and functionally wrong — a
> testbench that stops checking an output doesn't fail, it *passes*, because it isn't looking.
> We asked whether such faults could be caught by reading the testbench instead of running it.
> We built a six-check static analyser, proved it works by injecting 215 known faults — 93%
> detection, no false alarms, and it catches 30 faults that neither the compiler nor the
> simulator can see. Then we ran it on 220 real generations across two models and two circuit
> sets. It found two problems in the 190 analyses where the parser could read the file. The reason is that 87% of real failures are
> semantic — the testbench is well-formed and expects the wrong values, which is not visible in
> the text. We ruled out the obvious explanations: a weaker model is worse at the task but just
> as structurally tidy, and benchmark circuits chosen for maximum complexity changed nothing.
> The broader lesson is that tooling built to patch an AI's weaknesses expires as those
> weaknesses are trained away — AutoBench's largest gain came from a script fixing a mistake
> models no longer make.
