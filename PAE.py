'''
Created on Dec 14, 2015

@author: zhouchao
'''
from tkinter import *
import tkinter as tk
from tkinter import filedialog
from tkinter import ttk
from tkinter import messagebox
import traceback
import multiprocessing, shutil, os
from multiprocessing import Pool, Manager

# Import from new modular structure
from src.atp_handler import read_csv, read_pinmap, analyse_merge_config, build_config_from_classical
from src.pattern_processor import edit_pattern, extract_cycle_on_keyword
from src.utils import in_list
from src.main import process_atp_classical, process_atp_simple, dispatch_config_parallel
from src.logger import Logger

multiprocessing.freeze_support()

version = 'V1.14.0'

class PatAutoEditApp(tk.Tk):

    def __init__(self):
        super().__init__()  # 有点相当于tk.Tk()
        self.ATPfilename = []
        self.CSVfilename = []
        self.createWidgets()
        self.Pinmapfilename = [] #""
        self.FileFolder = ''
        self.logger = Logger(gui_callback=self.put_data_log)

    def createWidgets(self):
        self.title('Pattern Auto Edit Tool ' + version)
        # used to set each widget to resize together
        self.rowconfigure(0, weight=0, minsize=30)
        self.rowconfigure(1, weight=1, minsize=50)
        self.columnconfigure(0, weight=1, minsize=50)
        self.columnconfigure(1, weight=0)

        # create a notebook
        notebook = ttk.Notebook(self)
        notebook.grid(row=0, column=0, sticky="nsew")

        topframe = ttk.Frame(notebook, height=80, borderwidth=1)
        topframe_simple = ttk.Frame(notebook, height=80, borderwidth=1)
        topframe_utils = ttk.Frame(notebook, height=80, borderwidth=1)
        contentframe = ttk.Frame(self, height=80, borderwidth=1)
        contentframe.rowconfigure(0, weight=1)
        contentframe.columnconfigure(0, weight=1)
        topframe.grid(row=0, column=0, sticky=tk.W + tk.S + tk.E + tk.N)
        topframe_simple.grid(row=0, column=0, sticky=tk.W + tk.S + tk.E + tk.N)
        topframe_utils.grid(row=0, column=0, sticky=tk.W + tk.S + tk.E + tk.N)
        contentframe.grid(row=1, column=0, sticky=tk.W + tk.S + tk.E + tk.N)

        notebook.add(topframe, text='Classical')
        notebook.add(topframe_simple, text='Simplified')
        notebook.add(topframe_utils, text='Utils')

        # Step 1. Please enter ATP file path and name:
        self.ety2 = tk.Entry(topframe, width=40)
        self.ety2.grid(row=0, column=0)

        self.btn2 = tk.Button(
            topframe,
            text='Select ATP Files',
            command=lambda: self.CallATPFile(self.contents2), width=30)
        self.btn2.grid(row=0, column=1)

        self.contents2 = StringVar()
        self.contents2.set("Please Select ATP Files")
        self.ety2.config(textvariable=self.contents2)

        # Step 2. Please enter CSV file path and name:
        self.ety3 = tk.Entry(topframe, width=40)
        self.ety3.grid(row=1, column=0)

        self.btn3 = tk.Button(
            topframe,
            text='Select CSV Files',
            command=lambda: self.CallCSVFile(self.contents3), width=30)
        self.btn3.grid(row=1, column=1)

        self.contents3 = StringVar()
        self.contents3.set("Please Select CSV File")
        self.ety3.config(textvariable=self.contents3)

        # Step 3. Pin Name Entry
        self.ety = tk.Entry(topframe, width=40)
        self.ety.grid(row=2, column=0)

        self.contents4 = StringVar()
        self.contents4.set("Please Enter the Pin Name")
        self.ety.config(textvariable=self.contents4)

        # Step 4. Please choose function
        CmbList = ['DSSC Capture', 'DSSC Source', 'CMEM/HRAM Capture', 'Expand Pattern', 'Compress Pattern', 'WFLAG',
                   'Add Opcode', 'Remove Opcode']
        self.cmb = ttk.Combobox(topframe, values=CmbList, width=37)
        self.cmb.grid(row=3, column=0)

        self.contents5 = StringVar()
        self.contents5.set("[Please Select Capture Mode]")
        self.cmb.config(textvariable=self.contents5)

        # Step 5. Please enter pinmap file path and name:
        self.ety4 = tk.Entry(topframe, width=40)
        self.ety4.grid(row=4, column=0)

        self.btn4 = tk.Button(
            topframe,
            text='Optional: Select Pinmap File',
            command=lambda: self.CallPinmapFile(self.contents4), width=30)
        self.btn4.grid(row=4, column=1)

        self.contents4 = StringVar()
        self.contents4.set("Optional: Please Select Pinmap File")
        self.ety4.config(textvariable=self.contents4)

        self.check_box_Label2 = ttk.Label(topframe, text='Time Mode:\t\t')
        self.check_box_var2 = StringVar()
        self.check_box3 = ttk.Radiobutton(topframe,
                                          text=u'Single',
                                          variable=self.check_box_var2,
                                          value='Single',
                                          command=self.on_radiobox_changed)
        self.check_box4 = ttk.Radiobutton(topframe,
                                          text=u'Dual',
                                          variable=self.check_box_var2,
                                          value='Dual',
                                          command=self.on_radiobox_changed)
        self.check_box_var2.set('Single')
        self.check_box_Label2.grid(row=5, column=0, sticky='E')
        self.check_box3.grid(row=5, column=1, sticky='W')
        self.check_box4.grid(row=5, column=1, sticky='E')

        # Step 6, button
        self.btn = tk.Button(topframe, text='Generate', command=self.run_classical_multiprocess)
        self.btn.grid(row=7, column=0, columnspan=2)

        # Step 7. Label Name Entry
        self.ety_user_string = tk.Entry(topframe, width=40)
        self.ety_user_string.grid(row=3, column=1)

        self.contents7 = StringVar()
        self.contents7.set("Please Enter the User String")
        self.ety_user_string.config(textvariable=self.contents7)

        # Step 8. Please choose index mode
        self.check_box_Label = ttk.Label(topframe, text='Index Mode:\t\t')
        self.check_box_var1 = StringVar()
        self.check_box1 = ttk.Radiobutton(topframe,
                                          text=u'Cycle',
                                          variable=self.check_box_var1,
                                          value='Cycle',
                                          command=self.on_radiobox_changed)
        self.check_box2 = ttk.Radiobutton(topframe,
                                          text=u'Vector',
                                          variable=self.check_box_var1,
                                          value='Vector',
                                          command=self.on_radiobox_changed)
        self.check_box_var1.set('Cycle')
        self.check_box_Label.grid(row=6, column=0, sticky='E')
        self.check_box1.grid(row=6, column=1, sticky='W')
        self.check_box2.grid(row=6, column=1, sticky='E')

        # Simplified Tab
        # Step 1. Please enter ATP file path and name:
        self.ety2_simple = tk.Entry(topframe_simple, width=40)
        self.ety2_simple.grid(row=0, column=0)
        self.btn2_simple = tk.Button(
            topframe_simple,
            text='Select ATP Files',
            command=lambda: self.CallATPFile(self.contents2_simple), width=30)
        self.btn2_simple.grid(row=0, column=1)
        self.contents2_simple = StringVar()
        self.contents2_simple.set("Please Select ATP Files")
        self.ety2_simple.config(textvariable=self.contents2_simple)

        # Step 2. Please enter CSV file path and name:
        self.ety3_simple = tk.Entry(topframe_simple, width=40)
        self.ety3_simple.grid(row=1, column=0)
        self.btn3_simple = tk.Button(
            topframe_simple,
            text='Select CSV Files',
            command=lambda: self.CallCSVFile(self.contents3_simple), width=30)
        self.btn3_simple.grid(row=1, column=1)
        self.contents3_simple = StringVar()
        self.contents3_simple.set("Please Select CSV File")
        self.ety3_simple.config(textvariable=self.contents3_simple)

        # Step 3. Please enter pinmap file path and name:
        self.ety4_simple = tk.Entry(topframe_simple, width=40)
        self.ety4_simple.grid(row=4, column=0)

        self.btn4_simple = tk.Button(
            topframe_simple,
            text='Optional: Select Pinmap File',
            command=lambda: self.CallPinmapFile(self.contents4_simple), width=30)
        self.btn4_simple.grid(row=4, column=1)

        self.contents4_simple = StringVar()
        self.contents4_simple.set("Optional: Please Select Pinmap File")
        self.ety4_simple.config(textvariable=self.contents4_simple)

        # Step 6, button
        self.btn_simple = tk.Button(topframe_simple, text='Generate', command=self.run_simple_multiprocess)
        self.btn_simple.grid(row=6, column=0, columnspan=2)

        # Utils Tab
        # Step 1. Please enter ATP file path and name:
        self.ety1_utils = tk.Entry(topframe_utils, width=40)
        self.ety1_utils.grid(row=0, column=0)
        self.btn1_utils = tk.Button(
            topframe_utils,
            text='Select ATP Folder',
            command=lambda: self.GetFolderPath(self.contents1_utils), width=30)
        self.btn1_utils.grid(row=0, column=1)
        self.contents1_utils = StringVar()
        self.contents1_utils.set("Please Select ATP Folder")
        self.ety1_utils.config(textvariable=self.contents1_utils)

        # Step 2. Keyword Entry
        self.ety2_utils = tk.Entry(topframe_utils, width=40)
        self.ety2_utils.grid(row=1, column=0)
        self.contents2_utils = StringVar()
        self.contents2_utils.set("Please Enter the Keyword in ATP Comment")
        self.ety2_utils.config(textvariable=self.contents2_utils)

        # Step 6, Run button
        self.btn_simple = tk.Button(topframe_utils, text='Generate', command=self.run_utils_extract)
        self.btn_simple.grid(row=2, column=0, columnspan=2)


        # output log part
        right_bar = tk.Scrollbar(contentframe, orient=tk.VERTICAL)
        bottom_bar = tk.Scrollbar(contentframe, orient=tk.HORIZONTAL)
        self.textbox = tk.Text(contentframe, yscrollcommand=right_bar.set, xscrollcommand=bottom_bar.set)
        self.textbox.config()
        self.textbox.grid(row=0, column=0, sticky=tk.W + tk.S + tk.E + tk.N)
        right_bar.grid(row=0, column=1, sticky=tk.S + tk.N)
        bottom_bar.grid(row=1, column=0, sticky=tk.W + tk.E)
        right_bar.config(command=self.textbox.yview)
        bottom_bar.config(command=self.textbox.xview)
        
        # Configure text tags for logging
        self.textbox.tag_configure("error", foreground="red", font=("TkDefaultFont", 10, "bold"))
        self.textbox.tag_configure("warning", foreground="orange", font=("TkDefaultFont", 10, "bold"))
        self.textbox.tag_configure("info", foreground="blue", font=("TkDefaultFont", 10))

    def put_data_log(self, data_log):
        # Insert text with appropriate tags based on message type
        if data_log.startswith("Error:"):
            self.textbox.insert(tk.END, data_log + '\n', "error")
        elif data_log.startswith("Warning:"):
            self.textbox.insert(tk.END, data_log + '\n', "warning")
        elif data_log.startswith("Info:"):
            self.textbox.insert(tk.END, data_log + '\n', "info")
        else:
            self.textbox.insert(tk.END, data_log + '\n')
            
        self.textbox.see(tk.END)
        self.textbox.update()

    def on_radiobox_changed(self):
        print(self.check_box_var1.get())

    def run_simple(self):
        """Single-process fallback for the Simplified tab (kept for quick tests)."""
        ATPFile = self.ATPfilename
        CSVFile = self.CSVfilename
        pinmap = self.Pinmapfilename
        if len(pinmap) > 0:
            process_atp_simple(ATPFile, CSVFile[0], self.logger, pinmap[0])
        else:
            process_atp_simple(ATPFile, CSVFile[0], self.logger, "")

    def _start_parallel_run(self, button, config_list):
        """Common plumbing to dispatch a config_list to a fresh multiprocessing pool."""
        self.switchButtonState(button)
        ATPFiles = self.ATPfilename
        PinMap = self.Pinmapfilename
        pin_map_value = PinMap[0] if len(PinMap) > 0 else ""

        self.queue = Manager().Queue()
        self.counter = Manager().Value('i', 0)
        self.pool = Pool(processes=4)

        try:
            mp_logger = Logger(gui_callback=self.queue.put)
            self.active_button = button
            self.total_tasks = dispatch_config_parallel(
                self.pool, ATPFiles, config_list, mp_logger, pin_map_value, self.my_callback
            )
            if self.total_tasks == 0:
                self.logger.warning("No tasks dispatched (check CSV / ATP file selection).")
                self.switchButtonState(button)
                return
            self.after(500, self.update_progress)
        except Exception:
            error_msg = traceback.format_exc()
            self.put_data_log(error_msg)
            self.switchButtonState(button)

    def run_simple_multiprocess(self):
        """Simplified tab Generate — parses multi-column CSV and dispatches in parallel."""
        CSVFile = self.CSVfilename
        if len(CSVFile) == 0:
            self.logger.error("No CSV file selected !!!")
            return
        try:
            config_list = analyse_merge_config(CSVFile[0], self.logger)
        except Exception:
            self.put_data_log(traceback.format_exc())
            return
        self._start_parallel_run(self.btn_simple, config_list)

    def run_classical_multiprocess(self):
        """Classical tab Generate — builds config list from 2-column CSV + GUI and dispatches in parallel."""
        CSVFiles = self.CSVfilename
        if len(CSVFiles) == 0:
            self.logger.error("No CSV file selected !!!")
            return
        if len(CSVFiles) > 1:
            self.logger.error("Only ONE CSV file supported !!!")
            return

        PinName = self.ety.get()
        Mode = self.cmb.get()
        TimeMode = self.check_box_var2.get()
        IndexMode = self.check_box_var1.get()

        CmbList = ['DSSC Capture', 'DSSC Source', 'CMEM/HRAM Capture', 'Expand Pattern', 'Compress Pattern',
                   'WFLAG', 'Add Opcode', 'Remove Opcode']
        if Mode not in CmbList:
            self.logger.error("Wrong Choice !!!")
            return

        try:
            config_list = build_config_from_classical(CSVFiles[0], Mode, PinName, TimeMode, IndexMode)
        except Exception:
            self.put_data_log(traceback.format_exc())
            return
        self._start_parallel_run(self.btn, config_list)

    def run_utils_extract(self):
        FileFolder = self.contents1_utils.get()
        Keyword = self.contents2_utils.get()

        extract_cycle_on_keyword(FileFolder, Keyword, self.logger)

    def my_callback(self, result):
        self.counter.value += 1
        if self.counter.value == self.total_tasks:
            self.put_data_log("All tasks completed!!!")
            self.switchButtonState(self.active_button)

    def update_progress(self):
        if self.queue.empty() == False:
            message = self.queue.get()
            self.put_data_log(message)
        self.after(500, self.update_progress)

    def switchButtonState(self, button):
        if (button['state'] == tk.NORMAL):
            button['state'] = tk.DISABLED
        else:
            button['state'] = tk.NORMAL

    def CallATPFile(self, contents2):
        self.ATPfilename = tk.filedialog.askopenfilenames(
            filetypes=[('ATP File', '*.atp;*.atp.gz'), ("all", "*.*")])
        contents2.set(self.ATPfilename)

    def CallCSVFile(self, contents3):
        self.CSVfilename = tk.filedialog.askopenfilenames(
            filetypes=[('CSV File', '*.csv'), ("all", "*.*")])
        contents3.set(self.CSVfilename)

    def CallPinmapFile(self, contents3):
        self.Pinmapfilename = tk.filedialog.askopenfilenames(
            filetypes=[('Pinmap File', '*.txt'), ("all", "*.*")])
        contents3.set(self.Pinmapfilename)

    def GetFolderPath(self, contents2):
        # global FolderPath
        self.FolderPath = tk.filedialog.askdirectory()
        contents2.set(self.FolderPath)

    def addmenu(self, Menu):
        Menu(self)


class MyMenu():
    '''class for menu'''

    def __init__(self, root):
        '''initial menu class'''
        self.menubar = tk.Menu(root)  # Create Menu Bar

        # create "File"
        filemenu = tk.Menu(self.menubar, tearoff=0)
        filemenu.add_command(label="Exit", command=root.quit)

        # create "Help"
        helpmenu = tk.Menu(self.menubar, tearoff=0)
        helpmenu.add_command(label="About", command=self.help_about)

        # add menu to menu bar
        self.menubar.add_cascade(label="File", menu=filemenu)
        self.menubar.add_cascade(label="Help", menu=helpmenu)

        # add menu bar to win "root"
        root.config(menu=self.menubar)

    def help_about(self):
        messagebox.showinfo(
            'About',
            'Author：Chao Zhou \n verion ' + version + '\n 感谢您的使用！ \n chao.zhou@teradyne.com ')


if __name__ == '__main__':
    win = PatAutoEditApp()
    win.addmenu(MyMenu)
    win.mainloop()
