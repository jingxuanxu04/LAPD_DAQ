# -*- coding: utf-8 -*-
"""
McPherson Spectrometer DAQ System - GUI Control Interface

This module provides a PyQt5-based graphical user interface for controlling the 
McPherson spectrometer scan controller 789A-4 and coordinating data acquisition 
with LeCroy oscilloscopes.

Features:
- Manual spectrometer wavelength scanning controls
- Automated homing procedures
- Data acquisition setup and execution
- Real-time motor status monitoring

Author: LAPD Team
Created: 2022 (Original version)
Last Modified: June, 2025 (restructured code)
Dependencies: PyQt5, spectrometer_controller, McPherson_Scope_data_handling

For hardware documentation:
- PySerial: https://pyserial.readthedocs.io/
- ASCII commands: https://mcphersoninc.com/pdf/789A-4.pdf
- Manual: https://nstx.pppl.gov/nstxhome/DragNDrop/Operations/Diagnostics_&_Support_Sys/DIMS/789A3%20Manual.pdf
"""

import time
import sys
import os.path
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

from spectrometer_controller import spectrometer
from McPherson_Scope_data_handling import scope_data



class Window(QWidget):

	def __init__(self):
		super(Window, self).__init__()

		# Scan up a range of wavelength
		self.ScanUpLabel = QLabel("Scan Up ")
		self.ScanUpButton = QPushButton("Go", self)
		self.ScanUpInput = QDoubleSpinBox()
		self.ScanUpInput.setRange(0,100000)

		# Scan down a range of wavelength
		self.ScanDownLabel = QLabel("Scan Down ")
		self.ScanDownButton = QPushButton("Go", self)
		self.ScanDownInput = QDoubleSpinBox()
		self.ScanDownInput.setRange(0,100000)
		
		# Go from wavelength to another
		self.ScanFromLabel = QLabel("Scan from ")
		self.ScanToLabel = QLabel(" to ")
		self.ScanToButton = QPushButton("Go", self)
		self.ScanFromInput = QDoubleSpinBox()
		self.ScanToInput = QDoubleSpinBox()
		self.ScanFromInput.setRange(0,100000)
		self.ScanToInput.setRange(0,100000)
		
		


		# Set scan speed
		self.SetSpeedLabel = QLabel("Speed (steps/s) ")
		self.SetSpeedInput = QSpinBox()
		self.SetSpeedButton = QPushButton("Confirm")
		self.SetSpeedInput.setRange(36,60000)
		self.SetSpeedInput.setValue(10000)
		
		# Stop the scan
		self.StopMotorButton = QPushButton("Stop Motor")
		
		# Find home switch
		self.HomeButton = QPushButton("Find Home Switch")
		self.HomeLabel1 = QLabel("(Should be performed each time after connecting to the power)")
		self.HomeLabel2 = QLabel("(1200gr/mm) Home switch at 654.32")
		self.HomeLabel3 = QLabel("(2400gr/mm) Home switch at 654.38")
		self.HomeLabel4 = QLabel()
		self.HomeLabel4.setText('Homing status:..')
		
		# Data Acquisition blocks
		self.DAQLabel = QLabel("(Scan Controller page will be unavailable during data acquisition)")
		self.StartButton = QPushButton("Start Data Run")
		self.StartWavlLabel = QLabel("Starting wavelength:")
		self.NumWavlLabel = QLabel("Number of wavelengths:")
		self.NumShotLabel = QLabel("Number of shots:")
		self.IncrementLabel = QLabel("Increment:")
		self.SpeedLabel = QLabel("Scan speed:")
		self.ScopeIPLabel = QLabel("Scope IP address:")
		
		self.StartWavlInput = QDoubleSpinBox()
		self.NumWavlInput = QSpinBox()
		self.NumShotInput = QSpinBox()
		self.IncrementInput = QDoubleSpinBox()
		self.IncrementInput.setDecimals(3)            # added 25-06-19 to enable 0.025 increment
		self.SpeedInput = QSpinBox()
		self.ScopeIPInput = QLineEdit()
		
		self.SpeedInput.setRange(36,60000)
		self.NumShotInput.setRange(1, 100000)
		self.NumWavlInput.setRange(1, 100000)
		self.IncrementInput.setRange(0, 100000)
		self.StartWavlInput.setRange(0, 100000)
		self.ScopeIPInput.setText('192.168.7.91')
		
		
		# Connect buttons to functions
		self.ScanUpButton.clicked.connect(self.ScanUp)
		self.ScanDownButton.clicked.connect(self.ScanDown)
		self.SetSpeedButton.clicked.connect(self.SetSpeed)
		self.StopMotorButton.clicked.connect(self.StopMotor)
		self.ScanToButton.clicked.connect(self.ScanTo)
		self.HomeButton.clicked.connect(self.FindHome)
		self.StartButton.clicked.connect(self.StartDataRun)
		
		# Created pages
		self.pageCombo = QComboBox()
		self.pageCombo.addItems(["Scan Controller", "Data Acquisition"])
		self.pageCombo.activated.connect(self.SwitchPage)
		self.stackedLayout = QStackedLayout()
		
		# Scan Controller Page
		self.page1 = QWidget()
		self.layout1 = QGridLayout()
		
		self.layout1.addWidget(self.SetSpeedLabel, 0, 0)
		self.layout1.addWidget(self.SetSpeedInput, 0, 1)
		self.layout1.addWidget(self.SetSpeedButton, 0, 4)
		
		self.layout1.addWidget(self.ScanFromLabel, 1, 0)
		self.layout1.addWidget(self.ScanFromInput, 1, 1)
		self.layout1.addWidget(self.ScanToLabel, 1, 2)  
		self.layout1.addWidget(self.ScanToInput, 1, 3)
		self.layout1.addWidget(self.ScanToButton, 1, 4)
		
		
		self.layout1.addWidget(self.ScanUpLabel, 2, 0)
		self.layout1.addWidget(self.ScanUpInput, 2, 1)
		self.layout1.addWidget(self.ScanUpButton, 2, 4)

		self.layout1.addWidget(self.ScanDownLabel, 3, 0)
		self.layout1.addWidget(self.ScanDownInput, 3, 1)
		self.layout1.addWidget(self.ScanDownButton, 3, 4)        
		
		self.layout1.addWidget(self.StopMotorButton, 4, 0, 1, 5)
		
		self.layout1.addWidget(self.HomeButton, 5, 0, 1, 2)
		self.layout1.addWidget(self.HomeLabel2, 6, 0, 1, 2)
		self.layout1.addWidget(self.HomeLabel3, 7, 0, 1, 2)
		self.layout1.addWidget(self.HomeLabel4, 5, 2, 1, 2)
		
		self.page1.setLayout(self.layout1)       
		self.stackedLayout.addWidget(self.page1)
		
		# Data Acquisition Page
		self.page2 = QWidget()
		self.layout2 = QGridLayout()
		
		self.layout2.addWidget(self.DAQLabel, 0, 0, 1, 2)
		self.layout2.addWidget(self.StartWavlLabel, 1, 0)
		self.layout2.addWidget(self.StartWavlInput, 1, 1)
		self.layout2.addWidget(self.NumWavlLabel, 2, 0)
		self.layout2.addWidget(self.NumWavlInput, 2, 1)
		self.layout2.addWidget(self.NumShotLabel, 3, 0)
		self.layout2.addWidget(self.NumShotInput, 3, 1)
		self.layout2.addWidget(self.IncrementLabel, 4, 0)
		self.layout2.addWidget(self.IncrementInput, 4, 1)
		self.layout2.addWidget(self.SpeedLabel, 5, 0)
		self.layout2.addWidget(self.SpeedInput, 5, 1)
		self.layout2.addWidget(self.ScopeIPLabel, 6, 0)
		self.layout2.addWidget(self.ScopeIPInput, 6, 1)
		self.layout2.addWidget(self.StartButton, 7, 0)

		self.page2.setLayout(self.layout2)       
		self.stackedLayout.addWidget(self.page2)
		
		# Top-level layout
		layout = QVBoxLayout()
		self.setLayout(layout)
		layout.addWidget(self.pageCombo)
		layout.addLayout(self.stackedLayout)


		
		
		# Set size and font
		self.ScanUpLabel.setFont(QFont('Times font',20))
		self.ScanUpButton.setFont(QFont('Times font',20))
		self.ScanUpInput.setFont(QFont('Times font',20))
		
		self.ScanDownLabel.setFont(QFont('Times font',20))
		self.ScanDownButton.setFont(QFont('Times font',20))
		self.ScanDownInput.setFont(QFont('Times font',20))
		
		self.ScanFromLabel.setFont(QFont('Times font',20))
		self.ScanToLabel.setFont(QFont('Times font',20))
		self.ScanToButton.setFont(QFont('Times font',20))
		self.ScanFromInput.setFont(QFont('Times font',20))
		self.ScanToInput.setFont(QFont('Times font',20))
		self.ScanFromInput.setFont(QFont('Times font',20))

		self.SetSpeedLabel.setFont(QFont('Times font',20))
		self.SetSpeedInput.setFont(QFont('Times font',20))
		self.SetSpeedButton.setFont(QFont('Times font',20))
		
		self.StopMotorButton.setFont(QFont('Times font',20))
		
		self.HomeButton.setFont(QFont('Times font',20))
		self.HomeLabel1.setFont(QFont('Times font',14))
		self.HomeLabel2.setFont(QFont('Times font',14))
		self.HomeLabel3.setFont(QFont('Times font',14))
		self.HomeLabel4.setFont(QFont('Times font',14))

		self.DAQLabel.setFont(QFont('Times font',14))
		self.StartButton.setFont(QFont('Times font',20))
		self.StartWavlLabel.setFont(QFont('Times font',20))
		self.NumWavlLabel.setFont(QFont('Times font',20))
		self.NumShotLabel.setFont(QFont('Times font',20))
		self.IncrementLabel.setFont(QFont('Times font',20))
		self.SpeedLabel.setFont(QFont('Times font',20))
		self.ScopeIPLabel.setFont(QFont('Times font',20))
		
		self.StartWavlInput.setFont(QFont('Times font',20))
		self.NumWavlInput.setFont(QFont('Times font',20))
		self.NumShotInput.setFont(QFont('Times font',20))
		self.IncrementInput.setFont(QFont('Times font',20))
		self.SpeedInput.setFont(QFont('Times font',20))
		self.ScopeIPInput.setFont(QFont('Times font',20))

		self.pageCombo.setFont(QFont('Times font',20))
		
		self.p = None
		self.ConnectToDevice()
	
	def ConnectToDevice(self):
		
		try:
			self.p = spectrometer(verbose=True)
		except:
			print('Serial connection failed. Trying again in 2s...')
			time.sleep(2)
			return self.ConnectToDevice()
	
	def SwitchPage(self):
		self.stackedLayout.setCurrentIndex(self.pageCombo.currentIndex())

	def ScanUp(self):
		self.SetSpeed()
		wl = self.ScanUpInput.value()/10 # in dial position
		self.p.scan_up(wl)
		

	def ScanDown(self):
		self.SetSpeed()
		wl = self.ScanDownInput.value()/10 # in dial position
		self.p.scan_down(wl)
	
	def directScanTo(self):
		self.SetSpeed()
		wl = (self.ScanToInput.value() - self.ScanFromInput.value())/10
		if wl >= 0:
			self.p.scan_up(wl)
		else:
			self.p.scan_down(-wl)

	def ScanTo(self):
		delta_wl = (self.ScanToInput.value() - self.ScanFromInput.value())

		if delta_wl <= 0:                    # 0 causes mechanical reset to the current position
			self.p.set_speed(40000)
			self.SetSpeedInput.setValue(40000)
			self.p.scan_down((600 - delta_wl)/10)
			self.p.wait_for_motion_complete(0.2)
			delta_wl = 600

		if delta_wl >= 600:
			self.p.set_speed(40000)
			self.SetSpeedInput.setValue(40000)
			self.p.scan_up((delta_wl-50)/10)
			self.p.wait_for_motion_complete(0.2)
			delta_wl = 50

		if delta_wl >= 50:
			self.p.set_speed(10000)
			self.SetSpeedInput.setValue(10000)
			self.p.scan_up((delta_wl-20)/10)
			self.p.wait_for_motion_complete(0.2)
			delta_wl = 20

		if delta_wl >= 20:
			self.p.set_speed(2500)
			self.SetSpeedInput.setValue(2500)
			self.p.scan_up((delta_wl-10)/10)
			self.p.wait_for_motion_complete(0.2)
			delta_wl = 10

		# now delta_wl should be 10 or less
		self.p.set_speed(2500)
		while delta_wl > 2:
			self.p.scan_up(1/10)
			self.p.wait_for_motion_complete(0.1)
			delta_wl -= 1;

		while delta_wl > 0.1:
			self.p.scan_up(1/100)
			self.p.wait_for_motion_complete(0.1)
			delta_wl -= 0.1;

		self.p.scan_up(delta_wl/10)
			



	def SetSpeed(self):
		
		s = self.SetSpeedInput.value()
		self.p.set_speed(s)
		

	def StopMotor(self):
		
		self.p.stop_motor()
	
	def FindHome(self):
		self.HomeLabel3.setText('Start homing process...')
		r = self.p.homing()
		if r == True:
			self.HomeLabel3.setText('Homing process done.')
		else:
			self.HomeLabel3.setText('Homing process failed.')
	
	def StartDataRun(self):
		
		# Freeze scan controller page
		self.page1.setEnabled(False)
		self.pageCombo.setEnabled(False) # in fact unnecessary since the data taking process is not running on thread and will freeze everything anyway
		
		scope_ip   = self.ScopeIPInput.text()
		save_raw   = False
		scope       = scope_data(scope_ip, save_raw)
		start       = self.StartWavlInput.value()/10
		num_wavel  = int(self.NumWavlInput.value()) # total number of wavelength
		num_shots  = int(self.NumShotInput.value()) # number of shots at each wavelength
		increment  = self.IncrementInput.value()/10 # increment of wavelength
		if increment >= 10:
			increment /= 10000  #  cluge in order to enter very small numbers, e.g. .025 --> .0025 nm (type in 250)
		scan_speed = self.SpeedInput.value() # steps/sec, range from 36-60000. The motor might be inaccurate at low speed

		hdf5_file = scope.Acquire_Scope_Data(start, num_wavel, increment, num_shots, scan_speed, self.p)
		
		if os.path.isfile(hdf5_file):
			size = os.stat(hdf5_file).st_size/(1024*1024)
		
			print('wrote file "', hdf5_file, '",  ', time.ctime(), ', %6.1f'%size, ' MB     ', sep='')
		else:
			print('*********** file "', hdf5_file, '" is not found - this seems bad', sep='')
		
		self.page1.setEnabled(True)     # re-enable GUI controls
		self.pageCombo.setEnabled(True) 

	def fileQuit(self):
		if self.p is not None:
			self.p.close()
		self.close()

	def closeEvent(self, ce):
		self.fileQuit()



#=======================================
#=======================================
if __name__ == '__main__':

	app = QApplication(sys.argv)
	window = Window()
	window.show()

	sys.exit(app.exec_())




