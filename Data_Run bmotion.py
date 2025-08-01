# -*- coding: utf-8 -*-
"""
Multi-scope data acquisition program with probe movement using bapsf_motion library.
Run this program to acquire data from multiple scopes and save it in an HDF5 file.
Result is plotted in real time.

The user should edit this file to:


Created on July 24.2025
@author: Jia Han

TODO: this script is not optimized for speed. Need to:
- Data_Run_2D.py and Acquire_Scope_Data_2D.py includes saving raw data to disk; this needs to be added here.
- Parallelize the data acquisition
"""

import datetime
import os
import numpy as np
from multi_scope_acquisition import run_acquisition_bmotion
import time
import sys
import logging

logging.basicConfig(filename='motor.log', level=logging.WARNING, 
                   format='%(asctime)s %(levelname)s %(message)s')

############################################################################################################################
'''
User set following
'''
exp_name = '00-test'  # experiment name
date = datetime.date.today()
path = r"E:\Shadow data\Energetic_Electron_Ring\test"
save_path = f"{path}\\{exp_name}_{date}.hdf5"

num_duplicate_shots = 5  # number of shots per position
toml_path = r"E:\Shadow data\Energetic_Electron_Ring\example_bmotion_config.toml"

scope_ips = {
    'BdotScope': '192.168.7.66'
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
        # Path to your bmotion TOML configuration file
        toml_path = "example_bmotion_config.toml"  # Update this path as needed
        
        # Number of duplicate shots to acquire at each position
        
        
        # Run the bmotion acquisition
        run_acquisition_bmotion(save_path, toml_path, scope_ips, num_duplicate_shots)
        
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