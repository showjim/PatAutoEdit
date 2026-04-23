# PatAutoEdit Refactoring Task List

## Phase 1: Quick Wins (Bug Fixes)
- [x] Fix `cmp()` typo in `src/utils.py` (`tempa` → `tempb` on line 16)
- [x] Fix `read_csv()` operator precedence bug in `src/atp_handler.py` line 19
- [x] Fix `copy_and_rename()` in `src/file_ops.py` — removed redundant shutil.copy
- [x] Fix `self.ety2` double-assignment in `PAE.py` → renamed to `self.ety_user_string`
- [x] Add `src/__init__.py`

## Phase 2: Introduce Logging
- [x] Create a `Logger` class in `src/logger.py`
- [x] Replace all `textoutwin(...)` + `print(...)` pairs in `src/main.py`
- [x] Replace all `textoutwin(...)` + `print(...)` pairs in `src/pattern_processor.py`
- [x] Replace all `textoutwin(...)` + `print(...)` pairs in `src/atp_handler.py`
- [x] Wire the Logger to Tkinter's `put_data_log` in `PAE.py`
- [x] Wire the Logger to Streamlit's `send_log` in `PAE_webapp.py`

## Phase 3: Break up `edit_pattern()`
- [x] Extract shared `_validate_and_modify_pin_data()` helper
- [x] Extract `_apply_dssc_capture()` function
- [x] Extract `_apply_dssc_source()` function
- [x] Extract `_apply_cmem_capture()` function
- [x] Extract `_write_instrument_header()` for header logic
- [x] Use `_PatternEditError` exception for clean error flow

## Phase 4: Unify the Two Code Paths
- [x] Create `build_config_from_classical()` adapter in `src/atp_handler.py`
- [x] Rename `main11` → `process_atp_simple` (with backward compat alias)
- [x] Rename `main4` → `process_atp_classical` (with backward compat alias)
- [x] Refactor `process_atp_classical` to be thin wrapper → `build_config_from_classical()` → `process_atp_simple()`

## Phase 5: Naming Cleanup
- [x] Rename `DemoClass` → `PatAutoEditApp`
- [x] Rename `SayHello*` methods to descriptive names (`run_classical`, `run_simple`, etc.)
- [x] Rename `something`/`otherthing` → `input_path`/`output_path`/`prev_output_path`
- [x] Rename `textoutwin`/`textout` → `logger` across entire codebase
- [x] Rename `read_csv(something)` → `read_csv(input_path)`
