'''
Main module for ATP file processing
Created on Dec 8, 2015
@author: zhouchao
'''
import os
from typing import List, Dict, Any, Optional
from src.atp_handler import (read_pinmap, analyse_merge_config,
                             build_config_from_classical, missing_requirements, MODE_LIST,
                             COUNTER_MODES)
from src.counter_expand import parse_counter_values
from src.pattern_processor import edit_pattern
from src.logger import Logger


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_config_item(config_item: Dict, pingroup_dict: Optional[Dict]) -> Dict:
    """Return a copy of config_item with time_mode normalized and pin groups expanded.

    - Converts TimeMode string 'Single'/'Dual' to '1'/'2'.
    - Expands a pin-group name into comma-separated pin list when pingroup_dict is given.
    - Keeps the original pin name under key 'PinNameOri' for downstream use.
    """
    item = dict(config_item)
    pin_name = item.get("PinName", "")
    item["PinNameOri"] = pin_name
    if pingroup_dict and ("," not in pin_name) and (pin_name in pingroup_dict):
        item["PinName"] = ",".join(pingroup_dict[pin_name])

    time_mode = item.get("TimeMode", "Single")
    if time_mode == 'Single':
        item["TimeMode"] = '1'
    elif time_mode == 'Dual':
        item["TimeMode"] = '2'
    return item


def _resolve_atp_path(tmp_file_name: str, atp_files: List[str]) -> int:
    """Return the index of tmp_file_name in atp_files or -1.

    A config names the file as the user sees it, so match on basename, also
    accepting the name with '.gz' appended so a config written against
    `x.atp` still finds `x.atp.gz`. Substring matching is deliberately not
    used: it can silently attach a whole chain to the wrong file.
    """
    for i, path in enumerate(atp_files):
        name = os.path.basename(path)
        if name == tmp_file_name or name == tmp_file_name + '.gz':
            return i
    return -1


def _validate_config(config_list: List[Dict], atp_files: List[str], logger: Logger) -> bool:
    """Check a whole config list before any of it is dispatched.

    Reports every problem rather than stopping at the first, so one run tells
    the user everything that is wrong. A Pattern that is not in atp_files is a
    warning and a skip, not an error: a config legitimately covers more files
    than are selected for a given run.

    Returns True when the run may proceed.
    """
    problems = []
    for op in config_list:
        for field in missing_requirements(op):
            problems.append(f"{op.get('Mode', '')} on {op.get('ATPFile', '')}: {field} is required")
        if op.get("Mode") in COUNTER_MODES:
            try:
                parse_counter_values(op.get("UserString", ""))
            except ValueError as e:
                problems.append(f"{op.get('Mode', '')} on {op.get('ATPFile', '')}: User String: {e}")

    seen = set()
    for op in config_list:
        pattern = op.get("ATPFile", "")
        if pattern in seen:
            continue
        seen.add(pattern)
        if _resolve_atp_path(pattern, atp_files) < 0:
            logger.warning("Cannot find atp file: " + pattern)

    for message in problems:
        logger.error(message)
    if problems:
        logger.error(f"Configuration rejected, {len(problems)} problem(s) found. Nothing was processed.")
        return False
    return True


def _run_chained_ops(atp_file_path: str, ops: List[Dict], logger: Logger) -> Optional[str]:
    """Sequentially apply a list of ops to a single ATP file.

    ops is a list of normalized config dicts (TimeMode already '1'/'2', pin group
    expanded). Each op reads the previous op's output, which lives in Output/,
    so an intermediate is always inspectable and nothing is written next to the
    source ATP.

    Returns the final output file path in Output/, or None if any op failed.
    A failure stops the chain: later ops depend on the failed op's output, so
    continuing would produce a file that is neither the requested chain nor the
    original.

    This function is module-level (picklable) so it can be submitted to a
    multiprocessing.Pool as a unit-of-work for one ATP file.
    """
    prcs_file_name = atp_file_path
    result_file = None
    output_path = os.path.join(os.getcwd(), 'Output')
    prev_output_path = os.path.join(output_path, os.path.basename(atp_file_path))

    for idx, op in enumerate(ops):
        mode = op.get("Mode", "")
        if mode not in MODE_LIST:
            logger.error("Wrong Choice !!!")
            return None

        if idx > 0:
            if not os.path.exists(prev_output_path):
                logger.error("Cannot continue: the previous step produced no output for "
                             + os.path.basename(atp_file_path))
                return None
            prcs_file_name = prev_output_path

        logger.info("Start convert file: " + prcs_file_name)
        result_file = edit_pattern(
            logger,
            op.get("PinName", ""),
            prcs_file_name,
            op.get("CycleRange"),
            mode,
            op.get("TimeMode", '1'),
            op.get("IndexMode", 'Cycle'),
            op.get("UserString", ""),
            op.get("PinNameOri", ""),
        )

        if result_file is None:
            logger.error(f"Step {idx + 1} of {len(ops)} failed ({mode}); no output produced for "
                         + os.path.basename(atp_file_path))
            return None

        logger.info("Done conversion")

    return result_file


def _group_ops_by_atp(config_list: List[Dict], atp_files: List[str],
                      pingroup_dict: Optional[Dict]) -> List[tuple]:
    """Group a config list into (atp_file_path, [normalized_ops]) tuples.

    Ops for the same ATP are kept in their original order (required for the
    chained-op handoff: op N reads the output of op N-1).
    """
    groups: "dict[str, list]" = {}
    order: "list[str]" = []
    for config_item in config_list:
        tmp_file_name = config_item.get("ATPFile", "")
        if not tmp_file_name:
            continue
        j = _resolve_atp_path(tmp_file_name, atp_files)
        if j < 0:
            # Already reported by _validate_config, which runs first.
            continue
        atp_path = atp_files[j]
        norm = _normalize_config_item(config_item, pingroup_dict)
        if atp_path not in groups:
            groups[atp_path] = []
            order.append(atp_path)
        groups[atp_path].append(norm)
    return [(p, groups[p]) for p in order]


# ---------------------------------------------------------------------------
# Unified processing entry points
# ---------------------------------------------------------------------------

def process_atp_simple(atp_files: List[str],
                       merge_config_file: Optional[str] = None,
                       logger: Optional[Logger] = None,
                       pin_map: str = "",
                       *,
                       config_list: Optional[List[Dict]] = None) -> List[str]:
    """Process ATP files according to a merge configuration (single-process).

    Accepts either a merge_config_file path (legacy behavior) OR a pre-built
    config_list. Exactly one of the two must be provided.
    """
    if config_list is None and merge_config_file is None:
        raise ValueError("Must provide either merge_config_file or config_list")
    if config_list is not None and merge_config_file is not None:
        raise ValueError("Provide only one of merge_config_file / config_list, not both")

    if config_list is None:
        config_list = analyse_merge_config(merge_config_file, logger)

    if not _validate_config(config_list, atp_files, logger):
        return []

    pingroup_dict = read_pinmap(pin_map) if pin_map else None
    groups = _group_ops_by_atp(config_list, atp_files, pingroup_dict)

    result: List[str] = []
    for atp_path, ops in groups:
        final_file = _run_chained_ops(atp_path, ops, logger)
        if final_file and final_file not in result:
            result.append(final_file)
    return result


def process_atp_classical(atp_files: List[str], csv_files: List[str], pin_name: str, mode: str,
                          time_mode: str, user_string: str, index_mode: str,
                          logger: Logger, pin_map: Any) -> List[str]:
    """Process ATP files using classical 2-column CSV + GUI settings.

    Thin wrapper: converts classical inputs into a standard config list
    and delegates to process_atp_simple.
    """
    if len(csv_files) > 1:
        logger.error("Only ONE CSV file supported !!!")
        return []

    config_list = build_config_from_classical(csv_files[0], mode, pin_name, time_mode,
                                              index_mode, user_string)
    pin_map_value = pin_map[0] if (hasattr(pin_map, '__len__') and len(pin_map) > 0) else (pin_map or "")
    return process_atp_simple(atp_files, logger=logger, pin_map=pin_map_value, config_list=config_list)


# ---------------------------------------------------------------------------
# Multi-process dispatch (used by the Tk GUI)
# ---------------------------------------------------------------------------

def dispatch_config_parallel(pool, atp_files: List[str], config_list: List[Dict],
                             mp_logger: Logger, pin_map: str, callback) -> int:
    """Submit all work in config_list to `pool`, one task per ATP file.

    Returns the number of tasks submitted (== number of distinct ATP files with
    valid ops), or 0 if the config was rejected. Each task runs `_run_chained_ops`
    on one ATP file with its ordered sequence of ops.

    `callback` is invoked once per finished task, with the output path on success
    or None on failure. It is attached as the error callback as well, so an
    unexpected exception in a worker still counts as a finished task — otherwise
    the completion counter never reaches the total and the UI waits forever.
    """
    if not _validate_config(config_list, atp_files, mp_logger):
        return 0

    pingroup_dict = read_pinmap(pin_map) if pin_map else None
    groups = _group_ops_by_atp(config_list, atp_files, pingroup_dict)

    def task_raised(exc):
        mp_logger.error(f"Unexpected failure: {exc!r}")
        callback(None)

    total = 0
    for atp_path, ops in groups:
        pool.apply_async(_run_chained_ops, args=(atp_path, ops, mp_logger),
                         callback=callback, error_callback=task_raised)
        total += 1
    return total


# Keep old names as aliases for backward compatibility
main4 = process_atp_classical
main11 = process_atp_simple

if __name__ == '__main__':
    process_atp_simple([], r"C:\Users\zhouchao\PycharmProjects\EditPat\S5\Post_process_pattern_list_S5.csv")

