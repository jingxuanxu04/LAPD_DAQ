import time
import datetime
import os
from pathlib import Path
from pyphantom import Phantom, utils, cine

class PhantomRecorder:
    def __init__(self, config):
        """Initialize the Phantom camera recorder with configuration settings.
        
        Args:
            config (dict): Configuration dictionary containing:
                - save_path (str): Base path to save recorded cines
                - exposure_us (int): Exposure time in microseconds
                - fps (int): Frames per second
                - pre_trigger_frames (int): Number of frames to save before trigger
                - post_trigger_frames (int): Number of frames to save after trigger
                - resolution (tuple): Resolution as (width, height)
                - num_shots (int): Number of shots to record
        """
        self.config = config
        self.ph = Phantom()
        
        # Verify camera connection
        if self.ph.camera_count == 0:
            raise RuntimeError("No Phantom camera discovered")
            
        # Connect to first available camera
        self.cam = self.ph.Camera(0)
        self._configure_camera()
        
    def _configure_camera(self):
        """Apply configuration settings to the camera."""
        self.cam.resolution = self.config['resolution']
        self.cam.exposure = self.config['exposure_us']
        self.cam.frame_rate = self.config['fps']
        self.cam.pre_trigger = self.config['pre_trigger_frames']
        self.cam.post_trigger_frames = self.config['post_trigger_frames']
        
        # Ensure save directory exists
        Path(self.config['save_path']).mkdir(parents=True, exist_ok=True)
        
    def record_cine(self):
        """Record a single cine file, waiting for trigger."""
        print("Waiting for trigger... ", end='\r')
        
        # Clear previous recordings and start new recording
        self.cam.record(cine=1, delete_all=True)
        
        # Wait for recording to complete
        while not self.cam.partition_recorded(1):
            time.sleep(0.1)
        print("Recording complete")
        
    def save_cine(self, shot_number):
        """Save the recorded cine file with frame range and timestamp.
        
        Args:
            shot_number (int): Current shot number for filename
        """
        # Generate timestamp and filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"shot_{shot_number:03d}_{timestamp}.cine"
        full_path = os.path.join(self.config['save_path'], filename)
        
        # Create Cine object and save specified frame range
        rec_cine = cine.Cine.from_camera(self.cam, 1)
        frame_range = utils.FrameRange(
            -self.config['pre_trigger_frames'],
            self.config['post_trigger_frames']
        )
        rec_cine.save_range = frame_range
        
        # Save and monitor progress
        print(f"Saving to {filename}")
        rec_cine.save_non_blocking(filename=full_path)
        
        while rec_cine.save_percentage < 100:
            print(f"Saving: {rec_cine.save_percentage}%", end='\r')
            time.sleep(0.1)
            
        print(f"Save complete: {full_path}")
        rec_cine.close()
        
    def record_sequence(self):
        """Record the specified number of shots."""
        try:
            for shot in range(self.config['num_shots']):
                print(f"\nRecording shot {shot + 1}/{self.config['num_shots']}")
                self.record_cine()
                self.save_cine(shot + 1)
                
        finally:
            self.cleanup()
            
    def cleanup(self):
        """Clean up camera resources."""
        self.cam.close()
        self.ph.close()

def main():
    # Example configuration
    config = {
        'save_path': 'D:/phantom_recordings',
        'exposure_us': 20,
        'fps': 10000,
        'pre_trigger_frames': 100,
        'post_trigger_frames': 400,
        'resolution': (512, 512),
        'num_shots': 5
    }
    
    try:
        recorder = PhantomRecorder(config)
        recorder.record_sequence()
        
    except KeyboardInterrupt:
        print("\nRecording interrupted by user")
    except Exception as e:
        print(f"Error during recording: {e}")

if __name__ == '__main__':
    main() 