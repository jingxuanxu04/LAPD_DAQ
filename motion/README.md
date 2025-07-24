# Motion Package

This package contains all position and motor control functionality for the LAPD DAQ system.

## Components

### PositionManager (`position_manager.py`)
Handles position arrays, HDF5 position data storage, and position-related metadata.

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

### Configuration via config.txt

Global variables such as `nx`, `ny`, `nz`, `xmin`, `xmax`, `ymin`, `ymax`, `zmin`, `zmax`, `num_duplicate_shots`, `num_run_repeats`, `x_limits`, `y_limits`, `z_limits`, `xm_limits`, `ym_limits`, `zm_limits` are now loaded from a configuration file `config.txt` in the `motion` folder.

**Example usage:**
```python
from motion.position_manager import load_config
config = load_config('motion/config.txt')
nx = config['nx']
# ... use other config variables as needed
```

See `motion/example_config.txt` for a template.

### Backward Compatibility
```python
# Still works but deprecated
from multi_scope_acquisition import PositionManager
```

## Integration

This package is designed to work with:
- Multi-scope acquisition system
- Current motor control via `Motor_Control` and `Motor_Control_1D`
- Future bapsf_motion library integration

## Architecture

The motion package separates position management from scope operations, making the code more modular and preparing it for new motion control libraries like bapsf_motion. 