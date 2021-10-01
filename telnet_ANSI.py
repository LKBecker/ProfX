#

"""TODO:
    Move parse_raw_ansi() into Screen and figure out how to send() from there.

"""
import config
import getpass
import logging
import re
import struct
import telnetlib
import time

telnetLogger = logging.getLogger(__name__)

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


"""Pieces of ANSI control code that handle cursor position, color changes, PowerTerm script execution, etc."""
class RawANSICommand():
    #ANSICode = re.compile("\\x1b\[(?P<bytes>\d{0,2};{0,1}\d{0,2};{0,1}\d{0,2};{0,1})(?P<cmd>[a-zA-Z]{1})")
    CSI_EscSequence = re.compile(r'\x1b\[(?P<Prm_Bytes>[\x30-\x3F]*)(?P<Imd_Bytes>[\x20-\x2F]*)(?P<FinalByte>[\x40-\x7E])') 
    nF_EscSequence =  re.compile(r'\x1b\((?P<Prm_Bytes>[\x20-\x2F]*)(?P<Imd_Bytes>[\x20-\x2F]*)(?P<FinalByte>[\x30-\x7E])') 
    #See https://en.wikipedia.org/wiki/ANSI_escape_code#CSI_(Control_Sequence_Introducer)_sequences
    #See https://vt100.net/emu/ctrlseq_dec.html
    PTERMCmd = re.compile(r'\x1bP\$(?P<cmd>[a-zA-Z0-9]+) (?P<params>.+)\\x1b')

    ORD_FINAL_PRIVSEQ_MIN = ord("p")
    ORD_FINAL_PRIVSEQ_MAX = ord("~")
    ORD_PARAM_PRIVSEQ_MIN = ord("<")
    ORD_PARAM_PRIVSEQ_MAX = ord("?")
    
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
        'X' : "Self-appended chunk - telnet read wrong?"
        }

    def __init__(self, byte1, byte2, byte3, command, text, is_private=False):
        self.private_sequence = is_private
        #Private sequences with non-numeric bytes are announced through final or parameter bytes in certain ranges:
        if command:
            if (ord(command[0]) >= RawANSICommand.ORD_FINAL_PRIVSEQ_MIN) & (ord(command[0]) <= RawANSICommand.ORD_FINAL_PRIVSEQ_MAX):
                self.private_sequence = True

        if byte1:    
            if (ord(byte1[0]) >= RawANSICommand.ORD_PARAM_PRIVSEQ_MIN) & (ord(byte1[0]) <= RawANSICommand.ORD_PARAM_PRIVSEQ_MAX):
                self.private_sequence = True

        if self.private_sequence == False:
            self.b1 = int(byte1) if byte1 else 0
            self.b2 = int(byte2) if byte1 else 0
            self.b3 = int(byte3) if byte1 else 0
            self.cmdByte = command
            self.cmd = RawANSICommand.Commands[self.cmdByte]
        else:
            self.cmdByte = byte1
            self.b1 = command
            self.b2 = 0
            self.b3 = 0
            self.cmd = "Private Sequence" #TODO: Reconsider
        
        self.txt = text
    
    """Digests raw text into the ANSI command and the included text."""
    @staticmethod
    def from_text(text):
        CSI = RawANSICommand.CSI_EscSequence.match(text)
        if CSI:
            ANSIBytes = CSI.group("Prm_Bytes").split(";")
            while (len(ANSIBytes)<3): ANSIBytes.append('0')
            return RawANSICommand(*ANSIBytes, CSI.group("FinalByte"), text[len(CSI.group(0)):])

        nF = RawANSICommand.nF_EscSequence.match(text)
        if nF:
            ANSIBytes = nF.group("Prm_Bytes").split(";")
            ANSIBytes = [x for x in ANSIBytes if x]
            while (len(ANSIBytes)<3): ANSIBytes.append('0')
            return RawANSICommand(nF.group("FinalByte"), 0, 0, ")", text[len(nF.group(0)):]) #TODO test.

        else:
            #TelePath-specific Popup commands, etc.
            PTERM = RawANSICommand.PTERMCmd.match(text)
            return RawANSICommand(0, 0, 0, PTERM.group("cmd"), PTERM.group("params"))
            
    def __str__(self):  return (f"<{self.cmd}: {self.b1} {self.b2} {self.b3} => '{self.txt}'>")

    def __repr__(self): return (f"<{self.cmd}: {self.b1} {self.b2} {self.b3} => '{self.txt}'>")


"""Virtual screen, on which ParsedANSICommands are assembled into their final shape."""
class Screen(): #TODO: does this need to be a class?
    History = []
    HISTORY_LENGTH = 5

    def __init__(self, Connection, BasedOnPrev=True):
        self.BasedOnPrev    = BasedOnPrev
        self.ParsedANSI     = []        # The parsed ANSI instructions, whose execution will create the current screen from self.lastScreen
        self.Lines          = []        # The result of applying all the instructions in self.ParsedANSI to self.lastScreen
        self.Text           = ""        # The screen as a single multi-line text string
        self.Type           = "UNKNOWN" # The type of screen, usually indiated by the text on line 1
        self.Options        = []        # The final line of the screen tends to tell users how to proceed
        self.OptionStr      = ""
        self.DefaultOption  = "^"       # This includes a default option
        self.Errors         = []
        self.hasErrors      = False
        self.CursorRow      = 0
        self.CursorCol      = 0
        self.recognise_type = config.LOCALISATION.identify_screen
        self.Connection     = Connection

    def __str__(self):
        return (self.Text)

    def __repr__(self): 
        return (f"Screen({len(self.Lines)} lines, {len(self.ParsedANSI)} ANSI chunks)")

    @staticmethod
    def prevScreen():
        return Screen.History[-1]

    @staticmethod
    def prevLines():
        return Screen.History[-1].Lines

    @property
    def cursorPosition(self):
        return (self.CursorRow, self.CursorCol)

    @property
    def length(self):
        return len(self.Lines)

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

    def parse_raw_ANSI(self, workingText):
        _ParsedANSI       = []
        if workingText == b'\x05':
            self.Connection.write(config.LOCALISATION.ANSWERBACK)
            return
        workingText         = workingText.decode("ASCII")
        firstANSICodePos    = workingText.find('\x1b[')
        if (firstANSICodePos  == -1): raise Exception("Raw text does not contain *any* ANSI control codes - is this really telnet output?")
        if (firstANSICodePos > 0): 
            telnetLogger.warning("parse(): Raw text does not begin with an ANSI control code")
            telnetLogger.debug(f"Raw text is '{workingText}'")
            workingText = workingText[firstANSICodePos:]

        RawANSI = Connection.EscapeSplitter.split(workingText)       #split remaining text into <^[byte;byte;bytecmdText>tokens
        RawANSI = [x for x in RawANSI if x != ""]
        RawANSI = [RawANSICommand.from_text(x) for x in RawANSI if x != ""]
        
        #Local variables to cache ANSI code instructions for text, and transcribe them into ParsedANSICommands:
        currentLine   = 1
        currentColumn = 1
        #currentColor  = "bold;bg blue;fg green" #APEX default
        highlighted   = False
        
        for RawANSIChunk in RawANSI:
            #print ("processing %s (%s)" % (RawANSIChunk, RawANSIChunk.cmdByte))
            if RawANSIChunk.cmdByte == 'H':                #Set Cursor Position
                currentLine     = RawANSIChunk.b1 - 1      # Python starts at 0, ANSI lines start at 1, let's make this ~pythonic~ by subtracting
                #currentColumn   = RawANSIChunk.b2 - 1      # Same as above but for columns, though some SCP columns do start at 0!
                currentColumn   = RawANSIChunk.b2      # Same as above but for columns, though some SCP columns do start at 0!
                                
            elif RawANSIChunk.cmdByte == 'm':              #Select Graphic Rendition
                #if RawANSIChunk.b1 == 1:   currentColor  = "bold;"
                #else:               currentColor  = "undefined;"
                #if RawANSIChunk.b2 == 44:  currentColor += "bg blue;"
                #else:               currentColor += "undefined;"
                #if RawANSIChunk.b3 == 32:  currentColor += "fg green;"
                #if RawANSIChunk.b3 == 37:  currentColor += "fg white;"
                if RawANSIChunk.b3 == 32:  highlighted = False #Let's keep it simple for now, APEX style only.
                elif RawANSIChunk.b3 == 37:  highlighted = True
                
            elif RawANSIChunk.cmdByte == 'J': #Erase in Display 
                if RawANSIChunk.b1 > 2: telnetLogger.error("Encountered an Erase in Display command with a byte1 value greater than 2 in RawANSI.parse(). This violates the ANSI standard; check parsing")
                _delRawANSIChunk = ParsedANSICommand(currentLine, max(currentColumn,0), "", False, 2, RawANSIChunk.b1) # If RawANSIChunk.txt isn't nothing, we will append a 'fake' textRawANSIChunk lower down.
                _ParsedANSI.append(_delRawANSIChunk)

            elif RawANSIChunk.cmdByte == 'K': #Erase in Line
                #Erases part of the line. If n is 0 (or missing), clear from cursor to the end of the line. 
                #If n is 1, clear from cursor to beginning of the line. 
                #If n is 2, clear entire line. Cursor position does not change.
                _delRawANSIChunk = ParsedANSICommand(line=currentLine, column=currentColumn, text="", highlighted=highlighted, deleteMode=1, deleteTarget=RawANSIChunk.b1)
                _ParsedANSI.append(_delRawANSIChunk)
            
            elif RawANSIChunk.cmdByte == 'tmessage': 
                telnetLogger.warning("Received PowerTerm tmessage, args '%s'" % RawANSIChunk.txt)
                _tRawANSIChunk = ParsedANSICommand(0, 0, RawANSIChunk.txt, False, 0, 0, True) #RawANSIChunk.txt contains the parameters of the tmessage function call
                _ParsedANSI.append(_tRawANSIChunk)
                continue

            elif RawANSIChunk.cmdByte == '?25':
                pass

            else: telnetLogger.debug(f"Error: RawANSI.parseToText() has no specific code to handle ANSI code '{RawANSIChunk.cmdByte}' ({RawANSIChunk.cmd}).")

            if RawANSIChunk.txt: #position/color changes will have already been performed at this point, and apply to any subsequent RawANSIChunks due to being stored in local variables.
                #Making this test dependent on text len ensures nothing gets missed
                _tRawANSIChunk = ParsedANSICommand(line=currentLine, column=currentColumn, text=RawANSIChunk.txt, highlighted=highlighted, deleteMode=0, deleteTarget=0)
                #print(f"appending RawANSIChunk <{_tRawANSIChunk}>"
                _ParsedANSI.append(_tRawANSIChunk)
                currentColumn += len(RawANSIChunk.txt) #if the next RawANSIChunk does not reset position (e.g. cursor move), we need to keep up ourselves. 
        self.ParsedANSI = _ParsedANSI

    def from_text(self, text:str):
        self.parse_raw_ANSI(text)
        self.render()

    def save(self):
        self.Text = "\n".join(self.Lines)
        self.recognise_type(self)
        Screen.History.append(self)
        Screen.History = Screen.History[0: min(len(Screen.History), Screen.HISTORY_LENGTH)]

    def render(self):
        if len(Screen.History)>0: 
            if self.BasedOnPrev: self.Lines = Screen.prevLines() #Retrieve previous screen, which ANSI commands may alter
        for currentIndex in range(0, len(self.ParsedANSI)):
            ANSICmd = self.ParsedANSI[currentIndex]
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
                        #Just wipe .Lines and keep going
                        self.Lines = []
                        continue
      
            #Ensure implicit whitespace exists
            if (len(self.Lines[ANSICmd.line]) < ANSICmd.column):  self.Lines[ANSICmd.line] += (" "*(ANSICmd.column - len(self.Lines[ANSICmd.line])))
            
            if (ANSICmd.column < len(self.Lines[ANSICmd.line])): #if we're changing something inside the line, let's do it through string surgery
                self.Lines[ANSICmd.line] = self.Lines[ANSICmd.line][0:ANSICmd.column] + ANSICmd.text + self.Lines[ANSICmd.line][ANSICmd.column+len(ANSICmd.text):]
            else: 
                self.Lines[ANSICmd.line] += ANSICmd.text #else, we can just append

        self.save()


class Connection():
    """ Contains methods and strutures to connect to, and exchange data with, the LIMS system """
    DEBUGLEVEL          = 0                 # value >0 will show (parts of) telnet traffic on-screen, this may include your password 
    MAX_WINDOW_WIDTH    = 128               # Max Value: 65535
    MAX_WINDOW_HEIGHT   = 5000              # 
    TERMINALS           = [b"", b"VT100", b"VT102", b"NETWORK-VIRTUAL-TERMINAL", b"UNKNWN"] #A list of the different terminal types we're willing to lie and pretend we are
    EscapeSplitter = re.compile(r"(?=\x1b)", flags=re.M)

    def __init__(self):
        self.tn = telnetlib.Telnet()
        self.TERMCOUNTER         = 1                 # keeps track of how many terminal types we're already tried.
        self.LASTCMD             = b""               # stores last option being called, for purposes of knowing what subnegotiation to do (because telnetlib chops that up)
        self.textBuffer          = b""               # stores whatever was received from the socket.
        self.Screen              = Screen(self.tn)

    """ Handles TELNET option negotiation """
    def set_options(self, tsocket, command, option):
        if command == b"\xfa" and option == b"\x00": #Subnegotiation, request to send 
            #a = Connection.tn.read_sb_data()
            #print(a)
            if self.LASTCMD == b"\x18": #Negotiate terminal 
                if Connection.DEBUGLEVEL > 0: telnetLogger.debug("Subnegotiating terminal type...")
                tsocket.send(b"%s%s\x18\x00%s%s%s" % (telnetlib.IAC, telnetlib.SB, Connection.TERMINALS[self.TERMCOUNTER], telnetlib.IAC, telnetlib.SE) ) #Declare 
                if self.TERMCOUNTER < len(Connection.TERMINALS): self.TERMCOUNTER = self.TERMCOUNTER + 1
                self.LASTCMD = b''

            elif self.LASTCMD == telnetlib.NAWS: #Negotiated window size; technically irrelevant as this is a virtual terminal
                if Connection.DEBUGLEVEL > 0: telnetLogger.debug("Subnegotiating window size...")
                width = struct.pack('H', Connection.MAX_WINDOW_WIDTH)
                height = struct.pack('H', Connection.MAX_WINDOW_HEIGHT)
                tsocket.send(telnetlib.IAC + telnetlib.SB + telnetlib.NAWS + width + height + telnetlib.IAC + telnetlib.SE)
                self.LASTCMD = b''

            else: telnetLogger.debug("SUBNEGOTIATE OTHER: %s" % self.LASTCMD)
              
        elif option == b'\x18' and command == telnetlib.DO:
            telnetLogger.debug("Promising Terminal Type")
            tsocket.send(b"%s%s\x18" % (telnetlib.IAC, telnetlib.WILL)) # Promise we'll send a terminal type
            self.LASTCMD = b'\x18'
                    
        elif command == telnetlib.WILL and option == b'\x01': tsocket.send(b"%s%s\x01" % (telnetlib.IAC, telnetlib.DO))
        elif command == telnetlib.WILL and option == b'\x03': tsocket.send(b"%s%s\x03" % (telnetlib.IAC, telnetlib.DO))

        elif command == telnetlib.DO and option == telnetlib.NAWS: 
            tsocket.send(telnetlib.IAC + telnetlib.WILL + telnetlib.NAWS)
            self.LASTCMD = telnetlib.NAWS
        
        #For all commands we have not explicitly defined behaviour for, deny:
        elif command in (telnetlib.DO, telnetlib.DONT): tsocket.send(telnetlib.IAC + telnetlib.WONT + option) 
        #We refuse to do anything else
        elif command in (telnetlib.WILL, telnetlib.WONT): tsocket.send(telnetlib.IAC + telnetlib.DONT + option) 
        #We also don't care to discuss anything else. Good DAY to you, Sir. I said GOOD DAY. 

    def read_data(self, max_wait = 200, ms_input_wait = 100, wait = True): #HACK: 100 / 50?
        self.textBuffer = self.tn.read_very_eager() #very_eager never blocks, only returns data stripped of all TELNET control codes, negotiation, etc                              
        if self.textBuffer == b'' or wait:            # we didn't get anything (yet?) but we expected something
            time.sleep(ms_input_wait/1000)          # give APEX 500ms to get its shit together
            tmp = self.tn.read_very_eager()   # try reading again
            waited = ms_input_wait
            while tmp != b'' and waited < max_wait: # read until we get nothing
                self.textBuffer += tmp        # append what we got
                time.sleep(ms_input_wait/1000)      # give APEX 500ms to get its shit together
                waited = waited + ms_input_wait     # count wait time
                tmp = self.tn.read_very_eager()   # try reading again
        if self.textBuffer:
            self.Screen.from_text(self.textBuffer)
            self.Screen = Screen.History[-1]
            telnetLogger.debug("Connection.read_data(): Constructed screen from %d ANSIChunks" % len(self.Screen.ParsedANSI))

    def send_raw(self, message, quiet=False, readEcho=True):
        try:
            if not quiet: telnetLogger.debug(f"Sending {message} to Connection")
            self.tn.write(message)
            if (readEcho): self.tn.read_until(message)
        except OSError as OSE:
            telnetLogger.error(f"Error whilst attempting to send message to Connection: {OSE.strerror}")
        except:
            pass
    
    def send(self, message, quiet=False, readEcho=True, maxwait_ms=1000):
        try:
            message = str(message)
            ASCIImsg = message.encode("ASCII")+b'\x0D'
            if not quiet: telnetLogger.debug(f"Sending '{message}' to Connection")
            self.tn.write(ASCIImsg)
            if (readEcho): 
                if message:
                    if (message[0]=='^' and len(message)==2):
                        self.tn.read_until(message[1].encode("ASCII"), timeout=(maxwait_ms/1000))
                    else:
                        self.tn.read_until(message.encode("ASCII"), timeout=(maxwait_ms/1000))
        except OSError as OSE:
            telnetLogger.error("Error whilst attempting to send message to Connection: %s", OSE.strerror)
       
    def send_and_ignore(self, msg, quiet=False, readEcho=True):
        self.send(msg, quiet, readEcho)   # 
        self.tn.read_very_eager()         # Take and ignore all data being returned in response to this message

    def connect(self, IP, Port:int=23, IBMUser:str="AIX", Userprompt:str=None, User:str=None, PWPrompt:str=None, PW:str=None):
        if Userprompt and not User:
            telnetLogger.error("connect(): A Userprompt but no user has been supplied. Cannot aupply user if asked by remote host. Terminating.")
            raise Exception("connect(): Userprompt but no User supplied")
        
        if PWPrompt and not PW:
            telnetLogger.error("connect(): Given PWPrompt but no PW to respond with. Terminating.")
            raise Exception("connect(): PWPrompt but no PW supplied")

        self.tn.set_option_negotiation_callback(self.set_options)  #Register our set_options function as the resource to interpret any negotiation calls we get
        self.tn.set_debuglevel(Connection.DEBUGLEVEL)
        telnetLogger.debug("Opening connection to remote host...")
        self.tn.open(IP, Port, timeout=1)
        self.tn.read_until(b"login: ")
        self.send(IBMUser)
        telnetLogger.debug("Connected to remote. Waiting for login...")
        self.tn.read_until(b'\x05')
        self.tn.write(config.LOCALISATION.ANSWERBACK)
        #TODO: double check you can't still read until User THEN PW.
        #Or, get a user-supplied one, and if none, skip that part (and write at the other.)
        if Userprompt:
            self.tn.read_until(Userprompt)
            self.send(User)
        if PWPrompt:
            if User and not Userprompt:
                self.send(User)
            self.tn.set_debuglevel(0) #Let's not echo anyone's password(s)
            self.send(PW, quiet=True, readEcho=False)
            self.tn.set_debuglevel(Connection.DEBUGLEVEL)

