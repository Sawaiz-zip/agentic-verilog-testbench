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

## The whole project in plain words

*If you read nothing else in this folder, read this.*

We asked whether mistakes in AI-written test programs could be caught by **reading** the code
instead of **running** it. Reading is instant and free; running means a full compile-and-simulate
cycle every time.

We built the reading tool. We proved it works by deliberately planting 215 known mistakes and
checking it caught them — it caught 93%, and never raised a false alarm on correct code.

Then we pointed it at 280 real AI-generated test programs. **It found three things.**

Not because the tool is broken — we proved it isn't. Because the AI writes *tidy* code. The
wiring is fine: right ports, right widths, everything connected. A tool that checks wiring has
no work to do.

**What goes wrong instead is a different kind of mistake.** The AI writes a test that expects
the wrong answer — "the counter should read 5" when it reads 4. On the page that test looks
perfect. The number isn't wrong *on paper*; it's wrong compared to how the chip actually
behaves. You cannot see that by reading. You have to run it.

Out of 280 attempts, **88 worked and 192 failed** — roughly two in three fail. And about nine
in ten of those failures are the "expects the wrong answer" kind.

**What happens to a failed one? Mostly nothing.** In most configurations the pipeline isn't
allowed to retry. Where it is, we hand the AI the error and ask it to fix it — that worked
about **one time in five**. When it didn't, the usual reason was that the AI fixed the thing we
complained about and broke something else, so after three rounds it's still wrong, just wrong
somewhere new.

### The conclusion

The answer to the research question is **no** — and knowing *why* it is no is the contribution.

AI models have become good at the part of a testbench that is readable, and stayed bad at the
part that isn't. The same thing happened to the paper we built on: AutoBench's single biggest
result came from a similar reading-based fix, worth 42 percentage points in 2024. Our
equivalent check fired **zero** times.

> **Tools built to patch a model's weaknesses have a shelf life, because the weaknesses get
> trained away. Nobody had measured that before.**

That sentence is the project. Everything else is the evidence for it.

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
