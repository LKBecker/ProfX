import datetime
from tp_telnet import ProfX, Screen
from tp_utils import process_whitespaced_table, extract_column_widths
import time

import config

import logging
setRipperLogger = logging.getLogger(__name__)

""" Contains data about a Set of tests, containing their Authorisation Group and Autocomment Group. If set was unavailable (locked by other user), Success will be False. """
class SetDefinition():
    def __init__(self, SetCode, AuthorisationGroup:str, AutoCommentGroup:str, AccessedSuccessfully:bool):
        self.Code = SetCode
        self.AuthGroup = AuthorisationGroup
        self.AutoCommGroup = AutoCommentGroup
        self.Success = AccessedSuccessfully
        self.AuthGrpObj = None
        self.AutocomObj = None
    
    def __str__(self): 
        return f"SetDefinition(SetCode={self.Code}, AuthorisationGroup={self.AuthGroup}, AutoCommentGroup={self.AutoCommGroup})"

    def __repr__(self):
        return f"SetDefinition(SetCode={self.Code}, AuthorisationGroup={self.AuthGroup}, AutoCommentGroup={self.AutoCommGroup})"

    def file_dump(self):
        with open(f"./SetData/{self.Code}.txt", "w") as Output:
            Output.write(f"Begin Set '{self.Code}'\n")
            Output.write(f"Extracted {datetime.datetime.now().ctime()}\n\n")
            Output.write(f"{self.Code} is a member of Authorization group '{self.AuthGroup}'\n")
            Output.write(f"{self.Code} belongs to Autocomment group '{self.AutoCommGroup}'\n\n")
            Output.flush()

            Output.write("Authorization Group Details:\n")
            if self.AuthGrpObj:
                
                Output.write(f"Authorization Group {self.AuthGroup} contains [{len(self.AuthGrpObj)}] possible NPCL lists:\n")
                for AuthGrp in self.AuthGrpObj:
                    Output.write(f"\tNPCL list {AuthGrp.AuthCode}:\n")
                    Output.write("\t\tItems are added to this list if they fulfill the following filter logic:\n")
                    Output.write("\t\t\t")
                    Output.write("\n\t\t\t".join(AuthGrp.LogicTree))
                    Output.write("\n\n")
                    
                    Output.write("\t\tItems on this list are automatically authorized, unless *any* of the following are to True:\n")
                    Output.write(f"\t\t\tChecks:\n")
                    for Line in AuthGrp.Checks:
                        Output.write(f"\t\t\t\t{Line}\n")
                    Output.write("\n")
                    if AuthGrp.StyleSets:
                        for ListFilter in AuthGrp.StyleSets:
                            ValidEntries = [' '.join(x) for x in ListFilter.Value if x[0].strip(".")]
                            nEntries = len(ValidEntries)
                            if nEntries > 5:
                                nSpaces = " "*(len(ListFilter.Type)+1)
                                nCycles = nEntries // 5
                                Output.write(f"\t\t\t{ListFilter.Type} : {ValidEntries[0:5]}\n")
                                for i in range(1, nCycles):
                                    Output.write(f"\t\t\t{nSpaces}: {ValidEntries[i*5:(i*5)+5]}\n")
                                if nEntries % 5 != 0:
                                    Output.write(f"\t\t\t{nSpaces}: {ValidEntries[5*(nCycles):]}\n")
                            else:
                                Output.write(f"\t\t\t{ListFilter.Type} : {ValidEntries}\n")
                        Output.write("\n")
                    else:
                        Output.write("\t\t\tNo associated filters.\n")
            else:
                if self.AuthGroup:
                    Output.write("ERROR: Authorization group(s) could not be retrieved.\n")
                else:
                    Output.write(f"Authorization group(s) do not appear to be assigned to Set {self.Code}.\n")
            Output.write("End of Authorization Group Details\n\n\n")
            Output.flush()
            if self.AutocomObj:
                Output.write(f"Autocomment group {self.AutocomObj.Code} contains [{len(self.AutocomObj.Pages)}] possible sets of Autocomments:\n")
                for AutoCom in self.AutocomObj.Pages:
                    Output.write(f"\t\tDescription: {AutoCom.Description}\n")
                    Output.write(f"\t\tThese autocomments are applied if:\n")
                    Output.write("\t\t\t")
                    Output.write("\n\t\t\t".join(AutoCom.LogicTree))
                    Output.write("\n\n")
                    Output.write("\t\tAutocomments are:\n")
                    for Com in AutoCom.Comments:
                        Output.write(f"\t\t\t{Com}\n")
                    Output.write(f"\t\tPromote to Phone List: {str(AutoCom.PromoteTelList)}\n")
                    Output.write(f"\t\tFurther Set / Superset: {str(AutoCom.FurtherSetSuperset)}\n")
                    Output.write(f"\n\n")
                Output.write(f"End of Autocomments\n\n")
                Output.flush()
            else:
                if self.AutoCommGroup:
                    Output.write("ERROR: AutoComment logic could not be retrieved.\n")
                else:
                    Output.write(f"No AutoComments exist for Set {self.Code}.\n\n")
            Output.write("End of Set")
            Output.flush()


""" Supercontainer for Autocomment structure, containing multiple AutoCommentSet instances in its Pages list. 
AutoCommentSet instances list the logic of whether to apply this group of comment(s), and the comment(s) text """
class AutoCommentStructure():
    def __init__(self, AUTOCOM_Code):
        self.Code   = AUTOCOM_Code
        self.Pages  = []


""" Data container for an Autocomment page, containing its description, further set/superset, the actual comments, and the logic tree of whether to apply this AutoCommentSet it """
class AutoCommentSet():
    def __init__(self, lines, treelines):
        self.Description = lines[0][15:].strip() # Removes 1) Description
        self.PromoteTelList = len(lines[1][-1:].strip("."))>0
        self.FurtherSetSuperset = lines[2][27:].strip(".") # Removes "3) Further set or superset "
        self.Comments = []
        for line in lines[3:]:
            self.Comments.append(line[line.find(" ")+9:]) # Removes "[0-99]) Comment: "
        self.LogicTree = treelines


""" NPCL Styles, as defined in NPSET, filter samples to essential data for an NPCL list, e.g. relevant sets/tests or locations. """
class NPCLAuthIntervention():
    def __init__(self, ListName, SetIndex, SetType, SetValues):
        self.Name = ListName
        self.Index = SetIndex
        self.Type = SetType
        self.Value = SetValues      
    
    def __repr__(self):
        return f"NPCLAuthIntervention(ListName={self.Name},SetIndex={self.Index}, SetType={self.Type}, SetValues=...)"


""" Contains an NPCLList, to which samples are assigned, and their associated tests/data filtered(?) based on NPCLAuthIntervention(s)"""
class NPCLList():
    def __init__(self, AuthGroup, AuthCode):
        self.AuthGroup = AuthGroup
        self.AuthCode = AuthCode
        self.LogicTree = []
        self.StyleSets = []
        self.Checks = []
    
    def __repr__(self):
        return f"NPCLList(AuthGroup={self.AuthGroup}, AuthCode={self.AuthCode}, CheckSettings=..., Tree=..., StyleSets=...)"

    """ Captures data from SETM (Set Maintenance), currently only a Set's Authorisation group and Autocomment group
    Could be extended to capture sample type, etc"""

""" Using SETM, retrieves autocomment and authorisation list assignments for sets and/or supersets. Could also get e.g. sample types."""
def get_Set_definitions(Sets:list, reckless=False):

    def check_access():
        if (ProfX.screen.length >= 24):
            if (ProfX.screen.Lines[23].strip() == "Set accessed by another user at present. Press ESC"):
                setRipperLogger.warning(f"Cannot access Set {Set}, being used by another user. Dropping.")
                #SetDefinitions.append(SetDefinition(SetCode=Set, AuthorisationGroup="", AutoCommentGroup="", AccessedSuccessfully=False))
                ProfX.send_raw(b'\x1b', readEcho=False)
                ProfX.read_data()
                return False
        return True

    ProfX.return_to_main_menu()
    ProfX.send(config.LOCALISATION.SETMAINTENANCE)
    ProfX.read_data()
    ProfX.send('A')
    ProfX.read_data()
    SetDefinitions = []
    for Set in Sets:
        AUCOM_Code = ""
        AuthGroup_Code = ""
        ProfX.send(Set) #TODO: breaks here... works when debugging, stepping through SLOWLY
        if not reckless: 
            time.sleep(1)   # Seems to take about 1 second to check for access and return error
        else: 
            time.sleep(0.1)
        ProfX.read_data()
        if not check_access():            
                continue
        
        if (ProfX.screen.length >= 24):
            if (ProfX.screen.Lines[23].strip() == "WARNING: Exists as a superset, with priority at request entry - OK <N>"):
                setRipperLogger.warning(f"Set {Set} is a 'superset', retrieving anyway...")
                ProfX.send_raw('Y'.encode('ASCII')) #In this instance, the system instantly reacts to the keypress
                # sending it with the \r added by regular send() will then immediately skip to 'acceptable sample types'
                time.sleep(0.1) # Seems if we read too fast we miss the correction.
                if check_access(): #Still possible to get access denied here if another user is in here.
                    ProfX.read_data()
                else:
                     continue
                
        AuthGroupLine = [x for x in ProfX.screen.ParsedANSI if x.line == 19 and x.column == 68 and x.text.strip(".")] #[x for x in ProfX.screen.Lines[14].split(" ") if x]
        AUCOMLine = [x for x in ProfX.screen.ParsedANSI if x.line == 14 and x.column == 33 and x.text.strip(".")] #[x for x in ProfX.screen.Lines[19].split(" ") if x]

        if AUCOMLine:
            AUCOM_Code = AUCOMLine[0].text
        if AuthGroupLine:
            AuthGroup_Code = AuthGroupLine[0].text 

        SetDefinitions.append(SetDefinition(SetCode=Set, AuthorisationGroup=AuthGroup_Code, AutoCommentGroup=AUCOM_Code, AccessedSuccessfully=True))
        
        setRipperLogger.info(f"get_Set_definitions(): Retrieved Set {Set}: AUCOM {AuthGroup_Code}, SNPCL {AUCOM_Code}")
        ProfX.send(config.LOCALISATION.CANCEL_ACTION)
        ProfX.read_data()
    setRipperLogger.info(f"get_Set_definitions(): Loop complete. Returning {len(SetDefinitions)} identifiers.")
    return SetDefinitions

""" Retrieves details of Authorisation Interventions - 
    Being sifted into an NPCL list does not mean you -have- to be examined by a clinical scientist.
    Only when any of these equate to TRUE is the result held for authorisation. """
def get_NPCL_Interventions(NPCL_Lists:list):
    #FIX for 'XT'
    ProfX.tn.set_debuglevel(0)
    if not isinstance(NPCL_Lists, list):
        if isinstance(NPCL_Lists, NPCLList):
            NPCL_Lists = [NPCL_Lists]
    for NPCL_List in NPCL_Lists:
        ProfX.return_to_main_menu()
        
        ProfX.send(config.LOCALISATION.NPCLSETS)
        ProfX.read_data()
        setRipperLogger.info(f"Retrieving auto-Authorization Interventions for NPCL list '{NPCL_List.AuthCode}'...")
        ProfX.send(NPCL_List.AuthCode)
        ProfX.read_data()
        if (ProfX.screen.length <= 23): # The list exists
            NPCL_List.Checks = [ x[5:] for x in ProfX.screen.Lines[10:14] ]
            ProfX.send('^L')   
            ProfX.read_data()
            if (ProfX.screen.length <= 23): #List exists AND has sets
                if (ProfX.screen.hasErrors):
                    setRipperLogger.warning(f"'{NPCL_List.AuthCode}': No codes are within the given specification")
                    continue
                AuthSets =  [x for x in ProfX.screen.Lines[4:-1] if x] #grab lines with sets
                for line in AuthSets:
                    line = [x.strip() for x in line.split(" ") if x]
                    index = line[0].rstrip(")")
                    type  = line[-1]
                    ProfX.send(index)
                    ProfX.read_data()
                    #There does not seem to be an N option on this screen, ever; max is 28 items. No check / page turning code needed.
                    CodeLines = [x for x in ProfX.screen.Lines[5:-1] if x]
                    CodeTable = process_whitespaced_table(tableLines = CodeLines, headerWidths = [8, 14, 44, 47, 54, 86])
                    assert len(CodeTable) % 2 == 0
                    cleanTable = [x[0:3] for x in CodeTable]
                    for y in [x[3:6] for x in CodeTable]:
                        cleanTable.append(y)
                    del CodeTable
                    cleanTable = [x[1:] for x in cleanTable if x[2]]
                    NPCL_List.StyleSets.append( NPCLAuthIntervention(NPCL_List.AuthCode, index, type, cleanTable) )
                    ProfX.send('A') 
                    ProfX.read_data() #Probably won't start with an ANSI code?
                    ProfX.send('^L') # ESC is not echoed, but the L is?!
                    ProfX.read_data()
            else: #List does not have sets. Press ESC.
                setRipperLogger.warning(f"'{NPCL_List.AuthCode}' does not appear to have any filters specified.")
                ProfX.send_raw(b'\x1B')
                #NPCL_List.StyleSets.append( NPCLAuthIntervention(NPCL_List.AuthCode, None, None, None, OptLines) )
        else:
            # Error "<CODE> - Not in code list for Authorisation list code. Press ESC"
            setRipperLogger.warning(f"'{NPCL_List.AuthCode}' does not appear to be an existing NPCL list.")

""" Captures data for an authorisation group, derived from a Set via SETM"""
def get_authorisation_group_structure(SNPCLLists:set):
    NPCLObjs = []
    Page_Has_Blanks = None
    
    def process_SNPCL_screen():
        nonlocal Page_Has_Blanks
        nonlocal NPCL_Item_Tuples
        _tmpTable = process_whitespaced_table(tableLines=ProfX.screen.Lines[5:21], headerWidths=[7, 15, 44, 47, 55])
        for row in _tmpTable:
            if row[1]:
                NPCL_Item_Tuples.append((row[0].rstrip(")"), row[1], row[2]))
            else:
                Page_Has_Blanks = True
            if row[4]:
                NPCL_Item_Tuples.append((row[3].rstrip(")"), row[4], row[5]))
            else:
                Page_Has_Blanks = True 

    ProfX.return_to_main_menu()
    ProfX.send(config.LOCALISATION.SNPCL)
    ProfX.read_data()
    
    for SNPCLList in SNPCLLists:
        if not SNPCLList: # Some assays do not have pre-processing
            continue
        NPCL_Item_Tuples = []
        setRipperLogger.info(f"get_authorisation_group_structure(): Retrieving NPCL lists(s) for {SNPCLList}.")
        ProfX.send(SNPCLList)
        ProfX.read_data()
        if (ProfX.screen.length == 24):  # Set does not exist and we entered creation mode
            setRipperLogger.warning(f"Authorisation Group {SNPCLList} is being accessed. Must be retried later.")
            ProfX.send_raw(b'\x1B')
            ProfX.read_data()
            ProfX.return_to_main_menu()    # There's no graceful return option - B makes a set called B, ^ and '' both yeet one to the main menu.
            ProfX.send('SNPCL')            # So we just need to return...
            ProfX.read_data()
            continue

        if (ProfX.screen.Lines[4].strip() != "Auth code"):  # Set does not exist and we entered creation mode
            setRipperLogger.warning(f"Authorisation Group {SNPCLList} does not appear to exist. This shouldn't happen if fed from set_ripper().")
            ProfX.send(config.LOCALISATION.CANCEL_ACTION)        # There's no graceful return option - B makes a set called B, ^ and '' both yeet one back to the main menu.
            ProfX.read_data()
            ProfX.send(config.LOCALISATION.SNPCL)
            ProfX.read_data()
            continue

        process_SNPCL_screen() # Parses the whitespaced 'table' pf options, checks if we see any blanks, adds options to tuple thing.
        while Page_Has_Blanks == False:
            ProfX.send('N')
            ProfX.read_data()
            process_SNPCL_screen()
        #while Page_Has_Blanks == False

        for NPCLListIndex in NPCL_Item_Tuples:
            StarFreeAuthCode = NPCLListIndex[1].lstrip("*") #The * is prepended by TelePath if there is no log
            tmp = NPCLList(AuthGroup=SNPCLList, AuthCode=StarFreeAuthCode) 
            if (NPCLListIndex[1]==StarFreeAuthCode):
                ProfX.send('U')  # The only reason to call U without the index is that indices _could_ be over 99.
                ProfX.read_data()
                ProfX.send(NPCLListIndex[0])#, readEcho=False) # Indices here are not per page but unique, and can be called from any page.
                ProfX.read_data()
                tmp.LogicTree = [x for x in ProfX.screen.Lines[2:22] if x]
                ProfX.send('A')
                ProfX.read_data()
            else:
                tmp.LogicTree = ["No sift specified."]
            NPCLObjs.append( tmp )
        ProfX.send('B')    # Unlisted options, can still go (B)ack to overview
        ProfX.read_data()
    # For SNPCLList in SNPCLLists
    return NPCLObjs

""" Retrieves autocomment structure - the logic that is used for testing, and the resulting comments to be applied """
def get_autocomment_structure(AUCOMSets:set):
    AUCOM_Data = []
    ProfX.return_to_main_menu()
    ProfX.send(config.LOCALISATION.AUTOCOMMENTS)
    ProfX.read_data()                  
    for AUCOM_Routine in AUCOMSets:
        if not AUCOM_Routine:
            setRipperLogger.info(f"get_autocomment_structure(): Skipping malformed/empty autocomment routine '{AUCOM_Routine}'")
            continue
        setRipperLogger.info(f"get_autocomment_structure(): Retrieving Autocomment routines for {AUCOM_Routine}")
        Autocomment_Obj = AutoCommentStructure(AUCOM_Routine)
        ProfX.send(AUCOM_Routine)
        ProfX.read_data()
        if (ProfX.screen.length >= 24):
            if (ProfX.screen.Lines[-1] == " Unable to allocate spec. Press ESC"):  # If the set is being accessed and thus locked.
                ProfX.send_raw(b'\x1B')
                continue
        else:
            AUCOM_Chunks = [x for x in ProfX.screen.ParsedANSI if x.line == 3 and x.deleteMode == 0]
            if AUCOM_Chunks:
                AUCOM_Chunks = AUCOM_Chunks[1:] # First line is a header which we would like to ignore
                try:
                    assert len(AUCOM_Chunks) % 2 == 0
                    for ChunkIndex in range(0, len(AUCOM_Chunks))[::2]:
                        Index = AUCOM_Chunks[ChunkIndex].text.strip().rstrip(")")
                        ProfX.send('E')    # Enter (E)dit mode (no other way to see contents)
                        ProfX.read_data()
                        ProfX.send(Index)
                        #time.sleep(0.2)         # Safety measure, gives the server time to collate its data
                        ProfX.read_data()
                        CommStr = [x for x in ProfX.screen.Lines[3:-1] if x]
                        FinalComms=[]
                        for line in CommStr:
                            line = line.split("\r\n")
                            line = [x.strip() for x in line if x]
                            for comm in line:
                                if comm:
                                    FinalComms.append(comm)
                        ProfX.send('A')    # (A)ccept, switches to logic view
                        ProfX.read_data()
                        CommLogic = [x for x in ProfX.screen.Lines[3:-1] if x]
                        tmpACP = AutoCommentSet(FinalComms, CommLogic)
                        Autocomment_Obj.Pages.append(tmpACP)    # Creates data structure and appends to AutoCommentStructure container
                        ProfX.send('A')    # (A)ccept, goes back to root for next index
                        ProfX.read_data()
                except AssertionError:
                    setRipperLogger.debug(f"get_autocomment_structure(): '{AUCOM_Routine}' returns uneven number of AUCOM_Chunks. Adding 'None' and continuing.")
            else: 
                setRipperLogger.debug(f"get_autocomment_structure(): '{AUCOM_Routine}' returns no AUCOM_Chunks.")
            ProfX.send('A')    # (A)ccept, returns to root screen
            ProfX.read_data()
            try:
                FullLines = [x for x in ProfX.screen.Lines if x]
                assert len(FullLines) < 5 # If we successfully returned to the main screen, there is only System Header, Screen Type, Routine / Title line. Not even options.
            except AssertionError:
                setRipperLogger.debug(f"get_autocomment_structure(): Unclear whether return to base screen was successful:")
                setRipperLogger.debug(ProfX.screen.Text)
        #if ProfX.screen.length < 24
        AUCOM_Data.append( Autocomment_Obj )
    #for AUCOM_Routine
    return AUCOM_Data

""" For a list of sets, retrieves autocomment and NPCL list categories, then recursively retrieves those details and writes each to file as a report.
'reckless' deactivates a few time.sleep() options which otherwise await notification that other users are blocking entries. May get stuck if turned off!"""
def set_ripper(SetsToRip, reckless=True):
    setRipperLogger.info("set_ripper(): Start up")
    setRipperLogger.info(f"set_ripper(): Received {len(SetsToRip)} sets to grab.")
    
    #Gather data
    Sets = get_Set_definitions(SetsToRip, reckless) 
    SNPCLs = sorted(set([x.AuthGroup for x in Sets if x.Success and x.AuthGroup]))
    AUCOMs = sorted(set([x.AutoCommGroup for x in Sets if x.Success and x.AutoCommGroup]))
    if SNPCLs:
        setRipperLogger.info(f"set_ripper(): Retrieving Authorisation groups for {len(SNPCLs)} SNPCL objects.")
        SNPCL_Objs = get_authorisation_group_structure(SNPCLs)
        setRipperLogger.info(f"set_ripper(): Retrieving NPCL autorisation interventions for {len(SNPCL_Objs)} NPCL lists.")
        get_NPCL_Interventions(SNPCL_Objs)
    if AUCOMs:
        setRipperLogger.info(f"set_ripper(): Retrieving Autocomment logics for {len(AUCOMs)} autocomment sets.")
        AUCOM_Objs = get_autocomment_structure(AUCOMs)
    
    setRipperLogger.info("set_ripper(): Data collection complete. Collating...")
    #Assemble / collate into 'long form'
    SetObjCounter = 0
    nSamples = len(Sets)
    ReportInterval = max(min(250, int(nSamples*0.1)), 1)
    for SetObj in Sets:
        #setRipperLogger.info(f"set_ripper(): Assembling Set {SetObj.Code}...")
        Matched_Authorisation = [x for x in SNPCL_Objs if x.AuthGroup == SetObj.AuthGroup]
        if Matched_Authorisation:
            SetObj.AuthGrpObj = Matched_Authorisation
        Matched_AutoComment = [x for x in AUCOM_Objs if x.Code == SetObj.AutoCommGroup]
        if len(Matched_AutoComment)==1:
            SetObj.AutocomObj = Matched_AutoComment[0]
        SetObjCounter = SetObjCounter + 1
        Pct = (SetObjCounter / nSamples) * 100
        
        # Output
        #setRipperLogger.info(f"set_ripper(): Writing Set {SetObj.Code} to file...")
        SetObj.file_dump() # lol
        
        if( SetObjCounter % ReportInterval == 0): setRipperLogger.info("Collated %d of %d SetObjs (%.2f%%)."% (SetObjCounter, nSamples, Pct))
    setRipperLogger.info("set_ripper(): Complete.")

SetsIO = open("./SetsToExtract.txt", "r")
SetsToRip = SetsIO.readlines()
SetsIO.close()
SetsToRip = [x.strip() for x in SetsToRip]

try:
    ProfX.connect()#TrainingSystem=True)
    set_ripper(SetsToRip, reckless=True)

except Exception as e: 
    setRipperLogger.error(e)

finally:
    ProfX.disconnect()