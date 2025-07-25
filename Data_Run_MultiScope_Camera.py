# -*- coding: utf-8 -*-
"""
Multi-scope and high-speed camera data acquisition program with parallel arming support.
Run this program to acquire data from multiple scopes and Phantom camera, saving everything in a unified HDF5 file.

This combines the functionality of:
- multi_scope_acquisition.py for multiple scope data
- phantom_recorder.py for high-speed camera data

Configuration and metadata:
- Scope and channel descriptions, as well as experiment metadata, are now loaded from experiment_config.txt.
- Edit experiment_config.txt to set experiment description, scope descriptions, and channel descriptions.
- Use this script to set scope IP addresses, camera configuration, number of shots, delays, and file paths.

Created July.2025
@author: AI assistant based on Jia Han's Data_Run.py
"""

import datetime
import os
import numpy as np
from multi_scope_acquisition import MultiScopeAcquisition
from phantom_recorder import PhantomRecorder
import time
import sys
import h5py

# Add paths for imports - works regardless of where the script is run from
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
pi_gpio_dir = os.path.join(current_dir, "pi_gpio")

# Add directories to path if they exist and aren't already in path
for path_to_add in [current_dir, parent_dir, pi_gpio_dir]:
    if os.path.exists(path_to_add) and path_to_add not in sys.path:
        sys.path.insert(0, path_to_add)

from pi_client import TungstenDropper, TriggerClient

MOTOR_IP = '192.168.7.99'
PI_HOST = '192.168.7.38'
PI_PORT = 54321

############################################################################################################################
'''
User: Set experiment name and path
'''
exp_name = 'scope_cam_tungsten_test_3'  # experiment name
date = datetime.date.today()
base_path = r"E:\Shadow data\Energetic_Electron_Ring\test"
save_path = os.path.join(base_path, f"{exp_name}_{date}.hdf5")

#-------------------------------------------------------------------------------------------------------------
'''
User: Set acquisition parameters
'''
num_shots = 5  # Total number of shots to acquire

#-------------------------------------------------------------------------------------------------------------
'''
User: Set scope configuration
'''
scope_ips = {
    'testScope': '192.168.7.65',
}

external_delays = { # unit: milliseconds
    'testScope': 0,
}

#-------------------------------------------------------------------------------------------------------------
'''
User: Set camera configuration
'''
camera_config = {
    'name': exp_name,
    'save_path': base_path,  # Directory path for .cine files
    'exposure_us': 30,
    'fps': 10000,
    'pre_trigger_frames': -500,  # 500 frames before trigger
    'post_trigger_frames': 1000,  # 1000 frames after trigger
    'resolution': (256, 256),
    'hdf5_file_path': None  # Will be set to save_path during initialization
}

# Set to None to disable camera recording
# camera_config = None

#-------------------------------------------------------------------------------------------------------------
def get_experiment_description():
    """Return overall experiment description - DEPRECATED: Now loaded from experiment_config.txt"""
    print("Warning: get_experiment_description() is deprecated. Update experiment_config.txt instead.")
    return "Experiment description moved to experiment_config.txt"

def get_channel_description(tr):
    """Channel description - DEPRECATED: Now loaded from experiment_config.txt"""
    print("Warning: get_channel_description() is deprecated. Update experiment_config.txt instead.")
    return f'Channel {tr} - Update experiment_config.txt [channels] section'

def get_scope_description(scope_name):
    """Return description for each scope - DEPRECATED: Now loaded from experiment_config.txt"""
    print("Warning: get_scope_description() is deprecated. Update experiment_config.txt instead.")
    return f'Scope {scope_name} - Update experiment_config.txt [scopes] section'


#===============================================================================================================================================
# Enhanced acquisition function with camera integration
#===============================================================================================================================================
def run_acquisition_with_camera(save_path, scope_ips, external_delays=None, cam_config=None):
    """Run the main acquisition sequence with integrated camera recording
    
    Args:
        save_path: Path to save HDF5 file
        scope_ips: Dictionary of scope IPs
        external_delays: Dictionary of external delays for scopes
        camera_config: Camera configuration dictionary (None to disable camera)
    """
    print('Starting multi-scope and camera acquisition at', time.ctime())
    
    try:
        # Initialize multi-scope acquisition (no motor control)
        with MultiScopeAcquisition(scope_ips, save_path) as msa:
            
            # Initialize HDF5 file structure (append mode since file already exists)
            print("Initializing HDF5 file structure...", end='')
            msa.initialize_hdf5_base()
            print("✓")

            if cam_config is not None: # Initialize camera recorder if configured
                try:
                    print("Initializing Phantom camera...", end='')
                    # Set up configuration for HDF5 integration
                    cam_config['hdf5_file_path'] = save_path
                    
                    camera_recorder = PhantomRecorder(cam_config)
                    print("✓")
                except Exception as e:
                    print(f"⚠ Camera initialization failed: {e}")
                    print("Continuing with scope-only acquisition...")
                    camera_recorder = None
            else:
                print("Camera recording disabled")
                camera_recorder = None
            
            # Main acquisition loop
            for shot_num in range(1, num_shots + 1): 
                try:
                    acquisition_loop_start_time = time.time()
                    print(f"\n______Acquiring shot {shot_num}/{num_shots}______")

                    if shot_num == 1: # First shot: Initialize scopes and save time arrays
                        print("\nStarting initial scope acquisition...")
                        active_scopes = msa.initialize_scopes()
                        if not active_scopes:
                            raise RuntimeError("No valid data found from any scope. Aborting acquisition.")
                        print(f"Active scopes: {list(active_scopes.keys())}")
                    else:
                        msa.arm_scopes_for_trigger(active_scopes) # Arm scopes for trigger

                    if camera_recorder:
                        camera_recorder.start_recording(shot_num)
                        timestamp = camera_recorder.wait_for_recording_completion()
                    
                    all_data = msa.acquire_shot(active_scopes, shot_num) # Acquire data from scopes

                    if camera_recorder:
                        rec_cine = camera_recorder.save_cine(shot_num, timestamp)

                    # Update scope data in HDF5
                    msa.update_scope_hdf5(all_data, shot_num)
                    print("Save scope data to HDF5")

                    if camera_recorder:
                        camera_recorder.wait_for_save_completion(rec_cine)
                        
                        # Update HDF5 with camera metadata if HDF5 integration is enabled
                        if hasattr(camera_recorder, 'hdf5_path'):
                            filename = f"{camera_recorder.config['name']}_shot{shot_num:03d}.cine"
                            camera_recorder._update_hdf5_metadata(shot_num, filename, timestamp)
                            print("Save camera metadata to HDF5")

                    # Calculate and display remaining time
                    time_per_shot = (time.time() - acquisition_loop_start_time)
                    remaining_shots = num_shots - shot_num
                    remaining_time = remaining_shots * time_per_shot
                    print(f' | Remaining: {remaining_time/60:.1f}min ({remaining_time:.1f}s)')
                    
                except KeyboardInterrupt:
                    print(f'\n______Shot {shot_num} interrupted by Ctrl-C______')
                    raise  # Re-raise to propagate to outer exception handler

    except KeyboardInterrupt:
        print('\n______Halted due to Ctrl-C______', '  at', time.ctime())
        raise

    finally:
        # Cleanup camera
        if camera_recorder:
            try:
                camera_recorder.cleanup()
                print("Camera resources cleaned up successfully")
            except Exception as e:
                print(f"Error cleaning up camera: {e}")


def run_acquisition_with_WDropper(save_path, scope_ips, cam_config=None):
    """
    main acquisition function with tungsten dropper
    """
    print('Starting acquisition at', time.ctime())
    
    dropper = None
    trigger_client = None
    camera_recorder = None
    
    try:
        # Initialize multi-scope acquisition (no motor control)
        with MultiScopeAcquisition(scope_ips, save_path) as msa:
            
            # Initialize HDF5 file structure (append mode since file already exists)
            print("Initializing HDF5 file structure...", end='')
            msa.initialize_hdf5_base()
            print("✓")

            # Initialize tungsten dropper
            print("Initializing tungsten dropper...")
            dropper = TungstenDropper(motor_ip=MOTOR_IP, timeout=15)
            trigger_client = TriggerClient(PI_HOST, PI_PORT)
            trigger_client.get_status()  # Test connection
            print("✓ Trigger client initialized")

            if cam_config is not None: # Initialize camera recorder if configured
                try:
                    print("Initializing Phantom camera...")
                    # Set up configuration for HDF5 integration
                    cam_config['hdf5_file_path'] = save_path
                    camera_recorder = PhantomRecorder(cam_config)

                except Exception as e:
                    print(f"⚠ Camera initialization failed: {e}")
                    print("Continuing with scope-only acquisition...")
                    camera_recorder = None
            else:
                print("Camera recording disabled")
                camera_recorder = None
            
            # Main acquisition loop
            for shot_num in range(1, num_shots + 1): 
                try:
                    acquisition_loop_start_time = time.time()
                    print(f"\n______Acquiring shot {shot_num}/{num_shots}______")

                    if shot_num == 1: # First shot: Initialize scopes and save time arrays
                        print("\nStarting initial scope acquisition...")
                        trigger_client.send_trigger()
                        print("Trigger sent for getting scope time array")
                        active_scopes = msa.initialize_scopes()
                        if not active_scopes:
                            raise RuntimeError("No valid data found from any scope. Aborting acquisition.")
                        print(f"Active scopes: {list(active_scopes.keys())}")
                    else:
                        msa.arm_scopes_for_trigger(active_scopes) # Arm scopes for trigger

                    # Load tungsten ball and send trigger
                    print("Loading tungsten ball...")
                    dropper.load_ball()
                    print("Sending trigger signal...")
                    trigger_client.send_trigger()

                    if camera_recorder:
                        camera_recorder.start_recording(shot_num)
                        timestamp = camera_recorder.wait_for_recording_completion()
                    
                    all_data = msa.acquire_shot(active_scopes, shot_num) # Acquire data from scopes

                    if camera_recorder:
                        rec_cine = camera_recorder.save_cine(shot_num, timestamp)

                    # Update scope data in HDF5
                    msa.update_scope_hdf5(all_data, shot_num)
                    print("Save scope data to HDF5")

                    if camera_recorder:
                        camera_recorder.wait_for_save_completion(rec_cine)
                        
                        # Update HDF5 with camera metadata if HDF5 integration is enabled
                        if hasattr(camera_recorder, 'hdf5_path'):
                            filename = f"{camera_recorder.config['name']}_shot{shot_num:03d}.cine"
                            camera_recorder._update_hdf5_metadata(shot_num, filename, timestamp)
                            print("Save camera metadata to HDF5")

                    # Calculate and display remaining time
                    time_per_shot = (time.time() - acquisition_loop_start_time)
                    remaining_shots = num_shots - shot_num
                    remaining_time = remaining_shots * time_per_shot
                    print(f' | Remaining: {remaining_time/60:.1f}min ({remaining_time:.1f}s)')
                    
                except KeyboardInterrupt:
                    print(f'\n______Shot {shot_num} interrupted by Ctrl-C______')
                    raise  # Re-raise to propagate to outer exception handler

    except KeyboardInterrupt:
        print('\n______Halted due to Ctrl-C______', '  at', time.ctime())
        raise

    finally:
        # Cleanup all resources
        print("\n=== Cleaning up resources ===")
        
        # Cleanup camera
        if camera_recorder:
            try:
                camera_recorder.cleanup()
                print("✓ Camera resources cleaned up successfully")
            except Exception as e:
                print(f"⚠ Error cleaning up camera: {e}")
        

        
        print("=== Resource cleanup completed ===")
#===============================================================================================================================================
# Main Data Run sequence
#===============================================================================================================================================
def main():
    # Create save directory if it doesn't exist
    if not os.path.exists(base_path):
        os.makedirs(base_path)
        
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
    
    print('=== Multi-Scope and Camera Data Acquisition ===')
    print(f'Experiment: {exp_name}')
    print(f'Base path: {base_path}')
    print(f'HDF5 file: {save_path}')
    print(f'Scopes: {list(scope_ips.keys())}')
    print(f'Camera: {"Enabled" if camera_config else "Disabled"}')
    if camera_config:
        print(f'  Resolution: {camera_config["resolution"]}')
        print(f'  Frame rate: {camera_config["fps"]} fps')
        print(f'  Frames: {camera_config["pre_trigger_frames"]} to +{camera_config["post_trigger_frames"]}')
        print(f'  HDF5 metadata: Yes')  # Always saved when camera is enabled
    
    print(f'Total shots: {num_shots}')
    print(f'Acquisition type: Stationary (no probe movement)')
    print('=' * 50)
    
    t_start = time.time()
    
    try:
        run_acquisition_with_WDropper(save_path, scope_ips, camera_config)
        
    except KeyboardInterrupt:
        print('\n' + '='*60)
        print('______Acquisition INTERRUPTED by Ctrl-C______', '  at', time.ctime())
        print('='*60)
    except Exception as e:
        print('\n' + '='*60)
        print(f'______Acquisition FAILED due to error: {str(e)}______', '  at', time.ctime())
        print('='*60)
        import traceback
        traceback.print_exc()
    finally:
        print('\n' + '='*50)
        print('Data run finished at', datetime.datetime.now())
        print('Time taken: %.2f minutes' % ((time.time()-t_start)/60))
        
        # Print file size if it was created
        if os.path.isfile(save_path):
            size = os.stat(save_path).st_size/(1024*1024)
            print(f'Wrote file "{save_path}", {size:.1f} MB')
        else:
            print(f'File "{save_path}" was not created')
        print('='*50)

#===============================================================================================================================================
if __name__ == '__main__':
    main() 