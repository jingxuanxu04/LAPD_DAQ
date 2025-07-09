'''
Setup a simple TCP server to send trigger pulses when requested
Runs on Raspberry Pi
'''

import socket
import time
import signal
import sys
import argparse
import ctypes
import os.path

IP_ADDR = '192.168.7.38'
PORT = 5000

class TriggerServer:
    '''
    Trigger server class that manages GPIO pins and network communication for sending trigger pulses.

    This class sets up a TCP server that listens for trigger requests and controls GPIO pins on a Raspberry Pi.
    It uses a C library (gpio_detect.so) for low-level GPIO control.

    Attributes:
        host (str): IP address to bind the server to
        port (int): Port number to listen on
        trig_out_pin (int): GPIO pin number for trigger output
        trig_in_pin (int): GPIO pin number for trigger input detection
        running (bool): Server run state
        gpio_lib: Loaded C library for GPIO control
        sock: TCP socket for network communication

    Example:
        server = TriggerServer(host='192.168.1.100', port=5000, 
                             trig_out_pin=25, trig_in_pin=27)
        server.start()  # Starts listening for trigger requests
    '''
    def __init__(self, trig_out_pin, trig_in_pin, host=IP_ADDR, port=PORT):
        self.host = host
        self.port = port
        self.trig_out_pin = trig_out_pin
        self.trig_in_pin = trig_in_pin
        self.running = True
        
        # Check if GPIO library exists
        gpio_lib_path = "/home/generalpi/pi_gpio/gpio_detect.so"
        if not os.path.exists(gpio_lib_path):
            raise FileNotFoundError(f"GPIO library not found at {gpio_lib_path}")
            
        try:
            # Load the GPIO C library
            self.gpio_lib = ctypes.CDLL(gpio_lib_path)
        except OSError as e:
            raise RuntimeError(f"Failed to load GPIO library: {str(e)}")
            
        self._setup_gpio_functions()
        
        try:
            # Initialize GPIO
            if self.gpio_lib.initialize_pigpio() < 0:
                raise RuntimeError("Failed to initialize pigpio")
                
            # Setup pins
            if self.gpio_lib.setup_gpio_output_pin(self.trig_out_pin) < 0:
                raise RuntimeError(f"Failed to setup output pin {self.trig_out_pin}")
            if self.gpio_lib.setup_gpio_pin(self.trig_in_pin) < 0:
                raise RuntimeError(f"Failed to setup input pin {self.trig_in_pin}")
            
            # Setup socket
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.sock.bind((self.host, self.port))
            except socket.error as e:
                raise RuntimeError(f"Socket error: {str(e)}")
                
            # Setup signal handlers
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
            
        except Exception as e:
            # Clean up if initialization fails
            if hasattr(self, 'gpio_lib'):
                self.gpio_lib.terminate_pigpio()
            if hasattr(self, 'sock'):
                self.sock.close()
            raise
    
    def _setup_gpio_functions(self):
        """Setup C function signatures"""
        try:
            # Initialize and cleanup
            self.gpio_lib.initialize_pigpio.restype = ctypes.c_int
            self.gpio_lib.terminate_pigpio.restype = None
            
            # Pin setup
            self.gpio_lib.setup_gpio_pin.argtypes = [ctypes.c_int]
            self.gpio_lib.setup_gpio_pin.restype = ctypes.c_int
            self.gpio_lib.setup_gpio_output_pin.argtypes = [ctypes.c_int]
            self.gpio_lib.setup_gpio_output_pin.restype = ctypes.c_int
            
            # GPIO operations
            self.gpio_lib.wait_for_gpio_high.argtypes = [ctypes.c_int, ctypes.c_int]
            self.gpio_lib.wait_for_gpio_high.restype = ctypes.c_bool
            self.gpio_lib.send_gpio_pulse.argtypes = [ctypes.c_int]
            self.gpio_lib.send_gpio_pulse.restype = None
        except AttributeError as e:
            raise RuntimeError(f"Failed to setup GPIO functions: {str(e)}")
    
    def send_trigger(self):
        """Send a trigger pulse using C function"""
        try:
            self.gpio_lib.send_gpio_pulse(self.trig_out_pin)
        except Exception as e:
            raise RuntimeError(f"Failed to send trigger: {str(e)}")

    
    def wait_for_trigger(self, timeout=1):
        """Wait for rising edge using C function"""
        try:
            return self.gpio_lib.wait_for_gpio_high(self.trig_in_pin, int(timeout * 1000000))  # Convert to microseconds
        except Exception as e:
            raise RuntimeError(f"Failed to wait for trigger: {str(e)}")
    
    def handle_command(self, command):
        if not command:
            return 'ERR EMPTY_COMMAND'
            
        try:
            cmd_parts = command.upper().split()
            cmd = cmd_parts[0]
            
            if cmd == 'TRIG':
                self.send_trigger()
                return 'OK'
            elif cmd == 'STATUS':
                return 'READY'
            elif cmd == 'TEST_INPUT':
                # Parse test parameters
                if len(cmd_parts) < 2:
                    return 'ERR MISSING_PIN'
                try:
                    pin = int(cmd_parts[1])
                    iterations = int(cmd_parts[2]) if len(cmd_parts) > 2 else 5
                    delay = float(cmd_parts[3]) if len(cmd_parts) > 3 else 0.1
                except ValueError:
                    return 'ERR INVALID_PARAMETERS'
                    
                success = self.test_gpio_input(pin, iterations, delay)
                return 'TEST_PASS' if success else 'TEST_FAIL'
                
            elif cmd == 'TEST_OUTPUT':
                # Parse test parameters
                if len(cmd_parts) < 2:
                    return 'ERR MISSING_PIN'
                try:
                    pin = int(cmd_parts[1])
                    iterations = int(cmd_parts[2]) if len(cmd_parts) > 2 else 5
                    delay = float(cmd_parts[3]) if len(cmd_parts) > 3 else 0.1
                except ValueError:
                    return 'ERR INVALID_PARAMETERS'
                    
                success = self.test_gpio_output(pin, iterations, delay)
                return 'TEST_PASS' if success else 'TEST_FAIL'
                
            elif cmd == 'WAIT_TRIG':
                try:
                    timeout = float(cmd_parts[1]) if len(cmd_parts) > 1 else 1.0
                except ValueError:
                    return 'ERR INVALID_TIMEOUT'
                    
                if self.wait_for_trigger(timeout=timeout):
                    return 'TRIGGERED'
                return 'NO_TRIGGER'
                
            return 'ERR UNKNOWN_CMD'
            
        except Exception as e:
            return f'ERR {str(e)}'
    
    def test_gpio_input(self, pin, iterations=10, delay=0.1):
        """
        Test GPIO input detection on specified pin.
        
        This test verifies the GPIO input detection by:
        1. Waiting for signal on the specified input pin
        2. Reporting detection success/failure
        3. Repeating for specified iterations
        
        Args:
            pin (int): GPIO pin number to test for input
            iterations (int): Number of detection cycles to run (default: 10)
            delay (float): Delay between attempts in seconds (default: 0.1)
                - Should account for external signal timing
        
        Returns:
            bool: True if all signals were detected, False otherwise
        """
        print(f"\nStarting GPIO input test:")
        print(f"Input Pin: {pin}")
        print(f"Iterations: {iterations}")
        print(f"Delay: {delay}s")
        
        try:
            # Setup pin for input
            if self.gpio_lib.setup_gpio_pin(pin) < 0:
                raise RuntimeError(f"Failed to setup input pin {pin}")
            
            success_count = 0
            for i in range(iterations):
                print(f"\nTest {i+1}/{iterations}:", end=" ", flush=True)
                
                try:
                    # Wait for signal
                    if self.gpio_lib.wait_for_gpio_high(pin, int(1000000)):  # 1s timeout
                        success_count += 1
                        print("✓ Signal detected")
                    else:
                        print("✗ No signal detected")
                except Exception as e:
                    print(f"✗ Error during detection: {str(e)}")
                
                time.sleep(delay)
            
            print(f"\nTest complete: {success_count}/{iterations} successful")
            return success_count == iterations
            
        except Exception as e:
            print(f"\nTest failed: {str(e)}")
            return False
    
    def test_gpio_output(self, pin, iterations=10, delay=0.1):
        """
        Test GPIO output triggering on specified pin.
        
        This test verifies the GPIO output by:
        1. Sending trigger pulses on specified output pin
        2. Reporting trigger sent
        3. Repeating for specified iterations
        
        Args:
            pin (int): GPIO pin number to test for output
            iterations (int): Number of trigger cycles to run (default: 10)
            delay (float): Delay between triggers in seconds (default: 0.1)
                - Must be longer than trigger pulse width (1ms)
        
        Returns:
            bool: True if all triggers were sent successfully, False otherwise
        """
        print(f"\nStarting GPIO output test:")
        print(f"Output Pin: {pin}")
        print(f"Iterations: {iterations}")
        print(f"Delay: {delay}s")
        
        try:
            # Setup pin for output
            if self.gpio_lib.setup_gpio_output_pin(pin) < 0:
                raise RuntimeError(f"Failed to setup output pin {pin}")
            
            success_count = 0
            for i in range(iterations):
                print(f"\nTest {i+1}/{iterations}:", end=" ", flush=True)
                
                try:
                    # Send trigger
                    self.gpio_lib.send_gpio_pulse(pin)
                    success_count += 1
                    print("✓ Trigger sent")
                except Exception as e:
                    print(f"✗ Failed to send trigger: {e}")
                
                time.sleep(delay)
            
            print(f"\nTest complete: {success_count}/{iterations} successful")
            return success_count == iterations
            
        except Exception as e:
            print(f"\nTest failed: {str(e)}")
            return False
    
    def start(self):
        try:
            self.sock.listen(1)
            print(f"Server listening on {self.host}:{self.port}")
            
            while self.running:
                try:
                    conn, addr = self.sock.accept()
                    print(f"Connected by {addr}")
                    
                    while self.running:
                        try:
                            data = conn.recv(1024)
                            if not data:
                                break
                                
                            command = data.decode('ascii').strip()
                            response = self.handle_command(command)
                            conn.send(f"{response}\n".encode('ascii'))
                            
                        except socket.error as e:
                            print(f"Socket error while handling client: {str(e)}")
                            break
                        except Exception as e:
                            print(f"Error handling command: {str(e)}")
                            
                except KeyboardInterrupt:
                    print("\nReceived keyboard interrupt...")
                    break
                except socket.error as e:
                    print(f"Socket error: {str(e)}")
                except Exception as e:
                    print(f"Error: {str(e)}")
                finally:
                    if 'conn' in locals():
                        try:
                            conn.close()
                        except:
                            pass
                            
        except Exception as e:
            print(f"Fatal error: {str(e)}")
            self.cleanup()
    
    def signal_handler(self, signum, frame):
        print("\nShutting down server...")
        self.running = False
        self.cleanup()
        sys.exit(0)
        
    def cleanup(self):
        print("Cleaning up resources...")
        try:
            self.gpio_lib.terminate_pigpio()
        except:
            pass
            
        try:
            self.sock.close()
        except:
            pass
            
        print("Server stopped")

#===============================================================================================================================================
#<o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o>
#===============================================================================================================================================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='GPIO Trigger Server')
    parser.add_argument('--host', default=IP_ADDR, help='Host IP address')
    parser.add_argument('--port', type=int, default=PORT, help='Port number')
    parser.add_argument('--trig-out', type=int, default=23, help='Trigger output pin')
    parser.add_argument('--trig-in', type=int, default=25, help='Trigger input pin')
    
    args = parser.parse_args()
    
    try:
        # Initialize the server with GPIO pins only
        server = TriggerServer(trig_out_pin=args.trig_out, trig_in_pin=args.trig_in, 
                             host=args.host, port=args.port)
        print(f"GPIO Trigger Server initialized")
        print(f"Monitoring trigger input on pin {server.trig_in_pin}")
        print(f"Sending trigger output on pin {server.trig_out_pin}")
        print(f"Listening on {server.host}:{server.port}")
        print("Press Ctrl+C to stop.")
        
        # Start the server (no motor control logic here)
        server.start()
        
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt: Stopping server.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if 'server' in locals():
            server.cleanup()
        print("GPIO cleanup complete.")

