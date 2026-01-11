#!/home/markus/venvs/blake3/bin/python

#    !/usr/bin/env python3
# ------------------------------------------------------------------------------

# Includes for normal file operations etc.
import os
import sys
import json
import time
import atexit
import datetime
from   blake3 import blake3

# Includes for GUI stuff
import tkinter as tk
from   tkinter import ttk
from   tkinter.scrolledtext import ScrolledText
from   tkinter import filedialog

# ------------------------------------------------------------------------------
# Global Variables -------------------------------------------------------------

version = '1.0'

searchFileCnt = 0;

# Save and restore settings, normal - default - from_tk_var
initData = {}
defaultInitData = {}
tkVars = {}

# hold the list of files with duplicates
fileDB = {}

# hold folders to be searched
searchFolders      = {}
# last folder for file dialog
searchFolderLast   = ""
# marked for enable/disable/remove
searchFolderMarked = []
# used to stop search process by user
searchStopFlag = False

# holds name of last selected file in find tab
lastSelectedFile = ""
# will be filled with filename of ini data
fileNameInit   = ""
# will be filled with filename of file database
fileNameFileDB = ""

# some color definitions
colorFrame = ('#d9ffff', '#ffd9ff')             # light blue, light pink
colorFile  = ('#ccffcc', '#ffcccc')             # light green, light red
colorBlock = ('#FFFFFF', '#FFEEFF', '#DDFFFF', '#FFFFDD')  # white, very light pink, light blue, light yellow
colorButt  = ('#D9E9D9', '#E9D9D9', '#D9E9E9', '#E9D9B9', "#E1E190")

#myFont = 'DejaVu Sans Mono'

# ------------------------------------------------------------------------------
# helper -----------------------------------------------------------------------

# File system operations -------------------------

def delete_file( pathfile ):
    os.remove(pathfile)
    print(f"File {pathfile} deleted!")

def delete_empty_folder(folder):
    global initData
    if initData['DelEmptyFolder']:
        os.rmdir(folder)
        print(f"Empty folder {folder} deleted!")

def is_dir_empty(path: str) -> bool:
    # os.scandir returns an iterator of DirEntry objects.
    # next(..., None) yields the first entry or None if empty.
    return next(os.scandir(path), None) is None

# Save in INI file helpers -----------------------

def tk_variables_register_and_init(key, typ):
    global tkVars, initData, defaultInitData

    if key in initData:
        value = initData[key]
    elif key in defaultInitData:
        value = defaultInitData[key]
    else:
        value = False  if typ[0]=='b'  else  None
        initData[key] = value

    match typ[0]:
        case 's':   tkv = tk.StringVar(value=value)
        case 'b':   tkv = tk.BooleanVar(value=value)
        case 'i':   tkv = tk.IntVar(value=value)
        case 'd':   tkv = tk.DoubleVar(value=value)

    tkVars[key] = tkv
    return tkv

def tk_variables_get_to_save():
    global tkVars, initData
    for key in tkVars:
        initData[key] = tkVars[key].get()

# General ----------------------------------------

def humread( v ):
    i = 0
    x = 1 if v == 0 else v
    p = ('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB')
    while(x):
        x >>= 10
        i+=1
    i-=1
    v >>= (10 * i)
    return f'{v} {p[i]}'

# Class for scrollable frames --------------------

class ScrollableFrame(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.canvas = tk.Canvas(self, borderwidth=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)

        self.window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.scrollable_frame.bind( "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.window, width=e.width))

        # Mousewheel bindings (work only when mouse is over THIS canvas)
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)

    def _bind_mousewheel(self, event):
        # Windows and macOS
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        # Linux (You may need to bind globally, or test on your platform)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _unbind_mousewheel(self, event):
        # Unbind only when mouse leaves
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
        else:
            # Windows/macOS
            self.canvas.yview_scroll(-1 * int(event.delta / 120), "units")

# Screen & windows helpers -----------------------------------------------------

def getScreenSize( root ):
    return root.winfo_screenwidth(), root.winfo_screenheight()

# Save/remember settings at program end to a *.ini file for next start ---------
def on_exit():
    global initData, fileNameInit
    print("Program is ending! Saving settings.")

    initData['Version'] = version
    initData['LastUse'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    initData['SearchFolders']  = searchFolders
    initData['SearchFoldLast'] = searchFolderLast

    tk_variables_get_to_save()

    with open(fileNameInit, 'w', encoding='utf-8') as f:
        json.dump(initData, f, indent=1)

# ------------------------------------------------------------------------------
# Basic information from *.ini file

def init_data_load():
    global initData, defaultInitData, searchFolders, searchFolderLast, fileNameInit

    # Read stored ini data from this file
    fileNameInit = os.path.join(os.path.expanduser('~'), f'{__file__}.ini')

    # If no such file or failed, use this for initialization
    defaultInitData = { 'Version' : version,
                        'winSizeX':840, 'winSizeY':600,
                        'winPosX' :100, 'winPosY' :100,
                        'DelEmptyFolder' : True ,
                        'SaveMarkTexts'  : True ,
                        'SaveFileDB'     : False,
                        'SearchFoldLast' : searchFolderLast,
                        'SearchFolders'  : { os.path.expanduser('~') : 1 },
                        'DelEmptyFolder' : True,
                        'SaveMarkTexts'  : True,
                        'UseFastHash'    : True,
                        'HashBlkSize'    : "17",
                        'HashBlkNum'     : "11",
                      }

    if os.path.exists(fileNameInit):
        with open(fileNameInit, "r", encoding="utf-8") as f:
            try:
                initData = json.load(f)   # Reads file into a Python dict
            except json.JSONDecodeError:
                print(f"File '{fileNameInit}' contains invalid JSON. Please fix or delete file")
                exit(2)

        if not len( initData['SearchFolders'] ):
            initData['SearchFolders'] = { os.path.expanduser('~') : 1 }
    else:
        initData = defaultInitData

    searchFolders    = initData['SearchFolders']
    searchFolderLast = initData['SearchFoldLast']


# Check some data about windows geometry if it makes sense, root window needed!
def init_data_check( root ):
    global initData
    # Avoid that windows will initialy be placed outside the visible screen
    screenMaxX, screenMaxY = getScreenSize( root )

    #print("initDataA:", initData, screenMaxX, screenMaxY)

    if initData['winSizeX'] > screenMaxX:   initData['winSizeX'] = screenMaxX
    if initData['winSizeY'] > screenMaxY:   initData['winSizeY'] = screenMaxY
    if initData['winPosX'] < 0:  initData['winPosX'] = 0
    if initData['winPosY'] < 0:  initData['winPosY'] = 0
    if (initData['winPosX'] + initData['winSizeX']) > screenMaxX:   initData['winPosX'] = screenMaxX - initData['winSizeX']
    if (initData['winPosY'] + initData['winSizeY']) > screenMaxY:   initData['winPosY'] = screenMaxY - initData['winSizeX']

    #print("initDataB:", initData)

# ------------------------------------------------------------------------------
# menu ---------------------------------------------------------------------
def wmake_menu( root ):
    menubar = tk.Menu(root)
    root.config(menu=menubar)

    fileMenu = tk.Menu(menubar, tearoff=0)
    fileMenu.add_command( label='Exit', command=root.destroy)
    menubar.add_cascade(label="File", menu=fileMenu)

    helpMenu = tk.Menu(menubar, tearoff=0)
    helpMenu.add_command(label='Welcome')
    helpMenu.add_command(label='About...')
    menubar.add_cascade(label="Help", menu=helpMenu)

# ------------------------------------------------------------------------------
# Status Area ------------------------------------------------------------------

def status_write( text ):            # Use this function to log something to the status area
    if not hasattr(status_write, "statusArea" ):
        print(f"Call to 'status_write' with '{text}' but not initialized")
        return

    status_write.statusArea.config(state='normal')
    status_write.statusArea.insert(tk.END, f'\n{text}' )
    status_write.statusArea.config(state='disabled')
    status_write.statusArea.see(tk.END)
    status_write.statusArea.update()

def wmake_status_area( root ):
    statusArea = ScrolledText(root, width=80,  height=6)
    statusArea.pack(padx = 5, pady=5,  fill=tk.BOTH, side=tk.BOTTOM, expand=False)
    statusArea.config(state='normal')
    statusArea.insert(tk.END, "Status/Activity")
    statusArea.config(state='disabled')
    status_write.statusArea = statusArea

# ------------------------------------------------------------------------------
# TABs with a Notebook ---------------------------------------------------------

def wmake_tabs( root, tabs ):
    # Create the notebook itself
    notebook = ttk.Notebook(root)
    notebook.pack(pady=4, expand=True, fill='both')
    # create frames for every tab
    for k in tabs:   tabs[k][1] = ttk.Frame(notebook)
    # pack frames
    for k in tabs:   tabs[k][1].pack(fill='both', expand=True)
    # add frames to notebook
    for k in tabs:   notebook.add(tabs[k][1], text=tabs[k][0])

# ------------------------------------------------------------------------------
# Search folder ----------------------------------------------------------------

def search_folder_marked(event):
    global searchFolderMarked

    if not hasattr(search_folder_marked, "listbox"):
        sys.exit("ERROR: Call to 'search_folder_marked' but not initialized 'listbox'")

    selection = search_folder_marked.listbox.curselection()
    searchFolderMarked = [search_folder_marked.listbox.get(i) for i in selection]

def search_folder_update():
    global searchFolders

    if not hasattr(search_folder_marked, "listbox"):
        sys.exit("ERROR: Call to 'search_folder_update' but not initialized 'listbox'")

    i=0
    colors = ('#ffeeee', '#ccffcc', '#ccccff')
    search_folder_update.listbox.delete(0, tk.END)
    for item in searchFolders:
        #print( item )
        search_folder_update.listbox.insert(tk.END, item )
        search_folder_update.listbox.itemconfig(i, { 'bg': colors[searchFolders[item]] } )
        i+=1

def search_folder_add():
    global searchFolders, searchFolderLast

    if not len(searchFolderLast):
        searchFolderLast = os.path.expanduser('~')

    folder = tk.filedialog.askdirectory(parent=root,
                                        title="Select a folder to search for duplicates",
                                        initialdir=searchFolderLast,
                                        mustexist=True)
    #tk.messagebox.showinfo( title='Chosen Folder', message=f"folder {len(searchFolders)}" )
    if len(folder) > 0:
        searchFolders[folder]=1
        searchFolderLast = folder
        search_folder_update()

def search_folder_remove():
    global searchFolderMarked
    for key in searchFolderMarked:
        x = searchFolders.pop(key, None)
    search_folder_update()

def search_folder_enable():
    global searchFolderMarked, searchFolders
    for key in searchFolderMarked:
        searchFolders[key]=1
    search_folder_update()

def search_folder_disable():
    global searchFolderMarked, searchFolders
    for key in searchFolderMarked:
        searchFolders[key]=0
    search_folder_update()

def wmake_search_folder( tab ):
    global searchFolders
    # Create button frame
    butFoldFrame = ttk.Frame( tab )
    butFoldFrame.pack(padx = 10, pady=5, side=tk.TOP)
    # "Add folder" button
    butFoldAdd = tk.Button( butFoldFrame, text='ADD folder', command=search_folder_add, bg=colorButt[4] )
    butFoldAdd.pack(padx = 10, pady=5, side=tk.LEFT)
    # "Remove selected from list" button
    butFoldRmv = tk.Button( butFoldFrame, text='Remove selected', command=search_folder_remove, bg=colorButt[3] )
    butFoldRmv.pack(padx = (10,50), pady=5, side=tk.LEFT)
    # "Enable selected" button
    butFoldEna = tk.Button( butFoldFrame, text='Enable selected', command=search_folder_enable, bg=colorButt[0] )
    butFoldEna.pack(padx = 10, pady=5, side=tk.LEFT)
    # "Disable selected" button
    butFoldDis = tk.Button( butFoldFrame, text='Disable selected', command=search_folder_disable, bg=colorButt[1] )
    butFoldDis.pack(padx = 10, pady=5, side=tk.LEFT)
    # List of search folder
    searchFoldListbox = tk.Listbox(master=tab, listvariable=searchFolders.keys(), selectmode='multiple' )
    searchFoldListbox.pack(padx=10, pady=5, expand=True, fill=tk.BOTH, side=tk.TOP)
    searchFoldListbox.bind('<<ListboxSelect>>', search_folder_marked)
    search_folder_marked.listbox = searchFoldListbox
    search_folder_update.listbox = searchFoldListbox
    search_folder_update()

# ------------------------------------------------------------------------------
# Exclude tab ------------------------------------------------------------------

def wmake_exclude( tab ):
    labelExclude = ttk.Label(tab, text='to be defined')
    labelExclude.pack(anchor=tk.CENTER, expand=True)

# ------------------------------------------------------------------------------
# Search tab -------------------------------------------------------------------

# Calc a hash over a file. If file is big then pick only a few parts and build
# the hash over that. For smaller files build hash over full file content.
# If you always want to build over full content then set blockSize=0 or blockCount=0

def calc_b3_fast(filename, blockSize=131072, blockCount=8):
    # Filename must be given and existing
    if not filename or not os.path.isfile(filename):
        print(f"ERROR: File '{filename}' doesn't exist or is not a file!", file=sys.stderr)
        #sys.exit(1)
        return None

    # Start a new hash calculation
    hasher = blake3()
    # Get size of the file
    fileSize = os.path.getsize(filename)
    # Calculate the minimum file size where this 'blocking' makes sense
    filemin = blockSize * blockCount
    # if blockCount or blockSize = 0 then we make hash over full file content
    if filemin == 0:  filemin = fileSize

    # If file is big enough, just hash over BLOCK_COUNT x BLOCK_SIZE bytes
    if fileSize > filemin:
        # Calculate the distance between 2 blocks, is at least BLOCK_SIZE
        delta = fileSize // blockCount
        # We start reading at file's beginning
        offset = 0

        #print(f"File: {filename}   Size: {fileSize}   delta: {delta}")
        try:
            with open(filename, 'rb') as f:
                while offset < fileSize :
                    reminder = fileSize - delta - offset
                    if reminder < delta :
                        offset = fileSize - blockSize
                    f.seek(offset)
                    data = f.read(blockSize)
                    if not data :   break
                    hasher.update(data)
                    #print(offset)  # for debugging/compat with bash script
                    offset += delta
            return hasher.hexdigest()
        except FileNotFoundError:
            print(f"Datei nicht gefunden: {filename}")
            return None
        except PermissionError:
            print(f"Keine Zugriffsrechte auf: {filename}")
            return None
        except OSError as e:
            print(f"Dateifehler: {e}")
            return None
    else: # Hash the whole file
        try:
            with open(filename, 'rb') as f:
                while True:
                    data = f.read(65536)
                    if not data:   break
                    hasher.update(data)
            return hasher.hexdigest()
        except FileNotFoundError:
            print(f"Datei nicht gefunden: {filename}")
            return None
        except PermissionError:
            print(f"Keine Zugriffsrechte auf: {filename}")
            return None
        except OSError as e:
            print(f"Dateifehler: {e}")
            return None


def search_files( folder ):
    global fileDB, searchStopFlag, searchFileCnt

    status_write( f"Search in:{folder}" )

    searchFileCnt = 0;
    time_last = 0

    if searchStopFlag:
        status_write( f"Search in:{folder} stopped by stop key!" )
        return

    for dirpath, dirnames, filenames in os.walk(folder):
        # print(f'Current directory: {dirpath}')
        for filename in filenames:
            # If STOP flag is active then stop further operations immediatly
            if searchStopFlag:
                status_write( f"Search in:{folder} stopped by stop key!" )
                return
            # Define the FULL path/filename thing for accessing files absolute
            file_path = os.path.join(dirpath, filename)
            # Links will not be handled but ignored instead
            if not os.path.isfile( file_path ):   continue

            size_bytes = os.path.getsize(file_path)
            searchFileCnt += 1

            # every second print the number of files found, yet
            time_now = time.time()
            if time_now - time_last >= 1.0:
                search_files.label.config(text=f"Processed: {searchFileCnt:,}")
                #search_files.label.update_idletasks()
                search_files.label.update()
                time_last = time_now

            # if this is the first file with this size ...
            if size_bytes not in fileDB:
                # store the size as key, filename in set, and DO NOT calculate the HASH
                fileDB[size_bytes] = { '0' : { file_path : tk.BooleanVar(value=False) } }
            else:
                # Get the DICT hash:{fn1, fn2 ...} for the size of this file
                size_db = fileDB[size_bytes]
                # if we have only 1 item, yet ... calculate its HASH and create heash branch
                # and move previous element into new branch, later add also new item
                if '0' in size_db:
                    # Get the only key we have in this DICT, yet
                    #print(f'\nsize: {size_bytes} - file: {file_path}\nsdb: {size_db}')
                    file_old, file_flag = next(iter( size_db['0'].items() ))
                    # calculate HASH of the old/1st item, we did not before to save time
                    hashval = calc_b3_fast( file_old )
                    if not hashval:   continue
                    del size_db['0']
                    size_db[hashval] = { file_old : file_flag }

                # calculate HASH of the new item
                hashval = calc_b3_fast( file_path )
                if not hashval:   continue
                if hashval in size_db:
                    if file_path not in size_db[hashval]:
                        size_db[hashval][file_path] = tk.BooleanVar(value=False)
                else:
                    size_db[hashval] = { file_path : tk.BooleanVar(value=False) }

    # at the end display the complete number of files checked
    search_files.label.config(text=f"Processed: {searchFileCnt:,}")
    search_files.label.update()


def search_start():
    global searchFolders, searchStopFlag

    searchStopFlag = False

    for folder in searchFolders:
        # if search is disabled, continue with next folder
        if searchFolders[folder] == 0:
            continue
        search_files(folder)
        if searchStopFlag:
            status_write( "Search stopped by user!" )
            break

    if not searchStopFlag:
        status_write( "Search done!" )
        search_cleanup()
        search_update()

def search_stop():
    global searchStopFlag
    searchStopFlag = True
    status_write( "STOP button pressed!" )

def search_cleanup():
    global fileDB
    status_write( "Remove single entries ..." )
    groups=0
    # Walk through the whole 'size' dictonary and delete all hash entries with only 1 file
    # Use list() because we may delete entries from dictionaries inside this loop
    for size in list(fileDB):
        for hashval in list(fileDB[size]):
            # if only 1 file in this set then it cannot be a duplicate -> delete
            if len(fileDB[size][hashval]) <= 1 :
                del fileDB[size][hashval]
        # if we have no hash element in this size entry anymore then delete this size entry
        grps = len(fileDB[size])
        if not grps:
            del fileDB[size]
        else:
            groups += grps
    status_write( f"Remove single entries ... DONE, {groups} groups found" )


def search_del_flag_chg(c, f):
    e =  c.entry
    if f:
        c.set(1)
        e.config(bg=colorFile[1])
    else:
        c.set(0)
        e.config(bg=colorFile[0])


def search_update():
    global fileDB, lastSelectedFile, colorFile

    if not hasattr(search_update, "frame"):
        sys.exit("ERROR: Call to 'search_update' but not initialized 'search_update.frame'")

    i=0
    status_write( "Build list with duplicates ..." )

    # Completely remove the old list
    for widget in search_update.frame.winfo_children():  widget.destroy()

    # Walk over all sizes and re-build a new list
    for size in fileDB:
        size_db = fileDB[size]
        # Walk over all hashes and create a frame per hash with headline
        for hashval in size_db:
            hash_db = size_db[hashval]
            frameH = tk.Frame(search_update.frame, borderwidth=1, relief='solid', bg=colorFrame[i] )
            frameH.pack(fill='x', padx=2, pady=1, expand=True, side='top')
            hsize = humread( size )
            tk.Label(frameH, text=f"{hsize} ({size:,}) - {hashval}", bg=colorFrame[i], font=('Arial', 9) ).pack(side='top', fill='x')
            i ^= 1
            # Walk over all files, create a frameL per file with filename and selectors
            for filename in hash_db:
                # A HASH frame contains multiple FILE frames, one per file
                frameL = tk.Frame(frameH)
                flagObj = hash_db[filename]
                #print (flagObj, hash_db[filename] )
                # a FILE frame has a Checkbutton, Button, Entry
                chkb = tk.Checkbutton(frameL, text="del ", variable=flagObj )
                chkb.pack(side='left')
                butt = tk.Button(frameL, text="del now", font=('Arial', 8),
                                 command=lambda s=size, h=hashval, f=filename, l=frameL, g=frameH:
                                         search_delete_direct(s,h,f,l,g) )
                butt.pack(side='left')
                entry = tk.Entry(frameL,
                                 textvariable=tk.StringVar(value=filename),
                                 font='TkFixedFont',
                                 bg=colorFile[flagObj.get()],
                                 state="readonly",
                                 readonlybackground='' )
                entry.pack(side='left', fill='x', expand=True)
                entry.bind('<FocusIn>', lambda event, e=entry:
                           globals().__setitem__('lastSelectedFile', os.path.dirname(e.get())))
                # save the entry at flag object to be able to change background color
                flagObj.entry = entry
                # if checkbutton toggles, define callback lambda to change background of entry
                chkb.config(command=lambda v=flagObj:
                    v.entry.config(bg=colorFile[1] if v.get() else colorFile[0]))

                # line is complete now, display it
                frameL.pack(fill='x', padx=2, pady=1, expand=True, side='top')

    status_write( "Build list with duplicates ... DONE" )

def search_delete_file_from_db(size, hashval, filename):
    global fileDB
    status_write( f"Delete from DB: {filename}" )

    # Now delete the entry for this file
    del fileDB[size][hashval][filename]

    # if less than 2 files for this hash then delete the hash
    l = len(fileDB[size][hashval])
    if l < 2:
        if (l == 1):
            filename = next(iter(fileDB[size][hashval]))    # get remaining key
            delFlag = fileDB[size][hashval][filename].get()
            # if also the last file shall be deleted, do NOT delete the branch
            # below because otherwise we get an error at deleting the last one
            if delFlag:  return

        del fileDB[size][hashval]
        # if no more file hashs for this size, delete size entry
        if len(fileDB[size]) == 0:
            del fileDB[size]

def search_delete_direct(size, hashval, filename, linewidget, hashwidget):
    global fileDB
    status_write( f"Delete direct: {filename}" )
    # Delete the file
    delete_file(filename)

    # Delete the entry in the data base, remove full branch if less than 2 files
    search_delete_file_from_db(size, hashval, filename)

    # remove only the line if other files there, otherwise complete hash entry
    if (size in fileDB) and (hashval in fileDB[size]):
        linewidget.destroy()
    else:
        hashwidget.destroy()

def search_delete_marked():
    global fileDB
    status_write( "Delete marked!" )

    toDeleteInDB = []

    # Walk over all sizes
    for size in fileDB:
        size_db = fileDB[size]
        # Walk over all hashes
        for hashval in size_db:
            hash_db = size_db[hashval]
            # Walk over all files and delete all which are checked/marked
            for filename in hash_db:
                delFlag = hash_db[filename].get()
                #print(f'{filename} : {delFlag}')
                if delFlag :
                    status_write( f"Delete marked: {filename}" )
                    delete_file(filename)
                    folder = os.path.dirname(filename)
                    if is_dir_empty(folder):
                        status_write( f"Delete empty folder: {folder}" )
                        delete_empty_folder(folder)
                    toDeleteInDB.append((size, hashval, filename))

    # Now really delete the DB entries to be deleted, do it here to not screw up the loops above
    for size, hashval, filename in toDeleteInDB:
        search_delete_file_from_db(size, hashval, filename)

    # Update the displayed list of duplicate files
    search_update()

def search_show():
    global fileDB
    print(fileDB)

def search_save():
    global fileDB

def search_restore():
    global fileDB

def wmake_search( tab ):
    # Create button frame
    butSearchFrame = ttk.Frame( tab )
    butSearchFrame.pack(padx = 10, pady=5, side=tk.TOP)
    # "START" button
    butSearchStart = tk.Button( butSearchFrame, text='START search', command=search_start, bg=colorButt[0] )
    butSearchStart.pack(padx = 10, pady=5, side=tk.LEFT)
    # "STOP" button
    butSearchStop = tk.Button( butSearchFrame, text='STOP search', command=search_stop, bg=colorButt[2] )
    butSearchStop.pack(padx = 10, pady=5, side=tk.LEFT)
    # "DELETE marked" button
    butSearchDel = tk.Button( butSearchFrame, text='Delete marked', command=search_delete_marked, bg=colorButt[1] )
    butSearchDel.pack(padx = 10, pady=5, side=tk.LEFT)
    # "SHOW DB" button
    #butSearchStop = tk.Button( butSearchFrame, text='SHOW_DB', command=search_show, bg=colorButt[3] )
    #butSearchStop.pack(padx = 10, pady=5, side=tk.LEFT)
    # Create a scrollable frame to hold all the file groups/entries

    labelSearchProgress = tk.Label( butSearchFrame, text='Progress: ' )
    labelSearchProgress.pack(padx = 10, pady=5, side=tk.LEFT)
    search_files.label = labelSearchProgress

    # "Save list" button
    butSearchStart = tk.Button( butSearchFrame, text='Save list', command=search_save, bg=colorButt[4] )
    butSearchStart.pack(padx = 10, pady=5, side=tk.LEFT)
    # "Restore list" button
    butSearchStop = tk.Button( butSearchFrame, text='Restore list', command=search_restore, bg=colorButt[3] )
    butSearchStop.pack(padx = 10, pady=5, side=tk.LEFT)


    sf = ScrollableFrame( tab )
    sf.pack(fill='both', expand=True)
    doubles_scrollable_frame = sf.scrollable_frame
    # Fill in the files
    search_update.frame = doubles_scrollable_frame
    search_update()

# ------------------------------------------------------------------------------
# Mark to delete ---------------------------------------------------------------

def mark_length_name(db, s, flagNot, flagIgCa):
    # 1) get unique lengths in descending order
    L = sorted({len(os.path.basename(k)) for k in db}, reverse=flagNot)
    #L = sorted({len(k) for k in d1}, reverse=True)
    # 2) give each key its own list
    d2 = {length: [] for length in L}
    # 3) append each original key to the right bucket
    for k in db:  d2[len(os.path.basename(k))].append(k)
    # 4) set flags of files in 1st list to False and all other to True
    flag = False
    for l in d2:
        for k in d2[l]:
            # db[k].set(flag)
            search_del_flag_chg( db[k], flag )
            # print(f'{flag} : {k}')
            flag = True

# ---------------------------------------
def mark_length_path(db, s, flagNot, flagIgCa):
    L = sorted({len(os.path.dirname(k)) for k in db}, reverse=flagNot)
    d2 = {length: [] for length in L}
    for k in db:  d2[len(os.path.dirname(k))].append(k)
    flag = False
    for l in d2:
        for k in d2[l]:
            # db[k].set(flag)
            search_del_flag_chg( db[k], flag )
            # print(f'{flag} : {k}')
            flag = True

# ---------------------------------------
def mark_alpha_path(db, s, flagNot, flagIgCa):
    d2 = sorted({k for k in db}, reverse=flagNot)
    flag = False
    for k in d2:
        # db[k].set(flag)
        search_del_flag_chg( db[k], flag )
        # print(f'{flag} : {k}')
        flag = True

# ---------------------------------------
def mark_on_path(db, s, flagNot, flagIgCa):
    flag = 0
    # Check if we have  both cases, some in path, some not in path
    for k in db:   flag |= 1 if k.startswith(s.get()) else 2
    # We only process if both cases are fullfilled
    if flag == 3:
        for k in db:
            flag = flagNot  if k.startswith(s.get())  else  not flagNot
            # db[k].set(flag)
            search_del_flag_chg( db[k], flag )

# ---------------------------------------
def mark_one_word_file(db, s, flagNot, flagIgCa):
    flag = 0
    words = s.get().lower().split()  if flagIgCa  else  s.get().split()
    # Check if we have  both cases, some in path, some not in path
    for k in db:
        x = os.path.basename(k).lower()  if flagIgCa  else  os.path.basename(k)
        flag |= 1 if any(w in x for w in words) else 2
    # We only process if both cases are fullfilled
    if flag == 3:
        for k in db:
            x = os.path.basename(k).lower()  if flagIgCa  else  os.path.basename(k)
            flag = flagNot  if any(w in x for w in words) else  not flagNot
            # db[k].set(flag)
            search_del_flag_chg( db[k], flag )

# ---------------------------------------
def mark_all_words_file(db, s, flagNot, flagIgCa):
    flag = 0
    words = s.get().lower().split()  if flagIgCa  else  s.get().split()
    # Check if we have both cases, some in path, some not in path
    for k in db:
        x = os.path.basename(k).lower()  if flagIgCa  else  os.path.basename(k)
        flag |= 1 if all(w in x for w in words) else 2
    # We only process if both cases are fullfilled
    if flag == 3:
        for k in db:
            x = os.path.basename(k).lower()  if flagIgCa  else  os.path.basename(k)
            flag = flagNot  if all(w in x for w in words) else  not flagNot
            # db[k].set(flag)
            search_del_flag_chg( db[k], flag )

# ---------------------------------------
def mark_one_word_path(db, s, flagNot, flagIgCa):
    flag = 0
    words = s.get().lower().split()  if flagIgCa  else  s.get().split()
    # Check if we have  both cases, some in path, some not in path
    for k in db:
        x = os.path.dirname(k).lower()  if flagIgCa  else  os.path.dirname(k)
        flag |= 1 if any(w in x for w in words) else 2
    # We only process if both cases are fullfilled
    if flag == 3:
        for k in db:
            x = os.path.dirname(k).lower()  if flagIgCa  else  os.path.dirname(k)
            flag = flagNot  if any(w in x for w in words) else  not flagNot
            # db[k].set(flag)
            search_del_flag_chg( db[k], flag )

# ---------------------------------------
def mark_all_words_path(db, s, flagNot, flagIgCa):
    flag = 0
    words = s.get().lower().split()  if flagIgCa  else  s.get().split()
    # Check if we have  both cases, some in path, some not in path
    for k in db:
        x = os.path.dirname(k).lower()  if flagIgCa  else  os.path.dirname(k)
        flag |= 1 if all(w in x for w in words) else 2
    # We only process if both cases are fullfilled
    if flag == 3:
        for k in db:
            x = os.path.dirname(k).lower()  if flagIgCa  else  os.path.dirname(k)
            flag = flagNot  if all(w in x for w in words) else  not flagNot
            # db[k].set(flag)
            search_del_flag_chg( db[k], flag )

# ---------------------------------------
def mark_one_word_pafi(db, s, flagNot, flagIgCa):
    flag = 0
    words = s.get().lower().split()  if flagIgCa  else  s.get().split()
    # Check if we have  both cases, some in path, some not in path
    for k in db:
        x = k.lower()  if flagIgCa  else  k
        flag |= 1 if any(w in x for w in words) else 2
    # We only process if both cases are fullfilled
    if flag == 3:
        for k in db:
            x = k.lower()  if flagIgCa  else  k
            flag = flagNot  if any(w in x for w in words) else  not flagNot
            # db[k].set(flag)
            search_del_flag_chg( db[k], flag )

# ---------------------------------------
def mark_all_words_pafi(db, s, flagNot, flagIgCa):
    flag = 0
    words = s.get().lower().split()  if flagIgCa  else  s.get().split()
    # Check if we have  both cases, some in path, some not in path
    for k in db:
        x = k.lower()  if flagIgCa  else  k
        flag |= 1 if all(w in x for w in words) else 2
    # We only process if both cases are fullfilled
    if flag == 3:
        for k in db:
            x = k.lower()  if flagIgCa  else  k
            flag = flagNot  if all(w in x for w in words) else  not flagNot
            # db[k].set(flag)
            search_del_flag_chg( db[k], flag )

# ---------------------------------------
def mark_process( func, sVar, flagCond, flagIgCa ):
    global fileDB
    # Walk over all sizes
    for size in fileDB.keys():
        size_db = fileDB[size]
        # Walk over all hashes and
        for hashval in size_db.keys():
            hash_db = size_db[hashval]
            func(hash_db, sVar, flagCond, flagIgCa)

def mark_strings_extract():
    if not hasattr(mark_strings_extract, "markOptionVars"):
        sys.exit("ERROR: Call to 'mark_strings_extract' but not initialized 'markOptionVars'")

    values = [ sv.get() for sv in mark_strings_extract.markOptionVars ]
    return values

def mark_strings_restore( svs, values ):
    for sv, val in zip(svs, values):
        sv.set(val)
        #print(f'{sv} - {val}')

def wmake_mark( tab ):
    markOptions=(
        [mark_length_name    , "Keep file with SHORTEST FILENAME"              , None ],
        [mark_length_path    , "Keep file with SHORTEST PATHNAME"              , None ],
        [mark_on_path        , "Keep file which is in this PATH:"              , None, colorBlock[0], "pick" ],
        [mark_alpha_path     , "Keep file with ALPHABETIC FIRST in PATHFILE"   , None ],
        [mark_one_word_file  , "Keep file with ONE of these WORDS in FILENAME:", None, colorBlock[1] ],
        [mark_all_words_file , "Keep file with ALL of these WORDS in FILENAME:", None, colorBlock[1] ],
        [mark_one_word_path  , "Keep file with ONE of these WORDS in PATHNAME:", None, colorBlock[2] ],
        [mark_all_words_path , "Keep file with ALL of these WORDS in PATHNAME:", None, colorBlock[2] ],
        [mark_one_word_pafi  , "Keep file with ONE of these WORDS in PATHFILE:", None, colorBlock[3] ],
        [mark_all_words_pafi , "Keep file with ALL of these WORDS in PATHFILE:", None, colorBlock[3] ] )

    chkbCond = tk_variables_register_and_init('CheckNotInvert', 'bool')
    chkbIgCa = tk_variables_register_and_init('CheckIgnoreCase', 'bool')

    i=0
    for row in markOptions:
        if len(row)>3:
           row[2] = tk_variables_register_and_init(f'MarkText{i}', 'string')
           i += 1

    # Inverter/NOT checkbox
    frameL = tk.Frame(tab)
    frameL.pack(fill='x', padx=2, pady=(10,0), expand=True, side='top')
    chkbNot = tk.Checkbutton(frameL, text="NOT (invert, longest, not one, not all)", variable=chkbCond, bg='#EFD0D0' )
    chkbNot.pack(side='left', pady=(0,0), expand=True)
    chkbIgn = tk.Checkbutton(frameL, text="ignore case (WORDS)", variable=chkbIgCa, bg='#D0D0EF' )
    chkbIgn.pack(side='left', pady=(0,0), expand=True)

    # Create a scrollable frame to hold all the mark options
    sf = ScrollableFrame( tab )
    sf.pack(fill='both', expand=True)
    mark_scrollable_frame = sf.scrollable_frame

    # Fill in all the different possible selections from table above
    for maOpt in markOptions:
        frameL = ttk.Frame( mark_scrollable_frame )
        frameL.pack(padx = 2, pady=1, fill="x", expand=True, side=tk.TOP)
        but = tk.Button( frameL, text='mark', font=('Arial', 8) )
        but.pack(padx = 2, pady=0, side=tk.LEFT)
        tk.Label(frameL, text=maOpt[1] ).pack(side=tk.LEFT, fill='x')
        if len(maOpt) > 3:
            entry = tk.Entry(frameL, textvariable=maOpt[2], font='TkFixedFont', bg=maOpt[3] )
            entry.pack(side='left', padx=2, fill='x', expand=True)
            if len(maOpt) > 4:
                but_pick = tk.Button( frameL, text='pick', font=('Arial', 8) )
                but_pick.pack(padx = 2, pady=0, side=tk.LEFT)
                but_pick.config( command=lambda c=maOpt[2]: c.set(lastSelectedFile) )

        but.config( command=lambda f=maOpt[0], s=maOpt[2]: mark_process(f,s,chkbCond.get(),chkbIgCa.get()) )

# ------------------------------------------------------------------------------
# Settings ---------------------------------------------------------------------

def wmake_settings( tab ):
    global initData

    chkbDELF    = tk_variables_register_and_init('DelEmptyFolder', 'bool')
    chkbSTMT    = tk_variables_register_and_init('SaveMarkTexts' , 'bool')
    chkbSFDB    = tk_variables_register_and_init('SaveFileDB'    , 'bool')
    chkbFASE    = tk_variables_register_and_init('UseFastHash'   , 'bool')
    blockSize   = tk_variables_register_and_init('HashBlkSize'   , 'string')
    blockSizeHR = tk_variables_register_and_init('HashBlkSizeHR' , 'string')
    blockNum    = tk_variables_register_and_init('HashBlkNum'    , 'string')
    blockTotal  = tk_variables_register_and_init('HashBlkTotal'  , 'string')

    tk.Checkbutton(tab, text="Delete folder if they become empty by file removement",
        variable=chkbDELF ).pack(anchor="w", side='top', pady=(10,5) )

    tk.Checkbutton(tab, text="Save settings from the MARK tab at program's end",
        variable=chkbSTMT ).pack(anchor="w", side='top', pady=5)

    tk.Checkbutton(tab, text="Store file database at program's end to continue on next start without new 'search'",
        variable=chkbSFDB ).pack(anchor="w", side='top', pady=5)

    # Create a frame for the fast hash options
    def blockUpdate():
        bs = "(" + humread(1 << (int(blockSize.get()))) + ")"
        bt = " = " + humread(int(blockNum.get()) << (int(blockSize.get())))
        blockSizeHR.set(bs)
        blockTotal.set(bt)

    fastHashFrame = ttk.Frame( tab )
    fastHashFrame.pack(anchor="w", side='top', fill="x")

    tk.Checkbutton(fastHashFrame, text="Use fast file hashing for big files",
        variable=chkbDELF ).pack(anchor="w", side='left', pady=(10,5) )

    label = tk.Label(fastHashFrame, text="Block: 2^")
    label.pack(anchor="w", side='left', padx=(25,0), pady=(10,5), fill="x")

    spinbox = tk.Spinbox( fastHashFrame, from_= 9, to=30, wrap=True, width=3,
        textvariable=blockSize,
        command=blockUpdate )
    spinbox.pack(anchor="w", side='left', pady=(10,5), padx=(2,5))

    # A helper label to show the selected value in a human readable format
    label = tk.Label(fastHashFrame, textvariable=blockSizeHR)
    label.pack(anchor="w", side='left', padx=5, pady=(10,5), fill="x")

    # - - -

    label = tk.Label(fastHashFrame, text=" x  #blocks:")
    label.pack(anchor="w", side='left', padx=0, pady=(10,5), fill="x")

    spinbox = tk.Spinbox( fastHashFrame, from_= 3, to=100, wrap=True, width=3,
        textvariable=blockNum, command=blockUpdate )
    spinbox.pack(anchor="w", side='left', pady=(10,5), padx=(2,5))

    label = tk.Label(fastHashFrame, textvariable=blockTotal)
    label.pack(anchor="w", side='left', padx=0, pady=(10,5), fill="x")

    blockUpdate()

# ------------------------------------------------------------------------------
# MAIN -------------------------------------------------------------------------

def main( root ):              # Fill my main windows with life

    if sys.version_info < (3, 6):
        sys.exit("ERROR: This script requires Python 3.6 or higher.")

    wmake_menu( root )

    wmake_status_area( root )

    tabs = { 'FOLD' : [ ' Select Folder ', None ],
             'EXCL' : [ ' Exclude from selection ', None ],
             'FIND' : [ ' Find Dups ', None ],
             'MARK' : [ ' Mark to delete ', None ],
             'PARM' : [ ' Settings ', None ] }
    wmake_tabs( root, tabs )

    wmake_search_folder( tabs['FOLD'][1] )

    wmake_exclude( tabs['EXCL'][1] )

    wmake_search( tabs['FIND'][1] )

    wmake_mark( tabs['MARK'][1] )

    wmake_settings( tabs['PARM'][1] )

# ------------------------------------------------------------------------------
#                             E N T R Y                                        I
# ------------------------------------------------------------------------------

if __name__ == "__main__":
    # Load the data from *.ini file or defaults and store in global variables
    init_data_load()

    #print("initData1:", initData)

    # Register the EXIT handler
    atexit.register(on_exit)

    # Create my root window (main windows) -------------------------------------
    root = tk.Tk()

    # Check data from e.g. *.ini file or defaults for consistency, root is needed
    init_data_check( root )

    #print("initData2:", initData)

    # Save program window information in my init data (to restore on next start)
    def on_win_change_update():
        global initData, root
        initData['winSizeX'], initData['winSizeY'], initData['winPosX'], initData['winPosY'] =  \
          [int(p) for p in root.geometry().replace("x","+").split("+")]
        #print("WIN: ", initData['winPosX'], initData['winPosY'], initData['winSizeX'], initData['winSizeY'])

    afterId = None

    # Update my stored root window parameters if root window resized or moved
    def on_win_change(event):
        global afterId, root
        if afterId is not None:
            root.after_cancel(afterId)
        afterId = root.after(500, on_win_change_update)  # Wait 500 ms after the last event

    # Configure the root window
    root.bind("<Configure>", on_win_change)

    #print("initData3:", initData)

    root.geometry(f"{initData['winSizeX']}x{initData['winSizeY']}+{initData['winPosX']}+{initData['winPosY']}")
    root.title('De-Duplicator')

    main( root )

    root.mainloop()

