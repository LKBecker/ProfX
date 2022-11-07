#GPL-3.0-or-later

from tp_localisation import TelePath_Commands #This is used for connecting to TElePath systems.
from apex_localisation import APEX_Commands   #And this for APEX systems. In this example, we will connect to TelePath
#The commands and mnemonics supplied differ slightly for APEX users.

# Function to test if a SampleID is valid according to your local rules.
# If you don't have validation, just pass a dummy function that always return true :)
def your_sample_check(SampleID:str) -> bool:
    return True

# Function that assigns: 
#    self.Type          - The type of the screen, e.g. "MainMenu"
#    self.Options       - Available options
#    self.OptionStr     - Available options, as string
#    self.DefaultOption - the default option, either given by the lims or a neutral option
# ProfX relies on being able to recognise the main screen for most control flows (and the emergency ejector seat function)
def your_screen_check(self):
    if self.Lines[2] == "TelePath MainScreen":
        self.Type = "MainScreen"
    self.Options = ""
    self.OptionStr = ""
    self.DefaultOption = "^"

LOCALISATION = TelePath_Commands(
    LIMS_IP="192.168.0.1",                      # The IP address of the system to connect to
    LIMS_PORT=23,                               # The prt to connect to. Default: 23
    LIMS_USER="YOUR USERNAME HERE",             # LIMS username. If left blank (or set to 'YOUR PASSWORD HERE'), will ask the user to type it in when connecting
    LIMS_PW="YOUR PASSWORD HERE",               # LIMS password. If left blank (or set to 'YOUR PASSWORD HERE'), will ask the user to type it in when connecting
    IBM_USER="chm",                             # The 'username' for AIX (used to connect to the system running on AIX.)
    ANSWERBACK=b"PTERM:CHM\x0D",                # The message to send in response to \x05 (check your terminal emulator)
    NPEX_USER = "YOUR USERNAME HERE",           # The username for the NPEX website. 
    NPEX_PW   = "YOUR PASSWORD HERE",           # The password to access the NPEX website.
    PATIENTENQUIRY="ENQ_P",                     # Command to go from main menu to patient enquiry
    SPECIMENENQUIRY="ENQ_S",                    # Command to go from main menu to specimen enquiry
    UPDATE_SET_RESULT="U",                      # Enter/update result in a specimen set
    PRIVILEGES="PWRS",                          # Check/edit user accounts
    SETMAINTENANCE="MAINT",                     # Check/edit test sets
    NPCLSETS="NPC",                             # Check/edit NPCL lists
    SNPCL="SNPC",                               # Check/edit NPCL sorting/intermediates
    AUTOCOMMENTS="AUTOC",                       # Check/edit autocomments
    OUTSTANDING_WORK="W_OUT",                   # Not yet overdue but also not complete
    OVERDUE_SAMPLES="W_OVR",                    # Check overdue sets
    OVERDUE_AUTOMATION="AUTOM",                 # Overdue sets, section AUTOMATION
    OVERDUE_SENDAWAYS="AWAY",                   # Overdue sets, section SENDAWAYS
    CANCEL_REQUESTS="CANCEL",
    TRAININGSYSTEM="TRAIN",                     # Switch to training system
    SETHISTORY="H",                             # Retrieve history of a set
    QUIT="Q",                                   # Quit/Stop
    NA="NA",                                    # Value for failed assays etc
    RELEASE="R",                                # Command to release a set
    EMPTYSTR="",                                # Empty string, used to return to previous menu
    CANCEL_ACTION="^",                          # 'escape' command, cancels current action/returns to prev. screen. IMPORTANT.
    identify_screen=your_screen_check,          # This function receives the Screen and assigns its Type, OptionStr, Options, and DefaultOption
    check_sample_id=your_sample_check           # This function receives a sample ID and returns True if it's valid. Can just always return true if there is no check.
)

#You could also define different Localisations and then assign one to LOCALISATION, eg. TelePath = TelePath_Commands(...); APEX = APEX_Commands(...), LOCALISATION=APEX