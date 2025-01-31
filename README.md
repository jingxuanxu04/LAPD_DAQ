# LAPD_DAQ
 Data acquisition script using Ethernet motor and LeCroy scope as digitizer on LAPD.
Modified from Scope_DAQ used on process plasma chamber

## HDF5 Data Structure
The data acquisition script creates HDF5 files with the following structure:

```
experiment_name.hdf5/
├── attrs/
│   ├── description          # Overall experiment description
│   ├── creation_time        # Time when file was created
│   └── source_code          # Python scripts used to create the file
│       ├── Data_Run_0D.py
│       ├── multi_scope_acquisition.py
│       └── LeCroy_Scope.py
│
├── magnetron/              # First scope group
│   ├── attrs/
│   │   ├── description     # Scope description
│   │   ├── ip_address      # Scope IP address
│   │   ├── scope_type      # Scope identification string
│   │   └── external_delay(ms)  # External delay in milliseconds
│   │
│   ├── time_array          # Time array for all channels
│   │   ├── attrs/
│   │   │   ├── units       # "seconds"
│   │   │   ├── description # "Time array for all channels" or "Time array for all channels; data saved in sequence mode"
│   │   │   └── dtype       # Data type of time array
│   │
│   ├── shot_0/            # First shot data
│   │   ├── attrs/
│   │   │   └── acquisition_time
│   │   │
│   │   ├── C1_data        # Channel 1 voltage data (1D array for normal mode, 2D array for sequence mode)
│   │   │   └── attrs/
│   │   │       ├── description  # Channel description
│   │   │       └── dtype       # Data type of voltage data
│   │   ├── C1_header      # Channel 1 binary header
│   │   │   └── attrs/
│   │   │       └── description
│   │   ├── C2_data        # Channel 2 voltage data
│   │   ├── C2_header      # Channel 2 binary header
│   │   └── ...            # Additional channels
│   │
│   ├── shot_1/            # Second shot data
│   └── ...                # Additional shots
│
├── x-ray_dipole/          # Second scope group
│   └── ...                # Same structure as above
│
└── Bdot/                  # Third scope group
    └── ...                # Same structure as above
```

### Key Features
1. **Root Level**
   - Contains experiment metadata and scope groups
   - Stores source code used to create the file
   - Includes experiment description and creation time

2. **Scope Groups**
   - Each scope has its own group with metadata
   - Time array stored once per scope (in seconds)
   - External delay and scope configuration information
   - Supports both normal and sequence mode acquisition

3. **Shot Data**
   - Numbered shots under each scope group
   - Each shot contains:
     - Voltage data for each channel (1D array for normal mode, 2D array for sequence mode)
     - Binary header data for each channel
     - Channel descriptions and data types
     - Acquisition timestamp

4. **Time Arrays**
   - Stored in seconds in HDF5 file
   - Used in milliseconds for plotting
   - Saved once after first acquisition
   - Reused for all subsequent shots
   - Includes sequence mode information in attributes

5. **Sequence Mode Support**
   - Automatically detects and handles sequence mode acquisition
   - Stores sequence data as 2D arrays (segments × samples)
   - Optimized chunking for efficient data access
   - Maintains backward compatibility with normal mode

### Reading the Data
Example Python code to read the data:
```python
import h5py
import numpy as np

# Open the HDF5 file
with h5py.File('experiment_name.hdf5', 'r') as f:
    # Read experiment description
    description = f.attrs['description']
    
    # Access source code
    source_code = eval(f.attrs['source_code'])
    
    # Read scope data
    for scope_name in f.keys():
        scope_group = f[scope_name]
        
        # Get time array (in seconds)
        time_array = scope_group['time_array'][:]
        is_sequence = 'sequence mode' in scope_group['time_array'].attrs['description']
        
        # Read shots
        for shot_name in [k for k in scope_group.keys() if k.startswith('shot_')]:
            shot_group = scope_group[shot_name]
            
            # Read channel data
            for channel in [k for k in shot_group.keys() if k.endswith('_data')]:
                data = shot_group[channel][:]
                description = shot_group[channel].attrs['description']
                
                if is_sequence:
                    num_segments = data.shape[0]
                    samples_per_segment = data.shape[1]
                    print(f"Sequence data: {num_segments} segments, {samples_per_segment} samples each")
```

### Notes
- Time values are stored in seconds but displayed in milliseconds in plots
- Binary headers contain scope-specific metadata for each channel
- Source code is preserved with data for reproducibility
- Each scope can have different time arrays based on its settings
- Sequence mode data is stored as 2D arrays with optimized chunking
- Data compression and chunking are automatically optimized based on acquisition mode
