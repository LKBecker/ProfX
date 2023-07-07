#GPL-3.0-or-later

import dataclasses
from typing import Callable

@dataclasses.dataclass
class Labcentre_Commands:
    LIMS_IP:str
    LIMS_PORT:int
    LIMS_USER:str
    LIMS_PW:str
    ANSWERBACK: str
    EMPTYSTR: str
    CANCEL_ACTION: str
    identify_screen: Callable
    check_sample_id: Callable
