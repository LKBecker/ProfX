import config
from tp_structs import Specimen, SampleID
from bs4 import BeautifulSoup
from urllib.parse import urlencode, quote_plus
import requests
import logging

npexLogger = logging.getLogger(__name__)

#/Audit/GetAudits?SubjectID=WITH-A%2c21.7775958.R&Date=637680097018874737


NPEX_ROOT_LINK = "https://lab2lab.xlab.this.nhs.uk/Orders/Show/WITH-" #WITH-A%2c21.7775958.R for A,21.7775958.R, 404 if Sample Does Not Exist
NPEX_LOGIN_LINK = "https://lab2lab.xlab.this.nhs.uk/login/authenticate"
NPEX_SESSION = requests.session()
HAVE_LOGIN = False #TODO come up with better idea.


def get_NPEX_login():
    #Is NPEX_SESSION currnet/acitve? if no...
    npexLogger.info("get_NPEX_login(): Opening session.")
    NPEX_SESSION.get("https://lab2lab.xlab.this.nhs.uk/login")
    payload = {"username": config.NPEX_USER, "password": config.NPEX_PW, "__RequestVerificationToken": NPEX_SESSION.cookies['__RequestVerificationToken']}
    npexLogger.info("Logging into NPEX Web interface...")
    result = NPEX_SESSION.post(NPEX_LOGIN_LINK, payload)
    HAVE_LOGIN = True
    npexLogger.info("get_NPEX_login(): Complete.")
    #TODO: Check Result, raise exception if you get 403'd or time out.

def retrieve_NPEX_data(SampleID: str):
    if not HAVE_LOGIN:
        get_NPEX_login()
    Sample_URL = NPEX_ROOT_LINK + quote_plus(SampleID)
    npexLogger.debug(f"retrieve_NPEX_data(): Sample is [{Sample_URL}]")
    SampleData = NPEX_SESSION.get(Sample_URL)
    SampleDataSoup = BeautifulSoup(SampleData.text, 'html.parser')
    SpecimenTable = SampleDataSoup.find("table", id="specimen")
    PerfLabNumber = SpecimenTable.findChildren("tr")[1].p.text.split("\r\n")[2].strip()

    ResultsTable = SampleDataSoup.find("table", class_="results")

    pass

"""
<table class="specimen" id="specimen">
<tr><th>Performing Lab Number</th><td><p><i>MRI Biochemistry:</i>BG829238D</p></td></tr>

    <div class="test-body">
        
        <ul class="test-side">
            
            <li class="">
                <span class="state-icon Mapped" title="Mapped"></span>
                <span class="state-icon-header" title="15/09/2021 15:06:58">
                    Mapped</span> </li>
            
            <li class="">
                <span class="state-icon Requested" title="Requested"></span>
                <span class="state-icon-header" title="15/09/2021 15:06:58">
                    Requested</span> </li>
            
            <li class="">
                <span class="state-icon Accepted" title="Accepted"></span>
                <span class="state-icon-header" title="15/09/2021 15:06:58">
                    Accepted</span> </li>
            
            <li class="">
                <span class="state-icon Performing" title="Performing"></span>
                <span class="state-icon-header" title="16/09/2021 10:45:48">
                    Performing</span> </li>
            
            <li class="current">
                <span class="state-icon Completed" title="Completed"></span>
                <span class="state-icon-header" title="20/09/2021 16:30:29">
                    Completed</span> </li>
            
        </ul>

    <table class="results">
	<thead>
		<tr>
		<th class="result-name">Result</th>
		<th class="result-status">Status</th>
		<th class="result-value">Value</th>
		<th class="result-range">Range</th>
		<th class="result-units">Units</th>
		<th class="result-flags">Flags</th>
		</tr>
	</thead>
	<tbody>
		<tr class="result">
			<td class="result-name" rowspan="1">Faecal Immuno Test</td>
			<td class="result-status">Final</td>
			<td colspan="3" class="result-comments">
				<pre class="freetext">Specimen too old to carry out analysis</pre>
			</td>
			<td class="result-flags">
			</td>
		</tr>
		<tr>
			<td>Comment:</td>
			<td colspan="5" class="result-comment">
				<pre class="freetext">Due to method improvements, this assay is not currently\nUKAS accredited. An application for accreditation of\nthis assay is currently in process.</pre>
			</td>
		</tr>
	</tbody>
</table>
"""