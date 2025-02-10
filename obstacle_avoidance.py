import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

#===============================================================================================================================================
#===============================================================================================================================================

class BoundaryChecker:
    def __init__(self, verbose=False):
        self.probe_boundaries = []
        self.outer_boundary = None  # Function defining the valid workspace
        self.obstacle_boundaries = []  # Functions defining obstacles
        self.motor_boundaries = []
        self.check_resolution = 0.1
        self.min_clearance = 1.0
        self.buffer = 0.5  # Safety buffer for clearance
        self.obstacle_dimensions = None  # Will store (x_min, x_max), (y_min, y_max), (z_min, z_max)
        self.axis_clearances = None  # Will store [x_clearance, y_clearance, z_clearance]
        self.verbose = verbose
        
        # Default offset distances for path finding
        self.xy_offset = 4.0  # Default XY plane offset in cm
        self.z_offset = 2.0   # Default Z offset in cm
        self.min_offset = 2.0 # Minimum offset distance
        
    def _debug_print(self, *args, **kwargs):
        """Helper method for debug printing"""
        if self.verbose:
            print(*args, **kwargs)
            
    def _calculate_safe_offsets(self):
        """Calculate safe offset distances based on obstacle dimensions"""
        if not self.obstacle_dimensions:
            return
            
        (obs_x_min, obs_x_max), (obs_y_min, obs_y_max), (obs_z_min, obs_z_max) = self.obstacle_dimensions
        
        # Calculate obstacle size in each dimension
        x_size = abs(obs_x_max - obs_x_min)
        y_size = abs(obs_y_max - obs_y_min)
        z_size = abs(obs_z_max - obs_z_min)
        
        # Set offsets to be 1.5 times the obstacle size in that dimension
        # This ensures we go far enough around the obstacle
        self.xy_offset = max(self.min_offset, max(x_size, y_size) * 1.5)
        self.z_offset = max(self.min_offset, z_size * 1.5)
        
        # Add buffer for safety
        self.xy_offset += self.buffer
        self.z_offset += self.buffer

    def add_probe_boundary(self, boundary_func, is_outer_boundary=False):
        """Add a boundary function that operates in probe space
        Args:
            boundary_func: Function that returns True if position is valid
            is_outer_boundary: If True, this defines the valid workspace limits
        """
        if is_outer_boundary:
            self.outer_boundary = boundary_func
        else:
            self.obstacle_boundaries.append(boundary_func)
            # Calculate obstacle dimensions and clearances when first obstacle is added
            if len(self.obstacle_boundaries) == 1:
                self.find_obstacle_dimensions()
                if self.obstacle_dimensions:
                    self._calculate_clearances()
                    self._calculate_safe_offsets()  # Calculate offsets AFTER we have obstacle dimensions
        
    def add_motor_boundary(self, boundary_func):
        """Add a boundary function that operates in motor space"""
        self.motor_boundaries.append(boundary_func)

    def find_obstacle_dimensions(self):
        """Find obstacle dimensions by sampling points within the valid workspace"""
        if not self.obstacle_boundaries or not self.outer_boundary:
            return None

        # Initialize with extreme values
        x_min, x_max = float('inf'), float('-inf')
        y_min, y_max = float('inf'), float('-inf')
        z_min, z_max = float('inf'), float('-inf')
        
        # Use reasonable sampling - we only need enough points to find the obstacle boundaries
        # For a 2x2x2 box, 20 points per dimension (8000 total points) should be plenty
        x_range = np.linspace(-5, 5, 20)  # Reduced from 200 to 20 points
        y_range = np.linspace(-5, 5, 20)
        z_range = np.linspace(-5, 5, 20)
        
        found_obstacle = False
        # Find points where obstacles exist within valid workspace
        for x in x_range:
            for y in y_range:
                for z in z_range:
                    # First check if point is in valid workspace
                    if not self.outer_boundary(x, y, z):
                        continue
                        
                    # Then check if point is in any obstacle
                    for obstacle in self.obstacle_boundaries:
                        if not obstacle(x, y, z):  # Point is in obstacle
                            x_min = min(x_min, x)
                            x_max = max(x_max, x)
                            y_min = min(y_min, y)
                            y_max = max(y_max, y)
                            z_min = min(z_min, z)
                            z_max = max(z_max, z)
                            found_obstacle = True
                            break
        
        if not found_obstacle:  # No obstacles found
            self._debug_print("Warning: No obstacle points found during dimension calculation")
            self.obstacle_dimensions = None
        else:
            self._debug_print(f"Found obstacle points: x=[{x_min:.2f}, {x_max:.2f}], y=[{y_min:.2f}, {y_max:.2f}], z=[{z_min:.2f}, {z_max:.2f}]")
            # Add a small buffer to the dimensions to account for sampling resolution
            buffer = self.check_resolution
            self.obstacle_dimensions = (
                (x_min - buffer, x_max + buffer),
                (y_min - buffer, y_max + buffer),
                (z_min - buffer, z_max + buffer)
            )

    def _calculate_clearances(self):
        """Calculate clearance for each axis based on obstacle dimensions"""
        if not self.obstacle_dimensions:
            self.axis_clearances = None
            return
            
        (obs_x_min, obs_x_max), (obs_y_min, obs_y_max), (obs_z_min, obs_z_max) = self.obstacle_dimensions
        self.axis_clearances = [
            abs(obs_x_max - obs_x_min) + 2*self.buffer,  # X clearance
            abs(obs_y_max - obs_y_min) + 2*self.buffer,  # Y clearance
            abs(obs_z_max - obs_z_min) + 2*self.buffer   # Z clearance
        ]

    def is_position_valid(self, probe_pos, motor_pos=None):
        """Check if position is valid in both spaces"""
        x, y, z = probe_pos
        
        # First check if position is within valid workspace
        if self.outer_boundary and not self.outer_boundary(x, y, z):
            return False
                
        # Then check if position is in any obstacle
        for obstacle in self.obstacle_boundaries:
            if not obstacle(x, y, z):
                return False
                
        # Check motor space boundaries if motor_pos is provided
        if motor_pos is not None:
            mx, my, mz = motor_pos
            for boundary in self.motor_boundaries:
                if not boundary(mx, my, mz):
                    return False
                
        return True

    def is_path_valid(self, start_pos, end_pos):
        """Check if straight line path between points is valid by checking if the line
        intersects with any obstacle boundaries"""
        x1, y1, z1 = start_pos
        x2, y2, z2 = end_pos
        
        # If start or end point is invalid, path is invalid
        if not self.is_position_valid(start_pos):
            self._debug_print(f"Start position {start_pos} is invalid")
            return False
        if not self.is_position_valid(end_pos):
            self._debug_print(f"End position {end_pos} is invalid")
            return False
            
        # For each obstacle boundary
        for obstacle in self.obstacle_boundaries:
            # For a line segment P(t) = P1 + t(P2-P1), t ∈ [0,1]
            # Check if any point along the line intersects the obstacle
            
            # Get the min/max values for each coordinate where obstacle exists
            dx = x2 - x1
            dy = y2 - y1
            dz = z2 - z1
            
            # Check several points, with more checks if the distance is larger
            distance = np.sqrt(dx*dx + dy*dy + dz*dz)
            num_checks = max(5, int(distance))  # At least 5 checks, more for longer distances
            
            for i in range(num_checks + 1):
                t = i / num_checks
                point = (
                    x1 + t*dx,  # x = x1 + t(x2-x1)
                    y1 + t*dy,  # y = y1 + t(y2-y1)
                    z1 + t*dz   # z = z1 + t(z2-z1)
                )
                
                # If any point along the line is inside the obstacle, path is invalid
                if not obstacle(*point):
                    self._debug_print(f"Path intersects obstacle at point {point} (t={t:.2f})")
                    return False
                    
        return True

    def find_alternative_path(self, start_pos, end_pos, max_attempts=20):
        """Find an alternative path using intermediate points when direct path is blocked."""
        # Debug state at start of pathfinding
        self._debug_print("\nPathfinding Debug:")
        self._debug_print(f"Number of probe boundaries: {len(self.probe_boundaries)}")
        self._debug_print(f"Number of obstacle boundaries: {len(self.obstacle_boundaries)}")
        self._debug_print(f"Outer boundary exists: {self.outer_boundary is not None}")
        self._debug_print(f"Obstacle dimensions: {self.obstacle_dimensions}")
        self._debug_print(f"Current offsets - XY: {self.xy_offset}, Z: {self.z_offset}")
        
        # Quick returns for simple cases
        if not self.obstacle_boundaries:
            self._debug_print("No obstacle boundaries defined")
            return [end_pos]
            
        if self.obstacle_dimensions is None:
            self._debug_print("No obstacle dimensions calculated")
            return [end_pos]
            
        if self.is_path_valid(start_pos, end_pos):
            self._debug_print("Direct path is valid")
            return [end_pos]
            
        x1, y1, z1 = start_pos
        x2, y2, z2 = end_pos
        
        # Calculate direction vector from start to end
        dx = x2 - x1
        dy = y2 - y1
        dz = z2 - z1
        
        # Calculate perpendicular direction in XY plane
        # For a vector (dx, dy), a perpendicular vector is (-dy, dx)
        length = np.sqrt(dx*dx + dy*dy)
        if length > 0:
            perp_x = -dy/length * self.xy_offset
            perp_y = dx/length * self.xy_offset
        else:
            perp_x = self.xy_offset
            perp_y = 0
        
        self._debug_print(f"\nPath vector: ({dx:.2f}, {dy:.2f}, {dz:.2f})")
        self._debug_print(f"Using offsets: XY=({perp_x:.2f}, {perp_y:.2f}), Z={self.z_offset}")
        
        # Try both positive and negative perpendicular directions
        offsets = [
            (perp_x, perp_y, 0),
            (-perp_x, -perp_y, 0),
            (0, 0, self.z_offset),
            (0, 0, -self.z_offset)
        ]
        
        for i, (offset_x, offset_y, offset_z) in enumerate(offsets):
            # Create intermediate point offset from midpoint
            mid_x = (x1 + x2)/2 + offset_x
            mid_y = (y1 + y2)/2 + offset_y
            mid_z = (z1 + z2)/2 + offset_z
            waypoint = (mid_x, mid_y, mid_z)
            
            self._debug_print(f"\nTrying waypoint {i+1}/4: {waypoint}")
            # Check each segment individually for better debugging
            valid_waypoint = self.is_position_valid(waypoint)
            if not valid_waypoint:
                self._debug_print(f"Waypoint {waypoint} is not valid")
                continue
                
            valid_to_waypoint = self.is_path_valid(start_pos, waypoint)
            if not valid_to_waypoint:
                self._debug_print(f"Path to waypoint is not valid")
                continue
                
            valid_from_waypoint = self.is_path_valid(waypoint, end_pos)
            if not valid_from_waypoint:
                self._debug_print(f"Path from waypoint is not valid")
                continue
            
            self._debug_print(f"Valid path found through waypoint: {waypoint}")
            return [waypoint, end_pos]
        
        self._debug_print("\nNo valid path found after trying all offset directions")
        raise ValueError("Could not find valid path between points")

#===============================================================================================================================================
# Test functions
#===============================================================================================================================================
def plot_box(ax, center, size):
    """Helper function to plot a 3D box obstacle"""
    # Create arrays for the vertices
    x = np.array([[-size[0]/2, -size[0]/2, size[0]/2, size[0]/2],
                  [-size[0]/2, -size[0]/2, size[0]/2, size[0]/2],
                  [-size[0]/2, -size[0]/2, size[0]/2, size[0]/2],
                  [-size[0]/2, -size[0]/2, size[0]/2, size[0]/2]])
    y = np.array([[-size[1]/2, size[1]/2, size[1]/2, -size[1]/2],
                  [-size[1]/2, size[1]/2, size[1]/2, -size[1]/2],
                  [-size[1]/2, size[1]/2, size[1]/2, -size[1]/2],
                  [-size[1]/2, size[1]/2, size[1]/2, -size[1]/2]])
    z = np.array([[-size[2]/2, -size[2]/2, -size[2]/2, -size[2]/2],
                  [size[2]/2, size[2]/2, size[2]/2, size[2]/2],
                  [-size[2]/2, -size[2]/2, -size[2]/2, -size[2]/2],
                  [size[2]/2, size[2]/2, size[2]/2, size[2]/2]])

    # Offset by center position
    x = x + center[0]
    y = y + center[1]
    z = z + center[2]

    # Define vertices for each face
    faces = [
        # Bottom face (z-min)
        (np.array([[x[0,0], x[0,1]], [x[0,2], x[0,3]]]),
         np.array([[y[0,0], y[0,1]], [y[0,2], y[0,3]]]),
         np.array([[z[0,0], z[0,1]], [z[0,2], z[0,3]]])),
        # Top face (z-max)
        (np.array([[x[1,0], x[1,1]], [x[1,2], x[1,3]]]),
         np.array([[y[1,0], y[1,1]], [y[1,2], y[1,3]]]),
         np.array([[z[1,0], z[1,1]], [z[1,2], z[1,3]]])),
        # Front face (y-min)
        (np.array([[x[0,0], x[1,0]], [x[0,3], x[1,3]]]),
         np.array([[y[0,0], y[1,0]], [y[0,3], y[1,3]]]),
         np.array([[z[0,0], z[1,0]], [z[0,3], z[1,3]]])),
        # Back face (y-max)
        (np.array([[x[0,1], x[1,1]], [x[0,2], x[1,2]]]),
         np.array([[y[0,1], y[1,1]], [y[0,2], y[1,2]]]),
         np.array([[z[0,1], z[1,1]], [z[0,2], z[1,2]]])),
        # Left face (x-min)
        (np.array([[x[0,0], x[0,1]], [x[1,0], x[1,1]]]),
         np.array([[y[0,0], y[0,1]], [y[1,0], y[1,1]]]),
         np.array([[z[0,0], z[0,1]], [z[1,0], z[1,1]]])),
        # Right face (x-max)
        (np.array([[x[0,2], x[0,3]], [x[1,2], x[1,3]]]),
         np.array([[y[0,2], y[0,3]], [y[1,2], y[1,3]]]),
         np.array([[z[0,2], z[0,3]], [z[1,2], z[1,3]]]))
    ]

    # Plot each face as a solid surface
    for face in faces:
        ax.plot_surface(face[0], face[1], face[2], color='red', alpha=0.8)

def plot_path_3d(ax, waypoints, start_point, end_point):
    """Helper function to plot the path, waypoints, and start/end points"""
    waypoints_array = np.array(waypoints)
    ax.scatter(waypoints_array[:, 0], waypoints_array[:, 1], waypoints_array[:, 2], 
              c='blue', marker='o', s=50, label='Waypoints')
    
    for j in range(len(waypoints)-1):
        p1 = waypoints[j]
        p2 = waypoints[j+1]
        ax.plot([p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]], 
               'g--', label='Path' if j==0 else None, linewidth=2)

    # Add start and end points
    ax.scatter(*start_point, c='green', marker='^', s=100, label='Start')
    ax.scatter(*end_point, c='red', marker='v', s=100, label='End')

def setup_3d_plot(ax, title):
    """Helper function to setup the 3D plot appearance"""
    ax.set_xlabel('X (cm)')
    ax.set_ylabel('Y (cm)')
    ax.set_zlabel('Z (cm)')
    ax.set_title(title)
    ax.legend()
    ax.set_box_aspect([1, 1, 1])
    ax.grid(False)
    ax.view_init(elev=20, azim=45)
    
    # Make background transparent
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False

def test_small_box_obstacle():
    """Test obstacle avoidance with a 2x2x2 box centered at origin"""
    print("\nTesting Small Box (2x2x2)...")
    
    # Create boundary checker instance
    checker = BoundaryChecker(verbose=False)  # Set to True to enable debug prints
    checker.check_resolution = 0.1  # Finer resolution for small obstacle
    checker.min_clearance = 1.0    # Increased minimum clearance
    checker.buffer = 0.5           # Safety buffer
    checker.min_offset = 4.0       # Minimum offset for path finding
    
    # Define boundaries and obstacles
    def outer_boundary(x, y, z):
        return (-40 <= x <= 60 and -30 <= y <= 30 and -7 <= z <= 7)
    
    def small_box_obstacle(x, y, z):
        # Define a 2x2x2 box with buffer
        buffer = 0.5  # Safety buffer
        in_obstacle = (-1-buffer <= x <= 1+buffer and 
                      -1-buffer <= y <= 1+buffer and 
                      -1-buffer <= z <= 1+buffer)
        return not in_obstacle
    
    checker.add_probe_boundary(outer_boundary, is_outer_boundary=True)
    checker.add_probe_boundary(small_box_obstacle)
    
    # Print the calculated obstacle dimensions and offsets
    print(f"Obstacle dimensions: {checker.obstacle_dimensions}")
    print(f"XY offset: {checker.xy_offset}, Z offset: {checker.z_offset}")
    
    # Define test cases that require obstacle avoidance
    test_cases = [
        ((4, 0, 0), (-4, 0, 0), "X-axis path around obstacle"),
        ((4, 4, 0), (-4, -4, 0), "XY diagonal path around obstacle"),
        ((4, 0, 4), (-4, 0, -4), "XZ diagonal path around obstacle"),
        ((4, 4, 4), (-4, -4, -4), "XYZ diagonal path around obstacle")
    ]
    
    # Create visualization
    fig = plt.figure(figsize=(20, 15))
    fig.suptitle("Small Box (2x2x2) Obstacle Avoidance Tests - Valid Paths", fontsize=16)
    
    for i, (start_point, end_point, title) in enumerate(test_cases, 1):
        ax = fig.add_subplot(2, 2, i, projection='3d')
        
        # Plot obstacle - use same size as defined in obstacle function
        plot_box(ax, (0, 0, 0), (3, 3, 3))  # 2 + 2*buffer = 3
        
        print(f"\n{title}:")
        print(f"Start point: {start_point}")
        print(f"End point: {end_point}")
        
        # Always plot start and end points
        ax.scatter(*start_point, c='green', marker='^', s=100, label='Start')
        ax.scatter(*end_point, c='red', marker='v', s=100, label='End')
        
        try:
            # Try to find a path
            path = [start_point] + checker.find_alternative_path(start_point, end_point)
            print("Found path with waypoints:")
            for j, point in enumerate(path):
                print(f"Point {j}: {point}")
            
            # Verify the entire path is valid
            valid_path = True
            for j in range(len(path)-1):
                if not checker.is_path_valid(path[j], path[j+1]):
                    print(f"Warning: Path segment from {path[j]} to {path[j+1]} is invalid!")
                    valid_path = False
                    break
            
            if valid_path:
                # Plot waypoints (excluding start and end points)
                if len(path) > 2:
                    waypoints = path[1:-1]
                    ax.scatter([p[0] for p in waypoints], 
                             [p[1] for p in waypoints], 
                             [p[2] for p in waypoints],
                             c='blue', marker='o', s=50, label='Waypoints')
                
                # Plot path segments
                for j in range(len(path)-1):
                    p1, p2 = path[j], path[j+1]
                    ax.plot([p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]], 
                           'g--', label='Path' if j==0 else None, linewidth=2)
            else:
                print("Path validation failed - not plotting path")
            
        except ValueError as e:
            print(f"Could not find valid path: {str(e)}")
        
        # Setup plot appearance
        setup_3d_plot(ax, title)
        ax.set_xlim(-10, 10)  # Increased view range
        ax.set_ylim(-10, 10)
        ax.set_zlim(-10, 10)
    
    plt.tight_layout()
    plt.show()

def test_large_box_obstacle():
    """Test obstacle avoidance with a 30x6x11 cm box positioned from x=-50 to -20"""
    print("\nTesting Large Box (30x6x11 cm)...")
    
    # Create boundary checker instance
    checker = BoundaryChecker(verbose=False)  # Set to True to enable debug prints
    
    # Define boundaries and obstacles
    def outer_boundary(x, y, z):
        return (-60 <= x <= 60 and -30 <= y <= 30 and -7 <= z <= 7)
    
    def large_box_obstacle(x, y, z):
        # Add a small buffer to ensure paths don't get too close to the obstacle
        buffer = 0.2
        return (-50-buffer <= x <= -20+buffer and 
                -3-buffer <= y <= 3+buffer and 
                -5.5-buffer <= z <= 5.5+buffer)
    
    checker.add_probe_boundary(outer_boundary)
    checker.add_motor_boundary(large_box_obstacle)
    checker.check_resolution = 0.2  # Slightly coarser resolution for large obstacle
    checker.min_clearance = 1.0    # Larger minimum clearance for bigger obstacle
    
    # Define test cases with realistic probe positions (probe enters from x=+50)
    test_cases = [
        ((-25, +10, 0), (-25, -10, 0)),
        ((-25, 0, 7), (-25, 0, -7)),
        ((-20, 1, 7), (-20, -1, -7)),
        ((0, 0, 0), (-25, 6, 0))
    ]
    
    # Create figure
    fig = plt.figure(figsize=(20, 15))
    fig.suptitle("Large Box (30x6x11 cm) Obstacle Avoidance Tests", fontsize=16)
    
    # Run test cases
    for i, (start_point, end_point) in enumerate(test_cases, 1):
        title = f"Path {i}"
        print(f"\n{title}...")
        print(f"Start point: {start_point}")
        print(f"End point: {end_point}")
        
        # Create subplot
        ax = fig.add_subplot(2, 2, i, projection='3d')
        
        # Plot obstacle - centered at x=-35 (midpoint between -50 and -20)
        plot_box(ax, (-35, 0, 0), (30, 6, 11))
        
        # Find and plot path
        try:
            waypoints = [start_point] + checker.find_alternative_path(start_point, end_point)
            print("Found path with waypoints:")
            for j, point in enumerate(waypoints):
                print(f"Point {j}: {point}")
            plot_path_3d(ax, waypoints, start_point, end_point)
        except ValueError as e:
            print(f"Error finding path: {str(e)}")
        
        # Setup plot appearance
        setup_3d_plot(ax, title)
        ax.set_xlim(-60, 10)  # Adjusted to show more of the approach path
        ax.set_ylim(-10, 10)
        ax.set_zlim(-7, 7)
    
    plt.tight_layout()
    plt.show()

if __name__ == '__main__':
    # Run both tests
    test_small_box_obstacle()
    # test_large_box_obstacle() 