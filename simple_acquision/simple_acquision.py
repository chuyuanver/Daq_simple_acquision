'''
import pyqt5 library for gui setup
'''
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

'''
import matplotlib library for embeding graph into the PyQt Gui
'''
from matplotlib.backends.qt_compat import QtCore, QtWidgets
from matplotlib.backends.backend_qt5agg import (
        FigureCanvas, NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
import matplotlib

'''
import the nidaqmx library for configuring the daq card
'''
from nidaqmx.task import Task
from nidaqmx import constants

import numpy as np # import numpy to do some fast calcultion with arrays

import sys # import sys to open and close the gui window
import os # import os for finding the current directory
import ntpath # import ntpath for some configuration with file directory
import time # import time to time a task

# settig the base folder for the icons, subfunctions, etc.
BASE_FOLDER = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


'''
################################################################################
Multithreading setup section
'''

class WorkerSignals(QObject):
    '''
    standard thing for multithreading
    a class contains variable types for multithreading workers to emit data
    '''
    data_measured = pyqtSignal(np.ndarray)
    data_fourier = pyqtSignal(np.ndarray)


'''
-------------------------- read data--------------------------------------------
'''

class ReadDataWorker(QRunnable):
    '''
    a multithreading worker works on getting data from board
    '''
    def __init__(self, ai_task, stop_btn):
        '''
        when a worker is created, this function is run
        '''
        super(ReadDataWorker,self).__init__() # run the initiation of
        #ReadDataWorker's parent, which is QRunnable 
        self.ai_task = ai_task # assign the ai_task so that it is available
        # inside the class
        self.stop_btn = stop_btn
        self.signals = WorkerSignals()
        self.samp_num = 1000000 # set the number to be sampled per acq

    @pyqtSlot()
    def run(self):
        '''
        the function runs when this class is set to multithreading, (@pyqtSlot)
        is needed
        '''
        sig_data = np.zeros((1,self.samp_num)) # preallocate the memory for the
        # data to be read

        while True:
            self.ai_task.start() # start the configured task, check configuration
            self.ai_task.wait_until_done() # wait the task to be finished
            sig_data = np.array(self.ai_task.read(number_of_samples_per_channel = self.samp_num))
            # read the data with specified sample num
            self.signals.data_measured.emit(sig_data) # let the main program
            # know once the data is acquired
            if self.stop_btn.isChecked():
                # if the stop button is clicked, stop the acquisition
                break
            self.ai_task.stop() # stop the acq, ready for next acq


class FourierWorker(QRunnable):
    '''
    a multithreading class for doing the fourier transform
    '''
    def __init__(self, time_data_y):
        '''
        initiation of the class
        1. run FourierWorker's parent (QRunnable)
        2. set the data sent to be reachable inside the class
        3. initate the signal needed to report data back to main program
        '''
        super(FourierWorker,self).__init__()
        self.time_data_y = time_data_y
        self.signals = WorkerSignals()
    @pyqtSlot() # standard decorator for multithreading
    def run(self):
        '''
        when the worker is set to run, this part is run
        1. do the fft of the data
        2. send the forurier transformed data back to main program
        '''
        self.freq_data_y = np.fft.rfft(self.time_data_y)/len(self.time_data_y)*2
        self.signals.data_fourier.emit(self.freq_data_y)

'''
################################################################################
main gui window intitation
'''

class MainWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MainWindow,self).__init__()

        self.setWindowTitle('Pulse Visualizer') # set the title of the window
        # set the icon for the window
        self.setWindowIcon(QIcon(BASE_FOLDER + r'\icons\window_icon.png'))

        '''
        --------------------------setting menubar-------------------------------
        '''
        mainMenu = self.menuBar() #create a menuBar
        fileMenu = mainMenu.addMenu('&File') #add a submenu to the menu bar

        self.statusBar() #create a status bar

        '''
        --------------------------setting matplotlib----------------------------
        '''
        # depending on the resolution of the monitor, change the font size
        # in the matplotlib accordingly
        if app.desktop().screenGeometry().height() == 2160:
            matplotlib.rcParams.update({'font.size': 28})
        elif app.desktop().screenGeometry().height() == 1080:
            matplotlib.rcParams.update({'font.size': 14})

        # set the plotting area and decide the size in (w,h)
        self.canvas = FigureCanvas(Figure(figsize=(25, 15)))
        # include the built-in toolbar of the matplotlib
        self.addToolBar(NavigationToolbar(self.canvas, self))


        # add the first figure for time domain data
        self.ax = self.canvas.figure.add_subplot(121)
        # add the second figure for fourier data
        self.ax_f = self.canvas.figure.add_subplot(122)
        # change the axis tick position depending on the resolution of the
        # monitor
        if app.desktop().screenGeometry().height() == 2160:
            self.ax.tick_params(pad=20)
            self.ax_f.tick_params(pad=20)
        elif app.desktop().screenGeometry().height() == 1080:
            self.ax.tick_params(pad=10)
            self.ax_f.tick_params(pad=10)

        '''
        --------------------------setting widgets-------------------------------
        '''

        # setting the exit action,
        # 1. set it as an QAction, and give it some icon
        # 2. set the keyboard shortcut C+W
        # 3. when the mouse is hover over the icon, show the status tip at the bottom
        # 4. set if this action is triggered, what will happen, in this case,
        # a class method called exit_program is run, it can be found inside the
        # class defination after the initiation function
        # 5. add this action the the file menu
        exitProgram = QAction(QIcon(BASE_FOLDER + r'\icons\exit_program.png'),'&Exit',self)
        exitProgram.setShortcut("Ctrl+W")
        exitProgram.setStatusTip('Close the Program')
        exitProgram.triggered.connect(self.exit_program)
        fileMenu.addAction(exitProgram)


        # set a start button
        # 1. set a button with 'Start' as the text on it
        # 2. set what happens if the button is clicked, in this case, a class
        # method called start_acq is run
        startAcq = QPushButton('START',self)
        startAcq.clicked.connect(self.start_acq)
        self.start_status = False

        # set a stop acquisition button
        # set the stop button to be a check button (if pushed won't bounce
        # back, need to be pushed again to bounce)
        # the stop button's push status is set to be read by other functions so
        # it does not associatate with any class method as the previous two
        self.stopAcq = QPushButton('STOP',self)
        self.stopAcq.setCheckable(True)
        '''
        --------------------------setting layout--------------------------------
        '''

        # set a virtual widget to place it in the center, nothing is shown
        _main = QWidget()
        self.setCentralWidget(_main)
        # add the first layout to be vertical layout and set it as the child of
        # the center widget
        layout1 = QVBoxLayout(_main)

        # add the second layout to be horizontal
        layout2 = QHBoxLayout()
        # set the startacq button, stopacq button to be horizontally placed
        layout2.addWidget(startAcq)
        layout2.addWidget(self.stopAcq)
        # instead of equally space the widgets, push them to the left by adding
        # a large white space to their right
        layout2.addStretch(1)

        # add the canvas to the first layout
        layout1.addWidget(self.canvas)
        # nest the second layout into the first one
        layout1.addLayout(layout2)

        '''
        --------------------------Multithreading preparation--------------------
        '''
        # initiate the multithreading pool
        self.threadpool = QThreadPool() #Multithreading

        '''
        --------------------------configure daq task----------------------------
        '''
        # initiate the task with name 'signal_task' 
        self.sig_task = Task('signal_task')

        samp_rate = 100000

        # add the voltage channel with physical channel name, also set the
        # channel read mode to be differential
        self.sig_task.ai_channels.add_ai_voltage_chan(physical_channel = r"Dev1/ai1",
                terminal_config = constants.TerminalConfiguration.DIFF)
        # set the timing for the signal task, the sampling rate, sample number
        # and sample mode are set here
        self.sig_task.timing.cfg_samp_clk_timing(rate = samp_rate,
                     samps_per_chan = samp_rate*1,
                     sample_mode=constants.AcquisitionType.FINITE)

        # create the time axis
        self.time_data = np.linspace(0,1,samp_rate)
        # create the corresponding frequency axis
        f_max = samp_rate/2
        self.freq_data_x = np.linspace(0, f_max, int(len(self.time_data)/2)+1)

    def exit_program(self):
        '''
        set what happens when the exit action is triggered
        a message box will pop up with exit confirmation
        '''
        choice = QMessageBox.question(self, 'Exiting',
                                                'Are you sure about exit?',
                                                QMessageBox.Yes | QMessageBox.No) #Set a QMessageBox when called
        if choice == QMessageBox.Yes:  # give actions when answered the question
            sys.exit()

    def start_acq(self):
        '''
        set what happens when the startacq button is pressed
        1. initiate the worker with the task and stop button status
        2. set when data is measured what will happen next, in this case, a
        class method plot_data is called
        3. start the worker in a new thread
        '''
        if self.start_status == False:
            worker = ReadDataWorker(self.sig_task, self.stopAcq)
            worker.signals.data_measured.connect(self.plot_data)
            self.threadpool.start(worker)
            self.start_status = True

    def plot_data(self, data):
        '''
        when data is acquired, this function will run
        1. if the stop button is pressed, reset it,
        2. remove what was plot before
        3. plot the time domain data
        4. initialize the fourier worker with time domain data
        5. set what happens when the fourier worker gives the fourier domain
        data (run set_fourier class method)
        6. start the fourier_worker in a new thread
        '''
        if self.stopAcq.isChecked():
            self.stopAcq.toggle()
            self.start_status == False
        self.ax.clear()
        self.ax.plot(self.time_data, data)

        fourier_worker = FourierWorker(data)
        fourier_worker.signals.data_fourier.connect(self.set_fourier)
        self.threadpool.start(fourier_worker)

    def set_fourier(self, data):
        '''
        when the frequency data is calculated out by the fourier worker, this
        function is run
        1. clear the graph
        2. plot the frequency data
        '''
        self.ax_f.clear()
        self.ax_f.plot(self.freq_data_x, np.abs(data))

'''
################################################################################
'''

# initialize the application and the window
app = QApplication(sys.argv)

window = MainWindow()
# move the window from top left coner down 300 by 300 px
window.move(300,300)
# show the window
window.show()
# start the application
app.exec_()
