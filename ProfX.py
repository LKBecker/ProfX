#GPL-3.0-or-later

import argparse
from collections import Counter
import config
import datastructs
import datetime
import getpass
import logging
import os.path
import telnet_ANSI
import npex
import re
import time
import utils

VERSION = "1.8.6"
LOGFORMAT = '%(asctime)s: %(name)-11s:%(levelname)-7s:%(message)s'
UseTrainingSystem = False

logging.basicConfig(filename='./debug.log', filemode='w', level=logging.DEBUG, format=LOGFORMAT)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter(LOGFORMAT))
logging.getLogger().addHandler(console)

telnet_ANSI.Connection.recognise_Screen_type = config.LOCALISATION.identify_screen #Overrides default function with that from localisation
TelePath = telnet_ANSI.Connection(Answerback=config.LOCALISATION.ANSWERBACK)


#TODO: port over gr lr eq
class tp_SpecimenID(datastructs.SampleID):
    CHECK_INT = 23
    CHECK_LETTERS = ['B', 'W', 'D', 'F', 'G', 'K', 'Q', 'V', 'Y', 'X', 'A', 'S', 'T', 'N', 'J', 'H', 'R', 'P', 'L', 'C', 'Z', 'M', 'E']

    def __init__(self, IDStr:str, useLocalisationValidationFun:bool=False):
        datastructs.SampleID.__init__(self, IDStr, useLocalisationValidationFun)
        #Prefix, Date Part, Number Part, Check Char
        if IDStr == None:
            raise Exception("tp_SpecimenID.__init__(): Received None where expecting IDstr.")
        self.Prefix     = "A,"
        self.Year       = None
        self.LabNumber  = None
        self.CheckChar  = None
        self.useLocalisationValidationFun = useLocalisationValidationFun
        IDStr = IDStr.upper()
        if IDStr[1]==",":
            self.Prefix = IDStr[:2]
            IDStr=IDStr[2:]
        IDStrSplit = IDStr.split(".")

        try:
            if len(IDStrSplit)==1:
                #logging.debug("SampleID(): Only one piece of data found. Assuming it's a 7-digit sample number from current year.")
                if len(IDStrSplit[0]) == 7:
                    self.LabNumber = int(IDStrSplit[0])
                else: raise ValueError("Parsing one-piece IDStr. No 7-digit sample id found - cannot estimate Sample ID unambiguously.")
        
            elif len(IDStrSplit)==2:
                #logging.debug("SampleID(): Two pieces of data found. Checking whether Year+ID or ID+CheckDigit...")

                if len(IDStrSplit[0]) == 2:
                    logging.debug("SampleID(): First entry is len 2, likely Year")
                    self.Year = int(IDStrSplit[0])
                elif len(IDStrSplit[0]) == 7:
                    logging.debug("SampleID(): First entry is len 7, likely Sample ID")
                    self.LabNumber = int(IDStrSplit[0])
                else:
                    raise ValueError(f"Cannot parse '{IDStrSplit[0]}' as Year or Sample ID.")

                if len(IDStrSplit[1]) == 1:
                    logging.debug("SampleID(): Last entry is len 1, likely Check Digit")
                    self.CheckChar = IDStrSplit[1]
                elif len(IDStrSplit[1]) == 7:
                    logging.debug("SampleID(): Last entry is len 7, likely Sample ID")
                    self.LabNumber = int(IDStrSplit[1])
                elif len(IDStrSplit[1]) == 8:
                    logging.debug("SampleID(): Last entry is len 8, likely Sample ID and check digit")
                    chkOrd = ord(IDStrSplit[1][-1])
                    if chkOrd >= 65 and chkOrd <= 90: #it's an ASCII capital letter between A and Z
                        self.CheckChar = IDStrSplit[1][-1]
                        self.LabNumber = int(IDStrSplit[1][:-1])
                else:
                    raise ValueError(f"Cannot parse '{IDStrSplit[1]}' as Sample ID or Check Digit")

            elif len(IDStrSplit)==3:
                #logging.debug("SampleID(): Three pieces of data found. Running all tests.")
                assert len(IDStrSplit[0]) == 2
                self.Year = int(IDStrSplit[0])

                assert len(IDStrSplit[1]) == 7
                self.LabNumber = int(IDStrSplit[1])

                assert len(IDStrSplit[2]) == 1
                self.CheckChar= IDStrSplit[2]

            if not self.Year:
                #logging.debug("SampleID(): Year not found, using current.")
                self.Year = int(datetime.datetime.now().strftime("%y"))
            if not self.CheckChar:
                #logging.debug("SampleID(): Check digit not present, estimating.")
                self.iterate_check_digit()

            if not self.LabNumber:
                raise ValueError("No ID Number assigned after parsing, sample cannot be identified.")

            #logging.debug(f"SampleID(): ID '{str(self)}' assembled. ID is: {['Not Valid', 'Valid'][self.validate()]}")

        except (AssertionError, ValueError):
            logging.debug(f"SampleID(): ID parsing failed for {IDStr}.")

    def __str__(self) -> str:
        if self.Override:
            return self._str
        return f"{self.Year}.{self.LabNumber:07}.{self.CheckChar}" #Without padding of ID Number to 10 positions, the validation will not work correctly

    def __repr__(self) -> str:
        return(f"SampleID(\"A,{self.Year}.{self.LabNumber}.{self.CheckChar}\")")

    """Function to check sample IDs, replicating TelePath's check digit algorithm  """
    def validate(self) -> bool:
        assert self.Year
        assert self.LabNumber
        assert self.CheckChar

        if self.useLocalisationValidationFun:
            return config.LOCALISATION.check_sample_id(str(self))

        sID = str(self).replace(".", "")
        if (len(sID)!=10):
            logging.error("SampleID '%s' should be 10 charactes long, is %d." %(sID, len(sID)))
            return False
        sID = sID[:-1] #Remove check char
        sID = [char for char in sID]          # split into characters - year, then ID
        checkTuples = zip(range(22,13,-1), map(lambda x: int(x), sID))      # Each number of the sample ID gets multiplied by 22..14, go to 13 to get full length
        checkTuples = list(map(lambda x: x[0]*x[1], checkTuples))           # Multiply.
        checkSum    = sum(checkTuples)                                      # Calculate Sum...
        checkDig    = tp_SpecimenID.CHECK_INT - (checkSum % tp_SpecimenID.CHECK_INT)  # Check digit is 23 - (sum %% 23)
        checkDig    = tp_SpecimenID.CHECK_LETTERS[checkDig-1]                      # Not from the full alphabet, and not in alphabet order, however. -1 to translate into python list index
        result      = self.CheckChar==checkDig
        return result

    def iterate_check_digit(self):
        for digit in tp_SpecimenID.CHECK_LETTERS:
            self.CheckChar = digit
            if self.validate(): 
                logging.debug(f"iterate_check_digit(): Check digit {digit} is valid for '{self.Year}.{self.LabNumber}.?'.")
                break


class tp_Specimen(datastructs.Specimen):
    def __init__(self, SpecimenID):
        datastructs.Specimen.__init__(self, SpecimenID)
        self._ID = tp_SpecimenID(SpecimenID)

    def get_chunks(self):
        logging.debug("tp_Specimen.get_chunks(): Returning to main menu.")
        return_to_main_menu()
        TelePath.send(config.LOCALISATION.SPECIMENENQUIRY)
        TelePath.read_data()
        TelePath.send(self.ID)
        TelePath.read_data()
        self.from_chunks(TelePath.ParsedANSI)

    def from_chunks(self, ANSIChunks:list):
        if len(ANSIChunks)==0:
            raise Exception("tp_Specimen.from_chunks(): No chunks to process in list ANSIChunks.")
        RetrieveChunks = [x for x in range(0, len(ANSIChunks)) if ANSIChunks[x].text == "Retrieving data..."]
        if RetrieveChunks:
            LastRetrieveIndex = max( RetrieveChunks )
        else:
            LastRetrieveIndex = 0
        DataChunks = sorted([x for x in ANSIChunks[LastRetrieveIndex+1:] if x.highlighted and x.deleteMode == 0 and x.line != 6])
        #get the LAST item that mentions the sample ID, which should be the TelePath refresh after "Retrieving data..."
        
        specID                  = TelePath.chunk_or_none(DataChunks, line = 3, column = 17)
        if specID:
            if self._ID != tp_SpecimenID(specID):
                logging.warning(f"WARNING: Mismatch between assigned specimen ID {self._ID} and retrieved ID {specID}!")
        
        self.PatientID          = TelePath.chunk_or_none(DataChunks, line = 8, column = 1)
        self.LName              = TelePath.chunk_or_none(DataChunks, line = 8, column = 21)
        self.FName              = TelePath.chunk_or_none(DataChunks, line = 8, column = 35)
        self.DOB                = TelePath.chunk_or_none(DataChunks, line = 8, column = 63)
        if self.DOB:
            if "-" in self.DOB: #Pre-2000 DOBs that could be confused for 1900 DOBs get a - (within 9 years of current year)
                _DOB = self.DOB.split("-")
                _DOB = [x.strip() for x in _DOB]
                try:
                    self.DOB = datetime.date(year="19"+_DOB[2], month=_DOB[1], day=_DOB[0])
                except:
                    self.DOB = f"{_DOB[0]}/{_DOB[1]}/19{_DOB[2]}"
            else:
                try:
                    self.DOB = datetime.datetime.strptime(self.DOB, "%d.%m.%y")
                    currentDatetime = datetime.datetime.now()
                    # TelePath doesn't use - all the time to distinguish centuries,so we need to do a sanity check.
                    if (self.DOB.year > currentDatetime.year):
                        self.DOB = self.DOB.replace(year = self.DOB.year - 100)

                    if (self.DOB.year == currentDatetime.year) and (self.DOB.month > currentDatetime.month):
                        self.DOB = self.DOB.replace(year = self.DOB.year - 100)
                except:
                    pass
    
        if self.PatientID:
            if not tp_Patient.Storage.has_item(self.PatientID):
                _Patient = tp_Patient(self.PatientID)
                _Patient.LName = self.LName
                _Patient.FName = self.FName
                _Patient.DOB = self.DOB
                tp_Patient.Storage.append(_Patient)
            else:
                _Patient = tp_Patient.Storage[self.PatientID]
            _Patient.add_sample(self)
        
        self.Collected          = tp_Specimen.parse_datetime_with_NotKnown(TelePath.chunk_or_none(DataChunks, line = 3, column = 67)) 
        self.Received           = tp_Specimen.parse_datetime_with_NotKnown(TelePath.chunk_or_none(DataChunks, line = 4, column = 67))
        self.Type               = TelePath.chunk_or_none(DataChunks, line = 5, column = 15)
        self.Location           = TelePath.chunk_or_none(DataChunks, line = 9, column = 18)
        self.Requestor          = TelePath.chunk_or_none(DataChunks, line = 9, column = 55)
        self.Comment            = TelePath.chunk_or_none(DataChunks, line = 6, column = 16)
        self.ReportComment      = TelePath.chunk_or_none(DataChunks, line = 4, column = 16)
        
        #TelePath only highlights the specimen notepad option if entries exist; else it's part of a single chunk of options, none highlighted. So...
        if [x for x in ANSIChunks if (x.text=="spc N'pad" and x.highlighted)]: 
            self.hasNotepadEntries = True

        PossWaitMsg = [x for x in ANSIChunks if x.line==23 and x.column == 1]
        if PossWaitMsg:
            PossWaitMsg = PossWaitMsg[0]
            if PossWaitMsg.text == "Authorising in foreground - please wait":
                return

        TestStart = [x for x in ANSIChunks if x.text == "Sets Requested :-"]
        if TestStart:
            TestStart = ANSIChunks.index(TestStart[0])
            for i in range(TestStart+3, len(ANSIChunks), 4):
                if (ANSIChunks[i]).text == '' or (ANSIChunks[i+3]).text != '': break
                index   = int(ANSIChunks[i].text.strip().replace(")", ""))
                test    = ANSIChunks[i+1].text.strip()
                status  = ANSIChunks[i+2].text.strip().lstrip(".")
                if self.Sets:
                    _tmp = [x for x in range(0, len(self.Sets)) if self.Sets[x].Code == test]
                    if _tmp:
                        self.Sets[_tmp[0]].Index  = index
                        self.Sets[_tmp[0]].Status = status
                        continue
                self.Sets.append(tp_TestSet(Sample=self.ID, SetIndex=index, SetCode=test, Status=status))
        else:
            logging.debug(f"Cannot find 'Sets requested' for sample {self.ID}. Check ANSIChunks, please.")
            logging.debug(ANSIChunks)
           
    def validate_ID(self) -> bool: return self._ID.validate()


class tp_Patient(datastructs.Patient):
    def __init__(self, ID):
        self.ID = ID
        self.Samples = []
        self.FName = None
        self.LName = None
        self.DOB = None
        self.Sex = None
        self.Gender = None
        self.NHSNumber = None
        if not tp_Patient.Storage.has_item(self.ID):
            tp_Patient.Storage[self.ID] = self
        else:
            other = tp_Patient.Storage[self.ID]
            self.cross_complete(other) 
            tp_Patient.Storage[self.ID] = self #Should overwrite (well, re-link) duplicate object with existing one?
            del(other)


    def get_n_recent_samples(self, Set=None, nMaxSamples:int=10, retrieveContents:bool=False):
        def extract_specimens(samples):
            for sample in samples: #Max seven per page
                _tmpSpecimen = tp_Specimen(sample[2]) #Should auto-append to self.Samples?
                self.add_sample(_tmpSpecimen)
                nSpecimens = len(self.Samples)
                logging.debug(f"get_n_recent_samples(): Patient {self.ID} now contains {nSpecimens} specimens.")
                if nSpecimens == nMaxSamples+1: #len() is index 0!
                    return False
            return True

        if not self.ID or not self.LName:
            logging.error(f"Either Patient ID ({self.ID}) or First Name ({self.LName}) not sufficient to search for samples. Aborting.")
            return False
        return_to_main_menu()
        TelePath.send(config.LOCALISATION.PATIENTENQUIRY)
        TelePath.read_data()
        TelePath.send(self.ID)
        TelePath.read_data()
        if not TelePath.hasErrors:
            TelePath.send(self.LName[:2])
            TelePath.read_data()
            if TelePath.hasErrors:
                errMsg = TelePath.Errors[0]
                errMsg = errMsg[len('"No match - Name on file is'):]
                errMsg = errMsg[:errMsg.find('"')]
                self.LName = errMsg
                TelePath.send(self.FName[:1])
                TelePath.read_data()
            TelePath.send("S") #Spec select
            TelePath.read_data()
            TelePath.send("U") #Unknown specimen
            TelePath.read_data()
            TelePath.send('', readEcho=False) #EARLIEST
            TelePath.read_data() 
            TelePath.send('', readEcho=False) #LATEST
            TelePath.read_data()
            if not Set:
                TelePath.send('', readEcho=False) #ALL
            else:
                TelePath.send(Set) #Send desired set
            TelePath.read_data() #Get specimen table
            if TelePath.hasErrors:
                #TODO: Crashes sister sample retrieval. Why?
                return
            _continueLoop = True
            samples = utils.process_whitespaced_table(TelePath.Lines[14:-2], utils.extract_column_widths(TelePath.Lines[12]))
            if not extract_specimens(samples):
                _continueLoop = False
            while TelePath.DefaultOption == "N" and _continueLoop:
                TelePath.send('N')
                TelePath.read_data()
                samples = utils.process_whitespaced_table(TelePath.Lines[14:-2], utils.extract_column_widths(TelePath.Lines[12]))
                if not extract_specimens(samples):
                    break
            
        #TODO: else, do search via Name and DOB?
        else:
            logging.error(f"Could not retrieve data for patient {self.ID}: {';'.join(TelePath.Errors)}")
        TelePath.send('Q')
        TelePath.read_data()
        TelePath.send('')
        TelePath.read_data()
        if retrieveContents:
            tmpSets = None
            if Set:
                tmpSets = [Set]
            complete_specimen_data_in_obj(self.Samples, GetNotepad=True, GetComments=True, FillSets=True, FilterSets=tmpSets)

        logging.info("tp_Specimen(s) found.")


class tp_TestSet(datastructs.TestSet):
    def __init__(self,  Sample:str, SetIndex:str, SetCode:str, AuthedOn:str=None, AuthedBy:str=None, Status:str=None, 
                 Results:list=None, Comments:list=None, RequestedOn:str=None, TimeOverdue:str=None, Override:bool=False):
        super().__init__(Sample, SetIndex, SetCode, AuthedOn, AuthedBy, Status, Results, Comments, RequestedOn, TimeOverdue, Override)
        self.History = []

    @property
    def is_overdue(self): return self.Overdue.total_seconds() > 0

    def __repr__(self): 
        return f"tp_TestSet(ID={str(self.Sample)}, SetIndex={self.Index}, SetCode={self.Code}, AuthedOn={self.AuthedOn}, AuthedBy={self.AuthedBy}, Status={self.Status}, ...)"
    
    def __str__(self): 
        return f"[{self.Sample}, #{self.Index}: {self.Code} ({self.Status})] - {len(self.Results)} SetResults, {len(self.Comments)} Comments. Authorized {self.AuthedOn} by {self.AuthedBy}."
 

class tp_HistoryEntry():
    def __init__(self, Sample, TestSet, DateTime="", Event="", User=""):
        self.SampleID = Sample
        self.TestSet = TestSet
        self.DateTime = DateTime
        self.Event = Event
        self.User = User

    def fromChunks(self):
        pass

    def __repr__(self): 
        return f"tp_HistoryEntry(Sample={str(self.SampleID)}, TestSet={self.TestSet}, DateTime={self.DateTime}, Event={self.Event}, User={self.User})"
    
    def __str__(self): 
        return f"Sample {str(self.SampleID)}, Set {self.TestSet}, {self.DateTime}: {self.Event} {self.User}"

    
tp_Patient.Storage = datastructs.SingleTypeStorageContainer(tp_Patient)

""" Locates samples with AOT beyond TAT (...i.e. any), and marks the AOT as 'NA' if insert_NA_result is set to True """
def aot_stub_buster(insert_NA_result:bool=False, get_creators:bool=False) -> None:
    logging.debug(f"aot_stub_buster(): Start up. Gathering history: {get_creators}. NAing entries: {insert_NA_result}.")
    AOTSamples = get_overdue_sets("AUTO", "AOT")
    AOTStubs = Counter()
    
    if (insert_NA_result == False and get_creators == False):
        logging.info(f"aot_stub_buster(): There are {len(AOTSamples)} AOTs to process.")
        return

    return_to_main_menu()
    TelePath.send(config.LOCALISATION.SPECIMENENQUIRY, quiet=True)         # Go into Specimen Inquiry
    TelePath.read_data()
    for AOTSample in AOTSamples: #TODO: issue here; loop likes to get same sample X times...
        TelePath.send(AOTSample.ID, quiet=True, maxwait_ms=2000)  #Open record
        TelePath.read_data()
        AOTSample.from_chunks(TelePath.ParsedANSI)
        TargetIndex = AOTSample.get_set_index("AOT")
        
        if TargetIndex == -1:
            logging.error(f"Cannot locate AOT set for patient {AOTSample.ID}. Please check code and/or retry.")
            TelePath.send(config.LOCALISATION.EMPTYSTR) #Exit record
            continue
        if get_creators == True:
            #logging.info(f"aot_stub_buster(): Retrieving History for set [AOT] of sample [{AOTSample.ID}]")
            #TODO: Seems like a source of errors when there is no history - check route back in case of error is similar 
            #Or, brute force: go back to main menu and back to SENQ.
            TelePath.send(config.LOCALISATION.SETHISTORY+str(TargetIndex), quiet=True)  #Attempt to open test history, can cause error if none exists
            TelePath.read_data()
            if not TelePath.hasErrors:
                #locate line with 'Set requested by: '
                for line in TelePath.Lines[6].split("\r\n"):
                    if line.find("Set requested by: ") != -1:
                        user = line[ line.find("Set requested by: ")+len("Set requested by: "): ].strip()
                        creationDT  = line[0:16].strip()
                        logging.info(f"aot_stub_buster(): Open set [AOT] of sample [{AOTSample.ID}] was created by [{user}] at {creationDT}.")
                        AOTStubs[ user ] += 1
                TelePath.send(config.LOCALISATION.QUIT)
                TelePath.read_data()
            else:
                logging.info(f"aot_stub_buster(): Could not retrieve history for [AOT] of sample [{AOTSample.ID}].")
        
        if(insert_NA_result == True):
            logging.info(f"aot_stub_buster(): Closing Set [AOT] (#{TargetIndex}) for Sample [{AOTSample.ID}]...")
            TelePath.send(config.LOCALISATION.UPDATE_SET_RESULT+str(TargetIndex), quiet=True)  #Open relevant test record
            TelePath.read_data()
            #TODO: Check screen type!
            TelePath.send(config.LOCALISATION.NA)                              #Fill Record
            TelePath.read_data()
            TelePath.send(config.LOCALISATION.RELEASE, quiet=True)                   #Release NA Result
            #TODO: Check if you get the comment of "Do you want to retain ranges"! Doesn't happen for AOT but...
            TelePath.read_data()
            if (TelePath.ScreenType == "DirectResultEntry"):
                logging.debug("aot_stub_buster(): Using Direct result Entry screen shunt...")
                TelePath.send(config.LOCALISATION.EMPTYSTR)
                TelePath.read_data()
        TelePath.send(config.LOCALISATION.EMPTYSTR, quiet=True)                    #Close record
        time.sleep(0.25)
    #for AOTSample

    if get_creators==True:
        with open(f'./AOTCreators_{utils.timestamp(fileFormat=True)}.log', 'w') as AOTData:
            AOTData.write(f"AOT sets, created {utils.timestamp()}\n")
            AOTData.write("User\tNumber of AOT Stubs\n")
            for key, value in AOTStubs.most_common():
                AOTData.write(f"{key}\t{value}\n")
    logging.debug("aot_stub_buster(): Complete.")

""" Examines and sums up the number of sets awaiting authorisation for each NPCL queue. """
def auth_queue_size(QueueFilter:list=None, DetailLevel:int=0, writeToFile=True):
    WYTH_AUTH_HEADER_SIZES = [ 4,13,40,45,53]
    WYTH_NPCL_HEADER_SIZES = [12,21,52,61]

    def processTwoColumnLines(lines):
        #Limited to a max of 99 lists lol
        cleanLists = []
        for line in lines:
            line = [x for x in line if x]
            cleanLists.append((line[0][:2].strip(), line[1], line[2]))
            if len(line)>3:
                cleanLists.append((line[3][:2].strip(), line[4], line[5]))
        return cleanLists

    return_to_main_menu()
    ts = datetime.datetime.now()
    NPCLQueues = []

    logging.info("auth_queue_size(): Retrieving data...")
    TelePath.send(config.LOCALISATION.AUTHORISATION)
    TelePath.read_data()
    AuthQueues = TelePath.Lines[4].split("\r\n")[1:]
    AuthQueues = utils.process_whitespaced_table(AuthQueues, WYTH_AUTH_HEADER_SIZES)
    #AuthQueues = [item for sublist in AuthQueues for item in sublist]
    AuthQueues = processTwoColumnLines(AuthQueues)
    for AuthQueue in AuthQueues:
        if TelePath.ScreenType == "MainMenu":
            #Received error?
            TelePath.send(config.LOCALISATION.AUTHORISATION)
            TelePath.read_data()
        TelePath.send(AuthQueue[0]) #Received PowerTerm tmessage, args '"Number out of range" title "Authorisation list processing" error'
        time.sleep(0.2)
        TelePath.read_data()
        NPCLLists = [x for x in TelePath.Lines[5:-4] if x]
        NPCLLists = utils.process_whitespaced_table(NPCLLists, WYTH_NPCL_HEADER_SIZES)
        _subQueue = []
        for line in NPCLLists:
            if len(line)%2 != 0: 
                raise Exception("Number of items should be an even number!")
            line = [x for x in line if x]
            _subQueue.append((line[0], line[1]))
            if len(line)>2:
                _subQueue.append((line[2], line[3]))
        for subQueue in _subQueue:
            NPCLQueues.append( (AuthQueue[1], AuthQueue[2], subQueue[0], int(subQueue[1])) )
        TelePath.send('Q')
        time.sleep(0.2)
        TelePath.read_data()
    QueueSize = sum(item[3] for item in NPCLQueues)
    logging.info(f"auth_queue_size(): {QueueSize} samples are awaiting authorisation at {ts}.")
    
    outFile = "./AuthQueues.txt"

    if writeToFile:
        addHeader=False
        if not os.path.exists(outFile):
            addHeader = True
        DATA_OUT = open(outFile, 'a')
        if addHeader:
            DATA_OUT.write("DateTime\tHead Queue\tSubqueue\tN Samples\n")
        for subQueue in NPCLQueues:          
            DATA_OUT.write(f"{ts.strftime('%Y-%m-%d %H:%M:%S')}\t{subQueue[1]}\t{subQueue[2]}\t{subQueue[3]}\n")
        DATA_OUT.flush()
        DATA_OUT.close()
    
    if DetailLevel>0:
        AuthQueueTable = utils.generatePrettyTable(NPCLQueues, Headers=["Code", "Queue Name", "Sub-Queue", "Sets to authorise"])
        for x in AuthQueueTable: 
            logging.info(x)

""" Basic interface, not yet tested since I'm the only user """
def BasicInterface():
    #TODO: Test and improve
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
        if UserInput == re.sub(r'[\W0-9]+', '', UserInput):
            return True
        return False

    def is_yesOrNo(UserInput:str, lowerBound:None, upperBound:None):
        if (len(UserInput)!=1): return False
        UserInput = UserInput.upper()
        if UserInput == "Y" or UserInput == "N":
            return True
        return False

    def is_sample(UserInput:str, lowerBound:None, upperBound:None):
        _sample = tp_SpecimenID(UserInput)
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
    choice = get_user_input(is_numeric, "Please select a number from 1 to 8: ", "Please select from the above options: ", 1, 8)

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
            print("""   Would you like to retrieve a list of these samples? """)
            choice3 = get_user_input(is_yesOrNo, "Please answer either Y or N", "Y/N: ", None, None)
            if choice3 == "Y":
                choice2 = "2"

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
        2   Download the samples listed in ToRetrieve.txt
        """)
        choice2 = get_user_input(is_numeric, "Please select a number from 1 to 2.", "Please select from the above options: ", 1, 2)
        if choice2 == "1":
            SetToDL = get_user_input("For which set do you want to retreive samples? ", is_alphanumeric, "Please use only A-Za-z and 0-9.")
            NSets   = get_user_input("How many samples do you want to retrieve at most? ", is_numeric, "Please enter a number between 1 and 100.", 1, 100)
            SampleList = get_recent_samples_of_set_type(SetToDL, nMaxSamples=int(NSets))
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
        print(get_recent_samples_of_set_type(SetToDL, nMaxSamples=int(NSets)))
        
    if choice=="6":
        print("""
    Patient history
        """)
        SampleToDL = get_user_input(is_sample, "Please enter a valid sample ID.", "Which sample do you wish to generate a patient history from? ")
        get_recent_history(SampleToDL, nMaxSamples=15)

    input("Press any key to exit...")

""" command-line interface, also not yet tested """
def CLI():
    parser = argparse.ArgumentParser(prog='TelePath', description='Connects to a TelePath LIMS system and extracts data.')
    parser.add_argument('-sample', help="The ID of the sample to process")
    parser.add_argument('-t', "-training", help='Connects to training system, not live system', action="store_true")
    parser.add_argument('-saway', '-sendaways', help='Retrieves all outstanding sendaways tests (excluding ACOV2/COVABS),'+
                                                    ' with specimen notepad and any Set notes', action="store_true")
    parser.add_argument('-aot', '-aotBuster', help="Finds all outstanding samples with AOT (Add-on tests). "+
                                                    "Can also retrieve the creator of such stubs, and can NA the AOT entry automatically", action="store_true")
    parser.add_argument('-outfile', '-o', help='Filename for any output data.')
    parser.add_argument('-h', '-history', help='Retrieves recent test results for the patient associated'+
                                               'with a sample, and displays or outputs them.', action="store_true")
    parser.add_argument('-dl', '-download', help='Retrieves results for a list of samples.', action="store_true")
    parser.add_argument('-test', help='Specifies the test to download')
    parser.add_argument('-user', help='Specifies the user to access the system as. Overrides config.py. Will require user to enter their password.')

    args = parser.parse_args()
    #TODO: do the thing
    pass

""" Retrieves tp_Specimen data (demographics, etc) for any tp_Specimen object in the list SampleObjs.
    Option GetFurther also retrieves Clinical Details and NHS Number.
    Can also retreive Sets run, Set result(s), Set comments, and tp_Specimen Notepad data.
    If FillSets is true, loads all available data, else, only attempts to complete TestSet obj present in the tp_Specimen"""
def complete_specimen_data_in_obj(SampleObjs=None, GetNotepad:bool=False, GetComments:bool=False, GetFurther:bool=False, 
                                    ValidateSamples:bool=True, FillSets:bool=False, FilterSets:list=None, GetHistory:bool=False):
    if type(SampleObjs)==tp_Specimen:
        SampleObjs = [SampleObjs]

    def extract_set_comments(SetToGet):
        TelePath.send('S', quiet=True)    # enter Set comments
        while (TelePath.DefaultOption != 'B'):
            TelePath.read_data()
            CommStartLine = -1  # How many lines results take up varies from set to set!
            PossCommStartLines = range(5, TelePath.screenLength-1) #Comments start on the first line after line 5 that has *only* highlighted items in it.
            for line in PossCommStartLines:
                currentANSIs = [x for x in TelePath.ParsedANSI if x.line == line and x.deleteMode == 0]
                areHighlighted = [x.highlighted for x in currentANSIs]
                if all(areHighlighted): #All elements on this line after line 5 are highlighted
                    CommStartLine = line    # thus, it is the line we want
                    break                   # and since we only need the first line that fulfills these criteria, no need to loop further
            if (CommStartLine != -1): 
                SetToGet.Comments = []
                for commentline in TelePath.Lines[CommStartLine:-2]:
                    if commentline.strip():
                        SetToGet.Comments.append(commentline.strip()) # Let's just slam it in there
            TelePath.send(TelePath.DefaultOption, quiet=True) 
        TelePath.read_data()

    def extract_results(SetToGet, SampleCollectionTime):
        logging.debug("complete_specimen_data_in_obj(): extract_results(): Downloading results for set %s" % SetToGet.Code)
        SetHeaderWidths = utils.extract_column_widths(TelePath.Lines[6])
        SetResultData = utils.process_whitespaced_table(TelePath.Lines[7:-2], SetHeaderWidths)
    
        
        SetAuthUser = "[Not Authorized]"
        SetAuthTime = "[Not Authorized]"
        SetRepTime = "[Not Reported]"

        SetIsAuthed = True #TODO Set to True for some testing, should technically start False (but works due to defensive code below)
        if SetToGet.Status: #TODO: All Statuses are None - where are they retrieved?
            if SetToGet.Status[0]=="R":
                SetIsAuthed = True

        if SetIsAuthed:
            AuthData = [x for x in TelePath.ParsedANSI if x.line == 21 and x.highlighted == True][0]
            if AuthData:
                if AuthData.text.strip() == "WARNING :- these results are unauthorised":
                    SetIsAuthed = False
        
        if SetIsAuthed:
            SetAuthData = [x for x in TelePath.ParsedANSI if x.line == 4 and x.highlighted == True]
            SetAuthData.sort()
            SetAuthUser = SetAuthData[1].text
            SetAuthTime = SetAuthData[0].text
            SetRepData      = [x for x in TelePath.ParsedANSI if x.line == 5 and x.highlighted == True]
            if SetRepData:
                    SetRepTime = SetRepData[0].text
        
        for ResultLine in SetResultData:
            Analyte = ResultLine[0]
            Flag=None
            if Analyte[-1]=='+' or Analyte[-1]=='-':
                Analyte = ResultLine[0][:-1].strip()
                Flag = ResultLine[0][-1]
            ResObj = datastructs.SetResult(Analyte=Analyte, Value=ResultLine[1], Units=ResultLine[2], SampleTaken=SampleCollectionTime, ReportedOn=SetRepTime, AuthDateTime=SetAuthTime, Flags=Flag)
            SetToGet.Results.append(ResObj)
        
        SetToGet.AuthedOn = SetAuthTime
        SetToGet.AuthedBy = SetAuthUser

    def get_history(Set:tp_TestSet):
        TP_HISTORY_TIMESTAMP = "%d-%b-%y %H:%M"
        TP_HISTORY_TS_LEN = len(TP_HISTORY_TIMESTAMP)
        multiLineEvents = ["Free text entered/edited by:", "Results entered/edited by:"]

        def extract_history_page():
            historyLines = TelePath.Lines[6].split("\r\n")
            historyLines =  historyLines[1:]
            historyLines = [ x for x in historyLines if x ]

            index = 0
            while index < len(historyLines):
                line = historyLines[index]
                dateTime = line[:TP_HISTORY_TS_LEN+1]
                colIndex = line.find(":", TP_HISTORY_TS_LEN, len(line))
                if colIndex != -1:
                    dateTime = datetime.datetime.strptime(dateTime, TP_HISTORY_TIMESTAMP)
                    event = line[TP_HISTORY_TS_LEN+1:colIndex+1].strip()
                    user  = line[colIndex+1:].strip()

                    if event in multiLineEvents:
                        moreLines = 0
                        dateTimeMatch = False

                        while (dateTimeMatch == False) and (index+moreLines < len(historyLines)):
                            moreLines = moreLines + 1
                            try:
                                datetime.datetime.strptime(historyLines[index+moreLines][:len(TP_HISTORY_TIMESTAMP)+1], TP_HISTORY_TIMESTAMP)
                                dateTimeMatch = True
                            except:
                                continue
                            
                        event = event + ";".join(historyLines[index+1:index+moreLines])
                        index = index + moreLines 

                    Set.History.append( tp_HistoryEntry(Set.Sample, Set.Code, dateTime, event, user) )
                
                else:
                    logging.debug(f"Warning: Could not parse history event [{line}].")
                
                index = index + 1 

        assert(TelePath.ScreenType == "SENQ")
        TelePath.send('H' + str(Set.Index))
        TelePath.read_data()
        extract_history_page()
        
        last_line = TelePath.Lines[6]
        while TelePath.DefaultOption != 'Q':
            TelePath.send('+')
            TelePath.read_data()
            extract_history_page()
            if TelePath.Lines[6] == last_line: #Default option does not change to Q if there's exactly enough entries to fill a page.
                break
            last_line = TelePath.Lines[6]
        
        TelePath.send(config.LOCALISATION.CANCEL_ACTION)
        TelePath.read_data()
        assert(TelePath.ScreenType == "SENQ")

    def get_notepad_entries(Sample:tp_Specimen):
        assert(TelePath.ScreenType == "SENQ")
        if(Sample.hasNotepadEntries == True):
            TelePath.send('N', quiet=True)  #Open tp_Specimen Notepad for this Sample
            TelePath.read_data()
            if (TelePath.hasErrors == True):
                logging.warning("complete_specimen_data_in_obj(): Received error message when accessing specimen notepad for sample %s: %s" % (Sample, ";".join(TelePath.Errors)))
                TelePath.send("", quiet=True)
                tp_SpecimenNotepadEntries = [datastructs.SpecimenNotepadEntry(ID=Sample.ID, Author="[python]", Text="[Access blocked by other users, please retry later]", Index="0", Authored="00:00 1.1.70")]
            
            else:
                tp_SpecimenNotepadEntries = [x for x in TelePath.ParsedANSI if x.line >= 8 and x.line <= 21 and x.deleteMode == 0]
                SNObjects = []
                for entryLine in tp_SpecimenNotepadEntries:
                    _entryData = entryLine.text.split(" ")
                    _entryData = [x for x in _entryData if x != ""]
                    if len(_entryData) > 5:
                        #TODO: this never yet happened, ensure it works
                        logging.debug("There are likely two specimen notepad entries in line '%s'" % entryLine)
                        SNObjects.append(datastructs.SpecimenNotepadEntry(_entryData[7], _entryData[6], "", _entryData[5].strip(")"), _entryData[8]+" "+_entryData[9])) #THEORETICAL - not tested yet
                    SNObjects.append(datastructs.SpecimenNotepadEntry(_entryData[2], _entryData[1], "", _entryData[0].strip(")"), _entryData[3]+" "+_entryData[4]))
                
                for SNEntry in SNObjects:
                    TelePath.send(SNEntry.Index, quiet=True)  # Open the entry 
                    TelePath.read_data()           # Receive data
                    #TODO: What if more than one page of text?
                    SNText = list(map(lambda x: x.text, TelePath.ParsedANSI[2:-2]))
                    SNEntry.Text = ";".join(SNText)# Copy down the text and put it into the instance
                    TelePath.send("B", quiet=True)            # Go BACK, not default option QUIT 
                    time.sleep(0.1)
                    TelePath.read_data()           # Receive data
                
                Sample.NotepadEntries = SNObjects
                TelePath.send("Q", quiet=True)                # QUIT specimen notepad
                TelePath.read_data()               # Receive data
                assert(TelePath.ScreenType == "SENQ")


    if len(SampleObjs)==0: 
        logging.warning("Could not find any Samples to process. Exiting program.")
        return

    return_to_main_menu()
    TelePath.send(config.LOCALISATION.SPECIMENENQUIRY, quiet=True) #Move to specimen inquiry 
    TelePath.read_data()
    SampleCounter = 0
    nSamples = len(SampleObjs)
    ReportInterval = max(min(50, round(nSamples*0.1)), 1)
    logging.debug(f"complete_specimen_data_in_obj(): Beginning retrieval...")
    for Sample in SampleObjs: 
        if Sample.ID[:1] == "19":
            logging.info("complete_specimen_data_in_obj(): Avoiding specimen(s) from 2019, which can induce a crash on access.")    
            continue
        logging.debug(f"complete_specimen_data_in_obj(): Retrieving specimen [{Sample.ID}]...")
        if (ValidateSamples and not Sample.validate_ID()):
            logging.warning("complete_specimen_data_in_obj(): Sample ID '%s' does not appear to be valid. Skipping to next..." % Sample.ID)
            continue
        TelePath.send(Sample.ID, quiet=True)
        TelePath.read_data(max_wait=300)   # And read screen.
        if (TelePath.hasErrors == True):
            # Usually the error is "No such specimen"; the error shouldn't be 'incorrect format' if we ran validate_ID().
            logging.warning(f"complete_specimen_data_in_obj(): '{';'.join(TelePath.Errors)}'")
        else:
            _SetCodes = Sample.SetCodes #...blank list? TODO:check
            Sample.from_chunks(TelePath.ParsedANSI)  #Parse sample data, including patient details, sets, and assigning tp_Specimen.Collected DT.
            if FillSets == False:
                Sample.Sets = [x for x in Sample.Sets if x.Code in _SetCodes]

            if (GetNotepad == True):
                get_notepad_entries(Sample)
            
            if (GetFurther == True):
                #Retrieve NHS Number and Clinical Details, which are not visible on main screen...
                TelePath.send("F", quiet=True)
                TelePath.read_data()
                TelePath.send("1", quiet=True)
                TelePath.read_data()
                Sample.NHSNumber = TelePath.chunk_or_none(TelePath.ParsedANSI, line=17, column=37, highlighted=True)
                
                TelePath.send("4", quiet=True)
                TelePath.read_data()   # And read screen.
                Details = TelePath.Lines[11].strip()
                if Details:
                    Sample.ClinDetails = Details
                
                TelePath.send("Q", quiet=True)
                TelePath.read_data()

            if (Sample.Sets): 
                for SetToGet in Sample.Sets:
                    if FilterSets:
                        if SetToGet.Code not in FilterSets:
                            logging.debug(f"Set {SetToGet.Code} does not seem to contained in {FilterSets}")
                            continue
                    if SetToGet.Index == -1:
                        logging.error("complete_specimen_data_in_obj(): Sample %s has no Set '%s'. Skipping..." % (Sample, SetToGet))
                        continue

                    if GetHistory == True:
                        get_history(SetToGet)

                    TelePath.send(str(SetToGet.Index), quiet=True)
                    time.sleep(0.1)
                    TelePath.read_data()

                    if (TelePath.ScreenType == "SENQ_DisplayResults"):
                        extract_results(SetToGet, Sample.Collected)
                        if ("Set com" in TelePath.Options and GetComments==True):
                            extract_set_comments(SetToGet)

                    elif (TelePath.ScreenType == "SENQ_Screen3_FurtherSetInfo"): 
                        SetToGet.AuthedOn = "[Not Authorized]"
                        SetToGet.AuthedBy = "[Not Authorized]"
                        SetToGet.Results = []
                        if ("Results" in TelePath.Options):
                            TelePath.send('R', quiet=True)
                            TelePath.read_data()
                            extract_results(SetToGet, Sample.Collected)
                            if ("Set com" in TelePath.Options and GetComments==True):
                                extract_set_comments(SetToGet)
                            TelePath.send('B', quiet=True)
                            TelePath.read_data()

                    else: logging.error("complete_specimen_data_in_obj(): cannot handle screen type '%s'" % TelePath.ScreenType)

                    TelePath.send('B', quiet=True)        # Back to tp_Specimen overview - Without the sleep, bottom half of the SENQ screen might be caught still being transmitted.
                    TelePath.read_data()
                # for SetToGet in Sets
            # if (GetSets)
            TelePath.send("", quiet=True)                 # Exit specimen
            TelePath.read_data()              # Receive clean tp_Specimen Enquiry screen
        # if/else TelePath.hasError()
        SampleCounter += 1
        Pct = (SampleCounter / nSamples) * 100
        if(SampleCounter % ReportInterval == 0): 
            logging.info(f"complete_specimen_data_in_obj(): {SampleCounter:03} of {nSamples} samples ({Pct:.2f}%) complete")
    #for Sample in Samples
    logging.debug("complete_specimen_data_in_obj(): All downloads complete.")

""" Connects to a TelePath instance, and logs in the user, querying for Username and Password if none are supplied. """
def connect(TrainingSystem=False):  
    if config.LOCALISATION.LIMS_USER:
        if config.LOCALISATION.LIMS_USER != "YOUR USERNAME HERE": 
            user = config.LOCALISATION.LIMS_USER
        else: 
            user = input("Enter your TelePath username (and press Enter): ")
    else:
        user = input("Enter your TelePath username (and press Enter; it won't be shown!): ")
    user = user.upper()

    if config.LOCALISATION.LIMS_PW:
        if config.LOCALISATION.LIMS_PW == "YOUR PASSWORD HERE":
            pw = getpass.getpass()
        else:
            pw = config.LOCALISATION.LIMS_PW     
    else:
        pw = getpass.getpass()

    TelePath.connect(IP=config.LOCALISATION.LIMS_IP, Port=config.LOCALISATION.LIMS_PORT, Answerback=config.LOCALISATION.ANSWERBACK,
                    IBMUser=config.LOCALISATION.IBM_USER, Userprompt=None, PWPrompt=b"Password :", User=user, PW=pw)      
    
    while (TelePath.ScreenType != "MainMenu"):
        TelePath.read_data()
        if (TelePath.ScreenType == "ChangePassword"):
            raise Exception("TelePath demands a password change. Please log in using your regular client, change your password, then change the config file for this utility.")
        logging.debug(f"connect(): Screen type is {TelePath.ScreenType}, first lines are {TelePath.Lines[0:2]}")
        time.sleep(1) # Wait for ON-CALL? to go away
    logging.info("connect() Connection established. Login successful.")

""" Locates samples with AOT beyond TAT (...i.e. any), and marks the AOT as 'NA' if insert_NA_result is set to True """
def covid_stub_buster(insert_NA_result:bool=False) -> None:
    logging.debug(f"aot_stub_buster(): Start up. NAing entries: {insert_NA_result}.")
    TargetSets = ["COVABS", "ACOV2", "ACOV2S"]
    COVIDSamples = get_overdue_sets("AWAY", SetCode=TargetSets)
    if (insert_NA_result == False):
        logging.info(f"covid_stub_buster(): There are {len(COVIDSamples)} AOTs to process.")
        return

    return_to_main_menu()
    TelePath.send(config.LOCALISATION.SPECIMENENQUIRY, quiet=True)         # Go into Specimen Inquiry
    TelePath.read_data()

    for covSample in COVIDSamples:
        TelePath.send(covSample.ID, quiet=True, maxwait_ms=2000)  #Open specimen record
        TelePath.read_data()
        covSample.from_chunks(TelePath.ParsedANSI) # check which sets this specimen has, and at which indices
        
        for subSet in TargetSets:
            TargetIndex = covSample.get_set_index(subSet)
            if TargetIndex == -1:
                #The sample does not have an entry for this Set
                continue
            
            logging.info(f"covid_stub_buster(): Closing Set [{subSet}] (#{TargetIndex}) for Sample [{covSample.ID}]...")
            TelePath.send(config.LOCALISATION.UPDATE_SET_RESULT+str(TargetIndex), quiet=True)  #Open relevant test record
            TelePath.read_data()
            #TODO: Check screen type!
            TelePath.send(config.LOCALISATION.NA)       #Fill Record
            if subSet == "COVABS":
                TelePath.send(config.LOCALISATION.NA)   #One more...
                TelePath.send(config.LOCALISATION.NA)   #Two more.
                TelePath.send('')
            TelePath.read_data()
            TelePath.send(config.LOCALISATION.RELEASE, quiet=True)  #Release results
            #TODO: Check if you get the comment of "Do you want to retain ranges"! Doesn't happen for AOT but...
            TelePath.read_data()
            if TelePath.Lines[-1]=="Do you want to retain ranges for":
                TelePath.send('Y', readEcho=False)
                TelePath.read_data()

            if (TelePath.ScreenType == "DirectResultEntry"):
                logging.debug("covid_stub_buster(): Using Direct result Entry screen shunt...")
                TelePath.send(config.LOCALISATION.EMPTYSTR)
                TelePath.read_data()
        TelePath.send(config.LOCALISATION.EMPTYSTR, quiet=True)                    #Close specimen record once all sets are processed
        time.sleep(0.05)
    #for AOTSample
    logging.debug("covid_stub_buster(): Complete.")

""" Safely disconnects from the TelePath instance. """
def disconnect():
    return_to_main_menu(ForceReturn=True)
    logging.debug("disconnect(): Disconnecting.")
    TelePath.send('', readEcho=False)
    TelePath.send_raw(b'\x04', readEcho=False)         

def get_outstanding_samples_for_Set(Set:str, Section:str="ALL"):
    logging.info(f"get_outstanding_samples_for_Set(): Retrieving items for Set [{Set}]")
    OutstandingSamples = []
    return_to_main_menu()
    TelePath.send(config.LOCALISATION.OUTSTANDING_WORK)
    TelePath.read_data()
    TelePath.send(Section)
    TelePath.read_data()
    if TelePath.hasErrors:
        raise Exception("Unexpected error after sending Section")
    TelePath.send("2") # Request 'Detailed outstanding work by set'
    TelePath.read_data()
    TelePath.send(Set)
    TelePath.read_data()

    TelePath.send("-") #Using ourselves as a '''printer''' means all data is transmitted at once, but in a slightly less information-dense format.
    time.sleep(0.2)
    TelePath.read_data()
    _dataChunk = TelePath.AUXData[0].strip("\r\x0c").split("\r\n")
    _dataChunk = [x for x in _dataChunk if x]
    _dataChunk = _dataChunk[4:]
    assert _dataChunk[-1]=="End of list"
    _dataChunk = utils.process_whitespaced_table(_dataChunk[2:-1], [20, 36, 58, 76, 98])
    for x in _dataChunk:
        OutstandingSamples.append(x[0]) #Sample ID is in the second column; off by one makes that index 1.    
    
    logging.info(f"get_outstanding_samples_for_Set(): Located {len(OutstandingSamples)} samples.")
    return OutstandingSamples

""" Downloads lists of samples with one or more set(s) beyond their TAT from a named Section (default:AWAY). Optionally, filters for samples by Setcode"""
def get_overdue_sets(Section:str=config.LOCALISATION.OVERDUE_AUTOMATION, SetCode:str=None, FilterSets:list=None) -> list:
    return_to_main_menu()
    TelePath.send(config.LOCALISATION.OVERDUE_SAMPLES, quiet=True)     # Navigate to outstanding sample list
    TelePath.read_data()
    TelePath.send(Section)    # Section AUTOMATION
    TelePath.read_data()
    
    TelePath.send("-", quiet=True)
    time.sleep(0.2)
    TelePath.read_data()
    Samples=[]
    dataChunk = TelePath.AUXData[0].strip("\r\x0c").split("\r\n")
    dataChunk = [x for x in dataChunk if x]
    _headers = dataChunk[2]
    dataChunk = dataChunk[3:]
    
    assert dataChunk[-1]=='End of list'  #second to last chunk should be End of list
    dataChunk = [x for x in dataChunk if (x != "\r\x0cSouth Manchester Clinical Biochemistry System" and x != "Work beyond its turn around time" and x != _headers and x != "End of list")]
    _Samples     = utils.process_whitespaced_table(dataChunk, utils.extract_column_widths(_headers))
    for sample in _Samples: 
        _Set = tp_TestSet(Sample=sample[4], SetIndex=None, SetCode=sample[6], TimeOverdue=sample[7], RequestedOn=sample[5])
        if FilterSets:
            if _Set.Code in FilterSets:
                continue
        _Sample = tp_Specimen(SpecimenID=sample[4])
        _Sample.LName = sample[2]
        _Sample.Sets.append(_Set)
        Samples.append(_Sample)
       
    if SetCode is not None: 
        Samples = [x for x in Samples if SetCode in x.SetCodes]
        logging.debug("get_overdue_sets(): Located %s overdue samples for section '%s' with Set '%s'." % (len(Samples), Section, SetCode))
    else:
        logging.debug(f"get_overdue_sets(): Located {len(Samples)} overdue samples for section '{Section}'")
    return(Samples)

""" Retrieves specimen location (if any) from the SFS, without a popup that's right in your face"""
def get_rack_location(Samples, printTable=True, writeToFile=True):
    #TODO: assert that Samples is a List of tp_Specimen or tp_SampleID
    SampleLocStrs     = [["Sample", "Rack", "Row", "Column", "Stored"]]
    if writeToFile:
        LocDataIO = open(f'./SFS_Locations_{utils.timestamp(fileFormat=True)}.txt', 'w')
        LocDataIO.write("\t".join(SampleLocStrs[0]))
        LocDataIO.write('\n')

    return_to_main_menu()
    TelePath.send("SFS") #TODO Localise
    TelePath.read_data()
    TelePath.send("3") #TODO Localise
    TelePath.read_data()
    for sample in Samples:
        if isinstance(sample, tp_Specimen):
            _sample = sample.ID
        else:
            _sample = str(sample)

        TelePath.send(_sample)
        TelePath.read_data()
        
        #There's an erase instruction at the end, so instead of parsing the final screen we will have to grab the raw ANSI codes...
        StoredSamplesANSI = [x for x in TelePath.ParsedANSI if x.line >= 10 and x.deleteMode == 0]
        StoredSampleLines = list(set([x.line for x in StoredSamplesANSI])) #Get unique line number(s)

        for line in StoredSampleLines:
            lineItems = [x for x in StoredSamplesANSI if x.line == line]
            StorageLoc = [x for x in lineItems if x.column == 1][0].text
            StorageRow = [x for x in lineItems if x.column == 43][0].text
            StorageCol = [x for x in lineItems if x.column == 48][0].text
            StorageDT  = [x for x in lineItems if x.column == 56][0].text
            subStr = [_sample, StorageLoc, StorageRow, StorageCol, StorageDT]
            if writeToFile:
                LocDataIO.write(f"{_sample}\t{StorageLoc}\t{StorageRow}\t{StorageCol}\t{StorageDT}\n")
            SampleLocStrs.append(subStr)

    if writeToFile:
        LocDataIO.flush()
        LocDataIO.close()
        
    if printTable:
        if SampleLocStrs:
            utils.generatePrettyTable(SampleLocStrs, printTable=True)

""" Retrieves the last nMaxSamples samples that came before Sample for the same patient"""    
def get_recent_history(Sample:str, nMaxSamples:int=15, FilterSets:list=None):
    Patient = sample_to_patient(Sample)
    logging.debug(f"get_recent_history(): Retrieving recent samples for Patient [{Patient.ID}]")
    Patient.get_n_recent_samples(nMaxSamples=nMaxSamples)
    complete_specimen_data_in_obj(Patient.Samples, GetNotepad=True, GetComments=True, GetFurther=False, ValidateSamples=False,  FillSets=True, FilterSets=FilterSets)
    logging.info("get_recent_history(): Writing to file...")
    datastructs.samples_to_file(Patient.Samples)

""" Retrieve the most recent n samples with a specified set, regardless of patient"""
def get_recent_samples_of_set_type(Set:str, FirstDate:datetime.datetime=None, LastDate:datetime.datetime=None, nMaxSamples:int=50) -> list:
    logging.info(f"get_recent_samples_of_set_type(): Starting search for [{Set}] samples.")
    return_to_main_menu()
    TelePath.send(config.LOCALISATION.SPECIMENENQUIRY)
    TelePath.read_data()
    TelePath.send("U") #Engages search function
    TelePath.read_data()
    if FirstDate:
        TelePath.send(FirstDate.strftime("DD.MM.YY"))
    else:
        TelePath.send("")
    TelePath.read_data()
    #TODO: handle errors

    if LastDate:
        TelePath.send(LastDate.strftime("DD.MM.YY"))
    else:
        TelePath.send("")
    TelePath.read_data()
    #TODO: handle errors

    TelePath.send(Set)
    TelePath.read_data()

    TelePath.send("") # Skip location
    TelePath.send("") # Skip GP
    TelePath.send("") # Skip consultant
    time.sleep(0.2)
    TelePath.read_data() # TODO: why is everything in ONE LINE
    logging.info(f"get_recent_samples_of_set_type(): Loading samples...")
    fixLines = TelePath.Lines[1].split("\r\n")
    fixLines = [x for x in fixLines if x]
    col_widths = utils.extract_column_widths(fixLines[1])
    samples = []
    while (TelePath.DefaultOption == "N") and (len(samples) < nMaxSamples):
        _samples = utils.process_whitespaced_table(fixLines[2:], col_widths)
        for x in _samples:
            samples.append("".join(x[1:3]))
        TelePath.send(TelePath.DefaultOption)
        TelePath.read_data()
        fixLines = TelePath.Lines[1].split("\r\n")
        fixLines = [x for x in fixLines if x]
    logging.info(f"get_recent_samples_of_set_type(): Search complete. {len(samples)} samples found.")
    if len(samples) > nMaxSamples:
        return samples[:nMaxSamples]
    return samples

"""  """
def get_recent_sister_result(Samples:str, SetFilter:list, Analyte:str):
    #TODO: Easier to use Express Enquiry, flick to Earlier sample?
    #TODO: retrieve current sample from Patient, get SampleTaken, do time comparison + distance in days/hours
    #TODO: Sort? samples to get... well, most recent one _should_ always be first but don't trust TelePath.
    recentSisterSamples = []
    for sample in Samples:
        Patient = sample_to_patient(sample)
        Patient.get_n_recent_samples(Set=SetFilter, nMaxSamples=1, retrieveContents=True) #TODO: this isn't chronological and we know it
        if Patient.Samples:
            tmpSets = [Sample.Sets for Sample in Patient.Samples]
            if tmpSets:
                #TODO: Isolate sister sample
                tmpSets = [Set.Results for SampleSets in tmpSets for Set in SampleSets if Set.Code == SetFilter]
                if tmpSets:
                    tmpSets = [SetResult for SetResult in tmpSets for SetResult in SetResult if SetResult.Analyte == Analyte][0]
                    recentSisterSamples.append( [sample, tmpSets.Analyte, tmpSets.Value, tmpSets.Units, tmpSets.SampleTaken.strftime("%Y/%m/%d, %H:%M:%S")] )
    sisterSampleHeaders = ["Current Sample", "Sister Sample" "Analyte", "Value", "Units", "Sample Taken"]
    with open(f"./{utils.timestamp(fileFormat=True)}_SisterSamples.txt", 'w') as IO:
        IO.write('\t'.join(sisterSampleHeaders))
        IO.write('\n')
        for item in recentSisterSamples:
            IO.write('\t'.join(str(item)))
            IO.write('\n')
    utils.generatePrettyTable(recentSisterSamples, Headers=sisterSampleHeaders, printTable=True)

""" Retrieves worksheets via WRPRT, to check which run(s) a given sample has been on and help locate the physical sample in the freezer.
    Assay - code of the assay to retrieve.
    nSheets - maximum number of worksheets to retrieve. Default: 3
    startDate - datetime.date, from which to start searching. Default: today
    maxAttempts: Maximum number of days to search into the pase. Default: 14 """
def get_recent_worksheets(Assay:str, nSheets:int=3, startDate:datetime.date=None, maxAttempts:int = 14, writeToFile:bool=True) -> list:

    def make_pretty_worksheet(Sheet:str):
        doubleLineMode = False
        RunDate = Sheet[2]
        RunNo = f"{Sheet[1]:02}"
        Sheet = Sheet[0].split("\r\n")
        Sheet = [x.split("\x12\r\r\x0c") for x in Sheet]
        Sheet = [item for sublist in Sheet for item in sublist]
        Sheet = [x.strip("\x12") for x in Sheet if x]
        System = Sheet[0].strip("\r")
        Sheet = Sheet[1:-1]
        assert Sheet [-1] == "End of list"
        Run = Sheet[0]
        Sheet = Sheet[1:-1]
        Sheet = [x for x in Sheet if x != Run]
        Sheet = [x for x in Sheet if x != System]
        ColHeaders = [Sheet[0]]
        Sheet = Sheet[1:]
        if Sheet[0].split(" ")[0] == "Cup":
            doubleLineMode = True
            ColHeaders.append(Sheet[0])
            Sheet = Sheet[1:]
        for line in ColHeaders:
            Sheet = [x for x in Sheet if x != line]
        
        if doubleLineMode:
            Sheet = [" ".join(x) for x in zip(Sheet[0::2], Sheet[1::2])]
            #We could merge the headers into one line - 
            #ColWidths = utils.extract_column_widths(ColHeaders[-1])
            #ColHeaders = utils.process_whitespaced_table(ColHeaders, ColWidths)
            #maxLen = max([len(x) for x in ColHeaders])
            #for line in ColHeaders:
            #    while len(line) < maxLen:
            #        line.append("")
            #ColHeaders = [" ".join(x).strip() for x in zip(*ColHeaders)]

            #The merge above will have extended columns with headerless data from the 2nd line.
            #We could extend ColWidths... with predictable data, I suppose?
            #But let's not do that right now.
        
        if not doubleLineMode:
            ColHeaders    = "Run date Run " + ColHeaders
        else:
            ColHeaders[0] = "             " + ColHeaders[0]
            ColHeaders[1] = "Run date Run " + ColHeaders[1]
        
        Sheet = [f"{RunDate} {RunNo:3} {x}" for x in Sheet]
        Sheet = [f"{item}\n" for sublist in [ColHeaders, Sheet] for item in sublist] 
        return Sheet  

    Sheets = []
    nAttempts = 0
    if startDate is None:
        startDate = datetime.date.today()
    currentDate = startDate
    logging.info(f"get_recent_worksheets(): Preparing to retrieve up to [{nSheets}] [{Assay}] worksheets, over [{maxAttempts}] days, starting from [{startDate.strftime('%d.%m.%y')}]...")

    return_to_main_menu()
    TelePath.send("WRPRT") #TODO: l10n
    TelePath.read_data()
    
    while ((len(Sheets)<nSheets) and (nAttempts < maxAttempts)):
        #Send Assay
        TelePath.send(Assay)
        TelePath.read_data()
        if TelePath.hasErrors:
            err = parse_TP_error()
            logging.error(f"get_recent_worksheets(): TelePath sent the following error message: [{err['msg']}]. Exiting function.") 
            #Should be "Worksheet code unknown to the system", i.e. "this assay does not get worksheets"
            return
    
        #Send rundate
        _tmpDate = currentDate - datetime.timedelta(days = float(nAttempts))
        _tmpDate = _tmpDate.strftime("%d.%m.%y")
        #logging.debug(f"get_recent_worksheets(): Attempting to retrieve [{Assay}] worksheet from [{_tmpDate}]...")
        TelePath.send(_tmpDate)
        TelePath.read_data()
        if TelePath.hasErrors:
            err = parse_TP_error()
            if err['msg'] == f"No runs started on {_tmpDate}":
                logging.info(f"get_recent_worksheets(): There were no {Assay} runs started on {_tmpDate}.")
                nAttempts = nAttempts + 1
                continue #Back to main while loop
        
        else: 
            #Run(s) exist on this date
            nRuns = 1
            while True:
                TelePath.send(str(nRuns))
                TelePath.read_data()
                if TelePath.hasErrors:
                    err = parse_TP_error()
                    if err['msg'] == "Unknown run number":
                        break #quit inner while loop (only way to break out is to reach this error!)
                    else:
                        raise Exception(f"get_recent_worksheets(): Unexpected error: [{err['msg']}]")

                logging.info(f"get_recent_worksheets(): Located Run [{nRuns}] from {_tmpDate}.")
                TelePath.send("", readEcho=False) #Minimum cups (auto-assigned)
                TelePath.read_data()
                TelePath.send("", readEcho=False) #Maximum cups (auto-assigned)
                TelePath.read_data()
                TelePath.send("-") #output to AUX data ('printer')
                time.sleep(0.1)
                TelePath.read_data()
                Sheets.append( (TelePath.AUXData[0].strip("\r\x0c"), nRuns, _tmpDate) )

                #Prep for next iteration:
                nRuns = nRuns + 1
                TelePath.send(Assay) #Tool resets after a run has been printed
                TelePath.read_data()
                TelePath.send(_tmpDate)
                TelePath.read_data()
                                
            TelePath.send("^") #Once you hit Unknown run number, quit interface, which resets back to first line (assay)
            TelePath.read_data()
        
        nAttempts = nAttempts + 1 # A date has been tried, and the loop continues  
    #len(Sheets) exceeds nSheets or nAttempts exceeds nMaxAttempts

    Sheets = [make_pretty_worksheet(x) for x in Sheets]
    
    if writeToFile:
        with open(f"{utils.timestamp(True)}_{Assay}Worksheets.txt", 'w') as IO:
            for Worksheet in Sheets:
                IO.writelines(Worksheet)
                IO.write("\r\n")                    
    return (Sheets)

""" Combination of AOT stubs, SAWAY queue size and NPCL queue size(s) """
def lab_status_report():
    logging.info(" ### LAB STATUS REPORT ###")
    aot_stub_buster()
    sendaways_scan()
    auth_queue_size(DetailLevel=1)

""" Retrieves assay results for a list of Specimens.
    FilterSets: A list of strings, designating which """
def mass_download(Samples:list=None, FilterSets:list=None, getNotepad=False, getComments=False):
    if not Samples:
        logging.info("mass_download(): No samples supplied, loading from file")
        with open("./ToRetrieve.txt", 'r') as DATA_IN:
            Samples = DATA_IN.readlines()
        Samples = [tp_Specimen(x.strip()) for x in Samples]
    logging.info(f"mass_download(): Begin download of {len(Samples)} samples.")
    if isinstance(Samples[0], str):
        Samples = [tp_Specimen(x.strip()) for x in Samples]
    complete_specimen_data_in_obj(Samples, FilterSets=FilterSets, FillSets=True, GetNotepad=getNotepad, GetComments=getComments)
    datastructs.samples_to_file(Samples)
    logging.info("mass_download(): Complete.")

""" Retrieve currently-active FITs and check status via NPEX website """
def NPEX_Buster(Set:str="FIT"):
    logging.info(f"NPEX_Buster(): Retrieving outstanding [{Set}] samples...")
    CurrentSets = get_outstanding_samples_for_Set(Set)
    logging.info(f"NPEX_Buster(): {len(CurrentSets)} samples found. Checking NPEx...")
    npex.retrieve_NPEX_samples(CurrentSets) #TODO: currently broken :(

""" TelePath transmits errors as a text string to the terminal; this function parses them into a dict"""
def parse_TP_error() -> dict:
    #Error format is e.g. "Sample number not found in any rack" title "Sample Filing System" error
    # i.e. "message" param "value" error
    assert len(TelePath.Errors) == 1
    errorstr = [x.strip() for x in TelePath.Errors[0].split("\"") if x] # Split by quotation mark, remove empty strings, remove whitespace
    if len(errorstr)==4:
        return {'msg': errorstr[0], 'title': errorstr[2], 'type':errorstr[3]}
    raise Exception(f"Unexpected format of error: {errorstr}")

""" Attempts to return to the main menu by repeatedly writing ESCAPE or EMPTY commands until the main screen is reached."""
def return_to_main_menu(ForceReturn:bool=False, MaxTries:int=10):
    TryCounter = 0
    logging.debug("Returning to main menu...")
    TargetScreen = "MainMenu"
    if UseTrainingSystem and not ForceReturn:
        TargetScreen = "MainMenu_Training"
    while(TelePath.ScreenType != TargetScreen and TryCounter <= MaxTries):
        TelePath.send(config.LOCALISATION.CANCEL_ACTION)
        TelePath.read_data() #TODO: there is ONE location so far there empty/escape is not accepted and returns an error...
        TryCounter = TryCounter+1
    if TryCounter > MaxTries:
        raise Exception(f"Could not reach main menu in {MaxTries} attempts. Check recognise_Screen_type() logic works correctly and that ESCAPE is allowed input.")

""" Fetches the tp_Patient entry for a sample, or generates one if none exists in PATIENTSTORE."""
def sample_to_patient(Sample:str) -> tp_Patient:
    if isinstance(Sample, tp_Specimen):
        _tmpSample = Sample
    else:
        _tmpSample = tp_Specimen(Sample)
    if not _tmpSample.validate_ID():
        logging.info(f"sample_to_patient(): {Sample} is not a valid specimen ID. Abort.")
        return
    complete_specimen_data_in_obj(_tmpSample, GetFurther=False, FillSets=True) #Gets patient data via SENQ
    return tp_Patient.Storage[_tmpSample.PatientID] # Return patient obj

""" Retrieves outstanding sendaway (section AWAY) samples. For each sample, retrieves specimen notepad contents, patient details, and any set comments. """
def sendaways_scan(getDetailledData:bool=False) -> None:
    OverdueSAWAYs = get_overdue_sets("AWAY", FilterSets=["ACOV2", "COVABS", "ACOV2S"])    # Retrieve AWAY results from OVRW
    OverdueSAWAYs = [x for x in OverdueSAWAYs if str(x.ID) != "19.0831826.N"] #19.0831826.N - Sample stuck in Background Authoriser since 2019, RIP.
    logging.info(f"sendaways_scan(): There are a total of {len(OverdueSAWAYs)} overdue samples from section 'AWAY', which are not COVABS/ACOV2/ACOV2S or sample 19.0831826.N.")
    if getDetailledData:
        SAWAY_DB = datastructs.load_sendaways_table()
        # For each sample, retrieve details: Patient FNAME LNAME DOB    
        complete_specimen_data_in_obj(OverdueSAWAYs, GetNotepad=True, GetComments=True, GetFurther=True, 
                                                ValidateSamples=False, FillSets=False)
        outFile = f"./{utils.timestamp(fileFormat=True)}_SawayData.txt"
        SAWAY_Counters = range(0, len(OverdueSAWAYs))
        logging.info("sendaways_scan(): Beginning to write overdue sendaways to file...")
        with open(outFile, 'w') as SAWAYS_OUT:
            HeaderStr = "Specimen\tNHS Number\tLast Name\tFirst Name\tDOB\tSample Taken\tTest\tTest Name\tReferral Lab\tContact Lab At\t"
            HeaderStr = HeaderStr + "Hours Overdue\tCurrent Action\tAction Log\tRecord Status\tSet Comments\tClinical Details\tSpecimen Notepad\n"
            SAWAYS_OUT.write(HeaderStr)
            del HeaderStr
            for SAWAY_Sample in OverdueSAWAYs:
                for OverdueSet in SAWAY_Sample.Sets:
                    #Specimen NHSNumber   Lastname    First Name  DOB Received    Test
                    outStr = f"{SAWAY_Sample.ID}\t{SAWAY_Sample.NHSNumber}\t{SAWAY_Sample.LName}\t{SAWAY_Sample.FName}\t"
                    if isinstance(SAWAY_Sample.DOB, datetime.datetime):
                        outStr = outStr+SAWAY_Sample.DOB.strftime('%d/%m/%Y')
                    else:
                        outStr = outStr+str(SAWAY_Sample.DOB)
                    outStr = outStr+f"\t{SAWAY_Sample.Received.strftime('%d/%m/%Y')}\t{OverdueSet.Code}\t"

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
                                            
                    # CurrentAction   Action Log
                    outStr = outStr + "\t\t"
                        
                    #Sample Status
                    StatusStr = "Incomplete\t"
                    outStr = outStr + StatusStr

                    #Check for comments
                    CommStr = "\t"
                    if OverdueSet.Comments: 
                        CommStr = f"{' '.join(OverdueSet.Comments)}\t"
                    outStr = outStr + CommStr

                    #Clinical Details
                    if SAWAY_Sample.ClinDetails:
                        outStr = outStr + SAWAY_Sample.ClinDetails + "\t"
                    else:
                        outStr = outStr + "No Clinical Details\t"

                    
                    #Check for Notepad
                    NPadStr = ""
                    if SAWAY_Sample.hasNotepadEntries == True:
                        NPadStr = "|".join([str(x) for x in SAWAY_Sample.NotepadEntries])
                    outStr = outStr + NPadStr
                
                    outStr = outStr + "\n"
                    SAWAYS_OUT.write(outStr)
        logging.info(f"sendaways_scan(): Complete. Downloaded and exported data for {len(SAWAY_Counters)} overdue sendaway samples to file.")

if __name__ == "__main__":
    logging.info(f"TelePath TelePath client, version {VERSION}. (c) Lorenz K. Becker, under GNU General Public License")
    connect()
    
    try:
        #==========
        #Interfaces
        #==========
        #CLI()  
        BasicInterface()    

        #==========
        #Data retrieval functions
        #==========
        #mass_download(get_recent_samples_of_set_type("OEMS", nMaxSamples=200), FilterSets=["OEMS"], getNotepad=False) #FilterSets means only the specified sets are retrieved
        #mass_download() # Downloads all data for samples in ToRetrieve.txt and saves to file.
        #get_recent_sister_result(ReninALDOSamples, "E2", "K")
        #get_recent_history("22.0119928.T", nMaxSamples=24) #Gets up to nMaxSamples recent samples for the same patient as the given sample. Good to get a quick patient history.
        #npex.retrieve_NPEX_data("21.7767101.D")
        #get_rack_location(OestradiolSamples, writeToFile=False)
        #get_overdue_sets()
        #get_outstanding_samples_for_Set("AOT", "AUTO")
        #get_recent_worksheets("OEMS")

        #==========
        #Auto-processing functions: Sendaways, AOT stubs, NPEX stragglers.
        #==========
        #aot_stub_buster() # Shows how many open AOTs there are for section AUTO
        #aot_stub_buster(insert_NA_result=True, get_creators=False) # Shows how many open AOTs there are for section AUTO, closed them, tells you who made them
        #sendaways_scan() # Shows how many overdue sendaways there are
        #sendaways_scan(getDetailledData=True) # Shows how many overdue sendaways there are, and creates a spreadsheet to follow them up. Needs a sendaways_database.tsv    
        #NPEX_Buster(Set="FIT") # Retrieves outstanding (but not overdue) Sets for the entire lab, and checks NPEX whether there are results for any. 
        #NPEX_Buster(Set="FCAL")
        #auth_queue_size(DetailLevel=1)
        #lab_status_report()
        #visualise("A,22.0093756.G", nMaxSamples=10) #Still a bit experimental - retrieves recent data for the patient of this sample and makes graphs.
        pass

    # except Exception as e: 
    #     logging.error(e)

    finally:
        disconnect()
        logging.info("System is now shut down. Have a nice day!")