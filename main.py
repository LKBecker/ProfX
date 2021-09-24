#GPL-3.0-or-later

VERSION = "1.8.3"
LOGFORMAT = '%(asctime)s: %(name)-10s:%(levelname)-7s:%(message)s'

import argparse
import config
import datetime
import logging
import tp_structs
from tp_telnet import ProfX
from tp_utils import process_whitespaced_table, timestamp, extract_column_widths
import tp_NPEX
from collections import Counter
import re
import time

""" Locates samples with AOT beyond TAT (...i.e. any), and marks the AOT as 'NA' if insert_NA_result is set to True """
def aot_stub_buster(insert_NA_result:bool=False, get_creators:bool=False) -> None:
    logging.info(f"aot_stub_buster(): Start up. Gathering history: {get_creators}. NAing entries: {insert_NA_result}.")
    AOTSamples = tp_structs.get_overdue_sets("AUTO", "AOT")
    AOTStubs = Counter()
    
    if (insert_NA_result == False and get_creators == False):
        logging.info("aot_stub_buster() complete.")
        return

    ProfX.return_to_main_menu()
    ProfX.send(config.LOCALISATION.SPECIMENENQUIRY, quiet=True)         # Go into Specimen Inquiry
    ProfX.read_data()
    for AOTSample in AOTSamples: #TODO: issue here; loop likes to get same sample X times...
        ProfX.send(AOTSample.ID, quiet=True, maxwait_ms=2000)  #Open record
        ProfX.read_data()
        AOTSample.from_chunks(ProfX.screen.ParsedANSI) #sometimes around here we get "max() arg is an empty sequence"
        TargetIndex = AOTSample.get_set_index("AOT")
        
        if TargetIndex == -1:
            logging.error(f"Cannot locate AOT set for patient {AOTSample.ID}. Please check code and.or retry.")
            ProfX.send(config.LOCALISATION.EMPTYSTR) #Exit record
            continue
        if get_creators == True:
            #logging.info(f"aot_stub_buster(): Retrieving History for set [AOT] of sample [{AOTSample.ID}]")
            ProfX.send(config.LOCALISATION.SETHISTORY+str(TargetIndex), quiet=True)  #Attempt to open test history, can cause error if none exists
            ProfX.read_data()
            if not ProfX.screen.hasErrors:
                #locate line with 'Set requested by: '
                for line in ProfX.screen.Lines[6].split("\r\n"):
                    if line.find("Set requested by: ") != -1:
                        user = line[ line.find("Set requested by: ")+len("Set requested by: "): ].strip()
                        creationDT  = line[0:16].strip()
                        logging.info(f"aot_stub_buster(): Open set [AOT] of sample [{AOTSample.ID}] was created by [{user}] at {creationDT}.")
                        AOTStubs[ user ] += 1
                ProfX.send(config.LOCALISATION.QUIT)
                ProfX.read_data()
            else:
                logging.info(f"aot_stub_buster(): Could not retrieve history for [AOT] of sample [{AOTSample.ID}].")
        
        if(insert_NA_result == True):
            logging.info(f"aot_stub_buster(): Closing Set [AOT] (#{TargetIndex}) for Sample [{AOTSample.ID}]...")
            ProfX.send(config.LOCALISATION.UPDATE_SET_RESULT+str(TargetIndex), quiet=True)  #Open relevant test record
            ProfX.read_data()
            #TODO: Check screen type!
            ProfX.send(config.LOCALISATION.NA)                              #Fill Record
            ProfX.read_data()
            ProfX.send(config.LOCALISATION.RELEASE, quiet=True)                   #Release NA Result
            #TODO: Check if you get the comment of "Do you want to retain ranges"! Doesn't happen for AOT but...
            ProfX.read_data()
            #TODO: Error(?) in screen rendered seems to shift the IDLine, which 'should' be 'Direct result entry Request <XXX>'
            #if ProfX.screen.Lines[2].split() #Direct result entry           Request: 
            # if there's the interim screen, send another ''
        ProfX.send('', quiet=True)                    #Close record
    #for AOTSample

    if get_creators==True:
        with open(f'./AOTCreators_{timestamp(fileFormat=True)}.log', 'w') as AOTData:
            AOTData.write(f"AOT sets, created {timestamp()}\n")
            AOTData.write("User\tNumber of AOT Stubs\n")
            for key, value in AOTStubs.most_common():
                AOTData.write(f"{key}\t{value}\n")
    logging.info("aot_stub_buster(): Complete.")

""" Retrieves outstanding sendaway (section AWAY) samples. For each sample, retrieves specimen notepad contents, patient details, and any set comments. """
def sendaways_scan(getDetailledData:bool=False) -> None:
    OverdueSAWAYs = tp_structs.get_overdue_sets("AWAY", FilterSets=["ACOV2", "COVABS", "ACOV2S"])    # Retrieve AWAY results from OVRW
    OverdueSAWAYs = [x for x in OverdueSAWAYs if str(x.ID) != "19.0831826.N"] #19.0831826.N - Sample stuck in Background Authoriser since 2019, RIP.
    logging.info(f"sendaways_scan(): There are a total of {len(OverdueSAWAYs)} overdue samples from section 'AWAY', which are not COVABS/ACOV2/ACOV2S or sample 19.0831826.N.")
    if getDetailledData:
        SAWAY_DB = tp_structs.load_sendaways_table()
        # For each sample, retrieve details: Patient FNAME LNAME DOB    
        tp_structs.complete_specimen_data_in_obj(OverdueSAWAYs, GetNotepad=True, GetComments=True, GetFurther=True, ValidateSamples=False, FillSets=False)
        outFile = f"./{timestamp(fileFormat=True)}_SawayData.txt"
        SAWAY_Counters = range(0, len(OverdueSAWAYs))
        logging.info("sendaways_scan(): Beginning to write overdue sendaways to file...")
        with open(outFile, 'w') as SAWAYS_OUT:
            SAWAYS_OUT.write("Specimen\tNHS Number\tLast Name\tFirst Name\tDOB\tSample Taken\tTest\tTest Name\tReferral Lab\tContact Lab At\tHours Overdue\tCurrent Action\tAction Log\tRecord Status\tClinical Details\tSetComms\tSpecN'Pad\n")
            for SAWAY_Sample in OverdueSAWAYs:
                try:
                    OverdueSets = [x for x in SAWAY_Sample.Sets if x.is_overdue]
                    for OverdueSet in OverdueSets:
                        #Specimen NHSNumber   Lastname    First Name  DOB Received    Test
                        outStr = f"{SAWAY_Sample.ID}\t{SAWAY_Sample.NHSNumber}\t{SAWAY_Sample.LName}\t{SAWAY_Sample.FName}\t{SAWAY_Sample.DOB}\t{SAWAY_Sample.Received.strftime('%d/%m/%y')}\t{OverdueSet.Code}\t"

                        #Retrieve Referral lab info
                        ReferralLab_Match = [x for x in SAWAY_DB if x.SetCode == OverdueSet.Code]
                        if(len(ReferralLab_Match)==1):
                            ReferralLab_Match = ReferralLab_Match[0]
                        #Test Name  Referral Lab Contact
                        LabStr = "[Not Found]\t[Not Found]\t[Not Found]\t"
                        if ReferralLab_Match:
                            LabStr = f"{ReferralLab_Match.AssayName}\t{ReferralLab_Match.Name}\t{ReferralLab_Match.Contact}\t"
                            if ReferralLab_Match.Email:
                                LabStr = f"{ReferralLab_Match.AssayName}\t{ReferralLab_Match.Name}\t{ReferralLab_Match.Email}\t"
                        outStr = outStr + LabStr
                        
                        #Hours Overdue
                        outStr = outStr + f"{OverdueSet.Overdue.total_seconds()/3600}\t"
                        
                        ##Hours Since Request
                        HSinceRequest = -1
                        if OverdueSet.RequestedOn:
                            if isinstance(OverdueSet.RequestedOn, datetime.datetime):
                                HSinceRequest = (datetime.datetime.now()-OverdueSet.RequestedOn).total_seconds()//3600
                        #        outStr = outStr + f"{HSinceRequest}\t"
                        #else:
                        #    outStr = outStr + "#N/A\t"
                        
                        #Expected TAT
                        ExpectedTAT = -1
                        if ReferralLab_Match:
                            ExpectedTAT = ReferralLab_Match.MaxTAT
                        #    outStr = outStr + f"{ExpectedTAT}\t"
                        #else:
                        #    outStr = outStr + "[Unknown]\t"
                        
                        # CurrentAction   Action Log
                        outStr = outStr + "\t\t"
                            
                        #Sample Status
                        StatusStr = "Incomplete\t"
                        #if (HSinceRequest>0 and ExpectedTAT>0):
                        #    if(HSinceRequest <= ExpectedTAT):
                        #        StatusStr = "Incomplete (below TAT)\t"
                        outStr = outStr + StatusStr

                        #Clinical Details
                        if SAWAY_Sample.ClinDetails:
                            outStr = outStr + SAWAY_Sample.ClinDetails + "\t"
                        else:
                            outStr = outStr + "No Clinical Details\t"
                        #Check for comments
                        CommStr = "\t"
                        if OverdueSet.Comments: 
                            CommStr = f"{' '.join(OverdueSet.Comments)}\t"
                        outStr = outStr + CommStr
                        
                        #Check for Notepad
                        NPadStr = ""
                        if SAWAY_Sample.hasNotepadEntries == True:
                            NPadStr = "|".join([str(x) for x in SAWAY_Sample.NotepadEntries])
                        outStr = outStr + NPadStr
                    
                        outStr = outStr + "\n"
                        SAWAYS_OUT.write(outStr)
        
                except AssertionError:
                    continue
                    
        logging.info(f"sendaways_scan(): Complete. Downloaded and exported data for {len(SAWAY_Counters)} overdue sendaway samples to file.")

""" Retrieves privilege levels for a list of users"""
def privilege_scan(userlist = None) -> None:
    #TODO: UNTESTED UTILITY FUNCTION
    UserPrivs = []
    UserPrivs.append( "ProfX, Version {VERSION}.\nPrivilege level extraction\n\n" )
    UserPrivs.append( "Username\tFull Name\tPrivilege level\n" )

    if ProfX.UseTrainingSystem == True:
        logging.warning("privilege_scan(): the training system will return different result to the live system!")

    ProfX.return_to_main_menu()
    
    #Gather employee names OR read from file
    if not userlist:
        ul_file = open('./PrivCheck.txt', 'r')
        userlist = ul_file.readlines()
        userlist = [x.trim() for x in userlist]
    
    logging.error("privilege_scan(): FUNCTION ISN'T DONE YET")
    
    #Enter administration area - needs privilege on TelePath user to access
    ProfX.send(config.LOCALISATION.PRIVILEGES) #requires Level 1 access, do *not* write data to this area to avoid messing up the system.
    ProfX.read_data()
    assert ProfX.screen.Type == "PRIVS"

    for user in userlist:
        ProfX.send(user)
        ProfX.read_data() #Check access was successful

        #TODO: If querying an account that does not exist, the cursor goes to line... 6? (TODO:check it's line 6), to make a new account; abort via ProfX.send('^')
        if ProfX.screen.cursorPosition[0]<20:
            logging.info(f"privilege_scan(): User '{user}' does not appear to exist on the system.")
            ProfX.send(config.LOCALISATION.CANCEL_ACTION) #Return to main screen, ready for next
            continue
        
        #If that isn't the case, grab results and parse
        results = ProfX.screen.Lines[3:16] #TODO: Check exact lines
        results = [x for x in results if x.strip()]
        result_tbl = process_whitespaced_table(results, [0, 28]) #TODO: check this estimated col width works
        
        UserPrivs.append( f"{result_tbl[0][1]}\t{result_tbl[1][1]}\t{result_tbl[5][1]}\t\n" ) #TODO: check table

        ProfX.send('A') #Return to admin area, by Accepting the current settings without having changed a thing
    
    logging.info("privilege_scan(): Writing to output file.")
    outFile = f"./{timestamp(fileFormat=True)}_PrivScan.txt"
    with open(outFile, 'w') as out:
        for line in UserPrivs:
            out.write(line)
    logging.info("privilege_scan(): Complete.")

""" retrieves a list of recent speciments for a patient, and runs mass_download() on them. """
def patient_download(SampleID, FilterSets:list=None):
    
    pass

""" Retrieves assay results for a list of Specimens.
    FilterSets: A list of strings, designating which """
def mass_download(Samples:list=None, FilterSets:list=None):
    if not Samples:
        logging.info("mass_download(): No samples supplied, loading from file")
        with open("./ToRetrieve.txt", 'r') as DATA_IN:
            Samples = DATA_IN.readlines()
        Samples = [tp_structs.Specimen(x.strip()) for x in Samples]
    logging.info(f"mass_download(): Begin download of {len(Samples)} samples.")
    if isinstance(Samples[0], str):
        Samples = [tp_structs.Specimen(x.strip()) for x in Samples]
    tp_structs.complete_specimen_data_in_obj(Samples, FilterSets=FilterSets, FillSets=True, GetNotepad=False, GetComments=False)
    tp_structs.samples_to_file(Samples)
    logging.info("mass_download(): Complete.")

""" Experimental graph producer. Not working currently. """
def visualise(Sample:str, FilterSets:list=None, nMaxSamples:int=10):
    Patient = tp_structs.sample_to_patient(Sample)
    Patient.get_n_recent_samples(nMaxSamples=nMaxSamples)
    tp_structs.complete_specimen_data_in_obj(Patient.Samples, GetFurther=False, FillSets=True, ValidateSamples=False)
    Patient.create_plot(FilterAnalytes=FilterSets)

""" Retrieve currently-active FITs and check status via NPEX website """
def NPEX_Buster(Set:str="FIT"):
    logging.info(f"NPEX_Buster(): Retrieving outstanding [{Set}] samples...")
    CurrentSets = tp_structs.get_outstanding_samples_for_Set(Set)
    logging.info(f"NPEX_Buster(): {len(CurrentSets)} samples found. Checking NPEx...")
    tp_NPEX.retrieve_NPEX_samples(CurrentSets)

def auth_queue_size(QueueFilter:list=None, DetailLevel:int=0):
    ProfX.return_to_main_menu()
    QueueSize = 0
    #TODO: 
    logging.info(f"auth_queue_size(): There are {QueueSize} samples awaiting authorisation.")

def CLI():
    parser = argparse.ArgumentParser(prog='ProfX', description='Connects to a TelePath LIMS system and extracts data.')
    parser.add_argument('sample', help="The ID of the sample to process")
    parser.add_argument('-t', "-training", help='Connects to training system, not live system', action="store_true")
    parser.add_argument('-saway', '-sendaways', help='Retrieves all outstanding sendaways tests (excluding ACOV2/COVABS), with specimen notepad and any Set notes', action="store_true")
    parser.add_argument('-aot', '-aotBuster', help="Finds all outstanding samples with AOT (Add-on tests). Can also retrieve the creator of such stubs, and can NA the AOT entry automatically", action="store_true")
    parser.add_argument('-outfile', '-o', help='Filename for any output data.')
    parser.add_argument('-h', '-history', help='Retrieves recent test results for the patient associated with a sample, and displays or outputs them.', action="store_true")
    parser.add_argument('-dl', '-download', help='Retrieves results for a list of samples.', action="store_true")
    parser.add_argument('-test', help='Specifies the test to download')
    parser.add_argument('-user', help='Specifies the user to access the system as. Overrides config.py. Will require user to enter their password.')

    args = parser.parse_args()    

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

    def is_alphanumeric(UserInput:str, lowerBound:None, upperBound:None):
        if UserInput == re.sub('[\W0-9]+', '', UserInput):
            return True
        return False

    def is_sample(UserInput:str, lowerBound:None, upperBound:None):
        _sample = tp_structs.SampleID(UserInput)
        return _sample.validate()

    print("""
    
    Welcome to the ProfX custom TelePath client.
    
    Please select from the following options:
    
        1   Sendaway processing
        2   Closing outstanding AOTs for automation
        3   Mass download of results
        4   NPEX interface
        5   Retrieve recent samples for a Set
        6   Generate Patient history/graphs
        7   Set ripper for Beaker
        8   Exit
    """)
    choice = get_user_input(is_numeric, "Please select a number from 1 to 8:", "Please select from the above options: ", 1, 8)

    if choice=="1": # Sendaways
        print("""
    
    Sendaways processing menu
    
    Please select from the following options:

        1   List number of outstanding sendaways
        2   Generate outstanding sendaways table      
        
        """)
        choice2 = get_user_input(is_numeric, "Please select a number from 1 to 2.", "Please select from the above options: ", 1, 2)
        if choice2 == "1":
            sendaways_scan()
        if choice2 =="2":
            sendaways_scan(getDetailledData=True)

    if choice=="2": #AOTs
        print("""
    
    Outstanding AOTs menu
    
    Please select from the following options:

        1   List number of open AOTs for section AUTO
        2   Close all open AOTs for section AUTO
        3   List creators for all open AOTs for section AUTO
        4   Close all open AOTs for section AUTO and list creators
        """)
        choice2 = get_user_input(is_numeric, "Please select a number from 1 to 4.", "Please select from the above options: ", 1, 4)
        if choice2 == "1":
            aot_stub_buster()
        if choice2 =="2":
            aot_stub_buster(insert_NA_result=True)
        if choice2 =="3":
            aot_stub_buster(get_creators=True)
        if choice2 =="4":
            aot_stub_buster(insert_NA_result=True, get_creators=True)

    if choice=="3": #Mass Download
        print("""
    Mass data download menu
    
    Please select from the following options:

        1   Download a number of recent results for a set
        2   Download samples from an external file
        """)
        choice2 = get_user_input(is_numeric, "Please select a number from 1 to 2.", "Please select from the above options: ", 1, 2)
        if choice2 == "1":
            SetToDL = get_user_input("For which set do you want to retreive samples? ", is_alphanumeric, "Please use only A-Za-z and 0-9.")
            NSets   = get_user_input("How many samples do you want to retrieve at most? ", is_numeric, "Please enter a number between 1 and 100.", 1, 100)
            SampleList = tp_structs.get_recent_samples_of_set_type(SetToDL, nMaxSamples=int(NSets))
            mass_download(Samples=SampleList)
        if choice2 =="2":
            mass_download()

    if choice=="4": #NPEX interface
        print("""
    NPEX Interface
    
    Preparing to retrieve outstanding sample data from NPEx...
        """)
        SetToDL = get_user_input(is_alphanumeric, "Please use only A-Za-z and 0-9.", "For which set do you want to retreive NPEX data? ")
        NPEX_Buster(SetToDL)

    if choice=="5":
        print("""
    Recent samples
    
        """)
        SetToDL = get_user_input(is_alphanumeric, "Please use only A-Za-z and 0-9.", "For which set do you want to retrieve recent samples? ")
        NSets   = get_user_input(is_numeric, "Please enter a number between 1 and 100.", "How many samples do you want to retrieve at most? ", 1, 100)
        print(tp_structs.get_recent_samples_of_set_type(SetToDL, nMaxSamples=NSets))
        
    if choice=="6":
        print("""
    Patient history
    
        """)
        SampleToDL = get_user_input(is_sample, "Please enter a valid sample ID.", "Which sample do you wish to generate a patient history from? ")
        tp_structs.get_recent_history(SampleToDL, nMaxSamples=15)

    if choice=="7":
        import tp_setripper
        SetsIO = open("./SetsToExtract.txt", "r")
        SetsToRip = SetsIO.readlines()
        SetsIO.close()
        SetsToRip = [x.strip() for x in SetsToRip]
        tp_setripper.set_ripper(SetsToRip)

    else:
        return

logging.basicConfig(filename='./debug.log', filemode='w', level=logging.DEBUG, format=LOGFORMAT)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter(LOGFORMAT))
logging.getLogger().addHandler(console)

logging.info(f"ProfX TelePath client, version {VERSION}. (c) Lorenz K. Becker, under GNU General Public License")

try:
    ProfX.connect()
    #BasicInterface()

    #aot_stub_buster() # Shows how many open AOTs there are for section AUTO
    #aot_stub_buster(insert_NA_result=False, get_creators=True) # Shows how many open AOTs there are for section AUTO, closed them, tells you who made them
    
    #sendaways_scan() # Shows how many overdue sendaways there are
    #sendaways_scan(getDetailledData=True) # Shows how many overdue sendaways there are, and creates a spreadsheet to follow them up. Needs a sendaways_database.tsv    
    
    #recentSamples = tp_structs.get_recent_samples_of_set_type("ELAST", nMaxSamples=100) # Retrieves up to 100 recent samples with ELAST. Good for hunting for spare samples to test things.
    #mass_download(recentSamples, FilterSets=["ELAST"]) # Downloads and saves into a file all the results for the samples retrieved earlier. Filters for Set in FilterSets.
    #mass_download() # Downloads all data for samples in ToRetrieve.txt and saves to file.
    
    #tp_structs.get_recent_history("A,21.0676517.Z", nMaxSamples=15) #Gets up to 15 recent samples for the same patient as the given sample. Good to get a quick patient history.
    
    NPEX_Buster(Set="FIT") # Retrieves outstanding (but not overdue) Sets for the entire lab, and checks NPEX whether there are results for any. 
    #tp_NPEX.retrieve_NPEX_data("A,21.7784000.W")

    #visualise("A,21.0676517.Z", nMaxSamples=15) #Still a bit experimental - retrieves recent data for the patient of this sample and makes graphs.

except Exception as e: 
    logging.error(e)

finally:
    ProfX.disconnect()
    logging.info("System is now shut down. Have a nice day!")
    input("Press any key to exit...")