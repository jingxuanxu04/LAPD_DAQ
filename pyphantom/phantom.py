
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
#           fixed "discover(self, print_list = False)"  print format
#*****************************************************************************/

from .data.PhPy import phGetPh, phDoPh, phSetPh
from .data.PhPy import phGetCam, phDoCam, phSetCam 
from .data.PhPy import phGetCine, phDoCine, phSetCine 
import pyphantom
from pyphantom import utils

from collections import namedtuple
from enum import *
import numpy as np
import pandas as pd

class Phantom:
    def __init__(self):
        # add _ to all default dictionary items
        utils._generate_phantom_keys()  

# ---------- ACCESSORS ---------
#region
    @property
    def enable_log(self):
        return phGetPh(utils._phantom_keys._EnableLog) == 1
    @enable_log.setter
    def enable_log(self, var):
        phSetPh(utils._phantom_keys._EnableLog, int(var))

    @property
    def log_to_ram(self):
        return phGetPh(utils._phantom_keys._LogToRAM) == 1
    @log_to_ram.setter
    def log_to_ram(self, var):
        phSetPh(utils._phantom_keys._LogToRAM, int(var))

    @property
    def camera_count(self):
        return phGetPh(utils._phantom_keys._CameraCount)
#endregion   

# ---------- PRIVATE METHODS ---------
#region
    def __register(self):
        """This is automatically called when the SDK starts and, normally, you should not call it.
        """
        phDoPh(utils._phantom_keys._Register)

    def __unregister(self):
        """Call this when the execution of your application finishes.
        """
        phDoPh(utils._phantom_keys._Unregister)
#endregion

# ---------- PUBLIC METHODS ---------
#region
    def Camera(self, camera_number):
        """Instantiate Camera object

        Parameters
        ----------
        camera_number: int

        Returns
        -------
        Camera object
        """
        return pyphantom.Camera(camera_number)

    def add_simulated_camera(self, cameraVersion=7011, sensor_type=utils.SensorTypeEnum.COLOR):
        """Adds a simulated phantom camera

        Parameters
        ----------
        cameraVersion : sim camera version number
            default 7011, or VEO 640S
        sensor_type : SensorTypeEnum.MONO or COLOR
            default COLOR
        """      
        phDoPh(utils._phantom_keys._AddSimulatedCamera, (cameraVersion, sensor_type.value))
    
    def simulated_camera_dialog(self):
        """Allow adding simulated cameras and make them persistent over the restart of application
        """
        phDoPh(utils._phantom_keys._SimulatedCameraDialog)

    def file_select_dialog(self):
        """Display a dialog box to select a cine file to open. If the dialog is terminated by Cancel the string returned will be void

        Returns
        -------
        filepath : string
        """
        return phGetPh(utils._phantom_keys._FileSelectDialog)

    def discover(self, print_list = False):
        """
        get the list of all Phantom cameras connected to this computer

        Return
        ------
        List of Discovery NamedTuple containing info of available cameras
        """
        camcnt = phGetPh(utils._phantom_keys._CameraCount)

        if camcnt == 0:  # No real camera connected,  add a simulated camera
            phDoPh(utils._phantom_keys._AddSimulatedCamera, (12002, 0))  # hardware version; 12002 = VEO 1310L
            
        camcnt = phGetPh(utils._phantom_keys._CameraCount)

        # Display index, serial and name of available cameras
        if print_list:
            print("List of ", camcnt, " Phantom camera(s) connected to this computer\n")
            print('-' * 58)
            print("cn  Serial   Name             Model               Version")
        cam_list = []
        for cn in range(camcnt):
            sn = phGetCam(utils._phantom_keys._Serial, cn)
            nm = phGetCam(utils._phantom_keys._Name, cn)
            v = phGetCam(utils._phantom_keys._HardwareVersion, cn)
            md = phGetCam(utils._phantom_keys._Model, cn)
            if print_list: print('{:>2d}  {:>5d}    {:<16s} {:<14s}  {:>6d}\n'.format(cn, sn, nm, md, v))
            cam_entry = utils.CameraDiscoverInfo(nm, sn, md, cn)
            cam_list.append(cam_entry)
        return cam_list

    def time64_to_string(self, time64):
        """Utility to convert the image time from the numpy arrays returned by AuxData_np  to a printable string

        Parameters
        ----------
        time64 : uint64 datetime

        Returns
        -------
        datetime : string        
        """
        return phGetPh(utils._phantom_keys._Time64ToString, int(time64))

    def close(self):
        self.__unregister()

#endregion
