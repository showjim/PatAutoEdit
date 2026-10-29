# Plan: Expand SRM loops and counter repeats

Branch: `feat/expand-loop-microcode` (off `master`)

## Problem

UltraPin1600 SRM modules (`srm_vector`) use `loop` / `end_loop` to run a block
of vectors many times, with the loop count loaded into a user counter by
`set_msb` / `set cX`. Counters also drive `repeat cX`. The tool cannot flatten
any of this:

- `loop` / `end_loop` are **SRM-only** opcodes; they do not execute in VM. An
  expanded loop is far deeper than SRM allows (1023 vectors), so the expanded
  module must become a `vm_vector` module.
- `Expand Pattern` only understands `repeat <integer>`.
  [`get_repeat_cnt`](../../src/utils.py#L66) matches `repeat\s+\d+`, so
  `repeat c0` counts as one cycle and passes through untouched. Every
  cycle-indexed mode chained after it (DSSC, CMEM, WFLAG, Add Opcode) then
  miscounts.

Loops may nest, each level with its own counter, and one counter may serve
several loops and repeats in turn.

## What we found before designing

### Microcode semantics (MyInfo Copilot, UltraPin1600, IG-XL 11.10.00)

| Opcode | Behaviour | VM |
| --- | --- | --- |
| `set_msb M` | Temporary MSB register = upper 12 bits of (M−1). Must run at least once before any `set`; stale MSBs persist until the next `set_msb`. 1 ≤ M ≤ 2²⁸−1. | yes |
| `set cX N` | Counter cX = (MSB << 16) \| low16(N−1). 28-bit counter. | yes |
| `loop cX` | Pushes cX on the counter stack. NOP on the loop's own later iterations. In Single mode it may sit on the vector the `end_loop` label marks, or before it. | **SRM only** |
| `end_loop lbl` | Counter on top of the stack = 0 → pop and fall through; else decrement and jump to `lbl`. **When the loop ends the counter is back at its originally set value**, so it can be reused. | **SRM only** |
| `repeat cX` | Executes the vector counter + 1 times. | yes |
| `repeat N` | Literal repeat, 1 ≤ N ≤ 65536 in VM. | yes |

So a loop or counter repeat whose counter was loaded with `set cX N` runs
**N times**. UltraPin1600 has 16 user counters; loops nest at most 16 deep.

**Counter reuse, confirmed against Teradyne patterns:** one counter keeps its
value across different `loop` and `repeat cX` uses. MyInfo's short summaries
sometimes say a loop "consumes" its counter, but the detailed Loop Opcodes page
says another loop can use the same counter at its originally set value, and
the documentation is silent on `repeat cX`; the pattern check settles both.

`set_msb` is allowed inside a loop body. Its only placement rules are not to
share a vector with `refresh_en`, and the match-loop timing rule.

MTO commands on a vector (`(mto = xa inc ya inc_link_x)`) execute on **every**
cycle that vector runs, repeated or looped. Teradyne's own MTO example
`march6n.atp` relies on this to walk 32768 addresses.

Sources:
[Digital Pattern Opcodes](https://myinfo-support.teradyne.com/documentation/r/UltraPin1600-Specifications/Digital-Patterns/Digital-Pattern-Opcodes/IGXL11.10.00),
[Loop Opcodes](https://myinfo-support.teradyne.com/documentation/r/Vector-Data-Microcode/Opcodes-and-Control-Bits/Loop-Opcodes/IGXL11.10.00),
[Counter Opcodes](https://myinfo-support.teradyne.com/documentation/r/Vector-Data-Microcode/Opcodes-and-Control-Bits/Counter-Opcodes/IGXL11.10.00),
[Repeat Opcodes](https://myinfo-support.teradyne.com/documentation/r/Vector-Data-Microcode/Opcodes-and-Control-Bits/Repeat-Opcodes/IGXL11.10.00),
[Pattern Flow Control](https://myinfo-support.teradyne.com/documentation/r/UltraPin1600-Specifications/Digital-Patterns/Pattern-Flow-Control/IGXL11.10.00),
[MTO Address Counters](https://myinfo-support.teradyne.com/documentation/r/MTO-Theory-of-Operation/MTO-Memory-Pattern-Generator/Address-Generators/Address-Counters/IGXL11.10.00).

### The samples

`Sample/expand_loop/march6n.atp` (moved from `project/expand_loop/`):
`set_msb 32768`, `set c0 32768`, then `repeat c0`, two sequential `loop c0`
blocks and another `repeat c0`. One counter, four consumers — only correct
because of the reload rule.

`Sample/expand_loop/mychecker.atp`: `write_cols` (`c0` = 32) nests
`write_rows` (`c1` = 255), then the same pair again for reading. The inner loop
restarts on every outer pass. Opcodes combine with commas (`set c1 255, stv`,
`loop c1, stv`, `end_loop read_rows, stv`). The module name sits on the line
after `srm_vector`.

### Existing `Expand Pattern` behaviour this must match

[`remove_repeat`](../../src/pattern_processor.py#L26) treats every non-`>` line
before a vector as part of that vector and writes the whole block on every copy.
Full-line `//` comments inside a module body are skipped. A trailing comment
after `;` is copied onto every copy.

**Defect found (review):** every scratch file was named with
`something.replace('.atp', '_<Tag>.atp')`. That is case-sensitive, so for
`x.ATP` the scratch path *is* the source: it is opened for writing (emptied),
then moved to `Output/` and deleted, and the run reports success with a 0-byte
output. A user's own `x_<Tag>.atp` next to the source was overwritten and
deleted too. This affected every mode on `master`, not only the new ones.

**Defect found:** because the whole block is copied, a label on the line above a
`repeat N` vector is written once per repeat
([pattern_processor.py:65-67](../../src/pattern_processor.py#L65-L67)), and the
duplicate labels do not compile. None of the files in `Sample/` has a label
directly above a `repeat` vector, so fixing it does not move the regression
baseline.

## Decisions

| Area | Decision |
| --- | --- |
| Modes | Two jobs, two modes. **`Expand Repeat`** flattens `repeat N` and `repeat cX`. **`Expand Loop`** flattens `loop` / `end_loop`. Neither needs a pin or a cycle. |
| `Expand Pattern` | Kept as an **alias of `Expand Repeat`**: same code path, same output, including the new `repeat cX` handling. To be dropped in a future version. |
| Scope of `Expand Repeat` | Any module type (`repeat cX` is legal in VM and SRM). Module type is never changed. |
| Scope of `Expand Loop` | `srm_vector` modules only. A module that contained loops becomes `vm_vector`. **An `srm_vector` with no loops stays SRM.** `vm_vector` and `vector` modules pass through untouched. Literal `repeat N` is left alone. |
| Counter model | Emulate the hardware: track the MSB register and each counter as the module is read top to bottom, including across loop iterations. A `set` inside a loop body takes effect in later iterations. |
| Loop body | From the vector the `end_loop` label marks, through the `end_loop` vector. Each copy carries its own instrument (`mto`) lines. |
| `set` / `set_msb` removal | Strip the opcode **text** only; the vector stays. Other opcodes on the line stay (`set c1 255, stv` → `stv`). Stripped text is replaced with spaces so columns stay aligned. |
| When to strip `set cX` | Only if, after the mode's own expansion, **no `loop cX` and no `repeat cX` remains in that module**. Strip `set_msb` only once no `set` remains in the module. Either mode order gives the same final file. |
| Labels | Labels referenced only by `end_loop` are dropped. Any other label inside an expanded loop body is kept on the first copy only, with a warning. For `repeat N` and `repeat cX`, a label above the vector is written on the first copy only (fixes the defect above). |
| Comments | Same as today's `Expand Pattern`, in both modes: full-line `//` comments inside a module body the mode rewrites are dropped; trailing comments after `;` go on every copy. Header comments are kept. |
| Time mode | **Single only** for `Expand Loop` and for `repeat cX`. `opcode_mode=dual` / `quad` in the file, or Dual from the GUI, fails the file. `repeat N` keeps today's Dual support. |
| Unresolvable input | Fail the file (`edit_pattern` returns `None`, the chain stops for that file only), with line number and opcode in the error. |
| Size | **No cap.** Output is streamed; memory scales with the source module, not the expansion. |
| Nothing to expand | Copy through unchanged, log an info line; the chain continues. |

### Fail-the-file cases

Inside a module being expanded:

- Flow that depends on runtime state or other modules: `jump`, `call`,
  `return`, conditional branches (`branch_expr`, `if (…)`).
- Counter-stack opcodes: `push_loop`, `pop_loop`, `clr_loop`.
- Infinite counters: `set_infinite`, `set_msb_infinite`. The tool's own `WFLAG`
  mode inserts these, so running `Expand Loop` after `WFLAG` fails by design.
- An opcode **this mode expands** whose counter has no visible `set` (e.g.
  loaded from VBT via `TheHdw.Digital.Patgen.Counter`), or a `set` before any
  `set_msb`. An opcode the mode leaves in place (a `repeat cX` under
  `Expand Loop`, a `loop cX` under `Expand Repeat`) does not need its value, so
  an unset counter there is fine; the later mode checks it.
- `Expand Repeat` only: a `repeat cX` inside or after a loop body that holds
  both a `set_msb` and a `set cX`. The MSBs change between passes, so cX has a
  different value on each pass, and this mode reads each body once. The error
  says so and to run `Expand Loop` first; that order expands it correctly. This
  is a limit of the tool, not of the hardware: `set_msb` is legal in a loop.
- An `end_loop` whose label is not defined earlier in the module, or an
  `end_loop` with no matching `loop` on the stack.
- An `end_loop` with a relative address instead of a label. The docs allow
  it but no sample uses it; the code carries
  `# TODO: support end_loop with a relative address` at the point it fails.
- Dual / Quad mode as above.

## Code changes

### `src/counter_expand.py` (new)

- **Vector record parser.** Groups a module body into records: leading lines
  (labels, instrument lines, full-line comments), the opcode field before `>`,
  and the rest of the vector line. Splits the opcode field on commas. Detects
  module header (`srm_vector` / `vm_vector` / `vector`, module name on the
  same or the next line) and the closing `}`.
- **`CounterState`.** MSB register plus `c0`–`c15`; `set_msb`, `set`,
  `count(cX)` implementing the formulas above; errors on read-before-set.
- **`expand_loops(src, dst, logger)`.** Per SRM module: resolve the
  label → `end_loop` structure with a counter stack, buffer the module body,
  then emit by walking it recursively, N iterations per loop. Applies the
  strip rule, the label rule, and renames the header to `vm_vector` when the
  module had loops.
- **`expand_counter_repeats(src, dst, logger)`.** Per module: emits a
  `repeat cX` vector N times with `repeat cX` stripped, then applies the strip
  rule.

### `src/pattern_processor.py`

- **`remove_repeat`** — keep label lines on the first copy of a repeated
  vector only; instrument lines and the vector itself are still copied each
  time. Applies to Single and Dual.
- **`edit_pattern`** — `Expand Pattern` and `Expand Repeat` share one branch:
  `expand_counter_repeats` first (skipped when the file has no `repeat cX`, so
  Dual-mode files without counters behave exactly as today), then
  `remove_repeat`. New `Expand Loop` branch calls `expand_loops`. Both return
  `None` on failure.

### `src/file_ops.py`

- **`scratch_path(source, tag)`** — `<name>_<tag><ext>` with the extension
  taken from `source` as written (`.ATP` stays `.ATP`, `.atp.gz` stays
  `.atp.gz`), so it can never equal the source. Raises `FileExistsError`, and
  the mode fails naming the file, rather than overwrite a file already there.
  Used by `remove_repeat`, `add_repeat`, `remove_opcode`, and the two new modes.

### `src/atp_handler.py`

- **`MODE_LIST`** — add `Expand Repeat` and `Expand Loop`. Neither joins
  `_PIN_MODES`, `_CYCLE_MODES` or `_USER_STRING_MODES`.

### `PAE.py`, `PAE_webapp.py`

- No code change expected: both read `MODE_LIST`. Smoke-test that the two new
  modes appear and run.

### `Sample/expand_loop/`

- Commit `march6n.atp` and `mychecker.atp` as fixtures. A subfolder keeps them
  out of `test/regression_baseline.py`, which reads only the top of `Sample/`.

### `README.md`

- List `Expand Repeat` and `Expand Loop`; mark `Expand Pattern` as a
  deprecated alias of `Expand Repeat`. Show the chain
  `Expand Loop` → `Expand Repeat` for a fully flat VM pattern. Note Single
  mode only.

## Verification

New script `test/expand_loop_check.py`, in the style of `test/config_checks.py`.

1. **Vector counts** (hand-derived from the counter rules):

   | Sample | `Expand Loop` only | `Expand Repeat` only | Both, either order |
   | --- | --- | --- | --- |
   | `march6n.atp` | 131,077 | 65,543 | **196,611** |
   | `mychecker.atp` | **65,543** | unchanged | 65,543 |

   `mychecker`: 3 setup + 32 × (2 + 255 × 4 + 2) write + 2 + 32,768 read + 2.
2. **Opcode residue.** After both modes: no `loop`, `end_loop`, `repeat c`,
   `set c`, `set_msb`. After `Expand Loop` alone on `march6n`: `set_msb`,
   `set c0` and two `repeat c0` remain.
3. **Header.** `vm_vector` when the module had loops; an SRM module with no
   loops stays `srm_vector`.
4. **MTO.** Every expanded copy of a vector that had an `(mto = …)` line still
   has it.
5. **Other opcodes kept.** `stv` from `set c1 255, stv` and from
   `loop c1, stv` / `end_loop …, stv` survives.
6. **Order independence.** `Expand Loop` → `Expand Repeat` and the reverse are
   byte-identical.
7. **Alias.** `Expand Pattern` and `Expand Repeat` outputs are byte-identical.
8. **Synthetic cases** built in the script: `set` inside a loop body;
   `set_msb` above 65536 so the MSBs matter; stale MSBs; a non-`end_loop` label
   inside a body (first copy only, warning logged); a label above a `repeat N`
   vector and above a `repeat cX` vector (exactly one copy of the label in the
   output); full-line `//` comments inside a loop body (absent from the
   output).
9. **Failure fixtures**, each asserting no output is reported: `push_loop`,
   `jump`, `set_infinite`, a counter with no `set`, `set` before `set_msb`,
   an undefined `end_loop` label, an `end_loop` with a relative address,
   `opcode_mode=dual`.
   - **`set_msb` in a loop body:** `repeat c1` inside and after a body holding
     `set c1 2` and `set_msb 65537`. `Expand Loop` → `Expand Repeat` gives
     65,540 and 65,538 runs; `Expand Repeat` alone fails, naming `set_msb`,
     `c1` and "run Expand Loop first". A body with `set_msb` but no `set c1`
     does not trigger it.
   - **Unread counters:** an unset `repeat c1` under `Expand Loop` and an
     unset `loop c0` under `Expand Repeat` are left in place, not rejected.
   - **Scratch files** (`test/config_checks.py`): every scratch-using mode
     on `Upper.ATP` keeps the source and writes a non-empty output; an existing
     `Mine_<Tag>.atp` survives and the mode fails naming it.
10. **Regression.** `test/regression_baseline.py` shows the existing `Sample/`
    outputs are unchanged (none of them uses counters or SRM).
11. **GUI smoke.** Both new modes run from the Tk Simplified tab and the
    Streamlit app.

## Out of scope / deferred

- **Dual and Quad mode** for `Expand Loop` and `repeat cX`. The record parser
  keeps vector grouping in one place so this can be added later.
- **Size limits.** Deliberately none; handled by other tooling.
- **Match loops** (`match`, `match_vm`). Device-dependent, so they cannot be
  flattened, but not detected for now.
- **`end_loop` with a relative address.** Fails today; marked `TODO` in code.
- **Removing `Expand Pattern`.** Future version.

## Known limitations

- `Expand Loop` and `Expand Repeat` change cycle numbering downstream in a
  chain. Chain order matters and is the user's responsibility.
- `WFLAG` output cannot be loop-expanded (infinite counters).
- A label kept on the first copy of an expanded body may no longer mean what
  it did, if something outside the module jumps to it.
