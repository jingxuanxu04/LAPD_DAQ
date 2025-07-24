"""
Motion control and position management package for LAPD DAQ system.

This package contains:
- PositionManager: Handles position arrays and HDF5 position storage
- Motor control functions for different probe configurations
- Position generation utilities
"""

import os
import sys

# Add the motion directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import main classes and functions for easy access
from .position_manager import (
    PositionManager,
    initialize_motor, 
    initialize_motor_45deg, 
    move_45deg_probes,
    get_positions_xy,
    get_positions_xyz,
    outer_boundary,
    obstacle_boundary,
    motor_boundary,
    motor_boundary_2D
)

from .Motor_Control import Motor_Control_2D, Motor_Control_3D
from .Motor_Control_1D import Motor_Control

__all__ = [
    'PositionManager',
    'initialize_motor', 
    'initialize_motor_45deg',
    'move_45deg_probes',
    'get_positions_xy',
    'get_positions_xyz', 
    'outer_boundary',
    'obstacle_boundary',
    'motor_boundary',
    'motor_boundary_2D',
    'Motor_Control_2D',
    'Motor_Control_3D', 
    'MC',
    'Motor_Control'
] 