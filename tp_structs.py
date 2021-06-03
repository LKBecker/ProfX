#GPL-3.0-or-later

from tp_telnet import ProfX, Screen
from tp_utils import process_whitespaced_table, extract_column_widths, calc_grid

import datetime
from itertools import chain
import logging
import matplotlib.pyplot as plt
import matplotlib as mpl
plt.style.use('ggplot')
import os.path
import time

dataLogger = logging.getLogger(__name__)

def value_or_none(item):
    if item:
        return item
    return None

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

def loadReferenceRanges(filePath="S:/CS-PATHOLOGY/BIOCHEMISTRY/Z Personal/LKBecker/STP/Limits.txt"):
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

REF_RANGES = loadReferenceRanges()

class PatientContainer():
    def __init__(self):
        self.Patients = {}

    def has_patient(self, PatientID):
        if PatientID in self.Patients.keys() : return True
        return False


PATIENTSTORE = PatientContainer()

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
class Result():
    def __init__(self, Analyte, Value=None, Units="", ReportedOn=None, Flags=None):
        self.Analyte = Analyte
        self.Value = Value #TODO: NA, less than, greater than.
        self.Units = Units
        self.Flags = Flags
        #self.AuthorisedOn = None
        #self.AuthorisedBy = None
        if ReportedOn:
            try:
                self.ReportedOn = datetime.datetime.strptime(ReportedOn, "%d.%m.%y %H:%M")
            except:
                self.ReportedOn = ReportedOn
        else: 
            self.ReportedOn = None

    def __str__(self):
        ResStr = f"{self.Analyte}: {self.Value} {self.Units}"
        if self.ReportedOn:
            if isinstance(self.ReportedOn, datetime.datetime):
                ResStr = ResStr + f"({self.ReportedOn.strftime('%y-%m-%d %H:%M')})"
        if self.Flags:
            ResStr = ResStr + f" [{self.Flags}]"
        return ResStr

    def __repr__(self):
        RepOnStr = self.ReportedOn
        if isinstance(self.ReportedOn, datetime.datetime):
            RepOnStr = self.ReportedOn.strftime("%d.%m.%Y %H:%M")
        return f"Result(Analyte={self.Analyte}, Value={self.Value}, Units={self.Units}, Flags={self.Flags}, ReportedOn={RepOnStr})"


"""Contains a (set of) test(s), any result(s), and any comment(s) for that test"""
class TestSet():
    def __init__(self, Sample:str, SetIndex:str, SetCode:str, AuthedOn:str=None, AuthedBy:str=None, Status:str=None, 
                 Results:list=None, Comments:list=None, RequestedOn:str=None, TimeOverdue:str=None, OverrideID:bool=False):
        self.Sample     = SampleID(Sample, OverrideID)
        self.Index      = SetIndex
        self.Code       = SetCode
        self.Status     = Status
        self.Results    = Results
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

    def addResult(self, resItem:Result):
        #Add result to list after checking it's not already present, or a similar result for this analyte?
        raise NotImplementedError
    
    def __repr__(self): 
        return f"TestSet(ID={str(self.Sample)}, SetIndex={self.Index}, SetCode={self.Code}, AuthedOn={self.AuthedOn}, AuthedBy={self.AuthedBy}, Status={self.Status}, ...)"
    
    def __str__(self): 
        return f"[{self.Sample}, #{self.Index}: {self.Code} ({self.Status})] - {len(self.Results)} Results, {len(self.Comments)} Comments. Authorized {self.AuthedOn} by {self.AuthedBy}."
    
    def prepare_file_format(self):
        pass
    
    def write_to_file(self):
        pass


""" Contains de-and encoding for Sample IDs (barcoded) and enables ability to sort them"""
class SampleID():
    CHECK_INT = 23
    CHECK_LETTERS = ['B', 'W', 'D', 'F', 'G', 'K', 'Q', 'V', 'Y', 'X', 'A', 'S', 'T', 'N', 'J', 'H', 'R', 'P', 'L', 'C', 'Z', 'M', 'E']

    def iterate_check_digit(self):
        for digit in SampleID.CHECK_LETTERS:
            self.CheckChar = digit
            if self.validate(): 
                dataLogger.debug(f"iterate_check_digit(): Check digit {digit} is valid for '{self.Year}.{self.LabNumber}.?'.")
                break

    def __init__(self, IDStr, Override = False):
        #Prefix, Date Part, Number Part, Check Char
        self.Prefix = "A,"
        self.Year = None
        self.LabNumber = None
        self.CheckChar = None
        self.Override = Override
        self.AsText = ""

        if Override:
            self.AsText = IDStr
            return

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
                else:
                    raise ValueError(f"Cannot parse '{IDStrSplit[1]}' as Sample ID or Check Digit")

            elif len(IDStrSplit)==3:
                dataLogger.debug("SampleID(): Three pieces of data found. Running all tests.")
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
            dataLogger.debug("SampleID(): ID parsing failed for {IDStr}.")
    
    """Function to check sample IDs, replicating TelePath's check digit algorithm  """
    def validate(self) -> bool:
        assert self.Year
        assert self.LabNumber
        assert self.CheckChar

        if self.Override:
            return False

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

    def __str__(self) -> str:
        if self.Override:
            return self.AsText
        return f"{self.Year}.{self.LabNumber:07}.{self.CheckChar}" #Without padding of ID Number to 10 positions, the validation will not work correctly

    def __repr__(self) -> str:
        if self.Override:
            return f"SampleID(\"{self.AsText}\", Override=True)"
        return(f"SampleID(\"A,{self.Year}.{self.LabNumber}.{self.CheckChar}\")")

    def __gt__(self, other) -> bool:
        assert isinstance(other, SampleID)
        
        if self.Override or other.Override:
            return str(self) > str(other)

        if self.Year > other.Year:
            return True
        if self.Year < other.Year:
            return False

        if self.LabNumber > other.LabNumber:
            return True
        if self.LabNumber < other.LabNumber:
            return False

        return False

    def __eq__(self, other) -> bool:
        assert isinstance(other, SampleID)

        if self.Override or other.Override:
            return str(self) == str(other)

        if self.CheckChar != other.CheckChar:
            return False

        if self.Year != other.Year:
            return False

        if self.LabNumber != other.LabNumber:
            return False

        return True


"""Contains data describing a patient sample, including demographics of the patient, and Specimen Notepad"""
class Specimen():

    def __init__(self, SpecimenID:str, OverrideID:bool=False):
        self._ID                 = SampleID(SpecimenID, OverrideID)
        self.LName              = None
        self.FName              = None 
        self.DOB                = None
        self.ClinDetails        = None
        self.Ordered            = None 
        self.Received           = None
        self.Sets               = []
        self.NotepadEntries     = []
        self.hasNotepadEntries  = False
    
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
    
    def from_chunks(self, ANSIChunks:list):
        LastRetrieveIndex = max( [x for x in range(0, len(ANSIChunks)) if ANSIChunks[x].text == "Retrieving data..."] )
        DataChunks = sorted([x for x in ANSIChunks[LastRetrieveIndex+1:] if x.highlighted and x.deleteMode == 0 and x.line != 6])
        #get the LAST item that mentions the sample ID, which should be the Screen refresh after "Retrieving data..."
                
        self._ID                = SampleID(Screen.chunk_or_none(DataChunks, line = 3, column = 17))

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
        self.Ordered            = Specimen.parse_datetime_with_NotKnown(Screen.chunk_or_none(DataChunks, line = 3, column = 67)) 
        self.Received           = Specimen.parse_datetime_with_NotKnown(Screen.chunk_or_none(DataChunks, line = 4, column = 67))
        self.Type               = Screen.chunk_or_none(DataChunks, line = 5, column = 15)
        
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
    
    @property
    def SetCodes(self): return [x.Code for x in self.Sets]

    @property
    def ID(self): return str(self._ID)

    @property
    def Results(self): 
        return list(chain.from_iterable([x.Results for x in self.Sets]))
        
    #TODO - are these still needed?
    def get_set_index(self, code):
        if code not in self.SetCodes: return -1
        if len(self.Sets) == 0: raise IndexError("No tests are registered with this Specimen")
        #results = list(map(lambda y: y[0], filter(lambda x: x[1]==code, self.Tests)))
        results = [x.Index for x in self.Sets if x.Code==code]
        if len(results)==1 : return results[0]
        return results
    
    def get_set_status(self, code):
        if code not in self.SetCodes: return -1
        if len(self.Sets) == 0: raise IndexError("No tests are registered with this Specimen")
        #results = list(map(lambda y: y[2], filter(lambda x: x[1]==code, self.Tests)))
        results = [x.Status for x in self.Sets if x.Code==code]
        if len(results)==1 : return results[0]
        return results
    
    def __repr__(self):
        totalResults = sum([len(x.Results) for x in self.Sets])
        return f"<Specimen {self.ID}, {len(self.Sets)} Sets with {totalResults} total results, {len(self.NotepadEntries)} Notepad entries>"

    def __lt__(self, other):
        assert isinstance(other, Specimen)
        if self.Ordered and other.Ordered:
            if isinstance(self.Ordered, datetime.datetime) and isinstance(other.Ordered, datetime.datetime):
                #dataLogger.debug(f"Specimen.__lt__(): Checking datetime between self ({self.Ordered.strftime('%y-%m-%d %H:%M')}) and other ({other.Ordered.strftime('%y-%m-%d %H:%M')})")
                return self.Ordered < other.Ordered
            if isinstance(self.Ordered, str) and isinstance(other.Ordered, str):
                #dataLogger.debug(f"Specimen.__lt__(): Checking string between self ({self.Ordered}) and other ({other.Ordered})")
                return self.Ordered < other.Ordered
        #dataLogger.debug(f"Specimen.__lt__(): Checking IDs between self ({self.ID}) and other ({other.ID})")
        return (self.ID < other.ID)
    
    def validate_ID(self) -> bool: return self._ID.validate()
    
    """
    Writes the sample, and all data contained therein, to file.
    filename - the file to write to. Default: <SampleID>.txt
    path     - the path to write to. Default: /SampleExport/
    overwrite- whether to overwrite any existing file(s), or append. Default True (overwrite).
    anonymityLevel - removes PII from output depending on level. #TODO!!
        Level 0 - full output, no removal
        Level 1 - Name removed, DOB and sex remain
        Level 2 - Name and Sex removed, DOB remains
        Level 3 - Name and DOB removed, sex remains
        Level 4 - DOB, Name, Sex removed, only sample ID remains
    """
    def write_to_file(self, filename=None, path="/SampleExport/", overwrite=True, anonymityLevel=3):
        if not filename:
            filename = f"{self.ID}.txt"
        if not os.path.exists(path):
            os.makedirs(path)
        finalPath = os.path.join(path, filename)
        dataLogger.info(f"Exporting sample {self.ID} to {finalPath}")
        outFileMode = "a"
        if overwrite:
            outFileMode = "w"
        with open(finalPath, mode=outFileMode) as outFile:
            ts = datetime.datetime.now().strftime("%y-%m-%d %H:%M")
            outFile.write(f"ProfX TelePath client. Sample data exported {ts}.")
            #TODO
            pass

    def get_recent_results(self, nMaxSample:int=20):
        ProfX.return_to_main_menu()
        ProfX.send("SENQ")
        ProfX.read_data()
        ProfX.send(self.ID)
        ProfX.read_data()
        if (ProfX.screen.hasErrors == False):
            _data = []
            assert ("xpress Enq" in ProfX.screen.Options)
            ProfX.send("E") #Activate Express Enquiry
            ProfX.read_data()
            sampleCounter = 0
            while (sampleCounter < nMaxSample) and (ProfX.screen.hasErrors == False): 
                sampleCounter = sampleCounter + 1
                #Keep scanning until either the max samples are reached or you get an error, indicating you have run out of samples
                #retrieve data, filter out delimiter lines
                _SampleData = [x for x in ProfX.screen.Lines[7:-3] if x and x != "----------------------------------------------------------------------------"]
                _SampleANSI = [x for x in ProfX.screen.ParsedANSI if x.line >=3 and x.line <= 5 and x.highlighted]
                #TODO:
                #Specimen = Screen.chunk_or_none(chunks = _SampleANSI, line = , column =)
                #CollDate = Screen.chunk_or_none(chunks = _SampleANSI, line = , column =)
            
                #Construct Specimen() instance, and populate with TestSet()? -> hard to infer code...
                #Add to Patient
             
                #assert (ProfX.screen.Type == "SENQ/PENQ-ExpressEnquiry")
            #then, try sending Earlier, check for error 
            #"No earlier requests in booking area ALL" - most common error
        
        else: #Error when sending SampleID
            _errors = " ".join(ProfX.screen.Errors)
            dataLogger.error(f"get_recent_samples(): {_errors}")
            ProfX.send("")
            ProfX.read_data()


"""Contains data pertaining to a patient. PII-heavy, DO NOT EXPORT"""
class Patient():
    def __init__(self):
        #TODO: Add to PatientContainer, check for duplicate/pre-existing. Merge PID?
        self.ID = None
        self.Samples = []
        self.FName = None
        self.LName = None
        self.DOB = None
        self.Sex = None
        self.Gender = None
        self.Notepad = []
        PATIENTSTORE[self.ID] = self

    def get_history(self, nMaxSample:int=20):
        #PENQ
        raise NotImplementedError
        
    @staticmethod
    def search_for(lname:str, fname:str, dob:str, idNo:str):
        raise NotImplementedError
    
    def createPlot(self, Analyte:str=None, firstDate:datetime.datetime=None, lastDate:datetime.datetime=None):
        #TODO: Get analyte through REPL esque menu?
        Data = [Result for Sample in self.Samples for Set in Sample.Sets for Result in Set.Results]
        if Analyte:
            Analytes = [Analyte]
        else:
            Analytes = list(set([Result.Analyte for Sample in self.Samples for Set in Sample.Sets for Result in Set.Results]))
        fig = plt.figure()
        plt.subplots_adjust(top=0.96, wspace=0.25, left=0.1)

        FigCounter = 0
        nAnalytes = len(Analytes)
        gridSize = calc_grid(nAnalytes)

        for _Analyte in Analytes:
            _Data = [Result for Result in Data if Result.Analyte == _Analyte]
                        
            FigCounter = FigCounter + 1
            ax = fig.add_subplot(*gridSize, FigCounter)

            ax.plot([x.ReportedOn for x in _Data], [x.Value for x in _Data], c="#7d7d7d", zorder=1)

            RefInterval = [x for x in REF_RANGES if x.Analyte == _Analyte]
            if RefInterval:
                RefInterval = RefInterval[0]
                ax.axhspan(ymin=RefInterval.LowerLimit, ymax=RefInterval.UpperLimit, facecolor='#2ca02c', alpha=0.3)
                xInRef  = [x for x in _Data if x.Value >= RefInterval.LowerLimit and x.Value <= RefInterval.UpperLimit]
                ax.scatter(x=[x.ReportedOn for x in xInRef], y=[x.Value for x in xInRef], label=_Analyte, s=10, c="#1f9c47", zorder=10) #Green, inside RR
                xOutRef = [x for x in _Data if x.Value < RefInterval.LowerLimit or x.Value > RefInterval.UpperLimit]
                ax.scatter(x=[x.ReportedOn for x in xOutRef], y=[x.Value for x in xOutRef], label=_Analyte, s=15, c="#ba1a14", zorder=10) #Red, for out of RR
            else:
                ax.scatter(x=[x.ReportedOn for x in _Data], y=[x.Value for x in _Data], label=_Analyte, s=10, c="#000000", zorder=10) #Black, no RR
            
            ax.set_title(_Analyte)
            ax.xaxis.set_major_formatter(mpl.dates.DateFormatter("%b-%d"))
            ax.xaxis.set_minor_formatter(mpl.dates.DateFormatter("%b-%d"))
            ax.set_ylabel(f"{_Data[0].Analyte} ({_Data[0].Units})")
            #ax.set_xticklabels(ax.get_xticklabels(), rotation = 90)
        
        plt.show()

    def get_all_results(self):
        return list(chain.from_iterable([x.Results for x in self.Samples]))

"""Contains data about a Sendaway Assay - receiving location, contact, expected TAT"""
class ReferralLab():
    def __init__(self, assayname, setcode, maxtat, contact, email=None):
        self.AssayName  = assayname
        self.Setcode    = setcode
        self.MaxTAT     = maxtat
        self.Contact    = contact
        self.Email      = email

    def __str__(self): return f"{self.AssayName} ({self.Setcode}): {self.MaxTAT}. Contact {self.Contact}"


""" Loads data from Sendaways_Database.tsv, and parses into ReferralLab() instances. Assumes consistent, tab-separated data."""
def load_sendaways_table(filePath = "S:/CS-Pathology/BIOCHEMISTRY/Z Personal/LKBecker/Code/Python/TelePath_Connect/Sendaways_Database.tsv"):
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
        SAWAYS.append(ReferralLab(assayname=tmp[1], setcode=tmp[0], maxtat=int(tmpTAT), contact=tmp[4], email=email))
    return SAWAYS

"""Downloads lists of samples with one or more set(s) beyond their TAT from a named Section (default:AWAY). Optionally, filters for samples by Setcode"""
def get_overdue_sets(Section:str="AWAY", Setcode:str=None) -> list:
    ProfX.return_to_main_menu()
    ProfX.send('OVRW', quiet=True)     # Navigate to outstanding sample list
    ProfX.read_data()
    ProfX.send(Section)    # Section AUTOMATION
    ProfX.read_data()
    ProfX.send('0', quiet=True)        # Send output to screen, which in this case is then parsed as our input stream
    time.sleep(0.5)
    Samples = []
    while ProfX.screen.DefaultOption != "Q": # Parse overdue samples until there are none left to parse 
        ProfX.read_data()
        #if (len(ProfX.screen.Lines)>5):
        if (ProfX.screen.length > 5):        # #Presence of non-empty lines after four lines of header implies there are list members to parse
            samples     = process_whitespaced_table(ProfX.screen.Lines[5:-2], extract_column_widths(ProfX.screen.Lines[3]))
            for sample in samples: 
                _Sample = Specimen(SpecimenID=sample[4])
                _Sample.LName = sample[3]
                _Set = TestSet(Sample=sample[4], SetIndex=None, SetCode=sample[6], TimeOverdue=sample[7], RequestedOn=sample[5])
                _Sample.Sets.append(_Set)
                Samples.append(_Sample)
        ProfX.send(ProfX.screen.DefaultOption, quiet=True)
    ProfX.send('Q', quiet=True) #for completeness' sake, and so as to not block i guess
    if Setcode is not None: 
        Samples = [x for x in Samples if Setcode in x.SetCodes]
        dataLogger.info("Located %s overdue samples for section '%s' with Set '%s'." % (len(Samples), Section, Setcode))
    else:
        dataLogger.info("Located %s overdue samples for section '%s'" % (len(Samples), Section))
    return(Samples)
           
""" Retrieves specimen data, by sample ID string. """
def download_specimen_data_by_id(SampleIDs=None, Sets:list=None, GetNotepad:bool=False, GetComments:bool=False, ValidateSamples:bool=True):
    raise NotImplementedError

""" Retrieves Specimen data (demographics, etc) for any Specimen object in the list SampleObjs. 
    Can also retreive tests run, test result(s), comments, and specimen notepad data.
    If FillSets is true, loads all available data, else, only attempts to complete TestSet obj present in the Specimen"""
    #TODO: Comments for Sendaways still not always coming across
def complete_specimen_data_in_obj(SampleObjs=None, GetNotepad:bool=False, GetComments:bool=False, ValidateSamples:bool=True, FillSets:bool=False, FilterSets:list=None):

    def extract_set_comments(SetToGet):
        ProfX.send('S', quiet=True)    # enter Set comments
        while (ProfX.screen.DefaultOption != 'B'): # As long as there are more comments to read (TODO: does TP default to Next Screen?)
            ProfX.read_data()
            CommStartLine = -1  # How many lines results take up varies from set to set!
            #PossCommStartLines = range(5, len(ProfX.screen.Lines)-1) #Comments start on the first line after line 5 that has no highlighted items  (or is it ONLY highlighted items?) in it.
            PossCommStartLines = range(5, ProfX.screen.length-1) #Comments start on the first line after line 5 that has no highlighted items  (or is it ONLY highlighted items?) in it.
            for line in PossCommStartLines:
                currentANSIs = [x for x in ProfX.screen.ParsedANSI if x.line == line and x.deleteMode == 0]
                areHighlighted = [x for x in currentANSIs if x.highlighted==True]
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

    def extract_results(SetToGet):
        #dataLogger.debug("complete_specimen_data_in_obj(): extract_results(): Downloading results for set %s" % SetToGet.Code)
        SetHeaderWidths = extract_column_widths(ProfX.screen.Lines[6])
        SetResults = process_whitespaced_table(ProfX.screen.Lines[7:-2], SetHeaderWidths)
        #TODO: Parse into Result Objects - Analyte, Result, Units, Flags, Comment

        AuthData = [x for x in ProfX.screen.ParsedANSI if x.line == 21 and x.column==0 and x.highlighted == True]
        SetAuthUser = "[Not Authorized]"
        SetAuthTime = "[Not Authorized]"
        if AuthData:
            if not AuthData[0].text.strip() == "WARNING :- these results are unauthorised":
                SetAuth         = [x for x in ProfX.screen.ParsedANSI if x.line == 4 and x.highlighted == True]
                SetAuthUserData     = [x for x in SetAuth if x.column == 11]
                if SetAuthUserData:
                    SetAuthUser = SetAuthUserData[0].text
                SetAuthTimeData     = [x for x in SetAuth if x.column == 29][0].text
                if SetAuthTimeData:
                    SetAuthTime = SetAuthTimeData[0].text    
        SetToGet.AuthedOn = SetAuthTime
        SetToGet.AuthedBy = SetAuthUser
        SetToGet.Results =  SetResults

    if len(SampleObjs)==0: 
        dataLogger.warning("Could not find any Samples to process. Exiting program.")
        return

    ProfX.return_to_main_menu()
    ProfX.send("SENQ", quiet=True) #Move to specimen inquiry 
    ProfX.read_data()
    SampleCounter = 0
    nSamples = len(SampleObjs)
    ReportInterval = max(min(250, int(nSamples*0.1)), 1)
    #dataLogger.info("complete_specimen_data_in_obj(): Starting specimen data download.")

    for Sample in SampleObjs: 
        dataLogger.info(f"complete_specimen_data_in_obj(): Retrieving specimen [{Sample.ID}]...")
        if (ValidateSamples and not Sample.validate_ID()):
            dataLogger.warning("complete_specimen_data_in_obj(): Sample ID '%s' does not appear to be valid. Skipping to next..." % Sample.ID)
            continue
        ProfX.send(Sample.ID, quiet=True)
        ProfX.read_data(max_wait=400)   # And read screen.
        if (ProfX.screen.hasErrors == True):
            # Usually the error is "No such specimen"; the error shouldn't be 'incorrect format' if we ran validate_ID().
            dataLogger.warning("complete_specimen_data_in_obj(): '%s'" % ";".join(ProfX.screen.Errors))
        else:
            Sample.from_chunks(ProfX.screen.ParsedANSI)  #Parse sample data, which includes patient name, DOB, location, avalable test code(s) and their status.
            #TODO: it's here that all other sets are added, and thus will be retrieved. Filter here?

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
                                #todo: this never procced but also it worked for for up to 4 entries
                                dataLogger.debug("There are likely two specimen notepad entries in line '%s'" % entryLine)
                                SNObjects.append(SpecimenNotepadEntry(_entryData[7], _entryData[6], "", _entryData[5].strip(")"), _entryData[8]+" "+_entryData[9])) #THEORETICAL - not tested yet
                            SNObjects.append(SpecimenNotepadEntry(_entryData[2], _entryData[1], "", _entryData[0].strip(")"), _entryData[3]+" "+_entryData[4]))
                        for SNEntry in SNObjects:
                            ProfX.send(SNEntry.Index, quiet=True)  # Open the entry 
                            ProfX.read_data()           # Receive data
                            #TODO: What if more than one page of text (lol)
                            SNText = list(map(lambda x: x.text, ProfX.screen.ParsedANSI[2:-2]))
                            SNEntry.Text = ";".join(SNText)# Copy down the text and put it into the instance
                            ProfX.send("B", quiet=True)            # Go BACK, not default option QUIT 
                            time.sleep(0.1)
                            ProfX.read_data()           # Receive data
                        Sample.NotepadEntries = SNObjects
                        ProfX.send("Q", quiet=True)                # QUIT specimen notepad
                        ProfX.read_data()               # Receive data
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
                        extract_results(SetToGet)
                        if ("Set com" in ProfX.screen.Options and GetComments==True):
                            extract_set_comments(SetToGet)

                    elif (ProfX.screen.Type == "SENQ_Screen3_FurtherSetInfo"): 
                        SetToGet.AuthedOn = "[Not Authorized]"
                        SetToGet.AuthedBy = "[Not Authorized]"
                        SetToGet.Results = None
                        if ("Results" in ProfX.screen.Options):
                            ProfX.send('R', quiet=True)
                            ProfX.read_data(max_wait=400)
                            extract_results(SetToGet)
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
            dataLogger.info("complete_specimen_data_in_obj(): Retrieved data for %d of %d samples (%.2f%%)"% (SampleCounter, nSamples, Pct))
    #for Sample in Samples
    dataLogger.info("complete_specimen_data_in_obj(): All downloads complete.")

""" Supposed to retrieve the most recent n samples with a specified set, via SENQ"""
def get_recent_samples_of_set_type(Set:str, nSamples:int, FirstDate:datetime.datetime) -> list:
    #SENQ
    #U
    #FirstDate or ENTER, handle error
    #SecondDAte or ENTER, handle error
    #Set,  handle error
    # enter enter enter
    #read in page, parse sample(s) (get result(s))

    pass


