# Understanding This Project — A Guide From Scratch

**Who this is for:** you, with no background in hardware or circuits, needing to understand
and defend this project in a presentation.

Read in order. Each document assumes the ones before it and nothing else.

| # | Document | What you will be able to do after it |
|---|---|---|
| 1 | [Hardware and Verilog Basics](01-hardware-and-verilog.md) | Read a `.v` file and say what the circuit does |
| 2 | [Verification and Testbenches](02-verification-and-testbenches.md) | Explain what a testbench is, why it can be wrong, and what Eval0/1/2 measure |
| 3 | [The Tools We Used](03-tools-and-stack.md) | Say what Pyverilog, Icarus, Verible and LangGraph each do and why we needed them |
| 4 | [The AutoBench Paper](04-autobench-explained.md) | Explain what they built, how they prompted, what they measured, what they got |
| 5 | [Our Pipeline, Node by Node](05-our-pipeline.md) | Walk through every stage of our system and justify each choice |
| 6 | [Our Experiments and Results](06-experiments-and-results.md) | Explain what we ran, what we found, and what the numbers mean |
| 7 | [Us vs AutoBench](07-comparison.md) | Answer "did you beat them?" honestly and precisely |
| 8 | [Presentation Q&A](08-viva-questions.md) | Answer the questions your professor is likely to ask |

---

## The one-paragraph version

An AI writes test programs (testbenches) for digital circuits. Those programs are often
wrong. The usual way to find out is to run a simulation, which is slow. We asked whether
some mistakes could be caught by *reading* the test program instead of running it. We built
a tool that does this, proved the tool works by deliberately breaking 215 test programs and
checking it caught them, then ran it on 280 real AI-generated test programs — where it found
almost nothing. The reason is that AI models write structurally tidy programs that test the
wrong things, and "wrong thing" is not visible in the text.

**One number to keep straight.** The tool ran 434 times but could only *read* the file in 262
of those — Pyverilog cannot parse everything modern models write, and the fallback checks
syntax only. So the finding is **3 hits in 262**, not 3 in 434. Quote the smaller
denominator; it is the honest one and an examiner who checks the data will find it.

## Two distinctions you must not mix up

These trip people up, and your professor may probe them.

**1. Two different things get broken in this project, for two different reasons.**

| What we break | Why | Where it appears |
|---|---|---|
| the **testbench** | to test whether our static analyser notices | fault-injection study |
| the **circuit** | to test whether the testbench notices | Eval2 / mutants |

**2. Two different kinds of mistake in a testbench.**

| Kind | Example | Can you see it by reading? |
|---|---|---|
| **structural** | a 4-bit wire connected to an 8-bit port | yes |
| **semantic** | expecting the counter to read 1 when it reads 0 | no — you must run it |

Our tool handles the first kind. The project's central finding is that AI models mostly make
the second kind.

**3. "Better results" almost always means a better model, not a better pipeline.**

Late in the project we re-ran the 20 benchmark circuits with a stronger model. Eval1 doubled.
Nothing in the pipeline changed — same code, same frozen prompts, same circuits, one line of
configuration. If you say "our results improved", the next question is "what did you change?",
and the answer must be *the model*. Meanwhile the structural findings did **not** move, which
is the cleanest evidence for the project's central claim: capability decides whether a
testbench is *right*, not whether it is *well-formed*.
