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


# LAPD DAQ System

Multi-scope data acquisition system for the Large Plasma Device (LAPD) with support for probe positioning using motion control systems.

## Overview

This system handles:
- Multi-scope data acquisition from LeCroy oscilloscopes
- Probe positioning using motion control systems
- HDF5 data storage with comprehensive metadata
- Real-time data visualization
- Support for both stationary and moving probe measurements

## Main Scripts

### Data_Run.py
Standard data acquisition script for stationary or simple motion control measurements.

### Data_Run bmotion.py
Data acquisition script using the `bapsf_motion` library for advanced probe positioning. See the [bmotion Acquisition System](#bmotion-acquisition-system) section for detailed information.

## Configuration Files

### experiment_config.txt
Main experiment configuration containing:
- Experiment description and parameters
- Scope IP addresses and channel assignments
- Shot configuration (num_duplicate_shots, num_run_repeats)
- Channel descriptions and settings

## HDF5 File Structure

### Standard Acquisition Structure
```
experiment_file.hdf5
├── attributes: description, creation_time, source_code
├── ScopeName1/
│   ├── attributes: description, ip_address, scope_type
│   ├── time_array (dataset)
│   ├── shot_1/
│   │   ├── attributes: acquisition_time
│   │   ├── C1_data (dataset, int16)
│   │   ├── C1_header (dataset, binary)
│   │   ├── C2_data (dataset, int16)
│   │   └── C2_header (dataset, binary)
│   ├── shot_2/
│   └── ...
├── ScopeName2/
│   └── ... (similar structure)
└── Control/
    └── Positions/
        ├── positions_array (dataset, structured array)
        └── ProbeX/ [for multi-probe setups]
            ├── shot_1/
            ├── shot_2/
            └── ...
```

### Data Types and Compression

- **Scope data**: Stored as `int16` with LZF compression for optimal speed/size balance
- **Time arrays**: Stored as `float64` for maximum precision
- **Position data**: 32-bit floats for position coordinates
- **Headers**: Binary data preserving original scope header information

## bmotion Acquisition System

### Overview
The `bmotion` acquisition system provides advanced probe positioning capabilities using the `bapsf_motion` library, specifically designed for LAPD's 6K probe drive system.

### Key Features
- **Multi-Motion Group Support**: Handle multiple motion groups simultaneously
- **Advanced Motion Planning**: Complex patterns, grids, and exclusion zones
- **TOML Configuration**: Flexible, human-readable motion configuration
- **Real-time Position Feedback**: Verification and logging of achieved positions
- **Coordinate Transforms**: Support for LAPD probe coordinate systems
- **Error Recovery**: Graceful handling of motion failures with data preservation

### Configuration

#### bmotion_config.toml
TOML configuration file for `bapsf_motion` containing:
- **Motion group definitions**: Individual motion systems (e.g., probe drives)
- **Drive and axis configurations**: Hardware-specific settings
- **Transform parameters**: Coordinate system transformations
- **Motion builder settings**: Grid patterns, exclusion zones, custom paths
- **Layer definitions**: Multi-layer scan configurations

Example structure:
```toml
[motion_groups.probe_x]
name = "Probe X Drive"
drives = ["x_axis"]

[motion_groups.probe_x.motion_builder]
type = "grid"
x_start = -40.0
x_stop = 40.0
x_step = 2.0
y_start = -30.0
y_stop = 30.0
y_step = 2.0
```

### bmotion HDF5 Structure

When using `Data_Run bmotion.py`, the following enhanced structure is created:

```
experiment_file.hdf5
├── Configuration/
│   └── bmotion_config (dataset)              # Complete TOML configuration
│
├── Control/
│   └── Positions/
│       ├── motion_group_1_name/              # Each motion group directly under Positions
│       │   ├── motion_list (dataset)         # Planned positions from bmotion
│       │   ├── positions_array (dataset)     # Actual achieved positions (structured)
│       │   └── attributes: name, key
│       ├── motion_group_2_name/
│       │   ├── motion_list (dataset)
│       │   ├── positions_array (dataset)     # Structured array: shot_num, x, y
│       │   └── attributes: name, key
│       └── ...
│
├── ScopeName1/                               # Standard scope data structure
│   ├── time_array (dataset)
│   ├── shot_1/
│   │   ├── C1_data, C1_header, ...
│   └── ...
└── ScopeName2/
    └── ...
```

#### Motion Group Datasets

**motion_list Dataset**
- **Purpose**: Stores the complete motion list generated by `bapsf_motion`
- **Format**: 2D numpy array where each row is a [x, y] position
- **Source**: Generated from TOML configuration (grid settings, exclusion zones, etc.)
- **Coordinates**: Positions in the measurement coordinate system (typically cm)
- **Storage**: Created once at initialization with all planned positions

**positions_array Dataset**
- **Purpose**: Records actual achieved positions for each shot
- **Format**: Structured array with dtype `[('shot_num', '>u4'), ('x', '>f4'), ('y', '>f4')]`:
  - `shot_num`: Shot number (1-based indexing, uint32)
  - `x`: Actual x position achieved by the motion system (float32)
  - `y`: Actual y position achieved by the motion system (float32)
- **Updates**: Populated in real-time during acquisition with position feedback
- **Size**: Pre-allocated for total number of shots
- **Access**: Each motion group has its own positions_array directly under `Control/Positions/{group_name}/`

**bmotion_config Dataset**
- **Purpose**: Preserves complete TOML configuration for reproducibility
- **Format**: String dataset containing full TOML file content
- **Location**: `Configuration/bmotion_config`

### Motion Workflow

1. **Configuration Loading**
   - Load TOML configuration file
   - Initialize `bapsf_motion` RunManager
   - Display available motion groups to user

2. **Motion Group Selection**
   - Present motion groups with sizes and descriptions
   - Allow user to select specific groups or all groups
   - Configure motion direction (forward/backward) for each group

3. **Motion List Generation**
   - Generate motion lists from TOML parameters
   - Calculate maximum motion list size across all groups
   - Store motion lists in HDF5 structure

4. **Acquisition Loop**
   - For each position index:
     - Move all selected motion groups to target positions
     - Wait for motion completion and verify positions
     - Acquire scope data for specified number of shots
     - Record actual achieved positions for each motion group
     - Handle motion errors gracefully with position logging

5. **Data Organization**
   - Each motion group maintains its own position history
   - Planned vs. achieved positions clearly separated
   - Complete configuration preserved for analysis

### Usage

```bash
python "Data_Run bmotion.py"
```

**Interactive Workflow:**
1. System loads TOML configuration and displays available motion groups
2. User selects which motion groups to use for the acquisition
3. User configures motion direction (forward/backward) for each group
4. System calculates total shots and begins acquisition
5. Real-time position feedback and data acquisition proceeds
6. Complete motion and scope data saved to HDF5 file

### Error Handling

- **Motion Failures**: Individual motion group failures are logged with reasons
- **Position Verification**: Actual vs. planned positions compared and stored
- **Data Integrity**: Skipped shots documented with skip reasons
- **Recovery**: System continues acquisition even if some motion groups fail
- **Configuration Backup**: Complete TOML config preserved in HDF5 file

### Integration Benefits

- **Reproducibility**: Complete motion configuration stored with data
- **Flexibility**: Support for complex motion patterns and multiple motion groups
- **Reliability**: Robust error handling and position verification
- **Analysis**: Clear separation of planned vs. achieved positions
- **Scalability**: Support for multiple simultaneous motion systems

## Key Features

### Optimized Data Acquisition
- Parallel scope arming for synchronized measurements
- Raw int16 data acquisition for maximum speed
- Chunked HDF5 storage with compression
- Automatic error recovery and data preservation

### Comprehensive Metadata
- Complete experiment description and parameters
- Source code preservation for reproducibility
- Scope and channel configuration details
- Timing and acquisition metadata

### Robust Error Handling
- Automatic scope reconnection on failures
- Motion error recovery with position logging
- Skipped shot tracking with reason codes
- Data integrity preservation during interruptions

## Usage Examples

### Standard Acquisition
```python
python Data_Run.py
```

### bmotion Acquisition
```python
python "Data_Run bmotion.py"
```

