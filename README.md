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

### Automatic Acquisition Mode Detection

The system now automatically detects the acquisition mode from your configuration:

- **45-degree probe acquisition**: Detected when `[position]` section contains:
  - `probe_list` parameter (e.g., `probe_list = P16,P22,P29,P34,P42`)
  - Dictionary-format `xstart` and/or `xstop` parameters:
    ```ini
    xstart = {"P16": -38, "P22": -18, "P29": -38, "P34": -38, "P42": -38}
    xstop = {"P16": -38, "P22": 18, "P29": -38, "P34": -38, "P42": -38}
    ```

- **XY/XYZ probe acquisition**: Detected when `[position]` section contains:
  - Standard grid parameters: `nx`, `ny`, `xmin`, `xmax`, `ymin`, `ymax`
  - Optional Z parameters: `nz`, `zmin`, `zmax` (for 3D movement)

- **Stationary acquisition**: When `[position]` section is empty or missing

The `is_45deg` parameter is now automatically determined and no longer needs to be manually specified in most cases.

### Configuration Loading System

**Consolidated Configuration Parser**

The system now uses a single, centralized `load_position_config()` function located in `motion/position_manager.py`:

```python
from motion.position_manager import load_position_config

# Load configuration with automatic mode detection
config, is_45deg = load_position_config('experiment_config.txt')
```

**Function Features:**
- **Unified parsing**: Handles all configuration formats (tuples, JSON dicts, lists, etc.)
- **Automatic mode detection**: Returns both config data and determined acquisition mode
- **Smart type conversion**: 
  - Comma-separated values → tuples (e.g., `x_limits = -40,200`)
  - JSON format → dictionaries (e.g., `xstart = {"P16": -38, "P22": -18}`)
  - String lists → arrays (e.g., `probe_list = P16,P22,P29,P34,P42`)
- **Backward compatibility**: Existing code continues to work unchanged

**Return Values:**
- `config`: Dictionary of parsed configuration parameters (or `None` if no config)
- `is_45deg`: Boolean indicating 45-degree probe acquisition mode

**Previous Behavior (deprecated):**
Previously, there were two separate `load_position_config` functions in different modules, which caused confusion and code duplication. The consolidation eliminates this redundancy while maintaining all functionality.

**PositionManager Integration:**
The `PositionManager` class now automatically determines the acquisition mode:

```python
# Old way (manual specification)
pos_manager = PositionManager(save_path, nz=None, is_45deg=True)

# New way (automatic detection from config)
pos_manager = PositionManager(save_path, nz=None)  # is_45deg auto-detected

# Still supports manual override when needed
pos_manager = PositionManager(save_path, nz=None, is_45deg=False)  # Force non-45deg
```


### Data Acquisition Integration

#### HDF5 Structure and Data Format

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
│   │   ├── C1_data        # Channel 1 raw data (int16)
│   │   │   └── attrs/
│   │   │       ├── description  # Channel description
│   │   │       └── dtype       # Data type (int16)
│   │   ├── C1_header      # Channel 1 binary header
│   │   │   └── attrs/
│   │   │       └── description
│   │   ├── C2_data        # Channel 2 raw data (int16)
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

#### Key Features and Data Format (2025 Update)

1. **Raw int16 Data Storage**
   - All scope waveform data is now saved as raw `int16` arrays for maximum write speed and minimal file size.
   - No conversion to float64 is performed during acquisition or saving.
   - To convert to physical units, use the scale/offset in the binary header (see LeCroy documentation).

2. **HDF5 Optimization Settings**
   - **Chunking:** Large chunk sizes are used for fast writing (typically 512k–1M samples per chunk).
   - **Compression:** By default, no compression is used for maximum speed. Optionally, `'lzf'` can be enabled for fast, lightweight compression.
   - **Shuffle:** Disabled for speed (enabling can improve compression if used).
   - **Fletcher32:** Enabled by default for data integrity (detects corruption on read).

3. **Metadata and Structure**
   - Channel and scope descriptions, acquisition time, and binary headers are stored as attributes or datasets.
   - Skipped positions are recorded with `skipped=True` and a `skip_reason` attribute.
   - Time arrays are stored once per scope group.

#### Reading int16 Data

When reading, you will get raw int16 arrays. To convert to voltage:

```python
import h5py
import numpy as np

with h5py.File('experiment_name.hdf5', 'r') as f:
    scope_group = f['FastScope']
    for shot_name in [k for k in scope_group.keys() if k.startswith('shot_')]:
        shot_group = scope_group[shot_name]
        for channel in [k for k in shot_group.keys() if k.endswith('_data')]:
            raw = shot_group[channel][:]  # int16 array
            header = shot_group[channel.replace('_data', '_header')][:]
            # Use header to get vertical_gain and vertical_offset, then:
            # voltage = vertical_gain * raw - vertical_offset
```

#### HDF5 Performance Tuning

- For **maximum speed**, use `compression=None`, `shuffle=False`, `fletcher32=False`.
- For **data integrity**, set `fletcher32=True` (default in this repo).
- For **smaller files** with some speed, use `compression='lzf'` and optionally `shuffle=True`.
- Chunk size can be tuned for your disk and data size; larger chunks are faster up to a point.

---

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

