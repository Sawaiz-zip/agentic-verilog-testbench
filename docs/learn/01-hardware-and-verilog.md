# 1. Hardware and Verilog Basics

Nothing here assumes any electronics background.

---

## 1.1 What a digital circuit is

A digital circuit takes some inputs that are each either **0 or 1**, and produces outputs
that are each either 0 or 1. That is the whole idea. Everything else is detail about *which*
outputs you get for *which* inputs.

Two families, and the distinction runs through the entire project:

**Combinational** — the output depends *only* on the inputs right now. Change the inputs,
the output changes immediately. It has no memory. An adder is combinational: give it 3 and
5, it gives 8, and it does not care what you gave it a moment ago.

**Sequential** — the output depends on the inputs *and* on what happened before. It has
memory. A counter is sequential: its output depends on how many times it has been ticked.

Sequential circuits need a **clock** — a signal that alternates 0,1,0,1,… forever. The
circuit only updates its memory at the moment the clock goes from 0 to 1. That moment is
called a **rising edge** or **posedge**.

> **Why this matters to us:** our project treats CMB and SEQ circuits differently. Sequential
> ones need extra handling (a clock must be generated, outputs must be observed over time),
> and they are where AI models make more mistakes.

---

## 1.2 What Verilog is

**Verilog is a programming language for describing circuits.** You write text; a tool turns
it into hardware, or simulates it.

It looks like C but it does not behave like C. The biggest difference: in C, statements run
one after another. In Verilog, everything happens **at the same time**, because real circuits
are all running simultaneously.

A file containing Verilog has the extension **`.v`**.
A file containing SystemVerilog (a newer, bigger version) has **`.sv`**.

> Our project fixtures are `.v` files. The VerilogEval benchmark ships `.sv` files. Both work.

---

## 1.3 Reading your first circuit

Here is a real file from our project, `tests/fixtures/cmb/half_adder_ref.v`:

```verilog
module half_adder(input a, input b, output sum, output cout);
    assign sum  = a ^ b;
    assign cout = a & b;
endmodule
```

Line by line:

- **`module half_adder(...)`** — a module is one circuit. This one is named `half_adder`.
  Everything until `endmodule` belongs to it.
- **`input a, input b`** — two inputs, each 1 bit.
- **`output sum, output cout`** — two outputs.
- **`assign sum = a ^ b;`** — `^` is XOR. `assign` means "this is *permanently* true", not
  "do this once". Whenever `a` or `b` changes, `sum` updates instantly.
- **`assign cout = a & b;`** — `&` is AND.

This adds two single bits. 1+1 = 2, which in binary is `10`, so `sum`=0 and `cout`=1 (the
carry).

**The word "module" is important.** It is the unit of a circuit, and it is what gets
connected to other things.

---

## 1.4 Ports, and why they cause bugs

The things in the brackets are **ports** — the circuit's connection points.

```verilog
module alu_8bit (
  input      [7:0] a,          // 8 bits wide
  input      [7:0] b,
  input      [2:0] op,         // 3 bits wide
  output reg [7:0] result,
  output           zero        // no [..] means 1 bit
);
```

`[7:0]` means **8 bits**, numbered 7 down to 0. `[2:0]` means 3 bits. No bracket means 1 bit.

**This is where a lot of our project lives.** Two things can go wrong when something connects
to these ports:

1. You connect to a port that does not exist (typo in the name)
2. You connect a wire of the **wrong width** — a 4-bit wire to an 8-bit port

The second one is nasty. Verilog does not complain. It silently pads or chops the value and
carries on. We will come back to this repeatedly.

---

## 1.5 `wire` vs `reg`

Two ways to hold a value.

- **`wire`** — like an actual wire. It has whatever value is being driven onto it. You
  cannot assign to it from inside a procedural block.
- **`reg`** — holds a value until something changes it. Despite the name it is not
  necessarily a hardware register.

**Practical rule for testbenches:** things you *drive* are `reg`, things you *observe* are
`wire`.

```verilog
reg  [7:0] a;        // we set this
wire [7:0] result;   // the circuit sets this, we watch it
```

---

## 1.6 `always` blocks and edges

For anything with memory, you write an `always` block:

```verilog
always @(posedge clk) begin
    if (rst)
        count <= 4'b0000;
    else
        count <= count + 1;
end
```

- **`always @(posedge clk)`** — "every time the clock rises, do this"
- **`posedge`** = rising edge (0→1). `negedge` = falling edge.
- **`@(...)`** is the **sensitivity list** — what wakes this block up
- **`<=`** is a *non-blocking* assignment, used for sequential logic. All the `<=` in a block
  take effect together at the end.
- **`4'b0000`** — a 4-bit binary literal. `4'd0` would be the same thing in decimal, `8'hFF`
  is 8 bits in hex.

Also common:

```verilog
always @(*) begin ... end   // "whenever any input changes" - combinational
```

> **Where this bit us:** we once wrote a check that looked for `always` blocks with edge
> sensitivity in the *testbench*. It turned out AI-written testbenches almost never have
> those; they use a different style (§2.4). The check found nothing and we deleted it.

---

## 1.7 Reset

Sequential circuits need a way to get to a known starting state. That is **reset**.

```verilog
if (rst) count <= 0;   // when reset is 1, go to zero
else     count <= count + 1;
```

A testbench must **assert reset (set it to 1), then release it (set to 0)** before expecting
the circuit to do anything useful. Forgetting to release reset is a classic bug — the circuit
sits at zero forever while the test expects it to count. We hit exactly this early in the
project and had to rewrite a prompt to fix it.

---

## 1.8 Simulation-only constructs

Some Verilog is not real hardware — it exists only for testing:

| Construct | What it does |
|---|---|
| `initial begin ... end` | run this once at the start of the simulation |
| `#10` | wait 10 time units |
| `$display("...")` | print a line |
| `$monitor("...")` | print automatically whenever a listed signal changes |
| `$finish` | end the simulation |
| `$fdisplay(f, "...")` | print to a file rather than the screen |

You will only see these in testbenches, never in the circuit being tested.

> **`$fdisplay` will come up when we discuss AutoBench** — their single biggest improvement
> came from a script that inserted missing `$fdisplay` statements.

---

## 1.9 Vocabulary you must be able to define

| Term | Meaning |
|---|---|
| **module** | one circuit |
| **port** | a connection point on a module (input or output) |
| **DUT** | **D**esign **U**nder **T**est — the circuit being tested |
| **golden DUT** | a *known-correct* version of the circuit, used as the reference |
| **RTL** | Register Transfer Level — the style of Verilog that describes real hardware |
| **`.v` / `.sv`** | Verilog / SystemVerilog source files |
| **posedge** | the rising edge of the clock; when sequential circuits update |
| **width** | how many bits a signal carries, written `[7:0]` for 8 bits |
| **CMB / SEQ** | combinational (no memory) / sequential (has memory, needs a clock) |

**"Golden DUT" is worth memorising.** It means the correct answer. In our project the golden
DUT is used only for *marking*, never for generating — the AI never sees it while writing the
testbench, because that would be like giving a student the answer key during the exam.

---

**Next:** [2. Verification and Testbenches](02-verification-and-testbenches.md) — what a
testbench is, how it can be wrong, and what we measure.
