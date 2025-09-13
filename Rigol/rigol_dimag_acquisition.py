'''
Rigol-based data acquisition for diamagnetic measurements

Converted from LeCroy multi_scope_acquisition.py to work with Rigol DHO series
using telnet communication instead of VISA drivers.

Key changes:
- Replaced LeCroy_Scope with RigolScope (telnet-based)
- Adapted trigger detection and data acquisition methods
- Modified header processing for Rigol preamble format
- Simplified acquisition modes (no sequence mode for DHO series)

Dependencies:
- Rigol_Scope: Telnet interface to Rigol DHO oscilloscopes
- h5py: HDF5 file handling
- numpy: Numerical operations
- configparser: Configuration file parsing

Created for diamagnetic measurement acquisition
@author: Converted from LeCroy version
'''

import numpy as np
from Rigol_Scope import RigolScope
from Rigol_Scope_Header import RigolScopeHeader, RIGOL_WAVEDESC_SIZE
import h5py
import time
import os
import configparser
import traceback
import warnings
import logging
from datetime import datetime

#===============================================================================================================================================
# RIGOL-SPECIFIC ACQUISITION FUNCTIONS
#===============================================================================================================================================

def rigol_stop_triggering(scope, retry=500):
    """Stop Rigol scope triggering and ensure STOP state"""
    retry_count = 0
    
    # First, let's see what state the scope is in
    try:
        initial_status = scope.command(":TRIGger:STATus?").strip()
        print(f"Initial trigger status: {initial_status}")
    except Exception as e:
        print(f"Error getting initial status: {e}")
    
    while retry_count < retry:
        try:
            # Try different approaches to stop the scope
            if retry_count == 0:
                # First try: Standard stop command
                scope.command(":TRIGger:SWEep STOP")
            elif retry_count == 1:
                # Second try: Force stop
                scope.command(":STOP")
            elif retry_count == 2:
                # Third try: Single mode then stop
                scope.command(":TRIGger:SWEep SINGle")
                time.sleep(0.1)
                scope.command(":STOP")
            else:
                # Continue with standard approach
                scope.command(":TRIGger:SWEep STOP")
            
            time.sleep(0.1)  # Give scope time to respond
            
            # Check status
            status = scope.command(":TRIGger:STATus?").strip()
            print(f"Attempt {retry_count + 1}: Status = {status}")
            
            if status in ['STOP', 'TD', 'AUTO']:  # Add AUTO as acceptable
                print(f"✓ Scope entered acceptable state: {status}")
                return True
                
        except KeyboardInterrupt:
            print('Keyboard interrupted in rigol_stop_triggering')
            raise
        except Exception as e:
            print(f"Error in attempt {retry_count + 1}: {e}")
            
        retry_count += 1
        time.sleep(0.05)

    print(f'Rigol scope did not enter STOP state after {retry} attempts')
    return False

def rigol_init_acquire_from_scope(scope, scope_name):
    """Initialize acquisition from a Rigol scope (no cropping needed)"""
    time_array = None
    is_sequence = 0

    traces = scope.displayed_traces()
    
    if not traces:
        print(f"Warning: No displayed traces found on {scope_name}")
        return None, None
    
    for tr in traces:
        try:
            if rigol_stop_triggering(scope):
                # Get full time array (perfect size with 250k points)
                time_array = scope.time_array(tr)
                
                if time_array is not None and len(time_array) > 0:
                    logging.info(f"Got time array from {scope_name}:{tr} - {len(time_array)} points")
                    break
                else:
                    logging.warning(f"Invalid time array from {scope_name}:{tr}")
                    
            else:
                raise Exception(f'Rigol scope {scope_name} did not enter STOP state')
                
        except Exception as e:
            logging.error(f"Error initializing {tr} from {scope_name}: {e}")
            continue
    
    if time_array is None:
        print(f"Warning: Could not get valid time array from any trace on {scope_name}")
        return None, None
    
    return is_sequence, time_array

def rigol_acquire_from_scope(scope, scope_name):
    """METHOD 1: Acquire full window then crop to optimal -100ms to +100ms"""
    
    data = {}
    headers = {}
    active_traces = []

    traces = scope.displayed_traces()
    
    if not traces:
        logging.warning(f"No displayed traces on {scope_name}")
        return active_traces, data, headers
    
    # Skip C4 (trigger channel) - only acquire data channels
    data_channels = [tr for tr in traces if tr in ['C1', 'C2', 'C3']]
    
    logging.info(f"Acquiring and cropping optimal window from: {data_channels}")
    
    for tr in data_channels:
        try:
            if rigol_stop_triggering(scope):
                # Get voltage data and time array (full -200ms to +200ms window)
                voltage_data, header_bytes = scope.acquire(tr, raw=False)
                time_array = scope.time_array(tr)
                
                if voltage_data is not None and len(voltage_data) > 0 and time_array is not None:
                    
                    time_span = (time_array[-1] - time_array[0]) * 1000
                    print(f"  {tr}: {len(voltage_data):,} points, time span {time_span:.1f}ms")
                    print(f"    Full range: {time_array[0]*1000:.1f}ms to {time_array[-1]*1000:.1f}ms")
                    
                    # CROP TO OPTIMAL -100ms TO +100ms WINDOW
                    if time_array[0] <= -0.1 and time_array[-1] >= 0.1:
                        # Find indices for -100ms to +100ms
                        start_idx = np.argmin(np.abs(time_array - (-0.1)))  # -100ms
                        end_idx = np.argmin(np.abs(time_array - 0.1))       # +100ms
                        
                        # Crop both voltage and time arrays
                        cropped_voltage = voltage_data[start_idx:end_idx+1]
                        cropped_time = time_array[start_idx:end_idx+1]
                        
                        cropped_span = (cropped_time[-1] - cropped_time[0]) * 1000
                        
                        print(f"    CROPPED to optimal window:")
                        print(f"    Points: {len(cropped_voltage):,} (cropped from {len(voltage_data):,})")
                        print(f"    Time span: {cropped_span:.1f}ms")
                        print(f"    Range: {cropped_time[0]*1000:.1f}ms to {cropped_time[-1]*1000:.1f}ms")
                        
                        # Verify optimal diamagnetic window
                        if cropped_time[0] <= 0 <= cropped_time[-1]:
                            baseline_ms = abs(cropped_time[0]) * 1000
                            decay_ms = cropped_time[-1] * 1000
                            print(f"    ✅ PERFECT! Optimal diamagnetic window")
                            print(f"    📊 Baseline: {baseline_ms:.1f}ms, Decay: {decay_ms:.1f}ms")
                            
                            if 90 <= baseline_ms <= 110 and 90 <= decay_ms <= 110:
                                print(f"    🎯 IDEAL! ~100ms baseline + ~100ms decay")
                        
                        # Use cropped data for storage
                        voltage_for_storage = cropped_voltage
                        
                    else:
                        print(f"    ⚠️  Cannot crop to -100/+100ms window - using full data")
                        print(f"    Available range: {time_array[0]*1000:.1f}ms to {time_array[-1]*1000:.1f}ms")
                        voltage_for_storage = voltage_data
                    
                    # Convert to int16 for storage efficiency
                    voltage_range = np.max(voltage_for_storage) - np.min(voltage_for_storage)
                    if voltage_range > 0:
                        scale_factor = 30000 / voltage_range
                        int16_data = (voltage_for_storage * scale_factor).astype(np.int16)
                    else:
                        int16_data = voltage_for_storage.astype(np.int16)
                    
                    # Store the cropped optimal data
                    data[tr] = int16_data
                    headers[tr] = header_bytes
                    active_traces.append(tr)
                    
                    logging.info(f"Stored {tr}: {len(int16_data):,} points (cropped to optimal window)")
                        
                else:
                    logging.warning(f"No valid data from {scope_name}:{tr}")
                    
            else:
                raise Exception(f'Scope {scope_name} did not enter STOP state for {tr}')
                
        except Exception as e:
            logging.error(f"Error acquiring {tr} from {scope_name}: {e}")
            continue
            
    return active_traces, data, headers

#===============================================================================================================================================
# CONFIGURATION LOADING
#===============================================================================================================================================

def load_experiment_config(config_path='experiment_config.txt'):
    """Load experiment configuration from config file.
    
    Returns:
        tuple: (config, raw_config_text)
    """
    config = configparser.ConfigParser()
    
    # Read the raw config text
    raw_config_text = ""
    try:
        with open(config_path, 'r') as f:
            raw_config_text = f.read()
    except Exception as e:
        print(f"Warning: Could not read raw config file: {e}")
    
    # Parse the config
    config.read(config_path)
    
    # Set defaults if sections don't exist
    if 'experiment' not in config:
        config.add_section('experiment')
    if 'scopes' not in config:
        config.add_section('scopes')
    if 'channels' not in config:
        config.add_section('channels')
    
    # Set default values if not present
    if not config.get('experiment', 'description', fallback=None):
        config.set('experiment', 'description', 'Rigol DHO diamagnetic measurement')
    
    return config, raw_config_text

#===============================================================================================================================================
# RIGOL MULTI-SCOPE ACQUISITION CLASS
#===============================================================================================================================================

class RigolDimagAcquisition:
    """Rigol-based scope acquisition for diamagnetic measurements"""
    
    def __init__(self, save_path, config, raw_config_text=""):
        """
        Args:
            save_path: path to save HDF5 file
            config: ConfigParser object with experiment configuration
            raw_config_text: Raw text content of the configuration file
        """
        self.save_path = save_path
        self.scopes = {}
        self.time_arrays = {}  # Store time arrays for each scope
        self.config = config
        self.raw_config_text = raw_config_text
        
        # Load scope IPs from config
        if 'scope_ips' not in config:
            # Single scope configuration for diamagnetic setup
            self.scope_ips = {'rigol_scope': '128.97.13.178'}  # Your scope IP
            logging.info("Using default Rigol scope IP: 128.97.13.178")
        else:
            self.scope_ips = dict(config.items('scope_ips'))
            
        if not self.scope_ips:
            raise RuntimeError("No scope IPs configured")

    def cleanup(self):
        """Clean up resources"""
        logging.info("Cleaning up Rigol scope resources...")
        
        for name, scope in self.scopes.items():
            try:
                logging.info(f"Closing Rigol scope {name}...")
                scope.disconnect()
            except Exception as e:
                logging.error(f"Error closing scope {name}: {e}")
        self.scopes.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def get_scope_description(self, scope_name):
        """Get scope description from experiment config"""
        return self.config.get('scopes', scope_name, 
                             fallback=f'Rigol DHO scope {scope_name} - Diamagnetic measurement')
    
    def get_channel_description(self, channel_name):
        """Get channel description from experiment config"""
        return self.config.get('channels', channel_name, 
                             fallback=f'Channel {channel_name} - No description available')
    
    def get_experiment_description(self):
        """Get experiment description from experiment config"""
        description = self.config.get('experiment', 'description', 
                                    fallback='Rigol DHO diamagnetic measurement')
        return description

    def get_script_contents(self):
        """Read the contents of the Python scripts used to create the HDF5 file"""
        script_contents = {}
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Scripts for Rigol diamagnetic acquisition
        scripts = [
            'rigol_dimag_acquisition.py', 
            'Rigol_Scope.py',
            'Rigol_Scope_Header.py'
        ]
        
        for script in scripts:
            script_path = os.path.join(current_dir, script)
            try:
                # FIX: Try multiple encodings to handle encoding issues
                encodings_to_try = ['utf-8', 'latin-1', 'cp1252', 'utf-8-sig']
                
                for encoding in encodings_to_try:
                    try:
                        with open(script_path, 'r', encoding=encoding) as f:
                            script_contents[script] = f.read()
                        break  # Success, stop trying other encodings
                    except UnicodeDecodeError:
                        continue  # Try next encoding
                else:
                    # If all encodings failed, read as binary and decode with errors='replace'
                    with open(script_path, 'rb') as f:
                        content = f.read()
                    script_contents[script] = content.decode('utf-8', errors='replace')
                    logging.warning(f"Had to use error replacement for {script}")
                    
            except FileNotFoundError:
                logging.warning(f"Could not find {script}")
                script_contents[script] = f"File not found: {script}"
            except Exception as e:
                logging.warning(f"Could not read {script}: {str(e)}")
                script_contents[script] = f"Error reading file: {str(e)}"
    
        return script_contents
    
    def initialize_hdf5_base(self):
        """Initialize HDF5 file structure for Rigol scopes and experiment metadata"""
        with h5py.File(self.save_path, 'a') as f:
            # Add experiment description and creation time
            f.attrs['description'] = self.get_experiment_description()
            f.attrs['creation_time'] = time.ctime()
            f.attrs['acquisition_system'] = 'Rigol DHO Series via Telnet'
            
            # Add Python scripts used to create the file
            script_contents = self.get_script_contents()
            f.attrs['source_code'] = str(script_contents)
            
            # Store configuration files
            config_group = f.require_group('Configuration')
            
            if self.raw_config_text:
                # FIX: Replace np.string_ with np.bytes_ for NumPy 2.0 compatibility
                config_group.create_dataset('experiment_config', 
                                      data=np.bytes_(self.raw_config_text.encode('utf-8')))
                logging.info("Stored Rigol configuration file content")
            
            # Create scope groups with their descriptions
            for scope_name in self.scope_ips:
                if scope_name not in f:
                    scope_group = f.create_group(scope_name)
                    scope_group.attrs['scope_type'] = 'Rigol DHO Series'
                    scope_group.attrs['communication'] = 'Telnet'

    def initialize_scopes(self):
        """Initialize Rigol scopes and configure for diamagnetic measurement"""
        active_scopes = {}
        
        for name, ip in self.scope_ips.items():
            print(f"\nInitializing Rigol scope {name} at {ip}...", end='')
            
            try:
                # Create Rigol scope instance
                self.scopes[name] = RigolScope(ip, verbose=True, timeout=10000)
                scope = self.scopes[name]
                
                if not scope.connected:
                    raise ConnectionError(f"Failed to connect to Rigol scope at {ip}")
                
                logging.info(f"Connected to {scope.idn_string}")
                
                # CRITICAL: Configure for diamagnetic measurement
                self._configure_scope_for_diamagnetic(scope, name)
                
                # Get initial data and time arrays
                is_sequence, time_array = rigol_init_acquire_from_scope(scope, name)

                if is_sequence is not None and time_array is not None:
                    self.save_time_arrays(name, time_array, is_sequence)
                    self._save_scope_metadata(name)
                    active_scopes[name] = is_sequence
                    print(f" ✓ Successfully initialized {name}")
                else:
                    print(f" ✗ Could not initialize {name} - no valid data")
                    self.cleanup_scope(name)
                    
            except Exception as e:
                print(f" ✗ Error initializing {name}: {str(e)}")
                self.cleanup_scope(name)
                continue
                
        return active_scopes

    # CORRECT METHOD: Use time reference positioning instead of trigger position
    def _configure_scope_for_diamagnetic(self, scope, scope_name):
        """STABLE: 20ms/div configuration with post-acquisition cropping to -100/+100ms"""
        
        print(f"Configuring {scope_name} for diamagnetic measurement...")
        
        try:
            # Basic setup
            scope.command(":STOP")
            time.sleep(0.5)
            
            scope.command(":CHANnel4:DISPlay OFF")
            for ch_num in [1, 2, 3]:
                scope.command(f":CHANnel{ch_num}:DISPlay ON")
                time.sleep(0.1)
            
            # STEP 1: Complete reset for clean configuration
            print(f"  STEP 1: Resetting for proven stable configuration...")
            
            scope.command(":TRIGger:SWEep STOP")
            time.sleep(0.3)
            scope.command("*RST")
            time.sleep(2.0)
            
            # Re-enable channels after reset
            scope.command(":CHANnel4:DISPlay OFF")
            for ch_num in [1, 2, 3]:
                scope.command(f":CHANnel{ch_num}:DISPlay ON")
                time.sleep(0.1)
            
            # STEP 2: PROVEN STABLE - 20ms/div configuration
            print(f"  STEP 2: Setting proven stable 20ms/div timebase...")
            
            # 20ms/div × 10 = 200ms total window (-100ms to +100ms around trigger)
            # Will crop to exact -100ms to +100ms in post-processing
            scope.command(":TIMebase:MAIN:SCALe 0.02")    # 20ms/div (PROVEN STABLE)
            scope.command(":TIMebase:MAIN:OFFSet 0")      # Centered on trigger
            time.sleep(1.0)
            
            print(f"    Set timebase: 20ms/div (200ms total, will crop to 200ms optimal)")
            
            # STEP 3: Request full 1M memory depth
            scope.command(":ACQuire:TYPE NORMal")
            scope.command(":ACQuire:MDEPth 1000000")  # Full 1M points
            time.sleep(0.5)
            
            # STEP 4: Trigger configuration
            scope.command(":TRIGger:SOURce CHANnel4")
            scope.command(":TRIGger:LEVel 0.1")
            scope.command(":TRIGger:SLOPe POSitive")
            scope.command(":TRIGger:SWEep NORMal")
            time.sleep(0.5)
            
            # STEP 5: Channel configuration  
            for ch_num in [1, 2, 3]:
                scope.command(f":CHANnel{ch_num}:COUPling DC")
                scope.command(f":CHANnel{ch_num}:BWLimit OFF")
                scope.command(f":CHANnel{ch_num}:SCALe 0.02")  # 20mV/div
                scope.command(f":CHANnel{ch_num}:OFFSet 0")
                time.sleep(0.1)
        
            # STEP 6: Force buffer repositioning
            print(f"  STEP 6: Forcing buffer repositioning...")
            
            scope.command(":TRIGger:SWEep STOP")
            time.sleep(0.5)
            scope.command(":TRIGger:SWEep NORMal")
            time.sleep(1.0)
            
            # STEP 7: Verify the stable configuration
            print(f"  STEP 7: Verifying stable configuration with post-crop planning...")
            
            scope.command(':WAVeform:SOURce CHANnel2')
            time.sleep(0.3)
            scope.command(':WAVeform:MODE RAW')
            scope.command(':WAVeform:STARt 1')
            scope.command(':WAVeform:STOP MAX')
            time.sleep(0.5)
            
            # Check configuration
            preamble = scope.command(':WAVeform:PREamble?')
            if preamble and ',' in preamble:
                values = preamble.split(',')
                if len(values) >= 6:
                    total_points = int(float(values[2]))
                    x_inc = float(values[4])
                    x_origin = float(values[5])
                    
                    buffer_start_ms = x_origin * 1000
                    buffer_end_ms = buffer_start_ms + (total_points - 1) * x_inc * 1000
                    buffer_span_ms = buffer_end_ms - buffer_start_ms
                    sample_rate = 1 / x_inc
                    
                    print(f"    STABLE CONFIGURATION (20ms/div):")
                    print(f"    Total points: {total_points:,}")
                    print(f"    Sample rate: {sample_rate/1e6:.2f} MSa/s")
                    print(f"    Full buffer: {buffer_span_ms:.1f}ms")
                    print(f"    Full range: {buffer_start_ms:.1f}ms to {buffer_end_ms:.1f}ms")
                    
                    # Check cropping potential
                    if buffer_start_ms <= -100 and buffer_end_ms >= 100:
                        # Calculate cropped window characteristics
                        points_per_ms = 1000 / (x_inc * 1000)
                        crop_start_idx = int((100 + buffer_start_ms) * points_per_ms)
                        crop_end_idx = int((100 + buffer_start_ms + 200) * points_per_ms)
                        cropped_points = crop_end_idx - crop_start_idx
                        
                        print(f"    ✅ SUCCESS: Can crop to perfect -100ms to +100ms!")
                        print(f"    📊 Cropped points: ~{cropped_points:,} (from {total_points:,})")
                        print(f"    📊 Cropped resolution: {x_inc*1e6:.2f} µs per point")
                        print(f"    🎯 PERFECT: Stable telnet + optimal diamagnetic window!")
                    else:
                        print(f"    ⚠️  Cannot crop to -100/+100ms from available range")
                    
                    # STEP 8: Configure waveform extraction (full buffer)
                    print(f"  STEP 8: Configuring full buffer extraction for post-crop...")
                    
                    for ch_num in [1, 2, 3]:
                        scope.command(f':WAVeform:SOURce CHANnel{ch_num}')
                        time.sleep(0.2)
                        scope.command(':WAVeform:MODE RAW')
                        scope.command(':WAVeform:FORMat BYTE')
                        scope.command(':WAVeform:STARt 1')
                        scope.command(f':WAVeform:STOP {total_points}')
                        time.sleep(0.2)
                        
                        print(f"    C{ch_num}: Full buffer ({total_points:,} points) for cropping")
                    
                    print(f"    ✅ STABLE + OPTIMAL: 20ms/div proven config with -100/+100ms cropping")
                    print(f"    📊 Expected transfer: ~12s per channel (proven reliable)")
                    
                else:
                    print(f"    ❌ ERROR: Invalid preamble format")
            else:
                print(f"    ❌ ERROR: Could not get preamble")
            
            print("✓ Stable 20ms/div configuration with optimal cropping completed")
        
        except Exception as e:
            print(f"✗ Error in stable configuration: {e}")
            raise

    def _check_waveform_points(self, scope, channel='C1'):
        """Check how many points we'll actually get from waveform acquisition"""
        try:
            # Set waveform source
            scope.command(f':WAVeform:SOURce CHANnel{channel[-1]}')
            time.sleep(0.1)
            
            # CRITICAL: Set waveform parameters to get ALL points
            scope.command(':WAVeform:STARt 1')      # Start from point 1
            scope.command(':WAVeform:STOP MAX')     # Get all available points
            scope.command(':WAVeform:MODE RAW')     # RAW mode (all points)
            time.sleep(0.1)
            
            # Get preamble to see actual point count
            preamble = scope.command(':WAVeform:PREamble?')
            if preamble:
                values = preamble.split(',')
                if len(values) >= 5:
                    actual_points = int(float(values[2]))
                    x_increment = float(values[4]) if len(values) > 4 else 0
                    total_time = actual_points * x_increment if x_increment > 0 else 0
                    
                    print(f"  {channel} waveform: {actual_points:,} points, {total_time*1000:.1f}ms span")
                    
                    # Check for decimation issues
                    if total_time > 0.2:  # More than 200ms indicates wrong timebase
                        print(f"    ⚠️  Time span too large - check timebase settings")
                    elif total_time < 0.08:  # Less than 80ms indicates missing data
                        print(f"    ⚠️  Time span too small - may be missing data")
                    elif actual_points < 50000:
                        print(f"    ⚠️  Low point count - may be in decimation mode")
                    else:
                        print(f"    ✓ Good configuration for {channel}")
                        
                    return actual_points
            
            return None
        except Exception as e:
            print(f"  Error checking waveform points for {channel}: {e}")
            return None

    def _verify_timebase_settings(self, scope, scope_name):
        """Enhanced verification with 3-channel diagnostics"""
        try:
            # Query current settings
            timebase_scale = float(scope.command(":TIMebase:MAIN:SCALe?"))
            timebase_offset = float(scope.command(":TIMebase:MAIN:OFFSet?"))
            memory_depth = scope.command(":ACQuire:MDEPth?")
            sample_rate = float(scope.command(":ACQuire:SRATe?"))
            
            # NEW: Query actual acquisition points
            acq_points_str = scope.command(":ACQuire:POINts?")
            acq_points = int(float(acq_points_str)) if acq_points_str else 0
            
            # Calculate time window
            total_time = timebase_scale * 10  # 10 divisions
            time_per_point = 1 / sample_rate if sample_rate > 0 else 0
            calculated_points = int(total_time / time_per_point) if time_per_point > 0 else 0
            
            print(f"\nTimebase verification for {scope_name}:")
            print(f"  Scale: {timebase_scale}s/div × 10 = {total_time*1000:.1f}ms total")
            print(f"  Offset: {timebase_offset*1000:.1f}ms")  
            print(f"  Memory depth setting: {memory_depth}")
            print(f"  Sample rate: {sample_rate/1e6:.1f} MSa/s")
            print(f"  Acquisition points: {acq_points:,}")
            print(f"  Calculated points: {calculated_points:,}")
            print(f"  Time per point: {time_per_point*1e9:.1f} ns")
            
            # Check for discrepancies
            if abs(acq_points - calculated_points) > 1000:
                print(f"  ⚠️  Point count mismatch: acquired vs calculated")
            
            # Verify pre/post trigger split
            pre_trigger_time = total_time/2 + timebase_offset
            post_trigger_time = total_time/2 - timebase_offset  
            print(f"  Pre-trigger time: {pre_trigger_time*1000:.1f}ms")
            print(f"  Post-trigger time: {post_trigger_time*1000:.1f}ms")
            
            # Check if settings are optimal
            if abs(pre_trigger_time - 0.05) > 0.001:  # Should be ~50ms
                print(f"  ⚠️  WARNING: Pre-trigger time is not 50ms!")
            if abs(post_trigger_time - 0.05) > 0.001:  # Should be ~50ms  
                print(f"  ⚠️  WARNING: Post-trigger time is not 50ms!")
            
            # 3-channel specific warnings
            if sample_rate < 10e6:
                print(f"  ⚠️  Low sample rate may be due to 3-channel limitation")
            if acq_points < 100000:
                print(f"  ⚠️  Low acquisition points - consider reducing channels or timebase")
                
            return {
                'total_time': total_time,
                'pre_trigger_time': pre_trigger_time,
                'post_trigger_time': post_trigger_time,
                'sample_rate': sample_rate,
                'memory_depth': memory_depth,
                'acquisition_points': acq_points,
                'time_resolution': time_per_point
            }
            
        except Exception as e:
            print(f"Error verifying timebase: {e}")
            return None

    def _save_scope_metadata(self, scope_name):
        """Save Rigol scope metadata to HDF5"""
        with h5py.File(self.save_path, 'a') as f:
            scope_group = f[scope_name]
            scope_group.attrs['description'] = self.get_scope_description(scope_name)
            scope_group.attrs['ip_address'] = self.scope_ips[scope_name]
            scope_group.attrs['scope_idn'] = self.scopes[scope_name].idn_string
            scope_group.attrs['communication_method'] = 'Telnet'
            scope_group.attrs['port'] = 5555  # Standard LXI port

    def cleanup_scope(self, name):
        """Clean up resources for a specific Rigol scope"""
        if name in self.scopes:
            try:
                self.scopes[name].disconnect()
                del self.scopes[name]
            except Exception as e:
                logging.error(f"Error closing Rigol scope {name}: {e}")

    def acquire_shot(self, active_scopes, shot_num):
        """Acquire data from all active Rigol scopes for one shot"""
        all_data = {}
        failed_scopes = []
        
        for name in active_scopes:
            try:
                print(f"Acquiring data from Rigol scope {name}...", end='')
                scope = self.scopes[name]
                
                # For Rigol: Always use regular acquisition (no sequence mode)
                traces, data, headers = rigol_acquire_from_scope(scope, name)

                if traces:
                    all_data[name] = (traces, data, headers)
                    print(" ✓")
                else:
                    print(f" ✗ No valid data from {name} for shot {shot_num}")
                    failed_scopes.append(name)
                    
            except KeyboardInterrupt:
                print(f"\nRigol scope acquisition interrupted for {name}")
                raise
            except Exception as e:
                print(f" ✗ Error acquiring from {name}: {e}")
                failed_scopes.append(name)
                
        return all_data
    
    def arm_scopes_for_trigger(self, active_scopes):
        """Arm all Rigol scopes for hardware trigger (but don't wait yet)"""
        print("Arming Rigol scopes for trigger... ", end='')
        
        for name in active_scopes:
            try:
                scope = self.scopes[name]
                
                # Arm scope for single trigger
                scope.command(":TRIGger:SWEep NORMal")  # Normal mode
                scope.command(":TRIGger:SINGle")        # Arm for single shot
                
                logging.info(f"Armed {name} for trigger - scope is now waiting for trigger event")
                
            except Exception as e:
                logging.error(f"Error arming {name}: {e}")
                raise
    
        print("armed and waiting ✓")
        logging.info(" ALL SCOPES ARMED - Generate trigger signal now!")

    def wait_for_trigger_completion(self, active_scopes, trigger_timeout=60):
        """Wait for all armed scopes to complete their triggered acquisition"""
        print("Waiting for trigger completion... ", end='')
        
        for name in active_scopes:
            try:
                scope = self.scopes[name]
                
                logging.info(f"Waiting for trigger completion on {name}...")
                
                start_time = time.time()
                
                while True:
                    status = scope.command(":TRIGger:STATus?").strip()
                    
                    if status in ['STOP', 'TD']:  # Trigger completed
                        logging.info(f"Trigger completed on {name}")
                        break
                    elif time.time() - start_time > trigger_timeout:
                        raise TimeoutError(f"Trigger timeout on {name} after {trigger_timeout}s")
                    
                    time.sleep(0.1)  # Check every 100ms
                    
            except Exception as e:
                logging.error(f"Error waiting for trigger on {name}: {e}")
                raise
    
        print("completed ✓")
    
    def save_time_arrays(self, scope_name, time_array, is_sequence):
        """Save cropped time array (-100ms to +100ms) for diamagnetic measurements"""
        with h5py.File(self.save_path, 'a') as f:
            scope_group = f[scope_name]
            
            # Crop time array to optimal -100ms to +100ms window
            if time_array[0] <= -0.1 and time_array[-1] >= 0.1:
                start_idx = np.argmin(np.abs(time_array - (-0.1)))  # -100ms
                end_idx = np.argmin(np.abs(time_array - 0.1))       # +100ms
                cropped_time_array = time_array[start_idx:end_idx+1]
                
                print(f"Cropped time array from {len(time_array):,} to {len(cropped_time_array):,} points")
            else:
                cropped_time_array = time_array
                print(f"Could not crop time array - using full array")
            
            self.time_arrays[scope_name] = cropped_time_array
            
            if 'time_array' in scope_group:
                raise RuntimeError(f"Time array already exists for scope {scope_name}")
            
            # Calculate cropped characteristics
            start_time_ms = cropped_time_array[0] * 1000
            end_time_ms = cropped_time_array[-1] * 1000
            total_span_ms = (cropped_time_array[-1] - cropped_time_array[0]) * 1000
            
            # Save cropped time array to HDF5
            time_ds = scope_group.create_dataset('time_array', data=cropped_time_array, dtype='float64')
            time_ds.attrs['units'] = 'seconds'
            time_ds.attrs['description'] = 'Cropped optimal time array for diamagnetic measurements (-100ms to +100ms)'
            time_ds.attrs['dtype'] = str(cropped_time_array.dtype)
            time_ds.attrs['acquisition_mode'] = 'triggered' if is_sequence == 0 else 'sequence'
            time_ds.attrs['extraction_method'] = 'Method 1: Full buffer acquisition with post-processing crop to -100/+100ms'
            time_ds.attrs['total_span_ms'] = total_span_ms
            time_ds.attrs['start_time_ms'] = start_time_ms
            time_ds.attrs['end_time_ms'] = end_time_ms
            time_ds.attrs['start_time'] = cropped_time_array[0]
            time_ds.attrs['end_time'] = cropped_time_array[-1]
            
            # Should be perfectly centered
            if start_time_ms <= 0 <= end_time_ms:
                time_ds.attrs['trigger_in_window'] = True
                time_ds.attrs['baseline_duration_ms'] = abs(start_time_ms)
                time_ds.attrs['decay_duration_ms'] = end_time_ms
                logging.info(f"Saved optimal cropped time array: {len(cropped_time_array):,} points, perfect diamagnetic window")
            else:
                time_ds.attrs['trigger_in_window'] = False
                logging.warning(f"Cropped time array doesn't center trigger properly")

    def update_scope_hdf5(self, all_data, shot_num):
        """Update HDF5 file with Rigol scope data (save as int16)"""
        with h5py.File(self.save_path, 'a', libver='latest', rdcc_nbytes=0) as f:
            for scope_name, (traces, data, headers) in all_data.items():
                scope_group = f[scope_name]
                shot_name = f'shot_{shot_num}'
                
                if shot_name in scope_group:
                    raise RuntimeError(f"Shot {shot_num} already exists for scope {scope_name}")
                    
                shot_group = scope_group.create_group(shot_name)
                shot_group.attrs['acquisition_time'] = time.ctime()
                shot_group.attrs['scope_type'] = 'Rigol DHO Series'
                
                for tr in traces:
                    if tr not in data:
                        continue
                        
                    trace_data = np.asarray(data[tr], dtype=np.int16)
                    
                    # Set chunk size for optimal I/O
                    chunk_size = (min(len(trace_data), 8*1024*1024),)
                    
                    # Create datasets with compression
                    data_ds = shot_group.create_dataset(
                        f'{tr}_data',
                        data=trace_data,
                        dtype='int16',
                        chunks=chunk_size,
                        compression='lzf',
                        shuffle=True,
                        fletcher32=True
                    )
                    
                    header_ds = shot_group.create_dataset(
                        f'{tr}_header', 
                        data=np.void(headers[tr])
                    )
                    
                    # Add metadata
                    full_channel_key = f"{scope_name}_{tr}"
                    data_ds.attrs['description'] = self.get_channel_description(full_channel_key)
                    data_ds.attrs['dtype'] = 'int16'
                    data_ds.attrs['acquisition_method'] = 'Rigol hardware trigger'
                    header_ds.attrs['description'] = f'Rigol preamble data for {tr}'

#===============================================================================================================================================
# RIGOL ACQUISITION FUNCTIONS
#===============================================================================================================================================

def rigol_single_shot_acquisition(rda, active_scopes, shot_num):
    """Acquire a single shot from Rigol scopes using hardware trigger"""
    
    # Arm all Rigol scopes for hardware trigger
    rda.arm_scopes_for_trigger(active_scopes)
    
    print("\n GENERATE TRIGGER SIGNAL NOW!")
    print("   Scopes are armed and waiting for trigger on C4")
    print("   Looking for RISING edge at 0.1V threshold")
    
    rda.wait_for_trigger_completion(active_scopes, trigger_timeout=60)
    
    all_data = rda.acquire_shot(active_scopes, shot_num)
    
    if all_data:
        print('Updating Rigol scope data to HDF5...')
        rda.update_scope_hdf5(all_data, shot_num)
    else:
        print(f"Warning: No valid data acquired from Rigol scopes at shot {shot_num}")

#===============================================================================================================================================
# MAIN ACQUISITION FUNCTION
#===============================================================================================================================================

def run_rigol_acquisition(save_path=None, config_path='experiment_config.txt'):
    """Main function to run Rigol-based diamagnetic acquisition
    
    Args:
        save_path: Optional path for HDF5 file. If None, generates timestamped filename.
        config_path: Path to configuration file
    """
    
    # Generate timestamped filename if no save_path provided
    if save_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = f"rigol_diamagnetic_{timestamp}.h5"
        print(f"Generated filename: {save_path}")
    
    print('Starting Rigol DHO diamagnetic acquisition at', time.ctime())
    print(f'Data will be saved to: {save_path}')
    
    # Load configuration
    config, raw_config_text = load_experiment_config(config_path)
    num_duplicate_shots = int(config.get('nshots', 'num_duplicate_shots', fallback=1))
    num_run_repeats = int(config.get('nshots', 'num_run_repeats', fallback=1))
    
    # Initialize Rigol acquisition system
    with RigolDimagAcquisition(save_path, config, raw_config_text) as rda:
        try:
            # Initialize HDF5 file structure
            print("Initializing HDF5 file for Rigol data...", end='')
            rda.initialize_hdf5_base()
            print(" ✓")
            
            # Initialize Rigol scopes
            print("\nStarting Rigol scope initialization...")
            active_scopes = rda.initialize_scopes()
            
            if not active_scopes:
                raise RuntimeError("No valid Rigol scopes found. Check connections and IP addresses.")
            
            # Calculate total shots
            total_shots = num_duplicate_shots * num_run_repeats
            print(f"\nTotal shots to acquire: {total_shots}")
            
            # Main acquisition loop
            for shot_num in range(1, total_shots + 1):
                acquisition_start_time = time.time()
                
                print(f'\n--- Shot {shot_num}/{total_shots} ---')
                
                # Acquire single shot from all Rigol scopes
                rigol_single_shot_acquisition(rda, active_scopes, shot_num)
                
                # Calculate and display progress
                time_per_shot = time.time() - acquisition_start_time
                remaining_shots = total_shots - shot_num
                remaining_time = remaining_shots * time_per_shot
                
                print(f'Shot {shot_num} completed in {time_per_shot:.2f}s | '
                      f'Remaining time: {remaining_time/60:.2f}min')
                
        except KeyboardInterrupt:
            print(f'\n--- Acquisition halted by user at {time.ctime()} ---')
            raise

        finally:
            # Store final shot count for each scope
            try:
                with h5py.File(save_path, 'a') as f:
                    for scope_name in rda.scope_ips:
                        if scope_name in f:
                            scope_group = f[scope_name]
                            scope_group.attrs['final_shot_count'] = shot_num if 'shot_num' in locals() else 0
                            print(f"Stored final shot count for {scope_name}: {scope_group.attrs['final_shot_count']}")
            except Exception as e:
                logging.error(f"Error storing final shot count: {e}")

    print(f"\nRigol DHO diamagnetic acquisition completed at {time.ctime()}")
    print(f"Data saved to: {save_path}")
    return save_path  # Return the actual filename used

#===============================================================================================================================================
# ENHANCED FILENAME GENERATION FUNCTION
#===============================================================================================================================================

def generate_rigol_filename(base_name="rigol_diamagnetic", extension=".h5", 
                           include_microseconds=False):
    """Generate timestamped filename for Rigol data files
    
    Args:
        base_name: Base name for the file
        extension: File extension (default .h5)
        include_microseconds: Include microseconds in timestamp for ultra-precise timing
        
    Returns:
        str: Timestamped filename
        
    Examples:
        rigol_diamagnetic_20250905_173045.h5
        rigol_diamagnetic_20250905_173045_123456.h5 (with microseconds)
    """
    if include_microseconds:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    return f"{base_name}_{timestamp}{extension}"

def get_next_numbered_filename(base_path):
    """Get next available numbered filename if base exists
    
    Args:
        base_path: Base filename path
        
    Returns:
        str: Next available filename
        
    Example:
        If rigol_diamagnetic_20250905_173045.h5 exists,
        returns rigol_diamagnetic_20250905_173045_001.h5
    """
    if not os.path.exists(base_path):
        return base_path
    
    base, ext = os.path.splitext(base_path)
    counter = 1
    
    while True:
        new_path = f"{base}_{counter:03d}{ext}"
        if not os.path.exists(new_path):
            return new_path
        counter += 1
        
        # Safety check to prevent infinite loop
        if counter > 999:
            raise RuntimeError("Too many files with similar names (>999)")

#===============================================================================================================================================
# USAGE
#===============================================================================================================================================

if __name__ == "__main__":
    
    config_path = "experiment_config.txt"
    
    try:
        actual_filename = run_rigol_acquisition(config_path=config_path)
        print(f"\nAcquisition completed successfully!")
        print(f"\n Data file: {actual_filename}")
        
    except Exception as e:
        logging.error(f"Acquisition failed: {e}")
        raise