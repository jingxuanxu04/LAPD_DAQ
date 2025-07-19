#*****************************************************************************/
#                                                                   
#  Copyright (C) 1992-2023 Vision Research Inc. All Rights Reserved.
#                                                                   
#  The licensed information contained herein is the property of     
#  Vision Research Inc., Wayne, NJ, USA  and is subject to change   
#  without notice.                                                  
#                                                                   
#  No part of this information may be reproduced, modified or       
#  transmitted in any form or by any means, electronic or           
#  mechanical, for any purpose, without the express written         
#  permission of Vision Research Inc.                               
#                                        
#   Version                            
#          August 29, 2023
#
#           Fixed "get_images" method
#           Fixed "get_timestamps" method
#           Removed "get_image_range" method (not working yet under development)
#           Removed "get_timestamp_range" method (not working yet under development)
#           Fixed "is_color" method return incorrect value
#
#*****************************************************************************/

# import from pyphantom.phantom to keep the same namespace going
from wsgiref.headers import tspecials
from numpy import tri
from pyphantom.phantom import phGetPh, phDoPh, phSetPh
from pyphantom.phantom import phGetCam, phDoCam, phSetCam 
from pyphantom.phantom import phGetCine, phDoCine, phSetCine
from pyphantom import utils

from collections import namedtuple
from enum import *
import pandas as pd

class Cine:
    def __init__(self):
        """instantiate cine object
        """
        self._save_percentage = -1 # if -1, no save happening

    @classmethod
    def from_camera(cls, camera, cine_number):
        """instantiate Cine object from camera number, either from RAM or NVM

        Parameters
        ----------
        camera : Camera class
        cine_number : int
            cine number, either from RAM or NVM

        Returns
        -------
        Cine object
        """  
        c = cls()
        c._cine_number = cine_number
        c._camera = camera
        c._cine_handle = phGetCam(utils._phantom_keys._CineHandle, c._camera._camera_num, c._cine_number)
        return c

    @classmethod
    def from_filepath(cls, filepath):
        """instantiate Cine object from filepath

        Parameters
        ----------
        filepath : string

        Returns
        -------
        Cine object
        """  
        c = cls()
        c._cine_filepath = filepath
        c._cine_handle = phGetPh(utils._phantom_keys._CineHandle, filepath)
        c._cine_number = -1
        return c

# ---------- ACCESSORS ---------
#region
    @property
    def cine_number(self):
        return self._cine_number

# ---------- SET/GET Accessors ---------
#region
   
    @property
    def bright(self):
        return phGetCine(utils._phantom_keys._Bright, self._cine_handle)
    @bright.setter
    def bright(self, var):
        phSetCine(utils._phantom_keys._Bright, self._cine_handle, var)
    
    @property
    def contrast(self):
        return phGetCine(utils._phantom_keys._Contrast, self._cine_handle)
    @contrast.setter
    def contrast(self, var):
        phSetCine(utils._phantom_keys._Contrast, self._cine_handle, var)

    @property
    def gamma(self):
        return phGetCine(utils._phantom_keys._Gamma, self._cine_handle)
    @gamma.setter
    def gamma(self, var):
        phSetCine(utils._phantom_keys._Gamma, self._cine_handle, var)

    @property
    def white_balance(self):
        return utils.WhiteBalance(*phGetCine(utils._phantom_keys._WB, self._cine_handle))
    @white_balance.setter
    def white_balance(self, var):
        phSetCine(utils._phantom_keys._WB, self._cine_handle, var)

    @property
    def save_name(self):
        return phGetCine(utils._phantom_keys._SaveName, self._cine_handle)
    @save_name.setter
    def save_name(self, var):
        phSetCine(utils._phantom_keys._SaveName, self._cine_handle, var)

    @property
    def save_range(self):
        return utils.FrameRange(*phGetCine(utils._phantom_keys._SaveRange, self._cine_handle))
    @save_range.setter 
    def save_range(self, var):
        phSetCine(utils._phantom_keys._SaveRange, self._cine_handle, (var.first_image, var.last_image))

    @property
    def save_type(self):
        return utils.FileTypeEnum(phGetCine(utils._phantom_keys._SaveType, self._cine_handle)).name
    @save_type.setter
    def save_type(self, var):
        phSetCine(utils._phantom_keys._SaveType, self._cine_handle, var.value)

    @property
    def description(self):
        return phGetCine(utils._phantom_keys._Description, self._cine_handle)
    @description.setter
    def description(self, var):
        phSetCine(utils._phantom_keys._Description, self._cine_handle, var)
  
    @property
    def int_algo(self):
        return phGetCine(utils._phantom_keys._IntAlgo, self._cine_handle)
    @int_algo.setter
    def int_algo(self, var):
        phSetCine(utils._phantom_keys._IntAlgo, self._cine_handle, var.value)

    @property
    def no_processing(self):
        return phGetCine(utils._phantom_keys._NoProcessing, self._cine_handle)
    @no_processing.setter
    def no_processing(self, var):
        phSetCine(utils._phantom_keys._NoProcessing, self._cine_handle, var.value)

    @property
    def save_packed(self):
        return phGetCine(utils._phantom_keys._SavePacked, self._cine_handle)
    @save_packed.setter
    def save_packed(self, var):
        phSetCine(utils._phantom_keys._SavePacked, self._cine_handle, var.value)

    @property
    def cine_name(self):
        return phGetCine(utils._phantom_keys._CineName, self._cine_handle)
    @cine_name.setter
    def cine_name(self, var):
        phSetCine(utils._phantom_keys._CineName, self._cine_handle, var.value)
  
    @property
    def progress_callback(self):
        return phGetPh(utils._phantom_keys._Callback0)
    @progress_callback.setter
    def progress_callback(self, var):
        phSetPh(utils._phantom_keys._Callback0, var)

#endregion

# ---------- GET Only Accessors ---------
#region

    @property
    def resolution(self):
        return utils.Resolution(*phGetCine(utils._phantom_keys._Resolution, self._cine_handle))
    
    @property
    def post_trigger_frames(self):
        return phGetCine(utils._phantom_keys._PostTriggerFrames, self._cine_handle)

    @property
    def frame_rate(self):
        return phGetCine(utils._phantom_keys._FrameRate, self._cine_handle)

    @property
    def exposure(self):
        return phGetCine(utils._phantom_keys._Exposure, self._cine_handle)

    @property
    def edr_exposure(self):
        return phGetCine(utils._phantom_keys._EDRExposure, self._cine_handle)

    @property
    def image_delay(self):
        return phGetCine(utils._phantom_keys._ImageDelay, self._cine_handle)

    @property
    def sync_mode(self):
        return utils.SyncModeEnum(phGetCine(utils._phantom_keys._SyncMode, self._cine_handle)).name

    @property
    def shutter_off(self):
        return phGetCine(utils._phantom_keys._ShutterOff, self._cine_handle) == 1

    @property
    def auto_exposure(self):
        return phGetCine(utils._phantom_keys._AutoExposure, self._cine_handle) == 1

    @property
    def auto_exposure_level(self):
        return phGetCine(utils._phantom_keys._AutoExposureLevel, self._cine_handle)

    @property
    def bits_per_pixel(self):
        return phGetCine(utils._phantom_keys._BitsPerPixel, self._cine_handle)

    @property
    def is_color(self):
        b = phGetCine(utils._phantom_keys._BitsPerPixel, self._cine_handle)
        if b == 8 or b == 16:
            return utils.SensorTypeEnum.MONO
        elif b == 24 or b == 48:
            return utils.SensorTypeEnum.COLOR

    @property
    def black_white_levels(self):
        return utils.BlackWhiteLevels(*phGetCine(utils._phantom_keys._BlackWhiteLevels, self._cine_handle))

    @property
    def recorded_range(self):
        return utils.FrameRange(*phGetCine(utils._phantom_keys._RecordedRange, self._cine_handle))

    @property
    def range(self):
        return utils.FrameRange(*phGetCine(utils._phantom_keys._Range, self._cine_handle))

    @property
    def uv_sensor(self):
        return phGetCine(utils._phantom_keys._CineUvSensor, self._cine_handle)

    @property
    def sensor_mode(self):
        return phGetCine(utils._phantom_keys._CineSensorMode, self._cine_handle)

    @property
    def hardware_version(self):
        return phGetCine(utils._phantom_keys._CineHardwareVersion, self._cine_handle)

    @property
    def serial(self):
        return phGetCine(utils._phantom_keys._CineSerial, self._cine_handle)

    def get_selector_int(self, selector):
        return phGetCine(utils._phantom_keys._CineGetSelectorInt, self._cine_handle, selector)

    def get_selector_uint(self, selector):
        return phGetCine(utils._phantom_keys._CineGetSelectorUint, self._cine_handle, selector)

    def get_selector_float(self, selector):
        return phGetCine(utils._phantom_keys._CineGetSelectorFloat, self._cine_handle, selector)

    def get_selector_double(self, selector):
        return phGetCine(utils._phantom_keys._CineGetSelectorDouble, self._cine_handle, selector)

    def get_selector_string(self, selector):
        return phGetCine(utils._phantom_keys._CineGetSelectorString, self._cine_handle, selector)

#endregion

# ---------- SET Only Accessors ---------
#region
 
    def set_selector_int(self, var): #SetSelector  = namedtuple('SetSelector', 'selector, value')
        phSetCine(utils._phantom_keys._CineSetSelectorInt, self._cine_handle, var)

    def set_selector_uint(self, var): #SetSelector  = namedtuple('SetSelector', 'selector, value')
        phSetCine(utils._phantom_keys._CineSetSelectorUint, self._cine_handle, var)

    def set_selector_float(self, var): #SetSelector  = namedtuple('SetSelector', 'selector, value')
        phSetCine(utils._phantom_keys._CineSetSelectorFloat, self._cine_handle, var)

    def set_selector_double(self, var): #SetSelector  = namedtuple('SetSelector', 'selector, value')
        phSetCine(utils._phantom_keys._CineSetSelectorDouble, self._cine_handle, var)

#endregion


    @property
    def save_percentage(self):
        return self._save_percentage

#endregion

# ---------- PRIVATE METHODS ---------
#region
    def _get_default_progress_callback(self):
        # wrap up actual callback so you can pass in self
        # https://stackoverflow.com/questions/52288408/python-access-self-in-dll-callback-function-in-class
        def _default_progress_callback(cine_handle, progress):
            # print("{}%".format(progress))
            self._save_percentage = progress
            return 1

        return _default_progress_callback

#endregion

# ---------- PUBLIC METHODS ---------
#region
    def measure_white_balance (self, measure_wb_info: utils.MeasureWhiteBalance):
        """Camera measures white balance from a ROI of a set of live images. Requires gray surronding the ROI.
        
        Parameter
        ---------
        measure_wb_info : NamedTuple MeasureWhiteBalance (x , y, frame_count)
        
        Returns
        -------
        NamedTuple WhiteBalance : the compensating White Balance gains for the red and blue colors
        """
        return utils.WhiteBalance(*phGetCine(
            utils._phantom_keys._MeasureWB, self._cine_handle,
            (measure_wb_info.x, measure_wb_info.y, measure_wb_info.frame_count)))
        
    def get_image_range(self, framerange, disable_debayer=False, decimation=1):
        """Iterable: Get a range of images from cine as a numpy array of pixels
        3d for monochrome, 4d for color.
        Parameters
        ----------
        framerange: NamedTuple FrameRange
            first and last frame number, OR
            1D list of frame numbers (must be within valid range)

        Returns
        --------
        frame number: int
        image: numpy array, 3d for monochrome, 4d for color.
        """
        # TODO implement disable_debayer for intesity only streaming
        # TODO implement decimation (do nothing if <=1)
        playback = framerange
        if type(framerange) == utils.FrameRange:
            playback = range(framerange.first_image, framerange.last_image)

        if self.is_color: 
            align = utils._phantom_keys._gci_Reduce8
        else: 
            align = utils._phantom_keys._gci_LeftAlign

        for p in playback:
             img = phGetCine(utils._phantom_keys._Image_np, self._cine_handle, (p, p, align))
            #yield (p, img[0])
 
        #return

    def get_images(self, framerange: utils.FrameRange, Option=0):
        """Get a range of images from cine as a numpy array of pixels – 3d for monochrome, 4d for color.
        Note: a request for too many frames may result in an exception, depending on system resources.
        Parameters
        ----------
        framerange: NamedTuple FrameRange
            first and last frame number
        Option:
            Bit field
            1 = Reduce8
            2 = Align the 16 bit pixels left for compatibility with tiff format
            4 = ColorRaw (Reduce8 is invalid)
        Returns
        --------
         image: numpy array, 3d for monochrome or ColorRaw, 4d for color RGB.
        """
        if Option == 0:
            if self.is_color: 
                Option = utils._phantom_keys._gci_Reduce8
        else:
            if Option | 4 == 4: 
                # make sure Reduce8 is not set
                Option = Option & (~1)

        return phGetCine(
            utils._phantom_keys._Image_np, self._cine_handle, 
            (framerange.first_image, framerange.last_image, Option))
            
    def get_timestamp_range(self, framerange: utils.FrameRange, readable=True, from_trigger=False):
        """Iterable: Get auxiliary time recorded with images at framerange
        Returns
        -------
        framecount: int
        timestamp: if readable=True, time64 int. if readable=False, datetimestamp string
        """

        #TODO add from trigger functionality

        playback = range(framerange.first_image, framerange.last_image)
        for p in playback:
            ts = phGetCine(utils._phantom_keys._AuxData_np, self._cine_handle,
            (p, p, utils._phantom_keys._gca_Time))

            if readable:
                ts = pd.Timestamp(ts[0] / 2**32, unit='s')
            else:
                ts = ts[0]

            yield (p, ts)

        return

    def get_timestamps(self, framerange: utils.FrameRange, readable=True, from_trigger=False):
        """Get auxiliary time recorded with images at framerange

        Returns
        -------
        timestamps: if readable=True, numpy array of time64. if readable=False, numpy array of datetimestamp string
        """

        ts = phGetCine(utils._phantom_keys._AuxData_np, self._cine_handle,
            (framerange.first_image, framerange.last_image, utils._phantom_keys._gca_Time))
        if readable:
            ts = list(map((lambda x: pd.Timestamp(x / 2**32, unit='s')), ts))
        if from_trigger:
            pass # TODO make actual call here

        return ts

    def get_exposures(self, framerange: utils.FrameRange):
        """Get auxiliary exposure recorded with images at framerange

        Returns
        -------
        numpy array of exposures (us)
        """
        print("get_exposures Functionxx: %d %d" %(framerange.last_image, framerange.first_image))  
        return phGetCine(
            utils._phantom_keys._AuxData_np, self._cine_handle,
            (framerange.first_image, framerange.last_image, utils._phantom_keys._gca_Exposure))

    def get_imagessave (self, framerange: utils.FrameRange):

        playback = framerange
        if type(framerange) == utils.FrameRange:
            playback = range(framerange.first_image, framerange.last_image)

        if self.is_color: align = utils._phantom_keys._gci_Reduce8
        else: align = utils._phantom_keys._gci_LeftAlign
        for p in playback:
            img = phGetCine(utils._phantom_keys._Image_np, self._cine_handle, (p, p, align))
            yield (p, img[0])
        return



    def get_digital_signals(self, framerange: utils.FrameRange):
        """Get auxiliary digital(binary) signals recorded with images at framerange

        Returns
        -------
        numpy array of signals
        """
        d_ch = phGetCam(utils._phantom_keys._SigBinChannels, self._camera._camera_num)
        if d_ch != 0:
            return phGetCine(
                utils._phantom_keys._AuxData_np, self._cine_handle,
                (framerange.first_image, framerange.last_image, utils._phantom_keys._gca_Binsig))
        return None

    def get_analog_signals(self, framerange: utils.FrameRange):
        """Get auxiliary analog signals recorded with images at framerange
        
        Returns
        -------
        numpy array of signals
        """
        a_ch = phGetCam(utils._phantom_keys._SigAnaChannels, self._camera._camera_num)
        if a_ch != 0:
            return phGetCine(
                utils._phantom_keys._AuxData_np, self._cine_handle,
                (framerange.first_image, framerange.last_image, utils._phantom_keys._gca_Anasig))
        return None

    def save(self, filename='', format='', range=''):
        """Save cine from camera to file or convert a cine file to another format.
        Save options like file name, format, range have to be set in cine before this call.
        This call can update filename, format and/or range if defined.
        This call will return when save is complete.

        Parameter
        ---------
        filename : string                   if empty, use current save_name value
        format : utils.FileTypeEnum         if empty, use current save_type value
        range : utils.FrameRange            if empty, use current save_range value

        """        
        if filename != '':
            self.save_name = filename
        if format != '':
            self.save_type = format
        if range != '':
            self.save_range = range
        self.progress_callback = self._get_default_progress_callback()
        # todo BUG this throws exception
        phDoCine(utils._phantom_keys._Save, self._cine_handle)

    def save_non_blocking(self, filename='', format='', range=''):
        """Similar to save() but the control returns to caller immediately and the save operation is done in a separate thread.
        
        Parameter
        ---------
        filename : string                   if empty, use current save_name value
        format : utils.FileTypeEnum         if empty, use current save_type value
        range : utils.FrameRange            if empty, use current save_range value

        """ 
        if filename != '':
            self.save_name = filename
        if format != '':
            self.save_type = format
        if range != '':
            self.save_range = range       
        self.progress_callback = self._get_default_progress_callback()
        phDoCine(utils._phantom_keys._SaveNonBlocking, self._cine_handle)

    def save_nvm(self):
        """Save a cine recorded in the camera RAM memory to camera NonVolatileMemory.
        """
        phDoCine(utils._phantom_keys._SaveNVM, self._cine_handle)

    def save_dialog (self):
        """ Open from Phantom SDK the dialog box for setting the name of the file to save.
        If the dialog is terminated by Cancel function will return 0 and the application may skip the save operation.
        This call will return when save is complete.

        Returns
        --------
        Boolean
            OK was pressed = True, cancel = False
        """
        do_save = phDoCine(utils._phantom_keys._SaveDialog, self._cine_handle)
        if do_save:
            self.save()        
        return do_save == 1
        
    def close(self):
        """Close the cine, free the memory allocated for it in computer memory.
        The recording itself remains available from camera memory or from file.
        """
        phDoCine(utils._phantom_keys._Close, self._cine_handle)

#endregion


