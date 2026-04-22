'''
Main module for ATP file processing
Created on Dec 8, 2015
@author: zhouchao
'''
import os
from typing import List, Any
from src.utils import in_list
from src.atp_handler import read_csv, read_pinmap, analyse_merge_config, build_config_from_classical
from src.pattern_processor import edit_pattern
from src.file_ops import copy_and_rename
from src.logger import Logger

def process_atp_classical(atp_files: List[str], csv_files: List[str], pin_name: str, mode: str, 
          time_mode: str, user_string: str, index_mode: str, logger: Logger, pin_map: str) -> None:
    """Process ATP files using classical 2-column CSV + GUI settings.
    
    This is now a thin wrapper that converts classical inputs into the standard
    config list format and delegates to process_atp_simple().
    """
    if len(csv_files) > 1:
        logger.error("Only ONE CSV file supported !!!")
        return

    # Build standard config list from classical 2-column CSV + GUI settings
    config_list = build_config_from_classical(csv_files[0], mode, pin_name, time_mode, index_mode)
    
    # Write a temporary config file for process_atp_simple
    # (process_atp_simple expects a file path, so we create a temp CSV)
    import csv as csv_module
    import tempfile
    temp_config = csv_files[0] + '.tmp_config.csv'
    try:
        with open(temp_config, 'w', newline='') as f:
            writer = csv_module.writer(f)
            writer.writerow(['Instance(Optional)', 'Pattern', 'Status', 'Process Type', 'Pin or Method', 'Cycle'])
            for item in config_list:
                # Convert cycle range back to string format
                cycle_str = ';'.join([f'[{c}-{c}]' for c in item['CycleRange']])
                writer.writerow(['', item['ATPFile'], '', item['Mode'], item['PinName'], cycle_str])
        
        pin_map_value = pin_map[0] if len(pin_map) > 0 else ""
        process_atp_simple(atp_files, temp_config, logger, pin_map_value)
    finally:
        if os.path.exists(temp_config):
            os.remove(temp_config)

def process_atp_simple(atp_files: List[str], merge_config_file: str, logger: Logger, pin_map: str) -> List[str]:
    """Process ATP files according to merge configuration file (simple multi-column CSV)"""
    # check pin group
    if pin_map != "":
        pinrounp_dict = read_pinmap(pin_map)

    # use to process merge-setup format input
    config_list = analyse_merge_config(merge_config_file, logger)

    cmb_list = ['DSSC Capture', 'DSSC Source', 'CMEM/HRAM Capture', 'Expand Pattern', 
                'Compress Pattern', 'WFLAG', 'Add Opcode', 'Remove Opcode']

    pre_file_name = ""
    result = []
    for config_item in config_list:
        # initial parameters
        tmp_file_name = config_item["ATPFile"]
        mode = config_item["Mode"]
        pin_name = config_item["PinName"]
        cycle_range = config_item["CycleRange"]
        time_mode = config_item["TimeMode"]

        # check pin group
        pin_name_ori = pin_name
        if pin_map != "":
            if ("," not in pin_name) and (pin_name in pinrounp_dict.keys()):
                pin_name = ",".join(pinrounp_dict[pin_name])

        if time_mode == 'Single':
            time_mode = '1'
        elif time_mode == 'Dual':
            time_mode = '2'
        index_mode = config_item["IndexMode"]
        user_string = ""
        j = in_list(tmp_file_name, atp_files)

        prcs_file_name = atp_files[j]
        # if some  name as previous, then copy output of previous to src path
        if pre_file_name == tmp_file_name:
            OutputPath = os.path.join(os.getcwd(), 'Output')
            prev_output_path = os.path.join(OutputPath, os.path.basename(atp_files[j]))
            # shutil.copy(prev_output_path, ATPFiles[j])
            prcs_file_name = atp_files[j].replace(r'.atp', r'_1stpostprcs.atp')
            copy_and_rename(prev_output_path, prcs_file_name)

        # go~ and run process function
        if j >= 0:
            logger.info("Start convert file: " + prcs_file_name)
            if mode in cmb_list:
                result_file = edit_pattern(logger, pin_name, prcs_file_name, cycle_range,
                                        mode, time_mode, index_mode, user_string, pin_name_ori)

                # Check is it the temp file from dual post process
                if result_file.endswith(r"_1stpostprcs.atp"):
                    if os.path.exists(prcs_file_name):
                        os.remove(prcs_file_name)
                    dual_post_prcs_file = result_file.replace(r'_1stpostprcs.atp', r'.atp')
                    copy_and_rename(result_file, dual_post_prcs_file)
                    result_file = dual_post_prcs_file

                pre_file_name = tmp_file_name
                if result_file not in result:
                    result.append(result_file)
            else:
                logger.error("Wrong Choice !!!")
            logger.info("Done conversion")
        else:
            logger.warning("Cannot find atp file: " + tmp_file_name)
    return result

# Keep old names as aliases for backward compatibility
main4 = process_atp_classical
main11 = process_atp_simple

if __name__ == '__main__':
    process_atp_simple(r"C:\Users\zhouchao\PycharmProjects\EditPat\S5\Post_process_pattern_list_S5.csv")
