# Motion Package

This package contains all position and motor control functionality for the LAPD DAQ system.

## Configuration

See `example_experiment_config.txt` in the project root.

**Example for XY/XYZ Movement:**
```ini
[position]
nx = 31
ny = 41
xmin = -15
xmax = 15
ymin = -20
ymax = 20
```

**Example for 45deg Movement:**
```ini
[position]
probe_list = P16,P22,P29,P34,P42
nx = 37
xstart = {"P16": -38, "P22": -18, "P29": -38, "P34": -38, "P42": -38}
xstop = {"P16": -38, "P22": 18, "P29": -38, "P34": -38, "P42": -38}
```

If you want a run without probe movement, leave `[position]` empty or commented out.

## Configuration Loading

The motion package provides a centralized configuration loader:

```python
from motion.position_manager import load_position_config

# Load configuration with automatic mode detection
config, is_45deg = load_position_config('experiment_config.txt')

if config is None:
    print("No position configuration - stationary acquisition")
elif is_45deg:
    print("45-degree probe acquisition detected")
else:
    print("XY/XYZ grid acquisition detected")
```


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
Handles position arrays, HDF5 position data storage, and position-related metadata. Automatically detects acquisition mode from `[position]` section in `experiment_config.txt`.

```python
from motion import PositionManager

# Create position manager (automatically detects acquisition mode and loads positions)
pos_manager = PositionManager(save_path, config_path='experiment_config.txt')

# Access loaded positions
positions = pos_manager.positions
xpos = pos_manager.xpos
ypos = pos_manager.ypos
zpos = pos_manager.zpos  # Only available for 3D configurations

# Initialize HDF5 position structure
positions = pos_manager.initialize_position_hdf5()

# Update position data
pos_manager.update_position_hdf5(shot_num, positions)
```

**Automatic Mode Detection:**
- **45-degree mode**: Detected when config contains `probe_list` + dictionary-format `xstart`/`xstop`
- **XY/XYZ mode**: Detected when config contains standard grid parameters (`nx`, `ny`, etc.)
- **Stationary mode**: When no `[position]` section exists

**Automatic Position Loading:**
- Positions are automatically loaded during `__init__`
- Access via `self.positions`, `self.xpos`, `self.ypos`, `self.zpos`
- No need to manually call `get_positions()`

### Motor Control Methods
Motor control functions are now integrated as methods of the `PositionManager` class:

```python
from motion import PositionManager

# Create position manager
pos_manager = PositionManager(save_path, config_path='experiment_config.txt')

# Initialize motor control (automatically uses config from PositionManager)
if pos_manager.is_45deg:
    # For 45-degree probes
    motors = pos_manager.initialize_motor_45deg()
    if motors:
        achieved_positions = pos_manager.move_45deg_probes(active_motors, target_positions)
else:
    # For XY/XYZ probes
    mc = pos_manager.initialize_motor()
    if mc:
        # Use motor control for movement
        pass
```

**Key Changes:**
- Motor control functions are now methods of `PositionManager`
- Configuration is automatically loaded from `self.config`
- No need to pass external parameters
- Better integration with position management

### Utility Functions

**Position Generation:**
```python
from motion import get_positions_xy, get_positions_xyz, get_positions_45deg, create_all_positions_45deg

# Generate position arrays
positions, xpos, ypos = get_positions_xy(config)
positions, xpos, ypos, zpos = get_positions_xyz(config)
positions, xpos = get_positions_45deg(xstart, xstop, nx, nshots)
all_positions, all_xpos = create_all_positions_45deg(pr_ls, xstart, xstop, nx, nshots)
```

**Boundary Checking:**
```python
from motion import outer_boundary, obstacle_boundary, motor_boundary, motor_boundary_2D

# Check if position is within boundaries
is_valid = outer_boundary(x, y, z, config)
is_clear = obstacle_boundary(x, y, z, config)
is_motor_safe = motor_boundary(x, y, z, config)
is_2d_safe = motor_boundary_2D(x, y, z, config)
```

## Usage

### Direct Import (Recommended)
```python
from motion import PositionManager, load_position_config
from motion import get_positions_xy, outer_boundary, motor_boundary
```

### Complete Example
```python
from motion import PositionManager

# Create position manager with automatic configuration loading
pos_manager = PositionManager('data.h5', 'experiment_config.txt')

# Initialize HDF5 structure
positions = pos_manager.initialize_position_hdf5()

# Initialize motor control
if pos_manager.is_45deg:
    motors = pos_manager.initialize_motor_45deg()
else:
    mc = pos_manager.initialize_motor()

# During acquisition, update positions
pos_manager.update_position_hdf5(shot_num, current_positions)
```

## Integration

This package is designed to work with:
- Multi-scope acquisition system
- Current motor control via `Motor_Control` and `Motor_Control_1D`
- Future bapsf_motion library integration

## Architecture

The motion package separates position management from scope operations, making the code more modular and preparing it for new motion control libraries like bapsf_motion. The `PositionManager` class now provides a unified interface for both position management and motor control. 