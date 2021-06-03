#GPL-3.0-or-later
"""#TODO:
    telePath_telnet
        Update recognizeScreen() to also check whether data field(s) are filled in -> SpecEnquiry_Blank / SpecEnquiry_Filled; Notepad_Blank/ Notepad_Patient/ Notepad_Entry;   
    telePath_data
        Update Specimen parsing (check for highlighted chunks if not on the training system; on training system... idk, pray?)
        Specimen.WriteToFile and possibly TestSet.WriteToFile function(s)
        Extend Specimen() with matplotlib graphing function, or data dump (table format) -> hook into WriteToFile.
    main
        command line arg parser lol"""
VERSION = "1.6.0"
LOGFORMAT = '%(asctime)s:%(name)-10s:%(levelname)-7s:%(message)s'

#import argparse
import datetime
import logging
import tp_structs
from tp_telnet import ProfX
from tp_utils import process_whitespaced_table, timestamp

""" Locates samples with AOT beyond TAT (...i.e. any), and marks the AOT as 'NA' if insert_NA_result is set to True """
def aot_stub_buster(insert_NA_result:bool=False) -> None:
    AOTSamples = tp_structs.get_overdue_sets("AUTO", "AOT")
    logging.info(f"aot_stub_buster: There are {len(AOTSamples)} samples with Set AOT that is overdue.")
    if(insert_NA_result == True):
        ProfX.return_to_main_menu()
        ProfX.send('SENQ', quiet=True)         # Go into Specimen Inquiry
        ProfX.read_data()
        for AOTSample in AOTSamples:
            ProfX.send(AOTSample, quiet=True)  #Open record
            ProfX.read_data()
            SampleData = tp_structs.Specimen(AOTSample, ProfX.screen.ParsedANSI)
            TargetIndex = SampleData.get_set_index("AOT")
            logging.debug("AOT test should be at index %d for sample %s" % (TargetIndex, SampleData.ID))
        
            ProfX.send('U'+str(TargetIndex), quiet=True)   #Open relevant test record
            ProfX.send('NA')                  #Fill Record
            ProfX.send('R', quiet=True)                   #Release NA Result
            #TODO: Check if you get the comment of "Do you want to retain ranges"! Doesn't happen for AOT but...
            ProfX.send('', quiet=True)                     #Close record
        #for AOTSample
    #if insert_NA_result == True

""" Retrieves outstanding sendaway (section AWAY) samples. For each sample, retrieves specimen notepad contents, patient details, and any set comments. """
def sendaways_scan() -> None:
    SAWAY_DB = tp_structs.load_sendaways_table()
    logging.info("sendaways_scan(): Sendaways database loaded.")
    OverdueSAWAYs = tp_structs.get_overdue_sets("AWAY")    # Retrieve AWAY results from OVRW
    #19.0831826.N - Sample stuck in Background Authoriser since 2019, RIP.
    #OverdueSAWAYs = [x for x in OverdueSAWAYs if x  ]
    
    # For each sample, retrieve details: Patient FNAME LNAME DOB    
    tp_structs.complete_specimen_data_in_obj(OverdueSAWAYs, GetNotepad=True, GetComments=True, ValidateSamples=False, FillSets=False)
    outFile = f"S:/CS-Pathology/BIOCHEMISTRY/Z Personal/LKBecker/{timestamp(fileFormat=True)}_SawayData.txt"
    SAWAY_Counters = range(0, len(OverdueSAWAYs))
    logging.info("sendaways_scan(): Beginning to write overdue sendaways to file...")
    with open(outFile, 'w') as SAWAYS_OUT:
        SAWAYS_OUT.write("Specimen\tLastname\tFirst Name\tDOB\tReceived\tTest\tTest Name\tReferral Lab Contact\tHours Overdue\tHours Since Request\tExpected TAT\tNPEx\tCurrent Action\tAction Log\tSample Status\tSetComms\tSpecN'Pad\n")
        for SAWAY_Sample in OverdueSAWAYs:
            try:
                OverdueSets = [x for x in SAWAY_Sample.Sets if x.is_overdue]
                for OverdueSet in OverdueSets:
                    #Specimen   Lastname    First Name  DOB Received    Test
                    outStr = f"{SAWAY_Sample.ID}\t{SAWAY_Sample.LName}\t{SAWAY_Sample.FName}\t{SAWAY_Sample.DOB}\t{SAWAY_Sample.Received.strftime('%d/%m/%y')}\t{OverdueSet.Code}\t"
                    
                    #Retrieve Referral lab info
                    ReferralLab_Match = [x for x in SAWAY_DB if x.Setcode == OverdueSet.Code]
                    if(len(ReferralLab_Match)==1):
                        ReferralLab_Match = ReferralLab_Match[0]
                    #Test Name  Referral Lab Contact
                    LabStr = "[Not Found]\t[Not Found]\t"
                    if ReferralLab_Match:
                        LabStr = f"{ReferralLab_Match.AssayName}\t{ReferralLab_Match.Contact}\t"
                        if ReferralLab_Match.Email:
                            LabStr = f"{ReferralLab_Match.AssayName}\t{ReferralLab_Match.Email}\t"
                    outStr = outStr + LabStr
                    
                    #Hours Overdue
                    outStr = outStr + f"{OverdueSet.Overdue.total_seconds()/3600}\t"
                    
                    #Hours Since Request
                    HSinceRequest = -1
                    if OverdueSet.RequestedOn:
                        if isinstance(OverdueSet.RequestedOn, datetime.datetime):
                            HSinceRequest = (datetime.datetime.now()-OverdueSet.RequestedOn).total_seconds()//3600
                            outStr = outStr + f"{HSinceRequest}\t"
                    else:
                        outStr = outStr + "#N/A\t"
                    
                    #Expected TAT   NPEx    CurrentAction   Action Log
                    ExpectedTAT = -1
                    if ReferralLab_Match:
                        ExpectedTAT = ReferralLab_Match.MaxTAT
                        outStr = outStr + f"{ExpectedTAT}\t\t\t\t"
                    else:
                        outStr = outStr + "[Unknown]\t\t\t\t"
                        
                    #Sample Status
                    StatusStr = "Incomplete\t"
                    if (HSinceRequest>0 and ExpectedTAT>0):
                        if(HSinceRequest <= ExpectedTAT):
                            StatusStr = "TAT not elapsed\t"
                    outStr = outStr + StatusStr
                    
                    #Check for comments
                    CommStr = "\t"
                    if OverdueSet.Comments: 
                        CommStr = f"{' '.join(OverdueSet.Comments)}\t"
                    outStr = outStr + CommStr
                    
                    #Check for Notepad
                    NPadStr = "\t"
                    if SAWAY_Sample.hasNotepadEntries == True:
                        NPadStr = "%s\t" % ("|".join([str(x) for x in SAWAY_Sample.NotepadEntries]))
                    outStr = outStr + NPadStr
                
                    outStr = outStr + "\t\t\n"
                    SAWAYS_OUT.write(outStr)
    
            except AssertionError:
                continue
                
    logging.info(f"sendaways_scan(): Complete. Downloaded and exported data for {len(SAWAY_Counters)} overdue sendaway samples to file.")

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
        ul_file = open('S:/CS-Pathology/BIOCHEMISTRY/Z Personal/LKBecker/Code/Python/TelePath_Connect/PrivCheck.txt', 'r')
        userlist = ul_file.readlines()
        userlist = [x.trim() for x in userlist]
    
    logging.error("privilege_scan(): FUNCTION ISN'T DONE YET")
    raise NotImplementedError()
    
    #Enter administration area, needs privilege on TelePath user to access
    ProfX.send('PRIVS') #requires Level 1 access, do not write here.
    ProfX.read_data()
    assert ProfX.screen.Type == "PRIVS"

    for user in userlist:
        ProfX.send(user)
        ProfX.read_data() #Check access was successful

        #TODO: If querying an account that does not exist, the cursor goes to line... 6? (TODO:check it's line 6),to make a new account abort via ProfX.send('^')
        if ProfX.screen.cursorPosition[0]<20:
            logging.info(f"User '{user}' does not appear to exist on this system.")
            ProfX.send('^') #Return to main screen, ready for next
            continue
        
        #If that isn't the case, grab results and parse
        results = ProfX.screen.Lines[3:16] #TODO: Check exact lines
        results = [x for x in results if x.strip()]
        result_tbl = process_whitespaced_table(results, [0, 28]) #TODO: check this estimated col width works
        
        UserPrivs.append( f"{result_tbl[0][1]}\t{result_tbl[1][1]}\t{result_tbl[5][1]}\t\n" ) #TODO: check table

        ProfX.send('A') #Return to admin area, by Accepting the current settings without having changed a thing
    
    logging.info("privilege_scan(): Writing to output file.")
    outFile = f"S:/CS-Pathology/BIOCHEMISTRY/Z Personal/LKBecker/{timestamp(fileFormat=True)}_PrivScan.txt"
    with open(outFile, 'w') as out:
        for line in UserPrivs:
            out.write(line)
    logging.info("privilege_scan(): Complete.")

def mass_download(FilterSets:list=None):
    with open("S:/CS-Pathology/BIOCHEMISTRY/Z Personal/LKBecker/Code/Python/TelePath_Connect/ToRetrieve.txt", 'r') as DATA_IN:
        samples = DATA_IN.readlines()
    samples = [x.strip() for x in samples]
    samples = [tp_structs.Specimen(x) for x in samples]
    tp_structs.complete_specimen_data_in_obj(samples, FilterSets=FilterSets)
    
    outFile = f"S:/CS-Pathology/BIOCHEMISTRY/Z Personal/LKBecker/{timestamp(fileFormat=True)}_TPDownload.txt"
    with open(outFile, 'w') as DATA_OUT:
        DATA_OUT.write("SampleID\tSet\tResult(s)\n")
        for sample in samples:
            if sample.Sets:
                for _set in sample.Sets:
                    DATA_OUT.write(f"{sample.ID}\t{_set.Code}\t{_set.Results}\n") #TODO: Results parser (strip empties etc)
        DATA_OUT.write("End Of Line\n")


logging.basicConfig(filename='S:/CS-Pathology/BIOCHEMISTRY/Z Personal/LKBecker/Code/Python/TelePath_Connect/debug.log', filemode='w', level=logging.DEBUG, format=LOGFORMAT)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter(LOGFORMAT))
logging.getLogger().addHandler(console)

logging.info(f"Starting ProfX TelePath client, version {VERSION}. (c) Lorenz K. Becker, under GNU General Public License")

try:
    ProfX.connect()#TrainingSystem=True)
    #get_recent_results("A,21.0225526.L", 28)
    #aot_stub_buster()
    #sendaways_scan()
    mass_download(["CORT"])

except Exception as e: 
    logging.error(e)

finally:
    ProfX.disconnect()
    logging.info("System is now shut down. Have a nice day!")

"""
#if __name__ == "__main__":
    #parser = argparse.ArgumentParser(prog='ProfX', description='Connects to the TelePath LIMS system and extracts data')
    #parser.add_argument('-t', "-training", help='Connects to training system, not live system', action="store_true")
    #parser.add_argument('-saway', '-sendaways', help='retrieves and writes to file current outstanding sendaways, with specimen notepad and any Set notes', action="store_true")
    #parser.add_argument('-aot', '-aotBuster', help='Finds all outstanding samples with AOT (Add-on tests) and NA/'s the AOT entry', action="store_true")
    #
    #parser.add_argument('-dl', '-download', help='Loads', action="store_true")
    #parser.add_argument('-test', help='Specifies the test to download')
    #
    #args = parser.parse_args()
"""

# 21-05-04 TP accessible from ORC machine -> networks are accessible