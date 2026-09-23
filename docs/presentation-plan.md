# 20-Minute Presentation — Build Plan

**Purpose of this document.** Everything that goes on each slide, what to say, how long it takes,
which figure or screenshot it needs, and the one-line defence for each claim. Build the deck from
this.

---

## 0. Read this first — three decisions I'd push back on

### ❌ Node-by-node through 13 nodes will not fit, and would waste the talk

You asked for "each node, what it does, why, and the numbers". Thirteen nodes at even 45 seconds
each is **10 minutes of a 20-minute talk** — and it is the *least* interesting material. Most nodes
are plumbing that worked fine and produced no finding.

**Instead:** group the 13 nodes into **3 phases** (2 min total), then spend real time on the
**three nodes that carry the argument**: `gen_dut` (why we generate the circuit), `pyverilog_analysis`
(the contribution), and `repair` + modes (the evidence). A full node table goes in backup, so you
can answer any node question instantly without spending stage time on it.

### ✅ The project *is* a success — but say so with the right claim

The honest success story is **not** "our method improves testbench generation". The data does not
support that and you would be taken apart in Q&A. The claim that *is* fully supported:

> **We built a pre-simulation error localiser, proved by fault injection that it catches 100% of
> every fault class it was designed for — including 30 faults that neither the compiler nor the
> simulator can see — and then discovered that current LLMs have almost stopped making those
> mistakes. We know this is a property of the models and not a broken tool, because we measured the
> tool separately. Prior work could not have discovered this, because it has no control arm.**

That is a real contribution, a real finding, and every sentence is defensible. Lead with it and
close with it.

### ⚠️ Reframe your best number: it is stronger than 93%

The report quotes "93% detection". The per-class data says something much better:

| | |
|---|---|
| Fault classes the localiser was **designed** to catch | **201 / 201 = 100%** |
| The two classes we **deliberately built to be undetectable** (negative controls) | 0 / 14, as intended |
| **Overall** | 201 / 215 = 93% |

So it is not "93%, we missed some". It is **"100% of everything in scope, and we deliberately
included 14 out-of-scope faults to prove we weren't cherry-picking the fault set."** That is a far
stronger statement and it is exactly what the raw data says.

---

## 0.5 Is this the right structure at all?

You asked whether this is the best way to present. Short answer: **your structure is sound, it has
exactly one real risk, and the fix is one slide.**

### The three options

| | Structure | Good for | Risk |
|---|---|---|---|
| **A — yours** | problem → AutoBench → architecture → pipeline → results → conclusion | showing you did the work; examiners who want to verify effort | **results arrive at minute 14.** Overrun by 3 minutes and you lose the only part that matters |
| **B — results-first** | "here is what we found" → then the evidence backwards | conference talks, expert audiences | can read as skipping the engineering — risky for a student project where they want to see the build |
| **C — yours + a preview** ✅ | **A, plus a 30-second "where this ends up" slide at minute 3** | both | none material |

### Why **C**, and why it is only one slide of work

The genuine problem with pure chronological order is not that it is boring — it is that **your
audience has no reason to care about node 9 until they know that node 9 is where the surprise
happens.** For 13 minutes they are watching architecture with no idea what it is building toward.

Adding one preview slide fixes this completely:

- Everything after it has **tension**. The audience is now waiting to see whether you can prove the
  claim, rather than waiting for you to finish describing things.
- If you overrun and have to rush slides 12–13, **the conclusion has already landed**. That converts
  your worst-case outcome from "they never heard the finding" to "they heard it twice".
- It signals confidence. Presenters who hide the result until the end usually do so because the
  result is weak. Yours is not.

### The slide to add — insert as **Slide 3**, push everything else down one

> ### Where this ends up
>
> We built a tool that finds testbench bugs **without running anything**.
>
> **It works** — 100% of every fault class it was designed for, including 30 faults that neither
> the compiler nor the simulator can see.
>
> **And current AI models have almost stopped making those mistakes.**
> In 280 runs it triggered **one** repair.
>
> *Both halves of that sentence are results. The second one is only believable because we measured
> the first one separately — and that is what the rest of this talk is about.*

**Say it in 30 seconds, do not elaborate, move on.** You will return to each half at slides 9 and
12. Resist the urge to explain it here; the payoff is in the repetition.

### What I would *not* change

- **Keep AutoBench early.** Your contribution is defined by the gap in theirs; it makes no sense
  later.
- **Keep the architecture side-by-side.** It is your roadmap slide and it earns credit for scope.
- **Keep challenges before the conclusion.** Ending on challenges would end on a low note; ending
  on contributions is right.
- **Keep node coverage grouped, not individual.** Already argued in §0.

> **Verdict: go with your plan plus the preview slide.** The timing table below already includes it.

---

## 1. Timing budget

| # | Slide | Time | Cumulative |
|---|---|---|---|
| 1 | Title | 0:15 | 0:15 |
| 2 | The problem | 1:00 | 1:15 |
| **3** | **Where this ends up — the preview** ⬅ *added, see §0.5* | **0:30** | 1:45 |
| 4 | AutoBench, and the gap we found in it | 1:30 | 3:15 |
| 5 | **Architecture: theirs vs ours** | 2:00 | 5:15 |
| 6 | Phase 1 — write it | 0:45 | 6:00 |
| 7 | **Phase 2 — check it before running ★** | 1:30 | 7:30 |
| 8 | Phase 3 — fix it and mark it | 0:45 | 8:15 |
| 9 | How we measure: Eval0 / Eval1 / Eval2 | 1:30 | 9:45 |
| 10 | **Does the localiser work? ★ HERO** | 2:00 | 11:45 |
| 11 | The five modes, and the control arm | 1:30 | 13:15 |
| 12 | Ablation result | 1:30 | 14:45 |
| 13 | **The central finding ★ HERO** | 1:30 | 16:15 |
| 14 | Why? The defect class expired | 1:30 | 17:45 |
| 15 | Challenges | 1:00 | 18:45 |
| 16 | Contributions & conclusion | 1:00 | 19:45 |
| 17 | Thank you / repo | 0:15 | **20:00** |

⚠️ **Slide numbers in §2 below are the pre-insertion numbering** (the preview is §0.5). Renumber
once when you build the deck; the order and content are unchanged apart from the insertion.

**If you are running long, cut slides 5 and 7** (Phase 1 and Phase 3 walkthroughs) and fold one
sentence each into slide 4. That buys 2 minutes and costs nothing — they are the least load-bearing
slides in the deck.

---

## 2. Slide-by-slide

---

### Slide 1 — Title · 0:15

```
LLM-Driven Verilog Testbench Generation
with Pyverilog-Based Early Error Localization

Muhammad Sawaiz Naveed
Supervisor: Bing Wen · TU Ilmenau · S6.ReKI.1
```

**Visual:** none needed. Clean type.

---

### Slide 2 — The problem · 1:00

**Three facts, one per line, big type:**

- Verification is **~60% of chip design effort** (Foster 2022, Wilson Research survey)
- LLMs can write Verilog testbenches from plain English — but they are often
  **syntactically valid and functionally wrong**
- Finding out means **running a full simulation**. Slow feedback loop.

**Then the hook, in a box:**

> A testbench that stops checking an output **passes** — because it is no longer looking.
> No amount of simulation finds that.

**Say:** "That last line is the whole reason this project exists. If your test stops checking
something, running it tells you everything is fine."

**Visual:** 📊 **FIG-0 (optional, low priority)** — simple 60/40 donut for the verification-effort
stat. Skip if short on build time; the number alone works.

---

### Slide 3 — AutoBench, and the gap · 1:30

**Left half — what AutoBench does** (Qiu et al., MLCAD 2024):
- 6-stage LLM pipeline: classify → spec → scenarios → driver → checker
- Self-enhancement: scenario checks, auto-debug, restart up to 5×
- Results: Eval0 95.7%, Eval1 51.5%, Eval2 44.8% on 156 VerilogEval circuits

**Right half — the two gaps we build on:**

| Gap | Consequence |
|---|---|
| **They never parse the Verilog** | error detection is text search + compiler messages + simulation. Nothing checks structure before running. |
| **No control arm** | their pipeline also gives the AI *more attempts*. A gain could be the feedback — or just the extra try. Their experiment cannot tell. |

**Say:** "These two gaps are exactly the two things we add. The first is our technical contribution.
The second is our methodological one — and it turned out to be the more important."

**Visual:** 📋 **TAB-1** — simple 2-row table as above. No graphic needed.

---

### Slide 4 — Architecture: theirs vs ours · 2:00 ⭐ KEY SLIDE

**Visual:** 📊 **FIG-1 — side-by-side architecture diagram. Build this one carefully; it is the
spine of the talk.**

```
   AUTOBENCH (6 stages)              OURS (13 nodes, 3 phases)
   ─────────────────────             ──────────────────────────
                                     ┌─ PHASE 1: WRITE ──────────┐
   Stage 0  classify        ────────►│  classify                 │
        ✗  (no design)      ── NEW ─►│  gen_dut        ★ we add  │
   Stage 1  spec            ────────►│  extract_spec             │
   Stage 2  scenarios       ────────►│  gen_scenarios            │
   Stage 4  driver          ────────►│  gen_driver  ┐ parallel   │
   Stage 5  checker         ────────►│  gen_checker ┘            │
                                     │  merge_generation         │
                                     └───────────────────────────┘
                                     ┌─ PHASE 2: CHECK ──────────┐
   standardisation script   ────────►│  standardise              │
        ✗  (never parses)   ── NEW ─►│  pyverilog_analysis ★★★   │
        ✗                   ── NEW ─►│  error_reasoner     ★     │
                                     └───────────────────────────┘
                                     ┌─ PHASE 3: FIX & MARK ─────┐
   auto-debug + reboot ×5   ────────►│  repair                   │
        ✗  (no control)     ── NEW ─►│  regenerate  ★ control    │
   Eval0 / Eval1 / Eval2    ────────►│  evaluate                 │
                                     └───────────────────────────┘
```

**Colour code:** grey = same as AutoBench · **accent = what we add** · outline = what they have and
we don't.

**Say (this is your roadmap — point at it):** "Most of this is theirs and we say so. Four things
are ours: we generate the circuit too, we parse the Verilog before running anything, we turn those
findings into instructions, and we added a blind-retry control arm. The rest of the talk is about
whether those four things worked."

**⚠️ Also mention one thing they have that we don't** — it shows you read the paper properly:
"They check that every planned scenario actually appears in the generated driver. We don't. That's
listed in our future work."

---

### Slide 5 — Phase 1: write it · 1:00 *(cut this first if long)*

Six nodes, one line each, plain language:

| Node | What it does |
|---|---|
| `classify` | combinational or sequential? (cheap model) |
| `gen_dut` | **writes the circuit** — ★ AutoBench never does this |
| `extract_spec` | English → structured port/behaviour list |
| `gen_scenarios` | invents ~8 named test cases |
| `gen_driver` ∥ `gen_checker` | writes the testbench and a Python checker, **in parallel** |
| `merge_generation` | waits for both |

**Spend your time on `gen_dut` only.** Say: "We generate the circuit as well, because that's the
realistic flow — you have a description, you build a design, then you test it. The known-correct
circuit is locked away and used only at marking time, so the AI can never copy the answers."

**Defence ready:** if asked "doesn't that contaminate results?" → "We measured it. 273 of 280 runs
produce a design with the same interface as the reference. All 7 exceptions are one circuit."

**Visual:** 📋 **TAB-2** — the table above. No graphic.

---

### Slide 6 — Phase 2: check it before running it ★ · 1:30

**This is your contribution. Slow down here.**

**The six checks, and who else could catch them:**

| Check | Compiler? | Simulator? |
|---|---|---|
| port bound to wrong name | partly | usually |
| signal width ≠ port width | ❌ warning only | sometimes |
| input never driven | ❌ | usually |
| **output never checked** | ❌ | ❌ |
| **sequential output never printed** | ❌ | ❌ |
| clock never toggles | ❌ | rarely |

**Say:** "The two bold rows are the argument. If the testbench stops checking an output, running it
*passes*. Static analysis is the only thing that can see that."

**Then the honesty point, which earns you credit:**
> We built seven checks. We **deleted one** — it caught 0 of 5 faults it was built for and raised a
> false alarm on a correct testbench. A check with no recall and false alarms is worse than no check.

**Visual:** 📋 **TAB-3** — the check table, with the two ❌❌ rows highlighted.

---

### Slide 7 — Phase 3: fix it and mark it · 1:00 *(cut second if long)*

- **`repair`** — rewrite the testbench given an error report. Max 3 attempts.
  - Two safeguards worth naming: **oscillation detection** (same error twice → stop) and
    **best-so-far retention** (keep the best version, not the last — otherwise "more repair" could
    score *worse*, which is not a property an experiment may have).
- **`regenerate`** — rewrite it told **nothing**. The control arm. Slide 10 explains why.
- **`evaluate`** — Eval0/1/2, plus full telemetry: every AI call, tokens, latency.

**Visual:** none, or a tiny loop diagram.

---

### Slide 8 — How we measure · 1:30

**Three levels, then the funnel.**

| | Question |
|---|---|
| **Eval0** | does the testbench compile? |
| **Eval1** | run against the *known-correct* circuit — does everything pass? |
| **Eval2** | make 5 broken copies of the circuit — does the testbench catch them? |

**Visual:** 📊 **FIG-2 — funnel chart.** Three descending bars:

```
280 runs total
  ▼
259 compiled          92.5%
  ▼
 88 actually worked   31.4%
```

**Say:** "31% is not a number I'm going to dress up. These are the hardest quintile of the
benchmark, mostly sequential circuits, and it's in the same range as the prior work — they report
37% on sequential circuits."

**⚠️ Eval2 — say this in one sentence and move on:** "Our Eval2 looks very high, 95%, but that's a
ceiling caused by our own test circuits being too small for a bug to hide in. We proved that by
swapping the mutants and the circuits one at a time. We report it as a limitation, not a result."

**Defence ready (backup slide B3):** better mutants moved the score 1 point; different circuits
moved it 44.

---

### Slide 9 — Does the localiser actually work? ★★★ HERO SLIDE · 2:00

**This is your strongest slide. It is pure good news and it is fully defensible.**

**Method in one line:** we deliberately injected **215 known faults** into 14 working testbenches
and scored three detectors against them.

**Visual:** 📊 **FIG-3 — grouped horizontal bar chart. Build this one beautifully.**

Data (each row = a fault class, three bars: Static / Compiler / Simulator, as % of n):

| Fault class | n | Static | Compiler | Simulator |
|---|---|---|---|---|
| port renamed | 62 | **100%** | 100% | 0% |
| port dropped | 62 | **100%** | 0% | 98% |
| input never driven | 30 | **100%** | 0% | 97% |
| wrong width | 22 | **100%** | 0% | 82% |
| **output never checked** | **19** | **100%** | **0%** | **0%** |
| clock never toggles | 6 | **100%** | 0% | 17% |
| *swapped bindings (control)* | *9* | *0%* | *0%* | *78%* |
| *broken edge sync (control)* | *5* | *0%* | *0%* | *80%* |

**Call out the `output never checked` row with an arrow and a label:**
> **19 faults. Static analysis 100%. Compiler 0%. Simulator 0%.**
> The testbench passes, because it isn't looking.

**The headline, in a box:**

| | |
|---|---|
| Faults in the classes it was **designed** for | **201 / 201 — 100%** |
| Localised to the right class **and** the right signal | **100%** |
| False alarms on clean testbenches | **0** |
| Invisible to compiler **and** simulator | **33 — it caught 30** |

**Say:** "The two greyed rows are negative controls — faults we deliberately built to be
undetectable by structure, like swapping two same-width signals. Static analysis scores zero on
them, exactly as predicted. We included them so nobody has to take our word that the fault set
wasn't cherry-picked."

**This is the slide that makes the null result later a *finding* rather than a broken tool.**

---

### Slide 10 — The five modes, and why the control matters · 1:30

**The five configurations — same 13 nodes, one switch:**

| Mode | May do after the first draft |
|---|---|
| `baseline` | nothing |
| `retry_only` | rewrite it — **told nothing about what was wrong** |
| `compiler_only` | fix it, if it didn't compile |
| `pyverilog_only` | fix it, if our checker complained |
| `hybrid` | fix it for any reason — **ours** |

**The trap, said out loud:**

> If `hybrid` beats `baseline`, two explanations fit equally well:
> **(1)** the feedback found the problem, or **(2)** the AI just got a second try.
> `baseline` never gets a second try, so the comparison cannot separate them.

> **`retry_only` takes the second try with zero information. A mode must beat `retry_only`,
> not merely `baseline`.**

**Say:** "AutoBench has no arm like this, so their reported gains cannot separate those two
explanations. This is the single clearest methodological improvement in the project — and it cost
us our own headline number, which I'll show you next."

**Visual:** 📋 **TAB-4** — the mode table. Optionally a tiny 2-box "explanation 1 vs 2" graphic.

---

### Slide 11 — Ablation result · 1:30

**Visual:** 📊 **FIG-4 — vertical bar chart, "circuits that worked, out of 44".**

```
pyverilog_only   ████████▌           9
baseline         ███████████        12     ← same logic as pyverilog_only
retry_only       ████████████       13     ← the control
compiler_only    ██████████████     15
hybrid           ████████████████   18
```

**Add a shaded horizontal band of height 3 labelled "noise floor".**

**Say — three sentences, in this order:**

1. "`hybrid` beats `baseline` by 6 circuits. That looks like a clear win."
2. "But against the fair control it's 5 circuits, not 6."
3. "And look at `pyverilog_only` versus `baseline` — those two ran **effectively identical logic**,
   because our checker never fired, and they still landed **3 circuits apart**. So 3 circuits of
   difference happens by chance. A 5-circuit lead against a 3-circuit noise floor is **p = 0.372 —
   not significant.**"

**Then the line that wins you respect:**
> "So I report no significant advantage, rather than the 13.6-point win the naive comparison gives.
> Building the control is what caught our own overclaim."

**⚠️ Also disclose, one sentence:** "`hybrid` is also the only arm that can act on simulation
feedback, so even its lead can't be credited to the static layer. There's no `simulation_only` arm
to separate them — that's a gap in our design and it's in the report."

*(Saying this before they find it converts a weakness into evidence of rigour. Practise it.)*

---

### Slide 12 — The central finding ★★★ HERO SLIDE · 1:30

**Visual:** 📊 **FIG-5 — horizontal bar chart. What triggered every repair, across all 280 runs.**

```
simulation (ran, wrong answers)   ███████████████████████████  79
blind retry (control)             ██████████████████████       64
compiler errors                   ███                          10
static analysis  ← OUR LAYER      ▏                             1
```

**Make the `1` unmissable** — red label, arrow, large type.

**Say:** "In 280 runs, our static layer triggered **one** repair. `pyverilog_only` repaired **zero
times in 44 runs** — it never found anything to act on. Simulation and compiler feedback did
essentially all the work."

**Then immediately — this is the pivot from bad news to finding:**

> **This is not a broken tool.** Slide 9 proved it catches 100% of what it's built for.
> **The defects simply aren't there any more.** 87% of our observed failures are *semantic* —
> the wiring is perfect, the expected answer is wrong. No structural check can catch that.

---

### Slide 13 — Why? The defect class expired · 1:30

**This is the insight that makes the project interesting rather than merely honest.**

AutoBench's **largest single gain** was a deterministic script that fixed missing output
statements — sequential compile rate **55% → 97%**, +42 points. Same category of technique as ours.

**Our equivalent script fired 6 times in 188 sequential runs.**

**Visual:** 📊 **FIG-6 — bar chart, sequential compile rate.**

```
AutoBench, no standardisation    ███████████            55.5%
AutoBench, with it (their win)   ███████████████████    97.3%
OURS, standardiser doing nothing ██████████████████     90.7%   ← the proof
OURS, strong model               ████████████████████   98.7%
```

**Say:** "Their fix was worth 42 points in 2024. Ours does nothing — and here's the proof it's the
models and not us: the 182 sequential runs where our standardiser **never fired at all** still
compile at 90.7%, against their un-standardised 55%. A pipeline whose fix does nothing compiles 35
points better than a 2024 pipeline without one."

**The takeaway line, in a box:**
> **A fix can stop being valuable because the thing it fixed stopped happening.**
> Techniques in this field have a shelf life, and nobody measures it.

---

### Slide 14 — Challenges · 1:00

Four, honest and brief. These make you look like an engineer, not a script-runner:

| Challenge | What we did |
|---|---|
| **Pyverilog couldn't read 40% of the files** | LLMs write SystemVerilog; Pyverilog targets Verilog-2001. Added a **Verible fallback** on day one so "tool gave up" is distinguishable from "file is clean". |
| **A silent bug made our whole static arm inert** | A missing newline glued two files together — every parse failed, and an empty report looks identical to a clean one. Found and fixed; parse went 0/8 → 7/8. |
| **Text search treated comments as code** | A scenario named `..._overflow` made an unchecked `overflow` output look observed. Detection for that class went **47% → 100%** after blanking strings and comments. |
| **Randomness bigger than the effect** | At temperature 0.7 identical configurations differ by several circuits. We **measured** the noise floor instead of ignoring it. |

**Say:** "The second and third are false negatives — bugs that *hide* problems and look like
success. Neither was caught by the normal test suite. Both were caught by the fault-injection
study, which is the strongest argument for building one."

---

### Slide 15 — Contributions & conclusion · 1:00

**Four contributions:**

1. **A working graph-based pipeline** — 13 nodes, LangGraph, 5 configurations, 280 runs, full
   telemetry. Open source.
2. **A pre-simulation localiser, measured not asserted** — 100% on every class in scope, 0 false
   positives, 30 faults invisible to both the compiler and the simulator.
3. **A control arm the prior work lacks** — and the finding that it changes the conclusion.
4. **A shelf-life result** — the defect class that justified the prior work's biggest gain has
   largely disappeared from current models.

**The closing line — put it on the slide and read it:**

> We built the tool, proved it works, and proved it is no longer needed.
> Only the second half of that is surprising — and we could only find it because we measured
> both halves separately.

**Say:** "A negative result with a validated instrument behind it is worth more than a positive
result without one. That's what this project delivers."

---

### Slide 16 — Thank you / repo · 0:15

- GitHub link
- `results/RESULTS.md` — every number in this talk, traceable to raw data
- 48-page report · 280 runs · ~$16.50

---

## 3. Backup slides (after "Thank you" — do not present, jump to on question)

| # | Covers | Trigger question |
|---|---|---|
| **B1** | Full 13-node table with model + purpose | "walk me through node X" |
| **B2** | Eval2 vs AutoBench: their rule gives us 20% vs their 26% SEQ | "your Eval2 beats theirs" |
| **B3** | Mutant pilot: better mutants +1 pt, different circuits +44 pts | "were your mutants too easy?" |
| **B4** | Parse coverage: 262/434, and readable runs pass at 45.6% vs 6.0% | "what about the files it couldn't read?" |
| **B5** | Co-generation: 273/280 interface match, all 7 diffs are Prob150 | "you generate the circuit too?" |
| **B6** | The one static-triggered repair: 4-row iteration trace | "show me the static repair" |
| **B7** | Cost table: per-mode tokens, `compiler_only` best value | "what did it cost?" |
| **B8** | Repository map | "where's the code?" |
| **B9** | Repair success: 102 attempted, 26 succeeded; no signature ever repeated | "why do repairs fail?" |

---

## 4. Asset list — what to build and what to screenshot

### 📊 Figures to build (7)

| ID | Type | Slide | Priority | Data |
|---|---|---|---|---|
| **FIG-1** | Architecture diagram, 2 columns | 4 | ★★★ | layout in slide 4 above |
| **FIG-2** | Funnel, 3 bars | 8 | ★★ | 280 → 259 → 88 |
| **FIG-3** | Grouped horizontal bars, 8 classes × 3 detectors | 9 | ★★★ | table in slide 9 |
| **FIG-4** | Vertical bars + noise band | 11 | ★★★ | 9, 12, 13, 15, 18 of 44 |
| **FIG-5** | Horizontal bars, 4 rows | 12 | ★★★ | 79, 64, 10, 1 |
| **FIG-6** | Horizontal bars, 4 rows | 13 | ★★ | 55.5, 97.3, 90.7, 98.7 |
| **FIG-7** | Stacked bar *(optional)* | 11 backup | ★ | hybrid 18 = 15 first-try + 3 rescued |

**Chart rules — keep it one visual system:**
- **One accent colour** for "ours / static analysis", one neutral grey for everything else. No
  rainbow palettes.
- In FIG-3, colour **Static** in the accent and Compiler/Simulator in two greys. The story then
  reads without the legend.
- In FIG-5, colour the `static = 1` bar in a **warning red**. It should look alarming — that is the
  point of the slide.
- Label values directly on the bars. **No y-axis gridlines, no chart junk, no 3D, no pie charts.**
  (Pie charts are wrong for FIG-5 — a 1-of-154 slice is invisible, and invisible is the opposite of
  what you want.)
- Sans-serif, minimum 18pt on slides. If a number matters, it should be readable from the back row.

### 📸 Screenshots for you to take (5)

| ID | What | Slide | How |
|---|---|---|---|
| **SHOT-1** | **Pipeline graph, current** | 4 or 5 | ⚠️ **`docs/pipeline_graph.png` is STALE — do not use it.** It predates `gen_dut`, `merge_generation` and `regenerate`, and shows `standardise` disconnected. Regenerate from LangGraph Studio, or use the hand-drawn FIG-1 instead. |
| **SHOT-2** | `show_run.py` static-analysis trace for `Prob150` | B6 | `python scripts/show_run.py 363dfc7e` then screenshot the "Static analysis, pass by pass" table in `results/inspect/363dfc7e/SUMMARY.md`. Shows clean → findings → clean → findings in 4 rows. |
| **SHOT-3** | `results/RESULTS.md` rendered on GitHub | 16, B8 | Shows results are published and traceable. |
| **SHOT-4** | Repo file tree | B8 | `pipeline/`, `prompts/`, `scripts/`, `results/`, `tests/` |
| **SHOT-5** | A generated testbench, ~15 lines | 6 *(optional)* | From any `results/inspect/<id>/testbench.v`. Use it to point at a `$display` line. Consider a syntax-highlighted code block instead — usually cleaner than a screenshot. |

**Note:** you have two screenshots in `screenshots/` from July 2026 and three in `docs/` from June
2026. Check whether they still reflect the current pipeline before using any of them — the codebase
moved a long way after June.

### 📋 Tables (4, all small)

TAB-1 (AutoBench gaps, slide 3) · TAB-2 (Phase 1 nodes, slide 5) · TAB-3 (six checks, slide 6) ·
TAB-4 (five modes, slide 10).

**Rule: maximum 5 rows and 4 columns on any slide table.** Anything bigger goes to backup.

---

## 5. Numbers you must know cold

If you remember nothing else, remember these. Every one is verified against the raw records.

| Number | Meaning |
|---|---|
| **280** | total runs, 4 sweeps, ~$16.50 |
| **92.5% / 31.4%** | Eval0 / Eval1 |
| **215 faults, 100% in-scope, 0 false positives** | the localiser works |
| **33 → 30** | faults invisible to compiler+simulator, and how many static caught |
| **1** | repairs triggered by static analysis in 280 runs |
| **0 of 44** | repairs by `pyverilog_only` |
| **79 / 64 / 10 / 1** | repair triggers: simulation / blind / compile / static |
| **9, 12, 13, 15, 18** | circuits passed of 44: pyv, base, retry, compiler, hybrid |
| **3** | the noise floor, in circuits |
| **p = 0.372** | hybrid vs the control — not significant |
| **6 of 188** | standardiser firings |
| **90.7% vs 55.5%** | our un-standardised compile rate vs AutoBench's |
| **87%** | of failures that are semantic, not structural |

---

## 6. Three things to practise saying

**1. When the null result lands (slide 12).** Don't apologise. Deliver it as a discovery:
> "Our layer fired once in 280 runs — and that is the finding, not the failure. We know it's the
> models and not the tool, because slide 9 measured the tool separately."

**2. The pre-emptive disclosure (slide 11).** Say the `simulation_only` gap *before* anyone asks.
Volunteering a limitation reads as confidence; being caught on it reads as the opposite.

**3. If asked "so was the project a success?"**
> "Yes, and I'd define it precisely. We set out to find whether static analysis can localise
> testbench errors before simulation. The answer is: it can — 100% of every class in scope,
> including faults nothing else can see — but against current models there is very little left for
> it to find. We can state that with confidence rather than as a guess, because we validated the
> instrument separately and ran a control arm the prior work doesn't have. A measured negative is
> a better outcome than an unmeasured positive."

---

## 7. Build order (suggested)

1. **FIG-3, FIG-4, FIG-5** — the three hero charts. If only three things are polished, these.
2. **FIG-1** — the architecture spine.
3. Slides 9, 11, 12, 13, 15 — the argument.
4. FIG-2, FIG-6, the tables.
5. Slides 2–8 — context.
6. Backup slides.
7. Screenshots last.

**Rehearse with a timer.** The single most common failure in a 20-minute talk is spending 12
minutes on setup and rushing the results. Your results are the good part — protect slides 9 through
13 above everything else.
