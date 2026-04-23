# PatAutoEdit Refactoring Walkthrough

**Branch:** `refactor/code-cleanup`  
**Commit:** `f168166`  
**Scope:** 9 files changed, +341 / -287 lines

---

## Phase 1: Bug Fixes

| Bug | File | Fix |
|-----|------|-----|
| `cmp()` searched `tempa` instead of `tempb` | [utils.py](file:///Users/jerry/PycharmProjects/PatAutoEdit/src/utils.py#L16) | `commtindexb = tempb.find('//')` |
| `read_csv()` precedence: `len(row[0]) or len(row[1]) > 0` | [atp_handler.py](file:///Users/jerry/PycharmProjects/PatAutoEdit/src/atp_handler.py#L20) | `len(row[0]) > 0 or len(row[1]) > 0` |
| `copy_and_rename()` did copy + move (redundant) | [file_ops.py](file:///Users/jerry/PycharmProjects/PatAutoEdit/src/file_ops.py#L19) | Removed `shutil.copy`, kept `shutil.move` |
| `self.ety2` assigned twice (ATP entry and User String) | [PAE.py](file:///Users/jerry/PycharmProjects/PatAutoEdit/PAE.py#L144) | Renamed to `self.ety_user_string` |
| Missing `__init__.py` | [__init__.py](file:///Users/jerry/PycharmProjects/PatAutoEdit/src/__init__.py) | Created |

---

## Phase 2: Unified Logging

Created [src/logger.py](file:///Users/jerry/PycharmProjects/PatAutoEdit/src/logger.py) — a `Logger` class that outputs to both console and GUI callback in a single call:

```python
logger = Logger(gui_callback=self.put_data_log)
logger.info("Processing file...")   # → prints AND sends to GUI
logger.error("Something broke")     # → prints AND sends to GUI
```

**Before (30+ sites like this):**
```python
textoutwin("Error: Cannot find all given pins")
print("Error: Cannot find all given pins")
```

**After:**
```python
logger.error("Cannot find all given pins")
```

Multiprocessing uses `Logger(gui_callback=self.queue.put)` so worker processes route messages through the Manager queue.

---

## Phase 3: `edit_pattern()` Decomposition

Extracted from the 300-line monolith in [pattern_processor.py](file:///Users/jerry/PycharmProjects/PatAutoEdit/src/pattern_processor.py):

| Extracted Function | Purpose |
|---|---|
| `_validate_and_modify_pin_data()` | Shared validation for DSSC Capture, DSSC Source, CMEM Capture |
| `_apply_dssc_capture()` | Replace pin data with `V`, add `DigCap = Store` prefix |
| `_apply_dssc_source()` | Replace pin data with `D`, add `DigSrc = Send` prefix |
| `_apply_cmem_capture()` | Replace pin data with `V`, add `stv` prefix |
| `_write_instrument_header()` | Write instrument declaration block in header |
| `_PatternEditError` | Custom exception for clean error abort flow |

The key insight: DSSC Capture, DSSC Source, and CMEM Capture shared ~80% identical logic (find pin → validate → replace). Now it's one parameterized function.

---

## Phase 4: Code Path Unification

**The Problem:** Two interfaces used different CSV formats and completely separate processing code.

**The Solution:** Added [build_config_from_classical()](file:///Users/jerry/PycharmProjects/PatAutoEdit/src/atp_handler.py#L28) adapter that converts the 2-column CSV + GUI settings into the same config dict format used by the simple path.

```
Classical GUI → build_config_from_classical() → process_atp_simple()
Simple GUI   → analyse_merge_config()         → process_atp_simple()
Web App      → analyse_merge_config()         → process_atp_simple()
```

All three interfaces now feed into **one** processing engine.

---

## Phase 5: Naming Cleanup

| Old Name | New Name | Location |
|----------|----------|----------|
| `DemoClass` | `PatAutoEditApp` | PAE.py |
| `SayHello()` | `run_classical()` | PAE.py |
| `SayHello_simple()` | `run_simple()` | PAE.py |
| `SayHello_MultProcess()` | `run_classical_multiprocess()` | PAE.py |
| `SayHello_simple_MultProcess()` | `run_simple_multiprocess()` | PAE.py |
| `SayHello_utils()` | `run_utils_extract()` | PAE.py |
| `main4()` | `process_atp_classical()` | src/main.py |
| `main11()` | `process_atp_simple()` | src/main.py |
| `something` | `input_path` | pattern_processor.py, atp_handler.py |
| `otherthing` | `output_path` / `prev_output_path` | pattern_processor.py, main.py, PAE.py |
| `textoutwin` / `textout` | `logger` | All files |

> [!NOTE]
> Backward-compatible aliases `main4 = process_atp_classical` and `main11 = process_atp_simple` are kept in `src/main.py` in case any external scripts reference the old names.

---

## Verification

All 9 modified/created files pass `py_compile`:
```
✓ src/__init__.py
✓ src/logger.py  
✓ src/utils.py
✓ src/file_ops.py
✓ src/atp_handler.py
✓ src/pattern_processor.py
✓ src/main.py
✓ PAE.py
✓ PAE_webapp.py
```

> [!IMPORTANT]
> **Recommended next step:** Run the tool with a real ATP file to smoke-test before merging to main. Both the Classical tab and Simple tab should be tested.
