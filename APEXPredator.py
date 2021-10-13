#GPL-3.0-or-later

#TODO: APEX uses more short-lived information strings. they'll blink then be erased.
#Also, multiple patients to one specimen
#TODO: subclass Screen into APEX_Screen, and connection into APEX_Connection, I guess. Or attach a statusline=None
#Then, the line designated as statusline gets its chunk separated out, parsed ,but each time it's erased individually, its value is appended to list
#In fact - just make it a list of line(s)?


VERSION = "0.1.0"
LOGFORMAT = '%(asctime)s: %(name)-10s:%(levelname)-7s:%(message)s'

import argparse
import apex_config
from collections import Counter
import datetime
import getpass
import logging
from utils import process_whitespaced_table, timestamp, extract_column_widths
import re
import telnet_ANSI
import time

APEX = telnet_ANSI.Connection()
telnet_ANSI.recognise_type = apex_config.LOCALISATION.identify_screen

# Functions --------
""" """
def BasicInterface():
    def get_user_input(FilterFunction, FormatReminder, Prompt:str="Please make your selection: ", lowerBound=None, upperBound=None):
        while True:
            _input = input(Prompt)
            if FilterFunction(_input, lowerBound, upperBound):
                return _input
            print(f"Input '{_input}' was not recognised. {FormatReminder}")

    def is_numeric(UserInput:str, lowerBound:None, upperBound:None):
        try:
            a = int(UserInput)
            if lowerBound:
                if a >= lowerBound:
                    return True
                return False

            if upperBound:
                if a <= upperBound:
                    return True
                return False
            
            return True
        
        except:
            return False

    #def is_alphanumeric(UserInput:str, lowerBound:None, upperBound:None):
    #    if UserInput == re.sub('[\W0-9]+', '', UserInput):
    #        return True
    #    return False
    #
    #def is_sample(UserInput:str, lowerBound:None, upperBound:None):
    #    _sample = apex_structs.SampleID(UserInput)
    #    return _sample.validate()

    print("""
    
    Welcome to the APEXPredator custom APEX client.
    
    Please select from the following options:

        1   Exit
    """)
    choice = get_user_input(is_numeric, "Please select a number from 1 to 8:", "Please select from the above options: ", 1, 8)

    if choice=="1": # Sendaways
        return
        #choice2 = get_user_input(is_numeric, "Please select a number from 1 to 2.", "Please select from the above options: ", 1, 2)
    input("Press any key to exit...")

""" """
def return_to_main_menu(ForceReturn:bool=False, MaxTries:int=10):
    #APEX.send(b"\x1B\x5B\x31\x37\x7E") # CSI 17~ eq F6
    APEX.send(b"\x1B\x5B17~")
    APEX.send(b'Y')
    #TryCounter = 0
    #logging.debug("Returning to main menu...")
    #TargetScreen = "MainMenu"
    #while(APEX.ScreenType != TargetScreen and TryCounter <= MaxTries):
    #    APEX.send(apex_config.LOCALISATION.CANCEL_ACTION)
    #    APEX.read_data()
    #    TryCounter = TryCounter+1
    #if TryCounter > MaxTries:
    #    raise Exception(f"Could not reach main menu in {MaxTries} attempts.")

""" """
def retrieve_Specimen_data(Samples:list, retrieveBy:str="SpecimenID"):
    #assert retrieveBy is one of "SpecimenID", "NHSNumber" 
    return_to_main_menu()
    APEX.send(apex_config.LOCALISATION.ENQUIRIES)
    APEX.read_data()
    for Sample in Samples: 
        if (retrieveBy == "SpecimenID"):
            APEX.send_and_ignore(b'\x1B\x5B\x32\x42') #VT100 control sequence: ^[nB, or "arrow down n times"; undefined n means once
            APEX.send(Sample.ID)
        if (retrieveBy == "NHSNumber"):
            APEX.send_and_ignore(b'\x1B\x5B\x42') #Go down once
            APEX.send(Sample.NHSNumber)
        else:
            raise Exception("retrieve_Specimen_data(): retrieveBy must be either 'SpecimenID' (default) or 'NHSNumber'")
        APEX.read_data()

""" Connects to APEX and logs in user, querying for Username and Password. """
def connect(TrainingSystem=False):  
    if apex_config.LOCALISATION.LIMS_USER:
        if apex_config.LOCALISATION.LIMS_USER != "YOUR USERNAME HERE": 
            user = apex_config.LOCALISATION.LIMS_USER
        else: 
            user = input("Enter your APEX username: ")
    else:
        user = input("Enter your APEX username: ")
    user = user.upper()

    if apex_config.LOCALISATION.LIMS_PW:
        if apex_config.LOCALISATION.LIMS_PW == "YOUR PASSWORD HERE":
            pw = getpass.getpass()
        else:
            pw = apex_config.LOCALISATION.LIMS_PW     
    else:
        pw = getpass.getpass()

    APEX.connect(IP=apex_config.LOCALISATION.LIMS_IP, Port=apex_config.LOCALISATION.LIMS_PORT, IBMUser=apex_config.LOCALISATION.IBM_USER, 
    Userprompt=None, PWPrompt=b"Password :", User=user, PW=pw)      
    
    logging.info("Connected to APEX. Reading first screen...")
    while (APEX.ScreenType != "MainMenu"):
        APEX.read_data(wait=False)
        logging.debug(f"connect(): Screen type is {APEX.ScreenType}, first lines are {APEX.Screen.Lines[0:2]}")
        time.sleep(1) # Wait for ON-CALL? to go away
    logging.info("Connected to APEX Main Menu. Welcome.")

""" Disconnects as safely as possible."""
def disconnect():
    return_to_main_menu(ForceReturn=True)
    logging.info("disconnect(): Disconnecting.")
    APEX.send('X', readEcho=False)
    APEX.send('', readEcho=False)         

# Script --------
logging.basicConfig(filename='./apex_debug.log', filemode='w', level=logging.DEBUG, format=LOGFORMAT)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter(LOGFORMAT))
logging.getLogger().addHandler(console)

logging.info(f"APEXPredator client, version {VERSION}. (c) Lorenz K. Becker, under GNU General Public License")

try:
    connect()
    #BasicInterface()


except Exception as e: 
    logging.error(e)

finally:
    disconnect()
    logging.info("System is now shut down. Have a nice day!")