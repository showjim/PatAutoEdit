'''
Utility functions for pattern processing
'''
import re

def cmp(a, b):
    """Compare two lists, handling comments"""
    listlena = len(a)
    listlenb = len(b)
    result = -1
    if listlena == listlenb:
        for i in range(listlena):
            tempa = str(a[i])
            commtindexa = tempa.find('//')
            tempb = str(b[i])
            commtindexb = tempa.find('//')
            if commtindexa > 0:
                tempa = tempa[:commtindexa].strip()
            if commtindexb > 0:
                tempb = tempb[:commtindexb].strip()
            result = (tempa > tempb) - (tempa < tempb)
            if result != 0:
                break
    return result

def in_list(str_val, tmplist):
    """Check if string exists in list"""
    for i in range(len(tmplist)):
        if tmplist[i].find(str_val) > -1:
            return i
    return -1

def process_input_cycles(row: str):
    """Process input cycle ranges"""
    tmparray = row.replace('[', '').replace(']', '')
    if tmparray.endswith(";"):
        tmparray = tmparray[:-1]
    tmparray = tmparray.split(';')
    tmparray = [x.split('-') for x in tmparray]
    tmparray = [sorted([int(y) for y in x]) for x in tmparray]
    tmparray.sort(key=lambda x: x[0]) # sort list according to the first element of sub-list
    tmpSet = convert2oneDlist(tmparray)
    return tmpSet

def convert2oneDlist(source_array):
    """Convert 2D list to 1D"""
    target_lines = [] #set()
    for start, end in source_array:
        target_lines.extend(range(start, end + 1))  # 生成所有行号
    return target_lines

def check_in_range(cycle_num:int, cycle_range:set):
    """Check if cycle number is in range"""
    if cycle_num in cycle_range:
        return True
    return False

def check_in_same_range(cycle_num_list, cycle_range):
    """Check if cycle numbers are in same range"""
    for x in range(len(cycle_range)):
        if (cycle_num_list[0] in range(cycle_range[x][0], cycle_range[x][1] + 1)) and (
                cycle_num_list[1] in range(cycle_range[x][0], cycle_range[x][1] + 1)):
            return True
    return False

def get_repeat_cnt(line):
    """Get repeat count from line"""
    repeat_cnt = 0
    p = re.compile(r'(?<=repeat)\s+\d+')
    m = re.search(p, line)
    if m:
        repeat_cnt = int(m.group())

    if repeat_cnt > 1:
        return repeat_cnt
    else:
        return 1

def check_tset_line(tset_list, line):
    """Check tset line"""
    ii = -1
    for i, val in enumerate(tset_list):
        # last space need here to ensure the end
        val = r"> {0} ".format(val)
        if val in line:
            ii = i
            return ii
    return ii
