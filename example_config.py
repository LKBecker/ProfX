#GPL-3.0-or-later

from tp_localisation import Commands

# Function to test if a SampleID is valid according to your local rules.
# If you don't have validation, just pass a dummy function that always return true :)
def your_sample_check(SampleID:str) -> bool:
    return True

# Function that returns True if the current screen is your TelePath instance's main menu screen
# ProfX relies on being able to recognise the main screen for most control flows (and the emergency ejector seat function)
def your_main_screen_check(ScreenLines:list) -> bool:
    if ScreenLines[1] == "TelePath MainScreen":
        return True
    return False

YOUR_HOSPITAL = Commands(
    IBM_USER="chm",                             # The 'username' for AIX
    ANSWERBACK=b"PTERM:CHM\x0D",                # The message to send in response to \x05 (check your terminal emulator)
    PATIENTENQUIRY="PENQ",                      # Command to go from main menu to patient enquiry
    SPECIMENENQUIRY="SENQ",                     # Command to go from main menu to specimen enquiry
    UPDATE_SET_RESULT="U",                      # Enter/update result in a specimen set
    PRIVILEGES="PRIVS",                         # Check/edit user accounts
    SETMAINTENANCE="SETM",                      # Check/edit test sets
    NPCLSETS="NPSET",                           # Check/edit NPCL lists
    SNPCL="SNPCL",                              # Check/edit NPCL sorting/intermediates
    AUTOCOMMENTS="AUCOM",                       # Check/edit autocomments
    OUTSTANDING_WORK="OUTS",                    # Not yet overdue but also not complete
    OVERDUE_SAMPLES="OVRW",                     # Check overdue sets
    OVERDUE_AUTOMATION="AUTO",                  # Overdue sets, section AUTOMATION
    OVERDUE_SENDAWAYS="AWAY",                   # Overdue sets, section SENDAWAYS
    TRAININGSYSTEM="TRAIN",                     # Switch to training system
    SETHISTORY="H",                             # Retrieve history of a set
    QUIT="Q",                                   # Quit/Stop
    NA="NA",                                    # Value for failed assays etc
    RELEASE="R",                                # Command to release a set
    EMPTYSTR="",                                # Empty string, used to return to previous menu
    CANCEL_ACTION="^",                          # 'Escape' command, cancels current action/returns to prev. screen. IMPORTANT.
    check_main_screen=your_main_screen_check,   # This function receives the whole screen's lines, and returns True if the screen is the main screen.
    check_sample_id=your_sample_check           # This function receives a sample ID and returns True if it's valid. Can just always return true if there is no check.
)
LOCALISATION = YOUR_HOSPITAL        # Tells the system what commands are used in your TelePath implementation

LIMS_IP = "192.168.0.1"             # The IP at which the LIMS can be reached
LIMS_PORT = 23                      # Default: 23
USER="YOUR USERNAME HERE"           # If you supply an username for the LIMS, it will be automatically used to log into TelePath, else the program will ask for one
PW="YOUR PASSWORD HERE"             # If you supply a password, it will be used automatically, else the program will ask for one