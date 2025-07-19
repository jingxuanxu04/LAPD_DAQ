
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
#          August 25, 2023
#*****************************************************************************/

# import from pyphantom.phantom to keep the same namespace going
from pyphantom.phantom import phGetPh, phDoPh, phSetPh
from pyphantom.phantom import phGetCam, phDoCam, phSetCam 
from pyphantom.phantom import phGetCine, phDoCine, phSetCine
from pyphantom import utils
from pyphantom import Cine

from collections import namedtuple
from enum import *

class Camera:
    def __init__(self, camera_num):
        """instantiate camera object with camera number

        Parameters
        ----------
        camera_num : int
            camera number index
        """
        self._camera_num = camera_num
        self._live_cine = Cine.from_camera(self, -1)

# ---------- ACCESSORS ---------
#region

# ---------- GET Only Accessors ---------
#region

    def pio_signal_count(self, port=1):
       return phGetCam(utils._phantom_keys._PioSignalCount, self._camera_num, port)

    def pio_has_pulse_proc(self, port=1):
       return phGetCam(utils._phantom_keys._PioHasPulseProc, self._camera_num, port)

    def pio_get_pulse_proc(self, port):
        return phGetCam(utils._phantom_keys._PioGetPulseProc, self._camera_num, port)

    def pio_signal_name(self, var): #PioSignal  = namedtuple('PioSignal', 'port, signal')
        return phGetCam(utils._phantom_keys._PioSignalName, self._camera_num, var)

    def pio_get_signal(self, port=1):
        return phGetCam(utils._phantom_keys._PioGetSignal, self._camera_num, port)

    def get_selector_int(self, selector):
        return phGetCam(utils._phantom_keys._CamGetSelectorInt, self._camera_num, selector)

    def get_selector_uint(self, selector):
        return phGetCam(utils._phantom_keys._CamGetSelectorUint, self._camera_num, selector)

    def get_selector_float(self, selector):
        return phGetCam(utils._phantom_keys._CamGetSelectorFloat, self._camera_num, selector)

    def get_selector_double(self, selector):
        return phGetCam(utils._phantom_keys._CamGetSelectorDouble, self._camera_num, selector)

    def get_selector_string(self, selector):
        return phGetCam(utils._phantom_keys._CamGetSelectorString, self._camera_num, selector)


#endregion

# ---------- SET Only Accessors ---------
#region
    def pio_set_signal(self, var): #PioSignal  = namedtuple('PioSignal', 'port, signal')
        phSetCam(utils._phantom_keys._PioSetSignal, self._camera_num, var)

    def pio_set_pulse_proc(self, var): #PulseProcParam = namedtuple('PulseProcParam', 'port, invert, falling, delay, width, filter')
        phSetCam(utils._phantom_keys._PioSetPulseProc, self._camera_num, var)
 
    def set_selector_int(self, var): #SetSelector  = namedtuple('SetSelector', 'selector, value')
        phSetCam(utils._phantom_keys._CamSetSelectorInt, self._camera_num, var)

    def set_selector_uint(self, var): #SetSelector  = namedtuple('SetSelector', 'selector, value')
        phSetCam(utils._phantom_keys._CamSetSelectorUint, self._camera_num, var)

    def set_selector_float(self, var): #SetSelector  = namedtuple('SetSelector', 'selector, value')
        phSetCam(utils._phantom_keys._CamSetSelectorFloat, self._camera_num, var)

    def set_selector_double(self, var): #SetSelector  = namedtuple('SetSelector', 'selector, value')
        phSetCam(utils._phantom_keys._CamSetSelectorDouble, self._camera_num, var)

#endregion


# ---------- SET/GET Accessors ---------
#region

    @property
    def partition_count(self):
        return phGetCam(utils._phantom_keys._PartitionsCount, self._camera_num)
    @partition_count.setter
    def partition_count(self, var):
        phSetCam(utils._phantom_keys._PartitionsCount, self._camera_num, var)

    @property
    def resolution(self):
        return utils.Resolution(*phGetCam(utils._phantom_keys._Resolution, self._camera_num))
    @resolution.setter
    def resolution(self, var):
        phSetCam(utils._phantom_keys._Resolution, self._camera_num, var)

    @property
    def post_trigger_frames(self):
        return phGetCam(utils._phantom_keys._PostTriggerFrames, self._camera_num)
    @post_trigger_frames.setter
    def post_trigger_frames(self, var):
        phSetCam(utils._phantom_keys._PostTriggerFrames, self._camera_num, var)

    @property
    def frame_rate(self):
        return phGetCam(utils._phantom_keys._FrameRate, self._camera_num)
    @frame_rate.setter
    def frame_rate(self, var):
        phSetCam(utils._phantom_keys._FrameRate, self._camera_num, var)

    @property
    def exposure(self):
        return phGetCam(utils._phantom_keys._Exposure, self._camera_num)
    @exposure.setter
    def exposure(self, var):
        phSetCam(utils._phantom_keys._Exposure, self._camera_num, var)

    @property
    def edr_exposure(self):
        return phGetCam(utils._phantom_keys._EDRExposure, self._camera_num)
    @edr_exposure.setter
    def edr_exposure(self, var):
        phSetCam(utils._phantom_keys._EDRExposure, self._camera_num, var)

    @property
    def image_delay(self):
        return phGetCam(utils._phantom_keys._ImageDelay, self._camera_num)
    @image_delay.setter
    def image_delay(self, var):
        phSetCam(utils._phantom_keys._ImageDelay, self._camera_num, var)

    @property
    def sync_mode(self):
        return utils.SyncModeEnum(phGetCam(utils._phantom_keys._SyncMode, self._camera_num)).name        
    @sync_mode.setter
    def sync_mode(self, var):
        phSetCam(utils._phantom_keys._SyncMode, self._camera_num, var.value)

    @property
    def shutter_off(self):
        return phGetCam(utils._phantom_keys._ShutterOff, self._camera_num) == 1
    @shutter_off.setter
    def shutter_off(self, var):
        phSetCam(utils._phantom_keys._ShutterOff, self._camera_num, var)

    @property
    def auto_exposure(self):
        return phGetCam(utils._phantom_keys._AutoExposure, self._camera_num) #== 1
    @auto_exposure.setter
    def auto_exposure(self, var):
        phSetCam(utils._phantom_keys._AutoExposure, self._camera_num, var)

    @property
    def auto_exposure_level(self):
        return phGetCam(utils._phantom_keys._AutoExposureLevel, self._camera_num)
    @auto_exposure_level.setter
    def auto_exposure_level(self, var):
        phSetCam(utils._phantom_keys._AutoExposureLevel, self._camera_num, var)

    @property
    def name(self):
        return phGetCam(utils._phantom_keys._Name, self._camera_num)
    @name.setter
    def name(self, var):
        phSetCam(utils._phantom_keys._Name, self._camera_num, var)
    
    @property
    def nvm_auto_save(self):
        return phGetCam(utils._phantom_keys._NVMAutoSave, self._camera_num) == 1
    @nvm_auto_save.setter
    def nvm_auto_save(self, var):
        phSetCam(utils._phantom_keys._NVMAutoSave, self._camera_num, var)

    @property
    def auto_csr(self):
        return phGetCam(utils._phantom_keys._AutoCSR, self._camera_num) == 1
    @auto_csr.setter
    def auto_csr(self, var):
        phSetCam(utils._phantom_keys._AutoCSR, self._camera_num, var)

    @property
    def quiet(self):
        return phGetCam(utils._phantom_keys._Quiet, self._camera_num) == 1
    @quiet.setter
    def quiet(self, var):
        phSetCam(utils._phantom_keys._Quiet, self._camera_num, var)

    @property
    def enable_auto_trigger(self):
        return phGetCam(utils._phantom_keys._AutoTrig, self._camera_num) == 1
    @enable_auto_trigger.setter
    def enable_auto_trigger(self, var):
        phSetCam(utils._phantom_keys._AutoTrig, self._camera_num, var)

    @property
    def daq_digital_channel_count(self):
        return phGetCam(utils._phantom_keys._SigBinChannels, self._camera_num)
    @daq_digital_channel_count.setter
    def daq_digital_channel_count(self, var):
        phSetCam(utils._phantom_keys._SigBinChannels, self._camera_num, var)

    @property
    def daq_analog_channel_count(self):
        return phGetCam(utils._phantom_keys._SigAnaChannels, self._camera_num)
    @daq_analog_channel_count.setter
    def daq_analog_channel_count(self, var):
        phSetCam(utils._phantom_keys._SigAnaChannels, self._camera_num, var)

    @property
    def daq_samples_per_image(self):
        return phGetCam(utils._phantom_keys._SigSamplesPerImage, self._camera_num)
    @daq_samples_per_image.setter
    def daq_samples_per_image(self, var):
        phSetCam(utils._phantom_keys._SigSamplesPerImage, self._camera_num, var)

    @property
    def range_data_size(self):
        return phGetCam(utils._phantom_keys._RangeSize, self._camera_num)
    @range_data_size.setter
    def range_data_size(self, var):
        var = max(0, min(16, var))
        phSetCam(utils._phantom_keys._RangeSize, self._camera_num, var)

    @property
    def exp_index(self):
        return phGetCam(utils._phantom_keys._ExpIndex, self._camera_num)
    @exp_index.setter
    def exp_index(self, var):
        phSetCam(utils._phantom_keys._ExpIndex, self._camera_num, var)

    @property
    def lens_focus(self):
        return 0
    @lens_focus.setter
    def lens_focus(self, var):
        return phGetCam(utils._phantom_keys._LensFocus, self._camera_num, var)

    @property
    def lens_aperture(self):
        return phGetCam(utils._phantom_keys._LensAperture, self._camera_num)
    @lens_aperture.setter
    def lens_aperture(self, var):
        phSetCam(utils._phantom_keys._LensAperture, self._camera_num, var)

    @property
    def mechanical_shutter(self):
        return phGetCam(utils._phantom_keys._MechanicalShutter, self._camera_num)
    @mechanical_shutter.setter
    def mechanical_shutter(self, var):
        phSetCam(utils._phantom_keys._MechanicalShutter, self._camera_num, var)

    @property
    def trigger_edge_and_voltage(self):
        return phGetCam(utils._phantom_keys._TriggerEdgeAndVoltage, self._camera_num)
    @trigger_edge_and_voltage.setter
    def trigger_edge_and_voltage(self, var):
        phSetCam(utils._phantom_keys._TriggerEdgeAndVoltage, self._camera_num, var)

    @property
    def sensor_mode(self):
        return phGetCam(utils._phantom_keys._SensorMode, self._camera_num)
    @sensor_mode.setter
    def sensor_mode(self, var):
        phSetCam(utils._phantom_keys._SensorMode, self._camera_num, var)

    @property
    def trigger_filter(self):
        return phGetCam(utils._phantom_keys._TriggerFilter, self._camera_num)
    @trigger_filter.setter
    def trigger_filter(self, var):
        phSetCam(utils._phantom_keys._TriggerFilter, self._camera_num, var)

    @property
    def trigger_delay(self):
        return phGetCam(utils._phantom_keys._TriggerDelay, self._camera_num)
    @trigger_delay.setter
    def trigger_delay(self, var):
        phSetCam(utils._phantom_keys._TriggerDelay, self._camera_num, var)

    @property
    def select_int(self):
        return phGetCam(utils._phantom_keys._CamSelectorInt, self._camera_num)
    @select_int.setter
    def select_int(self, var):
        phSetCam(utils._phantom_keys._CamSelectorInt, self._camera_num, var)

    @property
    def select_double(self):
        return phGetCam(utils._phantom_keys._CamSelectorDouble, self._camera_num)
    @select_double.setter
    def select_double(self, var):
        phSetCam(utils._phantom_keys._CamSelectorDouble, self._camera_num, var)

#endregion

    @property
    def offline(self):
        return phGetCam(utils._phantom_keys._Offline, self._camera_num) == 1

    @property
    def active_partition(self):
        return phGetCam(utils._phantom_keys._ActivePartition, self._camera_num)[0]

    @property
    def active_partition_stored(self):
        return phGetCam(utils._phantom_keys._ActivePartition, self._camera_num)[1] == 1

    @property
    def partition_capacity(self):
        return phGetCam(utils._phantom_keys._PartitionCapacity, self._camera_num)

    @property
    def has_mechanical_shutter(self):
        return phGetCam(utils._phantom_keys._HasMechanicalShutter, self._camera_num) == 1

    @property
    def serial(self):
        return phGetCam(utils._phantom_keys._Serial, self._camera_num)

    @property
    def model(self):
        return phGetCam(utils._phantom_keys._Model, self._camera_num)

    @property
    def hardware_version(self):
        return phGetCam(utils._phantom_keys._HardwareVersion, self._camera_num)
       
    @property
    def nvm_cine_range(self):
        return phGetCam(utils._phantom_keys._NVMCineRange, self._camera_num)

    @property
    def nvm_size(self):
        return phGetCam(utils._phantom_keys._NVMSize, self._camera_num)

    @property
    def nvm_free(self):
        return phGetCam(utils._phantom_keys._NVMFree, self._camera_num)

    @property
    def nvm_available(self):
        return self.nvm_size != 0

    @property
    def resolution_usual(self):
        res_list = phGetCam(utils._phantom_keys._ResolutionUsual, self._camera_num)
        named_res_list = []
        for r in res_list:
            nr = utils.Resolution(x=r[0], y=r[1])
            named_res_list.append(nr)
        return named_res_list
    
    @property
    def resolution_mmi(self):
        return utils.MMI(*phGetCam(utils._phantom_keys._ResolutionMMI, self._camera_num))
    
    @property
    def period_mmi(self):
        return utils.MMI(*phGetCam(utils._phantom_keys._PeriodMMI, self._camera_num))
    
    @property
    def exposure_mmi(self):
        return utils.MMI(*phGetCam(utils._phantom_keys._ExposureMMI, self._camera_num))
    
    @property
    def edr_exposure_mmi(self):
        return utils.MMI(*phGetCam(utils._phantom_keys._EDRExposureMMI, self._camera_num))

    @property
    def frame_rate_mmi(self):
        val = self.period_mmi
        return utils.MMI(1e6/val.min, 1e6/val.max, val.inc)

    @property
    def image_delay_mmi(self):
        return utils.MMI(*phGetCam(utils._phantom_keys._ImageDelayMMI, self._camera_num))

    @property
    def camera_temperature(self):
        return phGetCam(utils._phantom_keys._CameraTemperature, self._camera_num)

    @property
    def sensor_temperature(self):
        return phGetCam(utils._phantom_keys._SensorTemperature, self._camera_num)

    @property
    def supports_uv_sensor(self):
        return phGetCam(utils._phantom_keys._SupportsUvSensor, self._camera_num)

    @property
    def supports_card_flash(self):
        return phGetCam(utils._phantom_keys._SupportsCardFlash, self._camera_num)

    @property
    def supports_magazine(self):
        return phGetCam(utils._phantom_keys._SupportsMagazine, self._camera_num)

    @property
    def supports_edr(self):
        return phGetCam(utils._phantom_keys._SupportsEDR, self._camera_num)

    @property
    def supports_pio(self):
        return phGetCam(utils._phantom_keys._SupportsPio, self._camera_num)

    @property
    def supports_sensor_mode(self):
        return phGetCam(utils._phantom_keys._SupportsSensorMode, self._camera_num)

    @property
    def supports_binning(self):
        return phGetCam(utils._phantom_keys._SupportsBinning, self._camera_num)

    @property
    def supports_battery(self):
        return phGetCam(utils._phantom_keys._SupportBattery, self._camera_num)

    @property
    def has_lock_at_trigger(self):
        return phGetCam(utils._phantom_keys._HasLockAtTrigger, self._camera_num)

    @property
    def has_card_flash(self):
        return phGetCam(utils._phantom_keys._HasCardFlash, self._camera_num)

    @property
    def has_10g(self):
        return phGetCam(utils._phantom_keys._Has_10G, self._camera_num)

    @property
    def max_partition(self):
        return phGetCam(utils._phantom_keys._MaxPartition, self._camera_num)

    @property
    def ip_address(self):
        return phGetCam(utils._phantom_keys._IpAddress, self._camera_num)

    @property
    def lens_aperture_range(self):
        return utils.LensApertureRange(*phGetCam(utils._phantom_keys._LensApertureRange, self._camera_num))

    @property
    def lens_description(self):
        return phGetCam(utils._phantom_keys._LensDescription, self._camera_num)

    @property
    def lens_focus_progress(self):
        return phGetCam(utils._phantom_keys._LensFocusProgress, self._camera_num)

    @property
    def lens_focus_at_limit(self):
        return phGetCam(utils._phantom_keys._LensFocusAtLimit, self._camera_num)

    @property
    def sensor_mode_list(self):
        return phGetCam(utils._phantom_keys._SensorModeList, self._camera_num)

    @property
    def pio_port_count(self):
        return phGetCam(utils._phantom_keys._PioPortCount, self._camera_num)

    @property
    def auto_trig_info(self):
        r = phGetCam(utils._phantom_keys._AutoTrigRect, self._camera_num)
        px = phGetCam(utils._phantom_keys._AutoTrigArea, self._camera_num)
        spd = phGetCam(utils._phantom_keys._AutoTrigSpeed, self._camera_num)
        thr = phGetCam(utils._phantom_keys._AutoTrigThr, self._camera_num)
        at = utils.AutoTrig(*r, px,spd, thr)
        return at
    @auto_trig_info.setter 
    def auto_trig_info(self, var):
        phSetCam(utils._phantom_keys._AutoTrigRect, self._camera_num, var[0:4])
        phSetCam(utils._phantom_keys._AutoTrigArea, self._camera_num, var.active_px_pct)
        phSetCam(utils._phantom_keys._AutoTrigSpeed, self._camera_num, var.trig_speed)
        phSetCam(utils._phantom_keys._AutoTrigThr, self._camera_num, var.trig_threshold)
    
#endregion
# ---------- PRIVATE METHODS ---------
#region
    def __get_single_partition_state(self, partition):
        act = self.active_partition
        if act == partition: 
            if self.active_partition_stored: state = utils.PartitionStateEnum.STORED
            else: state = utils.PartitionStateEnum.RECORDING
        else: 
            if self.partition_recorded(partition): state = utils.PartitionStateEnum.STORED
            else: state = utils.PartitionStateEnum.READY
        
        val = (partition, state)
        return val

#endregion
# ---------- PUBLIC METHODS ---------
#region
    def record(self, cine=1, delete_all = False):
        """Abort current recording and start a new recoding in partition specified.

        Parameters
        ----------
        cine: int
            cine number, default 1
        delete_all: boolean
            delete all recordings before record, default False
        """
        if delete_all:
            self.clear_ram()
            return
        phDoCam(utils._phantom_keys._RecordCine, self._camera_num, cine)
        return

    def trigger(self):
        """Send a software trigger. Camera will record PostTriggerFrames and will continue the recording in the next free partition.
        """
        phDoCam(utils._phantom_keys._Trigger, self._camera_num)

    def delete(self, cine=1, nvm=False):
        """Delete the recording in the specified partition.
        If cine is in the range of the cines from NVM, the NVM will be fully erased. Warn user before such an operation.

        Parameters
        ----------
        cine: int
            cine number, default 1
        nvm: boolean
            if true, cine number is in NVM range. if false, cine number is in RAM range.
        """
        if nvm:
            nvm_offset = self.nvm_cine_range[0] - 1
            cine = nvm_offset + cine        
        phDoCam(utils._phantom_keys._Delete, self._camera_num, cine)

    def clear_ram(self):
        """Delete all cines in camera memory
        """
        phDoCam(utils._phantom_keys._Record, self._camera_num)

    def csr(self):
        """CurrentSessionReference for camera sensor calibration.
        May require manual cover of lens if the camera does not have mechanical shutter.
        """
        no_shtr = self.has_mechanical_shutter == 0
        if no_shtr: input("Cover the lens for CSR and press Enter")
        phDoCam(utils._phantom_keys._CSR, self._camera_num)
        if no_shtr: input("CSR done free the lens for recording and press Enter")


    def signal_setup_dialog(self):
        """Display a dialog to configure the range data and signal acquisition (AuxData)
        """
        phDoCam(utils._phantom_keys._SigSetupDialog, self._camera_num)

    def Cine(self, cine=1):
        """Instantiate Cine object using camera object's camera_number

        Parameters
        ----------
        cine: int
            cine number, default 1

        Returns
        -------
        Cine object
        """
        return Cine.from_camera(self, cine)

    def partition_recorded(self, partition):
        """ Specified partition has a cine recorded.

        Returns
        -------
        Boolean
            True = recorded, False = not recorded
        """
        return phGetCam(utils._phantom_keys._Recorded, self._camera_num, partition) == 1

    def get_live_image(self):
        """get single live image from the camera

        Returns
        -------
        image data : numpy array
        """
        self._live_cine.is_color
        frng = utils.FrameRange(0, 0)
        image = self._live_cine.get_images(frng, Option=2)
        return image[0]

    def get_partition_state(self, partition=-1):
        """Gets the current state of the partition

        Parameters
        ----------
        partition : int
            partition index, default = -1, get all partition state

        Returns
        -------
        Partition State : tuple (cine number, PartitionStateEnum)
            if -1, returns a list of tuples
        """
        # cstats' style output (rec, str, rdy)
        if partition < 0:
            cine_list = []
            for i in range(self.partition_count):
                cl = self.__get_single_partition_state(i+1)
                cine_list.append(cl)
            return cine_list
        else: return self.__get_single_partition_state(partition)

    def close(self):
        self._live_cine.close()

#endregion

