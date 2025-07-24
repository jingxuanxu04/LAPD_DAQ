"""
Position management module for LAPD DAQ system.

Contains the PositionManager class for handling position arrays,
HDF5 position data storage, and position-related metadata.
"""

import numpy as np
import h5py
import os
import sys
from .Motor_Control import Motor_Control_2D, Motor_Control_3D, MC

# --- Config loader ---
def load_config(config_path):
    """Load configuration variables from a config.txt file."""
    import ast
    config = {}
    with open(config_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            try:
                # Try to parse as Python literal (int, float, list, tuple)
                value = ast.literal_eval(value)
            except Exception:
                pass
            config[key] = value
    return config

class PositionManager:
    """Handles position arrays, HDF5 position data, and position-related metadata"""
    
    def __init__(self, save_path, nz=None, is_45deg=False, config_path='motion/config.txt'):
        """
        Args:
            save_path: Path to HDF5 file
            nz: Number of z positions (None for 2D, int for 3D)
            is_45deg: Whether this is a 45-degree probe acquisition
            config_path: Path to config.txt file
        """
        self.save_path = save_path
        self.nz = nz
        self.is_45deg = is_45deg
        self.config = load_config(config_path)
        
    def get_positions(self):
        """Get position arrays based on acquisition type"""
        if self.is_45deg:
            from Data_Run_45deg import create_all_positions, xstart, xstop, nx, nshot
            return create_all_positions(['P16', 'P22', 'P29', 'P34', 'P42'], xstart, xstop, nx, nshot)
        else:
            if self.nz is None:
                return get_positions_xy(self.config)
            else:
                return get_positions_xyz(self.config)
    
    def initialize_position_hdf5(self):
        """Initialize HDF5 position structure and return positions"""
        if self.is_45deg:
            positions, xpos = self.get_positions()
            dtype = {'P16': [('shot_num', '>u4'), ('x', '>f4')],
                    'P22': [('shot_num', '>u4'), ('x', '>f4')],
                    'P29': [('shot_num', '>u4'), ('x', '>f4')],
                    'P34': [('shot_num', '>u4'), ('x', '>f4')],
                    'P42': [('shot_num', '>u4'), ('x', '>f4')]}
        else:
            if self.nz is None:
                positions, xpos, ypos = self.get_positions()
                dtype = [('shot_num', '>u4'), ('x', '>f4'), ('y', '>f4')]
            else:
                positions, xpos, ypos, zpos = self.get_positions()
                dtype = [('shot_num', '>u4'), ('x', '>f4'), ('y', '>f4'), ('z', '>f4')]

        with h5py.File(self.save_path, 'a') as f:
            # Create Control/Positions group and datasets
            if '/Control' not in f:
                ctl_grp = f.create_group('/Control')
            else:
                ctl_grp = f['/Control']
                
            if 'Positions' not in ctl_grp:
                pos_grp = ctl_grp.create_group('Positions')
                
                if self.is_45deg:
                    # Create separate position arrays for each probe
                    for probe in positions:
                        probe_grp = pos_grp.create_group(probe)
                        # Create setup array with metadata
                        setup_ds = probe_grp.create_dataset('positions_setup_array', 
                                                          data=positions[probe], 
                                                          dtype=dtype[probe])
                        setup_ds.attrs['xpos'] = xpos[probe]
                        
                        # Create array for actual positions
                        probe_grp.create_dataset('positions_array', 
                                               shape=(len(positions[probe]),), 
                                               dtype=dtype[probe])
                else:
                    # Create positions setup array with metadata
                    pos_ds = pos_grp.create_dataset('positions_setup_array', data=positions, dtype=dtype)
                    pos_ds.attrs['xpos'] = xpos
                    if not self.is_45deg:
                        pos_ds.attrs['ypos'] = ypos
                        if self.nz is not None:
                            pos_ds.attrs['zpos'] = zpos
                    
                    # Create positions array for actual positions
                    pos_grp.create_dataset('positions_array', shape=(len(positions),), dtype=dtype)

        return positions
    
    def update_position_hdf5(self, shot_num, positions):
        """Update HDF5 position arrays with current shot position data"""
        if positions is None:
            return
            
        with h5py.File(self.save_path, 'a') as f:
            if self.is_45deg:
                # For 45-degree probes, update each probe's position separately
                for probe, pos in positions.items():
                    if pos is not None:  # Only update if we have valid position data
                        pos_arr = f[f'/Control/Positions/{probe}/positions_array']
                        pos_arr[shot_num-1] = (shot_num, pos)
            else:
                # For regular XY/XYZ acquisition
                pos_arr = f['/Control/Positions/positions_array']
                if all(p is not None for p in positions.values()):
                    if self.nz is None:
                        pos_arr[shot_num-1] = (shot_num, positions['x'], positions['y'])
                    else:
                        pos_arr[shot_num-1] = (shot_num, positions['x'], positions['y'], positions['z'])

#===============================================================================================================================================
# Acquisition Function for XY or XYZ probe drive
#===============================================================================================================================================
def initialize_motor(positions, motor_ips, nz, config_path='motion/config.txt'):
    config = load_config(config_path)
    # Check if motor movement is needed
    needs_movement = False
    if len(positions) > 1:
        first_pos = positions[0]
        last_pos = positions[-1]
        if not (first_pos['x'] == last_pos['x'] and first_pos['y'] == last_pos['y'] and 
                (nz is None or first_pos['z'] == last_pos['z'])):
            needs_movement = True
    
    # Initialize motor control if needed
    mc = None
    if needs_movement:
        print("Initializing motor...", end='')
        if nz is None:
            print("XY drive in use")
            mc = Motor_Control_2D(motor_ips['x'], motor_ips['y'])
            # Add motor boundary for 2D drive
            mc.boundary_checker.add_motor_boundary(lambda x, y, z: motor_boundary_2D(x, y, z, config))
        else:
            print("XYZ drive in use")
            mc = Motor_Control_3D(motor_ips['x'], motor_ips['y'], motor_ips['z'])
            # Add boundaries only for 3D drive
            mc.boundary_checker.add_probe_boundary(lambda x, y, z: outer_boundary(x, y, z, config), is_outer_boundary=True)
            # mc.boundary_checker.add_probe_boundary(lambda x, y, z: obstacle_boundary(x, y, z, config))
            mc.boundary_checker.add_motor_boundary(lambda x, y, z: motor_boundary(x, y, z, config))
    else:
        print("No motor movement required")
    return mc, needs_movement

#===============================================================================================================================================
# Acquisition Function for 45 degree probe drive
#===============================================================================================================================================
def initialize_motor_45deg(positions, motor_ips):
    # Initialize dictionary to store motor controllers
    motors = {}
    
    # Try to connect to each probe's motor
    for probe in ['P16', 'P22', 'P29', 'P34', 'P42']:
        try:
            # Special case for P29 which has different cm_per_turn
            if probe == 'P29':
                motors[probe] = MC(server_ip_addr=motor_ips[probe], name=f"probe_{probe}", 
                                 stop_switch_mode=2, cm_per_turn=0.127)
            else:
                motors[probe] = MC(server_ip_addr=motor_ips[probe], name=f"probe_{probe}", 
                                 stop_switch_mode=2)
                
            # Set motor speed if connection successful
            motors[probe].motor_speed = 4
            print(f"Connected to {probe} motor")
            
        except Exception as e:
            print(f"Could not connect to {probe} motor: {str(e)}")
            motors[probe] = None
            
    return motors

def move_45deg_probes(mc_list, move_to_list):

	pos_list = []

	for mc in mc_list:
		mc.enable

	for i, mc in enumerate(mc_list):
		mc.motor_position = move_to_list[i]

	for i, mc in enumerate(mc_list): 

		pos = mc.motor_position
		
		if round(pos,2) != move_to_list[i]:
			retry = 0
			while retry < 3:
				try:
					mc.motor_position = move_to_list[i]
					pos = mc.motor_position
					if round(pos,2) == move_to_list[i]:
						break
					else:
						retry += 1
				except:
					print("Failed to move to position %.2f" %(move_to_list[i]))

		pos_list.append(round(pos,2))
		mc.disable
	
	return pos_list


#-------------------------------------------------------------------------------------------------------------
def get_positions_xy(config):
    """Generate the positions array for probe movement using config dict.
    Returns:
        tuple: (positions, xpos, ypos)
            - positions: Array of tuples (shot_num, x, y)
            - xpos: Array of x positions
            - ypos: Array of y positions
    """
    nx = config['nx']
    ny = config['ny']
    xmin = config['xmin']
    xmax = config['xmax']
    ymin = config['ymin']
    ymax = config['ymax']
    num_duplicate_shots = config['num_duplicate_shots']
    num_run_repeats = config['num_run_repeats']
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

def get_positions_xyz(config):
    """Generate the positions array for probe movement in 3D using config dict.
    Returns:
        tuple: (positions, xpos, ypos, zpos)
            - positions: Array of tuples (shot_num, x, y, z)
            - xpos: Array of x positions
            - ypos: Array of y positions
            - zpos: Array of z positions
    """
    nx = config['nx']
    ny = config['ny']
    nz = config['nz']
    xmin = config['xmin']
    xmax = config['xmax']
    ymin = config['ymin']
    ymax = config['ymax']
    zmin = config['zmin']
    zmax = config['zmax']
    num_duplicate_shots = config['num_duplicate_shots']
    num_run_repeats = config['num_run_repeats']
    if nx == 0 or ny == 0 or nz == 0:
        sys.exit('Position array is empty.')
        
    xpos = np.linspace(xmin, xmax, nx)
    ypos = np.linspace(ymin, ymax, ny) 
    zpos = np.linspace(zmin, zmax, nz)

    # Calculate total number of positions including duplicates and repeats
    total_positions = nx * ny * nz * num_duplicate_shots * num_run_repeats

    # Allocate the positions array
    positions = np.zeros(total_positions,
                        dtype=[('shot_num', '>u4'), ('x', '>f4'), ('y', '>f4'), ('z', '>f4')])

    # Create 3D rectangular shape position array
    index = 0
    for repeat_cnt in range(num_run_repeats):
        for z in zpos:
            for y in ypos:
                for x in xpos:
                    for dup_cnt in range(num_duplicate_shots):
                        positions[index] = (index + 1, x, y, z)
                        index += 1
                    
    return positions, xpos, ypos, zpos

def outer_boundary(x, y, z, config):
    """Return True if position is within allowed range using config dict."""
    x_limits = config['x_limits']
    y_limits = config['y_limits']
    z_limits = config['z_limits']
    return (x_limits[0] <= x <= x_limits[1] and 
            y_limits[0] <= y <= y_limits[1] and 
            z_limits[0] <= z <= z_limits[1])

def obstacle_boundary(x, y, z, config):
    """Return True if position is NOT in obstacle using config dict."""
    # Check large box obstacle (30x6x11 cm box from x=-50 to -20)
    buffer = 0.2  # Small buffer to ensure paths don't get too close
    # You may want to make these obstacle parameters configurable as well
    in_obstacle = ( -60 <= x <= -17 and 
                    -2.5 <= y <= 5 and 
                    -6.5 <= z <= 9)
    
    return not in_obstacle

def motor_boundary(x, y, z, config):
    """Return True if position is within allowed range using config dict."""
    xm_limits = config['xm_limits']
    ym_limits = config['ym_limits']
    zm_limits = config['zm_limits']
    in_outer_boundary = (xm_limits[0] <= x <= xm_limits[1] and 
                        ym_limits[0] <= y <= ym_limits[1] and 
                        zm_limits[0] <= z <= zm_limits[1])
    return in_outer_boundary

def motor_boundary_2D(x, y, z, config):
    """Return True if position is within allowed range using config dict."""
    xm_limits = config['xm_limits']
    ym_limits = config['ym_limits']
    in_outer_boundary = (xm_limits[0] <= x <= xm_limits[1] and 
                        ym_limits[0] <= y <= ym_limits[1] and
                        -999 <= z <= 999)
    return in_outer_boundary