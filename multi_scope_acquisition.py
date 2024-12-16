import numpy as np
import matplotlib.pyplot as plt
from LeCroy_Scope import LeCroy_Scope, WAVEDESC_SIZE
import h5py
import time
import os
import struct

#===============================================================================================================================================
def acquire_from_scope(scope, scope_name, first_acquisition=False):
    """Acquire data from a single scope with optimized speed
    Args:
        scope: LeCroy_Scope instance
        scope_name: Name of the scope
        first_acquisition: If True, return time array as well
    Returns:
        traces: List of trace names that have valid data
        data: Dict of trace data
        headers: Dict of trace headers
        time_array: Time array (only if first_acquisition=True)
    """
    st_time = time.time() # for checking acquisition time

    # Check if scope is in STOP mode before acquiring
    MAX_RETRIES = 100  # Maximum number of retries
    RETRY_DELAY = 0.05  # Delay between retries in seconds
    
    for retry in range(MAX_RETRIES):
        current_mode = scope.set_trigger_mode('')  # Get current mode without changing it
        if current_mode.strip() == 'STOP':
            break
        # if retry == 0:  # Only print first time
        #     print(f"Waiting for {scope_name} trigger mode to become STOP (currently {current_mode})")
        time.sleep(RETRY_DELAY)
    else:  # Loop completed without finding STOP mode
        print(f"Warning: Timeout waiting for {scope_name} trigger mode to become STOP after {MAX_RETRIES * RETRY_DELAY:.1f}s")
        if first_acquisition:
            return [], {}, {}, None
        return [], {}, {}

    data = {}
    headers = {}
    time_array = None
    active_traces = []  # List to store only traces that have data
    TIMEOUT = 10  # Timeout in seconds for acquisition

    traces = scope.displayed_traces()
    
    for tr in traces:
        try:
            # Set timeout for acquisition
            scope.timeout = TIMEOUT * 1000  # Convert to ms
            
            # Get raw data using acquire_raw (which now also parses header)
            trace_bytes = scope.acquire_raw(tr)
            
            # Get header bytes for storage
            headers[tr] = np.void(trace_bytes[15:15+WAVEDESC_SIZE])
            
            # Get data indices from already parsed header
            NSamples, ndx0, ndx1 = scope.parse_header(trace_bytes)
            
            # Parse the actual waveform data
            if scope.hdr.comm_type == 1:  # data returned in words
                wdata = struct.unpack(str(NSamples)+'h', trace_bytes[ndx0:ndx1])
                trace_data = np.array(wdata) * scope.hdr.vertical_gain - scope.hdr.vertical_offset
            else:  # data returned in bytes
                cdata = struct.unpack(str(NSamples)+'b', trace_bytes[ndx0:ndx1])
                trace_data = np.array(cdata) * scope.hdr.vertical_gain - scope.hdr.vertical_offset
            
            # Store the data
            data[tr] = trace_data
            active_traces.append(tr)
            
            # Get time array from first valid trace if needed
            if first_acquisition and time_array is None:
                time_array = scope.time_array()

        except Exception as e:
            if "timeout" in str(e).lower():
                print(f"Timeout acquiring {tr} from {scope_name} after {TIMEOUT}s")
            elif "NSamples = 0" in str(e):
                print(f"Skipping {tr} from {scope_name}: Channel is displayed but not active")
            else:
                print(f"Error acquiring {tr} from {scope_name}: {e}")
            continue
    
    # Print acquisition time
    print(f"Acquisition from {scope_name} completed in {time.time() - st_time:.2f} seconds")

    if first_acquisition:
        return active_traces, data, headers, time_array
    return active_traces, data, headers

class MultiScopeAcquisition:
    def __init__(self, scope_ips, num_loops=10, save_path='multi_scope_data.hdf5', 
                 external_delays=None):
        """
        Args:
            scope_ips: dict of scope names and IP addresses
            num_loops: number of shots to acquire
            save_path: path to save HDF5 file
            external_delays: dict of scope names and their external delays in seconds
        """
        self.scope_ips = scope_ips
        self.num_loops = num_loops
        self.save_path = save_path
        self.external_delays = external_delays if external_delays else {}
        self.scopes = {}
        self.figures = {}
        self.time_arrays = {}  # Store time arrays for each scope
        
        # Just create figures
        for name in self.scope_ips:
            try:
                self.figures[name] = plt.figure(figsize=(12, 8))
                self.figures[name].canvas.manager.set_window_title(f'Scope: {name}')
            except Exception as e:
                print(f"Error creating figure for {name}: {e}")
                self.cleanup()
                raise

    def cleanup(self):
        """Clean up resources"""
        # Close all scope connections
        for scope in self.scopes.values():
            try:
                scope.__exit__(None, None, None)
            except Exception as e:
                print(f"Error closing scope: {e}")
        
        # Close all figures
        for fig in self.figures.values():
            try:
                plt.close(fig)
            except Exception as e:
                print(f"Error closing figure: {e}")
        
        self.scopes.clear()
        self.figures.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def get_scope_description(self, scope_name):
        from Data_Run_0D import get_scope_description
        return get_scope_description(scope_name)
    
    def get_channel_description(self, channel_name):
        from Data_Run_0D import get_channel_description
        return get_channel_description(channel_name)
    
    def get_experiment_description(self):
        from Data_Run_0D import get_experiment_description
        return get_experiment_description()
    
    def get_script_contents(self):
        """Read the contents of the Python scripts used to create the HDF5 file"""
        script_contents = {}
        
        # Get the directory of the current script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # List of scripts to include
        scripts = ['Data_Run_0D.py', 'multi_scope_acquisition.py']
        
        for script in scripts:
            script_path = os.path.join(current_dir, script)
            try:
                with open(script_path, 'r') as f:
                    script_contents[script] = f.read()
            except Exception as e:
                print(f"Warning: Could not read {script}: {str(e)}")
                script_contents[script] = f"Error reading file: {str(e)}"
        
        return script_contents
    
    def initialize_hdf5(self):
        """Initialize HDF5 file with scope information"""
        with h5py.File(self.save_path, 'a') as f:
            # Add experiment description and creation time
            f.attrs['description'] = self.get_experiment_description()
            f.attrs['creation_time'] = time.ctime()
            
            # Add Python scripts used to create the file
            script_contents = self.get_script_contents()
            f.attrs['source_code'] = str(script_contents)
            
            # Create scope groups with their descriptions
            for scope_name in self.scope_ips:
                if scope_name not in f:
                    scope_group = f.create_group(scope_name)


    def initialize_scopes(self):
        """Initialize scopes and get time arrays on first acquisition"""
        all_data = {}
        active_scopes = []
        
        for name, ip in self.scope_ips.items():
            print(f"\nInitializing {name}...")
            
            try:
                # Create scope instance
                self.scopes[name] = LeCroy_Scope(ip, verbose=False)
                scope = self.scopes[name]
                
                # Optimize scope settings for faster acquisition
                scope.scope.chunk_size = 4*1024*1024  # Increase chunk size to 4MB for faster transfer
                scope.scope.timeout = 30000  # 30 second timeout
                
                # Set trigger mode
                scope.set_trigger_mode('SINGLE')
                
                # Get initial data and time arrays
                traces, data, headers, time_array = acquire_from_scope(scope, name, first_acquisition=True)
                
                if traces:  # Only save if we got valid data
                    self.save_time_arrays(name, time_array)
                    active_scopes.append(name)
                    all_data[name] = (traces, data, headers)
                    print(f"Successfully initialized {name}")
                else:
                    print(f"Warning: Could not initialize {name} - no traces returned")
                    self.cleanup_scope(name)
            except Exception as e:
                print(f"Error initializing {name}: {str(e)}")
                self.cleanup_scope(name)
                continue
        
        return all_data, active_scopes

    def cleanup_scope(self, name):
        """Clean up resources for a specific scope"""
        if name in self.scopes:
            try:
                self.scopes[name].__exit__(None, None, None)
                del self.scopes[name]
            except Exception as e:
                print(f"Error closing scope {name}: {e}")

    def acquire_shot(self, active_scopes, shot_num):
        """Acquire data from all active scopes for one shot"""
        all_data = {}
        failed_scopes = []
        
        for name in active_scopes:
            print(f"\nAcquiring data from {name}...")
            scope = self.scopes[name]
            
            try:
                traces, data, headers = acquire_from_scope(scope, name, first_acquisition=False)
                if traces:
                    all_data[name] = (traces, data, headers)
                else:
                    print(f"Warning: No valid data from {name} for shot {shot_num+1}")
                    failed_scopes.append(name)
            except Exception as e:
                print(f"Error acquiring from {name}: {str(e)}")
                failed_scopes.append(name)

            # start triggering again as soon as all traces are acquired
            scope.set_trigger_mode('SINGLE')
        
        # Remove failed scopes from active list
        for name in failed_scopes:
            active_scopes.remove(name)
        
        return all_data

    def save_time_arrays(self, scope_name, time_array):
        """Save time array for a scope to HDF5 file
        
        Args:
            scope_name: Name of the scope
            time_array: Time array to save
        """
        with h5py.File(self.save_path, 'a') as f:
            scope_group = f[scope_name]
            # Store the time array for this scope
            self.time_arrays[scope_name] = time_array
            
            # Check if time_array already exists
            if 'time_array' in scope_group:
                raise RuntimeError(f"Time array already exists for scope {scope_name}. This should not happen.")
            
            # Save to HDF5
            time_ds = scope_group.create_dataset('time_array', data=time_array, dtype='float64')
            time_ds.attrs['units'] = 'seconds'
            time_ds.attrs['description'] = 'Time array for all channels'
            time_ds.attrs['dtype'] = str(time_array.dtype)

    def update_hdf5(self, all_data, shot_num):
        """Update HDF5 file with acquired data using optimized settings"""
        with h5py.File(self.save_path, 'a') as f:
            # Save data for each scope
            for scope_name, (traces, data, headers) in all_data.items():
                scope_group = f[scope_name]
                
                # Check if shot group already exists
                shot_name = f'shot_{shot_num}'
                if shot_name in scope_group:
                    raise RuntimeError(f"Shot {shot_num} already exists for scope {scope_name}. This should not happen.")
                
                # Create shot group with optimized settings
                shot_group = scope_group.create_group(shot_name)
                shot_group.attrs['acquisition_time'] = time.ctime()
                
                # Save trace data and headers with optimized chunk size and compression
                for tr in traces:
                    if tr in data:
                        # Convert data to appropriate dtype if needed (e.g., uint16 for 12-bit data)
                        trace_data = np.asarray(data[tr])
                        if trace_data.dtype != np.uint16:
                            trace_data = trace_data.astype(np.uint16)
                        
                        # Calculate optimal chunk size (aim for ~1MB chunks)
                        chunk_size = min(len(trace_data), 512*1024)  # 512K samples per chunk
                        
                        # Create dataset with optimized settings
                        data_ds = shot_group.create_dataset(
                            f'{tr}_data', 
                            data=trace_data,
                            chunks=(chunk_size,),
                            compression='gzip',
                            compression_opts=9,  # Maximum compression
                            shuffle=True,  # Helps with compression of binary data
                            fletcher32=True  # Add checksum for data integrity
                        )
                        
                        # Store header as binary data
                        header_ds = shot_group.create_dataset(f'{tr}_header', data=headers[tr])
                        
                        # Add channel descriptions and metadata
                        data_ds.attrs['description'] = self.get_channel_description(tr)
                        data_ds.attrs['dtype'] = str(trace_data.dtype)
                        data_ds.attrs['original_size'] = len(trace_data)
                        data_ds.attrs['voltage_scale'] = '12-bit centered at 0V, ±10V range'
                        header_ds.attrs['description'] = f'Binary header data for {tr}'

    def update_plots(self, all_data, shot_num):
        """Update plots for all scopes with optimized data handling"""
        MAX_PLOT_POINTS = 10000  # Maximum number of points to plot
        
        for scope_name, (traces, data, _) in all_data.items():
            if not traces:  # Skip if no valid traces for this scope
                continue
            
            if scope_name not in self.time_arrays:
                print(f"Warning: No time array found for {scope_name}")
                continue
            
            fig = self.figures[scope_name]
            time_array = self.time_arrays[scope_name]
            
            try:
                # Calculate optimal downsample factor
                n_points = len(time_array)
                if n_points == 0:
                    print(f"Warning: Empty time array for {scope_name}")
                    continue
                
                downsample = max(1, n_points // MAX_PLOT_POINTS)
                
                # Pre-calculate downsampled time array
                plot_time = time_array[::downsample]
                
                ax = fig.add_subplot(self.num_loops, 1, shot_num + 1)
                
                # Plot each trace with optimized downsampling
                for tr in traces:
                    if tr not in data:
                        print(f"Warning: No data for trace {tr}")
                        continue
                    
                    # Convert binary data to voltage values if needed
                    trace_data = np.asarray(data[tr])
                    if trace_data.dtype == np.uint16:
                        # Convert 12-bit data to voltage (-10V to +10V range)
                        trace_data = (trace_data.astype(float) - 2048) * (20.0/4096)
                    
                    # Efficient downsampling using array slicing
                    plot_data = trace_data[::downsample]
                    
                    if len(plot_data) != len(plot_time):
                        print(f"Warning: Data length mismatch for {tr}")
                        continue
                    
                    # Plot in milliseconds
                    ax.plot(plot_time * 1000, plot_data, label=tr)
                
                ax.set_title(f'Shot {shot_num+1}')
                ax.set_xlabel('Time (ms)')
                ax.set_ylabel('Voltage (V)')
                ax.grid(True)
                if len(traces) > 1:
                    ax.legend()
                
                # Optimize figure updates
                fig.tight_layout()
                fig.canvas.draw()
                fig.canvas.flush_events()
                
            except Exception as e:
                print(f"Error updating plot for {scope_name}: {e}")
                continue
            
        plt.pause(0.01)  # Single pause after all plots are updated

    def run_acquisition(self):
        """Main acquisition loop with clear separation between initialization and acquisition"""
        try:
            # Initialize plots
            plt.ion()
            
            # Initialize HDF5 file structure
            print("Initializing HDF5 file...")
            self.initialize_hdf5()
            
            # First shot: Initialize scopes and get time arrays
            print("\nStarting initial acquisition (shot 1)...")
            start_time = time.time()
            
            all_data, active_scopes = self.initialize_scopes()
            
            if not active_scopes:
                raise RuntimeError("No valid data found from any scope. Aborting acquisition.")
            
            # Save and plot first shot
            self.update_hdf5(all_data, 0)
            self.update_plots(all_data, 0)
            print(f"Initial acquisition completed in {time.time() - start_time:.2f} seconds")
            
            # Subsequent shots
            for shot in range(1, self.num_loops):
                print(f"\nStarting acquisition shot {shot+1}/{self.num_loops}")
                start_time = time.time()
                
                # Acquire data from all active scopes
                all_data = self.acquire_shot(active_scopes, shot)
                
                if not all_data:
                    print(f"Warning: No valid data acquired for shot {shot+1}")
                    continue
                
                # Save and plot
                self.update_hdf5(all_data, shot)
                self.update_plots(all_data, shot)
                
                print(f"Shot {shot+1} completed in {time.time() - start_time:.2f} seconds")
            
            # Keep figures open after acquisition
            plt.show(block=False)
            input("Press Enter to close figures and exit...")
            
        except Exception as e:
            print(f"Error during acquisition: {str(e)}")
            raise
            
        finally:
            with h5py.File(self.save_path, 'a') as f:
                for scope_name in self.scope_ips:
                    scope_group = f[scope_name]
                    scope_group.attrs['description'] = self.get_scope_description(scope_name)
                    scope_group.attrs['ip_address'] = self.scope_ips[scope_name]
                    scope_group.attrs['scope_type'] = self.scopes[scope_name].idn_string
                    scope_group.attrs['external_delay(ms)'] = self.external_delays.get(scope_name, '')
            plt.close('all')  # Ensure all figures are closed