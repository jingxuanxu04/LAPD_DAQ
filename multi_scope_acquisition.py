import numpy as np
import matplotlib.pyplot as plt
from LeCroy_Scope import LeCroy_Scope
import h5py
import time
import multiprocessing as mp
from multiprocessing import Process, Manager, Lock
import os

class MultiScopeAcquisition:
    def __init__(self, scope_ips, num_loops=10, save_path='multi_scope_data.hdf5', 
                 file_description='', external_delays=None):
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
        self.file_description = file_description
        self.external_delays = external_delays if external_delays else {}
        self.scopes = {}
        self.figures = {}
        self.manager = Manager()
        self.data_lock = Lock()
        
        # Initialize scopes and figures
        for name, ip in self.scope_ips.items():
            self.scopes[name] = LeCroy_Scope(ip, verbose=False)
            self.figures[name] = plt.figure(figsize=(12, 8))
            self.figures[name].suptitle(f'{name} Traces')

    def acquire_from_scope(self, scope_name, return_dict):
        """Process worker to acquire data from a single scope"""
        scope = self.scopes[scope_name]
        traces = scope.displayed_traces()
        data = {}
        headers = {}
        time_array = None
        
        for tr in traces:
            try:
                data[tr] = scope.acquire(tr)
                headers[tr] = scope.header_bytes()
                # Get time array from scope after first acquisition
                if time_array is None:
                    time_array = scope.time_array()  # Store in seconds
            except Exception as e:
                print(f"Error acquiring {tr} from {scope_name}: {e}")
                continue
        
        # Store results in shared dictionary
        return_dict[scope_name] = (traces, data, headers, time_array)

    def save_to_hdf5(self, all_data, shot_num):
        """Save acquired data to HDF5 file with reorganized structure"""
        with self.data_lock:
            with h5py.File(self.save_path, 'a') as f:
                # Add file description if this is the first shot
                if shot_num == 0:
                    f.attrs['description'] = self.file_description
                    f.attrs['creation_time'] = time.ctime()
                    
                    # Create scope groups with their descriptions on first shot
                    for scope_name in self.scope_ips.keys():
                        if scope_name not in f:
                            scope_group = f.create_group(scope_name)
                            scope_group.attrs['description'] = self.get_scope_description(scope_name)
                            scope_group.attrs['ip_address'] = self.scope_ips[scope_name]
                            scope_group.attrs['scope_type'] = self.scopes[scope_name].idn_string
                            scope_group.attrs['external_delay(ms)'] = self.external_delays.get(scope_name, '')
                
                # Save data for each scope
                for scope_name, (traces, data, headers, time_array) in all_data.items():
                    scope_group = f[scope_name]
                    
                    # Save time array only once per scope
                    if 'time_array' not in scope_group:
                        time_ds = scope_group.create_dataset('time_array', data=time_array)
                        time_ds.attrs['units'] = 'seconds'
                        time_ds.attrs['description'] = 'Time array for all channels'
                    
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
                            data_ds.attrs['units'] = 'Volts'
                            header_ds.attrs['description'] = f'Binary header data for {tr}'

    def update_plots(self, all_data, shot_num):
        """Update plots for all scopes"""
        for scope_name, (traces, data, _, time_array) in all_data.items():
            fig = self.figures[scope_name]
            
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
            # Initialize plots
            plt.ion()  # Interactive mode on
            
            for shot in range(self.num_loops):
                print(f"Starting acquisition shot {shot+1}/{self.num_loops}")
                start_time = time.time()
                
                # Shared dictionary for process results
                return_dict = self.manager.dict()
                
                # Create and start processes for each scope
                processes = []
                for name in self.scopes.keys():
                    p = Process(target=self.acquire_from_scope, 
                              args=(name, return_dict))
                    processes.append(p)
                    p.start()
                
                # Wait for all processes to complete
                for p in processes:
                    p.join()
                
                # Convert manager dict to regular dict for further processing
                all_data = dict(return_dict)
                
                # Save data
                self.save_to_hdf5(all_data, shot)
                
                # Update plots
                self.update_plots(all_data, shot)
                
                print(f"Shot {shot+1} completed in {time.time() - start_time:.2f} seconds")
                
            plt.ioff()  # Interactive mode off
            plt.show()  # Keep figures open
            
        finally:
            # Cleanup
            for scope in self.scopes.values():
                scope.set_trigger_mode('STOP')
            
            for fig in self.figures.values():
                plt.close(fig)

if __name__ == '__main__':
    mp.freeze_support()
    
    # User input
    scope_ips = {
        'main_scope': '192.168.7.63',
        'magnetron': '192.168.7.64',
        'timing': '192.168.7.65'
    }
    
    external_delays = {
        'main_scope': 0.0,      # No delay
        'magnetron': 1.5e-6,    # 1.5 µs delay
        'timing': -0.5e-6       # -0.5 µs delay
    }
    
    save_path = 'multi_scope_data.hdf5'
    file_description = '''Multi-scope data acquisition for plasma experiment.
    Main scope: Probe diagnostics
    Magnetron scope: RF source measurements
    Timing scope: Trigger signals
    Experiment date: 2024-01-24
    Operator: User Name'''

    # Run acquisition
    acquisition = MultiScopeAcquisition(
        scope_ips=scope_ips,
        num_loops=10,
        save_path=save_path,
        file_description=file_description,
        external_delays=external_delays
    )
    
    acquisition.run_acquisition() 