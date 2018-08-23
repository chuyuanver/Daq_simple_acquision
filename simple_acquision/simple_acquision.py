from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from matplotlib.backends.qt_compat import QtCore, QtWidgets
from matplotlib.backends.backend_qt5agg import (
        FigureCanvas, NavigationToolbar2QT as NavigationToolbar)
from matplotlib.figure import Figure
import matplotlib

from nidaqmx.task import Task
from nidaqmx import constants

import numpy as np

import sys
import os
import ntpath
import time


BASE_FOLDER = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


'''
################################################################################
Multithreading
'''



class WorkerSignals(QObject):
    data_measured = pyqtSignal(np.ndarray)
    data_fourier = pyqtSignal(np.ndarray)


'''
-------------------------- read data--------------------------------------------
'''

class ReadDataWorker(QRunnable): #Multithreading
    def __init__(self, ai_task, stop_btn):
        super(ReadDataWorker,self).__init__()
        self.ai_task = ai_task
        self.stop_btn = stop_btn
        self.signals = WorkerSignals()
        self.samp_num = 1000000

    @pyqtSlot()
    def run(self):
        sig_data = np.zeros((1,self.samp_num))

        while True:
            self.ai_task.start()
            self.ai_task.wait_until_done()
            sig_data = np.array(self.ai_task.read(number_of_samples_per_channel = self.samp_num))
            self.signals.data_measured.emit(sig_data)
            if self.stop_btn.isChecked():
                break
            # time.sleep(1)
            self.ai_task.stop()


class FourierWorker(QRunnable): #Multithreading
    def __init__(self, time_data_y):
        super(FourierWorker,self).__init__()
        self.time_data_y = time_data_y
        self.signals = WorkerSignals()
    @pyqtSlot()
    def run(self):
        self.freq_data_y = np.fft.rfft(self.time_data_y)/len(self.time_data_y)*2

        self.signals.data_fourier.emit(self.freq_data_y)




'''
################################################################################
main gui window intitation
'''

class MainWindow(QMainWindow):
    def __init__(self, *args, **kwargs):
        super(MainWindow,self).__init__()

        self.setWindowTitle('Pulse Visualizer')
        self.setWindowIcon(QIcon(BASE_FOLDER + r'\pyqt_analysis\icons\window_icon.png'))

        '''
        --------------------------setting menubar-------------------------------
        '''
        mainMenu = self.menuBar() #create a menuBar
        fileMenu = mainMenu.addMenu('&File') #add a submenu to the menu bar


        self.statusBar() #create a status bar

        '''
        --------------------------setting matplotlib----------------------------
        '''
        if app.desktop().screenGeometry().height() == 2160:
            matplotlib.rcParams.update({'font.size': 28})
        elif app.desktop().screenGeometry().height() == 1080:
            matplotlib.rcParams.update({'font.size': 14})


        self.canvas = FigureCanvas(Figure(figsize=(25, 15)))
        self.addToolBar(NavigationToolbar(self.canvas, self))


        self.ax = self.canvas.figure.add_subplot(121)
        self.ax_f = self.canvas.figure.add_subplot(122)
        if app.desktop().screenGeometry().height() == 2160:
            self.ax.tick_params(pad=20)
            self.ax_f.tick_params(pad=20)
        elif app.desktop().screenGeometry().height() == 1080:
            self.ax.tick_params(pad=10)
            self.ax_f.tick_params(pad=10)

        '''
        --------------------------setting widgets-------------------------------
        '''

        exitProgram = QAction(QIcon(BASE_FOLDER + r'\pyqt_analysis\icons\exit_program.png'),'&Exit',self)
        exitProgram.setShortcut("Ctrl+W")
        exitProgram.setStatusTip('Close the Program')
        exitProgram.triggered.connect(self.exit_program)
        fileMenu.addAction(exitProgram)


        startAcq = QPushButton('START',self)
        startAcq.clicked.connect(self.start_acq)

        self.stopAcq = QPushButton('STOP',self)
        self.stopAcq.setCheckable(True)
        '''
        --------------------------setting layout--------------------------------
        '''

        _main = QWidget()
        self.setCentralWidget(_main)
        layout1 = QVBoxLayout(_main)

        layout2 = QHBoxLayout()
        layout2.addWidget(startAcq)
        layout2.addWidget(self.stopAcq)
        layout2.addStretch(1)

        layout1.addWidget(self.canvas)
        layout1.addLayout(layout2)

        '''
        --------------------------Multithreading preparation--------------------
        '''
        self.threadpool = QThreadPool() #Multithreading

        self.sig_task = Task('signal_task')

        samp_rate = 100000

        self.sig_task.ai_channels.add_ai_voltage_chan(physical_channel = r"Dev1/ai1",
                terminal_config = constants.TerminalConfiguration.DIFFERENTIAL)
        self.sig_task.timing.cfg_samp_clk_timing(rate = samp_rate,
                     samps_per_chan = samp_rate*1,
                     sample_mode=constants.AcquisitionType.FINITE)

        self.time_data = np.linspace(0,1,samp_rate)
        f_max = samp_rate/2
        self.freq_data_x = np.linspace(0, f_max, int(len(self.time_data)/2)+1)

    def exit_program(self):
        choice = QMessageBox.question(self, 'Exiting',
                                                'Are you sure about exit?',
                                                QMessageBox.Yes | QMessageBox.No) #Set a QMessageBox when called
        if choice == QMessageBox.Yes:  # give actions when answered the question
            sys.exit()

    def start_acq(self):
        worker = ReadDataWorker(self.sig_task, self.stopAcq)
        worker.signals.data_measured.connect(self.plot_data)
        self.threadpool.start(worker)

    def plot_data(self, data):
        if self.stopAcq.isChecked():
            self.stopAcq.toggle()
        self.ax.clear()
        self.ax.plot(self.time_data, data)


        fourier_worker = FourierWorker(data)
        fourier_worker.signals.data_fourier.connect(self.set_fourier)
        self.threadpool.start(fourier_worker)

    def set_fourier(self, data):
        self.ax_f.clear()
        self.ax_f.plot(self.freq_data_x, np.abs(data))

'''
################################################################################
'''

app = QApplication(sys.argv)

window = MainWindow()
window.move(300,300)
window.show()
app.exec_()
