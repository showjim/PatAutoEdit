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
from src.atp_handler import read_csv, read_pinmap, analyse_merge_config
from src.pattern_processor import edit_pattern
from src.utils import in_list
from src.main import main4, main11

multiprocessing.freeze_support()

version = 'V1.12.28'

class DemoClass(tk.Tk):

    def __init__(self):
        super().__init__()  # 有点相当于tk.Tk()
        self.ATPfilename = []
        self.CSVfilename = []
        self.createWidgets()
        self.Pinmapfilename = [] #""

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
        contentframe = ttk.Frame(self, height=80, borderwidth=1)
        contentframe.rowconfigure(0, weight=1)
        contentframe.columnconfigure(0, weight=1)
        topframe.grid(row=0, column=0, sticky=tk.W + tk.S + tk.E + tk.N)
        topframe_simple.grid(row=0, column=0, sticky=tk.W + tk.S + tk.E + tk.N)
        contentframe.grid(row=1, column=0, sticky=tk.W + tk.S + tk.E + tk.N)

        notebook.add(topframe, text='Classical')
        notebook.add(topframe_simple, text='Simplified')

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
        self.btn = tk.Button(topframe, text='Generate', command=self.SayHello_MultProcess)
        self.btn.grid(row=7, column=0, columnspan=2)

        # Step 7. Label Name Entry
        self.ety2 = tk.Entry(topframe, width=40)
        self.ety2.grid(row=3, column=1)

        self.contents7 = StringVar()
        self.contents7.set("Please Enter the User String")
        self.ety2.config(textvariable=self.contents7)

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
        self.btn_simple = tk.Button(topframe_simple, text='Generate', command=self.SayHello_simple)
        self.btn_simple.grid(row=6, column=0, columnspan=2)

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

    def SayHello(self):
        ATPFile = self.ATPfilename
        CSVFile = self.CSVfilename
        PinName = self.ety.get()
        Mode = self.cmb.get()
        TimeMode = self.check_box_var2.get()
        UserString = self.ety2.get()
        IndexMode = self.check_box_var1.get()
        textout = self.put_data_log
        pinmap = self.Pinmapfilename
        main4(ATPFile, CSVFile, PinName, Mode, TimeMode, UserString, IndexMode, textout, pinmap)

    def SayHello_simple(self):
        ATPFile = self.ATPfilename
        CSVFile = self.CSVfilename
        pinmap = self.Pinmapfilename
        textout = self.put_data_log
        if len(pinmap) > 0:
            main11(ATPFile, CSVFile[0], textout, pinmap[0])
        else:
            main11(ATPFile, CSVFile[0], textout, "")

    def single_item_post_process_simple(self, preFileName, tmpFileName, ATPFiles, textoutwin, Mode, CmbList, PinName,
                                        CycleRange, time_mode, IndexMode, UserString, result, j):
        if preFileName == tmpFileName:
            OutputPath = os.path.join(os.getcwd(), 'Output')
            otherthing = os.path.join(OutputPath, os.path.basename(ATPFiles[j]))
            shutil.copy(otherthing, ATPFiles[j])

        if j >= 0:
            textoutwin("Info: Start convert file: " + ATPFiles[j])
            print("Info: start convert file: +" + ATPFiles[j])
            if Mode in CmbList:
                result_file = edit_pattern(textoutwin, PinName, ATPFiles[j], CycleRange, Mode, time_mode,
                                          IndexMode, UserString)
                preFileName = tmpFileName
                if result_file not in result:
                    result.append(result_file)
            else:
                textoutwin("Error: Wrong Choice !!!")
                print("Error: Wrong Choice !!!")
            textoutwin("Info: Done conversion")
            print("Info: Done conversion")
        else:
            textoutwin("Warning: Cannot find atp file: " + tmpFileName)
            print("Warning: Cannot find atp file: " + tmpFileName)

        return preFileName

    def SayHello_simple_MultProcess(self):
        self.switchButtonState(self.btn_simple)
        ATPFiles = self.ATPfilename
        CSVFile = self.CSVfilename
        merge_config_file = CSVFile[0]

        textoutwin = self.put_data_log
        self.queue = Manager().Queue()
        self.counter = Manager().Value('i', 0)
        self.pool = Pool(processes=4)  # max 4 processes

        try:
            config_list = analyse_merge_config(merge_config_file, textoutwin)

            CmbList = ['DSSC Capture', 'DSSC Source', 'CMEM/HRAM Capture', 'Expand Pattern', 'Compress Pattern',
                       'WFLAG', 'Add Opcode', 'Remove Opcode']

            preFileName = ""
            result = []
            self.total_tasks = 0
            for config_item in config_list:
                tmpFileName = config_item["ATPFile"]
                Mode = config_item["Mode"]
                PinName = config_item["PinName"]
                CycleRange = config_item["CycleRange"]
                TimeMode = config_item["TimeMode"]
                if TimeMode == 'Single':
                    time_mode = '1'
                elif TimeMode == 'Dual':
                    time_mode = '2'
                IndexMode = config_item["IndexMode"]
                UserString = ""
                j = in_list(tmpFileName, ATPFiles)
                self.total_tasks += 1
                self.pool.apply_async(self.single_item_post_process_simple,
                                      args=(preFileName, tmpFileName, ATPFiles, textoutwin, Mode, CmbList, PinName,
                                            CycleRange, time_mode, IndexMode, UserString, result, j),
                                      callback=self.my_callback)
            self.after(500, self.update_progress)
        except Exception:
            error_msg = traceback.format_exc()
            self.put_data_log(error_msg)
            self.switchButtonState(self.btn)

    def SayHello_MultProcess(self):
        self.switchButtonState(self.btn)

        ATPFiles = self.ATPfilename
        CSVFiles = self.CSVfilename
        PinName = self.ety.get()
        Mode = self.cmb.get()
        TimeMode = self.check_box_var2.get()
        UserString = self.ety2.get()
        IndexMode = self.check_box_var1.get()
        textoutwin = self.put_data_log
        PinMap = self.Pinmapfilename

        self.queue = Manager().Queue()
        self.counter = Manager().Value('i', 0)
        self.pool = Pool(processes=4)

        try:
            PinNameOri = PinName
            if len(PinMap) > 0:
                pinrounp_dict = read_pinmap(PinMap[0])
                if ("," not in PinName) and (PinName in pinrounp_dict.keys()):
                    PinName = ",".join(pinrounp_dict[PinName])
            CmbList = ['DSSC Capture', 'DSSC Source', 'CMEM/HRAM Capture', 'Expand Pattern', 'Compress Pattern',
                       'WFLAG', 'Add Opcode', 'Remove Opcode']
            if TimeMode == 'Single':
                timemode = '1'
            elif TimeMode == 'Dual':
                timemode = '2'
            CycleRanges = []
            if len(CSVFiles) > 1:
                textoutwin("Error: Only ONE CSV file supported !!!")
                print("Error: Only ONE CSV file supported !!!")
                return
            CycleRanges = read_csv(CSVFiles[0])

            self.total_tasks = 0
            for key in CycleRanges.keys():
                tmpFileName = key
                j = in_list(tmpFileName, ATPFiles)
                if j >= 0:
                    textoutwin("Info: Start convert file: " + ATPFiles[j])
                    print("Info: start convert file: +" + ATPFiles[j])
                    if Mode in CmbList:
                        self.total_tasks += 1
                        self.pool.apply_async(edit_pattern, args=(
                            self.queue.put, PinName, ATPFiles[j], CycleRanges[key], Mode, timemode, IndexMode,
                            UserString, PinNameOri), callback=self.my_callback)
                    else:
                        textoutwin("Error: Wrong Choice !!!")
                        print("Error: Wrong Choice !!!")
                else:
                    textoutwin("Warning: Cannot find atp file: " + tmpFileName)
                    print("Warning: Cannot find atp file: " + tmpFileName)
            self.after(500, self.update_progress)
        except Exception:
            error_msg = traceback.format_exc()
            self.put_data_log(error_msg)
            self.switchButtonState(self.btn)

    def my_callback(self, result):
        self.counter.value += 1
        if self.counter.value == self.total_tasks:
            self.put_data_log("All tasks completed!!!")
            self.switchButtonState(self.btn)

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
        global FolderPath
        FolderPath = tk.filedialog.askdirectory()
        contents2.set(FolderPath)

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
    win = DemoClass()
    win.addmenu(MyMenu)
    win.mainloop()
