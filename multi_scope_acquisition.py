'''
Multi-scope data acquisition called by Data_Run.py

This module handles scope configuration, data acquisition, and HDF5 file management.
Motion control and probe positioning functionality has been moved to the motion package.

Key components:
- MultiScopeAcquisition class: Manages multiple oscilloscopes, data acquisition and storage
- Scope configuration and metadata loaded from experiment_config.txt
- HDF5 file structure optimized for large datasets with compression
- Parallel scope arming support for synchronized acquisition

Dependencies:
- LeCroy_Scope: Interface to LeCroy oscilloscopes
- h5py: HDF5 file handling
- numpy: Numerical operations
- configparser: Configuration file parsing
- motion package: All probe movement and positioning functionality

Created on Feb.14.2024
@author: Jia Han

Updated July.2025
- Separated motion control into dedicated motion package
- Separate scope arming into a separate function
- Change experiment description to read from experiment_config.txt
'''

import numpy as np
import matplotlib.pyplot as plt
from LeCroy_Scope import LeCroy_Scope, WAVEDESC_SIZE
import h5py
import time
import os
import configparser

# Import motion control components from the motion package
import sys
motion_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "motion")
if motion_dir not in sys.path:
    sys.path.insert(0, motion_dir)

from motion import PositionManager, initialize_motor, initialize_motor_45deg, move_45deg_probes
from motion.position_manager import load_position_config

#===============================================================================================================================================
def load_experiment_config(config_path='experiment_config.txt'):
    """Load experiment configuration from config file."""
    config = configparser.ConfigParser()
    config.read(config_path)
    
    # Set defaults if sections don't exist
    if 'experiment' not in config:
        config.add_section('experiment')
    if 'scopes' not in config:
        config.add_section('scopes')
    if 'channels' not in config:
        config.add_section('channels')
    
    # Set default values if not present
    if not config.get('experiment', 'description', fallback=None):
        config.set('experiment', 'description', 'No experiment description provided')
    
    return config



def stop_triggering(scope, retry=500):
    retry_count = 0
    while retry_count < retry:
        try:
            current_mode = scope.set_trigger_mode("")
            if current_mode[0:4] == 'STOP':
                return True
            time.sleep(0.05)
        except KeyboardInterrupt:
            print('Keyboard interrupted in stop_triggering')
            raise  # Re-raise to propagate the interrupt
        retry_count += 1

    print('Scope did not enter STOP state')
    return False

def init_acquire_from_scope(scope, scope_name):
    """Initialize acquisition from a single scope and get initial data and time arrays
    Args:
        scope: LeCroy_Scope instance
        scope_name: Name of the scope
    Returns:
        tuple: (is_sequence, time_array)
            - is_sequence: 0 for RealTime mode, 1 for sequence mode
            - time_array: Time array for the scope
    """
    time_array = None
    is_sequence = None

    traces = scope.displayed_traces()
    
    for tr in traces:
        try:
            if stop_triggering(scope) == True:
                trace_bytes, header_bytes = scope.acquire_bytes(tr)
                hdr = scope.translate_header_bytes(header_bytes)
            else:
                raise Exception('Scope did not enter STOP state')

            if hdr.subarray_count < 2: # Get number of segments
                is_sequence = 0 # in RealTime mode
            else:
                is_sequence = 1 # in sequence mode

            # Get time array from first valid trace
            if time_array is None:
                time_array = scope.time_array(tr)
                
            # Successfully got data from at least one trace, break out of loop
            break
                
        except Exception as e:
            print(f"Error initializing {tr} from {scope_name}: {e}")
            continue
    
    # Check if we got valid data
    if is_sequence is None or time_array is None:
        print(f"Warning: Could not get valid data from any trace on {scope_name}")
        return None, None
    
    return is_sequence, time_array

def acquire_from_scope(scope, scope_name):
    """Acquire data from a single scope with optimized speed
    Args:
        scope: LeCroy_Scope instance
        scope_name: Name of the scope
    Returns:
        tuple: (traces, data, headers)
            - traces: List of trace names that have valid data
            - data: Dict of trace data
            - headers: Dict of trace headers
    """
    data = {}
    headers = {}
    active_traces = []
    TIMEOUT = 10  # Timeout in seconds for acquisition

    traces = scope.displayed_traces()
    
    for tr in traces:
        if stop_triggering(scope) == True:
            data[tr], headers[tr] = scope.acquire(tr)
            active_traces.append(tr)
        else:
            raise Exception('Scope did not enter STOP state')
    
    return active_traces, data, headers

def acquire_from_scope_sequence(scope, scope_name):
    """Acquire sequence mode data from a single scope
    Args:
        scope: LeCroy_Scope instance
        scope_name: Name of the scope
    Returns:
        tuple: (traces, data, headers)
            - traces: List of trace names that have valid data
            - data: Dict of trace data arrays for each segment
            - headers: Dict of trace headers with sequence info
    """
    data = {}
    headers = {}
    active_traces = []

    traces = scope.displayed_traces()
    
    for tr in traces:

        if stop_triggering(scope) == True:
            data[tr], headers[tr] = scope.acquire_sequence_data(tr)
            active_traces.append(tr)
        else:
            raise Exception('Scope did not enter STOP state')
    
    return active_traces, data, headers

class MultiScopeAcquisition:
    """Handles scope connections, data acquisition, and scope data storage"""
    
    def __init__(self, scope_ips, save_path):
        """
        Args:
            scope_ips: dict of scope names and IP addresses
            save_path: path to save HDF5 file
        """
        self.scope_ips = scope_ips
        self.save_path = save_path
        
        self.scopes = {}
        self.figures = {}
        self.time_arrays = {}  # Store time arrays for each scope
        # self.plot_data = {}    # Store plot data for each scope/trace/shot

    def cleanup(self):
        """Clean up resources"""
        print("Cleaning up scope resources...")
        
        # Close all scope connections
        for name, scope in self.scopes.items():
            try:
                print(f"Closing scope {name}...")
                scope.__exit__(None, None, None)
            except Exception as e:
                print(f"Error closing scope {name}: {e}")
        self.scopes.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def get_scope_description(self, scope_name):
        """Get scope description from experiment config"""
        try:
            config = load_experiment_config()
            return config.get('scopes', scope_name, fallback=f'Scope {scope_name} - No description available')
        except Exception as e:
            print(f"Warning: Could not load scope description from config: {e}")
            return f'Scope {scope_name} - No description available'
    
    def get_channel_description(self, channel_name):
        """Get channel description from experiment config"""
        try:
            config = load_experiment_config()
            return config.get('channels', channel_name, fallback=f'Channel {channel_name} - No description available')
        except Exception as e:
            print(f"Warning: Could not load channel description from config: {e}")
            return f'Channel {channel_name} - No description available'
    
    def get_experiment_description(self):
        """Get experiment description from experiment config"""
        try:
            config = load_experiment_config()
            description = config.get('experiment', 'description', fallback='No experiment description provided')
            
            # Add position config information if available
            pos_config, _ = load_position_config()
            if pos_config:
                description += f"""

Position Configuration (from experiment_config.txt [position] section):
- X range: {pos_config.get('xmin', 'N/A')} to {pos_config.get('xmax', 'N/A')} cm, {pos_config.get('nx', 'N/A')} points
- Y range: {pos_config.get('ymin', 'N/A')} to {pos_config.get('ymax', 'N/A')} cm, {pos_config.get('ny', 'N/A')} points
- Z range: {pos_config.get('zmin', 'N/A')} to {pos_config.get('zmax', 'N/A')} cm, {pos_config.get('nz', 'N/A')} points
- {pos_config.get('num_duplicate_shots', 'N/A')} shots per position
- {pos_config.get('num_run_repeats', 'N/A')} full scan repeats
- Probe boundaries: x={pos_config.get('x_limits', 'N/A')}, y={pos_config.get('y_limits', 'N/A')}, z={pos_config.get('z_limits', 'N/A')}
- Motor boundaries: x={pos_config.get('xm_limits', 'N/A')}, y={pos_config.get('ym_limits', 'N/A')}, z={pos_config.get('zm_limits', 'N/A')}"""
            
            return description
        except Exception as e:
            print(f"Warning: Could not load experiment description from config: {e}")
            return 'No experiment description provided'

    def get_script_contents(self):
        """Read the contents of the Python scripts used to create the HDF5 file"""
        script_contents = {}
        
        # Get the directory of the current script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # List of scripts to include
        scripts = ['Data_Run.py', 'multi_scope_acquisition.py', 'LeCroy_Scope.py']
        
        for script in scripts:
            script_path = os.path.join(current_dir, script)
            try:
                with open(script_path, 'r') as f:
                    script_contents[script] = f.read()
            except Exception as e:
                print(f"Warning: Could not read {script}: {str(e)}")
                script_contents[script] = f"Error reading file: {str(e)}"
        
        return script_contents
    
    def initialize_hdf5_base(self):
        """Initialize HDF5 file structure for scopes and experiment metadata"""
        with h5py.File(self.save_path, 'a') as f:
            # Add experiment description and creation time
            f.attrs['description'] = self.get_experiment_description()
            f.attrs['creation_time'] = time.ctime()
            
            # Add Python scripts used to create the file
            script_contents = self.get_script_contents()
            f.attrs['source_code'] = str(script_contents)
            
            # Create scope groups with their descriptions
            for scope_name in self.scope_ips:
                if scope_name not in f:
                    f.create_group(scope_name)

    def initialize_scopes(self):
        """Initialize scopes and get time arrays on first acquisition"""
        active_scopes = {}
        for name, ip in self.scope_ips.items():
            print(f"\nInitializing {name}...", end='')
            
            try:
                # Create scope instance
                self.scopes[name] = LeCroy_Scope(ip, verbose=False)
                scope = self.scopes[name]
                
                # Optimize scope settings for faster acquisition
                scope.scope.chunk_size = 4*1024*1024  # Increase chunk size to 4MB for faster transfer
                scope.scope.timeout = 30000  # 30 second timeout
                
                scope.set_trigger_mode('SINGLE') # Set trigger mode
                
                # Get initial data and time arrays
                is_sequence, time_array = init_acquire_from_scope(scope, name)

                if is_sequence is not None and time_array is not None:  # Only save if we got valid data
                    self.save_time_arrays(name, time_array, is_sequence)
                    
                    # Save scope metadata immediately after successful initialization
                    self._save_scope_metadata(name)
                    
                    active_scopes[name] = is_sequence
                    print(f"Successfully initialized {name}")
                else:
                    print(f"Warning: Could not initialize {name} - no valid data returned")
                    self.cleanup_scope(name)
                    
            except Exception as e:
                print(f"Error initializing {name}: {str(e)}")
                self.cleanup_scope(name)
                continue
        return active_scopes

    def _save_scope_metadata(self, scope_name):
        """Save scope metadata to HDF5 immediately after initialization"""
        with h5py.File(self.save_path, 'a') as f:
            scope_group = f[scope_name]
            scope_group.attrs['description'] = self.get_scope_description(scope_name)
            scope_group.attrs['ip_address'] = self.scope_ips[scope_name]
            scope_group.attrs['scope_type'] = self.scopes[scope_name].idn_string

    def cleanup_scope(self, name):
        """Clean up resources for a specific scope"""
        if name in self.scopes:
            try:
                self.scopes[name].__exit__(None, None, None)
                del self.scopes[name]
            except Exception as e:
                print(f"Error closing scope {name}: {e}")

    def acquire_shot(self, active_scopes, shot_num):
        """Acquire data from all active scopes for one shot"""
        all_data = {}
        failed_scopes = []
        
        for name in active_scopes:
            try:
                print(f"Acquiring data from {name}...", end='')
                scope = self.scopes[name]
                
                if active_scopes[name] == 0:
                    traces, data, headers = acquire_from_scope(scope, name)
                elif active_scopes[name] == 1:
                    traces, data, headers = acquire_from_scope_sequence(scope, name)
                else:
                    raise ValueError(f"Invalid active_scopes value for {name}: {active_scopes[name]}")

                if traces:
                    all_data[name] = (traces, data, headers)
                else:
                    print(f"Warning: No valid data from {name} for shot {shot_num}")
                    failed_scopes.append(name)
                    
            except KeyboardInterrupt:
                print(f"\nScope acquisition interrupted for {name}")
                raise  # Re-raise to propagate the interrupt
            except Exception as e:
                print(f"Error acquiring from {name}: {e}")
                failed_scopes.append(name)
        print("✓")
        return all_data
    
    def arm_scopes_for_trigger(self, active_scopes):
        """Arm all scopes for trigger without waiting for completion (for parallel operation)"""
        print("Arming scopes for trigger... ", end='')
        for name in active_scopes:
            scope = self.scopes[name]
            scope.set_trigger_mode('SINGLE')
        print("armed")
    
    def save_time_arrays(self, scope_name, time_array, is_sequence):
        """Save time array for a scope to HDF5 file
        
        Args:
            scope_name: Name of the scope
            time_array: Time array to save
            is_sequence: Whether this is sequence mode data
        """
        with h5py.File(self.save_path, 'a') as f:
            scope_group = f[scope_name]
            # Store the time array for this scope
            self.time_arrays[scope_name] = time_array
            
            # Check if time_array already exists
            if 'time_array' in scope_group:
                raise RuntimeError(f"Time array already exists for scope {scope_name}. This should not happen.")
            
            # Save to HDF5
            time_ds = scope_group.create_dataset('time_array', data=time_array, dtype='float64')
            time_ds.attrs['units'] = 'seconds'
            if is_sequence == 1:
                time_ds.attrs['description'] = 'Time array for all channels; data saved in sequence mode'
            else:
                time_ds.attrs['description'] = 'Time array for all channels'
            time_ds.attrs['dtype'] = str(time_array.dtype)

    def update_scope_hdf5(self, all_data, shot_num):
        """Update HDF5 file with scope data only"""
        with h5py.File(self.save_path, 'a') as f:
            # Save data for each scope
            for scope_name, (traces, data, headers) in all_data.items():
                scope_group = f[scope_name]
                
                # Check if shot group already exists
                shot_name = f'shot_{shot_num}'
                if shot_name in scope_group:
                    raise RuntimeError(f"Shot {shot_num} already exists for scope {scope_name}.")
                
                # Create shot group with optimized settings
                shot_group = scope_group.create_group(shot_name)
                shot_group.attrs['acquisition_time'] = time.ctime()
                
                # Save trace data and headers with optimized chunk size and compression
                for tr in traces:
                    if tr not in data:
                        continue
                        
                    # Convert data to appropriate dtype
                    trace_data = np.asarray(data[tr])
                    if trace_data.dtype != np.float64:
                        trace_data = trace_data.astype(np.float64)
                    
                    # Check if this is sequence data (will be 2D array)
                    is_sequence = len(trace_data.shape) > 1
                    
                    # Calculate optimal chunk size
                    if is_sequence:
                        chunk_size = (1, min(trace_data.shape[1], 512*1024))
                    else:
                        chunk_size = (min(len(trace_data), 512*1024),)
                    
                    # Create dataset
                    data_ds = shot_group.create_dataset(f'{tr}_data', 
                                                      data=trace_data,
                                                      chunks=chunk_size,
                                                      compression='gzip',
                                                      compression_opts=9,
                                                      shuffle=True,
                                                      fletcher32=True)
                    
                    # Store header
                    header_ds = shot_group.create_dataset(f'{tr}_header', data=np.void(headers[tr]))
                    
                    # Add metadata
                    data_ds.attrs['description'] = self.get_channel_description(tr)
                    data_ds.attrs['dtype'] = str(trace_data.dtype)
                    header_ds.attrs['description'] = f'Binary header data for {tr}'
    


#===============================================================================================================================================
def single_shot_acquisition(pos, needs_movement, nz, msa, pos_manager, mc, save_path, scope_ips, active_scopes):

    shot_num = pos['shot_num']  # shot_num is 1-based
    # Move to next position if motor control is active
    if needs_movement:
        if nz is None:
            print(f'Shot = {shot_num}, x = {pos["x"]}, y = {pos["y"]}', end='')
        else:
            print(f'Shot = {shot_num}, x = {pos["x"]}, y = {pos["y"]}, z = {pos["z"]}', end='')
            
        try:
            mc.enable
            if nz is None:
                mc.probe_positions = (pos['x'], pos['y'])
            else:
                mc.probe_positions = (pos['x'], pos['y'], pos['z'])
            mc.disable
        except KeyboardInterrupt:
            raise KeyboardInterrupt
        except ValueError as e:
            print(f'\nSkipping position - {str(e)}')
            # Create empty shot group with explanation
            with h5py.File(save_path, 'a') as f:
                for scope_name in scope_ips:
                    scope_group = f[scope_name]
                    shot_group = scope_group.create_group(f'shot_{shot_num}')
                    shot_group.attrs['skipped'] = True
                    shot_group.attrs['skip_reason'] = str(e)
                    shot_group.attrs['acquisition_time'] = time.ctime()
            return
        except Exception as e:
            print(f'\nMotor failed to move with {str(e)}')
            # Create empty shot group with explanation
            with h5py.File(save_path, 'a') as f:
                for scope_name in scope_ips:
                    scope_group = f[scope_name]
                    shot_group = scope_group.create_group(f'shot_{shot_num}')
                    shot_group.attrs['skipped'] = True
                    shot_group.attrs['skip_reason'] = f"Motor movement failed: {str(e)}"
                    shot_group.attrs['acquisition_time'] = time.ctime()
            return
    else:
        print(f'Shot = {shot_num}', end='')
    
    # Arm scopes for trigger as soon as probe is in position
    msa.arm_scopes_for_trigger(active_scopes)

    # Acquire data from all scopes at this position
    all_data = msa.acquire_shot(active_scopes, shot_num)
    
    if all_data:
        # Update scope data in HDF5
        msa.update_scope_hdf5(all_data, shot_num)
        
        # Update position data in HDF5
        if not needs_movement:
            xpos, ypos, zpos = None, None, None
        elif nz is None:
            xpos, ypos = mc.probe_positions
            zpos = None
        else:
            xpos, ypos, zpos = mc.probe_positions
        
        positions = {'x': xpos, 'y': ypos, 'z': zpos}
        pos_manager.update_position_hdf5(shot_num, positions)
    else:
        print(f"Warning: No valid data acquired at shot {shot_num}")

def single_shot_acquisition_45(pos, motors, msa, pos_manager, save_path, scope_ips, active_scopes):
    """Acquire a single shot for 45-degree probe setup
    Args:
        pos: Dictionary containing positions for each probe, where each position is a numpy record with 'shot_num' and 'x' fields
        motors: Dictionary of motor controllers for each probe
        msa: MultiScopeAcquisition instance
        pos_manager: PositionManager instance
        save_path: Path to save HDF5 file
        scope_ips: Dictionary of scope IPs
        active_scopes: Dictionary of active scopes
    """
    # Extract the shot number from the first probe's position data
    # Access by index since it's a numpy record array (0 is shot_num, 1 is x)
    shot_num = int(pos['P16'][0])
    positions = {}
    
    print(f'Shot = {shot_num}', end='')
    
    # Collect active motors and their target positions
    active_motors = []
    target_positions = []
    probe_order = []  # Keep track of probe order for mapping returned positions
    
    for probe, motor in motors.items():
        if motor is not None:
            # Access by index since it's a numpy record array (0 is shotnum, 1 is x)
            x_position = float(pos[probe][1])  # Get the x field
            print(f', {probe}: {x_position}', end='')
            active_motors.append(motor)
            target_positions.append(x_position)
            probe_order.append(probe)
            positions[probe] = None  # Initialize all positions to None
        else:
            positions[probe] = None
    
    # Move all active probes simultaneously if we have any
    if active_motors:
        try:
            achieved_positions = move_45deg_probes(active_motors, target_positions)
            
            # Update positions dictionary with achieved positions
            for i, probe in enumerate(probe_order):
                positions[probe] = achieved_positions[i]
                
        except Exception as e:
            print(f'\nError moving probes: {str(e)}')
            # Create empty shot groups with explanation for failed probes
            with h5py.File(save_path, 'a') as f:
                for probe in probe_order:
                    probe_group = f[f'/Control/Positions/{probe}']
                    shot_group = probe_group.create_group(f'shot_{shot_num}')
                    shot_group.attrs['skipped'] = True
                    shot_group.attrs['skip_reason'] = str(e)
                    shot_group.attrs['acquisition_time'] = time.ctime()
            return
    
    # Arm scopes for trigger as soon as probes are in position
    msa.arm_scopes_for_trigger(active_scopes)

    # Acquire data from all scopes at this position
    all_data = msa.acquire_shot(active_scopes, shot_num)
    
    if all_data:
        # Update scope data in HDF5
        msa.update_scope_hdf5(all_data, shot_num)
        
        # Update position data in HDF5
        pos_manager.update_position_hdf5(shot_num, positions)
    else:
        print(f"Warning: No valid data acquired at shot {shot_num}")

#===============================================================================================================================================
# Main Acquisition Loop  
#===============================================================================================================================================
def run_acquisition(save_path, scope_ips, motor_ips=None,  nz=None, is_45deg=None):
    """Run the main acquisition sequence
    Args:
        save_path: Path to save HDF5 file
        scope_ips: Dictionary of scope IPs
        motor_ips: Dictionary of motor IPs (can be None for stationary acquisition)
        external_delays: Dictionary of external delays for scopes (unused in current implementation)
        nz: Number of z positions (None for 2D, int for 3D)
        is_45deg: Whether this is a 45-degree probe acquisition (auto-determined from config if None)
    """
    print('Starting acquisition loop at', time.ctime())
    
    # Initialize position manager (will auto-determine is_45deg from config if not specified)
    pos_manager = PositionManager(save_path, nz, is_45deg)
    
    # Get the actual is_45deg value after auto-detection
    is_45deg = pos_manager.is_45deg
    
    # Initialize multi-scope acquisition
    with MultiScopeAcquisition(scope_ips, save_path) as msa:
        try:
            # Initialize HDF5 file structure
            print("Initializing HDF5 file...", end='')
            msa.initialize_hdf5_base()  # Initialize scope structure
            positions = pos_manager.initialize_position_hdf5()  # Initialize position structure  
            print("✓")
            
            # Initialize motors based on acquisition type
            if is_45deg:
                motors = initialize_motor_45deg(positions, motor_ips)
                needs_movement = any(motor is not None for motor in motors.values())
            else:
                motors, needs_movement = initialize_motor(positions, motor_ips, nz)

            # First shot: Initialize scopes and save time arrays
            print("\nStarting initial acquisition...")
            active_scopes = msa.initialize_scopes()
            if not active_scopes:
                raise RuntimeError("No valid data found from any scope. Aborting acquisition.")
            
            # Main acquisition loop
            if is_45deg:
                # For 45-degree probes, we need to extract corresponding positions for each shot
                shots_count = len(positions['P16'])  # Use P16 as reference for number of shots
                for i in range(shots_count):
                    shot_pos = {}
                    for probe in positions:
                        shot_pos[probe] = positions[probe][i]  # Get ith position for each probe
                    
                    acquisition_loop_start_time = time.time()
                    
                    single_shot_acquisition_45(shot_pos, motors, msa, pos_manager, save_path, scope_ips, active_scopes)
                    
                    # Calculate and display remaining time
                    time_per_pos = (time.time() - acquisition_loop_start_time)
                    remaining_positions = shots_count - (i+1)
                    remaining_time = remaining_positions * time_per_pos
                    print(f'Remaining time: {remaining_time/3600:.2f}h')
            else:
                # Original loop for XY/XYZ acquisition
                for pos in positions:
                    acquisition_loop_start_time = time.time()

                    single_shot_acquisition(pos, needs_movement, nz, msa, pos_manager, motors, save_path, scope_ips, active_scopes)

                    # Calculate and display remaining time
                    time_per_pos = (time.time() - acquisition_loop_start_time)
                    remaining_positions = len(positions) - pos['shot_num']
                    remaining_time = remaining_positions * time_per_pos
                    print(f'Remaining time: {remaining_time/3600:.2f}h')

        except KeyboardInterrupt:
            print('\n______Halted due to Ctrl-C______', '  at', time.ctime())
            raise

        finally:
            # Cleanup resources
            plt.close('all')  # Ensure all figures are closed

#===============================================================================================================================================
 
def run_acquisition_bmotion(save_path, scope_ips):
    """Run the main acquisition sequence with probe movement set by bmotion library
    Args:
        save_path: Path to save HDF5 file
        scope_ips: Dictionary of scope IPs

        TODO: Implement bmotion integration with DAQ
    """
    print('Starting acquisition loop at', time.ctime())
    

