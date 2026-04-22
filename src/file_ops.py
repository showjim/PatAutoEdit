'''
File operations module for handling file read/write operations
'''
import os
import gzip
import shutil
import glob
from pathlib import Path
from typing import List
import zipfile

def openfile(filename, mode='r'):
    """Open a file, handling gzipped files automatically"""
    if filename.endswith('.gz'):
        return gzip.open(filename, mode + 't')  # "t" means open gz as string
    else:
        return open(filename, mode)

def copy_and_rename(src_path, dest_path):
    """Move/rename a file from src to dest (overwrites dest if exists)"""
    shutil.move(src_path, dest_path)

def get_all_files_list(source_dir, exts):
    """Get list of files with specified extensions"""
    all_files = []
    result = []
    for ext in exts:
        all_files.extend(
            glob.glob(os.path.join(source_dir, f"*.{ext}"), recursive=False)
        )
    for filepath in all_files:
        file_name = Path(filepath).name
        result.append(file_name)
    return result

def make_zip(filenames: List, output_filename):
    """Create a zip file from list of files"""
    with zipfile.ZipFile(output_filename, 'w') as zipf:
        for filename in filenames:
            print(filename)
            zipf.write(filename)
        print()

def get_files(files_array, dirname, extname):
    """Recursively get files with specified extension"""
    for path in os.listdir(dirname):
        absolutely_path = os.path.join(dirname, path)
        if os.path.isdir(absolutely_path):
            get_files(files_array, absolutely_path, extname)
        elif os.path.splitext(absolutely_path)[1] == extname:
            files_array.append(absolutely_path)
