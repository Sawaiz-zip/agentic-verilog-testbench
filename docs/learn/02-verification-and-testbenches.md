# 2. Verification and Testbenches

---

## 2.1 Why verification exists

You have designed a circuit. Does it actually work?

You cannot just build the chip and find out — a fabrication run costs millions and takes
months. So you **simulate**: run the design as software, feed it inputs, check the outputs.

This is not a side activity. Surveys by the Wilson Research Group put roughly **49% of a
design engineer's time** on verification rather than design. That statistic is in our report's
opening paragraph, and it is the reason automating any part of it is worth a research project.

---

## 2.2 What a testbench is

A **testbench** is a Verilog program whose job is to test another Verilog program.

It is never turned into hardware. It exists only to run in a simulator. It does four things:

1. Create signals to connect to the circuit
2. Instantiate the circuit (plug it in)
3. Drive the inputs with test values
4. Check the outputs are what they should be

Here is a complete, working testbench for the half adder from §1.3:

```verilog
module tb_half_adder;
    reg  a, b;              // 1. we drive these
    wire sum, cout;         //    we observe these

    half_adder uut (        // 2. plug in the circuit
        .a(a), .b(b),
        .sum(sum), .cout(cout)
    );

    initial begin           // 3. drive, and 4. check
        a = 0; b = 0; #10;
        if (sum === 0 && cout === 0) $display("PASS: zero_case");
        else                          $display("FAIL: zero_case");

        a = 1; b = 1; #10;
        if (sum === 0 && cout === 1) $display("PASS: both_ones");
        else                          $display("FAIL: both_ones");

        $finish;
    end
endmodule
```

Key syntax:

- **`half_adder uut (...)`** — creates an *instance* of the circuit called `uut` (Unit Under
  Test). This is the **instantiation**.
- **`.a(a)`** — "connect the circuit's port `a` to my signal `a`". This is a **port binding**.
  The name in the dot is the *circuit's* port; the name in brackets is *your* signal. They do
  not have to match.
- **`===`** — comparison that also handles unknown values (`x`). Safer than `==` in testbenches.
- **`#10`** — wait 10 time units, giving the circuit time to respond.

**The port bindings are where a lot of our static analysis operates.** If you write
`.aa(a)` and the circuit has no port `aa`, that is a structural fault we can detect.

---

## 2.3 A sequential testbench is harder

For a circuit with a clock, the testbench must also *generate* the clock:

```verilog
module tb_counter;
    reg clk, rst;
    wire [3:0] count;

    counter_4bit uut (.clk(clk), .rst(rst), .out(count));

    initial clk = 0;
    always #5 clk = ~clk;        // toggle forever: this IS the clock

    initial begin
        rst = 1;
        @(posedge clk); #1;      // wait for a clock edge, then a moment
        rst = 0;                 // release reset

        @(posedge clk); #1;
        if (count === 4'd1) $display("PASS: first_tick");
        else                $display("FAIL: first_tick");
        $finish;
    end
endmodule
```

Two new things:

- **`always #5 clk = ~clk;`** — the clock generator. `~` means NOT, so this flips the clock
  every 5 time units, forever. **If you forget this line, no clock edge ever happens and the
  circuit never does anything.** We have a check specifically for that.
- **`@(posedge clk)`** — pause here until the next rising clock edge. This is how a testbench
  stays in step with a sequential circuit.

> **Note the style.** The clock is generated in an `always` block, but all the *testing*
> happens in an `initial` block using `@(posedge clk)` to wait. This is the normal way AI
> models write testbenches, and it is why our sensitivity-list check (which looked for
> edge-triggered `always` blocks doing the testing) never fired.

---

## 2.4 The two ways a testbench can be wrong

**This is the single most important concept in the project.** Your professor will probe it.

### Structural faults — visible by reading

```verilog
reg [3:0] data_in;                       // 4 bits
fifo_8x8 uut (.data_in(data_in), ...);   // but the port is 8 bits
```

You do not need to know what a FIFO does to see this is wrong. The widths disagree. It is
decidable from the text.

Other structural faults:
- connecting to a port name the circuit does not have
- leaving a circuit input unconnected or never assigning it
- never checking one of the outputs
- declaring a clock and never toggling it

### Semantic faults — invisible by reading

```verilog
rst = 1; @(posedge clk); #1; rst = 0;
@(posedge clk); #1;
if (count === 4'd1) $display("PASS: after_reset");   // should be 4'd0
```

Every line is well-formed. The ports are right, the widths are right, the output is checked.
It is simply **expecting the wrong number**. Whether `4'd1` is correct depends entirely on
how the counter behaves — information that lives in the *circuit*, not in the testbench.

**No amount of reading the testbench will tell you this is wrong.** You have to run it.

### The analogy

Think of a testbench as an **exam paper that comes with its own answer key**.

- **Structural fault** = question 3 is missing, or an answer box is blank. Spot it by flipping
  through the paper.
- **Semantic fault** = the answer key says 7 where the right answer is 5. The paper looks
  immaculate. You have to do the maths yourself.

Our static analyser flips through the paper. It can never check the answer key.

---

## 2.5 The worst case: a testbench that tests nothing

Here is the fault that justifies the whole project.

Suppose a testbench simply stops checking one of the outputs. What happens when you run it?

**It passes.** Not "it fails" — it *passes*, because a check that is never performed cannot
fail. And it will keep passing, every time, forever.

Simulation **cannot** detect this. There is no observation the simulator could make that
distinguishes this testbench from a correct one. The compiler sees perfectly legal Verilog.

Static analysis is the *only* method that can catch it — you read the testbench, you see the
output is never mentioned in any comparison or print statement, you flag it.

> In our fault-injection study this class scored: **static 100%, compiler 0%, simulator 0%.**
> It is the strongest single result in the report.

---

## 2.6 How we measure a testbench: Eval0, Eval1, Eval2

Three levels, taken from the AutoBench paper so our numbers are comparable to theirs.

### Eval0 — does it compile?

Feed the testbench and the circuit to the compiler. Does it build?

This is the weakest bar. A testbench can compile and be completely useless. But if it does
not compile, nothing else can be measured.

### Eval1 — does it pass against a correct circuit?

Run the testbench against the **golden DUT** (the known-correct circuit). Every check should
report PASS.

If something FAILs, the *testbench* is wrong — because the circuit is known to be right. This
catches semantic faults: wrong expected values, wrong timing.

### Eval2 — does it actually catch bugs?

Here is the problem Eval1 does not solve: **a testbench that checks nothing passes Eval1.**

So we take the correct circuit and deliberately break it in small ways, producing **mutants**.
A good testbench should notice. We score it on how many mutants it catches.

```
Eval2 = mutants caught / valid mutants
```

---

## 2.7 Mutants — what they are and why

A **mutant** is a copy of the correct circuit with exactly one small bug introduced.

We ask a cheap AI model to make them, with these instructions (the real prompt from
`prompts/gen_mutant.j2`):

```
Change EXACTLY ONE line of logic (not comments, not port declarations)
The bug must be subtle: flip one operator, invert one signal,
  change one constant, swap two signals
The module must still compile with iverilog
Do NOT add or remove ports
```

So a mutant of the half adder might change `assign sum = a ^ b;` to `assign sum = a & b;`.

**We generate 5 mutants per testbench** — but only for testbenches that got as far as Eval2,
which means they had to pass Eval1 first. Across the three ablation sweeps:

| Sweep | Mutants | Valid | Caught |
|---|---|---|---|
| Sonnet, our circuits | 190 | 190 | 189 |
| mini, our circuits | 105 | 105 | 96 |
| mini, VerilogEval | 40 | 40 | 39 |
| **Total** | **335** | **335** | **324** |

The benchmark sweep produced few mutants because so few of its testbenches passed Eval1 and
reached Eval2 at all.

### Why "valid" mutants

Sometimes the AI produces a mutant that does not compile. That is a **bad mutation**, not a
testbench failure — it would be unfair to penalise the testbench for it. So we exclude
non-compiling mutants from **both** the numerator and denominator.

This was a real bug we fixed: originally they were excluded from the numerator but still
counted in the denominator, which silently capped every score at 0.8 when one mutant of five
failed to build.

### The honest problem with our Eval2

Our testbenches caught **324 of 335 mutants — 97%**.

That is a *ceiling*. When nearly everything scores full marks, the test is too easy to tell a
good testbench from a mediocre one — and it cannot separate our five configurations either.

**Careful here, because the obvious explanation is wrong.** It would be natural to say "our
mutants were too easy." We tested that, and it is not the cause:

| what we changed | result |
|---|---|
| our circuits, our original mutants | 96.7% |
| our circuits, **better** mutants (strong model, AutoBench's prompt, fakes filtered out) | **97.4%** |
| **different circuits** (the benchmark), AutoBench's own published mutants | **53.8%** |

Improving the mutants moved the score by **one point**. Changing the circuits moved it by
**forty-four**.

So the real cause is **our circuits are too small**. Our `dff` fixture has *one input bit* —
there is nowhere for a bug to hide, so any testbench that does anything at all finds every
non-equivalent mutant. Eval2 needs circuits with enough internal state for a defect to escape
a limited set of test inputs.

**This is why we report Eval2 as a limitation, not a result.** But we can now say something
stronger than "it's a limitation": we can say *we checked why*, and it was a flaw in our
choice of fixtures, not in the measuring instrument.

> If your professor asks *"your Eval2 looks better than AutoBench's"* — see doc 07 §7.3 for
> the full answer.

---

## 2.8 Two kinds of breaking — do not confuse them

You will be asked about this. There are **two separate deliberate-breaking activities** in
this project and they point in opposite directions.

| | **Mutants** | **Fault injection** |
|---|---|---|
| What gets broken | the **circuit** (DUT) | the **testbench** |
| What is being tested | is the testbench any good? | is our *static analyser* any good? |
| Who does the breaking | a cheap AI model | our Python code, deterministically |
| How many | 335 mutants | 215 injected faults |
| Which metric | Eval2 | detection / localisation rate |

**Mutants test the testbench. Fault injection tests our tool.**

---

## 2.9 Vocabulary check

| Term | Meaning |
|---|---|
| **testbench (TB)** | a program that tests a circuit |
| **instantiate** | plug a circuit into a testbench |
| **port binding** | `.port_name(my_signal)` — connecting a signal to a circuit port |
| **golden DUT** | the known-correct circuit, used for marking only |
| **mutant** | a copy of the circuit with one deliberate bug |
| **Eval0 / 1 / 2** | compiles / passes against correct circuit / catches bugs |
| **structural fault** | wrong by reading |
| **semantic fault** | wrong only by running |

---

**Next:** [3. The Tools We Used](03-tools-and-stack.md)
