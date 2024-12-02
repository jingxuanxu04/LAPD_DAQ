'''
Setup a simple TCP server to send trigger pulses when requested
Runs on Raspberry Pi
- Run normal server mode: python pi_send_trig.py
- Run self-test mode: python pi_send_trig.py --test
- Run custom test parameters: python pi_send_trig.py --test --iterations <N> --delay <T>
'''

import socket
import RPi.GPIO as GPIO
import time
import signal
import sys
import argparse

IP_ADDR = '192.168.1.100'
PORT = 5000

class TriggerServer:
    def __init__(self, host=IP_ADDR, port=PORT, trig_out_pin=18, trig_in_pin=23):
        self.host = host
        self.port = port
        self.trig_out_pin = trig_out_pin
        self.trig_in_pin = trig_in_pin
        self.running = True
        
        # Setup GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.trig_out_pin, GPIO.OUT)
        GPIO.setup(self.trig_in_pin, GPIO.IN)
        GPIO.output(self.trig_out_pin, GPIO.LOW)
        
        # Setup socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def handle_command(self, command):
        cmd = command.upper()
        
        if cmd == 'TRIG':
            self.send_trigger()
            return 'OK'
        elif cmd == 'STATUS':
            return 'READY'
        elif cmd == 'TEST':
            success = self.run_self_test(iterations=5)
            return 'TEST_PASS' if success else 'TEST_FAIL'
        elif cmd == 'WAIT_TRIG':
            if self.wait_for_trigger(timeout=1):
                return 'TRIGGERED'
            return 'NO_TRIGGER'
            
        return 'ERR UNKNOWN_CMD'
    
    def send_trigger(self):
        """Send a 10us trigger pulse"""
        GPIO.output(self.trig_out_pin, GPIO.HIGH)
        time.sleep(0.00001)  # 10 microseconds
        GPIO.output(self.trig_out_pin, GPIO.LOW)
    
    def wait_for_trigger(self, timeout=5):
        """Wait for rising edge on trigger input pin"""
        try:
            channel = GPIO.wait_for_edge(self.trig_in_pin, GPIO.RISING, timeout=int(timeout * 1000))
            return channel is not None
        except:
            return False
    
    def run_self_test(self, iterations=10, delay=0.1):
        """Run local GPIO loopback test"""
        print(f"\nStarting GPIO self-test:")
        print(f"Output Pin: {self.trig_out_pin}")
        print(f"Input Pin: {self.trig_in_pin}")
        print(f"Iterations: {iterations}")
        print(f"Delay: {delay}s")
        
        success_count = 0
        for i in range(iterations):
            print(f"\nTest {i+1}/{iterations}:", end=" ", flush=True)
            
            # Send trigger
            self.send_trigger()
            
            # Wait for trigger
            if self.wait_for_trigger(timeout=1):
                success_count += 1
                print("✓ Trigger received")
            else:
                print("✗ No trigger detected")
            
            time.sleep(delay)
        
        print(f"\nTest complete: {success_count}/{iterations} successful")
        return success_count == iterations
    
    def start(self):
        self.sock.listen(1)
        print(f"Server listening on {self.host}:{self.port}")
        
        while self.running:
            try:
                conn, addr = self.sock.accept()
                print(f"Connected by {addr}")
                
                while self.running:
                    data = conn.recv(1024).decode('ascii').strip()
                    if not data:
                        break
                    
                    response = self.handle_command(data)
                    conn.send(f"{response}\n".encode('ascii'))
                    
            except KeyboardInterrupt:
                print("\nReceived keyboard interrupt...")
                break
            except Exception as e:
                print(f"Error: {e}")
            finally:
                if 'conn' in locals():
                    conn.close()
    
    def handle_command(self, command):
        cmd = command.upper()
        
        if cmd == 'TRIG':
            self.send_trigger()
            return 'OK'
        elif cmd == 'STATUS':
            return 'READY'
        elif cmd == 'TEST':
            success = self.run_self_test(iterations=5)
            return 'TEST_PASS' if success else 'TEST_FAIL'
            
        return 'ERR UNKNOWN_CMD'
    
    def signal_handler(self, signum, frame):
        print("\nShutting down server...")
        self.running = False
        self.cleanup()
        sys.exit(0)
        
    def cleanup(self):
        print("Cleaning up resources...")
        self.sock.close()
        GPIO.cleanup()
        print("Server stopped")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Trigger Server with self-test capability')
    parser.add_argument('--test', action='store_true', help='Run GPIO self-test only')
    parser.add_argument('--iterations', type=int, default=10, help='Number of test iterations')
    parser.add_argument('--delay', type=float, default=0.1, help='Delay between tests in seconds')
    args = parser.parse_args()
    
    server = TriggerServer()
    
    try:
        if args.test:
            # Run self-test only
            success = server.run_self_test(iterations=args.iterations, delay=args.delay)
            sys.exit(0 if success else 1)
        else:
            # Start server
            server.start()
    except KeyboardInterrupt:
        pass
    finally:
        server.cleanup()