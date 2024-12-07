'''
Client interface for communicating with the trigger server on Raspberry Pi
'''

import socket
import time
import select

class TriggerClient:
    def __init__(self, host, port=5000):
        self.host = host
        self.port = port
        self.BUF_SIZE = 1024
        
    def send_command(self, command, receive=True, retries=3):
        """Send command to Pi with error handling and retries"""
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
        Wait for trigger from Pi
        
        Args:
            timeout (float): Maximum time to wait in seconds
            
        Returns:
            bool: True if trigger received, False if timeout
        """
        response = self.send_command(f'WAIT_TRIG {timeout}')
        if response == 'TRIGGERED':
            return True
        elif response == 'NO_TRIGGER':
            return False
        else:
            raise RuntimeError(f"Unexpected response: {response}")
        
    def get_status(self):
        """Get server status"""
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

#===============================================================================================================================================
#<o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o>
#===============================================================================================================================================
if __name__ == '__main__':
    # Example custom operation function
    def custom_operation(iteration):
        """Example operation between triggers"""
        time.sleep(0.05)  # Simulate some work
        
    # Initialize client
    client = TriggerClient('192.168.7.38')  # Use server's default IP
    
    try:
        # Test connection
        client.get_status()  # Will raise error if not ready
        print("Server ready")
        
        # Run trigger loop with custom operation
        completed = client.trigger_loop(
            operation_func=custom_operation,
            iterations=1000,
            delay=0.1,
            timeout=120
        )
        print(f"\nCompleted {completed} iterations")
        
    except KeyboardInterrupt:
        print("\nOperation interrupted by user")
    except Exception as e:
        print(f"\nError: {str(e)}")