#GPL-3.0-or-later

import dataclasses
from typing import Callable

@dataclasses.dataclass
class APEX_Commands:
    IBM_USER: str
    ANSWERBACK: str
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
    check_main_screen: Callable
    check_sample_id: Callable
