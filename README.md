# LAPD_DAQ
Data acquisition script using Ethernet motor and LeCroy scope as digitizer on LAPD.
Modified from Scope_DAQ used on process plasma chamber

## Configuration

All experiment settings are now configured through a single file: `experiment_config.txt`. This replaces the old system of hardcoded values in individual scripts.

### Setting Up an Experiment

1. **Copy the example config:**
   ```bash
   cp example_experiment_config.txt experiment_config.txt
   ```

2. **Edit the configuration sections:**

   **`[experiment]`** - Main experiment description (multi-line text)
   ```ini
   [experiment]
   description = """
   Your detailed experiment description here...
   Include plasma conditions, timing, probe setup, etc.
   """
   ```

   **`[scopes]`** - Scope descriptions
   ```ini
   [scopes]
   LPScope = LeCroy HDO4104 - 4GHz 20GS/s oscilloscope for Langmuir probe diagnostics
   testScope = LeCroy WavePro 404HD - RF and probe diagnostics
   ```

   **`[channels]`** - Channel descriptions
   ```ini
   [channels]
   LPScope_C1 = Isat, p39, G: 1
   LPScope_C2 = Isweep, p39
   testScope_C1 = RF signal input
   ```

   **`[position]`** - Motion/position settings (optional)
   ```ini
   [position]
   # Uncomment these lines to enable probe movement:
   # nx = 31
   # ny = 41
   # xmin = -15
   # xmax = 15
   # ...
   ```

3. **Choose acquisition mode:**
   - **With movement:** Uncomment and fill the `[position]` section → Use `Data_Run.py` or `Data_Run_45deg.py`
   - **Stationary:** Leave `[position]` empty/commented → Use `Data_Run_MultiScope_Camera.py`

### Data Acquisition Integration

1. **HDF5 Structure**
   ```
   experiment_name.hdf5/
   ├── attrs/
   │   ├── description          # Overall experiment description
   │   ├── creation_time        # Time when file was created
   │   └── source_code          # Python scripts used to create the file
   │
   ├── Control/
   │   └── Positions/
   │       ├── positions_setup_array  # Planned positions with metadata
   │       │   └── attrs/
   │       │       ├── xpos           # Array of x positions
   │       │       ├── ypos           # Array of y positions
   │       │       └── zpos           # Array of z positions (if 3D)
   │       │
   │       └── positions_array        # Actual achieved positions
   │
   ├── FastScope/               # Scope group
   │   ├── attrs/
   │   │   ├── description     # Scope description
   │   │   ├── ip_address      # Scope IP address
   │   │   ├── scope_type      # Scope identification string
   │   │   └── external_delay(ms)  # External delay in milliseconds
   │   │
   │   ├── time_array          # Time array for all channels
   │   │   └── attrs/
   │   │       ├── units       # "seconds"
   │   │       ├── description # Time array info and mode
   │   │       └── dtype       # Data type of time array
   │   │
   │   ├── shot_1/            # First shot data
   │   │   ├── attrs/
   │   │   │   └── acquisition_time
   │   │   │
   │   │   ├── C1_data        # Channel 1 voltage data
   │   │   │   └── attrs/
   │   │   │       ├── description  # Channel description
   │   │   │       └── dtype       # Data type
   │   │   ├── C1_header      # Channel 1 binary header
   │   │   │   └── attrs/
   │   │   │       └── description
   │   │   ├── C2_data        # Channel 2 voltage data
   │   │   ├── C2_header      # Channel 2 binary header
   │   │   └── ...            # Additional channels
   │   │
   │   ├── shot_2/            # Second shot data
   │   │   └── ...            # Same structure as shot_1
   │   │
   │   └── shot_N/            # Shot N data
   │       ├── attrs/         # For skipped positions:
   │       │   ├── skipped = True
   │       │   └── skip_reason = "Cannot find valid path..."
   │       └── acquisition_time
   │
   └── x-ray_dipole/          # Second scope group
       └── ...                # Same structure as above
```

### Key Features
1. **Root Level**
   - Contains experiment metadata and scope groups
   - Stores source code used to create the file
   - Includes experiment description and creation time

2. **Control Group**
   - Contains probe position information
   - `positions_setup_array`: Planned probe positions with metadata
   - `positions_array`: Actual achieved positions during acquisition

3. **Scope Groups**
   - Each scope has its own group with metadata
   - Time array stored once per scope (in seconds)
   - External delay and scope configuration information
   - Supports both normal and sequence mode acquisition

4. **Shot Data**
   - Numbered shots under each scope group
   - Each shot contains:
     - Voltage data for each channel
     - Binary header data for each channel
     - Channel descriptions and data types
     - Acquisition timestamp
   - For skipped positions (e.g., blocked by obstacles):
     - `skipped` attribute set to True
     - `skip_reason` explains why position was skipped

5. **Data Optimization**
   - Efficient chunking for large datasets
   - Compression enabled for voltage data
   - Metadata stored as attributes
   - Time array shared across all shots

### Reading the Data
Example Python code to read the data:
```python
import h5py
import numpy as np

# Open the HDF5 file
with h5py.File('experiment_name.hdf5', 'r') as f:
    # Read experiment description
    description = f.attrs['description']
    
    # Get planned and actual positions
    positions_setup = f['/Control/Positions/positions_setup_array'][:]
    positions_actual = f['/Control/Positions/positions_array'][:]
    
    # Access scope data
    scope_group = f['FastScope']
    time_array = scope_group['time_array'][:]
    
    # Read shots
    for shot_name in [k for k in scope_group.keys() if k.startswith('shot_')]:
        shot_group = scope_group[shot_name]
        
        # Check if position was skipped
        if 'skipped' in shot_group.attrs:
            print(f"{shot_name} was skipped: {shot_group.attrs['skip_reason']}")
            continue
            
        # Read channel data
        for channel in [k for k in shot_group.keys() if k.endswith('_data')]:
            data = shot_group[channel][:]
            description = shot_group[channel].attrs['description']
```

2. **Position Skipping**
   - When a position is blocked by an obstacle:
     ```
     shot_group.attrs['skipped'] = True
     shot_group.attrs['skip_reason'] = "Cannot find valid path: Position blocked by obstacle"
     ```
   - Data file maintains complete record of attempted positions
   - Empty shot groups created with skip explanations

### Notes
- All time values are stored in seconds
- Binary headers contain scope-specific metadata
- Source code is preserved for reproducibility
- Skipped positions are documented with reasons
- Data compression and chunking optimize storage


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

