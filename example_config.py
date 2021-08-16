from tp_localisation import Commands

YOUR_HOSPITAL = Commands(
    IBM_USER="chm",                 # The 'username' for AIX
    ANSWERBACK=b"PTERM:CHM\x0D",    # The message to send in response to \x05 (check your terminal emulator)
    PATIENTENQUIRY="PENQ",          # Main menu command to go to patient enquiry
    SPECIMENENQUIRY="SENQ",         # Main meny cummand to go to specimen enquiry
    UPDATE_SET_RESULT="U",          # Enter/update result in a specimen set
    PRIVILEGES="PRIVS",             # Check/edit user accounts
    SETMAINTENANCE="SETM",          # Check/edit test sets
    NPCLSETS="NPSET",               # Check/edit NPCL lists
    SNPCL="SNPCL",                  # Check/edit NPCL sorting/intermediates
    AUTOCOMMENTS="AUCOM",           # Check/edit autocomments
    OVERDUE_SAMPLES="OVRW",         # Check overdue sets
    OVERDUE_AUTOMATION="AUTO",      # Overdue sets, section AUTOMATION
    OVERDUE_SENDAWAYS="AWAY",       # Overdue sets, section SENDAWAYS
    TRAININGSYSTEM="TRAIN",         # Switch to training system
    SETHISTORY="H",                 # Retrieve history of a set
    QUIT="Q",                       # Quit/Stop
    NA="NA",                        # Value for failed assays etc
    RELEASE="R",                    # Command to release a set
    EMPTYSTR="",                    # Empty string, used to return to previous menu
    CANCEL_ACTION="^"               # 'escape' command, cancels current action/returns to prev. screen. IMPORTANT.
)
LOCALISATION = YOUR_HOSPITAL        # Tells the system what commands are used in your TelePath implementation

LIMS_IP = "192.168.0.1"             # The IP at which the LIMS can be reached
LIMS_PORT = 23                      # Default: 23
USER="USER"                         # If you supply a username for the LIMS, it will be automatically used, else the program will ask the user
PW="hunter2"                        # If you supply a password, it will be used, else the program will ask the user