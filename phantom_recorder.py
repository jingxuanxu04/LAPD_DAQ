

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
                - save_path (str): Base path to save recorded cines
                - name (str): Experiment name for file naming
                - exposure_us (int): Exposure time in microseconds
                - fps (int): Frames per second
                - pre_trigger_frames (int): Number of frames to save before trigger
                - post_trigger_frames (int): Number of frames to save after trigger
                - resolution (tuple): Resolution as (width, height)
                - save_format (str): 'cine', 'hdf5', or 'both' (default: 'cine')
                - hdf5_file_path (str): Path to existing HDF5 file from multi_scope_acquisition (required if save_format includes 'hdf5')
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
        
        # Initialize HDF5 integration if needed
        if self.config.get('save_format', 'cine') in ['hdf5', 'both']:
            if 'hdf5_file_path' not in self.config:
                raise ValueError("hdf5_file_path is required when save_format includes 'hdf5'")
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
        
        # Add camera configuration to the existing HDF5 file
        with h5py.File(self.hdf5_path, 'a') as f:
            # Create FastCam group under /Control if it doesn't exist
            if '/Control' not in f:
                f.create_group('/Control')
            
            control_group = f['/Control']
            
            if 'FastCam' not in control_group:
                fastcam_group = control_group.create_group('FastCam')
                
                # Add camera configuration metadata
                fastcam_group.attrs['camera_type'] = 'Phantom'
                fastcam_group.attrs['exposure_us'] = self.config['exposure_us']
                fastcam_group.attrs['fps'] = self.config['fps']
                fastcam_group.attrs['resolution'] = self.config['resolution']
                fastcam_group.attrs['pre_trigger_frames'] = self.config['pre_trigger_frames']
                fastcam_group.attrs['post_trigger_frames'] = self.config['post_trigger_frames']
                fastcam_group.attrs['total_frames'] = abs(self.config['pre_trigger_frames']) + self.config['post_trigger_frames']
                fastcam_group.attrs['configuration_time'] = time.ctime()
                
                print(f"FastCam configuration added to HDF5")
            
            # Create FastCam group at root level for shot data
            if 'FastCam' not in f:
                f.create_group('FastCam')
                f['FastCam'].attrs['description'] = 'Phantom high-speed camera data'
                f['FastCam'].attrs['camera_type'] = 'Phantom'
                f['FastCam'].attrs['synchronized_with_scopes'] = True
        
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
            shot_number (int): Current shot number for filename (0-based)
            timestamp (float): Camera shot timestamp saved in HDF5 file
        """
        # Create Cine object
        rec_cine = cine.Cine.from_camera(self.cam, 1)
        
        # Set frame range
        frame_range = utils.FrameRange(self.config['pre_trigger_frames'], self.config['post_trigger_frames'])
        rec_cine.save_range = frame_range
        
        save_format = self.config.get('save_format', 'cine')
        
        if save_format in ['cine', 'both']:
            # Save as .cine file
            filename = f"{self.config['name']}_shot{shot_number+1:03d}.cine"
            full_path = os.path.join(self.config['save_path'], filename)
            
            print(f"Saving to {filename}")
            try:
                rec_cine.save_non_blocking(filename=full_path)
                
                while rec_cine.save_percentage < 100:
                    print(f"Saving: {rec_cine.save_percentage}%", end='\r')
                    time.sleep(0.05)  # Reduced from 0.1 to 0.05 for faster response
                    
                print(f"Save complete: {full_path}")
            except KeyboardInterrupt:
                print(f"\nSave interrupted for {filename}")
                raise  # Re-raise to propagate the interrupt
        
        if save_format in ['hdf5', 'both']:
            # Save to HDF5
            try:
                self._save_to_hdf5(rec_cine, shot_number, timestamp)
            except KeyboardInterrupt:
                print("\nHDF5 save interrupted")
                raise  # Re-raise to propagate the interrupt
        
        rec_cine.close()
        
    def _save_to_hdf5(self, rec_cine, shot_number, timestamp):
        """Save cine data to HDF5 file integrated with multi_scope_acquisition.
        
        Args:
            rec_cine: Cine object with recorded data
            shot_number (int): Current shot number (0-based)
            timestamp (float): Recording timestamp
        """
        shot_name = f'shot_{shot_number+1}'
        print(f"Saving {shot_name} to HDF5...")
        
        with h5py.File(self.hdf5_path, 'a') as f:
            fastcam_group = f['FastCam']
            
            # Create shot group
            if shot_name in fastcam_group:
                print(f"Warning: {shot_name} already exists in FastCam group, overwriting...")
                del fastcam_group[shot_name]
            
            shot_group = fastcam_group.create_group(shot_name)
            
            # Calculate total frames
            total_frames = abs(self.config['pre_trigger_frames']) + self.config['post_trigger_frames']
            
            # Create datasets with optimized chunking and compression
            frames_ds = shot_group.create_dataset('frames', 
                                                shape=(total_frames, self.config['resolution'][1], self.config['resolution'][0]),
                                                dtype=np.uint16,
                                                chunks=(1, self.config['resolution'][1], self.config['resolution'][0]),
                                                compression='gzip',
                                                compression_opts=9,
                                                shuffle=True,
                                                fletcher32=True)
            
            timestamps_ds = shot_group.create_dataset('timestamps', 
                                                    shape=(total_frames,), 
                                                    dtype=np.float64,
                                                    compression='gzip',
                                                    compression_opts=9)
            
            # Create time array dataset (similar to scope data)
            time_interval = 1.0 / self.config['fps']
            time_array = np.arange(total_frames) * time_interval
            # Adjust time array to be relative to trigger (frame 0 is trigger)
            trigger_frame = abs(self.config['pre_trigger_frames'])
            time_array = time_array - (trigger_frame * time_interval)
            
            time_ds = shot_group.create_dataset('time_array', 
                                              data=time_array,
                                              dtype=np.float64,
                                              compression='gzip',
                                              compression_opts=9)
            
            # Add metadata to datasets
            frames_ds.attrs['description'] = 'High-speed camera frame data'
            frames_ds.attrs['units'] = 'counts'
            frames_ds.attrs['dtype'] = str(frames_ds.dtype)
            
            timestamps_ds.attrs['description'] = 'Absolute timestamps for each frame'
            timestamps_ds.attrs['units'] = 'seconds since epoch'
            
            time_ds.attrs['description'] = 'Time array relative to trigger'
            time_ds.attrs['units'] = 'seconds'
            time_ds.attrs['trigger_frame'] = trigger_frame
            
            # Read and save all frames
            for frame_idx in range(total_frames):
                try:
                    # Read frame data
                    frame_data = rec_cine.get_frame(frame_idx)
                    frames_ds[frame_idx] = frame_data
                    
                    # Calculate absolute timestamp for this frame
                    frame_time = timestamp + (frame_idx * time_interval)
                    timestamps_ds[frame_idx] = frame_time
                    
                    if frame_idx % 100 == 0:
                        print(f"Frame {frame_idx}/{total_frames}", end='\r')
                except KeyboardInterrupt:
                    print(f"\nHDF5 save interrupted for {shot_name}")
                    raise  # Re-raise to propagate the interrupt
                except Exception as e:
                    print(f"Error reading frame {frame_idx}: {e}")
                    # Fill with zeros if frame read fails
                    frames_ds[frame_idx] = np.zeros(self.config['resolution'][::-1], dtype=np.uint16)
                    timestamps_ds[frame_idx] = timestamp + (frame_idx * time_interval)
            
            # Add shot metadata
            shot_group.attrs['shot_number'] = shot_number + 1
            shot_group.attrs['recording_timestamp'] = timestamp
            shot_group.attrs['acquisition_time'] = time.ctime()
            shot_group.attrs['frame_rate'] = self.config['fps']
            shot_group.attrs['exposure_us'] = self.config['exposure_us']
            shot_group.attrs['resolution'] = self.config['resolution']
            shot_group.attrs['pre_trigger_frames'] = self.config['pre_trigger_frames']
            shot_group.attrs['post_trigger_frames'] = self.config['post_trigger_frames']
            shot_group.attrs['total_frames'] = total_frames
            shot_group.attrs['trigger_frame'] = trigger_frame
            shot_group.attrs['time_interval'] = time_interval
            
        print(f"HDF5 save complete for {shot_name}")
                    
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
         pre_trigger_frames=-100, post_trigger_frames=200, save_format='both',
         base_path=None, experiment_name=None):
    """
    Main function for testing PhantomRecorder with both HDF5 and cine file output.
    Creates a new HDF5 file and records N shots for testing purposes.
    
    Args:
        num_shots (int): Number of shots to record
        exposure_us (int): Exposure time in microseconds
        fps (int): Frames per second
        resolution (tuple): Camera resolution (width, height)
        pre_trigger_frames (int): Number of frames before trigger (negative)
        post_trigger_frames (int): Number of frames after trigger
        save_format (str): 'cine', 'hdf5', or 'both'
        base_path (str): Base path for saving files (None for default)
        experiment_name (str): Experiment name (None for auto-generated)
    """
    import datetime
    
    # Test configuration
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    
    # Create test HDF5 filename
    test_hdf5_filename = f"{experiment_name}.hdf5"
    test_hdf5_path = os.path.join(base_path, test_hdf5_filename)
    
    # Ensure directory exists
    Path(base_path).mkdir(parents=True, exist_ok=True)
    
    # Create a minimal HDF5 file structure for testing (simulating multi_scope_acquisition structure)
    print(f"Creating test HDF5 file: {test_hdf5_path}")
    with h5py.File(test_hdf5_path, 'w') as f:
        # Add basic experiment metadata
        f.attrs['experiment_name'] = experiment_name
        f.attrs['creation_time'] = time.ctime()
        f.attrs['description'] = 'Test recording with Phantom camera'
        
        # Create Control group (simulating multi_scope_acquisition structure)
        control_group = f.create_group('/Control')
        control_group.attrs['description'] = 'Control and configuration data'
    
    # Camera configuration for testing
    config = {
        'save_path': base_path,
        'name': experiment_name,
        'exposure_us': exposure_us,
        'fps': fps,
        'pre_trigger_frames': pre_trigger_frames,
        'post_trigger_frames': post_trigger_frames,
        'resolution': resolution,
        'save_format': save_format,
        'hdf5_file_path': test_hdf5_path
    }

    
    try:
        # Create recorder instance
        print("\nInitializing Phantom camera...")
        recorder = PhantomRecorder(config)

        print(f"\nStarting test recording of {num_shots} shots...")        
        
        for n in range(num_shots):
            print(f"====Starting recording {n}====")
            recorder.start_recording()
            timestamp = recorder.wait_for_recording_completion()
            print(f"\n=== Recording Complete ===")
            recorder.save_cine(n, timestamp)
            print(f"Files saved")

        recorder.cleanup()
        
        # Display file information
        if os.path.exists(test_hdf5_path):
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
         save_format='both', 
         base_path=r"E:\Shadow data\Energetic_Electron_Ring\test", 
         experiment_name="test") 