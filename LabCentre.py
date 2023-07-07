#GPL-3.0-or-later
#                   ⣰⣦⣄           
#                ⢀⣴⣿⡿⠃          
#               ⠭⠚⠿⣋            
#             ⡜ ⠱⡀             
#            ⡐   ⠑⡀            
#   ⣄      ⡰⣠⠼⠚⠛⢦⣜⣆      ⢠⠧⢴⣶⡆
#⠰⠿⠛⠹    ⡰⡹⠃ ⢠  ⠙⢭⣧⡀    ⠳⡀⠈ 
#  ⡠⠃ ⢀⣀⡴⠙⠷⢄ ⢸⠆ ⣠⠾⠉⠹⣶⠦⢤⣀⡇  
#  ⠉⠉⠉⠉⡰⠧  ⡵⣯⠿⠿⣭⠯⠤⠤⠤⠬⣆ ⠈   
#     ⣰⣁⣁⣀⣀⣄⣛⠉⠉⢟⠈⡄   ⢈⣆    
#    ⡰⡇⡘   ⣰⣀⣀⣀⣀⣀⣇⣀⣀⣀⣆⣋⡂     
#          ⢸    ⡇                  
#          ⠈⢆   ⠘⠒⢲⠆       
#            ⢹⡀   ⠸        
#            ⠈⡇   ⠁        
"""
    Behold! The awesome fires of God. 
    The limitless power of pure creation itself. 
    Look carefully. 
    Observe how it is used for the same purpose a man might use an especially sharp rock. 
"""


import argparse
from collections import Counter
import config
import datastructs
import datetime
import getpass
import logging
import os.path
import telnet_ANSI
import re
import time
import utils

VERSION = "0.5r77"
LOGFORMAT = '%(asctime)s: %(name)-11s:%(levelname)-7s:%(message)s'

DELAY_SHORTEST = 1.5
DELAY_SHORT = 3
DELAY_MED   = 5

#logging.basicConfig(filename='./debug.log', filemode='w', level=logging.DEBUG, format=LOGFORMAT)
logging.basicConfig(filename='./lastrun.log', filemode='w', level=logging.INFO, format=LOGFORMAT)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter(LOGFORMAT))
logging.getLogger().addHandler(console)

telnet_ANSI.Connection.recognise_Screen_type = config.LOCALISATION.identify_screen #Overrides default function with that from localisation
LabCentre = telnet_ANSI.Connection(Answerback=config.LOCALISATION.ANSWERBACK)

class LCSpecimen(datastructs.Specimen):
    def __init__(self):
        pass

    def printReport(self) -> None:
        pass

def connect_to_LIMS():  
    if config.LOCALISATION.LIMS_USER:
        if config.LOCALISATION.LIMS_USER != "YOUR USERNAME HERE": 
            user = config.LOCALISATION.LIMS_USER
        else: 
            user = input("Enter your LabCentre username (and press Enter) (and press Enter): ")
    else:
        user = input("Enter your LabCentre username (and press Enter; it won't be shown!) (and press Enter; it won't be shown!): ")
    user = user.upper()

    if config.LOCALISATION.LIMS_PW:
        if config.LOCALISATION.LIMS_PW == "YOUR PASSWORD HERE":
            pw = getpass.getpass()
        else:
            pw = config.LOCALISATION.LIMS_PW     
    else:
        pw = getpass.getpass()

    LabCentre.connect_single_user(IP=config.LOCALISATION.LIMS_IP, Port=config.LOCALISATION.LIMS_PORT, Answerback=config.LOCALISATION.ANSWERBACK,
                    User=config.LOCALISATION.LIMS_USER, PW=config.LOCALISATION.LIMS_PW)      
    LabCentre.send("") #Site Selection Screen (defaulting to S1)
    LabCentre.send("") #First Options Screen
    LabCentre.send("") #Second Options Screen
    tmp = LabCentre.tn.read_until("AGR.BACKGROUND is 0\r\n".encode("ASCII")) #Skip those screens
    #print(tmp)

    while (LabCentre.ScreenType != "LabCentre_MainScreen"):
        LabCentre.read_data()
        if (LabCentre.ScreenType == "ChangePassword"):
            raise Exception("LabCentre demands a password change. Please log in using your regular client, change your password, then change the config file for this utility.")
        logging.debug(f"connect(): Screen type is {LabCentre.ScreenType}, first lines are {LabCentre.Lines[0:3]}")
    logging.info("connect() Connection established. Login successful.")

def disconnect():
    logging.debug("disconnect(): Disconnecting.")
    #return_to_main_menu()
    counter = 0
    while counter < 15:
        LabCentre.send(config.LOCALISATION.CANCEL_ACTION, readEcho=False)
        time.sleep(DELAY_SHORTEST)
        counter = counter + 1
    logging.debug("disconnect(): Should be disconnected.")

def return_to_main_menu(MaxTries:int=10): #TODO: Fix, recognition probably busted,.
    TryCounter = 0
    logging.debug("Returning to main menu...")
    TargetScreen = "LabCentre_MainScreen"
    while(LabCentre.ScreenType != TargetScreen and TryCounter <= MaxTries):
        LabCentre.send(config.LOCALISATION.CANCEL_ACTION)
        LabCentre.read_data()
        logging.debug(f"return_to_main_menu(): Screen ID detected as {LabCentre.ScreenType}, first line is {' '.join(LabCentre.Lines[0:1])}")
        TryCounter = TryCounter+1
    if TryCounter > MaxTries:
        raise Exception(f"Could not reach main menu in {MaxTries} attempts. Check recognise_Screen_type() logic works correctly and that CANCEL_ACTION is allowed input.")

def get_Patient_Specimen_History(Patients:list=None, Filter:list=None):
    if not Patients:
        with open("./RetrieveHistory.txt", 'r') as io:
            Patients = [x.strip() for x in io.readlines()]

    nPatients = len(Patients)

    logging.info(f"get_Patient_Specimen_History(): Ready to retrieve details for {nPatients} Patients.")

    LabCentre.send("1") #Enter Clinical Chemistry
    LabCentre.read_data()
    LabCentre.send("1") #Enter Specimen Reception
    LabCentre.read_data()
    LabCentre.send("1") #Results Enquiry
    time.sleep(DELAY_SHORT)
    LabCentre.read_data()
        
    output = open(f"./{utils.timestamp(True)}_PatientHistory.txt", 'a')
    output.write("PatientID\tSpecimenID\tSpecimenDateTime\tSets\n")
    output.flush()
    patientCounter = 0
    headerWidths = None

    for currentPatient in Patients:
        _currentPatient = currentPatient
        if (len(_currentPatient) == 7) | (len(_currentPatient) == 5):
            if not (ord(_currentPatient[-1]) > 64 and ord(_currentPatient[-1]) < 91):
                if not _currentPatient == "1175942": #HACK
                    _currentPatient = _currentPatient.zfill(8)
                    logging.info(f"Patching patient ID from {currentPatient} to {_currentPatient}.")
            
        sampleCounter = 0
        patientCounter = patientCounter + 1
        
        LabCentre.send('') #Go down to patient enquiry
        LabCentre.read_data()
        LabCentre.send(_currentPatient) #TODO: Pad 5 / 7 number-only items to 8 with leading 0s
        time.sleep(DELAY_SHORT) #TODO: Verify "Loading Requests for {PATIENT NAME}..." is gone
        LabCentre.read_data()

        if (LabCentre.Lines[-1].find("PLEASE NOTE") != -1):
            LabCentre.send('')
            time.sleep(DELAY_MED)
            LabCentre.read_data()

        #TODO: check for bottommost-line being 'ID HAS CHANGED'/BELL, send ENTER

        if LabCentre.Lines[3].find("Requests") == -1:
            logging.error(f"ERROR processing patient {_currentPatient}. Please retry manually. Possible cause: Only one sample exists.")
            SpecimenData = ' '.join(LabCentre.Lines[2:5])
            output.write(f"{currentPatient}\t{SpecimenData}\n")
            LabCentre.send('A')
            time.sleep(DELAY_SHORT)
            LabCentre.read_data()
            continue
        
        while LabCentre.Bell == False:
            SpecimenData = LabCentre.Lines[5:20]
            if not headerWidths:
                headerWidths = utils.extract_column_widths(SpecimenData[0])
                headerWidths[0] = headerWidths[0] - 1 #HACK 
                headerWidths.remove(57) #HACK; the single space in the header throws off the current algo.

            SpecimenData = utils.process_whitespaced_table(SpecimenData[1:], headerWidths)
            SpecimenData = [x for x in SpecimenData if x[0]]
            for Specimen in SpecimenData:
                #"PatientID\tSpecimenID\tSpecimenDateTime\tSets\n"
                outStr = f"{currentPatient}\t{Specimen[2]}\t{Specimen[1]}\t{Specimen[5]}"
                output.write(outStr + '\n')
                #logging.debug(outStr)

            sampleCounter = sampleCounter + len(SpecimenData)

            LabCentre.send('F') #Further page
            time.sleep(DELAY_SHORTEST)
            LabCentre.read_data()
            
        logging.info(f"Retrieved {sampleCounter} samples for patient {currentPatient}.")
        
        LabCentre.send('C') #Cancel
        time.sleep(DELAY_SHORTEST)
        LabCentre.read_data()

        if patientCounter % 5 == 0:
            pct = (patientCounter / nPatients ) * 100
            output.flush()
            logging.info(f"get_Patient_Specimen_History(): Processed {patientCounter} of {nPatients} Patients ({pct:.2f} %). Flushing stream.")

    output.flush()
    output.close()
    logging.info("get_Patient_Specimen_History(): All patients processed.")

def get_Recent_Specimens_For_Set(Set:str, nResults:int=50, startDate:str=None, endDate:str=None) -> None:
    #TODO: implement nResults, startDate, endDate
    output = open(f"./{utils.timestamp(True)}_Recent_{Set}.txt", 'a')
    output.write("PatientID\tSpecimenID\tSpecimenDateTime\tSets\n")
    output.flush()

    LabCentre.send("1") #Enter Clinical Chemistry
    LabCentre.read_data()
    LabCentre.send("1") #Enter Specimen Reception
    LabCentre.read_data()
    LabCentre.send("1") #Results Enquiry
    time.sleep(DELAY_SHORT)
    LabCentre.read_data()
        
    specimenCounter = 0
    Specimens = []
    headerWidths = None
    currentDate = None
    if not startDate:
        startDate = datetime.datetime.now()
    startDate = startDate.strftime("%d-%m-%y")
    if not endDate:
        endDate = datetime.datetime.now()
    endDate = endDate.strftime("%d-%m-%y")

    LabCentre.send('') #Go down to patient code
    LabCentre.send('') #Go down to Source code
    LabCentre.send('') #Go down to Cons / GP
    LabCentre.send('') #Go down to Request Item
    LabCentre.read_data()
    LabCentre.send(Set)
    LabCentre.read_data() #TODO check for errors
    LabCentre.send('1') #Select booking source Central Biochem
    LabCentre.read_data() #TODO check for errors
    LabCentre.send(startDate)
    LabCentre.read_data()
    time.sleep(3)
    LabCentre.send(endDate)
    
    
    time.sleep(15) #TODO replace w/ sleep read sleep function
    LabCentre.read_data()

    if headerWidths is None:
        headerWidths = utils.extract_column_widths(LabCentre.Lines[5])
        #TODO: Hack/check improvement for 1-space items.
    #loop - read page, next, check for bell
    while LabCentre.Bell == False:
        SpecimenLines = [x for x in LabCentre.Lines[6:-2] if x]
        SpecimenLines = utils.process_whitespaced_table(SpecimenLines, headerWidths=headerWidths)
        for line in SpecimenLines:
            output.write("\t".join(line[1:]))
            output.write('\n')
            specimenCounter = specimenCounter+1
        
        LabCentre.send('F')
        LabCentre.read_data()

    # increment last date, check          
    logging.info(f"get_Recent_Specimens_For_Set(): Retrieved {specimenCounter} samples for set {Set}.")
    
    LabCentre.send('C') #Cancel
    time.sleep(DELAY_SHORTEST)
    LabCentre.read_data()

    output.flush()
    output.close()
    logging.info("get_Recent_Specimens_For_Set(): All retrieved.")

def get_Specimen_Data(Specimens:list=None, extractResults:bool=False, extractAuditLog:bool=False, extractDetailledDTs:bool=False, extractLabComments:bool=False) -> None:
    #TODO: Combine with Get_Specimen_Details() into Get_Specimen_Data(), with mode triggers, ability to extract comments, etc.
    #TODO: Create / port Masterlab_Specimen class. Specimen ID: one letter (B/H/S/I), nine digits, unknown checksum

    def processLabComments() -> None:
        LabCentre.send('1') #Enter lab comment pane/panges
        time.sleep(DELAY_SHORT)
        LabCentre.read_data()
        pageMatch = pageNumRegex.match(LabCentre.Lines[-1])
        if pageMatch:
            maxLabCommPages = int(pageMatch.group(1))
            labCommPage = 0
            logging.info(f"Extracting {maxLabCommPages} pages of Lab comments...")
            while labCommPage < maxLabCommPages:
                labCommPage = labCommPage + 1
                _tmpComments = LabCentre.Lines[9:17]
                _tmpComments = [x[11:70].strip() for x in _tmpComments]
                _tmpComments = [x for x in _tmpComments if x]
            
                for x in _tmpComments: Comments.append(x)
            
                if maxLabCommPages > 1:
                    LabCentre.send("F")
                    LabCentre.read_data()
            
            LabCentre.send('A') #exit multivalue action
            time.sleep(DELAY_SHORT)
            LabCentre.read_data()
    
    pageNumRegex = re.compile(r'\s+Page \d+ of (\d+)\s*: Multivalue Action')

    if not Specimens:
        with open("./RetrieveSpecimenData.txt", 'r') as io:
            Specimens = [x.strip() for x in io.readlines() if x]

    nSpecimens = len(Specimens)
    saveInterval = min(50, int(nSpecimens*0.1)) #Save every 50 specimens or every 10%, which ever is sooner
    saveInterval = max(saveInterval, 1)
    logging.debug(f"get_Specimen_Data(): saveInterval set to every {saveInterval} samples.")

    logging.info(f"get_Specimen_Data(): Ready to retrieve details for {nSpecimens} samples...")

    LabCentre.send("1") #Enter Clinical Chemistry
    LabCentre.read_data()
    LabCentre.send("1") #Enter Specimen Reception
    LabCentre.read_data()
    LabCentre.send("1") #Results Enquiry
    time.sleep(DELAY_MED)
    LabCentre.read_data()
    
    output = open(f"./{utils.timestamp(True)}_ExtractedSpecimenResults.txt", 'a', encoding="utf-8")
    output.write("Specimen ID\tCollection DateTime\tTest\tResult\tUnits\tRange\tStatus\n") #TODO only if file does not exist / daily file
    output.flush()
    specCounter = 0
    headerWidths = None

    for Specimen in Specimens:
        Comments = ["Laboratory Comment                                      Item"]
        compensateBlankRequests = False
        #assert LabCentre.ScreenType == "Specimen_Enquiry" #TODO
        LabCentre.send(Specimen)
        time.sleep(DELAY_SHORT)
        LabCentre.read_data()

        #TODO: check for invalid specimen ID line

        compensateBlankRequests = (LabCentre.Lines[-1].strip().find("REQUEST ITEM NOT ON FILE") != -1)

        while compensateBlankRequests == True:
            LabCentre.send('')
            time.sleep(DELAY_SHORT)
            LabCentre.read_data()
            compensateBlankRequests = (LabCentre.Lines[-1].strip().find("REQUEST ITEM NOT ON FILE") != -1)

        if (LabCentre.Lines[-1].find("PLEASE NOTE") != -1):
            LabCentre.send('')
            time.sleep(DELAY_MED)
            LabCentre.read_data()

        if (LabCentre.Lines[-1].find("No Requests for this patient") != -1):
            output.write(f"{Specimen}\tNo Request Found\t\t\t\t\n")
            LabCentre.send('')
            LabCentre.read_data()
            continue

        #TODO: Extract header data... 1:5 rows. Collection DT, Received DT, DOB, Name, ID...
        SpecimenDT = LabCentre.Lines[2][LabCentre.Lines[2].find("Spm:")+4:].strip()
        #header2 = re.match(r"Spm No: (?P<SpmNo>\w{1}\d{9})\s+(?P<PtLName>[\w \-]+), (?P<PtFNames>[\w\- ]+) \((?P<PtTitle>\w+\.*?)\) (?P<PtDOB>\d{2}-\w{3}-\d{4}) .+YRS (?P<PtSex>\w+)", headers[1])
        #header3 = re.match(r"Pat No: (?P<PtHospID>[\w0-9]+)\s+Source: (?P<SpmSource>[\w0-9]+) Con/Gp: (?P<SpmCon>[\w0-9, \.]+?)\s+(?P<SpmReqDate>\d{2}-\w{3}-\d{4})", headers[2])
        #extract to dict/list
        #TODO: Make object, encapsulate as function in Specimen() constructor / utility function     

        #TODO: add check of ID on screen vs internal ID - to detect if stuck.
        specCounter = specCounter + 1
        pageCounter = 0
        maxPages = 1

        MultiPage = LabCentre.Lines[-1].find("Multivalue Action")
        if MultiPage != -1:
            pageMatch = pageNumRegex.match(LabCentre.Lines[-1])
            if pageMatch:
                maxPages = int(pageMatch.group(1))
        logging.info(f"Retrieving {maxPages} pages of results for Specimen {Specimen} ...")

        if maxPages == 1: #If there's no multiple pages; any Lab Comments are displayed immediately
            LabCommentPane = [x for x in LabCentre.ParsedANSI if x.text.strip() == "LabCentre - LABORATORY COMMENTS"] #TODO: replace with checking precise line?
            if LabCommentPane:
                logging.debug(f"get_Specimen_Data(): Lab comments identified for specimen {Specimen}")
                if extractLabComments == True: 
                    processLabComments()

                LabCentre.send('A') #Accept
                time.sleep(DELAY_SHORT)
                LabCentre.read_data()

        if not headerWidths:
            headerWidths = utils.extract_column_widths(LabCentre.Lines[6])
            headerWidths.remove(6) #HACK
            headerWidths.remove(61) #HACK
            headerWidths.remove(66) #HACK
        
        while pageCounter < maxPages:
            pageCounter = pageCounter + 1
            if extractResults:
                #TestData = LabCentre.Lines[7:20]
                if pageCounter == 1:
                    output.write('──────────────────────────────────────────────────────────────────────────────\n')
                    Header = LabCentre.Lines[2:5]
                    for line in Header:
                        output.write(line)
                        output.write('\n')
                    output.write('──────────────────────────────────────────────────────────────────────────────\n')
                
                TestData = LabCentre.Lines[7:20]
                #TestData = utils.process_whitespaced_table(TestData, headerWidths=headerWidths)
                TestData = [x for x in TestData if x[0]]
                TestData = [x for x in TestData if x.strip()]
                for row in TestData:
                    #output.write(f"{Specimen}\t{SpecimenDT}\t{row[0]}\t{row[1]}\t{row[2]}\t{row[3]}\t{row[4]}\n")
                    #output.write(f"{row[0]}\t{row[1]}\t{row[2]}\t{row[3]}\t{row[4]}\n")
                    output.write(row)
                    output.write('\n')

            if maxPages > 1:
                LabCentre.send("F")
                LabCentre.read_data()

        if maxPages > 1: #if there's multiple pages of results, pages needs to be (A)ccepted, then any comments are displayed
            LabCentre.send('A') #Accept
            time.sleep(DELAY_SHORT)
            LabCentre.read_data()
            LabCommentPane = [x for x in LabCentre.ParsedANSI if x.text.strip() == "LabCentre - LABORATORY COMMENTS"]
            if LabCommentPane:
                if extractLabComments == True: 
                    processLabComments()
                LabCentre.send('A') #Accept
                time.sleep(DELAY_SHORT)
                LabCentre.read_data()

        if extractLabComments and len(Comments) > 1:
            output.write("\n")
            for line in Comments:
                output.write(f"{line}\n")

        #TODO: instead of blanket wait, send, read, check if "please wait" is on screen, if yes repeat until not...
        output.write("\n")

        #SpecimenChunks = [x for x in LabCentre.ParsedANSI if (x.line < 5)]
        #SpecimenDateTime = SpecimenData[0][53:].strip()
        #SpecimenID = SpecimenData[1][10:20]
        #PatientName= SpecimenData[1][21:42].strip().replace('\t', '')
        #PatientDOB = SpecimenData[1][43:54].strip()
        #PatientID = SpecimenData[2][9:21].strip()
        #SpecimenSource = SpecimenData[2][32:43].strip()

        if extractAuditLog:
            LabCentre.send('U') #open aUdit log
            time.sleep(DELAY_SHORT)
            LabCentre.read_data()

            logPageCounter = 0
            maxLogPages = 1
            pageMatch = pageNumRegex.match(LabCentre.Lines[-1])
            try:
                maxLogPages = int(pageMatch.group(1))
                logging.info(f"get_Specimen_Data(): Extracting {maxLogPages} pages of audit log for {Specimen}...")
            except Exception:
                pass


            while logPageCounter < maxLogPages:
                logPageCounter = logPageCounter + 1
                logData = LabCentre.Lines[7:22]
                for row in logData:
                    output.write(f"{Specimen}\t{SpecimenDT}\t{row}\n")

                if maxPages > 1:
                    LabCentre.send("F")
                    LabCentre.read_data()
                
            LabCentre.send("A")
            LabCentre.read_data()

            LabCentre.send("A")
            LabCentre.read_data()

        if extractDetailledDTs:
            #TODO
            logging.info(f"get_Specimen_Data(): Extracting Other Details for {Specimen}...")
            LabCentre.send('OD') #Other Details
            time.sleep(2)
            LabCentre.read_data()
            #CollectionDT = " ".join([x for x in LabCentre.Lines[2].split(" ") if x][-2:])
            ReceivedDT =   LabCentre.Lines[6][14:33]
            AuthDT =       LabCentre.Lines[7][14:33]
            #output.write(f"{Specimen}\t{SpecimenDT}\tCollected\t{CollectionDT}\n")
            output.write(f"{Specimen}\t{SpecimenDT}\tReceived\t{ReceivedDT}\n")
            output.write(f"{Specimen}\t{SpecimenDT}\tAuthorised\t{AuthDT}\n")
            LabCentre.send('A') #Return to overview
            LabCentre.read_data()

        pct = (specCounter / nSpecimens ) * 100
        try:
            if specCounter % saveInterval == 0:
                logging.info(f"get_Specimen_Data(): Processed {specCounter} of {nSpecimens} samples ({pct:.2f} %). Flushing stream.")
                output.flush()
        except ZeroDivisionError:
            pass

        LabCentre.send('A') #Accept; returning to specimen selection
        LabCentre.read_data()
        #REPEAT

    output.flush()
    output.close()
    logging.info("get_Specimen_Data(): All specimens processed.")

if __name__ == "__main__":
    logging.info(f"ProfX LabCentre client, version {VERSION}. (c) Lorenz K. Becker, under GNU General Public License")
    connect_to_LIMS()
        
    try:
        #get_Patient_Specimen_History(Patients=["03275453"])
        #get_Recent_Specimens_For_Set("AKIG", startDate=datetime.date(2023, 6, 21), endDate=datetime.date(2023, 6, 20))
        get_Specimen_Data(extractResults=True, extractAuditLog=False, extractDetailledDTs=False, extractLabComments=True)

    except Exception as e: 
        logging.error(e)

    finally:
        disconnect()
        logging.info("System is now shut down. Have a nice day!")
