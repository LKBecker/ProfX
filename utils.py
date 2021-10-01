#GPL-3.0-or-later

#import logging
import datetime
import math

"""Extracts the column widths from a variable-whitespace separated table, from a line of headers.
Headers are assumed *not* to have single spaces in their column names!"""
def extract_column_widths(headerStr:str) -> list: return [x+1 for x in range(0, len(headerStr)) if headerStr[x] == ' ' and headerStr[x+1] != ' ']

""" Uses headerWidths derived from extract_column_widths() to parse a list of strings into a list of lists of strings (a table)"""
def process_whitespaced_table(tableLines: list, headerWidths: list) -> list:
    if len(headerWidths) < 2: 
        raise Exception("headerWidths should contain at least two numbers.")
    parsedStrings = []
    for line in tableLines:
        if not line: continue
        parsedString = []
        if headerWidths[0] != 1:
            parsedString.append( line[0:headerWidths[0]].strip() )
        for counter in range(0, len(headerWidths)-1):
            parsedString.append( line[headerWidths[counter]:headerWidths[counter+1]].strip() )
        _tmpStr = line[headerWidths[-1]:].strip()
        if _tmpStr:
            parsedString.append( _tmpStr )
        parsedStrings.append(parsedString)
    return parsedStrings

def calc_grid(nItems):
    quadNum = round(math.sqrt(nItems))
    nRows = quadNum
    nCols = max(1, math.ceil(nItems/nRows) )
    return (nRows, nCols)

def timestamp(fileFormat=False):
    if fileFormat:
        return datetime.datetime.now().strftime("%y%m%d_%H%M")
    return datetime.datetime.now().strftime("%y-%m-%d %H:%M")

""" Utility function, testing for truth, otherwise returning None"""
def value_or_none(item):
    if item:
        return item
    return None