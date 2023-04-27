import os
import re

def read_fs_entry(filename):
    with open(filename, 'r') as fd:
        try:
            value = fd.readline().strip()
            value = re.findall(r'\d+\.\d+', value)[0]
        except:
            return 
    return float(value)

def get_branch1_pf():
    filename = "/home/petalinux/.temp/fps_branch1"
    return read_fs_entry(filename)

def get_branch2_pf():
    filename = "/home/petalinux/.temp/fps_branch2"
    return read_fs_entry(filename)