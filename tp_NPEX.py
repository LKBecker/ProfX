#GPL-3.0-or-later

import config
from tp_structs import Specimen, SampleID
from bs4 import BeautifulSoup
from urllib.parse import urlencode, quote_plus
from tp_utils import timestamp
import requests
import logging

npexLogger = logging.getLogger(__name__)

NPEX_ROOT_LINK = "https://lab2lab.xlab.this.nhs.uk/Orders/Show/WITH-"
NPEX_LOGIN_LINK = "https://lab2lab.xlab.this.nhs.uk/login/authenticate"
NPEX_SESSION = requests.session()
HAVE_LOGIN = False #TODO come up with better idea.


class NPEX_Result():
    def __init__(self, SampleID, Set:str="", Status:str="", Value:str="", Range:str="", Units:str="", Flags:str="", Comments:list=None):
        self.ParentSample = SampleID
        self.Set = Set
        self.Status = Status
        self.Value = Value
        self.Range = Range
        self.Units = Units
        self.Flags = Flags
        self.Comments = []
        if Comments: 
            self.Comments = Comments

    def __repr__(self):
        return f"NPEX_Result(ParentSample={self.ParentSample}, Set={self.Set}, Status={self.Status}, Value={self.Value}, Range={self.Range}, Units={self.Units}, Flags={self.Flags})"


class NPEX_Entry():
    def __init__(self, SampleID:str):
        self.ID = SampleID
        self.PerformingLabID = ""
        self.AuditTrail = []
        self.Results = []

def get_NPEX_login():
    global HAVE_LOGIN
    global NPEX_SESSION
    #Is NPEX_SESSION currnet/acitve? if no...
    npexLogger.info("get_NPEX_login(): Opening session.")
    NPEX_SESSION.get("https://lab2lab.xlab.this.nhs.uk/login")
    payload = {"username": config.NPEX_USER, "password": config.NPEX_PW, "__RequestVerificationToken": NPEX_SESSION.cookies['__RequestVerificationToken']}
    npexLogger.info("Logging into NPEX Web interface...")
    result = NPEX_SESSION.post(NPEX_LOGIN_LINK, payload)
    if result.status_code == 200:
        HAVE_LOGIN = True
        npexLogger.info("get_NPEX_login(): Complete.")
        #TODO: Check Result, raise exception if you get 403'd or time out.
    else:
        raise Exception("get_NPEX_login(): Status code is not 200, could not retrieve session. Check login details and connection.")

def retrieve_NPEX_samples(Samples:list):
    data = []
    for sample in Samples:
        try:
            data.append(retrieve_NPEX_data(sample))
        except:
            continue
    with open(f'./NPEX-Extract_{timestamp(fileFormat=True)}.log', 'w') as NPEX_Outfile:
        NPEX_Outfile.write("SpecimenID\tPerforming Lab ID\tTest\tResult\tComments\tMapped\tRequested\tAccepted\tPerforming\tCompleted")
        for item in data:
            NPEX_Outfile.write(f"\n") #TODO finish
    


def retrieve_NPEX_data(SampleID: str):

    def textOrDefault(Node, ChildType, ChildClass, DefaultText=""):
        Child = Node.findChild(ChildType, class_=ChildClass)
        if Child:
            return Child.text.replace('\n', '').strip()
        return DefaultText        

    if not HAVE_LOGIN:
        get_NPEX_login()
        
    Sample_URL = NPEX_ROOT_LINK + quote_plus(SampleID)
    npexLogger.info(f"retrieve_NPEX_data(): Retrieving sample [{SampleID}].")
    SampleData = NPEX_SESSION.get(Sample_URL)                                               # Retrieves the entire NPEX Webpage
    if SampleData.status_code != 200:
        if SampleData.status_code == 400:
            npexLogger.error(f"retrieve_NPEX_data(): NPEX answered with code [400 BAD REQUEST]. Please report this error to the program author (vit GitHub).")
            raise Exception(f"retrieve_NPEX_data(): 400 BAD REQUEST for sample {SampleID}.")
        if SampleData.status_code == 403:
            npexLogger.error(f"retrieve_NPEX_data(): NPEX answered with code [403 FORBIDDEN]. Check login details and retry.")
            raise Exception(f"retrieve_NPEX_data(): 403 FORBIDDEN for user {config.NPEX_USER}.")
        if SampleData.status_code == 404:
            npexLogger.info(f"retrieve_NPEX_data(): NPEX answered with code [404 NOT FOUND]. Your sample does not exist on NPEX.")
            return []
        else:
            npexLogger.info(f"retrieve_NPEX_data(): NPEX answered with code [{SampleData.status_code}]. Your request could not be compledted.")
            raise Exception(f"retrieve_NPEX_data(): [{SampleData.status_code}] for sample [{SampleID}], user [{config.NPEX_USER}].")

    NPEXSample = NPEX_Entry(SampleID=SampleID)

    SampleDataSoup = BeautifulSoup(SampleData.text, 'html.parser')                          # Turns it into soup (a parsed tree of HTML elements more easily traversable)
    
    SpecimenTable = SampleDataSoup.find("table", id="specimen")                             # Information about the Specimen is logged in a table with id 'specimen'
    NPEXSample.PerformingLabID = SpecimenTable.findAllNext("tr")[1].p.text.split("\r\n")[2].strip()    # Such as the performing lab number (if assigned)
    AuditHistory  = SpecimenTable.findNext("ul", class_="test-side")                   # And low-level audit history (if present/completed).
    # There -is- an option to retrieve a full audit trail but nobody's requested that. Also it involved javascript so... let's not do that.
    for AuditItem in AuditHistory.findAllNext("span", class_="state-icon-header"):
        NPEXSample.AuditTrail.append( (AuditItem.text.strip(), AuditItem.attrs['title']) )                   # Here, we make tuples with (timestamp, action) for the audit trail
    
    # results are in a <table> of class results. :)
    ResultsTable = SampleDataSoup.find("table", class_="results")                           
    ResultsTableBody = ResultsTable.findChild("tbody")
    ResultRows = ResultsTableBody.findAllNext("tr", class_="result")
    for ResultRow in ResultRows:                                                            
        _name           = ResultRow.findChild("td", class_="result-name").text
        _status         = ResultRow.findChild("td", class_="result-status").text
        _value          = textOrDefault(ResultRow, ChildType="td", ChildClass="result-value")
        _range          = textOrDefault(ResultRow, ChildType="td", ChildClass="result-range")
        _comments       = [ ]
        _comment = ResultRow.findChild("td", class_="result-comments")
        if _comment:
            _comments.append(_comment.text.replace('\n', '').strip())
        _flags          = textOrDefault(ResultRow, ChildType="td", ChildClass="result-flags")
        _subComments    = ResultRow.find_next("tr").findAllNext("td", class_="result-comment")
        for secondaryComment in _subComments:           # I would just pull out all <td> object with result-xxx class, 
            _comments.append( secondaryComment.text.replace('\n', '').strip() )   # but the freetext comments are in a later row, with no name, ID, or class. 
                                                        # It's easier to process them by position.
        NPEXSample.Results.append( NPEX_Result(SampleID=SampleID, Set=_name, Status=_status, Flags=_flags, Range=_range, Value=_value, Comments=_comments) )
    
    return(NPEXSample)