import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

#===============================================================================================================================================
#===============================================================================================================================================

class BoundaryChecker:
    def __init__(self):
        self.probe_boundaries = []
        self.motor_boundaries = []
        self.check_resolution = 0.1
        self.min_clearance = 1.0
        
    def add_probe_boundary(self, boundary_func):
        """Add a boundary function that operates in probe space"""
        self.probe_boundaries.append(boundary_func)
        
    def add_motor_boundary(self, boundary_func):
        """Add a boundary function that operates in motor space"""
        self.motor_boundaries.append(boundary_func)
    
    def is_position_valid(self, probe_pos, motor_pos=None):
        """Check if position is valid in both spaces
        Args:
            probe_pos: (x, y, z) tuple in probe coordinates
            motor_pos: Optional (x, y, z) tuple in motor coordinates. 
                      If None, only probe boundaries are checked.
        """
        # Check probe space boundaries
        x, y, z = probe_pos
        for boundary in self.probe_boundaries:
            if not boundary(x, y, z):
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
        if self.is_path_valid(start_pos, end_pos):
            return [end_pos]
            
        x1, y1, z1 = start_pos
        x2, y2, z2 = end_pos
        
        # Calculate path vector and properties
        path_vector = np.array([x2-x1, y2-y1, z2-z1])
        path_length = np.linalg.norm(path_vector)
        
        # Determine primary movement direction
        direction_magnitudes = np.abs(path_vector)
        primary_axis = np.argmax(direction_magnitudes)
        
        # For movements near obstacles, use larger step sizes
        x_step = 10.0  # Step size in X direction (away from obstacle)
        y_step = 5.0   # Step size in Y direction
        z_step = 5.0   # Step size in Z direction
        
        # Special handling for parallel movements near obstacles
        if abs(x2 - x1) < 0.1:  # Moving parallel to obstacle
            # Try stepping out in X direction (away from obstacle)
            if x1 < -30:  # We're on the negative X side
                x_offset = x_step  # Step towards positive X
            else:
                x_offset = -x_step  # Step towards negative X
                
            # First try: step out in X, move, step back
            mid_points = [
                (x1 + x_offset, y1, z1),  # Step out in X
                (x1 + x_offset, y2, z2),  # Move to target Y,Z
                (x2, y2, z2)              # Return to target X
            ]
            
            if all(self.is_path_valid(p1, p2) for p1, p2 in zip(mid_points[:-1], mid_points[1:])):
                return mid_points[1:]
                
            # Second try: step out in X and up in Z, move, step back
            mid_points = [
                (x1 + x_offset, y1, z1 + z_step),  # Step out and up
                (x1 + x_offset, y2, z1 + z_step),  # Move in Y while offset
                (x1 + x_offset, y2, z2),           # Move to target Z
                (x2, y2, z2)                       # Return to target X
            ]
            
            if all(self.is_path_valid(p1, p2) for p1, p2 in zip(mid_points[:-1], mid_points[1:])):
                return mid_points[1:]
                
            # Third try: larger step out in X
            mid_points = [
                (x1 + 2*x_offset, y1, z1),  # Step out further in X
                (x1 + 2*x_offset, y2, z2),  # Move to target Y,Z
                (x2, y2, z2)                # Return to target X
            ]
            
            if all(self.is_path_valid(p1, p2) for p1, p2 in zip(mid_points[:-1], mid_points[1:])):
                return mid_points[1:]
        
        # If special handling didn't work, try standard strategies
        clearance = max(path_length * 0.3, self.min_clearance * 3)
        strategies = []
        
        # Basic offset strategies
        offsets = [
            (x_step, 0, 0),
            (-x_step, 0, 0),
            (0, 0, z_step),
            (0, 0, -z_step)
        ]
        
        # Add two-point and three-point strategies
        for offset in offsets:
            # Two-point strategy
            strategies.append([
                (x1 + offset[0], y1 + offset[1], z1 + offset[2]),
                (x2 + offset[0], y2 + offset[1], z2 + offset[2]),
                (x2, y2, z2)
            ])
            
            # Three-point strategy with midpoint
            strategies.append([
                (x1 + offset[0], y1 + offset[1], z1 + offset[2]),
                ((x1 + x2)/2 + offset[0], (y1 + y2)/2 + offset[1], (z1 + z2)/2 + offset[2]),
                (x2 + offset[0], y2 + offset[1], z2 + offset[2]),
                (x2, y2, z2)
            ])
        
        # Try each strategy
        for waypoints in strategies:
            valid = True
            prev_point = start_pos
            
            for point in waypoints:
                if not self.is_path_valid(prev_point, point):
                    valid = False
                    break
                prev_point = point
                
            if valid:
                return waypoints
        
        # If no strategy works, try random intermediate points with bias
        for _ in range(max_attempts):
            # Generate random intermediate point with bias towards successful directions
            rand_offset = np.random.uniform(-1, 1, 3) * np.array([x_step, y_step/2, z_step])
            mid_point = np.array([x1, y1, z1]) + path_vector * 0.5 + rand_offset
            
            # Check if path through this point is valid
            if (self.is_path_valid(start_pos, tuple(mid_point)) and 
                self.is_path_valid(tuple(mid_point), end_pos)):
                return [tuple(mid_point), end_pos]
                
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