# LAPD_DAQ
 Data acquisition script using Ethernet motor and LeCroy scope as digitizer on LAPD.
Modified from Scope_DAQ used on process plasma chamber

## Motor Control and Obstacle Avoidance

### Motor Control Classes
The system supports both 2D and 3D probe movement through the `Motor_Control_2D` and `Motor_Control_3D` classes:

1. **Motor_Control_1D**
   - Base class for individual motor control
   - Handles direct motor commands and status monitoring
   - Properties: position, velocity, status, alarms
   - Safety features: limit switches, timeout protection

2. **Motor_Control_2D**
   - Controls X-Y probe movement
   - Converts probe coordinates to motor coordinates
   - Synchronizes motor velocities for straight-line motion
   - Properties: probe_positions, motor_positions, motor_velocity

3. **Motor_Control_3D**
   - Controls X-Y-Z probe movement
   - Advanced path planning with obstacle avoidance
   - Intelligent waypoint generation for safe paths
   - Velocity scaling for smooth multi-segment motion

### Obstacle Avoidance System

The `BoundaryChecker` class provides intelligent path planning around obstacles:

1. **Boundaries and Obstacles**
   ```python
   # Define probe movement limits and obstacles in Data_Run.py
   def probe_boundary(x, y, z):
       # Check outer boundary
       in_outer_boundary = (x_limits[0] <= x <= x_limits[1] and 
                          y_limits[0] <= y <= y_limits[1] and 
                          z_limits[0] <= z <= z_limits[1])
       
       # Check obstacles (e.g., large box obstacle)
       in_obstacle = (-50 <= x <= -20 and 
                     -3 <= y <= 3 and 
                     -5.5 <= z <= 5.5)
       
       return in_outer_boundary and not in_obstacle
   ```

2. **Path Planning Features**
   - Automatic detection of blocked paths
   - Multi-strategy path finding:
     - Direct paths when possible
     - Two-point paths with offset
     - Three-point paths for complex obstacles
     - Random exploration for difficult cases
   - Path optimization for smooth motion
   - Caching of successful paths for similar movements

3. **Safety Features**
   - Minimum clearance from obstacles
   - Configurable resolution for path checking
   - Velocity scaling based on path complexity
   - Emergency stop handling

### Data Acquisition Integration

The system handles inaccessible positions gracefully:

1. **Position Skipping**
   - When a position is blocked by an obstacle:
     ```
     shot_group.attrs['skipped'] = True
     shot_group.attrs['skip_reason'] = "Cannot find valid path: Position blocked by obstacle"
     ```
   - Data file maintains complete record of attempted positions
   - Empty shot groups created with skip explanations

2. **HDF5 Structure**
   ```
   experiment_name.hdf5/
   ├── Control/
   │   └── Positions/
   │       ├── positions_setup_array  # Planned positions
   │       └── positions_array        # Actual achieved positions
   │
   ├── scope_name/
   │   ├── shot_N/                   # For successful positions
   │   │   └── [scope data]
   │   │
   │   └── shot_M/                   # For skipped positions
   │       ├── attrs/
   │       │   ├── skipped = True
   │       │   └── skip_reason = "..."
   │       └── acquisition_time
   ```

### Usage Example
```python
# Initialize 3D motor control with obstacle avoidance
mc = Motor_Control_3D(x_ip_addr='...', y_ip_addr='...', z_ip_addr='...')
mc.boundary_checker.add_boundary(probe_boundary)

# Move to position with automatic obstacle avoidance
try:
    mc.probe_positions = (x, y, z)
except ValueError as e:
    print(f"Position skipped: {e}")
```

### Notes
- Obstacle definitions can be modified in `Data_Run.py`
- Path planning strategies can be tuned via `BoundaryChecker` parameters
- Failed positions are documented in the HDF5 file
- Motor movement is disabled between acquisitions for safety
- Emergency stops preserve the last known good position

## HDF5 Data Structure
The data acquisition script creates HDF5 files with the following structure:

```
experiment_name.hdf5/
├── attrs/
│   ├── description          # Overall experiment description
│   ├── creation_time        # Time when file was created
│   └── source_code          # Python scripts used to create the file
│       ├── Data_Run_0D.py
│       ├── multi_scope_acquisition.py
│       └── LeCroy_Scope.py
│
├── magnetron/              # First scope group
│   ├── attrs/
│   │   ├── description     # Scope description
│   │   ├── ip_address      # Scope IP address
│   │   ├── scope_type      # Scope identification string
│   │   └── external_delay(ms)  # External delay in milliseconds
│   │
│   ├── time_array          # Time array for all channels
│   │   ├── attrs/
│   │   │   ├── units       # "seconds"
│   │   │   ├── description # "Time array for all channels" or "Time array for all channels; data saved in sequence mode"
│   │   │   └── dtype       # Data type of time array
│   │
│   ├── shot_0/            # First shot data
│   │   ├── attrs/
│   │   │   └── acquisition_time
│   │   │
│   │   ├── C1_data        # Channel 1 voltage data (1D array for normal mode, 2D array for sequence mode)
│   │   │   └── attrs/
│   │   │       ├── description  # Channel description
│   │   │       └── dtype       # Data type of voltage data
│   │   ├── C1_header      # Channel 1 binary header
│   │   │   └── attrs/
│   │   │       └── description
│   │   ├── C2_data        # Channel 2 voltage data
│   │   ├── C2_header      # Channel 2 binary header
│   │   └── ...            # Additional channels
│   │
│   ├── shot_1/            # Second shot data
│   └── ...                # Additional shots
│
├── x-ray_dipole/          # Second scope group
│   └── ...                # Same structure as above
│
└── Bdot/                  # Third scope group
    └── ...                # Same structure as above
```

### Key Features
1. **Root Level**
   - Contains experiment metadata and scope groups
   - Stores source code used to create the file
   - Includes experiment description and creation time

2. **Scope Groups**
   - Each scope has its own group with metadata
   - Time array stored once per scope (in seconds)
   - External delay and scope configuration information
   - Supports both normal and sequence mode acquisition

3. **Shot Data**
   - Numbered shots under each scope group
   - Each shot contains:
     - Voltage data for each channel (1D array for normal mode, 2D array for sequence mode)
     - Binary header data for each channel
     - Channel descriptions and data types
     - Acquisition timestamp

4. **Time Arrays**
   - Stored in seconds in HDF5 file
   - Used in milliseconds for plotting
   - Saved once after first acquisition
   - Reused for all subsequent shots
   - Includes sequence mode information in attributes

5. **Sequence Mode Support**
   - Automatically detects and handles sequence mode acquisition
   - Stores sequence data as 2D arrays (segments × samples)
   - Optimized chunking for efficient data access
   - Maintains backward compatibility with normal mode

### Reading the Data
Example Python code to read the data:
```python
import h5py
import numpy as np

# Open the HDF5 file
with h5py.File('experiment_name.hdf5', 'r') as f:
    # Read experiment description
    description = f.attrs['description']
    
    # Access source code
    source_code = eval(f.attrs['source_code'])
    
    # Read scope data
    for scope_name in f.keys():
        scope_group = f[scope_name]
        
        # Get time array (in seconds)
        time_array = scope_group['time_array'][:]
        is_sequence = 'sequence mode' in scope_group['time_array'].attrs['description']
        
        # Read shots
        for shot_name in [k for k in scope_group.keys() if k.startswith('shot_')]:
            shot_group = scope_group[shot_name]
            
            # Read channel data
            for channel in [k for k in shot_group.keys() if k.endswith('_data')]:
                data = shot_group[channel][:]
                description = shot_group[channel].attrs['description']
                
                if is_sequence:
                    num_segments = data.shape[0]
                    samples_per_segment = data.shape[1]
                    print(f"Sequence data: {num_segments} segments, {samples_per_segment} samples each")
```

### Notes
- Time values are stored in seconds but displayed in milliseconds in plots
- Binary headers contain scope-specific metadata for each channel
- Source code is preserved with data for reproducibility
- Each scope can have different time arrays based on its settings
- Sequence mode data is stored as 2D arrays with optimized chunking
- Data compression and chunking are automatically optimized based on acquisition mode
