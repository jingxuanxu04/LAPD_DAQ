# -*- coding: utf-8 -*-
"""
Multi-scope data acquisition program with probe movement support.
Run this program to acquire data from multiple scopes and save it in an HDF5 file.
Result is plotted in real time.

The user should edit this file to:
    1) Set scope IP addresses and motor IP addresses
    2) Set probe position array and movement parameters
    3) Set number of shots and external delays
    4) Set the HDF5 filename and experiment description
    5) Set descriptions for scopes and channels
    6) Configure any other experiment-specific parameters
    7) Set probe movement boundaries

Created on Feb.14.2024
@author: Jia Han

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
# Load probe position and acquisition parameters from config.txt
config = load_config('motion/config.txt')

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
# Load boundaries from config.txt
xm_limits = config['xm_limits']
ym_limits = config['ym_limits']
zm_limits = config['zm_limits']
x_limits = config['x_limits']
y_limits = config['y_limits']
z_limits = config['z_limits']
#-------------------------------------------------------------------------------------------------------------

def get_experiment_description():
    """Return overall experiment description"""
    return f'''
    Isat and Langmuir sweep ylines. 6K Compumotor is broken. Using Jia's Python world to rescue. Instead of SIS, data from Oscilloscope is directly recorded.

    LAPD B field:
    ========
    Black magnets at south:(PS12-13: 1100A)	2.0 kG
    Magenta & yellow magnets: 		0.8 kG
    Black magnet at north PS11: (0 A) 	0.0 kG

    South LaB6 source:
    ============
    He plasma, 120 V bank discharge voltage, 3282 A discharge current
    1/3 Hz rep rate 
    Heater: ~36Vrms/2050 A
    Gas puff using Piezo near south anode (~1" size cu tube feeding gas ~ x = 40 cm)
    from both sides (east & west)
    He 40PSI, 67 V from east and west pulses on Piezo valves 
    Max Pressure: 4.5e-5  torr (New Cold magnetron gauge P33 west, N2 calibration) 
    8.5/100 mtorr max mech pumps
    Interferrometer (~288 GHz) @port 20, density at 15 ms ~6e12 cm^-3 assuming 40 cm plasma dia 
    Interferrometer (~288 GHz) @port 29, density at 15 ms ~6e12 cm^-3 assuming 40 cm plasma dia 

    North LaB6 source: Turned off and pulled out
    =================

    Antenna (turned OFF, in position):
    ===========================

    Port 47 top with four rods along x-direction
    rod 4: y=+4.5 cm, rod 3: y=1.5 cm
    rod 2: y=-1.5 cm, rod 1: y=-4.5 cm

    *Direction of Bx field should reverse between neighboring elements due to probe geometry.


    Timing:
    =====
    South Lab6 source: 0-15 ms 
    Breakdown time (discharge voltage pulse to 1 kA dischrge): ~17 ms
    Gas puff: 0 to  ~32 ms (w.r.t.  south discharge voltage pulse)
    Lang Sweep: 200 us pulse-width, 18 cycles every 1 ms starting at 0.7 ms
    Scope trigger: load traces to see. Must be several milliseconds befoe plasma turned on

    Bdot probe C13 (10 turn) on port 41, (drive 2): PULLED OUT 
    Bdot probe C16 (10 turn) on port 36, (drive 3): PULLED OUT
                        
    Moving Lang probe, coated shaft, 4 tip on port 29 (drive 4):
    ==================================================
    Isat-tip: Top-right, 50 Ohm, -120 V bias w.r.t. chamber ground
    Iswp-tip: Top-left, 3 Ohm, Reference chamber ground
    Tip size: ~0.5 mm x ~0.5 mm (???) - rely on interferro. calib.


    Channels:
    ======

    Chan1:  Isat, p39, G: 1
    Chan2:  Isweep, p39
    Chan3 : Vsweep, p39, G: 1/100 

    50 Ohm termination on scope.
    Isat channel has a low pass filter to kill noise.

    Probe Movement:
    - X range: {xmin} to {xmax} cm, {nx} points
    - Y range: {ymin} to {ymax} cm, {ny} points
    - Z range: {zmin} to {zmax} cm, {nz} points (part 1 was -12 to -4)
    - {num_duplicate_shots} shots per position
    - {num_run_repeats} full scan repeats
    '''

#-------------------------------------------------------------------------------------------------------------
# Scope and motor IP addresses
scope_ips = {
    'LPScope': '192.168.7.66' # LeCroy WavePro 404HD 4GHz 20GS/s
}

motor_ips = { # For 3D X:163, Y:165, Z:164
    'x': '192.168.7.166',
    'y': '192.168.7.167',   
}

def get_channel_description(tr):
    """Channel description"""
    descriptions = {
        'LPScope_C1': 'Isat, p39, G: 1',
        'LPScope_C2': 'Isweep, p39',
        'LPScope_C3': 'Vsweep, p39, G: 1/100 ',
        'LPScope_C4': 'N/A'
    }
    return descriptions.get(tr, f'Channel {tr} - No description available')

def get_scope_description(scope_name):
    """Return description for each scope"""
    descriptions = {
        'LPScope': '''LeCroy HDO4104'''
    }
    return descriptions.get(scope_name, f'Scope {scope_name} - No description available')

external_delays = { # unit: milliseconds
    'LPScope': 0
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