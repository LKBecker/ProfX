#GPL-3.0-or-later

from tp_telnet import ProfX, Screen
from tp_utils import process_whitespaced_table, extract_column_widths, calc_grid, timestamp
import config

from collections import Counter
import datetime
from itertools import chain
import logging
import matplotlib.pyplot as plt
import matplotlib as mpl
plt.style.use('ggplot')
font = {'family' : 'monospace',
        'size'   : 8}
plt.rc('font', **font)  # pass in the font dict as kwargs

import os.path
import time

dataLogger = logging.getLogger(__name__)

class ReferenceRange():
    def __init__(self, Analyte:str, Upper:float, Lower:float, Unit:str):
        self.UpperLimit = value_or_none(Upper)
        if self.UpperLimit:
            self.UpperLimit = float(self.UpperLimit)
        self.LowerLimit = value_or_none(Lower)
        if self.LowerLimit:
            self.LowerLimit = float(self.LowerLimit)
        self.Analyte    = value_or_none(Analyte)
        self.Unit       = value_or_none(Unit)

    def __repr__(self):
        return f"ReferenceRange(Analyte={self.Analyte}, Upper={self.UpperLimit}, Lower={self.LowerLimit}, Unit={self.Unit})"

    def __str__(self):
        return f"Reference range for {self.Analyte}: {self.LowerLimit} - {self.UpperLimit} {self.Unit}"


class PatientContainer():
    def __init__(self):
        self.Patients = {}

    def __getitem__(self, key):
        return self.Patients[key]

    def __setitem__(self, key, item):
        self.Patients[key] = item

    def has_patient(self, PatientID):
        if type(PatientID)=="Patient":
            PatientID = str(Patient)
        if PatientID in self.Patients.keys() : return True
        return False

    def append(self, Patient):
        self.Patients[str(Patient.ID)]=Patient


"""Contains a Specimen Notepad entry, including author, etc"""
class SpecimenNotepadEntry():
    def __init__(self, ID:str, Author:str, Text:str, Index:str, Authored:str):
        self.SampleID   = ID
        self.Author     = Author
        self.Text       = Text
        self.Index      = Index
        self.Authored   = Authored 
    
    def __repr__(self): return f"Spec N'pad Entry #{self.Index} for {self.SampleID}"
    
    def __str__(self): return f"[{self.SampleID} #{self.Index}] {self.Author} {self.Authored}: \"{self.Text}\""


""" Contains data regarding test result(s) - analyte, flags"""
class SetResult():
    def __init__(self, Analyte:str, Value=None, Units:str="", SampleTaken:datetime.datetime=None, AuthDateTime:str=None, ReportedOn:str=None, Flags:str=None):

        def datetime_or_none(Value, Scheme):
            if Value:
                try:
                    tmpDT = datetime.datetime.strptime(Value, Scheme)
                except:
                    tmpDT = Value
                return tmpDT 
            return None

        self.Analyte = Analyte
        try:
            self.Value = float(Value)
        except:
            self.Value = Value #Preserves freetext, and < or > values
            
        self.Units = Units
        self.Flags = Flags
        self.AuthDateTime = datetime_or_none(AuthDateTime, "%d.%m.%y %H:%M")
        self.ReportedOn = datetime_or_none(ReportedOn, "%d.%m.%y")
        self.SampleTaken = datetime_or_none(SampleTaken, "%d.%m.%y %H:%M")
        
    def __str__(self):
        ResStr = f"{self.Analyte}\t{self.Value}\t{self.Units}"
        #if self.SampleTaken:
        #    if isinstance(self.SampleTaken, datetime.datetime):
        #        ResStr = ResStr + f" (Sample taken: {self.SampleTaken.strftime('%y-%m-%d %H:%M')})"
        if self.Flags:
            ResStr = ResStr + f"\t[{self.Flags}]"
        return ResStr

    def __repr__(self):
        RepOnStr = self.ReportedOn
        if isinstance(self.ReportedOn, datetime.datetime):
            RepOnStr = self.ReportedOn.strftime("%d.%m.%Y %H:%M")
        return f"SetResult(Analyte={self.Analyte}, Value={self.Value}, Units={self.Units}, Flags={self.Flags}, ReportedOn={RepOnStr})"


"""Contains a (set of) test(s), any result(s), and any comment(s) for that test"""
class TestSet():
    def __init__(self, Sample:str, SetIndex:str, SetCode:str, AuthedOn:str=None, AuthedBy:str=None, Status:str=None, 
                 Results:list=None, Comments:list=None, RequestedOn:str=None, TimeOverdue:str=None, Override:bool=False):
        self.Sample     = SampleID(Sample, Override)
        self.Index      = SetIndex
        self.Code       = SetCode
        self.Status     = Status
        if not Results:
            self.Results    = []
        else:
            self.Results = Results
        if AuthedOn:
            try:
                self.AuthedOn    = datetime.datetime.strptime(AuthedOn, "%d.%m.%y %H:%M")
            except:
                self.AuthedOn   = AuthedOn
        else:
            self.AuthedOn   = None

        self.AuthedBy   = AuthedBy
        if Comments: 
            self.Comments = Comments
        else:
            self.Comments = []
        
        if RequestedOn:
            try:
                self.RequestedOn    = datetime.datetime.strptime(RequestedOn, "%d.%m.%y")
                self.CalcOverdue    = (datetime.datetime.now() - self.RequestedOn)
                self.OverdueHM      = self.CalcOverdue.days * 24 + self.CalcOverdue.seconds // 3600 + ((self.CalcOverdue.seconds // 60) % 60)
            except:
                self.RequestedOn    = None
        else:
            self.RequestedOn = None
            #self.CalcOverdue = None
            self.OverdueHM   = "XX:XX"
        
        if TimeOverdue:
            if (TimeOverdue[-1]=="m"): 
                self.Overdue    = datetime.timedelta(minutes=int(TimeOverdue[:-1]))
            else: 
                self.Overdue    = datetime.timedelta(hours=int(TimeOverdue))
        else:
            self.Overdue = datetime.timedelta(hours=0)
    
    @property
    def is_overdue(self): return self.Overdue.total_seconds() > 0

    def addSetResult(self, resItem:SetResult):
        #Add SetResult to list after checking it's not already present, or a similar result for this analyte?
        raise NotImplementedError
    
    def __repr__(self): 
        return f"TestSet(ID={str(self.Sample)}, SetIndex={self.Index}, SetCode={self.Code}, AuthedOn={self.AuthedOn}, AuthedBy={self.AuthedBy}, Status={self.Status}, ...)"
    
    def __str__(self): 
        return f"[{self.Sample}, #{self.Index}: {self.Code} ({self.Status})] - {len(self.Results)} SetResults, {len(self.Comments)} Comments. Authorized {self.AuthedOn} by {self.AuthedBy}."
    
    def prepare_file_format(self):
        pass
    
    def write_to_file(self):
        pass


""" Contains de-and encoding for Sample IDs (barcoded) and enables ability to sort them.
    By default, implements a Offset 23-based system in use at a local trust; set Override to True to disable these default checks."""
class SampleID():
    CHECK_INT = 23
    CHECK_LETTERS = ['B', 'W', 'D', 'F', 'G', 'K', 'Q', 'V', 'Y', 'X', 'A', 'S', 'T', 'N', 'J', 'H', 'R', 'P', 'L', 'C', 'Z', 'M', 'E']

    def __init__(self, IDStr, Override = False):
        self.Override = Override
        if self.Override:
            self.AsText = IDStr
            return

        #Prefix, Date Part, Number Part, Check Char
        self.Prefix     = "A,"
        self.Year       = None
        self.LabNumber  = None
        self.CheckChar  = None
        self.AsText     = ""

        IDStr = IDStr.upper()
        if IDStr[1]==",":
            self.Prefix = IDStr[:2]
            IDStr=IDStr[2:]
        IDStrSplit = IDStr.split(".")

        try:
            if len(IDStrSplit)==1:
                #dataLogger.debug("SampleID(): Only one piece of data found. Assuming it's a 7-digit sample number from current year.")
                if len(IDStrSplit[0]) == 7:
                    self.LabNumber = int(IDStrSplit[0])
                else: raise ValueError("Parsing one-piece IDStr. No 7-digit sample id found - cannot estimate Sample ID unambiguously.")
        
            elif len(IDStrSplit)==2:
                #dataLogger.debug("SampleID(): Two pieces of data found. Checking whether Year+ID or ID+CheckDigit...")

                if len(IDStrSplit[0]) == 2:
                    dataLogger.debug("SampleID(): First entry is len 2, likely Year")
                    self.Year = int(IDStrSplit[0])
                elif len(IDStrSplit[0]) == 7:
                    dataLogger.debug("SampleID(): First entry is len 7, likely Sample ID")
                    self.LabNumber = int(IDStrSplit[0])
                else:
                    raise ValueError(f"Cannot parse '{IDStrSplit[0]}' as Year or Sample ID.")

                if len(IDStrSplit[1]) == 1:
                    dataLogger.debug("SampleID(): Last entry is len 1, likely Check Digit")
                    self.CheckChar = IDStrSplit[1]
                elif len(IDStrSplit[1]) == 7:
                    dataLogger.debug("SampleID(): Last entry is len 7, likely Sample ID")
                    self.LabNumber = int(IDStrSplit[1])
                elif len(IDStrSplit[1]) == 8:
                    dataLogger.debug("SampleID(): Last entry is len 8, likely Sample ID and check digit")
                    chkOrd = ord(IDStrSplit[1][-1])
                    if chkOrd >= 65 and chkOrd <= 90: #it's an ASCII capital letter between A and Z
                        self.CheckChar = IDStrSplit[1][-1]
                        self.LabNumber = int(IDStrSplit[1][:-1])
                else:
                    raise ValueError(f"Cannot parse '{IDStrSplit[1]}' as Sample ID or Check Digit")

            elif len(IDStrSplit)==3:
                #dataLogger.debug("SampleID(): Three pieces of data found. Running all tests.")
                assert len(IDStrSplit[0]) == 2
                self.Year = int(IDStrSplit[0])

                assert len(IDStrSplit[1]) == 7
                self.LabNumber = int(IDStrSplit[1])

                assert len(IDStrSplit[2]) == 1
                self.CheckChar= IDStrSplit[2]

            if not self.Year:
                #dataLogger.debug("SampleID(): Year not found, using current.")
                self.Year = int(datetime.datetime.now().strftime("%y"))
            if not self.CheckChar:
                #dataLogger.debug("SampleID(): Check digit not present, estimating.")
                self.iterate_check_digit()

            if not self.LabNumber:
                raise ValueError("No ID Number assigned after parsing, sample cannot be identified.")

            #dataLogger.debug(f"SampleID(): ID '{str(self)}' assembled. ID is: {['Not Valid', 'Valid'][self.validate()]}")
            self.AsText = str(self)

        except (AssertionError, ValueError):
            dataLogger.debug(f"SampleID(): ID parsing failed for {IDStr}.")

    def __str__(self) -> str:
        if self.Override:
            return self.AsText
        if self.LabNumber:
            return f"{self.Year}.{self.LabNumber:07}.{self.CheckChar}" #Without padding of ID Number to 10 positions, the validation will not work correctly
        return f"{self.Year}.{self.LabNumber}.{self.CheckChar}" #Without padding of ID Number to 10 positions, the validation will not work correctly

    def __repr__(self) -> str:
        if self.Override:
            return f"SampleID(\"{self.AsText}\", Override=True)"
        return(f"SampleID(\"A,{self.Year}.{self.LabNumber}.{self.CheckChar}\")")

    def __gt__(self, other) -> bool:
        if not isinstance(other, SampleID):
            raise TypeError(f"Cannot compare SampleID with {type(other)}")
        
        if self.Override or other.Override:
            return str(self) > str(other)

        if self.Year != other.Year:
            return self.Year > other.Year

        if self.LabNumber != other.LabNumber:
            return self.LabNumber > other.LabNumber

        return False

    def __eq__(self, other) -> bool:
        if not isinstance(other, SampleID):
            raise TypeError(f"Cannot compare SampleID with {type(other)}")

        if self.Override or other.Override:
            return str(self) == str(other)

        if self.CheckChar != other.CheckChar:
            return False

        if self.Year != other.Year:
            return False

        if self.LabNumber != other.LabNumber:
            return False

        return True

    """Function to check sample IDs, replicating TelePath's check digit algorithm  """
    def validate(self) -> bool:
        assert self.Year
        assert self.LabNumber
        assert self.CheckChar

        if self.Override:
            return config.LOCALISATION.check_sample_id(self.AsText)

        sID = str(self).replace(".", "")
        if (len(sID)!=10):
            dataLogger.error("SampleID '%s' should be 10 charactes long, is %d." %(sID, len(sID)))
            return False
        sID = sID[:-1] #Remove check char
        sID = [char for char in sID]          # split into characters - year, then ID
        checkTuples = zip(range(22,13,-1), map(lambda x: int(x), sID))      # Each number of the sample ID gets multiplied by 22..14, go to 13 to get full length
        checkTuples = list(map(lambda x: x[0]*x[1], checkTuples))           # Multiply.
        checkSum    = sum(checkTuples)                                      # Calculate Sum...
        checkDig    = SampleID.CHECK_INT - (checkSum % SampleID.CHECK_INT)  # Check digit is 23 - (sum %% 23)
        checkDig    = SampleID.CHECK_LETTERS[checkDig-1]                      # Not from the full alphabet, and not in alphabet order, however. -1 to translate into python list index
        result      = self.CheckChar==checkDig
        return result

    def iterate_check_digit(self):
        for digit in SampleID.CHECK_LETTERS:
            self.CheckChar = digit
            if self.validate(): 
                dataLogger.debug(f"iterate_check_digit(): Check digit {digit} is valid for '{self.Year}.{self.LabNumber}.?'.")
                break


"""Contains data describing a patient sample, including demographics of the patient, and Specimen Notepad"""
class Specimen():
    def __init__(self, SpecimenID:str, Override:bool=False):
        self._ID                = SampleID(SpecimenID, Override)
        self.PatientID          = None
        self.LName              = None
        self.FName              = None 
        self.DOB                = None
        self.ClinDetails        = None
        self.Collected          = None 
        self.Received           = None
        self.Sets               = []
        self.NotepadEntries     = []
        self.hasNotepadEntries  = False
        self.Location           = "None"
        self.Requestor          = "None"
        self.ReportComment      = None
        self.Comment            = None
        self.Category           = None
        self.Type               = None
        self.NHSNumber          = None
    
    def __repr__(self):
        return f"<Specimen {self.ID}, {len(self.Sets)} Set(s), {len(self.NotepadEntries)} Notepad entries>"

    def __lt__(self, other):
        assert isinstance(other, Specimen)
        if self.Collected and other.Collected:
            if isinstance(self.Collected, datetime.datetime) and isinstance(other.Collected, datetime.datetime):
                #dataLogger.debug(f"Specimen.__lt__(): Checking datetime between self ({self.Collected.strftime('%y-%m-%d %H:%M')}) and other ({other.Collected.strftime('%y-%m-%d %H:%M')})")
                return self.Collected < other.Collected
            if isinstance(self.Collected, str) and isinstance(other.Collected, str):
                #dataLogger.debug(f"Specimen.__lt__(): Checking string between self ({self.Collected}) and other ({other.Collected})")
                return self.Collected < other.Collected
        #dataLogger.debug(f"Specimen.__lt__(): Checking IDs between self ({self.ID}) and other ({other.ID})")
        return (self.ID < other.ID)
    
    @property
    def SetCodes(self): return [x.Code for x in self.Sets]

    @property
    def ID(self): return str(self._ID)

    @property
    def Results(self):
        try:
            SetResults = [x.Results for x in self.Sets]
            if SetResults:
                SetResults = list(chain.from_iterable(SetResults))
                return SetResults
            else:
                return []
        except:
            dataLogger.warning(f"Property 'Results' raised an exception for an instance of Patient {self.ID}. Please investigate. Returning None.")
            return [] #TODO Probably shouldn't fail silently?

    @staticmethod
    def parse_datetime_with_NotKnown(string) -> datetime.datetime:
        if (string == None):
            return datetime.datetime(year=1900, month=1, day=1, hour=0, minute=1) 
        try:
            tmp = datetime.datetime.strptime(string, "%H:%M %d.%m.%y")
            return tmp
        except:
            strList = [x for x in string.split(" ") if x != ""]
            if not len(strList)==2: return datetime.datetime.min
            try:
                if strList[0]=="NK":                    # Time is now known
                    if (strList[1]=="NK"):              # Date is also not known
                        return datetime.datetime(year=1900, month=1, day=1, hour=0, minute=1) 
                    else:                               # We have a date but no time, which is fine
                        return datetime.datetime.strptime("00:00 %s" % strList[1], "%H:%M %d.%m.%y")
                if strList[1]=="NK":                    # Doubtful we should ever have time but not date
                    return datetime.datetime.strptime("%s 1.1.1900" % strList[0], "%H:%M %d.%m.%y") 
            except:
                return None
    
    def get_chunks(self):
        dataLogger.debug("Specimen.get_chunks(): Returning to main menu.")
        ProfX.return_to_main_menu()
        ProfX.send(config.LOCALISATION.SPECIMENENQUIRY)
        ProfX.read_data()
        ProfX.send(self.ID)
        ProfX.read_data()
        self.from_chunks(ProfX.screen.ParsedANSI)

    def from_chunks(self, ANSIChunks:list):
        if len(ANSIChunks)==0:
            raise Exception("Specimen.from_chunks(): No chunks to process in list ANSIChunks.")
        RetrieveChunks = [x for x in range(0, len(ANSIChunks)) if ANSIChunks[x].text == "Retrieving data..."]
        if RetrieveChunks:
            LastRetrieveIndex = max( RetrieveChunks )
        else:
            LastRetrieveIndex = 0
        DataChunks = sorted([x for x in ANSIChunks[LastRetrieveIndex+1:] if x.highlighted and x.deleteMode == 0 and x.line != 6])
        #get the LAST item that mentions the sample ID, which should be the Screen refresh after "Retrieving data..."
                
        self._ID                = SampleID(Screen.chunk_or_none(DataChunks, line = 3, column = 17))
        self.PatientID          = Screen.chunk_or_none(DataChunks, line = 8, column = 1)
        #TODO: put into PATIENT object (Search for existing patient, if not make new for Registration)
        #TODO: get patient ID (registration)

        self.LName              = Screen.chunk_or_none(DataChunks, line = 8, column = 21)
        self.FName              = Screen.chunk_or_none(DataChunks, line = 8, column = 35)
        self.DOB                = Screen.chunk_or_none(DataChunks, line = 8, column = 63)
        if self.DOB:
            if "-" in self.DOB:
                _DOB = self.DOB.split("-")
                try:
                    self.DOB = datetime.date(year="19"+_DOB[2], month=_DOB[1], day=_DOB[0])
                except:
                    self.DOB = f"{_DOB[0]}/{_DOB[1]}/19{_DOB[2]}"
            else:
                try:
                    self.DOB = datetime.date.strptime(self.DOB, "%d.%m.%y")
                except:
                    pass
        
        if self.PatientID:
            if not PATIENTSTORE.has_patient(self.PatientID):
                _Patient = Patient(self.PatientID)
                _Patient.LName = self.LName
                _Patient.FName = self.FName
                _Patient.DOB = self.DOB
                PATIENTSTORE.append(_Patient)
            else:
                _Patient = PATIENTSTORE[self.PatientID]
            _Patient.add_sample(self)
        
        self.Collected            = Specimen.parse_datetime_with_NotKnown(Screen.chunk_or_none(DataChunks, line = 3, column = 67)) 
        self.Received           = Specimen.parse_datetime_with_NotKnown(Screen.chunk_or_none(DataChunks, line = 4, column = 67))
        self.Type               = Screen.chunk_or_none(DataChunks, line = 5, column = 15)
        self.Location           = Screen.chunk_or_none(DataChunks, line = 9, column = 18)
        self.Requestor          = Screen.chunk_or_none(DataChunks, line = 9, column = 55)
        self.Comment            = Screen.chunk_or_none(DataChunks, line = 6, column = 16)
        self.ReportComment      = Screen.chunk_or_none(DataChunks, line = 4, column = 16)
        
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
            self.Sets.append(TestSet(Sample=self.ID, SetIndex=index, SetCode=test, Status=status))
        
        #TelePath only highlights the specimen notepad option if entries exist; else it's part of a single chunk of options, none highlighted. So...
        if [x for x in ANSIChunks if (x.text=="spc N'pad" and x.highlighted)]: 
            self.hasNotepadEntries = True
        
    #TODO - are these still needed?
    def get_set_index(self, code):
        if code not in self.SetCodes: return -1
        if len(self.Sets) == 0: raise IndexError("No tests are registered with this Specimen")
        #results = list(map(lambda y: y[0], filter(lambda x: x[1]==code, self.Tests)))
        Indices = [x.Index for x in self.Sets if x.Code==code]
        if len(Indices)==1 : return Indices[0]
        return Indices
    
    def get_set_status(self, code):
        if code not in self.SetCodes: return -1
        if len(self.Sets) == 0: raise IndexError("No tests are registered with this Specimen")
        #results = list(map(lambda y: y[2], filter(lambda x: x[1]==code, self.Tests)))
        Statuses = [x.Status for x in self.Sets if x.Code==code]
        if len(Statuses)==1 : return Statuses[0]
        return Statuses
    
    def validate_ID(self) -> bool: return self._ID.validate()
    
    
"""Contains data pertaining to a patient. PII-heavy, DO NOT EXPORT"""
class Patient():
    def __init__(self, ID):
        #TODO: Add to PatientContainer, check for duplicate/pre-existing. Merge PID?
        self.ID = ID
        self.Samples = []
        self.FName = None
        self.LName = None
        self.DOB = None
        self.Sex = None
        self.Gender = None
        self.NHSNumber = None
        if not PATIENTSTORE.has_patient(self.ID):
            PATIENTSTORE[self.ID] = self
        else:
            other = PATIENTSTORE[self.ID]
            self.cross_complete(other) 
            PATIENTSTORE[self.ID] = self #Should overwrite (well, re-link) duplicate object with existing one?
            del(other)

    def __eq__(self, other):
        if self.ID != other.ID: return False
        if self.DOB != other.DOB: return False
        if self.FName != other.FName: return False
        if self.LName != other.LName: return False
        if self.Sex != other.Sex: return False # this feels gross to write tbh
        return True

    def cross_complete(self, other):
        #We don't have a "last edited on" marker on these entries, so...
        try:
            assert self.ID == other.ID
            if self.DOB and other.DOB:
                if type(self.DOB) == "datetime" and type(other.DOB) == "datetime": 
                    assert self.DOB == other.DOB
        
        except AssertionError:
            dataLogger.error(f"cross_complete(): Patient Objects {self} and {other} have ID or DOB mismatch. Aborting.")
            return

        if not self.FName and other.FName:
            self.FName = other.FName
        if not self.LName and other.LName:            
            self.LName = other.LName        
        if not self.NHSNumber and other.NHSNumber: 
            self.NHSNumber = other.NHSNumber

        for otherSample in other.Samples:
            if otherSample in self.Samples: continue
            self.Samples.append(otherSample)
                            
    def create_plot(self, FilterAnalytes:list=None, firstDate:datetime.datetime=None, lastDate:datetime.datetime=None, nMinPoints:int=1):
        #TODO: Allow date limination? firstDate, lastDate, simple filter call when selecting Data
        Data = list(chain.from_iterable([x.Results for x in self.Samples]))
        Data = [x for x in Data if x.Value] #Remove results without value.
        
        if FilterAnalytes:
            Analytes = Counter(FilterAnalytes)
        else:
            Analytes = Counter([x.Analyte for x in Data]) #TODO: Don't bother plotting anything with less than nMinPoints?


        fig = plt.figure()
        plt.subplots_adjust(top=0.5, wspace=0.25, left=0.25)

        FigCounter = 0
        nAnalytes = len(Analytes.keys())
        gridSize = calc_grid(nAnalytes)

        #TODO: One loop to calculate number of plots, then use pages (which seem to be thing?) or separate figures altogether

        for _Analyte in Analytes.keys():
            _SubplotData = [Result for Result in Data if Result.Analyte == _Analyte and isinstance(Result.Value, float)] #HACK to get plotting working, ignores all non-float/integer values. sorry.
            if not _SubplotData:
                continue                        
            FigCounter = FigCounter + 1
            ax = fig.add_subplot(*gridSize, FigCounter)

            ax.plot([x.SampleTaken for x in _SubplotData], [y.Value for y in _SubplotData], c="#7d7d7d", zorder=1)

            RefInterval = [z for z in REF_RANGES if z.Analyte == _Analyte]
            if RefInterval:
                #TODO: Extract values within RR, set values below RR to -INF, display is <LOQ? Force compatibility with most non-numeric values...
                RefInterval = RefInterval[0]
                ax.axhspan(ymin=RefInterval.LowerLimit, ymax=RefInterval.UpperLimit, facecolor='#2ca02c', alpha=0.3)
                CmpLower = RefInterval.LowerLimit if RefInterval.LowerLimit is not None else float('-inf')
                CmpUpper = RefInterval.UpperLimit if RefInterval.UpperLimit is not None else float('inf')
                xInRef  = [x for x in _SubplotData if x.Value >= CmpLower and x.Value <= CmpUpper]
                ax.scatter(x=[x.SampleTaken for x in xInRef], y=[x.Value for x in xInRef], label=_Analyte, s=10, c="#1f9c47", zorder=10) #Green, inside RR
                xOutRef = [x for x in _SubplotData if x.Value < CmpLower or x.Value > CmpUpper]
                ax.scatter(x=[x.SampleTaken for x in xOutRef], y=[x.Value for x in xOutRef], label=_Analyte, s=15, c="#ba1a14", zorder=10) #Red, for out of RR
            else:
                ax.scatter(x=[x.SampleTaken for x in _SubplotData], y=[x.Value for x in _SubplotData], label=_Analyte, s=10, c="#000000", zorder=10) #Black, no RR
            
            ax.set_title(_Analyte)
            ax.xaxis.set_major_formatter(mpl.dates.DateFormatter("%b-%d"))
            ax.xaxis.set_minor_formatter(mpl.dates.DateFormatter("%b-%d"))
            ax.set_ylabel(f"{_SubplotData[0].Analyte} ({_SubplotData[0].Units})") #TODO ensure all analytes have same Units
            #ax.set_xticklabels(ax.get_xticklabels(), rotation = 90)
        
        plt.show()

    def list_loaded_results(self):
        return list(chain.from_iterable([x.Results for x in self.Samples]))

    def get_n_recent_samples(self, nMaxSamples:int=10):
        def extract_specimens(samples):
            for sample in samples: #Max seven per page
                _tmpSpecimen = Specimen(sample[2]) #Should auto-append to self.Samples?
                self.add_sample(_tmpSpecimen)
                nSpecimens = len(self.Samples)
                #logging.debug(f"get_n_recent_samples(): Patient {self.ID} now contains {nSpecimens} specimens.")
                if nSpecimens == nMaxSamples+1: #len() is index 0!
                    return False
            return True

        if not self.ID or not self.LName:
            dataLogger.error(f"Either Patient ID ({self.ID}) or First Name ({self.LName}) not sufficient to search for samples. Aborting.")
            return
        ProfX.return_to_main_menu()
        ProfX.send(config.LOCALISATION.PATIENTENQUIRY)
        ProfX.read_data()
        ProfX.send(self.ID)
        ProfX.read_data()
        if not ProfX.screen.hasErrors:
            ProfX.send(self.LName[:2])
            ProfX.read_data()
            if ProfX.screen.hasErrors:
                errMsg = ProfX.screen.Errors[0]
                errMsg = errMsg[len('"No match - Name on file is'):]
                errMsg = errMsg[:errMsg.find('"')]
                self.LName = errMsg
                ProfX.send(self.FName[:1])
                ProfX.read_data()
            ProfX.send("S") #Spec select
            ProfX.send("U") #Unknown specimen
            ProfX.send('', readEcho=False) #EARLIEST
            ProfX.read_data() 
            ProfX.send('', readEcho=False) #LATEST
            ProfX.read_data()
            ProfX.send('', readEcho=False) #ALL
            ProfX.read_data() #Get specimen table
            
            while ProfX.screen.DefaultOption == "N":
                samples = process_whitespaced_table(ProfX.screen.Lines[14:-2], extract_column_widths(ProfX.screen.Lines[12]))
                if not extract_specimens(samples):
                    break
                ProfX.send('N')
                ProfX.read_data()
            ProfX.send('Q')
        ProfX.read_data()
        ProfX.send('')
        ProfX.read_data()
        dataLogger.info("Specimen(s) found. Collecting data...")
        
    def add_sample(self, new_sample):
        IDs = [str(x.ID) for x in self.Samples]
        if not new_sample.ID in IDs:
            self.Samples.append(new_sample)
        #TODO: Cross-compare sample to sample? Complete information?


"""Contains data about a Sendaway Assay - receiving location, contact, expected TAT"""
class ReferralLab():
    def __init__(self, labname, assayname, setcode, maxtat, contact, email=None):
        self.Name       = labname
        self.AssayName  = assayname
        self.SetCode    = setcode
        self.MaxTAT     = maxtat
        self.Contact    = contact
        self.Email      = email

    def __str__(self): return f"{self.AssayName} ({self.SetCode}): {self.MaxTAT}. Contact {self.Contact}"


""" Loads data from Sendaways_Database.tsv, and parses into ReferralLab() instances. Assumes consistent, tab-separated data."""
def load_sendaways_table(filePath = "./Sendaways_Database.tsv"):
    if not(os.path.exists(filePath)): raise FileNotFoundError("File '%s' does not appear to exist" % filePath)
    SAWAYS = []
    SAWAY_IO = open(filePath).readlines()
    for line in SAWAY_IO:
        tmp = line.split('\t')
        if len(tmp)<16: continue
        tmpTAT = tmp[15].strip()
        if tmpTAT == '' or tmpTAT == 'ANY': tmpTAT = "720" # 30 days by default
        email = None
        if tmp[6]:
            email = tmp[6]
        SAWAYS.append(ReferralLab(labname=tmp[2], assayname=tmp[1], setcode=tmp[0], maxtat=int(tmpTAT), contact=tmp[4], email=email))
    return SAWAYS

"""Downloads lists of samples with one or more set(s) beyond their TAT from a named Section (default:AWAY). Optionally, filters for samples by Setcode"""
def get_overdue_sets(Section:str=config.LOCALISATION.OVERDUE_AUTOMATION, SetCode:str=None, FilterSets:list=None) -> list:
    ProfX.return_to_main_menu()
    ProfX.send(config.LOCALISATION.OVERDUE_SAMPLES, quiet=True)     # Navigate to outstanding sample list
    ProfX.read_data()
    ProfX.send(Section)    # Section AUTOMATION
    ProfX.read_data()
    ProfX.send('0', quiet=True)        # Send output to screen, which in this case is then parsed as our input stream
    time.sleep(0.2)
    Samples = []
    while ProfX.screen.DefaultOption != "Q": # Parse overdue samples until there are none left to parse 
        ProfX.read_data()
        #if (len(ProfX.screen.Lines)>5):
        if (ProfX.screen.length > 5):        # #Presence of non-empty lines after four lines of header implies there are list members to parse
            samples     = process_whitespaced_table(ProfX.screen.Lines[5:-2], extract_column_widths(ProfX.screen.Lines[3]))
            for sample in samples: 
                _Set = TestSet(Sample=sample[3], SetIndex=None, SetCode=sample[5], TimeOverdue=sample[6], RequestedOn=sample[4])
                if FilterSets:
                    if _Set.Code in FilterSets:
                        continue
                _Sample = Specimen(SpecimenID=sample[3])
                _Sample.LName = sample[2]
                _Sample.Sets.append(_Set)
                Samples.append(_Sample)
        ProfX.send(ProfX.screen.DefaultOption, quiet=True)
    ProfX.send('Q', quiet=True) #for completeness' sake, and so as to not block i guess
    if SetCode is not None: 
        Samples = [x for x in Samples if SetCode in x.SetCodes]
        dataLogger.info("get_overdue_sets(): Located %s overdue samples for section '%s' with Set '%s'." % (len(Samples), Section, SetCode))
    else:
        dataLogger.info("get_overdue_sets(): Located %s overdue samples for section '%s'" % (len(Samples), Section))
    return(Samples)
           
""" Retrieves Specimen data (demographics, etc) for any Specimen object in the list SampleObjs.
    Option GetFurther also retrieves Clinical Details and NHS Number.
    Can also retreive Sets run, Set result(s), Set comments, and Specimen Notepad data.
    If FillSets is true, loads all available data, else, only attempts to complete TestSet obj present in the Specimen"""
    #TODO: Comments for Sendaways still not always coming across
def complete_specimen_data_in_obj(SampleObjs=None, GetNotepad:bool=False, GetComments:bool=False, GetFurther:bool=False, ValidateSamples:bool=True, FillSets:bool=False, FilterSets:list=None):
    if type(SampleObjs)==Specimen:
        SampleObjs = [SampleObjs]

    def extract_set_comments(SetToGet):
        ProfX.send('S', quiet=True)    # enter Set comments
        while (ProfX.screen.DefaultOption != 'B'):
            ProfX.read_data()
            CommStartLine = -1  # How many lines results take up varies from set to set!
            PossCommStartLines = range(5, ProfX.screen.length-1) #Comments start on the first line after line 5 that has *only* highlighted items in it.
            for line in PossCommStartLines:
                currentANSIs = [x for x in ProfX.screen.ParsedANSI if x.line == line and x.deleteMode == 0]
                areHighlighted = [x.highlighted for x in currentANSIs]
                if all(areHighlighted): #All elements on this line after line 5 are highlighted
                    CommStartLine = line    # thus, it is the line we want
                    break                   # and since we only need the first line that fulfills these criteria, no need to loop further
            if (CommStartLine != -1): 
                SetToGet.Comments = []
                for commentline in ProfX.screen.Lines[CommStartLine:-2]:
                    if commentline.strip():
                        SetToGet.Comments.append(commentline.strip()) # Let's just slam it in there
            ProfX.send(ProfX.screen.DefaultOption, quiet=True) 
        ProfX.read_data()

    def extract_results(SetToGet, SampleCollectionTime):
        dataLogger.debug("complete_specimen_data_in_obj(): extract_results(): Downloading results for set %s" % SetToGet.Code)
        SetHeaderWidths = extract_column_widths(ProfX.screen.Lines[6])
        SetResultData = process_whitespaced_table(ProfX.screen.Lines[7:-2], SetHeaderWidths)
    
        
        SetAuthUser = "[Not Authorized]"
        SetAuthTime = "[Not Authorized]"
        SetRepTime = "[Not Reported]"

        SetIsAuthed = False
        if SetToGet.Status:
            if SetToGet.Status[0]=="R":
                SetIsAuthed = True

        if not SetIsAuthed:
            AuthData = [x for x in ProfX.screen.ParsedANSI if x.line == 21 and x.column==0 and x.highlighted == True]
            if AuthData:
                if not AuthData[0].text.strip() == "WARNING :- these results are unauthorised":
                    SetIsAuthed = True
        
        if SetIsAuthed:
            SetAuthData = [x for x in ProfX.screen.ParsedANSI if x.line == 4 and x.highlighted == True]
            SetAuthData.sort()
            SetAuthUser = SetAuthData[1].text
            SetAuthTime = SetAuthData[0].text
            SetRepData      = [x for x in ProfX.screen.ParsedANSI if x.line == 5 and x.highlighted == True]
            if SetRepData:
                    SetRepTime = SetRepData[0].text
        
        for ResultLine in SetResultData:
            Analyte = ResultLine[0]
            Flag=None
            if Analyte[-1]=='+' or Analyte[-1]=='-':
                Analyte = ResultLine[0][:-1].strip()
                Flag = ResultLine[0][-1]
            ResObj = SetResult(Analyte=Analyte, Value=ResultLine[1], Units=ResultLine[2], SampleTaken=SampleCollectionTime, ReportedOn=SetRepTime, AuthDateTime=SetAuthTime, Flags=Flag)
            SetToGet.Results.append(ResObj)
        
        SetToGet.AuthedOn = SetAuthTime
        SetToGet.AuthedBy = SetAuthUser

    if len(SampleObjs)==0: 
        dataLogger.warning("Could not find any Samples to process. Exiting program.")
        return

    ProfX.return_to_main_menu()
    ProfX.send(config.LOCALISATION.SPECIMENENQUIRY, quiet=True) #Move to specimen inquiry 
    ProfX.read_data()
    SampleCounter = 0
    nSamples = len(SampleObjs)
    ReportInterval = max(min(250, int(nSamples*0.1)), 1)

    for Sample in SampleObjs: 
        if Sample.ID[:1] == "19":
            dataLogger.info("complete_specimen_data_in_obj(): Avoiding specimen(s) from 2019, which can induce a crash on access.")    
            continue
        #dataLogger.info(f"complete_specimen_data_in_obj(): Retrieving specimen [{Sample.ID}]...")
        if (ValidateSamples and not Sample.validate_ID()):
            dataLogger.warning("complete_specimen_data_in_obj(): Sample ID '%s' does not appear to be valid. Skipping to next..." % Sample.ID)
            continue
        ProfX.send(Sample.ID, quiet=True)
        ProfX.read_data(max_wait=400)   # And read screen.
        if (ProfX.screen.hasErrors == True):
            # Usually the error is "No such specimen"; the error shouldn't be 'incorrect format' if we ran validate_ID().
            dataLogger.warning(f"complete_specimen_data_in_obj(): '%s'" % ";".join(ProfX.screen.Errors))
        else:
            _SetCodes = Sample.SetCodes
            Sample.from_chunks(ProfX.screen.ParsedANSI)  #Parse sample data, including patient details, sets, and assigning Specimen.Collected DT.
            if FillSets == False:
                Sample.Sets = [x for x in Sample.Sets if x.Code in _SetCodes]

            if (GetNotepad == True):
                if(Sample.hasNotepadEntries == True):
                    ProfX.send('N', quiet=True)  #Open Specimen Notepad for this Sample
                    ProfX.read_data()
                    if (ProfX.screen.hasErrors == True):
                        dataLogger.warning("complete_specimen_data_in_obj(): Received error message when accessing specimen notepad for sample %s: %s" % (Sample, ";".join(ProfX.screen.Errors)))
                        ProfX.send("", quiet=True)
                        SpecimenNotepadEntries = [SpecimenNotepadEntry(ID=Sample.ID, Author="[python]", Text="[Access blocked by other users, please retry later]", Index="0", Authored="00:00 1.1.70")]
                    else:
                        SpecimenNotepadEntries = [x for x in ProfX.screen.ParsedANSI if x.line >= 8 and x.line <= 21 and x.deleteMode == 0]
                        SNObjects = []
                        for entryLine in SpecimenNotepadEntries:
                            _entryData = entryLine.text.split(" ")
                            _entryData = [x for x in _entryData if x != ""]
                            if len(_entryData) > 5:
                                #todo: this never procced, ensure it works
                                dataLogger.debug("There are likely two specimen notepad entries in line '%s'" % entryLine)
                                SNObjects.append(SpecimenNotepadEntry(_entryData[7], _entryData[6], "", _entryData[5].strip(")"), _entryData[8]+" "+_entryData[9])) #THEORETICAL - not tested yet
                            SNObjects.append(SpecimenNotepadEntry(_entryData[2], _entryData[1], "", _entryData[0].strip(")"), _entryData[3]+" "+_entryData[4]))
                        for SNEntry in SNObjects:
                            ProfX.send(SNEntry.Index, quiet=True)  # Open the entry 
                            ProfX.read_data()           # Receive data
                            #TODO: What if more than one page of text?
                            SNText = list(map(lambda x: x.text, ProfX.screen.ParsedANSI[2:-2]))
                            SNEntry.Text = ";".join(SNText)# Copy down the text and put it into the instance
                            ProfX.send("B", quiet=True)            # Go BACK, not default option QUIT 
                            time.sleep(0.1)
                            ProfX.read_data()           # Receive data
                        Sample.NotepadEntries = SNObjects
                        ProfX.send("Q", quiet=True)                # QUIT specimen notepad
                        ProfX.read_data()               # Receive data
            
            if (GetFurther == True):
                #Retrieve NHS Number and Clinical Details, which are not visible on main screen...
                ProfX.send("F", quiet=True)
                ProfX.read_data()
                ProfX.send("1", quiet=True)
                ProfX.read_data()
                Sample.NHSNumber = Screen.chunk_or_none(ProfX.screen.ParsedANSI, line=17, column=37, highlighted=True)
                
                ProfX.send("4", quiet=True)
                ProfX.read_data()   # And read screen.
                Details = ProfX.screen.Lines[11].strip()
                if Details:
                    Sample.ClinDetails = Details
                
                ProfX.send("Q", quiet=True)
                ProfX.read_data()

            if (Sample.Sets): 
                for SetToGet in Sample.Sets:
                    if FilterSets:
                        if SetToGet.Code not in FilterSets:
                            logging.debug(f"Set {SetToGet.Code} does not seem to contained in {FilterSets}")
                            continue
                    if SetToGet.Index == -1:
                        dataLogger.error("complete_specimen_data_in_obj(): Sample %s has no Set '%s'. Skipping..." % (Sample, SetToGet))
                        continue
                    ProfX.send(str(SetToGet.Index), quiet=True)
                    ProfX.read_data()

                    if (ProfX.screen.Type == "SENQ_DisplayResults"):
                        extract_results(SetToGet, Sample.Collected)
                        if ("Set com" in ProfX.screen.Options and GetComments==True):
                            extract_set_comments(SetToGet)

                    elif (ProfX.screen.Type == "SENQ_Screen3_FurtherSetInfo"): 
                        SetToGet.AuthedOn = "[Not Authorized]"
                        SetToGet.AuthedBy = "[Not Authorized]"
                        SetToGet.Results = []
                        if ("Results" in ProfX.screen.Options):
                            ProfX.send('R', quiet=True)
                            ProfX.read_data(max_wait=400)
                            extract_results(SetToGet, Sample.Collected)
                            if ("Set com" in ProfX.screen.Options and GetComments==True):
                                extract_set_comments(SetToGet)
                            ProfX.send('B', quiet=True)
                            ProfX.read_data()

                    else: dataLogger.error("complete_specimen_data_in_obj(): cannot handle screen type '%s'" % ProfX.screen.Type)

                    ProfX.send('B', quiet=True)        # Back to Specimen overview - Without the sleep, bottom half of the SENQ screen might be caught still being transmitted.
                    ProfX.read_data()
                # for SetToGet in Sets
            # if (GetSets)
            ProfX.send("", quiet=True)                 # Exit specimen
            ProfX.read_data()              # Receive clean Specimen Enquiry screen
        # if/else Screen.hasError()
        SampleCounter += 1
        Pct = (SampleCounter / nSamples) * 100
        if( SampleCounter % ReportInterval == 0): 
            dataLogger.info(f"complete_specimen_data_in_obj(): {SampleCounter} of {nSamples} samples ({Pct:.2f}%) complete")
    time.sleep(0.1)
    #for Sample in Samples
    dataLogger.info("complete_specimen_data_in_obj(): All downloads complete.")

""" Supposed to retrieve the most recent n samples with a specified set, via SENQ"""
def get_recent_samples_of_set_type(Set:str, FirstDate:datetime.datetime=None, LastDate:datetime.datetime=None, nMaxSamples:int=50) -> list:
    dataLogger.info(f"get_recent_samples_of_set_type(): Starting search for [{Set}] samples.")
    ProfX.return_to_main_menu()
    ProfX.send(config.LOCALISATION.SPECIMENENQUIRY)
    ProfX.read_data()
    ProfX.send("U") #Engages search function
    ProfX.read_data()
    if FirstDate:
        ProfX.send(FirstDate.strftime("DD.MM.YY"))
    else:
        ProfX.send("")
    ProfX.read_data()
    #TODO: handle errors

    if LastDate:
        ProfX.send(LastDate.strftime("DD.MM.YY"))
    else:
        ProfX.send("")
    ProfX.read_data()
    #TODO: handle errors

    ProfX.send(Set)
    ProfX.read_data()

    ProfX.send("") # Skip location
    ProfX.send("") # Skip GP
    ProfX.send("") # Skip consultant
    ProfX.read_data() # TODO: why is everything in ONE LINE
    dataLogger.info(f"get_recent_samples_of_set_type(): Loading samples...")
    fixLines = ProfX.screen.Lines[1].split("\r\n")
    fixLines = [x for x in fixLines if x]
    col_widths = extract_column_widths(fixLines[1])
    samples = []
    while (ProfX.screen.DefaultOption == "N") and (len(samples) < nMaxSamples):
        _samples = process_whitespaced_table(fixLines[2:], col_widths)
        for x in _samples:
            samples.append("".join(x[1:3]))
        ProfX.send(ProfX.screen.DefaultOption)
        ProfX.read_data()
        fixLines = ProfX.screen.Lines[1].split("\r\n")
        fixLines = [x for x in fixLines if x]
    dataLogger.info(f"get_recent_samples_of_set_type(): Search complete. {len(samples)} samples found.")
    if len(samples) > nMaxSamples:
        return samples[:nMaxSamples]
    return samples

""" Loads simple text file and transforms it into a list of ReferenceRange objects"""
def load_reference_ranges(filePath="./Limits.txt"):
    RefRanges = []
    if not os.path.isfile(filePath):
        raise IOError
    with open(filePath, 'r') as RefRangeFile:
        for line in RefRangeFile:
            tmp = line.split("\t")
            tmp = [x.strip() for x in tmp]
            if tmp[0]=="Analyte": continue
            RefRanges.append( ReferenceRange(Analyte=tmp[0], Upper=tmp[3], Lower=tmp[2], Unit=tmp[1]) )
    return RefRanges

""" Utility function, testing for truth, otherwise returning None"""
def value_or_none(item):
    if item:
        return item
    return None

def get_outstanding_samples_for_Set(Set:str, Section:str=""):
    dataLogger.info(f"get_outstanding_samples_for_Set(): Retrieving items for Set [{Set}]")
    ProfX.return_to_main_menu()
    ProfX.send(config.LOCALISATION.OUTSTANDING_WORK)
    ProfX.read_data()
    ProfX.send(Section)
    ProfX.read_data()
    if ProfX.screen.hasErrors:
        #idk handle errors what am i a professional coder
        pass
    ProfX.send("2") # Request 'Detailed outstanding work by set'
    ProfX.send(Set)
    ProfX.read_data()
    ProfX.send("0", quiet=True) # Output on 'screen'
    time.sleep(0.2)
    OutstandingSamples = []
    tmp_table_widths = [1, 5, 20, 32, 39, 58, 61, 71, 74] # These are hardcoded because the headers seem misaligned.
    while ProfX.screen.DefaultOption != "Q":
        ProfX.read_data()
        #tmp_table_widths = extract_column_widths(ProfX.screen.Lines[4])
        tmp = process_whitespaced_table(ProfX.screen.Lines[7:-2], tmp_table_widths) #read and process screen
        for x in tmp:
            OutstandingSamples.append(x[1]) #Sample ID is in the second column; off by one makes that index 1. 
        ProfX.send(ProfX.screen.DefaultOption, quiet=True) 
    ProfX.send("Q")
    dataLogger.info(f"get_outstanding_samples_for_Set(): Located {len(OutstandingSamples)} samples.")
    return OutstandingSamples

def get_recent_history(Sample:str, nMaxSamples:int=15, FilterSets:list=None):
    Patient = sample_to_patient(Sample)
    logging.info(f"get_recent_history(): Retrieving recent samples for Patient [{Patient.ID}]")
    Patient.get_n_recent_samples(nMaxSamples=nMaxSamples)
    complete_specimen_data_in_obj(Patient.Samples, GetFurther=False, FillSets=True, ValidateSamples=False, FilterSets=FilterSets)
    logging.info("get_recent_history(): Writing to file...")
    samples_to_file(Patient.Samples)

def samples_to_file(Samples:list, FilterSets = None):
    logging.info("samples_to_file(): Writing data to file.")
    outFile = f"./{timestamp(fileFormat=True)}_TPDownload.txt"
    with open(outFile, 'w') as DATA_OUT:
        DATA_OUT.write("SampleID\tCollectionDate\tCollectionTime\tReceivedDate\tReceivedTime\tSet\tStatus\tAnalyte\tValue\tUnits\tFlags\tComments\n")
        for sample in Samples:
            OutStr = sample.ID + "\t"
            if sample.Sets:
                if sample.Collected:
                    OutStr = OutStr + sample.Collected.strftime("%d/%m/%Y") + "\t" + sample.Collected.strftime("%H:%M") + "\t"
                else:
                    OutStr = OutStr + "NA\tNA\t"

                if sample.Received:
                    OutStr = OutStr + sample.Received.strftime("%d/%m/%Y") + "\t" + sample.Received.strftime("%H:%M") + "\t"
                else:
                    OutStr = OutStr + "NA\tNA\t"

                for _set in sample.Sets:
                    if FilterSets:
                        if _set.Code not in FilterSets: 
                            continue
                    if _set.Results:
                        for _result in _set.Results:
                            ComStr = ' '.join(_set.Comments)
                            DATA_OUT.write(f"{OutStr}{_set.Code}\t{_set.Status}\t{_result}\t{ComStr}\n") #_result calls str(), which returns Analyte\tValue\tUnit
                    if sample.hasNotepadEntries == True:
                        NPadStr = "|".join([str(x) for x in sample.NotepadEntries])
                        DATA_OUT.write(f"{OutStr}\tSpecimen Notepad\t\t{NPadStr}\n")

def sample_to_patient(Sample:str):
    _tmpSample = Specimen(Sample)
    if not _tmpSample.validate_ID():
        logging.info(f"sample_to_patient(): {Sample} is not a valid specimen ID. Abort.")
        return
    complete_specimen_data_in_obj(_tmpSample, GetFurther=False, FillSets=True) #Gets patient data from SENQ
    return PATIENTSTORE[_tmpSample.PatientID] # Return patient obj


REF_RANGES = load_reference_ranges()
PATIENTSTORE = PatientContainer()