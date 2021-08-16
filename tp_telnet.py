import config
import getpass
import logging
import re
import struct
import telnetlib
import time

telnetLogger = logging.getLogger(__name__)

""" Class that holds a chunk of TelePath data and digests it into ParsedANSICommands."""
class TelePathData():
    ANSICodeSplitter = re.compile("(?=\\x1b[\[|P])", flags=re.M) # "(?=\\x1b\[)"

    def __init__(self, rawText):
        self.ParsedANSICommands = []
        self.raw        = rawText
        self.parse_ansi()

    def parse_ansi(self):
        ANSIChunks          = []
        workingText         = self.raw.decode("ASCII")  #Consider decoding later, to keep \r\n as single bytes?
        #workingText         = workingText.replace("\r\n", "\n") #Does this change line length, and mess up inserts / string surgery when removed?
        firstANSICodePos    = workingText.find('\x1b[')
        if (firstANSICodePos  == -1): raise Exception("Raw text does not contain *any* ANSI control codes - is this really telnet output?")
        if (firstANSICodePos > 0): 
            telnetLogger.warning("parse_ansi(): Raw text does not begin with an ANSI control code")
            telnetLogger.debug(f"Raw text is '{workingText}'")
            #ANSIChunks.append( ANSICommand(byte1=0, byte2=0, byte3=0, command='X', text=workingText[:firstANSICodePos]) ) #Breaks! And may not be needed
            workingText = workingText[firstANSICodePos:]
        tokenized = TelePathData.ANSICodeSplitter.split(workingText)       #split remaining text into <^[byte;byte;bytecmdText>tokens
        tokenized = [x for x in tokenized if x != ""]
        for token in tokenized: ANSIChunks.append(ANSICommand.from_text(token))  #digest each token into the ANSI code, any bytes (may all be 0 and not written!) and affected text

        #Local variables to cache ANSI code instructions for text, and transcribe them into ParsedANSICommands:
        currentLine   = 1
        currentColumn = 1
        #currentColor  = "bold;bg blue;fg green" #TelePath default
        highlighted   = False
        for chunk in ANSIChunks:
            #print ("processing %s (%s)" % (chunk, chunk.cmdByte))
            if chunk.cmdByte == 'H':                #Set Cursor Position
                currentLine     = chunk.b1 - 1      # Python starts at 0, ANSI lines start at 1, let's make this ~pythonic~ by subtracting
                #currentColumn   = chunk.b2 - 1      # Same as above but for columns, though some SCP columns do start at 0!
                currentColumn   = chunk.b2      # Same as above but for columns, though some SCP columns do start at 0!
                                
            elif chunk.cmdByte == 'm':              #Select Graphic Rendition
                #if chunk.b1 == 1:   currentColor  = "bold;"
                #else:               currentColor  = "undefined;"
                #if chunk.b2 == 44:  currentColor += "bg blue;"
                #else:               currentColor += "undefined;"
                #if chunk.b3 == 32:  currentColor += "fg green;"
                #if chunk.b3 == 37:  currentColor += "fg white;"
                if chunk.b3 == 32:  highlighted = False #Let's keep it simple for now, TelePath style only.
                elif chunk.b3 == 37:  highlighted = True
                
            elif chunk.cmdByte == 'J': #Erase in Display 
                if chunk.b1 > 2: telnetLogger.error("Encountered an Erase in Display command with a byte1 value greater than 2 in TelePathData.parse_ansi(). This violates the ANSI standard; check parsing")
                _delchunk = ParsedANSICommand(currentLine, max(currentColumn,0), "", False, 2, chunk.b1) # If chunk.txt isn't nothing, we will append a 'fake' textchunk lower down.
                self.ParsedANSICommands.append(_delchunk)

            elif chunk.cmdByte == 'K': #Erase in Line
                #Erases part of the line. If n is 0 (or missing), clear from cursor to the end of the line. 
                #If n is 1, clear from cursor to beginning of the line. 
                #If n is 2, clear entire line. Cursor position does not change.
                _delchunk = ParsedANSICommand(line=currentLine, column=currentColumn, text="", highlighted=highlighted, deleteMode=1, deleteTarget=chunk.b1)
                self.ParsedANSICommands.append(_delchunk)
            
            elif chunk.cmdByte == 'tmessage': 
                telnetLogger.warning("Received PowerTerm tmessage, args '%s'" % chunk.txt)
                _tchunk = ParsedANSICommand(0, 0, chunk.txt, False, 0, 0, True) #chunk.txt contains the parameters of the tmessage function call
                self.ParsedANSICommands.append(_tchunk)
                continue

            else: telnetLogger.debug(f"Error: TelePathData.parse_ansiToText() has no specific code to handle ANSI code '{chunk.cmdByte}' ({chunk.cmd}).")

            if chunk.txt: #position/color changes will have already been performed at this point, and apply to any subsequent chunks due to being stored in local variables.
                #Making this test dependent on text len ensures nothing gets missed
                _tchunk = ParsedANSICommand(line=currentLine, column=currentColumn, text=chunk.txt, highlighted=highlighted, deleteMode=0, deleteTarget=0)
                #print(f"appending chunk <{_tchunk}>"
                self.ParsedANSICommands.append(_tchunk)
                currentColumn += len(chunk.txt) #if the next chunk does not reset position (e.g. cursor move), we need to keep up ourselves. 


""" Contains text, with surrounding ANSI codes parsed into absolute coordinates and color. These parsed commands represents an operation performed on a Screen"""
class ParsedANSICommand():
    def __init__(self, line: int, column: int, text: str, highlighted: bool = False, deleteMode: int = 0, deleteTarget : int = 0, isPTERMCmd : bool = False):
        #Delete mode: 0 - off, 1 - line, 2 - screen
        #Delete target:
        # if mode is 0: none
        # if mode is 1(line):   0 - Cursor to End Of Line,   1 - cursor to start of line,   2 - whole line
        # if mode is 2(screen): 0 - Cursor to End of Screen, 1 - Cursor to start of screen, 2 - whole screen
        if (deleteMode < 0 or deleteMode >2) : 
            raise ValueError("deleteMode must be an integer between 0 and 2 for a valid ParsedANSICommand.")
        if (deleteTarget < 0 or deleteTarget>2) : 
            raise ValueError("deleteTarget must be an integer between 0 and 2 for a valid ParsedANSICommand.")
        if (deleteMode == 0 and deleteTarget> 0) : 
            raise ValueError("deleteTarget must be 0 when deleteMode is 0, but isn't.")
        if (line < 0) : 
            raise ValueError("line must be a positive integer for a valid ParsedANSICommand.")
        if (column < 0) : 
            raise ValueError("column must be a positive integer for a valid ParsedANSICommand.")
        self.line           = line
        self.column         = column
        self.text           = text
        self.highlighted    = highlighted
        self.deleteMode     = deleteMode
        self.deleteTarget   = deleteTarget
        self.isPTERMCmd     = isPTERMCmd

    def __str__(self):  return self.text #changed from " "*self.column + self.text

    def __repr__(self): 
        if self.deleteMode > 0 :
            _delMode = [["ILLEGAL VALUE00", "ILLEGAL VALUE01", "ILLEGAL VALUE02"], ["Cursor to End of Line", "Cursor to Start of Line", "Entire Line"], 
                        ["Cursor to End of Screen", "Cursor to Start of Screen", "Whole Screen"]][self.deleteMode][self.deleteTarget]
            return (f"<Delete: {_delMode}, @ Line {self.line} Col {self.column}>")
        _highlighted = ["plain", "highlighted"][self.highlighted]
        return (f"<Line {self.line} Col {self.column} ({_highlighted}) '{self.text}'>")

    def __lt__(self, other):
        assert isinstance(other, ParsedANSICommand)
        if (self.line > other.line): 
            return False
        if (self.line < other.line): 
            return True
        if (self.column < other.column): 
            return True
        return False

    def __gt__(self, other):
        assert isinstance(other, ParsedANSICommand)
        if (self.line > other.line): 
            return True
        if (self.line < other.line): 
            return False
        if (self.column > other.column): 
            return True
        return False

    def __eq__(self, other):
        assert isinstance(other, ParsedANSICommand)
        if self.text != other.text:
            return False
        if self.highlighted != other.highlighted:
            return False
        if self.line != other.line:
            return False
        if self.column != other.column:
            return False
        return True


"""Relative ANSI control codes that handle cursor position, color changes, PowerTerm script execution, etc."""
class ANSICommand():
    ANSICode = re.compile("\\x1b\[(?P<bytes>\d{0,2};{0,1}\d{0,2};{0,1}\d{0,2};{0,1})(?P<cmd>[a-zA-Z]{1})") 
    PTERMCmd = re.compile("\\x1bP\$(?P<cmd>[a-zA-Z0-9]+) (?P<params>.+)\\x1b")
    Commands = {
        'A':'Cursor Up',
        'B':'Cursor Down',
        'C':'Cursor Forward',
        'D':'Cursor Back',
        'E':'Cursor Next Line',
        'F':'Cursor Previous Line',
        'G':'Cursor Horizontal Absolute',
        'H':'Set Cursor Position',
        'J':'Erase in Display',
        'K':'Erase in Line',
        'R':'DSR Response',
        'S':'Scroll Up',
        'T':'Scroll Down',
        'f':'Set Horizontal Vertical Position',
        'm':'Select Graphic Rendition',
        'i':'AUX Port',
        'n':'Device Status Report',
        'tmessage': "PowerTerm Popup",
        'X' : "Self-appended chunk - telnet read wrong?"}

    def __init__(self, byte1, byte2, byte3, command, text):
        self.b1 = int(byte1) if byte1 != '' else 0
        self.b2 = int(byte2) if byte1 != '' else 0
        self.b3 = int(byte3) if byte1 != '' else 0
        self.cmdByte = command
        self.cmd = ANSICommand.Commands[command]
        self.txt = text
    
    """Digests raw text into the ANSI command and the included text."""
    @staticmethod
    def from_text(text):
        ANSI = ANSICommand.ANSICode.match(text)
        if ANSI:
            ANSIBytes = ANSI.group("bytes").split(";")
            while (len(ANSIBytes)<3): ANSIBytes.append('0')
            return ANSICommand(*ANSIBytes, ANSI.group("cmd"), text[len(ANSI.group(0)):])
        else:
            PTERM = ANSICommand.PTERMCmd.match(text)
            return ANSICommand(0, 0, 0, PTERM.group("cmd"), PTERM.group("params"))
            
    def __str__(self):  return (f"<{self.cmd}: {self.b1} {self.b2} {self.b3} => '{self.txt}'>")

    def __repr__(self): return (f"<{self.cmd}: {self.b1} {self.b2} {self.b3} => '{self.txt}'>")


"""Virtual screen, on which ParsedANSICommands are assembled into their final shape."""
class Screen():
    def __init__(self):
        self.ParsedANSI     = []    # The parsed ANSI instructions, whose execution will create the current screen from self.lastScreen
        self.Lines          = []    # The result of applying all the instructions in self.ParsedANSI to self.lastScreen
        self.Text           = ""    # The screen as a single multi-line text string
        self.Type           = ""    # The type of screen, usually indiated by the text on line 1
        self.Options        = []    # The final line of the screen tends to tell users how to proceed
        self.OptionStr      = ""
        self.DefaultOption  = "^"   # This includes a default option
        self.Errors         = []
        self.hasErrors      = False
        self.CursorRow      = 0
        self.CursorCol      = 0
        self.prevScreen     = None

    def __str__(self):
        return (self.Text)

    def __repr__(self): 
        return (f"Screen({len(self.Lines)} lines, {len(self.ParsedANSI)} ANSI chunks)")

    @staticmethod
    def chunk_or_none(chunks, line, column, highlighted=None):
        if highlighted is not None:
            _chunk = [x for x in chunks if x.line == line and x.column == column and x.highlighted == highlighted]
        else:
            _chunk = [x for x in chunks if x.line == line and x.column == column]
        if _chunk:
            if len(_chunk)>1:
                telnetLogger.debug("chunk_or_none(): Multiple candidates, returning None. Please refine search criteria.")
                return None
            return _chunk[0].text
        return None

    def recognise_type(self):
        self.Type = "UNKNOWN"
        if len(self.Lines) <2 : 
            telnetLogger.warning("Screen has less than two lines?")
            return
        IDLine = self.Lines[1].strip()
        IDLineSplit = IDLine.split(" ")
        self.OptionStr = self.Lines[-1].strip()
        self.Options = [x.strip() for x in self.OptionStr.split("\\") if x != ""]
        #self.Options = list(map(lambda x: x.strip(), filter(lambda y: y != '', self.OptionStr.split("\\"))))
        tmp = re.match(".*\<([A-Z]+)\>.*$", self.Options[-1]) #Last option has a default in it, which the \\ split will not have removed
        if (tmp): 
            self.DefaultOption = tmp.group(1)
            tmp = self.Options[-1]
            self.Options[-1] = tmp[:tmp.find('<')-1].strip()

        if not IDLine: 
            telnetLogger.debug("Screen does not have an ID line; Check for error / merge problem?")
            self.Type = "ERROR/NO ID LINE"
            return
        # Attempt to identify the screen through direct matching
        if IDLine == "Specimen Enquiry. Screen 1 / Select specimen": 
            self.Type = "SENQ" #TODO Add more complex logic to recognise the type of SENQ
        elif IDLine == "Specimen Enquiry. Screen 3 / further set information": 
            self.Type = "SENQ_Screen3_FurtherSetInfo"
        elif IDLine == "Patient enquiry ---- Express results":
            self.Type = "SENQ/PENQ-ExpressEnquiry"
        elif IDLine[:len("Specimen enquiry. Display results")] == "Specimen enquiry. Display results": 
            self.Type = "SENQ_DisplayResults"
        elif IDLine == "Specimen note pad maintenance": 
            self.Type = "SpecNotepad"
        elif IDLine == "Set Definition" : 
            self.Type = "SETM_Root"
        elif IDLine == "Set Definition - Amend": 
            self.Type = "SETM_Amend"      
        elif IDLine == "Set Definition - Component tests":
            self.Type = "SETM_Tests"
        elif IDLine == "Authorisation group rule definition":
            self.Type = "SNPCL_Base"
        elif IDLine == "Authorization Intervention - Definition":
            self.Type = "NPSET_Base"
        elif IDLine == "Code directory for Interception criteria used":
            self.Type = "NPSET_^L_Screen"
        elif IDLine == "Authorization Intervention - Definition - Set":
            self.Type = "NPSET_Set"
        elif IDLine == "Auto comment / Further work / Tel. list routine setup":
            self.Type = "AUCOM_Any"
        elif IDLine == "Work beyond its turn around time":
            self.Type = "BeyondTAT"
            if self.Lines[3].split(" ")[0] == "Entry": self.Type = "BeyondTAT_Data"
        elif IDLine == "Audit Trail Information":
            self.Type = "Audit"
        elif IDLine == "Enter/edit user i.d.'s and privileges":
            self.Type = "PRIVS"
        elif IDLine == "Patient demographics":
            self.Type="SENQ/Demographics"
        elif IDLine == "Patient enquiry":
            self.Type ="PENQ"
        elif IDLine == "ON-CALL?": 
            self.Type = "ONCALL_PreMenu"
        
        #Some ID lines have variable components. We could use regex to parse them, but here, we just parse the static bits
        if self.Type == "UNKNOWN" and len(IDLineSplit)>=2:
            if IDLineSplit[-2] == "[CHM]" and IDLineSplit[0]=="Line": 
                self.Type = "MainMenu"
            elif IDLineSplit[-2] == "[CHT]" and IDLineSplit[0]=="Line": 
                self.Type = "MainMenu_Training"
            elif IDLineSplit[0] == "Request:": 
                self.Type = "ResultEntry/Auth"
            elif " ".join(IDLineSplit[:5]) == "Authorisation group rule definition for": 
                self.Type = "SNPCL_Set"
        
        if self.Type == "UNKNOWN": telnetLogger.warning("Could not identify screen '%s'" % IDLine)
        telnetLogger.debug("Screen type is <%s>" % (self.Type))
 
    def render(self):
        if (ProfX.prevScreen is not None): self.Lines = ProfX.prevScreen #Retrieve previous screen, which ANSI commands may alter
        for ANSICmd in self.ParsedANSI:
            self.CursorCol = ANSICmd.column
            self.CursorRow = ANSICmd.line

            if (ANSICmd.isPTERMCmd == True):
                self.Errors.append(ANSICmd.text)
                self.hasErrors = True
                continue
            while (len(self.Lines) <= ANSICmd.line): self.Lines.append("") #ensure the line being addressed definitely exists in the screen self.Lines

            if (ANSICmd.deleteMode > 0 and ANSICmd.text == ""): #It's a partial or total delete command, and has no text, as it should.
                if(ANSICmd.deleteMode == 1): #Delete Line Mode
                    if(ANSICmd.deleteTarget == 0): #Cursor to End Of Line
                        self.Lines[ANSICmd.line] = self.Lines[ANSICmd.line][:ANSICmd.column]
                        continue
                    if(ANSICmd.deleteTarget == 1): #Cursor to Start Of Line
                        self.Lines[ANSICmd.line] = " "*ANSICmd.column + self.Lines[ANSICmd.line][ANSICmd.column:]
                        continue
                    if(ANSICmd.deleteTarget == 2): #Whole Line
                        self.Lines[ANSICmd.line] = ""
                        continue

                if(ANSICmd.deleteMode == 2): #Delete Screen Mode
                    if(ANSICmd.deleteTarget == 0): #Cursor to End of Screen
                        tmpLine = self.Lines[ANSICmd.line][:ANSICmd.column]                       # save current line up to cursor
                        self.Lines = self.Lines[:ANSICmd.line-1]                        # remove all lines after current line (and also current line)
                        self.Lines.append(tmpLine)                                                # restore current line up to cursor position
                        continue
                    if(ANSICmd.deleteTarget == 1): #Cursor to Start Of Screen
                        tmpLine = " "*ANSICmd.column + self.Lines[ANSICmd.line][ANSICmd.column:]  # save current line
                        tmpLines = self.Lines[ANSICmd.line+1:]                                    # save all lines behind cursor
                        self.Lines = []                                                           # wipe screen    
                        while (len(self.Lines) <= ANSICmd.line-1): self.Lines.append("")# replaced erased lines before cursor
                        self.Lines.append(tmpLine)                                                # replace line up until cursor
                        for line in tmpLines: self.Lines.append(line)                             # replace lines after cursor
                        continue
                    if(ANSICmd.deleteTarget == 2): #Wipe whole screen
                        self.Lines = []                                                           # DESTROY
                        continue
      
            #Ensure implicit whitespace exists
            if (len(self.Lines[ANSICmd.line]) < ANSICmd.column):  self.Lines[ANSICmd.line] += (" "*(ANSICmd.column - len(self.Lines[ANSICmd.line])))
            
            if (ANSICmd.column < len(self.Lines[ANSICmd.line])): #if we're changing something inside the line, let's do it through string surgery
                self.Lines[ANSICmd.line] = self.Lines[ANSICmd.line][0:ANSICmd.column] + ANSICmd.text + self.Lines[ANSICmd.line][ANSICmd.column+len(ANSICmd.text):]
            else: 
                self.Lines[ANSICmd.line] += ANSICmd.text #else, we can just append

        self.Text = "\n".join(self.Lines)
        ProfX.prevScreen = self.Lines
        ProfX.screenHistory.append(self)
        ProfX.screenHistory = ProfX.screenHistory[0: min(len(ProfX.screenHistory), ProfX.SCREEN_HISTORY_LENGTH)]
        self.recognise_type()

    @property
    def cursorPosition(self):
        return (self.CursorRow, self.CursorCol)

    @property
    def length(self):
        return len(self.Lines)

    @staticmethod
    def create_from_TPData(TPData:TelePathData):
        self = Screen()
        self.ParsedANSI = TPData.ParsedANSICommands
        self.render()
        return self

    @staticmethod
    def from_text(text:str):
        TPData = TelePathData(text)
        return Screen.create_from_TPData(TPData)

    def restore_previous(self):
        if self.prevScreen is not None: 
            self.Lines = self.prevScreen.Lines
            self.Text = "\n".join(self.Lines)
        else:
            self.Lines = []
            self.Text = ""
 

"""Handles connecting to the TelePath LIMS system, performs I/O via telnet"""
class ProfX(): #Because it's a more powerful TelePath(y) user
    """ Contains methods and strutures to connect to, and exchange data with, the TelePath LIMS system """
    tn=telnetlib.Telnet()
    IP                  = config.LIMS_IP   # love 2 LAN
    PORT                = config.LIMS_PORT # technically pointless, but let's be precise
    DEBUGLEVEL          = 0                 # value >0 will show (parts of) telnet traffic on-screen, this may include your password 
    #MAX_WINDOW_WIDTH    = 5000              # Max Value: 65535
    MAX_WINDOW_WIDTH    = 128              # Max Value: 65535
    MAX_WINDOW_HEIGHT   = 5000              # 
    TERMCOUNTER         = 1                 # keeps track of how many terminal types we're already tried.
    TERMINALS           = [b"", b"VT100", b"VT102", b"NETWORK-VIRTUAL-TERMINAL", b"UNKNWN"] #A list of the different terminal types we're willing to lie and pretend we are
    LASTCMD             = b""               # stores last option being called, for purposes of knowing what subnegotiation to do (because telnetlib chops that up)
    UseTrainingSystem   = False
    textBuffer          = b""               # stores whatever was received from the socket.
    prevScreen          = None              # Holds previous screens (ANSI data without an explicit WIPE SCREEN is an edit to a previous screen)
    screen              = Screen()
    screenHistory       = []
    SCREEN_HISTORY_LENGTH = 10
   
    @staticmethod
    def return_to_main_menu(ForceReturn:bool=False, MaxTries:int=10):
        TryCounter = 0
        telnetLogger.debug("Returning to main menu...")
        TargetScreen = "MainMenu"
        if ProfX.UseTrainingSystem and not ForceReturn:
            TargetScreen = "MainMenu_Training"
        while(ProfX.screen.Type != TargetScreen and TryCounter <= MaxTries):
            ProfX.send(config.LOCALISATION.CANCEL_ACTION)
            ProfX.read_data()
            TryCounter = TryCounter+1
        if TryCounter > MaxTries:
            raise Exception(f"Could not reach main menu in {MaxTries} attempts. Check Screen.recognise_type() logic works correctly.")

    """ Handles TELNET option negotiation """
    @staticmethod
    def set_options(tsocket, command, option):
        if command == b"\xfa" and option == b"\x00": #Subnegotiation, request to send 
            #a = ProfX.tn.read_sb_data()
            #print(a)
            if ProfX.LASTCMD == b"\x18": #Negotiate terminal 
                if ProfX.DEBUGLEVEL > 0: telnetLogger.debug("Subnegotiating terminal type...")
                tsocket.send(b"%s%s\x18\x00%s%s%s" % (telnetlib.IAC, telnetlib.SB, ProfX.TERMINALS[ProfX.TERMCOUNTER], telnetlib.IAC, telnetlib.SE) ) #Declare 
                if ProfX.TERMCOUNTER < len(ProfX.TERMINALS): ProfX.TERMCOUNTER = ProfX.TERMCOUNTER + 1
                ProfX.LASTCMD = b''

            elif ProfX.LASTCMD == telnetlib.NAWS: #Negotiated window size; technically irrelevant as this is a virtual terminal
                if ProfX.DEBUGLEVEL > 0: telnetLogger.debug("Subnegotiating window size...")
                width = struct.pack('H', ProfX.MAX_WINDOW_WIDTH)
                height = struct.pack('H', ProfX.MAX_WINDOW_HEIGHT)
                tsocket.send(telnetlib.IAC + telnetlib.SB + telnetlib.NAWS + width + height + telnetlib.IAC + telnetlib.SE)
                ProfX.LASTCMD = b''

            else: telnetLogger.debug("SUBNEGOTIATE OTHER: %s" % ProfX.LASTCMD)
              
        elif option == b'\x18' and command == telnetlib.DO:
            telnetLogger.debug("Promising Terminal Type")
            tsocket.send(b"%s%s\x18" % (telnetlib.IAC, telnetlib.WILL)) # Promise we'll send a terminal type
            ProfX.LASTCMD = b'\x18'
                    
        elif command == telnetlib.WILL and option == b'\x01': tsocket.send(b"%s%s\x01" % (telnetlib.IAC, telnetlib.DO))
        elif command == telnetlib.WILL and option == b'\x03': tsocket.send(b"%s%s\x03" % (telnetlib.IAC, telnetlib.DO))

        elif command == telnetlib.DO and option == telnetlib.NAWS: 
            tsocket.send(telnetlib.IAC + telnetlib.WILL + telnetlib.NAWS)
            ProfX.LASTCMD = telnetlib.NAWS
        
        #For all commands we have not explicitly defined behaviour for, deny:
        elif command in (telnetlib.DO, telnetlib.DONT): tsocket.send(telnetlib.IAC + telnetlib.WONT + option) 
        #We refuse to do anything else
        elif command in (telnetlib.WILL, telnetlib.WONT): tsocket.send(telnetlib.IAC + telnetlib.DONT + option) 
        #We also don't care to discuss anything else. Good DAY to you, Sir. I said GOOD DAY.

    """ Connects to TelePath and logs in user, querying for Username and Password. """
    @staticmethod
    def connect(TrainingSystem=False):        
        ProfX.tn.set_option_negotiation_callback(ProfX.set_options) 
        #Register our set_options function as the resource to interpret any negotiation calls we get
        ProfX.tn.set_debuglevel(ProfX.DEBUGLEVEL)
        telnetLogger.debug("Opening connection to TelePath...")
        ProfX.tn.open(ProfX.IP, ProfX.PORT, timeout=1)
        ProfX.tn.read_until(b"login: ")
        ProfX.send(config.LOCALISATION.IBM_USER)
        telnetLogger.debug("Connected to CHEMISTRY module. Waiting for login...")
        ProfX.tn.read_until(b'\x05')
        ProfX.tn.write(config.LOCALISATION.ANSWERBACK)
        ProfX.tn.read_until(b"User ID :")
        if config.USER:
            ProfX.send(config.USER)
        else:
            user = input("Enter your TelePath username: ")
            ProfX.send(user)
            #TODO: check data returned, if username wrong re-query
        ProfX.tn.read_until(b"Password:")
        ProfX.tn.set_debuglevel(0) #Let's not echo anyone's password(s)
        if config.PW:
            ProfX.send(config.PW, quiet=True, readEcho=False)
            ProfX.tn.read_until(b"*"*len(config.PW)) #TelePath will echo the PW as *s
        else:
            PW = getpass.getpass()
            ProfX.send(PW, quiet=True, readEcho=False)
            ProfX.tn.read_until(b"*"*len(PW)) #TelePath will echo the PW as *s
        ProfX.tn.set_debuglevel(ProfX.DEBUGLEVEL) #Resume previous debugging level (if >0)
        #TODO: be able to work with errors!
        telnetLogger.debug("Connection to TelePath established. Attempting to read screen...")
        while (ProfX.screen.Type != "MainMenu"): #TODO: Localise?
            ProfX.read_data()
            telnetLogger.debug(f"connect(): Screen type is {ProfX.screen.Type}, first lines are {ProfX.screen.Lines[0:2]}")
            time.sleep(1) # Wait for ON-CALL? to go away
        if(TrainingSystem):
            ProfX.UseTrainingSystem = True
            telnetLogger.info("Connecting to training sub-system, for safe testing and development. Remember: Never test in production.")
            ProfX.send(config.LOCALISATION.TRAININGSYSTEM)
            ProfX.read_data()

    """
    Reads in all available data and parses it into a screen, deposited in ProfX.screen, and associated ParsedANSIChunks.
    max_wait under 200 appears to make the system a little unstable.
    """
    @staticmethod
    def read_data(max_wait = 200, ms_input_wait = 100, wait = True): #HACK: 100 / 50?
        ProfX.textBuffer = ProfX.tn.read_very_eager() #very_eager never blocks, only returns data stripped of all TELNET control codes, negotiation, etc                              
        if ProfX.textBuffer == b'' or wait:            # we didn't get anything (yet?) but we expected something
            time.sleep(ms_input_wait/1000)          # give Telepath 500ms to get its shit together
            tmp = ProfX.tn.read_very_eager()   # try reading again
            waited = ms_input_wait
            while tmp != b'' and waited < max_wait: # read until we get nothing
                ProfX.textBuffer += tmp        # append what we got
                time.sleep(ms_input_wait/1000)      # give Telepath 500ms to get its shit together
                waited = waited + ms_input_wait     # count wait time
                tmp = ProfX.tn.read_very_eager()   # try reading again
        if ProfX.textBuffer:
            ProfX.screen = Screen.from_text(ProfX.textBuffer)
            #telnetLogger.debug("ProfX.read_data(): Constructed screen from %d ANSIChunks" % len(ProfX.screen.ParsedANSI))

    @staticmethod
    def send_raw(message, quiet=False, readEcho=True):
        try:
            if not quiet: telnetLogger.debug("Sending '%s' to TelePath" % message)
            ProfX.tn.write(message)
            if (readEcho): ProfX.tn.read_until(message)
        except OSError as OSE:
            telnetLogger.error("Error whilst attempting to send message to TelePath: %s", OSE.strerror)
        except:
            pass
    
    @staticmethod
    def send(message, quiet=False, readEcho=True, maxwait_ms=1000):
        try:
            message = str(message)
            ASCIImsg = message.encode("ASCII")+b'\x0D'
            if not quiet: telnetLogger.debug("Sending '%s' to TelePath" % message)
            ProfX.tn.write(ASCIImsg)
            if (readEcho): 
                if message:
                    if (message[0]=='^' and len(message)==2):
                        ProfX.tn.read_until(message[1].encode("ASCII"), timeout=(maxwait_ms/1000))
                    else:
                        ProfX.tn.read_until(message.encode("ASCII"), timeout=(maxwait_ms/1000))
        except OSError as OSE:
            telnetLogger.error("Error whilst attempting to send message to TelePath: %s", OSE.strerror)
    
    @staticmethod        
    def send_and_ignore(msg, quiet=False, readEcho=True):
        ProfX.send(msg, quiet, readEcho)   # 
        ProfX.tn.read_very_eager()         # Take and ignore all data being returned in response to this message

    @staticmethod
    def disconnect():
        ProfX.return_to_main_menu(ForceReturn=True)
        telnetLogger.info("disconnect(): Disconnecting.")
        ProfX.send('', readEcho=False)
        ProfX.send_raw(b'\x04', readEcho=False)         
