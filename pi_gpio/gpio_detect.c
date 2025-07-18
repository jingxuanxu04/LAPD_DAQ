#include <stdio.h>
#include <stdlib.h>
#include <pigpio.h>
#include <unistd.h>

static int pigpio_initialized = 0;

// Initialize pigpio library
int initialize_pigpio() {
    if (!pigpio_initialized) {
        if (gpioInitialise() < 0) {
            fprintf(stderr, "CCC Failed to initialize pigpio.\n");
            return -1;
        }
        pigpio_initialized = 1;
        fprintf(stderr, "CCC pigpio library initialized.\n");
    }
    return 0;
}

// Terminate pigpio library
void terminate_pigpio() {
    if (pigpio_initialized) {
        gpioTerminate();
        pigpio_initialized = 0;
        fprintf(stderr, "CCC pigpio library terminated.\n");
    }
}

// Setup GPIO pin for input
int setup_gpio_pin(int gpio_num) {
    if (!pigpio_initialized) {
        fprintf(stderr, "CCC pigpio not initialized. Call initialize_pigpio() first.\n");
        return -1;
    }
    gpioSetMode(gpio_num, PI_INPUT);
    gpioSetPullUpDown(gpio_num, PI_PUD_DOWN);
    fprintf(stderr, "CCC GPIO# %d configured for input with pull-down resistor.\n", gpio_num);
    return 0;
}

// Setup GPIO pin for output
int setup_gpio_output_pin(int gpio_num) {
    if (!pigpio_initialized) {
        fprintf(stderr, "CCC pigpio not initialized. Call initialize_pigpio() first.\n");
        return -1;
    }
    gpioSetMode(gpio_num, PI_OUTPUT);
    gpioWrite(gpio_num, PI_HIGH);
    fprintf(stderr, "CCC GPIO# %d configured for inverted output and set to HIGH.\n", gpio_num);
    return 0;
}


// Improved wait_for_gpio_high with hardware timing
int wait_for_gpio_high(int gpio_num, int timeout_us) {
    if (!pigpio_initialized) {
        fprintf(stderr, "CCC pigpio not initialized. Call initialize_pigpio() first.\n");
        return 0;
    }
    
    uint32_t start_tick = gpioTick();
    uint32_t current_tick;
    
    // Use hardware timer for precise edge detection
    //pp gpioSetWatchdog(gpio_num, timeout_us/1000); // Set watchdog in ms; timeout=0 disables watchdog
    
    fprintf(stderr, "CCC busy-wait...");
    while (1) {
        if (gpioRead(gpio_num) == PI_HIGH) {
            //pp gpioSetWatchdog(gpio_num, 0); // timeout=0 disables watchdog
            fprintf(stderr, "CCC GPIO# %d detected HIGH...", gpio_num);
            return 1;
        }
        
        current_tick = gpioTick();
        if (timeout_us > 0 && (current_tick - start_tick) > timeout_us) {
            //pp gpioSetWatchdog(gpio_num, 0); // timeout=0 disables watchdog
            fprintf(stderr, "CCC Timeout...");
            return 0;
        }
        
        // Use minimal sleep to reduce CPU load while maintaining low latency
        gpioDelay(100); // 100 microsecond delay
    }
}

// Send a trigger pulse on GPIO pin
void send_gpio_pulse(int gpio_num) {
    if (!pigpio_initialized) {
        fprintf(stderr, "CCC pigpio not initialized. Call initialize_pigpio() first.\n");
        return;
    }
    gpioWrite(gpio_num, PI_LOW);
    gpioDelay(1000);            // Wait for 1 ms
    gpioWrite(gpio_num, PI_HIGH);
    fprintf(stderr, "CCC Trigger pulse sent on GPIO# %d.\n", gpio_num);
}
