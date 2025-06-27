'''
Pattern processing module for ATP file modifications
'''
import os, csv
import re
from typing import List, Any, Tuple
from src.file_ops import openfile, copy_and_rename
from src.utils import get_repeat_cnt, cmp, check_in_range, check_in_same_range, get_all_files
from src.atp_handler import find_pin_index

def remove_opcode(something: str, user_string: str) -> str:
    """Remove specified opcode from ATP file"""
    otherthing = something.replace(r'.atp', r'_RemoveOpcode.atp')
    with openfile(otherthing, mode='w') as new_atp_file:
        with openfile(something) as atp_file:
            while True:
                tmp_line = atp_file.readline()
                if len(tmp_line) == 0:
                    break
                if tmp_line.strip().startswith(user_string):
                    tmp_line = tmp_line.replace(user_string, '')
                new_atp_file.write(tmp_line)
    return otherthing

def remove_repeat(something: str, timemode: str) -> str:
    """Remove repeat statements from ATP file"""
    otherthing = something.replace(r'.atp', r'_RemoveRepeat.atp')

    line_num = 1 if timemode == '1' else 2
    body_flag = False

    with openfile(otherthing, mode='w') as new_atp_file:
        with openfile(something) as atp_file:
            while True:
                line = []  # initial line for dual mode
                if not body_flag:
                    headerline = atp_file.readline()
                    if headerline.strip().startswith(r"{"):
                        body_flag = True

                    if len(headerline) == 0:
                        break

                    new_atp_file.write(headerline)
                else:
                    for i in range(line_num):
                        while True:
                            tmp_line = atp_file.readline()
                            if tmp_line.strip().startswith(r'//'):
                                continue
                            else:
                                break
                        line.append(tmp_line)
                    repeat_cnt = get_repeat_cnt(line[-1])

                    if repeat_cnt > 1:
                        line[-1] = line[-1].replace('repeat', ' ' * len('repeat'), 1)
                        line[-1] = line[-1].replace(str(repeat_cnt), ' ' * len(str(repeat_cnt)), 1)
                        for j in range(repeat_cnt):
                            for i in range(len(line)):
                                new_atp_file.write(line[i])
                    else:
                        for i in range(len(line)):
                            new_atp_file.write(line[i])

                        if (line[-1].find(r'}') != -1) or line[-1] == '':
                            body_flag = False
    return otherthing

def add_repeat(something: str, timemode: str) -> str:
    """Add repeat statements to ATP file"""
    otherthing = something.replace(r'.atp', r'_AddRepeat.atp')

    line_index = 0
    repeat_cnt = 1
    prev_line = []
    line_num = 1 if timemode == '1' else 2
    body_flag = False

    with openfile(otherthing, mode='w') as new_atp_file:
        with openfile(something) as atp_file:
            while True:
                line = []  # initial line for dual mode
                if not body_flag:
                    headerline = atp_file.readline()
                    if headerline.strip().startswith(r"{"):
                        body_flag = True

                    if len(headerline) == 0:
                        break

                    new_atp_file.write(headerline)
                else:
                    for i in range(line_num):
                        while True:
                            tmp_line = atp_file.readline()
                            if tmp_line.strip().startswith(r'//'):
                                continue
                            else:
                                line_index += 1
                                break
                        line.append(tmp_line)

                    if cmp(line, prev_line) == 0 and repeat_cnt < 65535:
                        repeat_cnt += 1
                    elif line_index != line_num:
                        for i in range(len(prev_line) - 1):
                            new_atp_file.write('{0}'.format(prev_line[i]))

                        if repeat_cnt != 1:
                            new_atp_file.write('repeat {0}    {1}'.format(repeat_cnt, prev_line[-1]))
                        else:
                            new_atp_file.write('{0}'.format(prev_line[-1]))
                        repeat_cnt = 1

                    if (line[-1].find(r'}') != -1) or line[-1] == '':
                        body_flag = False
                        for i in range(len(line)):
                            new_atp_file.write('{0}'.format(line[i]))

                    prev_line = line
    return otherthing

def merge_instrument_declare(temp_file: str) -> None:
    """Merge multiple instrument declarations in the file before '>' line into a single declaration"""
    instrument_content = []
    header_lines = []
    body_lines = []
    found_instruments = False
    in_instruments_block = False
    
    # Read the file and process lines
    with openfile(temp_file) as f:
        for line in f:
            if line.find(r"$") != -1:
                body_lines.append(line)
                # Add all remaining lines to body
                body_lines.extend(f.readlines())
                break
                
            if line.strip() == "instruments = {":
                found_instruments = True
                in_instruments_block = True
                continue
            
            if in_instruments_block:
                if line.strip() == "}":
                    in_instruments_block = False
                else:
                    # Add instrument declaration line
                    instrument_content.append(line.strip())
                continue
                
            header_lines.append(line)
    
    # Only proceed if we found multiple instrument declarations
    if found_instruments:
        # Write back the merged content
        with openfile(temp_file, 'w') as f:
            # Write header lines
            for line in header_lines:
                f.write(line)
            
            # Write merged instruments block if we have instrument content
            if instrument_content:
                f.write("instruments = {\n")
                for line in instrument_content:
                    if line:  # Skip empty lines
                        f.write(f"{line}\n")
                f.write("}\n\n")
            
            # Write the rest of the file
            for line in body_lines:
                f.write(line)

def edit_pattern(textoutwin: Any, pin_name: str, something: str, cycle_range: List,
                mode: str, timemode: str, index_mode: str, user_string: str = '', 
                pin_name_ori: str = "") -> str:
    """Edit ATP pattern file according to specified mode and parameters"""
    # Track if any errors occurred during processing
    has_errors = False

    output_path = os.path.join(os.getcwd(), 'Output')
    if not os.path.exists(output_path):
        os.mkdir(output_path)

    otherthing = os.path.join(output_path, os.path.basename(something))

    if mode == 'Expand Pattern':
        remove_repeat_file = remove_repeat(something, timemode)
        copy_and_rename(remove_repeat_file, otherthing)
        if os.path.exists(remove_repeat_file):
            os.remove(remove_repeat_file)
        return otherthing

    if mode == 'Compress Pattern':
        add_repeat_file = add_repeat(something, timemode)
        copy_and_rename(add_repeat_file, otherthing)
        if os.path.exists(add_repeat_file):
            os.remove(add_repeat_file)
        return otherthing

    if mode == 'Remove Opcode':
        remove_opcode_file = remove_opcode(something, user_string)
        copy_and_rename(remove_opcode_file, otherthing)
        if os.path.exists(remove_opcode_file):
            os.remove(remove_opcode_file)
        return otherthing

    line_index = 0
    cycle_num = 0
    repeat_cnt = 0
    temp_file = None

    last_cycle_num = cycle_range[-1]
    cycle_range = set(cycle_range)

    # Remove all "repeat" opcode first
    if index_mode == 'Cycle':
        remove_repeat_file = remove_repeat(something, timemode)
    else:
        remove_repeat_file = something

    try:
        temp_file = otherthing + '.tmp'
        with openfile(temp_file, mode='w') as new_atp_file:
            with openfile(remove_repeat_file) as atp_file:
                while True:
                    line = atp_file.readline()
                    line_index += 1

                    # Modify the head part of atp file
                    if line.find(r">") == -1:
                        if line[0:12] == "import tset " or line[0:22] == 'import_all_undefineds ':
                            new_atp_file.write(line)

                            if mode == 'DSSC Capture':
                                pin_name_list = pin_name.split(',')
                                new_atp_file.write("\n")
                                new_atp_file.write("instruments = {\n")
                                new_atp_file.write(
                                    "({0}):DigCap {1}:auto_trig_enable;\n".format(pin_name_ori, len(pin_name_list)))
                                new_atp_file.write("}\n")
                            elif mode == 'DSSC Source':
                                pin_name_list = pin_name.split(',')
                                new_atp_file.write("\n")
                                new_atp_file.write("instruments = {\n")
                                new_atp_file.write(
                                    "({0}):DigSrc {1};\n".format(pin_name_ori, len(pin_name_list)))
                                new_atp_file.write("}\n")
                            elif mode == 'Add Opcode':
                                new_atp_file.write("\n")
                                if pin_name != '':
                                    pin_name_list = pin_name.split(',')
                                    new_atp_file.write("instruments = {\n")
                                    for pin in pin_name_list:
                                        new_atp_file.write(
                                            "{0}:DCVS 1;\n".format(pin))
                                    new_atp_file.write("}\n")

                        elif line.find("$tset") != -1:
                            index = find_pin_index(mode, pin_name, line, textoutwin)
                            if 0 in index:
                                textoutwin('Error: Cannot find pinname')
                                print('Error: Cannot find pinname')
                                has_errors = True
                                return something  # Return original file path to indicate error
                            new_atp_file.write(line)

                        else:
                            new_atp_file.write(line)
                    else:
                        repeat_cnt = get_repeat_cnt(line)
                        if cycle_num == 0:
                            # Find the modify pin position
                            modify_index = 0
                            pattern = re.compile(r"> *\S+")
                            start_search_pos = re.search(pattern, line).end()

                            modify_index_list = []
                            for i in range(len(index)):
                                modify_index = start_search_pos
                                count_num = 0
                                for x in line[start_search_pos:]:
                                    if not x.isspace():
                                        count_num += 1
                                    if index[i] + 1 == count_num:
                                        modify_index_list.append(modify_index)
                                        break
                                    modify_index += 1

                        # Add DigSrc Signal
                        if (cycle_num == 1) and (mode == 'DSSC Source'):
                            line = "(({0}):DigSrc = Start DSSCSrcSig)".format(pin_name_ori) + line

                        # Add wflag setup
                        if mode == 'WFLAG':
                            if cycle_num == 0:
                                line = 'branch_expr = (!cpuA_cond)\t' + line
                            if cycle_num == 1:
                                line = 'set_msb_infinite\t' + line
                            if cycle_num == 2:
                                line = 'set_infinite c0\t' + line
                            if cycle_num == 3:
                                line = 'push_loop c0\t' + line
                            if check_in_range(cycle_num + 1, cycle_range):
                                line = 'set_cpu_cond (cpuA_cond)\t' + line

                        if cycle_num in cycle_range:
                            if mode == 'DSSC Capture':
                                if repeat_cnt == 1:
                                    line_list = line.split()
                                    for k in index:
                                        try:
                                            start_index = line_list.index(">")
                                        except Exception as e:
                                            textoutwin(f"Error: '>' is not in list, {e} ")
                                            print(f"Error: '>' is not in list, {e} ")
                                            has_errors = True
                                            return something  # Return original file path to indicate error
                                        if line_list[start_index + 1 + k + 1] == '0' or line_list[start_index + 1 + k + 1] == '1':
                                            textoutwin("Error: Drive data found in DigCap, line " + str(line_index) + ", and pin data index " + str(k))
                                            print("Error: Drive data found in DigCap, line " + str(line_index) + ", and pin data index " + str(k))
                                            has_errors = True
                                            return something  # Return original file path to indicate error
                                        elif line_list[start_index + 1 + k + 1] == 'X':
                                            textoutwin("Error: ""X"" data found in DigCap, line " + str(
                                                line_index) + ", and pin data index " + str(k))
                                            print("Error: ""X"" data found in DigCap, line " + str(
                                                line_index) + ", and pin data index " + str(k))
                                            has_errors = True
                                            return something  # Return original file path to indicate error
                                        else:
                                            line_list[start_index + 1 + k + 1] = "V"
                                    line = "(({0}):DigCap = Store) ".format(pin_name_ori) + " ".join(line_list) + "\n"
                                else:
                                    cycle_num_list = [cycle_num, cycle_num + repeat_cnt - 1]
                                    if check_in_same_range(cycle_num_list, cycle_range):
                                        line_list = line.split()
                                        for k in index:
                                            start_index = line_list.index(">")
                                            if line_list[start_index + 1 + k + 1] == '0' or line_list[start_index + 1 + k + 1] == '1':
                                                textoutwin("Error: Drive data found in DigCap, line " + str(line_index) + ", and pin data index " + str(k))
                                                print("Error: Drive data found in DigCap, line " + str(line_index) + ", and pin data index " + str(k))
                                                has_errors = True
                                                return something  # Return original file path to indicate error
                                            elif line_list[start_index + 1 + k + 1] == 'X':
                                                textoutwin("Error: ""X"" data found in DigCap, line " + str(
                                                    line_index) + ", and pin data index " + str(k))
                                                print("Error: ""X"" data found in DigCap, line " + str(
                                                    line_index) + ", and pin data index " + str(k))
                                                has_errors = True
                                                return something  # Return original file path to indicate error
                                            else:
                                                line_list[start_index + 1 + k + 1] = "V"
                                        line = "(({0}):DigCap = Store) ".format(pin_name_ori) + " ".join(line_list) + "\n"

                            elif mode == 'DSSC Source':
                                if repeat_cnt == 1:
                                    line_list = line.split()
                                    for k in index:
                                        start_index = line_list.index(">")
                                        if line_list[start_index + 1 + k + 1] == 'H' or line_list[start_index + 1 + k + 1] == 'L':
                                            textoutwin("Error: Compare data found in DigSrc, line " + str(line_index) + ", and pin data index " + str(k))
                                            print("Error: Compare data found in DigSrc, line " + str(line_index) + ", and pin data index " + str(k))
                                            has_errors = True
                                            return something  # Return original file path to indicate error
                                        else:
                                            line_list[start_index + 1 + k + 1] = "D"
                                    line = "(({0}):DigSrc = Send) ".format(pin_name_ori) + " ".join(line_list) + "\n"
                                else:
                                    cycle_num_list = [cycle_num, cycle_num + repeat_cnt - 1]
                                    if check_in_same_range(cycle_num_list, cycle_range):
                                        line_list = line.split()
                                        for k in index:
                                            start_index = line_list.index(">")
                                            if line_list[start_index + 1 + k + 1] == 'H' or line_list[start_index + 1 + k + 1] == 'L':
                                                textoutwin("Error: Compare data found in DigSrc, line " + str(line_index) + ", and pin data index " + str(k))
                                                print("Error: Compare data found in DigSrc, line " + str(line_index) + ", and pin data index " + str(k))
                                                has_errors = True
                                                return something  # Return original file path to indicate error
                                            else:
                                                line_list[start_index + 1 + k + 1] = "D"
                                        line = "(({0}):DigSrc = Send) ".format(pin_name_ori) + " ".join(line_list) + "\n"

                            elif mode == 'CMEM/HRAM Capture':
                                if repeat_cnt == 1:
                                    line_list = line.split()
                                    for k in index:
                                        start_index = line_list.index(">")
                                        if line_list[start_index + 1 + k + 1] == '0' or line_list[start_index + 1 + k + 1] == '1':
                                            textoutwin("Error: Drive data found in Cap, line " + str(line_index) + ", and pin data index " + str(k))
                                            print("Error: Drive data found in Cap, line " + str(line_index) + ", and pin data index " + str(k))
                                            has_errors = True
                                            return something  # Return original file path to indicate error
                                        elif line_list[start_index + 1 + k + 1] == 'X':
                                            textoutwin("Error: ""X"" data found in Cap, line " + str(line_index) + ", and pin data index " + str(k))
                                            print("Error: ""X"" data found in Cap, line " + str(line_index) + ", and pin data index " + str(k))
                                            has_errors = True
                                            return something  # Return original file path to indicate error
                                        else:
                                            line_list[start_index + 1 + k + 1] = "V"
                                    line = "stv\t" + " ".join(line_list) + "\n"
                                else:
                                    cycle_num_list = [cycle_num, cycle_num + repeat_cnt - 1]
                                    if check_in_same_range(cycle_num_list, cycle_range):
                                        line_list = line.split()
                                        for k in index:
                                            start_index = line_list.index(">")
                                            if line_list[start_index + 1 + k + 1] == '0' or line_list[start_index + 1 + k + 1] == '1':
                                                textoutwin("Error: Drive data found in Cap, line " + str(line_index) + ", and pin data index " + str(k))
                                                print("Error: Drive data found in Cap, line " + str(line_index) + ", and pin data index " + str(k))
                                                has_errors = True
                                                return something  # Return original file path to indicate error
                                            elif line_list[start_index + 1 + k + 1] == 'X':
                                                textoutwin("Error: ""X"" data found in Cap, line " + str(line_index) + ", and pin data index " + str(k))
                                                print("Error: ""X"" data found in Cap, line " + str(line_index) + ", and pin data index " + str(k))
                                                has_errors = True
                                                return something  # Return original file path to indicate error
                                            else:
                                                line_list[start_index + 1 + k + 1] = "V"
                                        line = " ".join(line_list).replace('repeat', 'stv,repeat') + "\n"

                            elif mode == 'WFLAG':
                                if repeat_cnt == 1:
                                    line = 'wflag\t' + line

                            elif mode == 'Add Opcode':
                                if repeat_cnt == 1:
                                    line = user_string + '\t' + line

                        new_atp_file.write(line)

                        if index_mode == 'Cycle':
                            cycle_num += repeat_cnt
                        else:
                            cycle_num += 1

                    if len(line) == 0:
                        if cycle_num < last_cycle_num:
                            textoutwin('Error: The cycle you specified exceeds the total number of cycles in the pattern: ' + something)
                            print('Error: The cycle you specified exceeds the total number of cycles in the pattern: ' + something)
                            has_errors = True
                            return something  # Return original file path to indicate error
                        break

            if os.path.exists(remove_repeat_file):
                if index_mode == 'Cycle':
                    os.remove(remove_repeat_file)
            else:
                textoutwin("Error: The file " + remove_repeat_file + " does not exist")
                print("Error: The file " + remove_repeat_file + " does not exist")
                has_errors = True
                return something  # Return original file path to indicate error

        # Only rename temp file to final output if no errors occurred
        if not has_errors:
            if os.path.exists(temp_file):
                # Merge instrument declarations if in DSSC modes
                if mode in ['DSSC Capture', 'DSSC Source']:
                    merge_instrument_declare(temp_file)
                
                if os.path.exists(otherthing):
                    os.remove(otherthing)
                os.rename(temp_file, otherthing)
                textoutwin("Info: Done conversion: " + something)
                print("Info: Done conversion: " + something)
                return otherthing
        else:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return something

    except Exception as e:
        textoutwin(f"Error: An unexpected error occurred: {str(e)}")
        print(f"Error: An unexpected error occurred: {str(e)}")
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)
        return something

    return something  # Return original file path if we somehow get here

def extract_cycle_on_keyword(fileFolder: str, keyword: str, textoutwin):
    """Extract cycle_on keyword from ATP files."""
    resultDict = {}
    resylt_list = get_all_files(fileFolder, ".atp")

    for singleFile in resylt_list:
        removeRepeatFile = remove_repeat(singleFile, '1')
        cycle_num = 0
        fileName = os.path.basename(singleFile)
        resultDict[fileName] = []
        try:
            with openfile(removeRepeatFile) as atp_file:
                while True:
                    line = atp_file.readline()
                    if line.find(r">") != -1:
                        line, sep, tail = line.partition(';')

                        if keyword in tail:
                            resultDict[fileName].append(cycle_num)

                        cycle_num += 1
                    if len(line) == 0:
                        break
        except Exception as e:
            textoutwin(f"Error: An unexpected error occurred: {str(e)}")
            print(f"Error: An unexpected error occurred: {str(e)}")
            if removeRepeatFile and os.path.exists(removeRepeatFile):
                os.remove(removeRepeatFile)

        # restore
        if os.path.exists(removeRepeatFile):
            os.remove(removeRepeatFile)

    # print to csv
    with open(fileFolder+ '/extract_result.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        for key, value in resultDict.items():
            cycleContent = ';'.join(['[' + str(x) + '-' + str(x) + ']' for x in value])
            writer.writerow([key, cycleContent])
    textoutwin(f"Info: Extraction done.")
    print(f"Info: Extraction done.")


if __name__ == '__main__':
    extract_cycle_on_keyword(r"C:\Users\zhouchao\PycharmProjects\EditPat\Sample", "Wait")