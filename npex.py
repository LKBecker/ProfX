#GPL-3.0-or-later

import config
from bs4 import BeautifulSoup
from urllib.parse import urlencode, quote_plus
from utils import timestamp
import requests
import logging

npexLogger = logging.getLogger(__name__)
NPEX_ROOT_LINK = "https://lab2lab.nhs.labgnostic.com/"
NPEX_LOGIN_LINK = NPEX_ROOT_LINK + "login/authenticate/"
NPEX_DATA_LINK = NPEX_ROOT_LINK + "Orders/Show/WITH-"
NPEX_SEARCH_LINK = NPEX_ROOT_LINK + ""

NPEX_SESSION = requests.session()
HAVE_LOGIN = False #TODO come up with better idea.

if __name__ == "__main__":
    import sys
    LOGFORMAT = '%(asctime)s: %(name)-10s:%(levelname)-7s:%(message)s'
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format=LOGFORMAT) #redirects logging to stdout
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    console.setFormatter(logging.Formatter(LOGFORMAT))
    logging.getLogger().addHandler(console)

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
    NPEX_SESSION.get("https://lab2lab.xlab.this.nhs.uk/login", timeout=30)
    payload = {"username": config.LOCALISATION.NPEX_USER, "password": config.LOCALISATION.NPEX_PW, "__RequestVerificationToken": NPEX_SESSION.cookies['__RequestVerificationToken']}
    npexLogger.info("Logging into NPEX Web interface...")
    result = NPEX_SESSION.post(NPEX_LOGIN_LINK, data=payload)
    if result.status_code == 200 or result.status_code == 302:
        #TODO: get NPExAuth cookie!
        HAVE_LOGIN = True
        print(NPEX_SESSION.cookies.get_dict()) # r.cookies._cookies which is a dictionary whose keys are [<domain>][<path>]
        debugCookies = [ {'name': c.name, 'value': c.value, 'domain': c.domain, 'path': c.path} for c in NPEX_SESSION.cookies ]
        npexLogger.info("get_NPEX_login(): Complete.")

        #TODO: Check Result, raise exception if you get 403'd or time out.
    else:
        raise Exception("get_NPEX_login(): Status code is not 200, could not retrieve session. Check login details and connection.")

def retrieve_NPEX_samples(Samples:list):
    headerStr = "SpecimenID\tPerforming Lab ID\tTest\tStatus\tResult\tComments\n"
    data = []
    for sample in Samples:
        try:
            item = retrieve_NPEX_data(sample)
            data.append(item)
        except Exception as e: 
            print(e)
            continue

    with open(f'./NPEX-Extract_{timestamp(fileFormat=True)}.log', 'w') as NPEX_Outfile:
        NPEX_Outfile.write(headerStr)
        print(headerStr, end='')
        for sample in data:
            parentStr = f"{sample.ID}\t{sample.PerformingLabID}\t"
            for result in sample.Results:
                finalStr = parentStr+ f"{result.Set}\t{result.Status}\t{result.Value}\t{' '.join(result.Comments)}\n"
                NPEX_Outfile.write(finalStr)
                print(finalStr, end = '')

def retrieve_NPEX_data(SampleID: str):

    def textOrDefault(Node, ChildType, ChildClass, DefaultText=""):
        Child = Node.findChild(ChildType, class_=ChildClass)
        if Child:
            return Child.text.replace('\n', '').strip()
        return DefaultText        

    if not HAVE_LOGIN:
        get_NPEX_login()

    if not HAVE_LOGIN:
        raise Exception("Cannot obtain NPEX login. Please retry or reprogram.")
        
    Sample_URL = NPEX_ROOT_LINK + quote_plus(SampleID)
    payload = { "__RequestVerificationToken": NPEX_SESSION.cookies['__RequestVerificationToken']} 
    SampleData = NPEX_SESSION.get(Sample_URL, data=payload)                                               # Retrieves the entire NPEX Webpage
    NPEXSample = NPEX_Entry(SampleID=SampleID)
    if SampleData.status_code != 200:
        if SampleData.status_code == 400:
            npexLogger.error(f"retrieve_NPEX_data(): NPEX answered with code [400 BAD REQUEST]. Please report this error to the program author (vit GitHub).")
            raise Exception(f"retrieve_NPEX_data(): 400 BAD REQUEST for sample {SampleID}.")
        if SampleData.status_code == 403:
            npexLogger.error(f"retrieve_NPEX_data(): NPEX answered with code [403 FORBIDDEN]. Check login details and retry.")
            raise Exception(f"retrieve_NPEX_data(): 403 FORBIDDEN for user {config.LOCALISATION.NPEX_USER}.")
        if SampleData.status_code == 404:
            npexLogger.info(f"retrieve_NPEX_data(): NPEX answered with code [404 NOT FOUND]. Your sample does not exist on NPEX.")
            return NPEXSample
        else:
            npexLogger.info(f"retrieve_NPEX_data(): NPEX answered with code [{SampleData.status_code}]. Your request could not be compledted.")
            raise Exception(f"retrieve_NPEX_data(): [{SampleData.status_code}] for sample [{SampleID}], user [{config.LOCALISATION.NPEX_USER}].")

    SampleDataSoup = BeautifulSoup(SampleData.text, 'html.parser')                          # Turns it into soup (a parsed tree of HTML elements more easily traversable)

    SpecimenTable = SampleDataSoup.find("table", id="specimen")                             # Information about the Specimen is logged in a table with id 'specimen'
    if not SpecimenTable:
        raise Exception("Could not find specimen table. Was a webpage retrieved?")
    NPEXSample.PerformingLabID = SpecimenTable.findAllNext("tr")[1].p.text.split("\r\n")[2].strip()    # Such as the specimen ID at the performing lab lab number (if assigned)
    AuditHistory  = SpecimenTable.findNext("ul", class_="test-side")                   # And low-level audit history (if present/completed).
    # There -is- an option to retrieve a full audit trail but nobody's requested that. Also it involved javascript so... let's not do that.

    for AuditItem in AuditHistory.findAllNext("span", class_="state-icon-header"):
        NPEXSample.AuditTrail.append( (AuditItem.text.strip(), AuditItem.attrs['title']) )                   # Here, we make tuples with (timestamp, action) for the audit trail
    
    # results are in a <table> of class results. :)
    ResultsTable = SampleDataSoup.find("table", class_="results")      
    if ResultsTable:                     
        ResultsTableBody = ResultsTable.findChild("tbody")
        ResultRows = ResultsTableBody.findAllNext("tr", class_="result")
        for ResultRow in ResultRows:                                                            
            _name           = ResultRow.findChild("td", class_="result-name").text.strip()
            _status         = ResultRow.findChild("td", class_="result-status").text.strip()
            _value          = textOrDefault(ResultRow, ChildType="td", ChildClass="result-value")
            _range          = textOrDefault(ResultRow, ChildType="td", ChildClass="result-range")
            _comments       = [ ]
            _comment = ResultRow.findChild("td", class_="result-comments")
            if _comment:
                _comments.append(_comment.text.replace('\n', '').strip())
            _flags          = textOrDefault(ResultRow, ChildType="td", ChildClass="result-flags")
            _subComments    = ResultRow.find_next("tr").findAllNext("td", class_="result-comment")
            for secondaryComment in _subComments:           # I would just pull out all <td> object with result-xxx class, 
                _comments.append( secondaryComment.text.replace('\n', ' ').replace('  ', ' ').strip() )   # but the freetext comments are in a later row, with no name, ID, or class. 
                                                            # It's easier to process them by position.
            NPEXSample.Results.append( NPEX_Result(SampleID=SampleID, Set=_name, Status=_status, Flags=_flags, Range=_range, Value=_value, Comments=_comments) )
            #npexLogger.info(f"retrieve_NPEX_data(): Successfully retrieved sample [{SampleID}].")
    else:
        currentStatus = AuditHistory.findChild("li", class_="current")
        try:
            currentStatus = currentStatus.attrs['title']
        except KeyError:
            currentStatus = AuditHistory.findChild("li", class_="current").findChild("span").attrs['title']
        #npexLogger.info(f"retrieve_NPEX_data(): No results available for sample [{SampleID}]; current status is [{currentStatus}].")
        NPEXSample.Results.append( NPEX_Result(SampleID, "N/A", currentStatus) )
    return(NPEXSample)


if __name__ == "__main__":
    get_NPEX_login()
    retrieve_NPEX_data("21.0813761.F")

    VitsAE = [  "21.0813761.F", "21.0916611.W", "21.0760460.E", "21.0957616.F", "21.0833724.Y", 
                "21.0795603.J", "21.0817181.W", "21.0804830.W", "21.0948997.Q", "22.0093139.C", 
                "21.0757762.Q", "21.0817202.E", "22.0100944.D", "21.0757571.J", "21.0743401.J", 
                "22.0108245.A", "21.0813751.L", "22.7702826.Y", "22.0090457.Z", "22.0083143.J", 
                "22.0092365.H", "21.0857646.B", "21.0026800.N", "21.7792117.F", "21.7792118.T", 
                "21.7787926.J", "22.0050302.B", "22.0100803.B", "22.0116632.C", "21.0760477.W", 
                "22.0090443.E", "21.0859229.L", "22.0090469.B", "21.0891368.Z", "22.0116651.F", 
                "21.0798654.T", "21.7739971.C", "21.7792116.P", "21.0858661.B", "22.4413866.V", 
                "21.7789359.T", "22.0058268.K", "22.0095182.Y", "21.0907651.S", "21.3214580.A", 
                "22.0097712.Q", "21.0840943.R", "21.0798697.D", "21.7792316.Y", "21.0804383.A", 
                "22.0080407.M", "22.0093190.X", "22.0113841.J"]
    #retrieve_NPEX_samples(VitsAE)
