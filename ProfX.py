#GPL-3.0-or-later

VERSION = "1.8.5"
LOGFORMAT = '%(asctime)s: %(name)-10s:%(levelname)-7s:%(message)s'

import argparse
from collections import Counter
from functools import reduce
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

telnet_ANSI.Connection.recognise_Screen_type = config.LOCALISATION.identify_screen
TelePath = telnet_ANSI.Connection(Answerback=config.LOCALISATION.ANSWERBACK)

UseTrainingSystem = False

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
        self.AsText     = ""
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
            self.AsText = str(self)

        except (AssertionError, ValueError):
            logging.debug(f"SampleID(): ID parsing failed for {IDStr}.")

    def __str__(self) -> str:
        return f"{self.Year}.{self.LabNumber:07}.{self.CheckChar}" #Without padding of ID Number to 10 positions, the validation will not work correctly

    def __repr__(self) -> str:
        return(f"SampleID(\"A,{self.Year}.{self.LabNumber}.{self.CheckChar}\")")

    """Function to check sample IDs, replicating TelePath's check digit algorithm  """
    def validate(self) -> bool:
        assert self.Year
        assert self.LabNumber
        assert self.CheckChar

        if self.useLocalisationValidationFun: #TODO: test
            return config.LOCALISATION.check_sample_id(self.AsText)

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
        #TODO: put into PATIENT object (Search for existing patient, if not make new for Registration)
        #TODO: get patient ID (registration)

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
        
        TestStart = ANSIChunks.index([x for x in ANSIChunks if x.text == "Sets Requested :-"][0])
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
            self.Sets.append(datastructs.TestSet(Sample=self.ID, SetIndex=index, SetCode=test, Status=status))
        
        #TelePath only highlights the specimen notepad option if entries exist; else it's part of a single chunk of options, none highlighted. So...
        if [x for x in ANSIChunks if (x.text=="spc N'pad" and x.highlighted)]: 
            self.hasNotepadEntries = True
    
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


tp_Patient.Storage = datastructs.SingleTypeStorageContainer(tp_Patient)

"""Downloads lists of samples with one or more set(s) beyond their TAT from a named Section (default:AWAY). Optionally, filters for samples by Setcode"""
def get_overdue_sets(Section:str=config.LOCALISATION.OVERDUE_AUTOMATION, SetCode:str=None, FilterSets:list=None) -> list:
    return_to_main_menu()
    TelePath.send(config.LOCALISATION.OVERDUE_SAMPLES, quiet=True)     # Navigate to outstanding sample list
    TelePath.read_data()
    TelePath.send(Section)    # Section AUTOMATION
    TelePath.read_data() #tODO: should be replacing ..... with the thing sent. Based on.... position?
    TelePath.send('0', quiet=True)        # Send output to screen, which in this case is then parsed as our input stream
    time.sleep(0.5)
    Samples = []
    while TelePath.DefaultOption != "Q": # Parse overdue samples until there are none left to parse 
        time.sleep(0.2)
        TelePath.read_data()
        if (TelePath.screenLength > 5):        # #Presence of non-empty lines after four lines of header implies there are list members to parse
            samples     = utils.process_whitespaced_table(TelePath.Lines[5:-2], utils.extract_column_widths(TelePath.Lines[3]))
            for sample in samples: 
                _Set = datastructs.TestSet(Sample=sample[3], SetIndex=None, SetCode=sample[5], TimeOverdue=sample[6], RequestedOn=sample[4])
                if FilterSets:
                    if _Set.Code in FilterSets:
                        continue
                _Sample = tp_Specimen(SpecimenID=sample[3])
                _Sample.LName = sample[2]
                _Sample.Sets.append(_Set)
                Samples.append(_Sample)
        TelePath.send(TelePath.DefaultOption, quiet=True)
    TelePath.send('Q', quiet=True) #for completeness' sake, and so as to not block i guess
    if SetCode is not None: 
        Samples = [x for x in Samples if SetCode in x.SetCodes]
        logging.debug("get_overdue_sets(): Located %s overdue samples for section '%s' with Set '%s'." % (len(Samples), Section, SetCode))
    else:
        logging.debug("get_overdue_sets(): Located %s overdue samples for section '%s'" % (len(Samples), Section))
    return(Samples)
           
""" Retrieves tp_Specimen data (demographics, etc) for any tp_Specimen object in the list SampleObjs.
    Option GetFurther also retrieves Clinical Details and NHS Number.
    Can also retreive Sets run, Set result(s), Set comments, and tp_Specimen Notepad data.
    If FillSets is true, loads all available data, else, only attempts to complete TestSet obj present in the tp_Specimen"""
    #TODO: Comments for Sendaways still not always coming across
def complete_specimen_data_in_obj(SampleObjs=None, GetNotepad:bool=False, GetComments:bool=False, GetFurther:bool=False, ValidateSamples:bool=True, FillSets:bool=False, FilterSets:list=None):
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

        SetIsAuthed = False
        if SetToGet.Status:
            if SetToGet.Status[0]=="R":
                SetIsAuthed = True

        if not SetIsAuthed:
            AuthData = [x for x in TelePath.ParsedANSI if x.line == 21 and x.column==0 and x.highlighted == True]
            if AuthData:
                if not AuthData[0].text.strip() == "WARNING :- these results are unauthorised":
                    SetIsAuthed = True
        
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

    if len(SampleObjs)==0: 
        logging.warning("Could not find any Samples to process. Exiting program.")
        return

    return_to_main_menu()
    TelePath.send(config.LOCALISATION.SPECIMENENQUIRY, quiet=True) #Move to specimen inquiry 
    TelePath.read_data()
    SampleCounter = 0
    nSamples = len(SampleObjs)
    ReportInterval = max(min(250, int(nSamples*0.1)), 1)
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
        TelePath.read_data(max_wait=400)   # And read screen.
        if (TelePath.hasErrors == True):
            # Usually the error is "No such specimen"; the error shouldn't be 'incorrect format' if we ran validate_ID().
            logging.warning(f"complete_specimen_data_in_obj(): '{';'.join(TelePath.Errors)}'")
        else:
            _SetCodes = Sample.SetCodes #...blank list? TODO:check
            Sample.from_chunks(TelePath.ParsedANSI)  #Parse sample data, including patient details, sets, and assigning tp_Specimen.Collected DT.
            if FillSets == False:
                Sample.Sets = [x for x in Sample.Sets if x.Code in _SetCodes]

            if (GetNotepad == True):
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
                    TelePath.send(str(SetToGet.Index), quiet=True)
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
                            TelePath.read_data(max_wait=400)
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
            logging.info(f"complete_specimen_data_in_obj(): {SampleCounter} of {nSamples} samples ({Pct:.2f}%) complete")
    time.sleep(0.1)
    #for Sample in Samples
    logging.debug("complete_specimen_data_in_obj(): All downloads complete.")

""" Supposed to retrieve the most recent n samples with a specified set, via SENQ"""
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

def get_outstanding_samples_for_Set(Set:str, Section:str=""):
    logging.info(f"get_outstanding_samples_for_Set(): Retrieving items for Set [{Set}]")
    return_to_main_menu()
    TelePath.send(config.LOCALISATION.OUTSTANDING_WORK)
    TelePath.read_data()
    TelePath.send(Section)
    TelePath.read_data()
    if TelePath.hasErrors:
        #idk handle errors what am i a professional coder
        raise Exception("Unexpected error after sending Section")
    TelePath.send("2") # Request 'Detailed outstanding work by set'
    TelePath.read_data()
    TelePath.send(Set)
    TelePath.read_data()
    TelePath.send("0", quiet=True) # Output on 'screen'
    time.sleep(0.2)
    OutstandingSamples = []
    tmp_table_widths = [1, 5, 20, 32, 39, 58, 61, 71, 74] # These are hardcoded because the headers seem misaligned.
    while TelePath.DefaultOption != "Q":
        TelePath.read_data()
        if TelePath.ScreenType == "OUTW_Basic":
            #System has returned to main screen without giving Q as the final option...
            break
        #tmp_table_widths = extract_column_widths(TelePath.Lines[4])
        tmp = utils.process_whitespaced_table(TelePath.Lines[7:-2], tmp_table_widths) #read and process screen
        for x in tmp:
            OutstandingSamples.append(x[1]) #Sample ID is in the second column; off by one makes that index 1. 
        TelePath.send(TelePath.DefaultOption, quiet=True) 
    TelePath.send("Q")
    logging.info(f"get_outstanding_samples_for_Set(): Located {len(OutstandingSamples)} samples.")
    return OutstandingSamples

def get_specimen_history(Samples:list):

    pass

def get_recent_history(Sample:str, nMaxSamples:int=15, FilterSets:list=None):
    Patient = sample_to_patient(Sample)
    logging.debug(f"get_recent_history(): Retrieving recent samples for Patient [{Patient.ID}]")
    Patient.get_n_recent_samples(nMaxSamples=nMaxSamples)
    complete_specimen_data_in_obj(Patient.Samples, GetNotepad=True, GetComments=True, GetFurther=False, ValidateSamples=False,  FillSets=True, FilterSets=FilterSets)
    logging.info("get_recent_history(): Writing to file...")
    datastructs.samples_to_file(Patient.Samples)

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

""" Attempts to return to the main menu by repeatedly writing ESCAPE or EMPTY commands until the main screen is reached."""
def return_to_main_menu(ForceReturn:bool=False, MaxTries:int=10):
    TryCounter = 0
    logging.debug("Returning to main menu...")
    TargetScreen = "MainMenu"
    if UseTrainingSystem and not ForceReturn:
        TargetScreen = "MainMenu_Training"
    while(TelePath.ScreenType != TargetScreen and TryCounter <= MaxTries):
        TelePath.send(config.LOCALISATION.CANCEL_ACTION)
        TelePath.read_data()
        TryCounter = TryCounter+1
    if TryCounter > MaxTries:
        raise Exception(f"Could not reach main menu in {MaxTries} attempts. Check recognise_Screen_type() logic works correctly.")

""" Connects to a TelePath instance, and logs in the user, querying for Username and Password if none are supplied. """
def connect(TrainingSystem=False):  
    if config.LOCALISATION.LIMS_USER:
        if config.LOCALISATION.LIMS_USER != "YOUR USERNAME HERE": 
            user = config.LOCALISATION.LIMS_USER
        else: 
            user = input("Enter your TelePath username: ")
    else:
        user = input("Enter your TelePath username: ")
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

""" Safely disconnects from the TelePath instance. """
def disconnect():
    return_to_main_menu(ForceReturn=True)
    logging.debug("disconnect(): Disconnecting.")
    TelePath.send('', readEcho=False)
    TelePath.send_raw(b'\x04', readEcho=False)         

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
                try:
                    OverdueSets = [x for x in SAWAY_Sample.Sets if x.is_overdue]
                    for OverdueSet in OverdueSets:
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
        
                except AssertionError:
                    continue
                    
        logging.info(f"sendaways_scan(): Complete. Downloaded and exported data for {len(SAWAY_Counters)} overdue sendaway samples to file.")

""" Retrieves privilege levels for a list of users"""
def privilege_scan(userlist = None) -> None:
    #TODO: UNTESTED UTILITY FUNCTION
    UserPrivs = []
    UserPrivs.append( "TelePath, Version {VERSION}.\nPrivilege level extraction\n\n" )
    UserPrivs.append( "Username\tFull Name\tPrivilege level\n" )

    if UseTrainingSystem == True:
        logging.warning("privilege_scan(): the training system will return different result to the live system!")

    return_to_main_menu()
    
    #Gather employee names OR read from file
    if not userlist:
        ul_file = open('./PrivCheck.txt', 'r')
        userlist = ul_file.readlines()
        userlist = [x.trim() for x in userlist]
    
    logging.error("privilege_scan(): FUNCTION ISN'T DONE YET")
    
    #Enter administration area - needs privilege on TelePath user to access
    TelePath.send(config.LOCALISATION.PRIVILEGES) #requires Level 1 access, do *not* write data to this area to avoid messing up the system.
    TelePath.read_data()
    assert TelePath.ScreenType == "PRIVS"

    for user in userlist:
        TelePath.send(user)
        TelePath.read_data() #Check access was successful

        #TODO: If querying an account that does not exist, the cursor goes to line... 6? (TODO:check it's line 6), to make a new account; abort via TelePath.send('^')
        if TelePath.cursorPosition[0]<20:
            logging.info(f"privilege_scan(): User '{user}' does not appear to exist on the system.")
            TelePath.send(config.LOCALISATION.CANCEL_ACTION) #Return to main screen, ready for next
            continue
        
        #If that isn't the case, grab results and parse
        results = TelePath.Lines[3:16] #TODO: Check exact lines
        results = [x for x in results if x.strip()]
        result_tbl = utils.process_whitespaced_table(results, [0, 28]) #TODO: check this estimated col width works
        
        UserPrivs.append( f"{result_tbl[0][1]}\t{result_tbl[1][1]}\t{result_tbl[5][1]}\t\n" ) #TODO: check table

        TelePath.send('A') #Return to admin area, by Accepting the current settings without having changed a thing
    
    logging.info("privilege_scan(): Writing to output file.")
    outFile = f"./{utils.timestamp(fileFormat=True)}_PrivScan.txt"
    with open(outFile, 'w') as out:
        for line in UserPrivs:
            out.write(line)
    logging.info("privilege_scan(): Complete.")

""" retrieves a list of recent speciments for a patient, and runs mass_download() on them. """
def patient_download(SampleID, FilterSets:list=None):
    
    pass

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

""" Experimental graph producer. Not working currently. """
def visualise(Sample:str, FilterSets:list=None, nMaxSamples:int=10):
    Patient = sample_to_patient(Sample)
    Patient.get_n_recent_samples(nMaxSamples=nMaxSamples)
    complete_specimen_data_in_obj(Patient.Samples, GetFurther=False, FillSets=True, ValidateSamples=False)
    Patient.create_plot(FilterAnalytes=FilterSets)

""" Retrieve currently-active FITs and check status via NPEX website """
def NPEX_Buster(Set:str="FIT"):
    logging.info(f"NPEX_Buster(): Retrieving outstanding [{Set}] samples...")
    CurrentSets = get_outstanding_samples_for_Set(Set)
    logging.info(f"NPEX_Buster(): {len(CurrentSets)} samples found. Checking NPEx...")
    npex.retrieve_NPEX_samples(CurrentSets)

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

    TelePath.send(config.LOCALISATION.AUTHORISATION)
    TelePath.read_data()
    AuthQueues = TelePath.Lines[4].split("\r\n")[1:]
    AuthQueues = utils.process_whitespaced_table(AuthQueues[1:], WYTH_AUTH_HEADER_SIZES)
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

def CLI():
    parser = argparse.ArgumentParser(prog='TelePath', description='Connects to a TelePath LIMS system and extracts data.')
    parser.add_argument('sample', help="The ID of the sample to process")
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
        if UserInput == re.sub(r'[\W0-9]+', '', UserInput):
            return True
        return False

    def is_sample(UserInput:str, lowerBound:None, upperBound:None):
        _sample = tp_SpecimenID(UserInput)
        return _sample.validate()

    print("""
    
    Welcome to the TelePath custom TelePath client.
    
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
        print(get_recent_samples_of_set_type(SetToDL, nMaxSamples=NSets))
        
    if choice=="6":
        print("""
    Patient history
    
        """)
        SampleToDL = get_user_input(is_sample, "Please enter a valid sample ID.", "Which sample do you wish to generate a patient history from? ")
        get_recent_history(SampleToDL, nMaxSamples=15)

    if choice=="7":
        import tp_setripper
        SetsIO = open("./SetsToExtract.txt", "r")
        SetsToRip = SetsIO.readlines()
        SetsIO.close()
        SetsToRip = [x.strip() for x in SetsToRip]
        tp_setripper.set_ripper(SetsToRip)

    input("Press any key to exit...")

def lab_status_report():
    logging.info(" ### LAB STATUS REPORT ###")
    aot_stub_buster()
    sendaways_scan()
    auth_queue_size(DetailLevel=1)
       
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
        utils.generatePrettyTable(SampleLocStrs, printTable=True)

def get_recent_sister_result(Samples, SetFilter, Analyte):
    #TODO: retrieve current sample from Patient, get SampleTaken, do time comparison + distance in days/hours
    #TODO: Sort? samples to get... well, most recent one _should_ always be first but don't trust TelePath.
    recentSisterSamples = []
    for sample in Samples:
        Patient = sample_to_patient(sample)
        Patient.get_n_recent_samples(Set=SetFilter, nMaxSamples=1, retrieveContents=True)
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

logging.basicConfig(filename='./debug.log', filemode='w', level=logging.DEBUG, format=LOGFORMAT)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter(LOGFORMAT))
logging.getLogger().addHandler(console)

logging.info(f"TelePath TelePath client, version {VERSION}. (c) Lorenz K. Becker, under GNU General Public License")
connect()

try:
    #==========
    #Interfaces
    #==========
    #CLI()  
    #BasicInterface()    

    #==========
    #Data retrieval functions
    #==========
    #mass_download(get_recent_samples_of_set_type("FK506", nMaxSamples=210), FilterSets=["FK506"], getNotepad=False) #FilterSets means only the specified sets are retrieved
    #mass_download() # Downloads all data for samples in ToRetrieve.txt and saves to file.
    ReninALDOSamples = ["22.0070714.L", "22.0070949.X", "22.4403542.M", "22.4402775.S", "22.4402793.X", 
                    "22.4402838.N", "22.4403832.S", "22.4401819.B", "22.4401818.J", "22.4406052.T", 
                    "22.4401879.D", "22.4406285.Y", "22.4406348.A", "22.0088894.G", "22.0088903.E", 
                    "22.0088917.Z", "22.4406511.Q", "22.4406504.D", "22.4406506.Z", "22.4406507.Q", 
                    "22.4406508.H", "22.4406509.W", "22.4406510.Z", "22.0089936.A", "22.4406576.V", 
                    "22.4406577.R", "22.4406578.D", "22.4406613.Y", "22.4406614.P", "22.4406619.R", 
                    "22.4406629.W", "22.4406630.Z", "22.4406688.P", "22.4411065.E", "22.4411064.N", 
                    "22.4406732.E", "22.4406721.K", "22.4406722.J", "22.4406723.B", "22.4406724.X", 
                    "22.4406725.L", "22.4406726.G", "22.4406727.N", "22.4411094.J", "22.4411096.X", 
                    "22.4411079.Z", "22.4411080.R", "22.4411092.C", "22.4411093.K", "22.4411091.A", 
                    "22.4411089.K", "22.4411090.W", "22.4411078.S", "22.4411077.D", "22.4411075.V", 
                    "22.4411076.R", "22.4406692.P", "22.4411104.L", "22.4406734.P", "22.4406735.F", 
                    "22.4406736.T", "22.4406737.M", "22.4406738.V", "22.4406739.R", "22.4406746.Z", 
                    "22.4406747.Q", "22.4406748.H", "22.4411224.L", "22.4406912.Z", "22.4406906.D", 
                    "22.4406908.Z", "22.4406909.Q", "22.4411232.Y", "22.4411229.P", "22.4410146.R", 
                    "22.4410147.D", "22.4410148.S", "22.4406913.Q", "22.4406948.Q", "22.4406949.H"]
    #mass_download(ReninALDOSamples, FilterSets=["ALDO1", "E2"])
    #get_recent_sister_result(ReninALDOSamples, "E2", "K")
    
    #get_recent_history("22.0119928.T", nMaxSamples=24) #Gets up to nMaxSamples recent samples for the same patient as the given sample. Good to get a quick patient history.
    #npex.retrieve_NPEX_data("21.7767101.D")
    #get_rack_location(["22.0107743.M", "22.0098413.B", "22.0106865.A", "22.0101155.H", "22.0097636.K"])

    #==========
    #Auto-processing functions: Sendaways, AOT stubs, NPEX stragglers.
    #==========
    #aot_stub_buster() # Shows how many open AOTs there are for section AUTO
    #aot_stub_buster(insert_NA_result=True, get_creators=False) # Shows how many open AOTs there are for section AUTO, closed them, tells you who made them
    #sendaways_scan() # Shows how many overdue sendaways there are
    #sendaways_scan(getDetailledData=True) # Shows how many overdue sendaways there are, and creates a spreadsheet to follow them up. Needs a sendaways_database.tsv    
    #NPEX_Buster(Set="FIT") # Retrieves outstanding (but not overdue) Sets for the entire lab, and checks NPEX whether there are results for any. 
    #NPEX_Buster(Set="FCAL")
    auth_queue_size(DetailLevel=1)
    #lab_status_report()
    #visualise("A,22.0093756.G", nMaxSamples=10) #Still a bit experimental - retrieves recent data for the patient of this sample and makes graphs.
    pass

except Exception as e: 
    logging.error(e)

finally:
    disconnect()
    logging.info("System is now shut down. Have a nice day!")
