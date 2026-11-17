# Preloaded Counters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Expand Loop and Expand Repeat expand ATPs whose counters the IG-XL test program loads, using run counts typed in `User String`. Also warn when Expand Loop writes MTO lines into a `vm_vector` module.

**Architecture:** On an Expand row, `User String` holds `cN=run count` pairs. `parse_counter_values` in `src/counter_expand.py` reads them, and `_validate_config` rejects bad text before anything runs. `edit_pattern` passes the parsed values to `expand_loops` / `expand_counter_repeats`. These seed each module's `_Counters`, as if the VBT had loaded the counters just before the pattern starts.

**Tech Stack:** Python 3.11, standard library only. Checks are plain scripts run with `python test/<name>.py`; there is no pytest.

**Spec:** the Decisions table below, plus [GLOSSARY.md](../../GLOSSARY.md) (Expand, Run count, Preloaded counter, Variant), [ADR 0001](../adr/0001-counter-values-from-the-user.md) and [ADR 0002](../adr/0002-expanded-mto-patterns-are-not-compiled.md).

## Global Constraints

- Standard library only; no new dependency.
- `User String` format: `cN=run count` pairs separated by `;`. Spaces around tokens are allowed, `c` or `C`, counters `c0`–`c15`, decimal values 1–268,435,455, each counter at most once. Empty segments (a trailing `;`) are ignored; blank text means no values.
- A value is a **run count**: the N in `set cX N`. `_Counters` stores N − 1, the register value. A preload does not set the MSB register, so an in-pattern `set` still needs its own `set_msb` first.
- Preloaded values are each module's counter state when it starts. In-pattern `set` overrides them from that vector on.
- Counter expansion stays Single mode only, as today.
- No change to CSV columns or `Sample/` fixtures. Checks build their own patterns. Never use files under `project/` (customer data, git-ignored).
- Bump `version` in `PAE.py` once: `V1.15.1` → `V1.16.0`.
- No commits unless the user asks.
- Message texts, copied verbatim (`{…}` are values):
  - Parse errors (`ValueError` text):
    - `cannot read {segment!r}; write cN=run count, separated by ';' (for example c0=262144; c7=8)`
    - `c{n} is not a user counter (c0..c15)`
    - `c{n} is given twice`
    - `c{n}={value} is outside 1..268435455`
  - Rejected config: `{mode} on {file}: User String: {reason}`
  - Missing counter: `{user} c{n} uses a counter that is never set in this module; if the test program loads it, add c{n}=<run count> to User String`
  - Unused values (info, counters in ascending order): `{path}: User String values not used by {mode}: c1, c7`
  - MTO (warning, once per file): `{path}: MTO lines kept in a vm_vector module: IG-XL can't compile this file; use it as input for an MTO data tool`

## Review Focus

1. In the Tk Classical tab, the default text "Please Enter the User String" left in the box must count as empty for every mode, not fail parsing. Task 4 covers it; it is a manual GUI check.
2. Values pasted in VBT style with commas (`c0=262144, c7=8`) are rejected before anything runs, and the message shows the expected format. Task 1 check.
3. The same `User String` on both an Expand Loop row and an Expand Repeat row: both succeed, and either order gives byte-identical output. Task 2 check.
4. Expand Repeat with values on a file that has no `repeat cX`: the output is identical to a run without values, plus one info line. Task 2 check.
5. An MTO file run through Expand Repeat only stays SRM and logs no MTO warning; only Expand Loop warns. Task 3 check.

## Decisions

| Area | Decision |
| --- | --- |
| Purpose | Expand ATPs whose counters the test program loads. For MTO patterns, the output is input for a separate MTO data tool and is never compiled ([ADR 0002](../adr/0002-expanded-mto-patterns-are-not-compiled.md)). |
| Source of values | `User String` on the Expand row. EditPat never reads the workbook, test instances or flow table ([ADR 0001](../adr/0001-counter-values-from-the-user.md)). |
| Modes | Expand Loop, Expand Repeat and its alias Expand Pattern. Other modes keep today's meaning of `User String`. |
| Meaning | Run counts. A VBT line `Patgen.Counter(tlPgCounterN) = X` loads the register directly, so the run count is X + 1 (MyInfo, `TheHdw.Digital.Patgen.Counter`, IG-XL 11.10.00). |
| Missing value | A counter the mode needs, with no value and no `set`, fails the file. The message points to `User String`. |
| Unused values | Ignored, with one info line per file per mode, so one string can go on every Expand row. |
| Validation | Checked with the rest of the config, before anything runs. |
| Variants | One renamed copy of the ATP per set of values. No new column. |
| MTO | Expand Loop keeps expanding MTO modules and warns once per file. Expand Repeat logs nothing. The README notes that an expanded SRM module must stay within about 1,000 vectors to run. |
| Vector 0 / `repeat 2` | Not handled by EditPat and not documented: the VBT side fixes it after expansion. |
| Output layout | Unchanged. |
| Tk hint text | "Please Enter the User String" counts as empty, in every mode. |

## Later changes

- 2026-11-17, at the user's request: two samples were added in `Sample/expand_loop/`, `counters_set_in_atp.atp` and `counters_preloaded_mto.atp`, with rows in `Sample/Sample_ATP - simple.csv`. `check_samples` in `test/expand_loop_check.py` covers them. The "no `Sample/` changes" constraint is lifted for these files.
- Found while compiling the samples with `apc` 11.10.00: a VM module needs at least 64 vectors in single mode. So an Expand Loop output under 64 vectors does not compile; the compiler says "Minimum size is 64 vector(s)".

## Pre-work

- [x] Capture the regression baseline before any code change. Done 2026-11-17 into the session scratchpad: `run-sample`, `run-chain4`, `run-classical`.
- [x] `python test/config_checks.py` and `python test/expand_loop_check.py` pass on unmodified code.

---

### Task 1: Read counter values from User String and reject bad text up front

**Files:**
- Modify: `src/counter_expand.py` (add `parse_counter_values`)
- Modify: `src/atp_handler.py` (add `COUNTER_MODES`; `build_config_from_classical` docstring for `user_string`)
- Modify: `src/main.py` (`_validate_config`)
- Test: `test/config_checks.py`

**Interfaces:**
- Produces: `parse_counter_values(text: str) -> Dict[int, int]` in `src/counter_expand.py`. It maps counter number to run count and raises `ValueError(reason)`.
- Produces: `COUNTER_MODES = ('Expand Pattern', 'Expand Repeat', 'Expand Loop')` in `src/atp_handler.py`.

- [x] **Step 1: Write the failing checks** in `test/config_checks.py`. Import `parse_counter_values`, add `check_counter_values(work)`, and register it in `main()`. Assertions:
  - `parse_counter_values('c0=262144; c7=8') == {0: 262144, 7: 8}`
  - `parse_counter_values(' C0 = 5 ;c15=1; ') == {0: 5, 15: 1}`
  - `parse_counter_values('') == {}` and `parse_counter_values('   ') == {}`
  - `parse_counter_values('c0=268435455') == {0: 268435455}`
  - Each of these raises `ValueError` whose text contains the second item:

    ```python
    [('c0', 'cannot read'), ('c0=1, c7=8', 'cannot read'), ('c0=0x10', 'cannot read'),
     ('c16=1', 'c16 is not a user counter'), ('c0=1; c0=2', 'c0 is given twice'),
     ('c0=0', 'outside 1..268435455'), ('c0=268435456', 'outside 1..268435455')]
    ```
  - In `check_validation`, add a case: `('Expand Loop with an unreadable User String is rejected', [_op([], 'Expand Loop', '', 'c0=abc')])`, expecting `result == []`.
  - Also capture messages (`Logger(gui_callback=messages.append)`) for that config, and check that an `Error` line contains `Expand Loop on Sample_ATP.atp: User String: cannot read 'c0=abc'`.
- [x] **Step 2: Run `python test/config_checks.py`.** Expected: `ImportError: cannot import name 'parse_counter_values'`.
- [x] **Step 3: Implement.**
  - `parse_counter_values` follows the format and messages in Global Constraints. Reuse `_COUNTERS` and `_MAX_VALUE`.
  - In `_validate_config`, for each op whose `Mode` is in `COUNTER_MODES`, call `parse_counter_values(op.get('UserString', ''))`. On `ValueError`, append the "Rejected config" message to `problems`.
- [x] **Step 4: Run `python test/config_checks.py`.** Expected: `All checks passed.`

### Task 2: Expand with preloaded counters

**Files:**
- Modify: `src/counter_expand.py`: `_Counters`, `_expand_module_loops`, `expand_loops`, `_expand_module_repeats`, `expand_counter_repeats`; add `log_unused_counters`
- Modify: `src/pattern_processor.py`: `edit_pattern`, the Expand Repeat / Expand Pattern / Expand Loop branches
- Test: `test/expand_loop_check.py`

**Interfaces:**
- Consumes: `parse_counter_values` (Task 1).
- Produces:
  - `expand_loops(src, dst, timemode, logger, counters: Optional[Dict[int, int]] = None) -> bool`
  - `expand_counter_repeats(src, dst, timemode, logger, counters: Optional[Dict[int, int]] = None) -> bool`
  - `log_unused_counters(logger, path: str, mode: str, counters: Dict[int, int], used: Set[int]) -> None` logs the "Unused values" line when `set(counters) - used` is not empty.
  - `_Counters(preloaded: Optional[Dict[int, int]] = None, used: Optional[Set[int]] = None)` starts with `values = {c: n - 1}` and `msb = None`. `get` adds the counter to `used`.

- [x] **Step 1: Write the failing checks** in `test/expand_loop_check.py`.
  - `run_chain` and `run_text` gain `user_string=''`, which goes into every op's `"UserString"`.
  - Add `check_preloaded_counters()` and register it in `main()`. Its fixture:

    ```python
    _PRELOADED = srm('                > t 0 ;\n'
                     'top:\n'
                     'loop c0         > t 1 ;\n'
                     'repeat c7       > t H ;\n'
                     'end_loop top    > t L ;\n'
                     'halt            > t 0 ;\n')
    ```
  - Assertions, with `user_string='c0=3; c7=2'` unless stated:
    1. Expand Loop succeeds with 11 vectors. `repeat c7` appears 3 times. An `Info` line contains `not used by Expand Loop: c7`.
    2. Expand Loop → Expand Repeat succeeds with 14 vectors and 6 vectors ending in `H`. No `loop`, `end_loop` or `repeat c` is left. An `Info` line contains `not used by Expand Repeat: c0`.
    3. Expand Repeat → Expand Loop gives byte-identical text to case 2.
    4. With `'c0=1; c7=2'`, Expand Loop gives 5 vectors.
    5. On `srm('repeat c0       > t 1 ;\nset_msb 4       > t 0 ;\nset c0 4        > t 0 ;\nrepeat c0       > t H ;\nhalt            > t 0 ;\n')` with `'c0=2'`, Expand Repeat gives 2 vectors ending in `1` and 4 ending in `H`.
    6. On `srm('set c0 4        > t 0 ;\nrepeat c0       > t 1 ;\n')` with `'c0=2'`, Expand Repeat fails: `expect_failure(..., 'set_msb')`.
    7. On `_PRELOADED` with `'c0=3'`, Expand Repeat fails. The errors contain `c7` and `User String`.
    8. On `_PRELOADED` with `'c0=abc'`, Expand Loop fails, and the errors contain `User String: cannot read 'c0=abc'`.
    9. `run_chain(SAMPLE_ATP, ['Expand Repeat'], user_string='c0=5')` has the same text as the run without a user string. An `Info` line contains `not used by Expand Repeat: c0`.
- [x] **Step 2: Run `python test/expand_loop_check.py`.** Expected: FAIL lines in `check_preloaded_counters`, with errors like `loop c0 uses a counter that is never set`.
- [x] **Step 3: Implement.**
  - Wire `counters` and one per-file `used` set through both module functions into `_Counters`.
  - After the module loop, both public functions call `log_unused_counters(logger, src, mode, counters or {}, used)`.
  - `_Counters.get` uses the "Missing counter" text.
  - In `edit_pattern`, parse `user_string` with `parse_counter_values` at the top of the three Expand branches. On `ValueError`, log the "Rejected config" text with `something` as the file and return `None`.
  - Pass `counters` on to `expand_counter_repeats` and `expand_loops`.
  - When `has_counter_repeat` is false, call `log_unused_counters(logger, something, 'Expand Repeat', counters, set())`.
  - The Expand Pattern alias reports as `Expand Repeat`, as its errors already do.
- [x] **Step 4: Run both scripts.** Expected: `All checks passed.` twice.

### Task 3: Warn when Expand Loop writes MTO lines into a vm_vector module

**Files:**
- Modify: `src/counter_expand.py` (`expand_loops`; new `_has_mto`)
- Test: `test/expand_loop_check.py` (`check_march6n`, `check_synthetic`)

**Interfaces:**
- Produces: `_has_mto(records: List[_Record]) -> bool` (private). It is true when a record's opcode field, or one of its `pre` lines of kind `'other'`, matches `re.compile(r'\(\s*mto\s*=', re.IGNORECASE)`.

- [x] **Step 1: Write the failing checks.**
  - In `check_march6n`, check `el.warnings().count('MTO lines kept in a vm_vector module') == 1` for Expand Loop, and `'MTO lines kept' not in er.warnings()` for Expand Repeat.
  - In `check_synthetic`, check that the first case (no MTO, Expand Loop) gives `'MTO lines kept' not in r.warnings()`.
- [x] **Step 2: Run `python test/expand_loop_check.py`.** Expected: FAIL on the march6n warning check.
- [x] **Step 3: Implement.** In `expand_loops`, note whether any module it expands has `_has_mto`. After the loop, log the "MTO" warning once.
- [x] **Step 4: Run `python test/expand_loop_check.py`.** Expected: `All checks passed.`

### Task 4: GUI text, docs and version

**Files:**
- Modify: `PAE.py` (hint constant, Classical run, `version`)
- Modify: `PAE_webapp.py` (User String help)
- Modify: `README.md`
- Modify: `doc/feat-expand-loop/plan.md`

- [x] **Step 1: Update `PAE.py`.**
  - Add the module constant `_USER_STRING_HINT = "Please Enter the User String"` and use it in `self.contents7.set(...)`.
  - In `run_classical_multiprocess`, set `UserString = ""` when `UserString.strip() == _USER_STRING_HINT`.
  - Set `version = 'V1.16.0'`.
- [x] **Step 2: Update the `User String` help in `PAE_webapp.py`:** `"Add Opcode / Remove Opcode: the opcode text. Expand Repeat / Expand Loop: counter run counts, e.g. c0=262144; c7=8"`.
- [x] **Step 3: Update `README.md`.**
  - Feature list: Expand Repeat and Expand Loop accept counter values in `User String`.
  - `User String` table row: the opcode text for Add/Remove Opcode, or run counts for the three Expand modes.
  - New section "Counters loaded by the test program". It covers why values are needed, the format, run counts (`Counter = X` → type X + 1), the three behaviour rules, renamed copies for variants, and links to ADR 0001 and the glossary.
  - New section "MTO patterns". It covers the Expand Loop warning, that the output is for an MTO data tool, and the SRM limit of about 1,000 vectors for Expand Repeat output. Link ADR 0002.
- [x] **Step 4: Update `doc/feat-expand-loop/plan.md`.**
  - Under "Known limitations": MTO lines in a `vm_vector` module don't compile (`apc` 11.10.00), so Expand Loop output for MTO patterns is for an MTO data tool, and Expand Loop warns (ADR 0002).
  - On the "loaded from VBT" fail case: point to this plan.
- [x] **Step 5: Verify.**
  - `python test/config_checks.py` and `python test/expand_loop_check.py` both print `All checks passed.`
  - `python -m py_compile PAE.py PAE_webapp.py` succeeds.
  - Regression: rerun `test/regression_baseline.py run-sample|run-chain4|run-classical` into a new folder, then `diff` against the baseline. Expected: every file identical.
  - Manual, reported to the user:
    - Classical tab, Expand Loop on a small file with the hint text left in the box. It runs.
    - Web app: the User String help shows the new text.
