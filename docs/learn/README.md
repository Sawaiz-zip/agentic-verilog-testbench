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
checking it caught them, then ran it on 220 real AI-generated test programs — where it found
almost nothing. The reason is that AI models write structurally tidy programs that test the
wrong things, and "wrong thing" is not visible in the text.

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
