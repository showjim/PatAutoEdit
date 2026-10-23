'''
ATP file handling module
'''
import csv
import re
from typing import Dict, List
from src.file_ops import openfile
from src.utils import process_input_cycles
from src.logger import Logger
csv.field_size_limit(100000000)

#: Processing modes the tool understands. Single source of truth for the
#: configuration parser, the validators and every mode picker in the UIs.
MODE_LIST = ['DSSC Capture', 'DSSC Source', 'CMEM/HRAM Capture',
             'Expand Pattern', 'Expand Repeat', 'Expand Loop', 'Compress Pattern', 'WFLAG',
             'Add Opcode', 'Remove Opcode']

#: Modes that need a pin name, a cycle range, or an opcode string to do anything.
_PIN_MODES = ('DSSC Capture', 'DSSC Source', 'CMEM/HRAM Capture')
_CYCLE_MODES = _PIN_MODES + ('WFLAG', 'Add Opcode')
_USER_STRING_MODES = ('Add Opcode', 'Remove Opcode')

#: Columns a row-per-op config must carry, matched case-insensitively.
_REQUIRED_COLUMNS = ('pattern', 'process type', 'pin or method', 'cycle')
#: Columns that are read but optional (blank when absent).
_OPTIONAL_COLUMNS = ('user string',)
#: Columns that are accepted and ignored.
_IGNORED_COLUMNS = ('instance', 'status')


class ConfigError(Exception):
    """Raised when a configuration file cannot be used, with a user-facing message."""


def missing_requirements(op: Dict) -> List[str]:
    """Return the fields an operation is missing, given its mode.

    An empty list means the operation has everything its mode needs.
    """
    mode = op.get("Mode", "")
    if mode not in MODE_LIST:
        return ["Process Type " + repr(mode) + " is not a known mode (valid: " +
                ", ".join(MODE_LIST) + ")"]
    missing = []
    if mode in _PIN_MODES and not op.get("PinName"):
        missing.append("Pin or Method")
    if mode in _CYCLE_MODES and not op.get("CycleRange"):
        missing.append("Cycle")
    if mode in _USER_STRING_MODES and not op.get("UserString"):
        missing.append("User String")
    return missing

def read_csv(input_path: str) -> Dict:
    """Read CSV file containing cycle ranges"""
    cycle_range = {}
    with openfile(input_path) as f:
        f_csv = csv.reader(f)
        for row in f_csv:
            if len(row) > 0:
                if len(row[0]) > 0 or len(row[1]) > 0:
                    cycle_range[row[0]] = process_input_cycles(row[1])
                else:
                    break
            else:
                break
    return cycle_range

def build_config_from_classical(csv_file: str, mode: str, pin_name: str,
                                 time_mode: str, index_mode: str,
                                 user_string: str = "") -> List[Dict]:
    """Convert classical 2-column CSV + GUI settings into standard config list.

    This adapter function allows the classical interface to use the same
    processing code path as the simplified interface (process_atp_simple).

    Args:
        csv_file: Path to the 2-column CSV (filename, cycle_range)
        mode: Processing mode from GUI (e.g., 'DSSC Capture')
        pin_name: Pin name from GUI
        time_mode: 'Single' or 'Dual' from GUI
        index_mode: 'Cycle' or 'Vector' from GUI
        user_string: Opcode text for 'Add Opcode' / 'Remove Opcode'

    Returns:
        List of config dicts in the same format as analyse_merge_config output
    """
    cycle_ranges = read_csv(csv_file)
    config_list = []
    for filename, cycles in cycle_ranges.items():
        config_list.append({
            "ATPFile": filename,
            "CycleRange": cycles,
            "Mode": mode,
            "PinName": pin_name,
            "UserString": user_string,
            "TimeMode": time_mode,
            "IndexMode": index_mode
        })
    return config_list

def read_pinmap(pinmap_dir: str) -> Dict:
    """Read pin mapping file"""
    pin_dict = {}
    line_cnt = 0
    with open(pinmap_dir, mode='r') as f:
        f_csv = csv.reader(f, delimiter="\t")
        for row in f_csv:
            if len(row) >= 2 and line_cnt >= 3:
                if row[1] != "":
                    key = row[1]
                    if key in pin_dict.keys():
                        pin_dict[key].append(row[2])
                    else:
                        pin_dict[key] = [row[2]]
            line_cnt += 1
    return pin_dict

def analyse_merge_config(merge_config_file: str, logger: Logger) -> List[Dict]:
    """Read a row-per-op configuration file into a config list.

    One row is one operation. Rows sharing a `Pattern` form a single chain and
    are applied in row order, each operation consuming the previous one's
    output.

    Columns are matched by name, case-insensitively and ignoring surrounding
    whitespace, so column order does not matter. `_REQUIRED_COLUMNS` must all be
    present; `_IGNORED_COLUMNS` are accepted and not read; anything else is
    reported and ignored. Blank rows are skipped wherever they appear.

    Raises:
        ConfigError: if the file is not usable in this format.
    """
    def fail(message):
        raise ConfigError(f"{merge_config_file}: {message}")

    with openfile(merge_config_file) as f:
        rows = [row for row in csv.reader(f) if any(cell.strip() for cell in row)]

    if not rows:
        fail("the file is empty")

    header = [cell.strip().lower() for cell in rows[0]]

    if len(header) >= 9:
        sample = ','.join(rows[1] if len(rows) > 1 else rows[0])
        fail(
            "this looks like the old 9-column format, which is no longer supported. "
            "Each operation now gets its own row, so a row like\n"
            f"    {sample}\n"
            "becomes one row per operation:\n"
            "    Pattern,Process Type,Pin or Method,Cycle\n"
            "    sample.atp,DSSC Capture,TDO,[7-7];[12-12]\n"
            "    sample.atp,DSSC Capture,PORN,[13-14]"
        )

    missing = [c for c in _REQUIRED_COLUMNS if c not in header]
    if missing:
        fail("missing required column(s): " + ", ".join(missing) +
             ". Required: " + ", ".join(_REQUIRED_COLUMNS) + " (case-insensitive)")

    unknown = [c for c in header
               if c and c not in _REQUIRED_COLUMNS + _OPTIONAL_COLUMNS + _IGNORED_COLUMNS]
    if unknown:
        logger.warning("Ignoring unrecognised column(s): " + ", ".join(unknown))

    columns = {name: header.index(name) for name in header
               if name in _REQUIRED_COLUMNS + _OPTIONAL_COLUMNS}

    config_list = []
    for line_no, row in enumerate(rows[1:], start=2):
        def cell(name):
            i = columns.get(name)
            return row[i].strip() if i is not None and i < len(row) else ""

        pattern, mode = cell('pattern'), cell('process type')
        if not pattern or not mode:
            fail(f"line {line_no}: Pattern and Process Type are both required")

        cycle_text = cell('cycle')
        try:
            cycles = process_input_cycles(cycle_text) if cycle_text else []
        except Exception:
            fail(f"line {line_no}: cannot parse Cycle {cycle_text!r}; expected e.g. [7-7];[12-12]")

        config_list.append({
            "ATPFile": pattern,
            "CycleRange": cycles,
            "Mode": mode,
            "PinName": cell('pin or method'),
            "UserString": cell('user string'),
            "TimeMode": "Single",
            "IndexMode": "Cycle",
        })

    if not config_list:
        fail("no operations found (the file has a header but no data rows)")

    return config_list

def find_pin_index(mode:str, pin_names: str, str_line: str, logger: Logger) -> List[int]:
    """Find pin indices in line"""
    pin_name = pin_names.split(",")
    str_line = str_line.replace(' ', '')
    pattern = re.compile(r'(?<=\,)\s*([^\,^\s]+)(?=[\,\)])')
    tmparray = re.findall(pattern, str_line)
    index = []

    for i in range(len(pin_name)):
        for x in range(len(tmparray)):
            if tmparray[x] == pin_name[i]:
                index.append(x)
                
    if (len(index) != len(pin_name)) and (mode not in ['WFLAG', 'Add Opcode']):
        index = []
        logger.error("Cannot find all given pins")
    return index
