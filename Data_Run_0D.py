# -*- coding: utf-8 -*-
"""
Multi-scope data acquisition program.
Run this program to acquire data from multiple scopes and save it in an HDF5 file.
Result is plotted in real time.

The user should edit this file to:
    1) Set scope IP addresses
    2) Set number of shots and external delays
    3) Set the HDF5 filename and experiment description
    4) Set descriptions for scopes and channels
    5) Configure any other experiment-specific parameters

Created on Dec.13.2024
@author: Jia Han
"""

import datetime
import os
from multi_scope_acquisition import MultiScopeAcquisition
import time
import sys

############################################################################################################################
'''
User: Set experiment name and path
'''
exp_name = 'exp_11_multi_scope'  # experiment name
date = datetime.date.today()
path = f"E:\\Shadow data\\Energetic_Electron_Ring\\{exp_name}_{date}"
save_path = f"{path}\\{exp_name}.hdf5"

#-------------------------------------------------------------------------------------------------------------
'''
User: Set scope IP addresses and parameters
'''
scope_ips = {
    'magnetron': '192.168.7.63',      # RF source measurements
    'x-ray_dipole': '192.168.7.64',   # X-ray dipole measurements  
    'Bdot': '192.168.7.65'           # Magnetic field measurements
}

external_delays = {
    'magnetron': 15,      
    'x-ray_dipole': 15,  
    'Bdot': 25
} # unit: milliseconds

num_shots = 20  # Number of acquisitions to make
#-------------------------------------------------------------------------------------------------------------
def get_experiment_description(): # USER EDITED
    """Return overall experiment description"""
    return f'''Energetic electron ring experiment.
    
    Experiment: {exp_name}
    Date: {date}
    Operator: Jia Han
    
    Setup:
    - Plasma condition
        - Helium backside pressure 42 Psi
        - Puff with top valve only 105V for 20ms; plasma starts at ~11ms
        - Discharge 20ms; bank 140V; current 4.2kA
        - Pressure 0.025-0.05mTorr
        - Density 5e12⇒1.8e12 from 20⇒25ms (see separate data saved on diagnostic PC)
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
def get_channel_description(tr): # USER EDITED
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

def get_scope_description(scope_name): # USER EDITED
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
    
    print('Data run started at', datetime.datetime.now())
    t_start = time.time()
    
    try:
        # Initialize and run acquisition
        with MultiScopeAcquisition(
            scope_ips=scope_ips,
            num_loops=num_shots,
            save_path=save_path,
            external_delays=external_delays
        ) as acquisition:
            acquisition.run_acquisition()
        
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
# Test Data Run
#===============================================================================================================================================

def run_test():
    """Run a test data acquisition with minimal settings"""
    test_scope_ips = {
        'magnetron': '192.168.7.64',
        'x-ray_dipole': '192.168.7.66'
    }
    
    test_external_delays = {
        'magnetron': 0,    
        'x-ray_dipole': 0      
    }
    
    test_save_path = r"E:\Shadow data\Energetic_Electron_Ring\test.hdf5"
    test_path = os.path.dirname(test_save_path)
    
    # Create test directory if it doesn't exist
    if not os.path.exists(test_path):
        os.makedirs(test_path)
        
    print('\n=== Running Test Acquisition ===')
    print('Using test configuration:')
    print(f'Scopes: {list(test_scope_ips.keys())}')
    print(f'Save path: {test_save_path}')
    print('Number of shots: 1')
    
    try:
        # Run test acquisition
        with MultiScopeAcquisition(
            scope_ips=test_scope_ips,
            num_loops=1,
            save_path=test_save_path,
            external_delays=test_external_delays
        ) as acquisition:
            acquisition.run_acquisition()
        
        if os.path.isfile(test_save_path):
            size = os.stat(test_save_path).st_size/(1024*1024)
            print(f'\nTest successful! Wrote file "{test_save_path}", {size:.1f} MB')
        else:
            print('\nTest failed: File was not created')
            
    except Exception as e:
        print(f'\nTest failed with error: {str(e)}')

#===============================================================================================================================================
#<o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o>
#===============================================================================================================================================

if __name__ == '__main__':
    run_test()
