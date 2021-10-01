#GPL-3.0-or-later

import dataclasses
from typing import Callable

@dataclasses.dataclass
class APEX_Commands:
    LIMS_IP:str
    LIMS_PORT:int
    LIMS_USER:str
    LIMS_PW:str
    IBM_USER: str
    ANSWERBACK: str
    NPEX_USER:str
    NPEX_PW:str
    CANCEL_ACTION: str
    NA: str
    RELEASE: str
    EMPTYSTR: str
    QUIT: str
    SPECIMEN_ENQUIRY: str
    PATIENT_ENQUIRY: str
    OUTSTANDING_WORK: str
    OVERDUE_SAMPLES: str
    OVERDUE_AUTOMATION: str
    identify_screen: Callable
    check_sample_id: Callable
