# -*- coding: utf-8 -*-
"""
Multi-scope data acquisition program with probe movement support.
See multi_scope_acquisition.py for more details.

Configuration and metadata:
- Edit experiment_config.txt to set experiment description, scope/channel descriptions, and probe movement/position parameters.
- Use this script to set file paths, scope and motor IP addresses, and other run-specific parameters.

Created on Feb.14.2024
@author: Jia Han

Update July.2025
- Change experiment description to read from experiment_config.txt
- Change probe position and movement to read from experiment_config.txt


TODO: this script is not optimized for speed. Need to:
- Data_Run_2D.py and Acquire_Scope_Data_2D.py includes saving raw data to disk; this needs to be added here.
- Parallelize the data acquisition
"""

import datetime
import os
import numpy as np
from multi_scope_acquisition import run_acquisition
import time
import sys
import logging
from motion.position_manager import load_config

logging.basicConfig(filename='motor.log', level=logging.WARNING, 
                   format='%(asctime)s %(levelname)s %(message)s')

############################################################################################################################
'''
User: Set experiment name and path
'''
exp_name = '18-isatswp-p39-xy-2000G-800G'  # experiment name
date = datetime.date.today()
path = f"C:\\data\\PPPL_AlfvenWave"
save_path = f"{path}\\{exp_name}_{date}.hdf5"

#-------------------------------------------------------------------------------------------------------------
'''
User: Set probe position array (units in cm)
'''
# Load probe position and acquisition parameters from experiment_config.txt
config = load_config()  # Uses default 'experiment_config.txt'

if config is None:
    print("No position configuration found in experiment_config.txt")
    print("This will be a stationary acquisition (no probe movement)")
    # Set default values for stationary mode
    xmin = xmax = nx = 0
    ymin = ymax = ny = 0 
    zmin = zmax = nz = None
    num_duplicate_shots = 1
    num_run_repeats = 1
    xm_limits = ym_limits = zm_limits = (0, 0)
    x_limits = y_limits = z_limits = (0, 0)
else:
    xmin = config['xmin']
    xmax = config['xmax']
    nx = config['nx']
    ymin = config['ymin']
    ymax = config['ymax']
    ny = config['ny']
    zmin = config['zmin']
    zmax = config['zmax']
    nz = config['nz']
    num_duplicate_shots = config['num_duplicate_shots']
    num_run_repeats = config['num_run_repeats']
    
    #-------------------------------------------------------------------------------------------------------------
    '''
    User: Set probe movement boundaries (unit: cm)
    '''
    # Load boundaries from experiment_config.txt
    xm_limits = config['xm_limits']
    ym_limits = config['ym_limits']
    zm_limits = config['zm_limits']
    x_limits = config['x_limits']
    y_limits = config['y_limits']
    z_limits = config['z_limits']
#-------------------------------------------------------------------------------------------------------------

def get_experiment_description():
    """Return overall experiment description - DEPRECATED: Now loaded from experiment_config.txt"""
    print("Warning: get_experiment_description() is deprecated. Update experiment_config.txt instead.")
    return "Experiment description moved to experiment_config.txt"

#-------------------------------------------------------------------------------------------------------------
# Scope and motor IP addresses
scope_ips = {
    'LPScope': '192.168.7.66' # LeCroy WavePro 404HD 4GHz 20GS/s
}

motor_ips = { # For 3D X:163, Y:165, Z:164
    'x': '192.168.7.166',
    'y': '192.168.7.167',   
}

#===============================================================================================================================================
# Main Data Run sequence
#===============================================================================================================================================
def main():
    # Create save directory if it doesn't exist
    if not os.path.exists(path):
        os.makedirs(path)
        
    # Check if file already exists
    if os.path.exists(save_path):
        while True:
            response = input(f'File "{save_path}" already exists. Overwrite? (y/n): ').lower()
            if response in ['y', 'n']:
                break
            print("Please enter 'y' or 'n'")
            
        if response == 'n':
            print('Exiting without overwriting existing file')
            sys.exit()
        else:
            print('Overwriting existing file')
            os.remove(save_path)  # Delete the existing file
    
    print('Data run started at', datetime.datetime.now())
    t_start = time.time()
    
    try:
        run_acquisition(save_path, scope_ips, motor_ips, external_delays, nz)
    
    except KeyboardInterrupt:
        print('\n______Halted due to Ctrl-C______', '  at', time.ctime())
    except Exception as e:
        print(f'\n______Halted due to error: {str(e)}______', '  at', time.ctime())
    finally:
        print('Data run finished at', datetime.datetime.now())
        print('Time taken: %.2f hours' % ((time.time()-t_start)/3600))
        
        # Print file size if it was created
        if os.path.isfile(save_path):
            size = os.stat(save_path).st_size/(1024*1024)
            print(f'Wrote file "{save_path}", {size:.1f} MB')
        else:
            print(f'File "{save_path}" was not created')

#===============================================================================================================================================
#<o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o>
#===============================================================================================================================================

if __name__ == '__main__':
    # Run a test acquisition with minimal settings
    # run_test(test_save_path = r"E:\Shadow data\Energetic_Electron_Ring\test.hdf5")
    main()