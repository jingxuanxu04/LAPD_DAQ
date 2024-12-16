import numpy as np
import matplotlib.pyplot as plt
from LeCroy_Scope import LeCroy_Scope
import h5py
import time
import os

#===============================================================================================================================================

def acquire_from_scope(scope_name, scope_ip, first_acquisition=False):
    """Acquire data from a single scope
    Args:
        scope_name: Name of the scope
        scope_ip: IP address of the scope
        first_acquisition: If True, return time array as well
    Returns:
        traces: List of trace names
        data: Dict of trace data
        headers: Dict of trace headers
        time_array: Time array (only if first_acquisition=True)
    """
    data = {}
    headers = {}
    time_array = None

    with LeCroy_Scope(scope_ip, verbose=False) as scope:
        scope.set_trigger_mode('STOP')
        traces = scope.displayed_traces()        
        for tr in traces:
            try:
                data[tr] = scope.acquire(tr)
                headers[tr] = np.void(scope.header_bytes())
                if first_acquisition and time_array is None:
                    time_array = scope.time_array  # Get time array on first acquisition

            except Exception as e:
                print(f"Error acquiring {tr} from {scope_name}: {e}")
                continue
        scope.set_trigger_mode('NORM')

    if first_acquisition:
        return traces, data, headers, time_array
    return traces, data, headers

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
        
        # Initialize scopes and figures
        for name, ip in self.scope_ips.items():
            self.scopes[name] = LeCroy_Scope(ip, verbose=False)
            self.figures[name] = plt.figure(figsize=(12, 8))
            self.figures[name].suptitle(f'{name} Traces')

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
        """Initialize HDF5 file with scope information and time arrays"""
        with h5py.File(self.save_path, 'a') as f:
            # Add experiment description and creation time
            f.attrs['description'] = self.get_experiment_description()
            f.attrs['creation_time'] = time.ctime()
            
            # Add Python scripts used to create the file
            script_contents = self.get_script_contents()
            f.attrs['source_code'] = str(script_contents)
            
            # Create scope groups with their descriptions
            for scope_name, ip in self.scope_ips.items():
                if scope_name not in f:
                    scope_group = f.create_group(scope_name)
                    scope_group.attrs['description'] = self.get_scope_description(scope_name)
                    scope_group.attrs['ip_address'] = self.scope_ips[scope_name]
                    scope_group.attrs['scope_type'] = self.scopes[scope_name].idn_string
                    scope_group.attrs['external_delay(ms)'] = self.external_delays.get(scope_name, '')

    def save_time_arrays(self):
        """Save time arrays to HDF5 file"""
        with h5py.File(self.save_path, 'a') as f:
            for scope_name, time_array in self.time_arrays.items():
                scope_group = f[scope_name]
                if 'time_array' not in scope_group:
                    time_ds = scope_group.create_dataset('time_array', data=time_array)
                    time_ds.attrs['units'] = 'seconds'
                    time_ds.attrs['description'] = 'Time array for all channels'

    def update_hdf5(self, all_data, shot_num):
        """Update HDF5 file with acquired data"""
        with h5py.File(self.save_path, 'a') as f:
            # Save data for each scope
            for scope_name, (traces, data, headers) in all_data.items():
                scope_group = f[scope_name]
                
                # Create shot group within scope
                shot_group = scope_group.create_group(f'shot_{shot_num}')
                shot_group.attrs['acquisition_time'] = time.ctime()
                
                # Save trace data and headers with descriptions
                for tr in traces:
                    if tr in data:
                        data_ds = shot_group.create_dataset(f'{tr}_data', data=data[tr])
                        header_ds = shot_group.create_dataset(f'{tr}_header', data=headers[tr])
                        
                        # Add channel descriptions and metadata
                        data_ds.attrs['description'] = self.get_channel_description(tr)
                        header_ds.attrs['description'] = f'Binary header data for {tr}'

    def update_plots(self, all_data, shot_num):
        """Update plots for all scopes"""
        for scope_name, (traces, data, _) in all_data.items():
            fig = self.figures[scope_name]
            time_array = self.time_arrays[scope_name]
            
            for i, tr in enumerate(traces):
                if tr in data:
                    ax = fig.add_subplot(self.num_loops, 1, shot_num + 1)
                    # Convert to milliseconds only for plotting
                    ax.plot(time_array * 1000, data[tr])
                    ax.set_title(f'{tr} - Shot {shot_num+1}')
                    ax.set_xlabel('Time (ms)')
                    ax.set_ylabel('Voltage (V)')
                    ax.grid(True)
            
            fig.tight_layout()
            plt.draw()
            plt.pause(0.01)

    def run_acquisition(self):
        """Main acquisition loop"""
        try:
            # Initialize plots and HDF5 file
            plt.ion()  # Interactive mode on
            self.initialize_hdf5()
            
            # First acquisition to get time arrays
            print("Performing initial acquisition to get time arrays...")
            for name, ip in self.scope_ips.items():
                traces, data, headers, time_array = acquire_from_scope(name, ip, first_acquisition=True)
                self.time_arrays[name] = time_array
            
            # Save time arrays to HDF5
            self.save_time_arrays()
            
            # Main acquisition loop
            for shot in range(self.num_loops):
                print(f"Starting acquisition shot {shot+1}/{self.num_loops}")
                start_time = time.time()
                
                all_data = {}
                
                # Acquire data from each scope sequentially
                for name, ip in self.scope_ips.items():
                    traces, data, headers = acquire_from_scope(name, ip)
                    all_data[name] = (traces, data, headers)
                
                # Save data and update plots
                self.update_hdf5(all_data, shot)
                self.update_plots(all_data, shot)
                
                print(f"Shot {shot+1} completed in {time.time() - start_time:.2f} seconds")
                
            plt.ioff()  # Interactive mode off
            plt.show()  # Keep figures open
            
        finally:
            # Cleanup
            for fig in self.figures.values():
                plt.close(fig)

#===============================================================================================================================================
#<o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o> <o>
#===============================================================================================================================================

if __name__ == '__main__':
    scope_ips = {
        'Bdot': '192.168.7.63',
        'magnetron': '192.168.7.64',
        'x-ray_dipole': '192.168.7.66'
    }
    
    external_delays = {
        'main_scope': 0,
        'magnetron': 0,    
        'x-ray': 0      
    }
    
    save_path = r"E:\Shadow data\Energetic_Electron_Ring\test.hdf5"

    # Run acquisition
    acquisition = MultiScopeAcquisition(
        scope_ips=scope_ips,
        num_loops=1,
        save_path=save_path,
        external_delays=external_delays
    )
    
    acquisition.run_acquisition()
