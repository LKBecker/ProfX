#GPL-3.0-or-later

from collections import Counter
import config
import datetime
from itertools import chain
import logging
import utils
import os.path
import time

#import matplotlib.pyplot as plt
#import matplotlib as mpl
#plt.style.use('ggplot')
#font = {'family' : 'monospace',
#        'size'   : 8}
#plt.rc('font', **font)  # pass in the font dict as kwargs

datastructLogger = logging.getLogger(__name__)

class ReferenceRange():
    def __init__(self, Analyte:str, Upper:float, Lower:float, Unit:str):
        self.UpperLimit = utils.value_or_none(Upper)
        if self.UpperLimit:
            self.UpperLimit = float(self.UpperLimit)
        self.LowerLimit = utils.value_or_none(Lower)
        if self.LowerLimit:
            self.LowerLimit = float(self.LowerLimit)
        self.Analyte    = utils.value_or_none(Analyte)
        self.Unit       = utils.value_or_none(Unit)

    def __repr__(self):
        return f"ReferenceRange(Analyte={self.Analyte}, Upper={self.UpperLimit}, Lower={self.LowerLimit}, Unit={self.Unit})"

    def __str__(self):
        return f"Reference range for {self.Analyte}: {self.LowerLimit} - {self.UpperLimit} {self.Unit}"


class SingleTypeStorageContainer():
    def __init__(self, targetType):
        self.Objects = {}
        self.TargetType = type(targetType)

    def __getitem__(self, key):
        return self.Objects[key]

    def __setitem__(self, key, item):
        self.Objects[key] = item

    def has_item(self, itemID):
        if isinstance(itemID, self.TargetType):
            itemID = str(itemID)
        if itemID in self.Objects.keys() : return True
        return False

    def append(self, Patient):
        self.Objects[str(Patient.ID)]=Patient


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
            
            if (TimeOverdue[-5:]==" mins"): 
                self.Overdue    = datetime.timedelta(minutes=int(TimeOverdue[:-5]))

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
    def __init__(self, IDStr, Override = False):
        self.Override = Override
        if self.Override:
            self._str = IDStr
            return
        self.LabNumber = ""
        self.Year = ""
        self.CheckChar = ""
        self._str = f"{self.Year}.{self.LabNumber}.{self.CheckChar}"

    def __str__(self) -> str:
        return self._str

    def __repr__(self) -> str:
        return f"SampleID(\"{self._str}\", Override={self.Override})"

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
                #datastructLogger.debug(f"Specimen.__lt__(): Checking datetime between self ({self.Collected.strftime('%y-%m-%d %H:%M')}) and other ({other.Collected.strftime('%y-%m-%d %H:%M')})")
                return self.Collected < other.Collected
            if isinstance(self.Collected, str) and isinstance(other.Collected, str):
                #datastructLogger.debug(f"Specimen.__lt__(): Checking string between self ({self.Collected}) and other ({other.Collected})")
                return self.Collected < other.Collected
        #datastructLogger.debug(f"Specimen.__lt__(): Checking IDs between self ({self.ID}) and other ({other.ID})")
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
            datastructLogger.warning(f"Property 'Results' raised an exception for an instance of Patient {self.ID}. Please investigate. Returning None.")
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
    
       
    """ Gets the set's index in the LIMP (NOT the index in sample.Sets!) """
    def get_set_index(self, code):
        if code not in self.SetCodes: return -1
        if len(self.Sets) == 0: raise IndexError("No tests are registered with this Specimen")
        Indices = [x.Index for x in self.Sets if x.Code==code]
        if len(Indices)==1 : return Indices[0]
        return Indices

    def get_set(self, code):
        if code not in self.SetCodes: return -1
        if len(self.Sets) == 0: raise IndexError("No tests are registered with this Specimen")
        return [x for x in self.Sets if x.Code==code][0]
    
    def get_set_status(self, code):
        if code not in self.SetCodes: return -1
        if len(self.Sets) == 0: raise IndexError("No tests are registered with this Specimen")
        #results = list(map(lambda y: y[2], filter(lambda x: x[1]==code, self.Tests)))
        Statuses = [x.Status for x in self.Sets if x.Code==code]
        if len(Statuses)==1 : return Statuses[0]
        return Statuses
    

"""Contains data pertaining to a patient. PII-heavy, DO NOT EXPORT"""
class Patient():
    def __init__(self, ID):
        self.ID = ID
        self.Samples = []
        self.FName = None
        self.LName = None
        self.DOB = None
        self.Sex = None
        self.Gender = None
        self.NHSNumber = None
        if not Patient.Storage.has_item(self.ID):
            Patient.Storage[self.ID] = self
        else:
            other = Patient.Storage[self.ID]
            self.cross_complete(other) 
            Patient.Storage[self.ID] = self #Should overwrite (well, re-link) duplicate object with existing one?
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
            datastructLogger.error(f"cross_complete(): Patient Objects {self} and {other} have ID or DOB mismatch. Aborting.")
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
        raise NotImplementedError("create_plot(): Not implemented yet.")
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
        gridSize = utils.calc_grid(nAnalytes)

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

""" Loads simple text file and transforms it into a list of ReferenceRange objects"""
def load_reference_ranges(filePath="./Limits.txt"):
    RefRanges = []
    if not os.path.isfile(filePath):
        logging.error(f"Missing {filePath} file in installation directory. Will not be able to use Reference Ranges for graphs.")
        return []
    with open(filePath, 'r') as RefRangeFile:
        for line in RefRangeFile:
            tmp = line.split("\t")
            tmp = [x.strip() for x in tmp]
            if tmp[0]=="Analyte": continue
            RefRanges.append( ReferenceRange(Analyte=tmp[0], Upper=tmp[3], Lower=tmp[2], Unit=tmp[1]) )
    return RefRanges

def samples_to_file(Samples:list, FilterSets = None):
    logging.info("samples_to_file(): Writing data to file.")
    outFile = f"./{utils.timestamp(fileFormat=True)}_TPDownload.txt"
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
                    OutStr = OutStr + sample.Received.strftime("%d/%m/%Y") + "\t" + sample.Received.strftime("%H:%M")
                else:
                    OutStr = OutStr + "NA\tNA"

                for _set in sample.Sets:
                    if FilterSets:
                        if _set.Code not in FilterSets: 
                            continue
                    
                    if _set.Results:
                        ComStr = ' '.join(_set.Comments)
                        for _result in _set.Results:
                            if _result.Flags:
                                DATA_OUT.write(f"{OutStr}\t{_set.Code}\t{_set.Status}\t{_result}\t{ComStr}\n") #_result calls str(), which returns Analyte\tValue\tUnit\tFlags
                            else:
                                DATA_OUT.write(f"{OutStr}\t{_set.Code}\t{_set.Status}\t{_result}\t\t{ComStr}\n") #_result calls str(), needs an extra \t if there are no flags
                    else:
                        DATA_OUT.write(f"{OutStr}\t{_set.Code}\t{_set.Status}\t\t\t\t\t\t\t\n") #_result calls str(), which returns Analyte\tValue\tUnit\tFlags
            if sample.hasNotepadEntries == True:
                NPadStr = "|".join([str(x) for x in sample.NotepadEntries])
                DATA_OUT.write(f"{OutStr}\tSpecimen Notepad\t\t\t\t\t\t{NPadStr}\n")

#REF_RANGES = load_reference_ranges()

Patient.Storage = SingleTypeStorageContainer(Patient)