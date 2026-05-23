'''
ATP file handling module
'''
import csv
import os
import re
from typing import Dict, List
from src.file_ops import openfile
from src.utils import process_input_cycles
from src.logger import Logger
csv.field_size_limit(100000000)

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
                                 time_mode: str, index_mode: str) -> List[Dict]:
    """Convert classical 2-column CSV + GUI settings into standard config list.
    
    This adapter function allows the classical interface to use the same 
    processing code path as the simplified interface (process_atp_simple).
    
    Args:
        csv_file: Path to the 2-column CSV (filename, cycle_range)
        mode: Processing mode from GUI (e.g., 'DSSC Capture')
        pin_name: Pin name from GUI
        time_mode: 'Single' or 'Dual' from GUI
        index_mode: 'Cycle' or 'Vector' from GUI
    
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
    """Analyze merge configuration file"""
    config_list = []
    with openfile(merge_config_file) as f:
        f_csv = csv.reader(f)
        for index, row in enumerate(f_csv):
            if index == 0:
                head_list = row
            elif len(row) > 0:
                if "".join(row) == "":
                    break
                cur_config_dict = {
                    "ATPFile": "", 
                    "CycleRange": None,
                    "Mode": "",
                    "PinName": "",
                    "TimeMode": "Single",
                    "IndexMode": "Cycle"
                }
                for i, item in enumerate(row):
                    item = item.strip()
                    if item != "" and item is not None:
                        if i == 1 and item.lower().endswith(".atp"):
                            cur_config_dict["ATPFile"] = item
                        elif i == 3 or i == 6:
                            cur_config_dict["Mode"] = item
                            if "Pattern" in item:
                                tmp_dict = cur_config_dict.copy()
                                config_list.append(tmp_dict)
                                # reset possible conflict info
                                cur_config_dict["CycleRange"] = None
                                cur_config_dict["Mode"] = ""
                                cur_config_dict["PinName"] = ""
                        elif i == 4 or i == 7:
                            cur_config_dict["PinName"] = item
                        elif i == 5 or i == 8:
                            try:
                                cur_config_dict["CycleRange"] = process_input_cycles(item)
                            except Exception as e:
                                content = ",".join(row)
                                logger.error(f"Cannot parse the cycle list, content: {content}")
                                cur_config_dict["CycleRange"] = []
                            if "Pattern" not in item:
                                tmp_dict = cur_config_dict.copy()
                                config_list.append(tmp_dict)
                                # reset possible conflict info
                                cur_config_dict["CycleRange"] = None
                                cur_config_dict["Mode"] = ""
                                cur_config_dict["PinName"] = ""
            else:
                logger.warning("NO CONFIG FOUND!!!")
                break
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
