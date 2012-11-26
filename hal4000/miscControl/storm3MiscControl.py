#!/usr/bin/python
#
# Miscellaneous controls, such as the EPI/TIRF motor and
# the various lasers for STORM3.
#
# Hazen 06/12
#

import glob
import Image
import numpy
import os
import sys
from PyQt4 import QtCore, QtGui

import miscControl

# Debugging
import halLib.hdebug as hdebug

# UIs.
import qtdesigner.storm3_misc_ui as miscControlsUi

# SMC100 motor (for EPI/TIRF)
import newport.SMC100 as SMC100

# Prior filter wheel
import stagecontrol.storm3StageControl as filterWheel


#
# Misc Control Dialog Box
#
class AMiscControl(miscControl.MiscControl):
    @hdebug.debug
    def __init__(self, parameters, tcp_control, camera_widget, parent = None):
        super(AMiscControl, self).__init__(parameters, tcp_control, camera_widget, parent)

        self.filter_wheel = filterWheel.QPriorFilterWheel()
        self.move_timer = QtCore.QTimer(self)
        self.move_timer.setInterval(50)
        self.smc100 = SMC100.SMC100()

        # UI setup
        self.ui = miscControlsUi.Ui_Dialog()
        self.ui.setupUi(self)
        self.setWindowTitle(parameters.setup_name + " Misc Control")

        # connect signals
        if self.have_parent:
            self.ui.okButton.setText("Close")
            self.ui.okButton.clicked.connect(self.handleOk)
        else:
            self.ui.okButton.setText("Quit")
            self.ui.okButton.clicked.connect(self.handleQuit)

        # setup epi/tir stage control
        self.ui.EPIButton.clicked.connect(self.goToEPI)
        self.ui.leftSmallButton.clicked.connect(self.smallLeft)
        self.ui.rightSmallButton.clicked.connect(self.smallRight)
        self.ui.leftLargeButton.clicked.connect(self.largeLeft)
        self.ui.rightLargeButton.clicked.connect(self.largeRight)
        self.ui.TIRFButton.clicked.connect(self.goToTIRF)
        self.ui.tirGoButton.clicked.connect(self.goToX)
        self.move_timer.timeout.connect(self.updatePosition)

        self.position = self.smc100.getPosition()
        self.setPositionText()

        # setup filter wheel
        self.filters = [self.ui.filter1Button,
                        self.ui.filter2Button,
                        self.ui.filter3Button,
                        self.ui.filter4Button,
                        self.ui.filter5Button,
                        self.ui.filter6Button]
        for filter in self.filters:
            filter.clicked.connect(self.handleFilter)
        self.filters[self.filter_wheel.getPosition()-1].click()

        # Imagine Eyes stuff
        self.ie_accumulate = False
        self.ie_accumulate_count = 0
        self.ie_autosave = False
        self.ie_capture = False
        self.ie_directory = "c:\\tif_directory\\"
        self.ie_index = 1
        self.ie_setting_ROI = 0
        self.ie_start_x = 0
        self.ie_start_y = 0
        self.ie_stop_x = 0
        self.ie_stop_y = 0
        self.ui.iEyesLabel.setText(self.getIEName())

        self.ui.iEyesAutoSaveButton.clicked.connect(self.handleAutoSave)
        self.ui.iEyesClearROIButton.clicked.connect(self.handleClearROI)
        self.ui.iEyesResetButton.clicked.connect(self.handleReset)
        self.ui.iEyesSaveButton.clicked.connect(self.handleSave)
        self.ui.iEyesSetROIButton.clicked.connect(self.handleSetROI)

        if self.camera_widget:
            self.camera_widget.mousePress.connect(self.handleMousePress)

        self.newParameters(self.parameters)

    def getIEName(self):
        return "img.ch00.{0:04d}.tif".format(self.ie_index)

    @hdebug.debug
    def goToEPI(self):
        self.position = self.epi_position
        self.moveStage()

    @hdebug.debug
    def goToTIRF(self):
        self.position = self.tirf_position
        self.moveStage()

    @hdebug.debug
    def goToX(self):
        self.position = self.ui.tirSpinBox.value()
        self.moveStage()

    @hdebug.debug
    def handleAutoSave(self):
        if self.ie_autosave:
            self.ui.iEyesAutoSaveButton.setText("Auto Save")
            self.ui.iEyesAutoSaveButton.setStyleSheet("QPushButton { color: black }")
            self.ie_autosave = False
            self.ie_capture = False
        else:
            self.ui.iEyesAutoSaveButton.setText("Stop Saving")
            self.ui.iEyesAutoSaveButton.setStyleSheet("QPushButton { color: red }")
            self.ie_autosave = True
            self.ie_capture = True
            
    @hdebug.debug
    def handleClearROI(self):
        self.start_x = 0
        self.stop_x = self.parameters.x_pixels
        self.start_y = 0
        self.stop_y = self.parameters.y_pixels
        self.updateROIText()

    @hdebug.debug
    def handleFilter(self):
        for i, filter in enumerate(self.filters):
            if filter.isChecked():
                filter.setStyleSheet("QPushButton { color: red}")
                self.filter_wheel.setPosition(i+1)
                self.parameters.filter_position = i
            else:
                filter.setStyleSheet("QPushButton { color: black}")

    @hdebug.debug
    def handleOk(self):
        self.hide()

    @hdebug.debug
    def handleMousePress(self, mouse_x, mouse_y):
        mouse_x = mouse_x * self.camera_widget.image.width()/512
        mouse_y = mouse_y * self.camera_widget.image.height()/512
        if (self.ie_setting_ROI == 1):
            self.start_x = mouse_x
            self.start_y = mouse_y
            self.ie_setting_ROI = 2
            self.updateROIText()
        elif (self.ie_setting_ROI == 2):
            self.stop_x = mouse_x
            self.stop_y = mouse_y
            if (self.stop_x < self.start_x):
                temp = self.start_x
                self.start_x = self.stop_x
                self.stop_x = temp
            if (self.stop_y < self.start_y):
                temp = self.start_y
                self.start_y = self.stop_y
                self.stop_y = temp
            self.ie_setting_ROI = 0
            self.ui.iEyesSetROIButton.setEnabled(True)
            self.updateROIText()

    @hdebug.debug
    def handleReset(self):
        tif_files = glob.glob(self.ie_directory + "*.tif")
        for file in tif_files:
            os.remove(file)
        self.ie_index = 1
        self.ui.iEyesLabel.setText(self.getIEName())     

    @hdebug.debug
    def handleSave(self):
        self.ie_capture = True

    @hdebug.debug
    def handleSetROI(self):
        self.ui.iEyesSetROIButton.setEnabled(False)
        self.ie_setting_ROI = 1

    @hdebug.debug
    def largeLeft(self):
        if self.position > 14.0:
            self.position -= 10.0 * self.jog_size
            self.moveStage()

    @hdebug.debug
    def largeRight(self):
        if self.position < 23.0:
            self.position += 10.0 * self.jog_size
            self.moveStage()

    def moveStage(self):
        self.move_timer.start()
        self.smc100.stopMove()
        self.smc100.moveTo(self.position)
        self.setPositionText()

    def newFrame(self, frame):
        if self.ie_capture and frame and not self.ie_setting_ROI:

            bg_term = self.ui.iEyesBackgroundSpinBox.value()
            frame_data = numpy.fromstring(frame.data,dtype=numpy.uint16).reshape((self.camera_widget.image.height(),
                                                                                  self.camera_widget.image.width()))
            frame_data[(frame_data<bg_term)] = bg_term
            frame_data = frame_data[self.start_y:self.stop_y,self.start_x:self.stop_x] - bg_term

            if (type(self.ie_accumulate) == type(numpy.array([]))):
                self.ie_accumulate = numpy.concatenate((self.ie_accumulate, frame_data),axis=1)
            else:
                self.ie_accumulate = frame_data

            self.ie_accumulate_count += 1
            if (self.ie_accumulate_count >= self.ui.iEyesAccumulateSpinBox.value()):
                print self.ie_accumulate.dtype
                image = Image.fromstring("I;16",
                                         (self.ie_accumulate.shape[1], self.ie_accumulate.shape[0]), 
                                         self.ie_accumulate.tostring())
                image.save(self.ie_directory + self.getIEName())
                self.ie_index += 1
                self.ui.iEyesLabel.setText(self.getIEName())
                self.ie_accumulate = False
                self.ie_accumulate_count = 0

                if (not self.ie_autosave):
                    self.ie_capture = False

    @hdebug.debug
    def newParameters(self, parameters):
        self.parameters = parameters
        self.jog_size = parameters.jog_size
        self.epi_position = parameters.epi_position
        self.tirf_position = parameters.tirf_position

        names = parameters.filter_names
        if (len(names) == 6):
            for i in range(6):
                self.filters[i].setText(names[i])
        self.filters[self.parameters.filter_position].click()

        self.handleClearROI()

    def setPositionText(self):
        self.ui.positionText.setText("{0:.3f}".format(self.position))

    @hdebug.debug
    def smallLeft(self):
        if self.position > 14.0:
            self.position -= self.jog_size
            self.moveStage()

    @hdebug.debug
    def smallRight(self):
        if self.position < 23.0:
            self.position += self.jog_size
            self.moveStage()

    @hdebug.debug
    def updateROIText(self):
        self.ui.iEyesROILabel.setText("(" + str(self.start_x) + ", " + str(self.start_y) + ") - (" + str(self.stop_x) + ", " + str(self.stop_y) + ")")

    def updatePosition(self):
        if not self.smc100.amMoving():
            self.move_timer.stop()
        self.position = self.smc100.getPosition()
        self.setPositionText()

    @hdebug.debug
    def quit(self):
        self.smc100.shutDown()

#
# The MIT License
#
# Copyright (c) 2012 Zhuang Lab, Harvard University
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#