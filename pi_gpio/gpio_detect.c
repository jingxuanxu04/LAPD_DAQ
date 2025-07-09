#include <stdio.h>
#include <stdlib.h>
#include <pigpio.h>
#include <unistd.h>

static int pigpio_initialized = 0;

// Initialize pigpio library
int initialize_pigpio() {
    if (!pigpio_initialized) {
        if (gpioInitialise() < 0) {
            fprintf(stderr, "Failed to initialize pigpio.\n");
            return -1;
        }
        pigpio_initialized = 1;
        printf("pigpio library initialized.\n");
    }
    return 0;
}

// Terminate pigpio library
void terminate_pigpio() {
    if (pigpio_initialized) {
        gpioTerminate();
        pigpio_initialized = 0;
        printf("pigpio library terminated.\n");
    }
}

// Setup GPIO pin for input
int setup_gpio_pin(int pin) {
    if (!pigpio_initialized) {
        fprintf(stderr, "pigpio not initialized. Call initialize_pigpio() first.\n");
        return -1;
    }
    gpioSetMode(pin, PI_INPUT);
    gpioSetPullUpDown(pin, PI_PUD_DOWN);
    printf("GPIO pin %d configured for input with pull-down resistor.\n", pin);
    return 0;
}

// Setup GPIO pin for output
int setup_gpio_output_pin(int pin) {
    if (!pigpio_initialized) {
        fprintf(stderr, "pigpio not initialized. Call initialize_pigpio() first.\n");
        return -1;
    }
    gpioSetMode(pin, PI_OUTPUT);
    gpioWrite(pin, PI_HIGH);
    printf("GPIO pin %d configured for inverted output.\n", pin);
    return 0;
}

// Improved wait_for_gpio_high with hardware timing
void wait_for_gpio_high(int pin, int timeout_us) {
    if (!pigpio_initialized) {
        fprintf(stderr, "pigpio not initialized. Call initialize_pigpio() first.\n");
        return;
    }
    
    uint32_t start_tick = gpioTick();
    uint32_t current_tick;
    
    // Use hardware timer for precise edge detection
    gpioSetWatchdog(pin, timeout_us/1000); // Set watchdog in ms
    
    while (1) {
        if (gpioRead(pin) == PI_HIGH) {
            gpioSetWatchdog(pin, 0); // Disable watchdog
            printf("GPIO pin %d detected HIGH.\n", pin);
            return;
        }
        
        current_tick = gpioTick();
        if (timeout_us > 0 && (current_tick - start_tick) > timeout_us) {
            gpioSetWatchdog(pin, 0); // Disable watchdog
            fprintf(stderr, "Timeout waiting for GPIO pin %d\n", pin);
            return;
        }
        
        // Use minimal sleep to reduce CPU load while maintaining low latency
        gpioDelay(1); // 1 microsecond delay
    }
}

// Send a trigger pulse on GPIO pin
void send_gpio_pulse(int pin) {
    if (!pigpio_initialized) {
        fprintf(stderr, "pigpio not initialized. Call initialize_pigpio() first.\n");
        return;
    }
    gpioWrite(pin, PI_LOW);  
    gpioDelay(1000);            // Trigger pulse duration
    gpioWrite(pin, PI_HIGH);   
    // printf("Trigger pulse sent on GPIO pin %d.\n", pin);
}
