#GPL-3.0-or-later

"""TODO:
    # TODO: APEX is a lively fella that will secrete multiple screens at once.
    # TODO: Supply Screen Recognition function? Input Screen lines[], get str ScreenID
"""

VERSION = "0.0.1"
LOGFORMAT = '%(asctime)s: %(name)-10s:%(levelname)-7s:%(message)s'

import argparse
import apex_config
#import apex_structs
from collections import Counter
import datetime
import getpass
import logging
from utils import process_whitespaced_table, timestamp, extract_column_widths
import re
from telnet_ANSI import Connection
import time

APEX = Connection(apex_config.LOCALISATION.ANSWERBACK)

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
    TryCounter = 0
    logging.debug("Returning to main menu...")
    TargetScreen = "MainMenu"
    while(APEX.Screen.Type != TargetScreen and TryCounter <= MaxTries):
        APEX.send(apex_config.LOCALISATION.CANCEL_ACTION)
        APEX.read_data()
        TryCounter = TryCounter+1
    if TryCounter > MaxTries:
        raise Exception(f"Could not reach main menu in {MaxTries} attempts. Check Screen.recognise_type() logic works correctly.")

""" Connects to APEX and logs in user, querying for Username and Password. """
def connect(TrainingSystem=False):  
    if apex_config.LIMS_USER:
        if apex_config.LIMS_USER != "YOUR USERNAME HERE": 
            user = apex_config.LIMS_USER
        else: 
            user = input("Enter your APEX username: ")
    else:
        user = input("Enter your APEX username: ")
    user = user.upper()

    if apex_config.LIMS_PW:
        if apex_config.LIMS_PW == "YOUR PASSWORD HERE":
            pw = getpass.getpass()
        else:
            pw = apex_config.LIMS_PW     
    else:
        pw = getpass.getpass()

    APEX.connect(IP=apex_config.LIMS_IP, Port=apex_config.LIMS_PORT, IBMUser=apex_config.LOCALISATION.IBM_USER, Userprompt=None, PWPrompt=b"Password :", User=user, PW=pw)      
    
    logging.info("Connected to APEX. Reading first screen...")
    while (APEX.Screen.Type != "MainMenu"):
        APEX.read_data()
        logging.debug(f"connect(): Screen type is {APEX.Screen.Type}, first lines are {APEX.Screen.Lines[0:2]}")
        time.sleep(1) # Wait for ON-CALL? to go away

""" """
def disconnect():
    return_to_main_menu(ForceReturn=True)
    logging.info("disconnect(): Disconnecting.")
    APEX.send('', readEcho=False)
    APEX.send_raw(b'\x04', readEcho=False)         

# Script --------
logging.basicConfig(filename='./apex_debug.log', filemode='w', level=logging.DEBUG, format=LOGFORMAT)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter(LOGFORMAT))
logging.getLogger().addHandler(console)

logging.info(f"APEXPredator client, version {VERSION}. (c) Lorenz K. Becker, under GNU General Public License")

try:
    connect()
    BasicInterface()

except Exception as e: 
    logging.error(e)

finally:
    disconnect()
    logging.info("System is now shut down. Have a nice day!")