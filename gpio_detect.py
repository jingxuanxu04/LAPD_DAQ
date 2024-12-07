import ctypes
import atexit

# Load the shared library
library_path = "/home/generalpi/pi_gpio/gpio_detect.so"
gpio_interface = ctypes.CDLL(library_path)

# Define the function prototypes
gpio_interface.initialize_pigpio.restype = ctypes.c_int
gpio_interface.terminate_pigpio.restype = None
gpio_interface.setup_gpio_pin.argtypes = [ctypes.c_int]
gpio_interface.setup_gpio_pin.restype = ctypes.c_int
gpio_interface.busy_wait_gpio.argtypes = [ctypes.c_int]
gpio_interface.busy_wait_gpio.restype = None
gpio_interface.setup_gpio_output_pin.argtypes = [ctypes.c_int]
gpio_interface.setup_gpio_output_pin.restype = ctypes.c_int
gpio_interface.send_trigger_pulse.argtypes = [ctypes.c_int]
gpio_interface.send_trigger_pulse.restype = None

def initialize_pigpio():
    """
    Initialize pigpio library using C function.
    """
    result = gpio_interface.initialize_pigpio()
    if result < 0:
        raise RuntimeError("Failed to initialize pigpio.")

def terminate_pigpio():
    """
    Terminate pigpio library using C function.
    """
    gpio_interface.terminate_pigpio()

def setup_gpio_pin(pin):
    """
    Configure GPIO pin for input using C function.
    """
    result = gpio_interface.setup_gpio_pin(pin)
    if result < 0:
        raise RuntimeError(f"Failed to setup GPIO pin {pin}.")

def wait_for_gpio_high(pin, timeout_us=0):
    """
    Wait for GPIO pin to go high using hardware-timed detection.
    
    Args:
        pin (int): GPIO pin number
        timeout_us (int): Timeout in microseconds, 0 for no timeout
        
    Returns:
        bool: True if signal detected, False if timeout
    """
    gpio_interface.wait_for_gpio_high.argtypes = [ctypes.c_int, ctypes.c_int]
    gpio_interface.wait_for_gpio_high.restype = ctypes.c_bool
    return gpio_interface.wait_for_gpio_high(pin, timeout_us)

def setup_gpio_output_pin(pin):
    """
    Configure GPIO pin for output using C function.
    """
    result = gpio_interface.setup_gpio_output_pin(pin)
    if result < 0:
        raise RuntimeError(f"Failed to setup GPIO pin {pin} for output.")

def send_trigger_pulse(pin):
    """
    Send a trigger pulse on GPIO pin using C function.
    """
    gpio_interface.send_trigger_pulse(pin)

def test_gpio_loopback(trig_out_pin=18, trig_in_pin=25):
    """
    Test sending a trigger pulse and waiting for GPIO input.
    """
    try:
        initialize_pigpio()
        setup_gpio_output_pin(trig_out_pin)
        setup_gpio_pin(trig_in_pin)

        print(f"Sending a trigger pulse on GPIO pin {trig_out_pin}...")
        send_trigger_pulse(trig_out_pin)

        print(f"Waiting for GPIO pin {trig_in_pin} to go HIGH. Press Ctrl+C to stop...")
        wait_for_gpio_high(trig_in_pin)
        print(f"GPIO pin {trig_in_pin} detected HIGH signal!")
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt: Stopping test.")
    finally:
        terminate_pigpio()

if __name__ == "__main__":
    test_gpio_loopback(23,24)
