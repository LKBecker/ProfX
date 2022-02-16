#GPL-3.0-or-later

#import logging
import datetime
import math

"""Extracts the column widths from a variable-whitespace separated table, from a line of headers.
Headers are assumed *not* to have single spaces in their column names!"""
def extract_column_widths(headerStr:str, mustStartWithCapital:bool=True) -> list: 
    if not mustStartWithCapital:
        return [x+1 for x in range(0, len(headerStr)) if headerStr[x] == ' ' and headerStr[x+1] != ' ']
    return [x+1 for x in range(0, len(headerStr)) if headerStr[x] == ' ' and headerStr[x+1] != ' ' and (ord(headerStr[x+1]) > 64 and ord(headerStr[x+1]) < 91) ]

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

def calc_grid(nItems) -> tuple:
    quadNum = round(math.sqrt(nItems))
    nRows = quadNum
    nCols = max(1, math.ceil(nItems/nRows) )
    return (nRows, nCols)

def timestamp(fileFormat=False) -> str:
    if fileFormat:
        return datetime.datetime.now().strftime("%y%m%d_%H%M")
    return datetime.datetime.now().strftime("%y-%m-%d %H:%M")

""" Utility function, testing for truth, otherwise returning None"""
def value_or_none(item):
    if item:
        return item
    return None

def generatePrettyTable(Body, Separator=" | ", Headers=None, printTable=False) -> list:
    prettyTable = []
    #Ensure each line is the same length as all others (table is not ragged)
    maxItemsPerLine = max(len(line) for line in Body)
    for line in Body:
        while len(line) < maxItemsPerLine:
            line.append("")

    #Ensure there are headers
    if not Headers:
        Headers = Body[0]
        Body = Body[1:]

    #...and they too must have the right number of items
    while len(Headers) < maxItemsPerLine:
        Headers.append(f"Column_{len(Headers)+1}")

    #Determine cell size based on longest string per column, body OR header
    cellLengths = [[len(str(y)) for y in x] for x in Body]
    cellLengths = list(map(list, zip(*cellLengths))) #transpose to per-column data
    maxCellLengths = [max(*x) for x in cellLengths]
    maxCellLengths = [max(*x) for x in list(zip(maxCellLengths, [len(x) for x in Headers]))]
   
    #Build separator string and header string
    separatorStr = "-" * (sum(maxCellLengths) + ( len(Separator) * (len(maxCellLengths)-1) ))
    prettyTable.append(separatorStr)

    headerStr = Separator.join([Headers[i].ljust(maxCellLengths[i]) for i in range(0, maxItemsPerLine)])
    prettyTable.append(headerStr)
    prettyTable.append(separatorStr)

    for line in Body:
        prettyTable.append(Separator.join([str(line[i]).ljust(maxCellLengths[i]) for i in range(0, maxItemsPerLine)]))
    
    prettyTable.append(separatorStr)
    
    if printTable:
        for tableLine in prettyTable:
            print(tableLine)

    return prettyTable
