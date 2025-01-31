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

Created on Feb.14.2024
@author: Jia Han
"""

import datetime
import os
import numpy as np
from multi_scope_acquisition import MultiScopeAcquisition, run_acquisition
from Motor_Control_2D import Motor_Control_2D
import time
import sys
import logging

logging.basicConfig(filename='motor.log', level=logging.WARNING, 
                   format='%(asctime)s %(levelname)s %(message)s')

############################################################################################################################
'''
User: Set experiment name and path
'''
exp_name = 'exp_00_test'  # experiment name
date = datetime.date.today()
path = f"E:\\Shadow data\\Energetic_Electron_Ring\\{exp_name}_{date}"
save_path = f"{path}\\{exp_name}.hdf5"

#-------------------------------------------------------------------------------------------------------------
'''
User: Set probe position array
'''
# Probe position parameters
xmin = -14
xmax = 30
nx = 23

ymin = 0
ymax = 0
ny = 1

num_duplicate_shots = 20      # number of duplicate shots recorded at each location
num_run_repeats = 1          # number of times to repeat sequentially over all locations

#-------------------------------------------------------------------------------------------------------------
def get_experiment_description():
    """Return overall experiment description"""
    return f'''Energetic electron ring experiment with probe movement.
    
    Experiment: {exp_name}
    Date: {date}
    Operator: Jia Han
    
    Probe Movement:
    - X range: {xmin} to {xmax} cm, {nx} points
    - Y range: {ymin} to {ymax} cm, {ny} points
    - {num_duplicate_shots} shots per position
    - {num_run_repeats} full scan repeats
    
    Setup:
    - Plasma condition
        - Helium backside pressure 42 Psi
        - Puff with top valve only 105V for 20ms; plasma starts at ~11ms
        - Discharge 20ms; bank 140V; current 4.2kA
        - Pressure 0.025-0.05mTorr
        - Density 5e12⇒1.8e12 from 20⇒25ms
    - Magnetron condition:
        - Filament current 52A
        - Magnetic field 4.A 25.7V
        - Magnetron duration 40ms
        - Charging voltage and power see scope

    - X-ray camera:

    - Scope descriptions: See scope_group.attrs['description']
    - Channel descriptions: See channel_group.attrs['description']

    Notes:
    All delays are set with respect to plasma 1kA as T=0
    '''

#-------------------------------------------------------------------------------------------------------------
def get_channel_description(tr):
    """Return description for each channel"""
    descriptions = {
        # Magnetron scope channels
        'magnetron_C1': 'Forward power',
        'magnetron_C2': 'Reflected power', 
        'magnetron_C3': 'RF envelope',
        'magnetron_C4': 'RF phase',
        
        # X-ray dipole scope channels
        'x-ray_dipole_C1': 'X-ray signal 1',
        'x-ray_dipole_C2': 'X-ray signal 2',
        'x-ray_dipole_C3': 'X-ray signal 3',
        'x-ray_dipole_C4': 'X-ray signal 4',
        
        # Bdot scope channels
        'Bdot_C1': 'Bdot probe 1',
        'Bdot_C2': 'Bdot probe 2',
        'Bdot_C3': 'Bdot probe 3',
        'Bdot_C4': 'Bdot probe 4'
    }
    return descriptions.get(tr, f'Channel {tr} - No description available')

def get_scope_description(scope_name):
    """Return description for each scope"""
    descriptions = {
        'magnetron': '''RF source measurements scope
        Channels: Forward/reflected power, RF envelope and phase
        Timebase: 500 ns/div
        Vertical scales: See channel settings''',
        
        'x-ray_dipole': '''X-ray dipole measurements scope
        Channels: X-ray signals from dipole detectors
        Timebase: 1 µs/div
        Vertical scales: See channel settings''',
        
        'Bdot': '''Magnetic field measurements scope
        Channels: Bdot probe signals
        Timebase: 100 ns/div
        Vertical scales: 5V/div'''
    }
    return descriptions.get(scope_name, f'Scope {scope_name} - No description available')

#-------------------------------------------------------------------------------------------------------------
'''
User: Set scope and motor IP addresses and parameters
'''
scope_ips = {
    'magnetron': '192.168.7.64',      # RF source measurements
    'x-ray_dipole': '192.168.7.66',   # X-ray dipole measurements  
    'Bdot': '192.168.7.63'           # Magnetic field measurements
}

motor_ips = {
    'x': '192.168.7.161',  # X-axis motor
    'y': '192.168.7.162',   # Y-axis motor
    'z': '192.168.7.163'   # Z-axis motor
}


external_delays = { # unit: milliseconds
    'magnetron': 15,
    'x-ray_dipole': 15,  
    'Bdot': 25
}

#-------------------------------------------------------------------------------------------------------------
def get_positions():
    """Generate the positions array for probe movement.
    Returns:
        tuple: (positions, xpos, ypos)
            - positions: Array of tuples (shot_num, x, y)
            - xpos: Array of x positions
            - ypos: Array of y positions
    """
    if nx == 0 or ny == 0:
        sys.exit('Position array is empty.') 
        
    xpos = np.linspace(xmin, xmax, nx)
    ypos = np.linspace(ymin, ymax, ny)

    # Calculate total number of positions including duplicates and repeats
    total_positions = nx * ny * num_duplicate_shots * num_run_repeats

    # Allocate the positions array
    positions = np.zeros(total_positions, 
                        dtype=[('shot_num', '>u4'), ('x', '>f4'), ('y', '>f4')])


    # Create rectangular shape position array
    index = 0
    for repeat_cnt in range(num_run_repeats):
        for y in ypos:
            for x in xpos:
                for dup_cnt in range(num_duplicate_shots):
                    positions[index] = (index + 1, x, y)
                    index += 1
                    
    return positions, xpos, ypos

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
        run_acquisition(save_path, scope_ips, motor_ips, external_delays)
        
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