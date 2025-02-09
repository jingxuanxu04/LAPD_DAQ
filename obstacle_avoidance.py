import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

#===============================================================================================================================================
#===============================================================================================================================================

class BoundaryChecker:
    def __init__(self):
        self.probe_boundaries = []
        self.outer_boundary = None  # Function defining the valid workspace
        self.obstacle_boundaries = []  # Functions defining obstacles
        self.motor_boundaries = []
        self.check_resolution = 0.1
        self.min_clearance = 1.0
        self.buffer = 0.5  # Safety buffer for clearance
        self.obstacle_dimensions = None  # Will store (x_min, x_max), (y_min, y_max), (z_min, z_max)
        self.axis_clearances = None  # Will store [x_clearance, y_clearance, z_clearance]
        
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
        
        # Sample points in a reasonable range
        x_range = np.linspace(-60, 60, 100)  # Adjust range based on your workspace
        y_range = np.linspace(-30, 30, 100)
        z_range = np.linspace(-15, 15, 100)
        
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
                            break
        
        if x_min == float('inf'):  # No obstacles found
            self.obstacle_dimensions = None
        else:
            self.obstacle_dimensions = (
                (x_min, x_max),
                (y_min, y_max),
                (z_min, z_max)
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
        """Check if straight line path between points is valid"""
        x1, y1, z1 = start_pos
        x2, y2, z2 = end_pos
        
        # Calculate path vector and length
        path_vector = np.array([x2-x1, y2-y1, z2-z1])
        path_length = np.linalg.norm(path_vector)
        
        # Number of points to check along path
        num_points = max(int(path_length / self.check_resolution), 10)  # At least 10 points
        
        # Check points along path
        for i in range(num_points + 1):
            t = i / num_points
            point = np.array([x1, y1, z1]) + t * path_vector
            if not self.is_position_valid(tuple(point)):
                return False
                
        return True

    def find_alternative_path(self, start_pos, end_pos, max_attempts=20):
        """Find an alternative path using intermediate points when direct path is blocked"""
        # Quick returns for simple cases
        if not self.probe_boundaries or self.obstacle_dimensions is None:
            return [end_pos]
            
        if self.is_path_valid(start_pos, end_pos):
            return [end_pos]
            
        x1, y1, z1 = start_pos
        x2, y2, z2 = end_pos
            
        # Function to generate waypoints for a given direction
        def get_waypoints_for_direction(axis, direction):
            # Use pre-calculated clearance
            offset = self.axis_clearances[axis] * direction
            
            # Base waypoint with only the offset applied
            waypoint = list(start_pos)
            waypoint[axis] += offset
            
            # Generate path based on axis
            if axis == 0:  # X axis
                return [
                    tuple(waypoint),                    # Move in X
                    (waypoint[0], y2, z1),             # Move in Y
                    (waypoint[0], y2, z2),             # Move in Z
                    end_pos                            # Final position
                ]
            elif axis == 1:  # Y axis
                return [
                    tuple(waypoint),                    # Move in Y
                    (x1, waypoint[1], z2),             # Move in Z
                    (x2, waypoint[1], z2),             # Move in X
                    end_pos                            # Final position
                ]
            else:  # Z axis
                return [
                    tuple(waypoint),                    # Move in Z
                    (x2, y1, waypoint[2]),             # Move in X
                    (x2, y2, waypoint[2]),             # Move in Y
                    end_pos                            # Final position
                ]

        # Try each axis in order of priority (Y, X, Z)
        axes_to_try = [(1, 1), (1, -1), (0, 1), (0, -1), (2, 1), (2, -1)]
        
        # Try each direction systematically
        for axis, direction in axes_to_try:
            waypoints = get_waypoints_for_direction(axis, direction)
            
            # Validate entire path
            valid = True
            prev_point = start_pos
            for point in waypoints:
                if not self.is_path_valid(prev_point, point):
                    valid = False
                    break
                prev_point = point
                
            if valid:
                return waypoints
                
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
    checker = BoundaryChecker()
    
    # Define boundaries and obstacles
    def outer_boundary(x, y, z):
        return (-40 <= x <= 60 and -30 <= y <= 30 and -7 <= z <= 7)
    
    def small_box_obstacle(x, y, z):
        # Add a small buffer to ensure paths don't get too close to the obstacle
        buffer = 0.2
        return (-1-buffer <= x <= 1+buffer and 
                -1-buffer <= y <= 1+buffer and 
                -1-buffer <= z <= 1+buffer)
    
    checker.add_probe_boundary(outer_boundary)
    checker.add_motor_boundary(small_box_obstacle)
    checker.check_resolution = 0.1  # Finer resolution for small obstacle
    checker.min_clearance = 0.5    # Minimum clearance from obstacles
    
    # Define test cases
    test_cases = [
        ((-2, 0, 0), (2, 0, 0), "Straight through"),
        ((-2, -2, 0), (2, 2, 0), "Diagonal across"),
        ((0, -2, 0), (0, 2, 0), "Along Y-axis"),
        ((0, 0, -2), (0, 0, 2), "Along Z-axis")
    ]
    
    # Create figure
    fig = plt.figure(figsize=(20, 15))
    fig.suptitle("Small Box (2x2x2) Obstacle Avoidance Tests", fontsize=16)
    
    # Run test cases
    for i, (start_point, end_point, title) in enumerate(test_cases, 1):
        print(f"\n{title}...")
        print(f"Start point: {start_point}")
        print(f"End point: {end_point}")
        
        # Create subplot
        ax = fig.add_subplot(2, 2, i, projection='3d')
        
        # Plot obstacle
        plot_box(ax, (0, 0, 0), (2, 2, 2))
        
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
        ax.set_xlim(-3, 3)
        ax.set_ylim(-3, 3)
        ax.set_zlim(-3, 3)
    
    plt.tight_layout()
    plt.show()

def test_large_box_obstacle():
    """Test obstacle avoidance with a 30x6x11 cm box positioned from x=-50 to -20"""
    print("\nTesting Large Box (30x6x11 cm)...")
    
    # Create boundary checker instance
    checker = BoundaryChecker()
    
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
    # test_small_box_obstacle()
    test_large_box_obstacle() 