import dataclasses

@dataclasses.dataclass
class Commands:
    IBM_USER: str
    ANSWERBACK: str
    PATIENTENQUIRY: str
    SPECIMENENQUIRY: str
    UPDATE_SET_RESULT:str
    PRIVILEGES: str
    SETMAINTENANCE: str
    NPCLSETS: str
    SNPCL: str
    AUTOCOMMENTS: str
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
    check_main_screen: function
    check_sample_id: function

def default_check_main_screen(Lines:list):
    if (Lines[2]=="MainScreen"):
        return True
    return False

def default_check_sample_id(SampleID:str):
    return True

DEFAULT = Commands(
    IBM_USER="TP",
    ANSWERBACK=b"\x0D",
    PATIENTENQUIRY="ENQ_P",
    SPECIMENENQUIRY="ENQ_S",
    UPDATE_SET_RESULT="U",
    PRIVILEGES="USERS",
    SETMAINTENANCE="SETS",
    NPCLSETS="NPCL",
    SNPCL="SNPCL",
    AUTOCOMMENTS="AUTOC",
    OVERDUE_SAMPLES="OVERD",
    OVERDUE_AUTOMATION="AUTO",
    OVERDUE_SENDAWAYS="SAWAYS",
    TRAININGSYSTEM="TRAIN",
    QUIT="Q",
    SETHISTORY="H",
    NA="NA",
    RELEASE="R",
    EMPTYSTR="",
    CANCEL_ACTION="^",
    check_main_screen=default_check_main_screen,
    check_sample_id=default_check_sample_id
)