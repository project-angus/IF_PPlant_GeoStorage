#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""

__author__ = "wtp, witte"

"""

import os
import sys
import csv
import datetime

def clean_control_file_list(a_list):
    '''
    Function to delete empty rows and whitespaces from an xml-style list
    :param a_list: the input list
    :param type: list of strings
    :returns: a list of strings
    '''

    for i in range(len(a_list)):
        a_list[i] = a_list[i].strip()
    another_list = list(filter(None, a_list))

    return another_list

def get_idxfrom_control_file_list(a_list, keyword):
    '''
    Function to obtain index of the beginning of a specific keyword in an xml type list
    :param a_list: the input list, following an xml format style
    :param type: list of strings
    :param keyword: the keyword which will be searched for in the input list
    :param type: str
    :returns: int
    '''
    key_string_start = '<' + keyword + '>'
    key_string_end = '<\'' + keyword + '>'

    pos_ident = search_section(a_list, key_string_start)
    end_pos_ident = search_section(a_list, key_string_end)

    if pos_ident >= 0 and pos_ident < end_pos_ident:
        return a_list[pos_ident + 1]
    else:
        return -1

def get_valuefrom_control_file_list(a_list, keyword):
    '''
    Function to obtain values for a specific keyword from an xml type list
    :param a_list: the input list, following an xml format style
    :param type: list of strings
    :param keyword: the keyword which will be searched for in the input list
    :param type: string
    :returns: a string
    '''
    key_string_start = '<' + keyword + '>'
    key_string_end = '<\'' + keyword + '>'

    pos_ident = search_section(a_list, key_string_start)
    end_pos_ident = search_section(a_list, key_string_end)

    if pos_ident >= 0 and pos_ident < end_pos_ident:
        return a_list[pos_ident + 1]
    else:
        return 'KEY_NOT_FOUND'

def write_file(path, a_list):
    '''
    Short function to write a file based on a list of strings

    :param a_list: the input list
    :param type: string
    :returns: no return value
    '''
    with open (path, 'w') as f:
        for entry in a_list:
            f.write("%s" % entry)

def get_file(path):
    '''
    Short function to read a file and save as a list fo strings

    :param path: the path to the file 
    :param type: string
    :returns: a list of strings
    '''
    a_list = []
    with open(path) as f:
        a_list = list(f)
    f.closed
    
    return a_list

def contract_data_array(input):
    '''
    Short function to clean and contract a data array

    :param input: the input list to be cleaned
    :param type: string
    :returns: a list of strings
    '''
    output = []
    rows = len(input)
    
    for i in range(rows):
        # for each row do remove the stuff and save as clean list
        a_row = input[i]
        a_row = a_row.replace('\t', ';')
        a_row = a_row.split(';')
       # if not a_row[0]: 
        del a_row[0]  #first entry is always blank in ecl rsm output
        a_new_row = []
        for j in a_row:
            temp_str = j.strip()
            if not str(temp_str):
                temp_str = 'n.a.'
            a_new_row.append(temp_str)
        # if itis the last row delete last entry of that row
        #print('i: ', i , ' total rows: ', rows)
        if (i + 1) == rows:
            del a_new_row[-1]
            
        output.append(a_new_row)
    
    #go through whole list and delete double date entries
    date_positions = [i for i, s in enumerate(output[0]) if 'DATE' in s]
    #print('Positions of \'DATE\' in array: ', date_positions)
    max_count = len(date_positions)
    for e in reversed(date_positions):
        if max_count > 1:
            for i in range(len(output)):
                del output[i][e]
        max_count = max_count - 1
    
    return output

def delete_file(path_to_file):
    if os.path.exists(path_to_file):
        os.remove(path_to_file)

def search_section(data_list, section):
    '''
    function to search for a given string in a list of strings

    :param data_list: the input list to be searched
    :param type: list of strings
    :param section: the string which is searched for
    :param type: string
    :returns: int
    '''
    #what if there is a whitespace behind keyword?
    pos = -1
    if section in data_list:
        pos = data_list.index(section)
    else:
        section += "\n"
        if section in data_list:
            pos = data_list.index(section)
    return pos

def get_string_positions(input, keyword):
    '''
    function to get all positions of a string in a list

    :param input: the input list to be searched in
    :param type: list of strings
    :param keyword: the string to be searched for
    :param type: string
    :returns: list of int
    '''
    return [i for i, s in enumerate(input) if keyword in s]

def get_string_count(input, keyword):
    '''
    function to count the occurence of a string in a list

    :param input: the input list to be searched in
    :param type: list of strings
    :param keyword: the string to be searched for
    :param type: string
    :returns: int
    '''
    return sum ( 1 for s in input if keyword in s)


def read_series(path):
    '''
    reads now the input time series file using csv package.

    :param path: path to input time series
    :type path: str
    :returns: ts_dict (*dict*) - dictionary mapping datetime to power
    '''
    ts_dict = {}
    with open(path, mode='r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')

        for row in reader:
            time_str = row['timeindex']
            # Fast, standard parsing. Assuming format is always standard after first check.
            t_idx = datetime.datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')

            # Net power [MW or kW]
            power = float(row['input']) - float(row['output'])
            ts_dict[t_idx] = power

    return ts_dict

class Logger(object):
    """
    Redirects stdout to a file and the terminal.
    If debug=False, it safely ignores flush() to prevent
    massive performance bottlenecks during simulation loops.
    """
    def __init__(self, filepath):
        self.terminal = sys.stdout
        self.log = open(filepath, "a")
        self.debug = False # toggle this from coupling.py

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        # this flush method is needed for python 3 compatibility.
        # this handles the flush command by doing nothing.
        if self.debug:
            self.terminal.flush()
            self.log.flush()