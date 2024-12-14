import numpy as np
import matplotlib.pyplot as plt
from LeCroy_Scope import LeCroy_Scope
import h5py
import time
import os

#===============================================================================================================================================

def acquire_from_scope(scope_name, scope_ip, NTimes):
    """Acquire data from a single scope"""
    data = {}
    headers = {}

    with LeCroy_Scope(scope_ip, verbose=False) as scope:
        scope.set_trigger_mode('STOP')
        traces = scope.displayed_traces()        
        for tr in traces:
            try:
                data[tr] = scope.acquire(tr)[0:NTimes]
                headers[tr] = np.void(scope.header_bytes())

            except Exception as e:
                print(f"Error acquiring {tr} from {scope_name}: {e}")
                continue
        scope.set_trigger_mode('NORM')

        if scope.time_array is None:
            time_ds = scope_group.create_dataset('time_array', data=time_array)
            time_ds.attrs['units'] = 'seconds'
            time_ds.attrs['description'] = 'Time array for all channels'
    return traces, data, headers

class MultiScopeAcquisition:
    def __init__(self, scope_ips, num_loops=10, save_path='multi_scope_data.hdf5', 
                 external_delays=None):
        """
        Args:
            scope_ips: dict of scope names and IP addresses
            num_loops: number of shots to acquire
            save_path: path to save HDF5 file
            file_description: description of the experiment
            external_delays: dict of scope names and their external delays in seconds
        """
        self.scope_ips = scope_ips
        self.num_loops = num_loops
        self.save_path = save_path
        self.external_delays = external_delays if external_delays else {}
        self.scopes = {}
        self.figures = {}
        
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
    
    def initialize_hdf5(self):
        """Initialize HDF5 file with scope information
        return time arrays for each scope"""
        time_dic = {}
        with h5py.File(self.save_path, 'a') as f:
            f.attrs['description'] = self.get_experiment_description()
            f.attrs['creation_time'] = time.ctime()
            
            # Create scope groups with their descriptions
            for scope_name in self.scope_ips.keys():
                if scope_name not in f:
                    scope_group = f.create_group(scope_name)
                    scope_group.attrs['description'] = self.get_scope_description(scope_name)
                    scope_group.attrs['ip_address'] = self.scope_ips[scope_name]
                    scope_group.attrs['scope_type'] = self.scopes[scope_name].idn_string
                    scope_group.attrs['external_delay(ms)'] = self.external_delays.get(scope_name, '')

                    

    def update_hdf5(self, all_data, shot_num):
        """Update HDF5 file with acquired data"""
        with h5py.File(self.save_path, 'a') as f:
            # Save data for each scope
            for scope_name, (traces, data, headers, time_array) in all_data.items():
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

    def update_plots(self, time_dic, all_data, shot_num):
        """Update plots for all scopes"""
        for scope_name, (traces, data, _,) in all_data.items():
            fig = self.figures[scope_name]
            
            for i, tr in enumerate(traces):
                if tr in data:
                    ax = fig.add_subplot(self.num_loops, 1, shot_num + 1)
                    # Convert to milliseconds only for plotting
                    ax.plot(time_dic[scope_name] * 1000, data[tr])
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
            # Initialize plots
            plt.ion()  # Interactive mode on
            time_dic = self.initialize_hdf5()
            
            for shot in range(self.num_loops):
                print(f"Starting acquisition shot {shot+1}/{self.num_loops}")
                start_time = time.time()
                
                all_data = {}
                
                # Acquire data from each scope sequentially
                for name, ip in self.scope_ips.items():
                    print(time_dic.keys())
                    NTimes = time_dic[name].size
                    traces, data, headers = acquire_from_scope(name, ip, NTimes)
                    all_data[name] = (traces, data, headers)
                
                # Save data
                self.save_to_hdf5(all_data, shot)
                
                # Update plots
                self.update_plots(time_dic, all_data, shot)
                
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
