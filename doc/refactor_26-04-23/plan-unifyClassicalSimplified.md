# Plan: Unify Classical + Simplified Backends (Fix Previous AI Refactor)

## Audit: What the previous AI did wrong

### 1. The unified path is **dead code** — never invoked by the UI
- The Classical tab's `Generate` button is wired to [`run_classical_multiprocess`](PAE.py#L300), not `run_classical`.
- `run_classical_multiprocess` still calls [`read_csv`](src/atp_handler.py#L13) + dispatches [`edit_pattern`](PAE.py#L343) directly to the `multiprocessing.Pool` — it does not go through `process_atp_classical` or `build_config_from_classical` at all.
- The AI's new [`build_config_from_classical`](src/atp_handler.py#L27) and the rewritten [`process_atp_classical`](src/main.py#L13) are only reachable from the unused [`run_classical`](PAE.py#L273) (single-process) path. So the "unification" never runs.

### 2. `process_atp_classical` does a lossy filesystem round-trip
In [`src/main.py`](src/main.py#L26-L45), after building a clean in-memory config list, the code **serializes it back to a temp CSV file** just so `process_atp_simple` can re-parse it via `analyse_merge_config`. Two problems:
- It's an unnecessary filesystem trip when the data is already in the target shape.
- The line `cycle_str = ';'.join([f'[{c}-{c}]' for c in item['CycleRange']])` is **semantically wrong**: by the time we reach this code, `CycleRange` is already a flat list of expanded integer cycles (see [`process_input_cycles`](src/utils.py#L32) which returns a 1-D list via `convert2oneDlist`). A range like `[20-10]` in the original CSV has already been exploded to `[10,11,…,20]`; re-emitting each as `[N-N]` is a correctness trap if anything downstream reads it as ranges again.

### 3. `process_atp_simple` cannot accept a pre-built config list
Because it only accepts a file path and internally calls `analyse_merge_config`, there's no clean way to feed it an in-memory config. That forced the temp-file hack above. The right shape is: have `process_atp_simple` accept *either* a path or an already-parsed config list (or split the parser from the processor).

### 4. Duplicated parallel logic was never unified
[`run_classical_multiprocess`](PAE.py#L300) and [`run_simple_multiprocess`](PAE.py#L248) both re-implement the dispatch loop. The real duplication problem (multiprocess dispatch of `edit_pattern`) wasn't addressed — only the rarely-used single-process path was "cleaned up."

### 5. Minor inconsistencies
- `run_simple_multiprocess` is not bound to any button (the Simplified tab button calls `run_simple`, the single-process one), yet is still maintained. Likely stale.
- In `run_classical_multiprocess`, pinmap expansion is done once outside the loop (OK for classical because mode/pin are fixed); in `process_atp_simple`, it's done per-item (correct for simple). This asymmetry needs to be preserved when unifying.
- `single_item_post_process_simple` in PAE.py is submitted to `Pool.apply_async` as a **bound method of a Tk widget** — `self` is not picklable on Windows (spawn start method). This path would crash if ever invoked.

---

## Plan: Unify Classical + Simplified Correctly

**TL;DR** — Introduce a real "config list" as the single internal representation, feed it to **both** the single-process and the multi-process dispatchers, and rewrite the two UI handlers to be thin wrappers that only *build the config list* differently. Remove the temp-CSV hack and the dead single-process wrappers.

### Phase 1 — Core data model (foundation)
1. In [`src/atp_handler.py`](src/atp_handler.py), split `analyse_merge_config` so it returns the list-of-dicts it already produces (no change), and keep `build_config_from_classical` but **fix its semantics**: it should produce config items whose `CycleRange` field holds the same flat integer list that `analyse_merge_config` produces for a simple-CSV row (already does — the bug is only on the *re-emit* side, which we'll delete).
2. Fix the `read_csv` operator-precedence bug at [`src/atp_handler.py` L19](src/atp_handler.py#L19): `len(row[0]) or len(row[1]) > 0` → `len(row[0]) > 0 or len(row[1]) > 0`.

### Phase 2 — Single processing engine that accepts config list
3. In [`src/main.py`](src/main.py), refactor `process_atp_simple` to accept either a `merge_config_file: str` **or** a `config_list: List[Dict]` parameter (mutually exclusive). Internal logic stays the same from the point after `analyse_merge_config`. This removes the need for the temp-file hack.
4. Rewrite `process_atp_classical` as a **3-line** wrapper: `config_list = build_config_from_classical(...)` → `process_atp_simple(atp_files, config_list=config_list, logger=logger, pin_map=pin_map)`. Delete the temp-file code.

### Phase 3 — Single multi-process dispatcher
5. Extract a new module-level helper in [`src/main.py`](src/main.py), e.g. `dispatch_config_parallel(pool, atp_files, config_list, mp_logger, pin_map, callback) -> int` that:
   - iterates `config_list`, performs pinmap expansion per item (same as `process_atp_simple`),
   - submits each item via `pool.apply_async(edit_pattern, args=...)`,
   - returns the total number of tasks submitted.
   - Note: items that share the same `ATPFile` in simple mode have **sequential dependency** (second op reads first op's output). Multi-process dispatch must serialize those. Simplest solution: group by `ATPFile`, dispatch one group per worker via a small sequential helper function (must be module-level so it's picklable on Windows).
6. Add a module-level function `_run_chained_ops(atp_file_path, ops_for_file, mp_logger, pin_map) -> str` that applies a sequence of `edit_pattern` calls to a single file sequentially (handling the `_1stpostprcs.atp` handoff currently in `process_atp_simple`). This is the unit submitted to the pool.

### Phase 4 — Rewire the UI
7. In [`PAE.py`](PAE.py), rewrite `run_classical_multiprocess` to:
   - Build `config_list` via `build_config_from_classical(CSVFile[0], Mode, PinName, TimeMode, IndexMode)`.
   - Call the new unified `dispatch_config_parallel(...)`.
8. Rewrite `run_simple_multiprocess` similarly: build `config_list` via `analyse_merge_config`, call `dispatch_config_parallel`. Bind it to the Simplified tab's Generate button (replacing `run_simple` so the Simplified tab also benefits from parallelism).
9. Delete the dead methods: `run_classical` (single-process) and `single_item_post_process_simple` (unpicklable bound method).
10. Keep `run_simple` only if the user wants a single-process fallback; otherwise drop it.

### Phase 5 — Verification
11. **Classical regression test**: Run `Sample/Sample_ATP.csv` + `Sample_ATP.atp`, `Sample_ATP - 1.atp`, `DDR.atp` through the Classical tab in DSSC Capture mode. Confirm `Output/` contains the same files as before refactor, byte-identical (diff against a pre-refactor run).
12. **Simple regression test**: Run `Sample/Sample_ATP - simple.csv` through the Simplified tab. Confirm the dual-op chain on `Sample_ATP.atp` (DSSC Capture TDO then DSSC Capture PORN) still produces the same output as before.
13. **Parallelism smoke test**: Run on a ≥4-file config and verify worker pool actually runs in parallel (log timestamps) and `my_callback` fires `total_tasks` times.
14. **Pinmap test**: Use `workDir/PinMap_FT.txt` with a pin group name in the CSV; confirm classical and simple both expand it correctly.

### Relevant files
- [src/atp_handler.py](src/atp_handler.py) — `read_csv` bug fix, keep `build_config_from_classical` (fix docstring/usage), no change to `analyse_merge_config`.
- [src/main.py](src/main.py) — refactor `process_atp_simple` to accept config list; simplify `process_atp_classical`; add `dispatch_config_parallel` + `_run_chained_ops`.
- [PAE.py](PAE.py) — rewrite `run_classical_multiprocess` and `run_simple_multiprocess`; delete dead methods; rebind Simplified button.
- [PAE_webapp.py](PAE_webapp.py) — confirm it still works against the new `process_atp_simple` signature (should be backward compatible via default `merge_config_file` arg).

### Decisions / Scope
- **Kept**: Two UI tabs (Classical for quick jobs, Simplified for batch). Only the *backend* is unified.
- **Excluded** from this plan: the other refactor items in [analysis_results.md](doc/refactor_2026_April/analysis_results.md) (breaking up `edit_pattern`, full rename pass, unit tests). Those can follow independently.
- Pin-group expansion stays per-item (as in `process_atp_simple`) because after unification Classical's config items will all carry the same pin — the semantics remain correct.

### Further Considerations
1. **Should Simplified tab lose its single-process path entirely?** Option A: replace `run_simple` with multi-process (recommended — simpler, matches Classical). Option B: keep both as "Generate" + "Generate (Parallel)" buttons. Recommend A.
2. **How to handle `process_atp_simple` signature change** for `PAE_webapp.py` callers? Option A: keyword-only `config_list=None` added, `merge_config_file` stays positional (fully backward compatible). Option B: split into two separate functions. Recommend A.
3. **Chained-op safety in parallel mode**: grouping by `ATPFile` is necessary; worth noting that the existing `process_atp_simple` only safely chains ops when the CSV lists them **consecutively**. The parallel version should preserve that ordering within each group, not reorder.
