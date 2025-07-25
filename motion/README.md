# Motion Package

This package contains all position and motor control functionality for the LAPD DAQ system.

## Configuration

All experiment, scope, channel, and (optionally) position/motion settings are now in a single file: `experiment_config.txt` in the project root.

- `[experiment]`: General experiment description (multi-line string allowed)
- `[scopes]`: Scope names and descriptions
- `[channels]`: Channel names and descriptions
- `[position]`: (Optional) Position/motion settings. If empty or commented out, the system assumes stationary acquisition (no movement).

**Example for XY/XYZ Movement:**
```ini
[position]
nx = 31
ny = 41
xmin = -15
xmax = 15
ymin = -20
ymax = 20
num_duplicate_shots = 11
num_run_repeats = 1
```

**Example for 45deg Movement:**
```ini
[position]
probe_list = P16,P22,P29,P34,P42
nx = 37
nshots = 5
xstart = {"P16": -38, "P22": -18, "P29": -38, "P34": -38, "P42": -38}
xstop = {"P16": -38, "P22": 18, "P29": -38, "P34": -38, "P42": -38}
```

If you want a stationary run (e.g., for Data_Run_MultiScope_Camera), leave `[position]` empty or commented out.

## Movement Styles

The system supports two movement styles:

1. **XY/XYZ Movement** (`Data_Run.py`): Regular rectangular grid scanning
   - Uses `nx`, `ny`, `nz`, `xmin`, `xmax`, `ymin`, `ymax`, `zmin`, `zmax`
   - Supports 2D (XY) and 3D (XYZ) scanning patterns
   
2. **45deg Movement** (`Data_Run_45deg.py`): Multi-probe radial line scanning  
   - Uses `probe_list`, `nx`, `nshots`, `xstart`, `xstop`
   - Each probe can have different start/stop positions
   - Designed for 45-degree angle probe configurations

## Components

### PositionManager (`position_manager.py`)
Handles position arrays, HDF5 position data storage, and position-related metadata. Reads from `[position]` in `experiment_config.txt`.

```python
from motion import PositionManager

# Create position manager
pos_manager = PositionManager(save_path, nz=None, is_45deg=False)

# Initialize HDF5 position structure
positions = pos_manager.initialize_position_hdf5()

# Update position data
pos_manager.update_position_hdf5(shot_num, positions)
```

### Motor Control (`motor_control.py`)
Functions for initializing and controlling different types of probe motors.

```python
from motion import initialize_motor, initialize_motor_45deg, move_45deg_probes

# For XY/XYZ probes
mc, needs_movement = initialize_motor(positions, motor_ips, nz)

# For 45-degree probes  
motors = initialize_motor_45deg(positions, motor_ips)
achieved_positions = move_45deg_probes(active_motors, target_positions)
```

## Usage

### Direct Import (Recommended)
```python
from motion import PositionManager, initialize_motor, initialize_motor_45deg
```

## Integration

This package is designed to work with:
- Multi-scope acquisition system
- Current motor control via `Motor_Control` and `Motor_Control_1D`
- Future bapsf_motion library integration

## Architecture

The motion package separates position management from scope operations, making the code more modular and preparing it for new motion control libraries like bapsf_motion. 