'''
Client interface for communicating with the GPIO trigger server on Raspberry Pi.

This module provides a TriggerClient class for network communication with the Pi server,
plus utility functions for motor control operations. The client can:
- Send trigger commands to the Pi
- Wait for trigger responses from the Pi  
- Run GPIO input/output tests
- Control motor sequences with trigger synchronization

Usage:
    client = TriggerClient()
    client.send_trigger()
    client.wait_for_trigger(timeout=5)
'''

import socket
import time
import select

# Configuration variables - modify these to match your setup
PI_HOST = '127.0.0.1'      # Pi server IP address
PI_PORT = 54321            # Pi server port (must match pi_server.py)
MOTOR_IP = '192.168.7.38'  # Motor controller IP address
BUFFER_SIZE = 1024         # Socket buffer size

class TriggerClient:
    """
    Client for communicating with the GPIO trigger server on Raspberry Pi.
    
    Provides methods to send commands to the Pi server and receive responses.
    Handles connection management, retries, and error handling automatically.
    
    Attributes:
        host (str): Pi server IP address
        port (int): Pi server port number
        BUF_SIZE (int): Socket buffer size for receiving data
    """
    def __init__(self, host=PI_HOST, port=PI_PORT):
        self.host = host
        self.port = port
        self.BUF_SIZE = BUFFER_SIZE
        
    def send_command(self, command, receive=True, retries=3):
        """
        Send command to Pi with error handling and retries.
        
        Creates a new socket connection for each command and closes it afterward.
        This ensures no persistent connections are maintained, improving reliability
        for long-running operations.
        
        Args:
            command (str): Command to send to Pi server
            receive (bool): Whether to wait for and return response
            retries (int): Number of retry attempts on failure
            
        Returns:
            str or None: Server response if receive=True, None otherwise
        """
        for attempt in range(retries):
            s = None
            try:
                # Create socket
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                
                # Connect
                s.connect((self.host, self.port))
                
                # Send command
                message = f"{command}\n"
                s.send(message.encode('ascii'))
                
                if receive:
                    # Wait for response with select
                    readable, _, _ = select.select([s], [], [], 5.0)
                    if readable:
                        data = s.recv(self.BUF_SIZE)
                        return data.decode('ascii').strip()
                    else:
                        raise TimeoutError("No response from server")
                        
                return None
                
            except TimeoutError:
                if attempt == retries - 1:
                    raise TimeoutError(f"Connection timed out after {retries} attempts")
                time.sleep(0.5)
            except ConnectionRefusedError:
                if attempt == retries - 1:
                    raise ConnectionRefusedError(f"Connection refused by {self.host}:{self.port}")
                time.sleep(0.5)
            except Exception as e:
                if attempt == retries - 1:
                    raise Exception(f"Failed to communicate with Pi: {str(e)}")
                time.sleep(0.5)
            finally:
                if s:
                    s.close()
        
        return None
        
    def send_trigger(self):
        """Send trigger command"""
        response = self.send_command('TRIG')
        if response != 'OK':
            raise RuntimeError(f"Unexpected trigger response: {response}")
        return True
    
    def wait_for_trigger(self, timeout=5):
        """
        Wait for trigger detection from Pi server.
        timeout (float): Maximum time to wait in seconds
        Returns True if trigger received, False if timeout
        Raises RuntimeError If server response is unexpected
        """
        response = self.send_command(f'WAIT_TRIG {timeout}')
        if response == 'TRIGGERED':
            return True
        elif response == 'NO_TRIGGER':
            return False
        else:
            raise RuntimeError(f"Unexpected response: {response}")
        
    def get_status(self):
        """
        Get server status and verify connection.
        Returns True if server is ready.
        Raises RuntimeError If server is not ready or unreachable.
        """
        response = self.send_command('STATUS')
        if response != 'READY':
            raise RuntimeError(f"Server not ready: {response}")
        return True

    def trigger_loop(self, operation_func=None, iterations=1000, delay=0.1, timeout=120):
        """Run a loop sending triggers and executing operations
        
        Args:
            operation_func: Function to call between triggers
            iterations: Number of trigger cycles to run
            delay: Delay between triggers in seconds
            timeout: Maximum time to wait for each trigger in seconds
            
        Returns:
            int: Number of completed iterations
        """
        completed = 0
        
        for i in range(iterations):
            try:
                # Send trigger
                self.send_trigger()
                
                # Wait for trigger response
                if not self.wait_for_trigger(timeout=timeout):
                    print(f"\nFailed to receive trigger {i+1}")
                    continue
                    
                # Run custom operation if provided
                if operation_func:
                    operation_func(i)
                    
                completed += 1
                time.sleep(delay)
                
            except Exception as e:
                print(f"\nError in trigger loop: {e}")
                break
                
        return completed

    def test_gpio_input(self, pin, iterations=5, delay=0.1):
        """
        Test GPIO input detection on specified pin
        Args:
            pin (int): GPIO pin number to test for input
            iterations (int): Number of detection cycles to run (default: 5)
            delay (float): Delay between attempts in seconds (default: 0.1)
        Returns:
            bool: True if all signals were detected, False otherwise
        """
        response = self.send_command(f'TEST_INPUT {pin} {iterations} {delay}')
        if response == 'TEST_PASS':
            return True
        elif response == 'TEST_FAIL':
            return False
        else:
            raise RuntimeError(f"Unexpected test response: {response}")

    def test_gpio_output(self, pin, iterations=5, delay=0.1):
        """
        Test GPIO output triggering on specified pin
        Args:
            pin (int): GPIO pin number to test for output
            iterations (int): Number of trigger cycles to run (default: 5)
            delay (float): Delay between triggers in seconds (default: 0.1)
        Returns:
            bool: True if all triggers were sent successfully, False otherwise
        """
        response = self.send_command(f'TEST_OUTPUT {pin} {iterations} {delay}')
        if response == 'TEST_PASS':
            return True
        elif response == 'TEST_FAIL':
            return False
        else:
            raise RuntimeError(f"Unexpected test response: {response}")

def run_tungsten_drop_sequence(motor_ip, client, num_drops=5, max_balls=700, timeout=15):
    """
    Run tungsten ball dropping sequence with GPIO trigger synchronization.
    
    This function integrates motor control with the GPIO trigger system:
    1. Moves motor to drop position
    2. Sends trigger pulse via Pi server
    3. Waits for trigger detection confirmation
    4. Repeats for specified number of drops
    
    Args:
        motor_ip (str): IP address of the motor controller
        client (TriggerClient): Initialized client for Pi communication
        num_drops (int): Number of drops to perform
        max_balls (int): Maximum number of balls before stopping
        timeout (float): Timeout for trigger detection (seconds)
        
    Returns:
        int: Number of successful drops completed
    """
    from Motor_Control_1D import Motor_Control

    print(f"Starting tungsten drop sequence: {num_drops} drops")
    print(f"Motor IP: {motor_ip}")
    print(f"Max balls limit: {max_balls}")
    print(f"Trigger timeout: {timeout}s")
    
    try:
        # Initialize motor control
        mc_w = Motor_Control(server_ip_addr=motor_ip, stop_switched=False, name="w_dropper")
        spt = mc_w.steps_per_rev()
        one_drop = int(spt/12) + 1
        
        completed_drops = 0
        
        for i in range(num_drops):
            try:
                # Check current position and ball count
                cur_step = mc_w.current_step()
                ball_count = int(cur_step/one_drop)
                print(f"\nDrop {i+1}/{num_drops} - Ball count: {ball_count}")
                
                # Check if we've reached the ball limit
                if ball_count >= max_balls:
                    print(f'Ball limit reached ({max_balls}). Stopping sequence.')
                    break
                
                # Move motor to drop position
                print("Moving motor to drop position... ", end='')
                mc_w.turn_to(cur_step + one_drop)
                print("done")
                
                # Send trigger to server
                print("Sending trigger... ", end='')
                client.send_trigger()
                print(f"sent at {time.strftime('%H:%M:%S', time.localtime())}")
                
                # Wait for trigger detection
                print("Waiting for trigger detection... ", end='')
                if client.wait_for_trigger(timeout=timeout):
                    print(f"detected at {time.strftime('%H:%M:%S', time.localtime())}")
                    completed_drops += 1
                    time.sleep(0.5)  # Brief pause after successful trigger
                else:
                    print("TIMEOUT - No trigger detected")
                    print("Check trigger connections and try again")
                    break
                
                # Verify motor moved correctly
                if mc_w.current_step() == cur_step:
                    print('ERROR: Motor position did not change after drop command')
                    print('Check motor operation before continuing')
                    break
                
                # Delay between drops
                time.sleep(1)
                
            except Exception as e:
                print(f"Error during drop {i+1}: {e}")
                break
        
        print(f"\nSequence completed: {completed_drops}/{num_drops} successful drops")
        return completed_drops
        
    except Exception as e:
        print(f"Failed to initialize motor control: {e}")
        return 0

#===============================================================================================================================================
#<o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o>
#===============================================================================================================================================
def test():
    """
    Test mode: Runs a trigger loop test with the Pi server.
    
    This demonstrates basic client functionality by:
    1. Connecting to the Pi server
    2. Running a loop that sends triggers and waits for responses
    3. Executing a custom operation between each trigger cycle
    
    Useful for testing the GPIO trigger system end-to-end.
    """
    
    # Example custom operation function
    def custom_operation(iteration):
        """Example operation between triggers - simulates work being done"""
        time.sleep(0.05)  # Simulate some processing work
        
    # Initialize client with configured server settings
    client = TriggerClient(PI_HOST, PI_PORT)
    
    try:
        # Test connection to Pi server
        print(f"Connecting to GPIO trigger server at {PI_HOST}:{PI_PORT}")
        client.get_status()  # Will raise error if server not ready
        print("✓ Server connection established")
        
        # Run trigger loop test with custom operation
        print("\nStarting trigger loop test...")
        print("Press Ctrl+C to stop early")
        completed = client.trigger_loop(
            operation_func=custom_operation,
            iterations=1000,      # Run 1000 trigger cycles
            delay=0.1,           # 100ms delay between cycles
            timeout=120          # 2 minute timeout per trigger
        )
        print(f"\nTest completed: {completed} iterations successful")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nError: {str(e)}")

def main(): # Main tungsten drop sequence operation.

    client = TriggerClient(PI_HOST, PI_PORT) # Connect to Pi server
    
    try:
        print(f"Testing connection to GPIO trigger server at {PI_HOST}:{PI_PORT}")
        client.get_status()  # Will raise error if server not ready
        print("✓ Server connection established")
        
        print("\nStarting tungsten drop sequence...")
        print("Press Ctrl+C to stop early")
        
        completed = run_tungsten_drop_sequence(
            motor_ip=MOTOR_IP,
            client=client,
            num_drops=10,        # Number of drops to perform
            max_balls=700,       # Maximum ball count before stopping
            timeout=15           # Timeout per trigger detection
        )
        
        print(f"\nSequence completed: {completed} drops successful")
        
    except KeyboardInterrupt:
        print("\nSequence interrupted by user")
    except Exception as e:
        print(f"\nError: {str(e)}")

if __name__ == '__main__':

    test()

    # main()
