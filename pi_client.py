'''
Main data acquisition script for tungsten dropper
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
                        return_text = data.decode('ascii').strip()
                        s.close()
                        return return_text
                    else:
                        s.close()
                        raise TimeoutError("No response from server")
                        
                s.close()
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
                if 's' in locals():
                    s.close()
        
        return None
        
    def send_trigger(self):
        """Send trigger command"""
        response = self.send_command('TRIG')
        if response != 'OK':
            raise RuntimeError(f"Unexpected trigger response: {response}")
        return True
    
    def wait_for_trigger(self, timeout=5, sleep_interval=0.1):
        """
        Wait for trigger from Pi
        
        Args:
            timeout (float): Maximum time to wait in seconds
            sleep_interval (float): Time between checks in seconds
            
        Returns:
            bool: True if trigger received, False if timeout
        """
        start_time = time.time()
        timeout_time = start_time + timeout
        print_interval = 3  # seconds
        next_print_time = start_time + print_interval
        
        while time.time() < timeout_time:
            try:
                response = self.send_command('WAIT_TRIG')
                if response == 'TRIGGERED':
                    return True
                    
                # Print progress dots
                if time.time() > next_print_time:
                    next_print_time += print_interval
                    print('.', end='', flush=True)
                    
                time.sleep(sleep_interval)
                
            except Exception as e:
                print(f"\nError while waiting for trigger: {e}")
                return False
                
        print("\nTimeout while waiting for trigger")
        return False
        
    def get_status(self):
        """Get server status"""
        response = self.send_command('STATUS')
        if response != 'READY':
            raise RuntimeError(f"Server not ready: {response}")
        return True
        
    def run_test(self):
        """Run server self-test"""
        response = self.send_command('TEST')
        if response == 'TEST_PASS':
            return True
        elif response == 'TEST_FAIL':
            return False
        else:
            raise RuntimeError(f"Unexpected test response: {response}")       
            
    def trigger_loop(self, operation_func=None, iterations=1000, delay=0.1, timeout=120):
        """Run a loop sending triggers and executing operations
        
        Args:
            operation_func: Function to call between triggers
            iterations: Number of trigger cycles to run
            delay: Delay between triggers in seconds
            timeout: Maximum time to wait for each trigger in seconds
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

#===============================================================================================================================================
#<o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o>
#===============================================================================================================================================
if __name__ == '__main__':
    # Example custom operation function
    def custom_operation(iteration):
        """Example operation between triggers"""
        # Add your custom operations here
        time.sleep(0.05)  # Simulate some work
        
    # Initialize client
    client = TriggerClient('192.168.1.100')  # Replace with your Pi's IP
    
    try:
        # Test connection
        response = client.send_command('STATUS')
        print(f"Pi status: {response}")
        
        # Run trigger loop with custom operation
        client.trigger_loop(
            operation_func=custom_operation,
            iterations=1000,
            delay=0.1,
            timeout=120
        )
        
    except KeyboardInterrupt:
        print("\nOperation interrupted by user")
    except Exception as e:
        print(f"\nError: {str(e)}")