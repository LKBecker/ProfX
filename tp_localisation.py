#GPL-3.0-or-later

import dataclasses
from typing import Callable

@dataclasses.dataclass
class TelePath_Commands:
    LIMS_IP:str
    LIMS_PORT:int
    LIMS_USER:str
    LIMS_PW:str
    IBM_USER: str
    ANSWERBACK: str
    NPEX_USER:str
    NPEX_PW:str
    PATIENTENQUIRY: str
    SPECIMENENQUIRY: str
    UPDATE_SET_RESULT:str
    PRIVILEGES: str
    SETMAINTENANCE: str
    NPCLSETS: str
    SNPCL: str
    AUTOCOMMENTS: str
    OUTSTANDING_WORK: str
    OVERDUE_SAMPLES: str
    OVERDUE_AUTOMATION: str
    OVERDUE_SENDAWAYS: str
    TRAININGSYSTEM: str
    SETHISTORY: str
    CANCEL_ACTION: str
    NA: str
    RELEASE: str
    EMPTYSTR: str
    QUIT: str
    identify_screen: Callable
    check_sample_id: Callable
