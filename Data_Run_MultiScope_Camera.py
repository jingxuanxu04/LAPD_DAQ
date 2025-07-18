# -*- coding: utf-8 -*-
"""
Multi-scope and high-speed camera data acquisition program with parallel arming support.
Run this program to acquire data from multiple scopes and Phantom camera, saving everything in a unified HDF5 file.

This combines the functionality of:
- multi_scope_acquisition.py for multiple scope data
- phantom_recorder.py for high-speed camera data

The user should edit this file to:
    1) Set scope IP addresses
    2) Set camera configuration parameters
    3) Set number of shots and external delays
    4) Set the HDF5 filename and experiment description
    5) Set descriptions for scopes and channels
    6) Configure any other experiment-specific parameters

Created on Dec.1.2024
@author: Assistant based on Jia Han's Data_Run.py
"""

import datetime
import os
import numpy as np
from multi_scope_acquisition import MultiScopeAcquisition
from phantom_recorder import PhantomRecorder
import time
import sys
import h5py

############################################################################################################################
'''
User: Set experiment name and path
'''
exp_name = 'multiscope_camera_test'  # experiment name
date = datetime.date.today()
base_path = r"E:\Shadow data\Energetic_Electron_Ring\test"
save_path = os.path.join(base_path, f"{exp_name}_{date}.hdf5")

#-------------------------------------------------------------------------------------------------------------
'''
User: Set acquisition parameters
'''
num_shots = 10  # Total number of shots to acquire

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
    'save_format': 'both'  # 'cine', 'hdf5', or 'both'
}

# Set to None to disable camera recording
# camera_config = None

#-------------------------------------------------------------------------------------------------------------
def get_experiment_description():
    """Return overall experiment description"""
    return f'''
    Multi-scope and High-speed Camera Data Acquisition
    
    Experiment: {exp_name}
    Date: {date}
    Operator: Automated System
    
    Acquisition Parameters:
    - Number of shots: {num_shots}
    - No probe movement (stationary acquisition)
    
    Scope Configuration:
    - Scopes: {list(scope_ips.keys())}
    - External delays: {external_delays}
    
    Camera Configuration:
    - Camera: {'Phantom' if camera_config else 'Disabled'}
    - Resolution: {camera_config.get('resolution', 'N/A') if camera_config else 'N/A'}
    - Frame rate: {camera_config.get('fps', 'N/A') if camera_config else 'N/A'} fps
    - Exposure: {camera_config.get('exposure_us', 'N/A') if camera_config else 'N/A'} μs
    - Frame range: {camera_config.get('pre_trigger_frames', 'N/A') if camera_config else 'N/A'} to +{camera_config.get('post_trigger_frames', 'N/A') if camera_config else 'N/A'}
    
    Setup Details:
    - Add your specific experimental setup details here
    - Plasma conditions, magnetic field settings, etc.
    - Antenna configuration, timing sequences, etc.
    
    Notes:
    - All data synchronized and saved to unified HDF5 file
    - Scope data in respective scope groups (e.g., FastScope/, LPScope/)
    - Camera data in FastCam/ group
    - Configuration data in Control/ group
    '''

#-------------------------------------------------------------------------------------------------------------
def get_channel_description(tr):
    """Channel description for all scopes"""
    descriptions = {
        # FastScope channels
        'testScope_C1': 'RF signal input',
        'testScope_C2': 'RF signal at amplifier output', 
        'testScope_C3': 'Probe signal',
        'testScope_C4': 'Trigger signal',
    }
    return descriptions.get(tr, f'Channel {tr} - No description available')

def get_scope_description(scope_name):
    """Return description for each scope"""
    descriptions = {
        'testScope': 'LeCroy WavePro 404HD 4GHz 20GS/s; RF and probe diagnostics',
    }
    return descriptions.get(scope_name, f'Scope {scope_name} - No description available')


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
    
    # Create HDF5 file first to ensure it exists for camera initialization
    print("Creating HDF5 file...")
    with h5py.File(save_path, 'w') as f:
        # Add basic experiment description and creation time
        f.attrs['description'] = get_experiment_description()
        f.attrs['creation_time'] = time.ctime()
        f.attrs['num_shots'] = num_shots
    
    # Initialize camera recorder if configured
    camera_recorder = None
    if cam_config is not None:
        try:
            print("Initializing Phantom camera...")
            # Set up configuration for HDF5 integration
            cam_config['hdf5_file_path'] = save_path
            cam_config['num_shots'] = 1  # Single shot mode for integration
            
            camera_recorder = PhantomRecorder(cam_config)
            print("✓ Camera initialized successfully")
        except Exception as e:
            print(f"⚠ Camera initialization failed: {e}")
            print("Continuing with scope-only acquisition...")
            camera_recorder = None
    else:
        print("Camera recording disabled")
    
    try:
        # Initialize multi-scope acquisition (no motor control)
        with MultiScopeAcquisition(scope_ips, save_path, nz=None, is_45deg=False) as msa:
            
            # Initialize HDF5 file structure (append mode since file already exists)
            print("Initializing HDF5 file structure...")
            
            with h5py.File(save_path, 'a') as f:
                # Add Python scripts used to create the file
                script_contents = msa.get_script_contents()
                f.attrs['source_code'] = str(script_contents)
                
                # Create scope groups with their descriptions
                for scope_name in scope_ips:
                    if scope_name not in f:
                        f.create_group(scope_name)
                
                # Create Control group
                if '/Control' not in f:
                    ctl_grp = f.create_group('/Control')
                    ctl_grp.attrs['num_shots'] = num_shots

            # First shot: Initialize scopes and save time arrays
            print("\nStarting initial scope acquisition...")
            active_scopes = msa.initialize_scopes()
            if not active_scopes:
                raise RuntimeError("No valid data found from any scope. Aborting acquisition.")
            
            print(f"Active scopes: {list(active_scopes.keys())}")
            
            # Main acquisition loop with parallel arming
            for shot_num in range(1, num_shots + 1):
                try:
                    acquisition_loop_start_time = time.time()
                    
                    print(f'Shot {shot_num}/{num_shots} - ', end='')

                    # Arm scopes for trigger using dedicated parallel arming function
                    msa.arm_scopes_for_trigger(active_scopes)

                    if camera_recorder:
                        camera_recorder.start_recording()
                    
                    # Check for KeyboardInterrupt before scope acquisition
                    time.sleep(0.001)  # Small delay to allow interrupt handling
                    
                    all_data = msa.acquire_shot_after_trigger(active_scopes, shot_num)

                    if camera_recorder:
                        timestamp = camera_recorder.wait_for_recording_completion()
                        print(f"\n=== Recording Complete ===")
                        camera_recorder.save_cine(shot_num - 1, timestamp)
                        print(f"Files saved']")

                    # Store scope data in memory first, then write to HDF5
                    if all_data:
                        msa.update_hdf5(all_data, shot_num, positions=None)
                    else:
                        print(f"Warning: No valid data acquired at shot {shot_num}")

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
        
        # Note: MultiScopeAcquisition cleanup is handled by the context manager (__exit__)

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
    
    print(f'Total shots: {num_shots}')
    print(f'Acquisition type: Stationary (no probe movement)')
    print('=' * 50)
    
    t_start = time.time()
    
    try:
        run_acquisition_with_camera(save_path, scope_ips, external_delays, camera_config)
        
    except KeyboardInterrupt:
        print('\n' + '='*60)
        print('______Acquisition INTERRUPTED by Ctrl-C______', '  at', time.ctime())
        print('Cleaning up resources...')
        print('='*60)
    except Exception as e:
        print('\n' + '='*60)
        print(f'______Acquisition FAILED due to error: {str(e)}______', '  at', time.ctime())
        print('Cleaning up resources...')
        print('='*60)
        import traceback
        traceback.print_exc()
    finally:
        print('Data run finished at', datetime.datetime.now())
        print('Time taken: %.2f minutes' % ((time.time()-t_start)/60))
        
        # Print file size if it was created
        if os.path.isfile(save_path):
            size = os.stat(save_path).st_size/(1024*1024)
            print(f'Wrote file "{save_path}", {size:.1f} MB')
            
            # Show final HDF5 structure
            print('\nFinal HDF5 structure:')
            try:
                with h5py.File(save_path, 'r') as f:
                    def print_structure(name, obj):
                        indent = "  " * name.count('/')
                        if isinstance(obj, h5py.Group):
                            print(f"{indent}{name}/")
                        else:
                            shape_str = f"{obj.shape}" if hasattr(obj, 'shape') else ""
                            print(f"{indent}{name} {shape_str}")
                    
                    f.visititems(print_structure)
            except Exception as e:
                print(f"Could not display HDF5 structure: {e}")
        else:
            print(f'File "{save_path}" was not created')

#===============================================================================================================================================
if __name__ == '__main__':
    main() 