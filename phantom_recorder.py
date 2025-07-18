

import time
import datetime
import os
import numpy as np
import h5py
from pathlib import Path
from pyphantom import Phantom, utils, cine

class PhantomRecorder:
    def __init__(self, config):
        """Initialize the Phantom camera recorder with configuration settings.
        
        Args:
            config (dict): Configuration dictionary containing:
                - save_path (str): Base directory path to save recorded cines
                - name (str): Experiment name for file naming
                - exposure_us (int): Exposure time in microseconds
                - fps (int): Frames per second
                - pre_trigger_frames (int): Number of frames to save before trigger
                - post_trigger_frames (int): Number of frames to save after trigger
                - resolution (tuple): Resolution as (width, height)
                - hdf5_file_path (str): Path to HDF5 file for metadata (None to disable)
                
        Notes:
            - Always saves .cine files with naming: "experiment_name_shot###.cine"
            - If hdf5_file_path is provided, saves metadata (shot number, cine filename, timestamp) to HDF5
            - If hdf5_file_path is None, saves only .cine files
        """
        self.config = config
        self.ph = Phantom()
        
        # Verify camera connection
        if self.ph.camera_count == 0:
            self.ph.close()
            raise RuntimeError("No Phantom camera discovered")
            
        # Connect to first available camera
        self.cam = self.ph.Camera(0)
        self._configure_camera()
        
        # Initialize HDF5 integration if hdf5_file_path is provided
        if self.config.get('hdf5_file_path') is not None:
            self._initialize_hdf5_integration()
        
    def _configure_camera(self):
        """Apply configuration settings to the camera."""
        self.cam.resolution = self.config['resolution']
        self.cam.exposure = self.config['exposure_us']
        self.cam.frame_rate = self.config['fps']
        
        # Ensure save directory exists
        Path(self.config['save_path']).mkdir(parents=True, exist_ok=True)
        
    def _initialize_hdf5_integration(self):
        """Initialize HDF5 integration with existing multi_scope_acquisition file."""
        self.hdf5_path = self.config['hdf5_file_path']
        
        # Add camera configuration and data arrays to /Control/FastCam
        with h5py.File(self.hdf5_path, 'a') as f:
            # Create Control group if it doesn't exist
            if '/Control' not in f:
                f.create_group('/Control')
            
            control_group = f['/Control']
            
            # Create FastCam group under Control if it doesn't exist
            if 'FastCam' not in control_group:
                fastcam_group = control_group.create_group('FastCam')
                
                # Create config group for camera configuration
                config_group = fastcam_group.create_group('config')
                config_group.attrs['camera_type'] = 'Phantom'
                config_group.attrs['exposure_us'] = self.config['exposure_us']
                config_group.attrs['fps'] = self.config['fps']
                config_group.attrs['resolution'] = self.config['resolution']
                config_group.attrs['pre_trigger_frames'] = self.config['pre_trigger_frames']
                config_group.attrs['post_trigger_frames'] = self.config['post_trigger_frames']
                config_group.attrs['configuration_time'] = time.ctime()
                
                # Create extensible 1D arrays for shot data
                # Shot numbers (1-based indexing)
                shot_numbers = fastcam_group.create_dataset('shot number', 
                                                          shape=(0,), 
                                                          maxshape=(None,),
                                                          dtype='i4',
                                                          chunks=True)
                shot_numbers.attrs['description'] = 'Shot numbers (1-based)'
                
                # Cine filenames
                cine_filenames = fastcam_group.create_dataset('cine file name', 
                                                            shape=(0,), 
                                                            maxshape=(None,),
                                                            dtype=h5py.string_dtype(encoding='utf-8'),  # Variable-length UTF-8 strings
                                                            chunks=True)
                cine_filenames.attrs['description'] = 'Cine filenames for each shot'
                
                # Timestamps
                timestamps = fastcam_group.create_dataset('timestamp', 
                                                        shape=(0,), 
                                                        maxshape=(None,),
                                                        dtype='f8',
                                                        chunks=True)
                timestamps.attrs['description'] = 'Recording timestamps for each shot'
                timestamps.attrs['units'] = 'seconds since epoch'
                
                print(f"FastCam configuration and data arrays created in /Control/FastCam")
        
    def start_recording(self):
        """Start recording without waiting for completion (for parallel arming)."""
        print("Arming camera for trigger... ", end='')
        
        # Clear previous recordings and start new recording
        self.cam.record(cine=1, delete_all=True)
        print("armed")
        
    def wait_for_recording_completion(self):
        """Wait for recording to complete and return timestamp."""
        print("Waiting for camera trigger... ", end='\r')
        
        # Wait for recording to complete
        try:
            while not self.cam.partition_recorded(1):
                time.sleep(0.05)  # Reduced from 0.1 to 0.05 for faster response
        except KeyboardInterrupt:
            print("\nCamera recording interrupted by user")
            raise  # Re-raise to propagate the interrupt
        
        print("Camera recording complete")
        return time.time()
        
    def save_cine(self, shot_number, timestamp):
        """Save the recorded cine file with frame range and trigger timestamp.
        
        Args:
            shot_number (int): Current shot number for filename
        """
        # Create Cine object
        rec_cine = cine.Cine.from_camera(self.cam, 1)

        filename = f"{self.config['name']}_shot{shot_number:03d}.cine"
        full_path = os.path.join(self.config['save_path'], filename)
        
        # Set frame range and save
        frame_range = utils.FrameRange(self.config['pre_trigger_frames'], self.config['post_trigger_frames'])
        rec_cine.save_range = frame_range
        
        # Save and monitor progress
        print(f"Saving to {filename}")
        rec_cine.save_non_blocking(filename=full_path)
        
        while rec_cine.save_percentage < 100:
            print(f"Saving: {rec_cine.save_percentage}%", end='\r')
            time.sleep(0.1)
            
        print(f"Save complete: {full_path}")
        rec_cine.close()
        
    def _update_hdf5_metadata(self, shot_number, cine_filename, timestamp):
        """Update HDF5 metadata arrays with shot information.
        
        Args:
            shot_number (int): Current shot number (0-based)
            cine_filename (str): Filename of the saved cine file
            timestamp (float): Recording timestamp
        """
        print(f"Updating HDF5 metadata for shot {shot_number+1}...")
        
        with h5py.File(self.hdf5_path, 'a') as f:
            fastcam_group = f['/Control/FastCam']
            
            # Get the three 1D arrays
            shot_numbers = fastcam_group['shot number']
            cine_filenames = fastcam_group['cine file name']
            timestamps = fastcam_group['timestamp']
            
            # Resize all arrays to add new shot
            current_size = shot_numbers.shape[0]
            shot_numbers.resize((current_size + 1,))
            cine_filenames.resize((current_size + 1,))
            timestamps.resize((current_size + 1,))
            
            # Add metadata for this shot (shot number is 1-based)
            shot_numbers[current_size] = shot_number + 1
            cine_filenames[current_size] = cine_filename
            timestamps[current_size] = timestamp
            
            print(f"HDF5 metadata updated: shot {shot_number+1}, {cine_filename}, timestamp {timestamp}")
                    
    def cleanup(self):
        """Clean up camera resources."""
        print("Cleaning up camera resources...")
        
        try:
            if hasattr(self, 'cam'):
                print("Closing camera connection...")
                self.cam.close()
        except Exception as e:
            print(f"Error closing camera: {e}")
            
        try:
            if hasattr(self, 'ph'):
                print("Closing Phantom interface...")
                self.ph.close()
        except Exception as e:
            print(f"Error closing Phantom interface: {e}")
            
        print("Camera cleanup complete")
            

def main(num_shots=2, exposure_us=50, fps=5000, resolution=(256, 256), 
         pre_trigger_frames=-100, post_trigger_frames=200, 
         base_path=None, experiment_name=None, save_metadata_to_hdf5=True):
    """
    Main function for testing PhantomRecorder with simplified configuration.
    Creates a new HDF5 file and records N shots for testing purposes.
    
    Args:
        num_shots (int): Number of shots to record
        exposure_us (int): Exposure time in microseconds
        fps (int): Frames per second
        resolution (tuple): Camera resolution (width, height)
        pre_trigger_frames (int): Number of frames before trigger (negative)
        post_trigger_frames (int): Number of frames after trigger
        base_path (str): Base path for saving files (None for default)
        experiment_name (str): Experiment name (None for auto-generated)
        save_metadata_to_hdf5 (bool): Whether to create HDF5 file and save metadata
    """
    import datetime
    
    # Test configuration
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    
    # Create test HDF5 filename and path only if saving metadata
    test_hdf5_path = None
    if save_metadata_to_hdf5:
        test_hdf5_filename = f"{experiment_name}.hdf5"
        test_hdf5_path = os.path.join(base_path, test_hdf5_filename)
        
        # Ensure directory exists
        Path(base_path).mkdir(parents=True, exist_ok=True)
        
        # Create a minimal HDF5 file structure for testing
        print(f"Creating test HDF5 file: {test_hdf5_path}")
        with h5py.File(test_hdf5_path, 'w') as f:
            # Add basic experiment metadata
            f.attrs['experiment_name'] = experiment_name
            f.attrs['creation_time'] = time.ctime()
            f.attrs['description'] = 'Test recording with Phantom camera - simplified configuration'
            
            # Create Control group (simulating multi_scope_acquisition structure)
            control_group = f.create_group('/Control')
            control_group.attrs['description'] = 'Control and configuration data'
    else:
        # Ensure directory exists even if not saving HDF5
        Path(base_path).mkdir(parents=True, exist_ok=True)
    
    # Camera configuration for testing
    config = {
        'save_path': base_path,
        'name': experiment_name,
        'exposure_us': exposure_us,
        'fps': fps,
        'pre_trigger_frames': pre_trigger_frames,
        'post_trigger_frames': post_trigger_frames,
        'resolution': resolution,
        'hdf5_file_path': test_hdf5_path  # None if not saving metadata
    }

    
    try:
        # Create recorder instance
        print("\nInitializing Phantom camera...")
        recorder = PhantomRecorder(config)

        print(f"\nStarting test recording of {num_shots} shots...")        
        
        for n in range(num_shots):
            print(f"====Starting recording {n+1}====")
            recorder.start_recording()
            timestamp = recorder.wait_for_recording_completion()
            print(f"\n=== Recording Complete ===")
            recorder.save_cine(n, timestamp)
            print(f"Shot {n+1} saved")

        recorder.cleanup()
        
        # Display file information
        if test_hdf5_path and os.path.exists(test_hdf5_path):
            hdf5_size = os.path.getsize(test_hdf5_path) / (1024 * 1024)  # MB
            print(f"HDF5 file size: {hdf5_size:.1f} MB")
            
            # Show HDF5 structure
            print("\nHDF5 file structure:")
            with h5py.File(test_hdf5_path, 'r') as f:
                def print_structure(name, obj):
                    indent = "  " * (name.count('/') - 1)
                    if isinstance(obj, h5py.Group):
                        print(f"{indent}{name.split('/')[-1]}/")
                    else:
                        shape_str = f"{obj.shape}" if hasattr(obj, 'shape') else ""
                        dtype_str = f"{obj.dtype}" if hasattr(obj, 'dtype') else ""
                        print(f"{indent}{name.split('/')[-1]} {shape_str} {dtype_str}")
                
                f.visititems(print_structure)

        
        # List cine files
        cine_files = [f for f in os.listdir(base_path) if f.endswith('.cine') and config['name'] in f]
        if cine_files:
            print(f"\nCine files created:")
            for cine_file in sorted(cine_files):
                cine_path = os.path.join(base_path, cine_file)
                if os.path.exists(cine_path):
                    cine_size = os.path.getsize(cine_path) / (1024 * 1024)  # MB
                    print(f"  {cine_file} ({cine_size:.1f} MB)")
        
        
    except KeyboardInterrupt:
        print("\n=== Recording interrupted by user ===")
    except Exception as e:
        print(f"\n=== Error during recording ===")
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if 'recorder' in locals():
            try:
                recorder.cleanup()
                print("Camera resources cleaned up")
            except Exception as e:
                print(f"Error during cleanup: {e}")
    
    print(f"\nTest completed. Files saved in: {base_path}")
    if test_hdf5_path:
        print("Note: HDF5 file contains metadata - actual frames are in .cine files")
    else:
        print("Note: Only .cine files saved - no HDF5 metadata")

#===============================================================================================================================================
# Main Test Loop
#===============================================================================================================================================

if __name__ == '__main__':
    main(num_shots=2, 
         exposure_us=50, 
         fps=5000, 
         resolution=(256, 256),
         pre_trigger_frames=-100, 
         post_trigger_frames=200,
         save_metadata_to_hdf5=True, 
         base_path=r"E:\Shadow data\Energetic_Electron_Ring\test", 
         experiment_name="test") 