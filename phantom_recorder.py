

import time
import datetime
import os
import numpy as np
import h5py
from pathlib import Path
from pyphantom import Phantom, utils, cine

def check_phantom_prerequisites():
    """Check if Phantom camera prerequisites are met before initialization.
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Check if pyphantom library is properly installed
        import pyphantom
        
        # Try to access some basic phantom utilities
        # This will fail early if there are library issues
        try:
            # Test basic phantom utilities without full initialization
            phantom_version = getattr(pyphantom, '__version__', 'unknown')
            print(f"PyPhantom library version: {phantom_version}")
            
            return True, "Prerequisites check passed"
            
        except Exception as e:
            return False, f"PyPhantom library issue: {str(e)}"
            
    except ImportError as e:
        return False, f"PyPhantom library not found: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error during prerequisites check: {str(e)}"

def print_troubleshooting_guide():
    """Print comprehensive troubleshooting guide for Phantom camera issues."""
    print("\n" + "="*60)
    print("PHANTOM CAMERA TROUBLESHOOTING GUIDE")
    print("="*60)
    print()
    print("Common causes of 'Requested parameter is missing' error:")
    print()
    print("1. CAMERA HARDWARE:")
    print("   - Camera is not powered on")
    print("   - Camera is not fully booted (wait 2-3 minutes after power on)")
    print("   - Ethernet cable is not connected or faulty")
    print("   - Camera IP address is not accessible from this computer")
    print()
    print("2. SOFTWARE CONFLICTS:")
    print("   - Phantom Camera Control (PCC) software is running")
    print("   - Another Python script is using the camera")
    print("   - Previous camera connection was not properly closed")
    print()
    print("3. DRIVER/SDK ISSUES:")
    print("   - Phantom SDK is not properly installed")
    print("   - PyPhantom library is outdated or corrupted")
    print("   - Windows drivers are missing or outdated")
    print()
    print("4. NETWORK CONFIGURATION:")
    print("   - Camera and computer are on different subnets")
    print("   - Firewall is blocking camera communication")
    print("   - Network adapter settings are incorrect")
    print()
    print("TROUBLESHOOTING STEPS:")
    print()
    print("Step 1: Check Hardware")
    print("   - Verify camera power LED is on")
    print("   - Check Ethernet cable connection")
    print("   - Ping camera IP address from command prompt")
    print()
    print("Step 2: Close Conflicting Software")
    print("   - Close Phantom Camera Control (PCC)")
    print("   - Close any other camera applications")
    print("   - Restart Python if previous scripts crashed")
    print()
    print("Step 3: Restart Camera")
    print("   - Power cycle the camera")
    print("   - Wait 2-3 minutes for full boot")
    print("   - Try connecting again")
    print()
    print("Step 4: Check Network")
    print("   - Verify camera IP address is accessible")
    print("   - Check network adapter settings")
    print("   - Temporarily disable firewall for testing")
    print()
    print("Step 5: Reinstall Software (if needed)")
    print("   - Reinstall Phantom SDK")
    print("   - Update PyPhantom library: pip install --upgrade pyphantom")
    print("   - Update camera firmware if available")
    print()
    print("="*60)

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
                - save_format (str): 'cine', 'hdf5', or 'both' (default: 'cine')
                - hdf5_file_path (str): Path to existing HDF5 file from multi_scope_acquisition (required if save_format includes 'hdf5')
        """
        self.config = config
        
        # Initialize Phantom camera with better error handling
        try:
            print("Initializing Phantom camera connection...")
            self.ph = Phantom()
            print(f"Phantom library initialized successfully")
        except ValueError as e:
            if "Requested parameter is missing" in str(e):
                raise RuntimeError(
                    "Failed to initialize Phantom camera. This error typically indicates:\n"
                    "1. Camera is not connected or powered on\n"
                    "2. Camera drivers are not properly installed\n"
                    "3. Another application is using the camera\n"
                    "4. Camera configuration files are missing or corrupted\n\n"
                    "Troubleshooting steps:\n"
                    "- Ensure camera is connected via Ethernet and powered on\n"
                    "- Close any other applications using the camera (PCC, etc.)\n"
                    "- Restart the camera and wait for full boot\n"
                    "- Check network connectivity to camera\n"
                    "- Reinstall Phantom SDK if necessary\n\n"
                    f"Original error: {str(e)}"
                )
            else:
                raise RuntimeError(f"Failed to initialize Phantom camera: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error initializing Phantom camera: {str(e)}")
        
        # Verify camera connection
        try:
            camera_count = self.ph.camera_count
            print(f"Found {camera_count} Phantom camera(s)")
            
            if camera_count == 0:
                raise RuntimeError(
                    "No Phantom camera discovered. Please check:\n"
                    "1. Camera is powered on and fully booted\n"
                    "2. Ethernet connection is working\n"
                    "3. Camera IP address is accessible\n"
                    "4. No firewall blocking camera communication\n"
                    "5. Camera is not in use by another application"
                )
        except Exception as e:
            raise RuntimeError(f"Failed to check camera count: {str(e)}")
            
        # Connect to first available camera
        try:
            print("Connecting to camera...")
            self.cam = self.ph.Camera(0)
            print("Camera connection established")
        except Exception as e:
            raise RuntimeError(f"Failed to connect to camera: {str(e)}")
        
        # Configure camera settings
        try:
            self._configure_camera()
            print("Camera configured successfully")
        except Exception as e:
            raise RuntimeError(f"Failed to configure camera: {str(e)}")
        
        # Initialize HDF5 integration if needed
        if self.config.get('save_format', 'cine') in ['hdf5', 'both']:
            if 'hdf5_file_path' not in self.config:
                raise ValueError("hdf5_file_path is required when save_format includes 'hdf5'")
            try:
                self._initialize_hdf5_integration()
                print("HDF5 integration initialized")
            except Exception as e:
                raise RuntimeError(f"Failed to initialize HDF5 integration: {str(e)}")
        
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
        
        if not os.path.exists(self.hdf5_path):
            raise FileNotFoundError(f"HDF5 file not found: {self.hdf5_path}")
        
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
                
                print(f"FastCam configuration added to HDF5: {self.hdf5_path}")
            
            # Create FastCam group at root level for shot data
            if 'FastCam' not in f:
                f.create_group('FastCam')
                f['FastCam'].attrs['description'] = 'Phantom high-speed camera data'
                f['FastCam'].attrs['camera_type'] = 'Phantom'
                f['FastCam'].attrs['synchronized_with_scopes'] = True
        
    def record_cine(self):
        """Record a single cine file, waiting for trigger (traditional blocking method)."""
        print("Waiting for trigger... ", end='\r')
        
        # Use the new async methods for consistency
        self.start_recording_async()
        timestamp = self.wait_for_recording_completion()
        return timestamp
    
    def start_recording_async(self):
        """Start recording without waiting for completion (for parallel arming)."""
        print("Arming camera for trigger... ", end='')
        
        # Clear previous recordings and start new recording
        self.cam.record(cine=1, delete_all=True)
        print("armed")
        
    def wait_for_recording_completion(self):
        """Wait for recording to complete and return timestamp."""
        print("Waiting for camera trigger... ", end='\r')
        
        # Wait for recording to complete
        while not self.cam.partition_recorded(1):
            time.sleep(0.1)
        print("Camera recording complete")
        return time.time()
        
    def save_cine(self, shot_number, timestamp):
        """Save the recorded cine file with frame range and trigger timestamp.
        
        Args:
            shot_number (int): Current shot number for filename (0-based)
            timestamp (float): Recording timestamp
        """
        # Create Cine object
        rec_cine = cine.Cine.from_camera(self.cam, 1)
        
        # Set frame range
        frame_range = utils.FrameRange(self.config['pre_trigger_frames'], self.config['post_trigger_frames'])
        rec_cine.save_range = frame_range
        
        save_format = self.config.get('save_format', 'cine')
        
        if save_format in ['cine', 'both']:
            # Save as .cine file
            filename = f"{self.config['name']}_shot{shot_number+1:03d}_{timestamp}.cine"
            full_path = os.path.join(self.config['save_path'], filename)
            
            print(f"Saving to {filename}")
            rec_cine.save_non_blocking(filename=full_path)
            
            while rec_cine.save_percentage < 100:
                print(f"Saving: {rec_cine.save_percentage}%", end='\r')
                time.sleep(0.1)
                
            print(f"Save complete: {full_path}")
        
        if save_format in ['hdf5', 'both']:
            # Save to HDF5
            self._save_to_hdf5(rec_cine, shot_number, timestamp)
        
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
        
    def record_sequence(self):
        """Record the specified number of shots using traditional blocking method."""
        try:
            for shot in range(self.config['num_shots']):
                print(f"\nRecording shot {shot + 1}/{self.config['num_shots']}")
                timestamp = self.record_cine()
                self.save_cine(shot, timestamp)
                
        finally:
            self.cleanup()
    
    def record_sequence_async(self):
        """Record the specified number of shots using async arming method."""
        try:
            for shot in range(self.config['num_shots']):
                print(f"\nRecording shot {shot + 1}/{self.config['num_shots']} (async)")
                
                # Start recording (non-blocking)
                self.start_recording_async()
                
                # Wait for completion
                timestamp = self.wait_for_recording_completion()
                
                # Save the data
                self.save_cine(shot, timestamp)
                
        finally:
            self.cleanup()
    
    def record_single_shot(self, shot_number):
        """Record a single shot with specified shot number.
        
        Args:
            shot_number (int): Shot number (1-based) to match multi_scope_acquisition
        """
        print(f"Recording shot {shot_number}")
        timestamp = self.record_cine()
        self.save_cine(shot_number - 1, timestamp)  # Convert to 0-based for internal use
    

        
    def cleanup(self):
        """Clean up camera resources."""
        self.cam.close()
        self.ph.close()

def test_hdf5_data(hdf5_file_path):
    """
    Test function to read and verify HDF5 data created by PhantomRecorder.
    
    Args:
        hdf5_file_path (str): Path to the HDF5 file to test
    """
    print(f"\n=== Testing HDF5 Data: {hdf5_file_path} ===")
    
    if not os.path.exists(hdf5_file_path):
        print(f"Error: HDF5 file not found: {hdf5_file_path}")
        return False
    
    try:
        with h5py.File(hdf5_file_path, 'r') as f:
            # Check experiment metadata
            print("Experiment metadata:")
            for key, value in f.attrs.items():
                print(f"  {key}: {value}")
            
            # Check camera configuration
            if '/Control/FastCam' in f:
                print("\nCamera configuration:")
                fastcam_config = f['/Control/FastCam']
                for key, value in fastcam_config.attrs.items():
                    print(f"  {key}: {value}")
            
            # Check FastCam data
            if 'FastCam' in f:
                fastcam_group = f['FastCam']
                print(f"\nFastCam group attributes:")
                for key, value in fastcam_group.attrs.items():
                    print(f"  {key}: {value}")
                
                # List all shots
                shots = [key for key in fastcam_group.keys() if key.startswith('shot_')]
                print(f"\nFound {len(shots)} shots: {sorted(shots)}")
                
                # Examine first shot in detail
                if shots:
                    first_shot = sorted(shots)[0]
                    shot_group = fastcam_group[first_shot]
                    
                    print(f"\nDetailed info for {first_shot}:")
                    print(f"  Shot metadata:")
                    for key, value in shot_group.attrs.items():
                        print(f"    {key}: {value}")
                    
                    print(f"  Datasets:")
                    for dataset_name in shot_group.keys():
                        dataset = shot_group[dataset_name]
                        print(f"    {dataset_name}: {dataset.shape} {dataset.dtype}")
                        
                        # Show some statistics for frame data
                        if dataset_name == 'frames' and len(dataset) > 0:
                            first_frame = dataset[0]
                            print(f"      First frame stats: min={np.min(first_frame)}, max={np.max(first_frame)}, mean={np.mean(first_frame):.1f}")
                            if len(dataset) > 1:
                                last_frame = dataset[-1]
                                print(f"      Last frame stats: min={np.min(last_frame)}, max={np.max(last_frame)}, mean={np.mean(last_frame):.1f}")
                        
                        # Show time array info
                        elif dataset_name == 'time_array' and len(dataset) > 0:
                            print(f"      Time range: {dataset[0]:.6f} to {dataset[-1]:.6f} seconds")
                            if len(dataset) > 1:
                                dt = dataset[1] - dataset[0]
                                print(f"      Time step: {dt:.6f} seconds ({1/dt:.1f} Hz)")
            
            print(f"\n✓ HDF5 file structure is valid")
            return True
            
    except Exception as e:
        print(f"Error reading HDF5 file: {e}")
        import traceback
        traceback.print_exc()
        return False

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
        'num_shots': num_shots,
        'save_format': 'cine',
        'hdf5_file_path': test_hdf5_path
    }
    
    print("=== Phantom Camera Test Configuration ===")
    print(f"Experiment: {config['name']}")
    print(f"Cine files: {base_path}")
    print(f"Resolution: {config['resolution']}")
    print(f"Frame rate: {config['fps']} fps")
    print(f"Exposure: {config['exposure_us']} μs")
    print(f"Frames: {config['pre_trigger_frames']} to +{config['post_trigger_frames']}")
    print(f"Total frames per shot: {abs(config['pre_trigger_frames']) + config['post_trigger_frames']}")
    print(f"Number of shots: {config['num_shots']}")
    print(f"Save format: {config['save_format']}")
    print("=" * 45)
    
    try:
        # Check prerequisites before attempting initialization
        print("\nChecking Phantom camera prerequisites...")
        prereq_success, prereq_message = check_phantom_prerequisites()
        
        if not prereq_success:
            print(f"Prerequisites check failed: {prereq_message}")
            print("\nPlease resolve the issues above before running the camera test.")
            return
        
        print(f"✓ {prereq_message}")
        
        # Create recorder instance
        print("\nInitializing Phantom camera...")
        recorder = PhantomRecorder(config)
        
        print(f"\nStarting test recording of {config['num_shots']} shots...")
        print("Press Ctrl+C to stop early if needed")
        
        # Test traditional recording method
        print("\n=== Testing Traditional Recording ===")
        recorder.record_sequence()
        
        # Test async arming functionality with a fresh recorder instance
        print("\n=== Testing Async Arming ===")
        print("Testing start_recording_async() and wait_for_recording_completion()...")
        
        # Create a new recorder for async testing to avoid conflicts with cleaned up recorder
        async_config = config.copy()
        async_config['num_shots'] = 1  # Just one shot for async test
        async_recorder = PhantomRecorder(async_config)
        
        try:
            # Test async arming
            async_recorder.start_recording_async()
            print("Camera armed successfully")
            
            # Simulate waiting for trigger (in real use, external trigger would fire)
            print("Waiting for external trigger (simulated)...")
            time.sleep(2)  # Simulate trigger delay
            
            # Test completion
            timestamp = async_recorder.wait_for_recording_completion()
            print(f"Recording completed at timestamp: {timestamp}")
            
            # Save the test shot
            async_recorder.save_cine(0, timestamp)  # Use 0 for single async test shot
            print("Async test completed successfully")
            
        finally:
            async_recorder.cleanup()
        
        print(f"\n=== Recording Complete ===")
        print(f"Cine files saved in: {base_path}")
        
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
        
        # Show troubleshooting guide for common camera errors
        if any(error_msg in str(e).lower() for error_msg in [
            'requested parameter is missing',
            'failed to initialize phantom camera',
            'no phantom camera discovered',
            'failed to connect to camera'
        ]):
            print_troubleshooting_guide()
        
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
    print("\nTo run with custom settings, modify the parameters in the if __name__ == '__main__' section")

#===============================================================================================================================================
# Main Test Loop
#===============================================================================================================================================

if __name__ == '__main__':
    main(num_shots=1,  # Reduced to 1 shot for initial testing
         exposure_us=100,  # Increased exposure for better reliability
         fps=1000,  # Reduced frame rate for testing
         resolution=(256, 256),  # Keep resolution small for testing
         pre_trigger_frames=-50,  # Reduced frame count for testing
         post_trigger_frames=100,  # Reduced frame count for testing
         save_format='cine',  # Start with cine only for testing
         base_path=r"C:\temp\phantom_test",  # More accessible path
         experiment_name='phantom_test') 