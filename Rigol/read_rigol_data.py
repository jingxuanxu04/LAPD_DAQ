# -*- coding: utf-8 -*-
"""
Read Rigol DHO800/DHO900 scope data files
Enhanced to support both old and new shot-based HDF5 formats

@author: Converted for Rigol DHO by GitHub Copilot
"""

import numpy as np
import h5py
import os
from datetime import datetime
from Rigol_Scope_Header import RigolScopeHeader

#======================================================================================

def decode_rigol_header_info(hdr_data):
    """Decode Rigol header information (mirrors decode_header_info)"""
    try:
        if isinstance(hdr_data, bytes):
            # Try to decode as text first (preamble string)
            try:
                text_data = hdr_data.decode('utf-8').strip('\x00')
                if ',' in text_data and len(text_data.split(',')) >= 10:
                    # This looks like a preamble string
                    return RigolScopeHeader.from_preamble_string(text_data)
            except:
                pass
            
            # Try as binary header
            return RigolScopeHeader(hdr_data)
        elif isinstance(hdr_data, dict):
            return RigolScopeHeader.from_dict(hdr_data)
        elif isinstance(hdr_data, str):
            # Preamble string
            return RigolScopeHeader.from_preamble_string(hdr_data)
        else:
            return RigolScopeHeader(hdr_data)
    except Exception as e:
        print(f"Error decoding Rigol header info: {e}")
        return None

#======================================================================================
# NEW SHOT-BASED FORMAT FUNCTIONS
#======================================================================================

def detect_hdf5_format(file_path):
    """Detect which HDF5 format is used in the file"""
    with h5py.File(file_path, 'r') as f:
        if 'rigol_scope' in f:
            # Check if it has shot structure
            rigol_group = f['rigol_scope']
            shots = [key for key in rigol_group.keys() if key.startswith('shot_')]
            if shots:
                return 'new_shot_based'
            else:
                return 'new_single'
        elif 'Acquisition' in f:
            return 'old_acquisition'
        else:
            return 'unknown'

def list_available_shots(file_path):
    """List all available shots in the new format"""
    with h5py.File(file_path, 'r') as f:
        if 'rigol_scope' in f:
            scope_group = f['rigol_scope']
            shots = [key for key in scope_group.keys() if key.startswith('shot_')]
            return sorted(shots, key=lambda x: int(x.split('_')[1]))
        else:
            return []

def list_available_channels_new_format(file_path, shot_number=1):
    """List all available channels for a given shot in new format"""
    with h5py.File(file_path, 'r') as f:
        shot_path = f'rigol_scope/shot_{shot_number}'
        if shot_path in f:
            shot_group = f[shot_path]
            channels = set()
            for key in shot_group.keys():
                if key.endswith('_data'):
                    channel = key.replace('_data', '')
                    channels.add(channel)
            return sorted(list(channels))
        else:
            return []

def list_available_channels_old_format(file_path):
    """List available channels in old format"""
    channels = []
    with h5py.File(file_path, 'r') as f:
        # Check Rigol scope structure
        if '/Acquisition/Rigol_scope' in f:
            scope_group = f['/Acquisition/Rigol_scope']
            for key in scope_group.keys():
                if key.startswith('Channel') and isinstance(scope_group[key], h5py.Dataset):
                    channels.append(key)
        
        # Check LeCroy scope structure for compatibility
        elif '/Acquisition/LeCroy_scope' in f:
            scope_group = f['/Acquisition/LeCroy_scope']
            for key in scope_group.keys():
                if key.startswith('Channel') and isinstance(scope_group[key], h5py.Dataset):
                    channels.append(key)
    
    return sorted(channels)

def read_new_shot_data(file_path, shot_number=1, channel='C1', 
                      list_some_header_info=False):
    """Read data from the new shot-based HDF5 structure"""
    
    with h5py.File(file_path, 'r') as f:
        # New path structure
        data_path = f'/rigol_scope/shot_{shot_number}/{channel}_data'
        header_path = f'/rigol_scope/shot_{shot_number}/{channel}_header'
        time_path = f'/rigol_scope/time_array'
        
        if data_path not in f:
            raise KeyError(f"Shot {shot_number}, channel {channel} not found")
        
        # Read int16 data (needs scaling back to voltage)
        raw_data = f[data_path][:]
        
        # Read time array
        if time_path in f:
            time_array = f[time_path][:]
        else:
            # Fallback time array
            dt = 1e-4  # 100μs for diamagnetic measurements
            time_array = np.arange(len(raw_data)) * dt - len(raw_data) * dt / 2
        
        # Convert int16 back to voltage
        # The acquisition scales voltage with a factor, we need to reverse it
        # For now, use a simple scaling - this may need adjustment based on your data
        voltage_range_estimate = 0.010  # 10mV typical for diamagnetic signals
        voltage_data = raw_data.astype(np.float64) * voltage_range_estimate / 30000.0
        
        # Read header if requested
        if list_some_header_info and header_path in f:
            try:
                header_bytes = f[header_path][()]
                header = decode_rigol_header_info(header_bytes)
                if header:
                    print(f"dt = {getattr(header, 'dt', 'unknown')}")
                    print(f"vertical_gain = {getattr(header, 'vertical_gain', 'unknown')}")
            except Exception as e:
                print(f"Could not decode header: {e}")
            
            # Print dataset attributes
            try:
                data_attrs = dict(f[data_path].attrs)
                print(f"Dataset attributes: {data_attrs}")
                time_attrs = dict(f[time_path].attrs) if time_path in f else {}
                print(f"Time array attributes: {time_attrs}")
            except Exception as e:
                print(f"Could not read attributes: {e}")
        
        return voltage_data, time_array

def get_file_info_new_format(file_path):
    """Get detailed information about new format file"""
    info = {}
    
    with h5py.File(file_path, 'r') as f:
        # File-level attributes
        info['file_attrs'] = dict(f.attrs)
        
        # Shots information
        shots = list_available_shots(file_path)
        info['shots'] = shots
        info['num_shots'] = len(shots)
        
        if shots:
            # Channel information from first shot
            channels = list_available_channels_new_format(file_path, 1)
            info['channels'] = channels
            info['num_channels'] = len(channels)
            
            # Time array information
            if 'rigol_scope/time_array' in f:
                time_ds = f['rigol_scope/time_array']
                info['time_points'] = len(time_ds)
                info['time_range'] = (float(time_ds[0]), float(time_ds[-1]))
                info['sample_rate'] = 1.0 / (time_ds[1] - time_ds[0]) if len(time_ds) > 1 else 0
                info['time_attrs'] = dict(time_ds.attrs)
            
            # Data information from first channel of first shot
            if channels:
                first_channel = channels[0]
                data_path = f'rigol_scope/shot_1/{first_channel}_data'
                if data_path in f:
                    data_ds = f[data_path]
                    info['data_points'] = len(data_ds)
                    info['data_type'] = str(data_ds.dtype)
                    info['data_range'] = (int(np.min(data_ds[:])), int(np.max(data_ds[:])))
        
        # Scope information
        if 'rigol_scope' in f:
            scope_attrs = dict(f['rigol_scope'].attrs)
            info['scope_attrs'] = scope_attrs
    
    return info

#======================================================================================
# UNIFIED READING FUNCTION
#======================================================================================

def read_rigol_hdf5_data_universal(file_path, channel='C1', shot_number=1, 
                                 position_index=0, list_some_header_info=False):
    """Universal function to read Rigol data from any supported HDF5 format"""
    
    file_format = detect_hdf5_format(file_path)
    
    if file_format == 'new_shot_based':
        # Convert channel names for compatibility
        if channel.startswith('Channel'):
            channel = channel.replace('Channel', 'C')
        
        return read_new_shot_data(file_path, shot_number, channel, list_some_header_info)
    
    elif file_format == 'old_acquisition':
        # Convert channel names for compatibility
        if not channel.startswith('Channel'):
            channel = f'Channel{channel.replace("C", "")}'
        
        return read_rigol_hdf5_data(file_path, channel, position_index, list_some_header_info)
    
    else:
        raise ValueError(f"Unsupported HDF5 format: {file_format}")

#======================================================================================
# ANALYSIS FUNCTIONS FOR DIAMAGNETIC DATA
#======================================================================================

def analyze_diamagnetic_shot(file_path, shot_number=1, channels=['C1', 'C2', 'C3']):
    """Analyze a single diamagnetic shot"""
    
    results = {
        'shot_number': shot_number,
        'channels': {},
        'time_info': {},
        'analysis': {}
    }
    
    # Read time array first
    _, time_array = read_rigol_hdf5_data_universal(file_path, channels[0], shot_number)
    results['time_info'] = {
        'time_points': len(time_array),
        'time_span': time_array[-1] - time_array[0],
        'sample_rate': 1.0 / (time_array[1] - time_array[0]) if len(time_array) > 1 else 0,
        'time_range': (time_array[0], time_array[-1])
    }
    
    # Read all channels
    for channel in channels:
        try:
            voltage_data, _ = read_rigol_hdf5_data_universal(file_path, channel, shot_number)
            
            # Basic statistics
            channel_stats = {
                'mean': np.mean(voltage_data),
                'std': np.std(voltage_data),
                'min': np.min(voltage_data),
                'max': np.max(voltage_data),
                'peak_to_peak': np.max(voltage_data) - np.min(voltage_data),
                'rms': np.sqrt(np.mean(voltage_data**2)),
                'data_points': len(voltage_data)
            }
            
            # Find trigger point (assume it's at center for now)
            trigger_index = len(voltage_data) // 2
            pre_trigger = voltage_data[:trigger_index]
            post_trigger = voltage_data[trigger_index:]
            
            channel_stats.update({
                'pre_trigger_mean': np.mean(pre_trigger),
                'post_trigger_mean': np.mean(post_trigger),
                'trigger_response': np.mean(post_trigger) - np.mean(pre_trigger)
            })
            
            results['channels'][channel] = {
                'data': voltage_data,
                'stats': channel_stats
            }
            
        except Exception as e:
            print(f"Error analyzing {channel}: {e}")
            results['channels'][channel] = {'error': str(e)}
    
    # Cross-channel analysis
    if len(results['channels']) > 1:
        channels_with_data = [ch for ch in channels if 'data' in results['channels'].get(ch, {})]
        if len(channels_with_data) >= 2:
            # Calculate correlations
            correlations = {}
            for i, ch1 in enumerate(channels_with_data):
                for ch2 in channels_with_data[i+1:]:
                    data1 = results['channels'][ch1]['data']
                    data2 = results['channels'][ch2]['data']
                    correlation = np.corrcoef(data1, data2)[0, 1]
                    correlations[f'{ch1}_{ch2}'] = correlation
            
            results['analysis']['correlations'] = correlations
    
    return results

#======================================================================================
# KEEP ORIGINAL FUNCTIONS FOR COMPATIBILITY
#======================================================================================

# [Keep all the original functions from your read_rigol_data.py here...]
# I'll include the key ones:

def read_rigol_hdf5_data(file_path, dataset_name='Channel1', position_index=0, 
                        list_some_header_info=False):
    """Read Rigol scope data from HDF5 file (original function)"""
    
    with h5py.File(file_path, 'r') as f:
        # Try Rigol path first, then LeCroy for compatibility
        data_path = f'/Acquisition/Rigol_scope/{dataset_name}'
        header_path = f'/Acquisition/Rigol_scope/Headers/{dataset_name}'
        time_path = f'/Acquisition/Rigol_scope/time'
        
        if data_path not in f:
            data_path = f'/Acquisition/LeCroy_scope/{dataset_name}'
            header_path = f'/Acquisition/LeCroy_scope/Headers/{dataset_name}'
            time_path = f'/Acquisition/LeCroy_scope/time'
        
        if data_path not in f:
            raise KeyError(f"Dataset {dataset_name} not found in file")
        
        # Read voltage data
        dataset = f[data_path]
        if len(dataset.shape) == 1:
            signal_data = dataset[:]
        elif len(dataset.shape) == 2:
            if position_index >= dataset.shape[0]:
                raise IndexError(f"Position index {position_index} out of range")
            signal_data = dataset[position_index, :]
        else:
            raise ValueError(f"Unexpected dataset shape: {dataset.shape}")
        
        # Read time array
        if time_path in f:
            time_array = f[time_path][:]
        else:
            # Manual time array calculation
            dt = 1e-6  # 1 µs per sample
            time_array = np.arange(len(signal_data)) * dt
        
        # Clean signal data (remove NaN padding)
        signal_data, first_idx, last_idx = clean_signal_data(signal_data)
        
        # Adjust time array to match cleaned data
        if time_path in f and first_idx != 0:
            time_array = time_array[first_idx:last_idx+1]
        
        return signal_data, time_array

def clean_signal_data(signal_data):
    """Remove NaN values and return clean data"""
    if np.any(np.isnan(signal_data)):
        # Find first and last valid indices
        valid_mask = ~np.isnan(signal_data)
        if np.any(valid_mask):
            valid_indices = np.where(valid_mask)[0]
            first_valid = valid_indices[0]
            last_valid = valid_indices[-1]
            cleaned_data = signal_data[first_valid:last_valid+1]
            return cleaned_data, first_valid, last_valid
        else:
            return signal_data, 0, len(signal_data)-1
    else:
        return signal_data, 0, len(signal_data)-1

def examine_hdf5_file(file_path):
    """Examine the contents of the HDF5 file for debugging"""
    print(f"\n=== Examining HDF5 file: {file_path} ===")
    
    file_format = detect_hdf5_format(file_path)
    print(f"Detected format: {file_format}")
    
    if file_format == 'new_shot_based':
        info = get_file_info_new_format(file_path)
        print(f"Shots: {info['num_shots']} ({info['shots']})")
        print(f"Channels: {info['num_channels']} ({info['channels']})")
        print(f"Time points: {info.get('time_points', 'unknown')}")
        print(f"Sample rate: {info.get('sample_rate', 0):.0f} Sa/s")
        if 'time_range' in info:
            print(f"Time range: {info['time_range'][0]*1000:.3f} to {info['time_range'][1]*1000:.3f} ms")
    else:
        # Use original examination function
        with h5py.File(file_path, 'r') as f:
            def print_item(name, obj):
                if isinstance(obj, h5py.Group):
                    print(f"Group: {name}")
                elif isinstance(obj, h5py.Dataset):
                    print(f"Dataset: {name} - Shape: {obj.shape}, Type: {obj.dtype}")
            
            f.visititems(print_item)

#======================================================================================
# MAIN TEST FUNCTION
#======================================================================================

if __name__ == '__main__':
    """Test the new functionality"""
    
    # Test files (modify these to match your actual files)
    test_files = [
        'rigol_diamagnetic_data.h5',  # New format
        'rigol_scope_single_20250905_173046.h5'  # Old format if you have it
    ]
    
    for test_file in test_files:
        if os.path.exists(test_file):
            print(f"\n{'='*60}")
            print(f"Testing file: {test_file}")
            print('='*60)
            
            try:
                # Examine file structure
                examine_hdf5_file(test_file)
                
                # Detect format and read data
                file_format = detect_hdf5_format(test_file)
                print(f"\nFile format: {file_format}")
                
                if file_format == 'new_shot_based':
                    # Test new format
                    shots = list_available_shots(test_file)
                    channels = list_available_channels_new_format(test_file, 1)
                    
                    print(f"Available shots: {shots}")
                    print(f"Available channels: {channels}")
                    
                    if shots and channels:
                        # Read first shot, first channel
                        voltage, time = read_new_shot_data(test_file, 1, channels[0], 
                                                         list_some_header_info=True)
                        print(f"Successfully read {len(voltage)} samples from shot 1, {channels[0]}")
                        print(f"Voltage range: {np.min(voltage)*1000:.3f} to {np.max(voltage)*1000:.3f} mV")
                        print(f"Time range: {time[0]*1000:.3f} to {time[-1]*1000:.3f} ms")
                        
                        # Analyze shot
                        analysis = analyze_diamagnetic_shot(test_file, 1, channels[:3])
                        print(f"Analysis completed for shot 1")
                        for ch in channels[:3]:
                            if ch in analysis['channels'] and 'stats' in analysis['channels'][ch]:
                                stats = analysis['channels'][ch]['stats']
                                print(f"  {ch}: {stats['peak_to_peak']*1000:.3f} mV p-p, "
                                      f"RMS: {stats['rms']*1000:.3f} mV")
                
                elif file_format == 'old_acquisition':
                    # Test old format
                    channels = list_available_channels_old_format(test_file)
                    print(f"Available channels: {channels}")
                    
                    if channels:
                        voltage, time = read_rigol_hdf5_data(test_file, channels[0],
                                                           list_some_header_info=True)
                        print(f"Successfully read {len(voltage)} samples from {channels[0]}")
                        
            except Exception as e:
                print(f"Error testing {test_file}: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"Test file {test_file} not found")

