# -*- coding: utf-8 -*-
"""
Rigol DHO800/DHO900 Scope Header access class
Based on DHO800/DHO900 Programming Guide

@author: Converted for Rigol DHO by GitHub Copilot
"""

import collections
import numpy as np
import datetime

RIGOL_WAVEDESC_SIZE = 256  # Native Rigol header size

# Rigol DHO waveform preamble structure
RigolWaveformPreamble = collections.namedtuple('RigolWaveformPreamble', [
    'format',        # Data format (0=BYTE, 1=WORD, 2=ASC)
    'type',          # Acquisition type (0=NORM, 1=PEAK, 2=AVER, 3=ULTR)
    'points',        # Number of data points
    'count',         # Always 1
    'x_increment',   # Time interval between data points
    'x_origin',      # Time of first data point
    'x_reference',   # Reference time (usually 0)
    'y_increment',   # Voltage difference between data points
    'y_origin',      # Voltage at center of screen
    'y_reference'    # Reference voltage (usually 127 for BYTE format)
])

# Extended header for HDF5 storage (includes additional metadata)
RigolWaveformHeader = collections.namedtuple('RigolWaveformHeader', [
    # From preamble
    'format', 'type', 'points', 'count',
    'x_increment', 'x_origin', 'x_reference',
    'y_increment', 'y_origin', 'y_reference',
    
    # Channel settings
    'channel',           # Channel name (CHANnel1, CHANnel2, etc.)
    'channel_scale',     # Vertical scale (V/div)
    'channel_offset',    # Vertical offset
    'channel_coupling',  # Coupling (AC, DC, GND)
    'channel_bwlimit',   # Bandwidth limit
    'channel_probe',     # Probe ratio
    'channel_units',     # Channel units
    
    # Timebase settings
    'timebase_scale',    # Horizontal scale (s/div)
    'timebase_offset',   # Horizontal offset
    'timebase_mode',     # Timebase mode (MAIN, DELay, etc.)
    
    # Acquisition settings
    'sample_rate',       # Sample rate (Sa/s)
    'memory_depth',      # Memory depth
    'acquire_type',      # Acquisition type (NORMal, AVERages, etc.)
    'acquire_averages',  # Number of averages (if applicable)
    
    # Trigger settings
    'trigger_mode',      # Trigger mode (EDGE, PULSe, etc.)
    'trigger_sweep',     # Trigger sweep (AUTO, NORMal, SINGle)
    'trigger_source',    # Trigger source
    'trigger_level',     # Trigger level
    'trigger_slope',     # Trigger slope
    
    # Instrument info
    'instrument_id',     # Full instrument identification
    'model',            # Scope model (DHO804, DHO924S, etc.)
    'serial',           # Serial number
    'firmware',         # Firmware version
    
    # Timing and waveform info
    'acquisition_time',  # Time when data was acquired
    'waveform_start',    # Start point of waveform
    'waveform_stop',     # Stop point of waveform
])

# Constants for data types and acquisition modes specific to DHO series
RIGOL_DHO_FORMAT_BYTE = 0
RIGOL_DHO_FORMAT_WORD = 1
RIGOL_DHO_FORMAT_ASCII = 2

RIGOL_DHO_TYPE_NORMAL = 0
RIGOL_DHO_TYPE_PEAK = 1
RIGOL_DHO_TYPE_AVERAGE = 2
RIGOL_DHO_TYPE_ULTRA = 3

# Memory depth options for DHO series
RIGOL_DHO_MEMORY_DEPTHS = [
    "AUTO", "1k", "10k", "100k", "1M", "5M", "10M", "25M", "50M"
]

# Acquisition types for DHO series
RIGOL_DHO_ACQUIRE_TYPES = [
    "NORMal", "PEAK", "AVERages", "ULTRa"
]

# Trigger modes for DHO series
RIGOL_DHO_TRIGGER_MODES = [
    "EDGE", "PULSe", "SLOPe", "VIDeo", "PATTern", "DURation", 
    "TIMeout", "RUNT", "WINDows", "DELay", "SHOLd", "NEDGe",
    "RS232", "IIC", "SPI", "CAN", "LIN"
]

# Simplified Rigol channel mapping
RIGOL_CHANNELS = ['CHANnel1', 'CHANnel2', 'CHANnel3', 'CHANnel4']

# Rigol coupling types (simplified)
RIGOL_COUPLINGS = ['DC', 'AC', 'GND']

# Rigol formats  
RIGOL_DATA_FORMATS = ['BYTE', 'WORD', 'ASCII']

class RigolWaveformHeaderProcessor:
    """
    Process Rigol waveform headers from preamble data
    Native Rigol DHO implementation
    """
    
    def __init__(self, scope=None):
        self.scope = scope
        self._cache = {}
    
    def process_preamble(self, preamble_string, channel='C1'):
        """
        Process Rigol preamble string into header structure
        """
        try:
            # Parse comma-separated preamble
            values = [x.strip() for x in preamble_string.split(',')]
            
            if len(values) < 10:
                return self._get_default_preamble()
            
            return {
                'format': int(float(values[0])),
                'type': int(float(values[1])),
                'points': int(float(values[2])),
                'count': int(float(values[3])),
                'x_increment': float(values[4]),
                'x_origin': float(values[5]),
                'x_reference': float(values[6]),
                'y_increment': float(values[7]),
                'y_origin': float(values[8]),
                'y_reference': float(values[9]) if len(values) > 9 else 127.0
            }
            
        except Exception as e:
            return self._get_default_preamble()
    
    def create_header_from_scope(self, channel='C1'):
        """
        Create complete header from live scope data
        """
        if not self.scope:
            raise ValueError("No scope instance available")
        
        try:
            # Get preamble
            preamble_str = self.scope.query(f':WAVeform:SOURce {channel}; :WAVeform:PREamble?')
            preamble_data = self.process_preamble(preamble_str, channel)
            
            # Get additional scope settings
            header_dict = self._build_complete_header(preamble_data, channel)
            
            return RigolScopeHeader(hdr_data=header_dict)
            
        except Exception as e:
            print(f"Error creating header from scope: {e}")
            return RigolScopeHeader()  # Return empty header
    
    def _build_complete_header(self, preamble_data, channel):
        """
        Build complete header dictionary from preamble and scope settings
        """
        try:
            # Get scope settings
            timebase_scale = self._query_with_cache(':TIMebase:MAIN:SCALe?', float, 1e-6)
            vertical_scale = self._query_with_cache(f':CHANnel{channel[-1]}:SCALe?', float, 0.1)
            sample_rate = self._query_with_cache(':ACQuire:SRATe?', float, 1e6)
            
            # Get instrument info
            idn_response = self._query_with_cache('*IDN?', str, 'RIGOL,DHO804,Unknown,Unknown')
            idn_parts = idn_response.split(',') if ',' in idn_response else ['RIGOL', 'DHO804', 'Unknown', 'Unknown']
            
            # Build complete header - FIXED FIELD NAMES
            header_dict = {
                # From preamble
                'format': preamble_data['format'],
                'type': preamble_data['type'],
                'points': preamble_data['points'],
                'count': preamble_data['count'],
                'x_increment': preamble_data['x_increment'],
                'x_origin': preamble_data['x_origin'],
                'x_reference': preamble_data['x_reference'],
                'y_increment': preamble_data['y_increment'],
                'y_origin': preamble_data['y_origin'],
                'y_reference': preamble_data['y_reference'],
                
                # Channel configuration - FIXED FIELD NAMES
                'channel': f'CHANnel{channel[-1]}',  # Match namedtuple
                'channel_scale': vertical_scale,
                'channel_offset': 0.0,
                'channel_coupling': 'DC',
                'channel_bwlimit': 'OFF',
                'channel_probe': 1.0,
                'channel_units': 'V',
                
                # Timebase configuration
                'timebase_scale': timebase_scale,
                'timebase_offset': 0.0,
                'timebase_mode': 'MAIN',
                
                # Acquisition settings
                'sample_rate': sample_rate,
                'memory_depth': 'AUTO',
                'acquire_type': 'NORMal',
                'acquire_averages': 1,
                
                # Trigger information
                'trigger_mode': 'EDGE',
                'trigger_sweep': 'AUTO',
                'trigger_source': f'CHANnel{channel[-1]}',
                'trigger_level': 0.0,
                'trigger_slope': 'POS',
                
                # Instrument identification - FIXED FIELD NAMES
                'instrument_id': idn_response,  # Full IDN string
                'model': idn_parts[1] if len(idn_parts) > 1 else 'DHO804',  # Match namedtuple
                'serial': idn_parts[2] if len(idn_parts) > 2 else 'Unknown',  # Match namedtuple
                'firmware': idn_parts[3] if len(idn_parts) > 3 else 'Unknown',  # Match namedtuple
                
                # Timing and waveform info - ADD MISSING FIELDS
                'acquisition_time': datetime.datetime.now().isoformat(),
                'waveform_start': 0,  
                'waveform_stop': preamble_data['points'] - 1, 
            }
            
            return header_dict
            
        except Exception as e:
            # Return basic header from preamble only
            return {**preamble_data, **self._get_default_header_fields()}
    
    def _query_with_cache(self, command, convert_func, default_value):
        """Query scope with caching to reduce SCPI traffic"""
        if command in self._cache:
            return self._cache[command]
        
        try:
            if self.scope:
                response = self.scope.query(command)
                value = convert_func(response.strip())
                self._cache[command] = value
                return value
        except:
            pass
        
        return default_value
    
    def _get_default_header_fields(self):
        """Get default header fields for fallback"""
        return {
            'channel': 'CHANnel1',             
            'channel_scale': 0.1,
            'channel_offset': 0.0,
            'channel_coupling': 'DC',
            'channel_bwlimit': 'OFF',
            'channel_probe': 1.0,
            'channel_units': 'V',
            'timebase_scale': 1e-6,
            'timebase_offset': 0.0,
            'timebase_mode': 'MAIN',
            'sample_rate': 1e6,
            'memory_depth': 'AUTO',
            'acquire_type': 'NORMal',
            'acquire_averages': 1,
            'trigger_mode': 'EDGE',
            'trigger_sweep': 'AUTO',
            'trigger_source': 'CHANnel1',
            'trigger_level': 0.0,
            'trigger_slope': 'POS',
            'instrument_id': 'RIGOL DHO',       
            'model': 'DHO804',                  
            'serial': 'Unknown',                
            'firmware': 'Unknown',              
            'acquisition_time': datetime.datetime.now().isoformat(),
            'waveform_start': 0,                
            'waveform_stop': 1199,              
        }
    
    def clear_cache(self):
        """Clear query cache"""
        self._cache.clear()

    @staticmethod
    def header_to_dict(header):
        """Convert header namedtuple to dictionary for HDF5 storage"""
        return header._asdict()
    
    @staticmethod
    def dict_to_header(header_dict):
        """Convert dictionary back to header namedtuple"""
        return RigolWaveformHeader(**header_dict)
    
    @staticmethod
    def calculate_time_array(header):
        """Calculate time array from header information"""
        return np.arange(header.points) * header.x_increment + header.x_origin
    
    @staticmethod
    def get_acquisition_type_string(type_code):
        """Convert acquisition type code to string"""
        type_map = {
            0: 'NORMAL',
            1: 'PEAK',
            2: 'AVERAGE',
            3: 'ULTRA'
        }
        return type_map.get(type_code, f'UNKNOWN_{type_code}')
    
    @staticmethod
    def get_format_string(format_code):
        """Convert format code to string"""
        format_map = {
            0: 'BYTE',
            1: 'WORD',
            2: 'ASCII'
        }
        return format_map.get(format_code, f'UNKNOWN_{format_code}')
    
    @staticmethod
    def validate_dho_model(model_string):
        """Validate if the model is a supported DHO series"""
        supported_models = [
            'DHO802', 'DHO804', 'DHO812', 'DHO814',  # DHO800 series
            'DHO914', 'DHO914S', 'DHO924', 'DHO924S'  # DHO900 series
        ]
        return any(model in model_string for model in supported_models)
    
    @staticmethod
    def get_channel_count(model_string):
        """Get number of channels based on model"""
        if any(model in model_string for model in ['DHO802', 'DHO812']):
            return 2  # 2+EXT channel models
        else:
            return 4  # 4 channel models
    
    @staticmethod
    def get_max_memory_depth(model_string, channels_enabled=1):
        """Get maximum memory depth based on model and number of enabled channels"""
        is_dho900 = any(model in model_string for model in ['DHO914', 'DHO924'])
        
        if channels_enabled == 1:
            return "50M" if is_dho900 else "25M"
        elif channels_enabled == 2:
            return "25M" if is_dho900 else "10M"
        elif channels_enabled >= 3:
            return "10M" if is_dho900 else "5M"
        else:
            return "AUTO"
    
    def _get_default_preamble(self):
        """Get default preamble values"""
        return {
            'format': 0,
            'type': 0, 
            'points': 1200,
            'count': 1,
            'x_increment': 1e-6,
            'x_origin': 0.0,
            'x_reference': 0.0,
            'y_increment': 0.01,
            'y_origin': 0.0,
            'y_reference': 127.0
        }
    
class RigolScopeHeader:
    """
    Main Rigol DHO scope header class
    Native Rigol DHO implementation for telnet communication
    """
    
    def __init__(self, hdr_data=None, scope=None, channel=None):
        """
        Initialize Rigol scope header

        """
        self._data = {}
        self._preamble = None
        self._time_array = None
        
        if isinstance(hdr_data, dict):
            # Dictionary header data
            self._data = hdr_data.copy()
        elif scope and channel:
            # Create from live scope
            self._create_from_scope(scope, channel)
        else:
            # Empty header with defaults
            self._set_defaults()
    
    def _create_from_scope(self, scope, channel):
        """Create header from live scope data using TEXT preamble"""
        try:
            preamble_str = scope.query(f':WAVeform:SOURce {channel}; :WAVeform:PREamble?')
            processor = RigolWaveformHeaderProcessor(scope)
            preamble_data = processor.process_preamble(preamble_str, channel)
            
            self._data = processor._build_complete_header(preamble_data, channel)
            self._data['header_source'] = 'live_scope'
        except Exception as e:
            self._set_defaults()
    
    def _set_defaults(self):
        """Set default header values with ALL required fields"""
        self._data = {
            # Preamble fields
            'format': 0, 'type': 0, 'points': 1200, 'count': 1,
            'x_increment': 1e-6, 'x_origin': 0.0, 'x_reference': 0.0,
            'y_increment': 0.01, 'y_origin': 0.0, 'y_reference': 127.0,
            
            # Channel settings - MATCH namedtuple field names
            'channel': 'CHANnel1',  
            'channel_scale': 0.1,
            'channel_offset': 0.0,
            'channel_coupling': 'DC',
            'channel_bwlimit': 'OFF',
            'channel_probe': 1.0,
            'channel_units': 'V',
            
            # Timebase settings
            'timebase_scale': 1e-6,
            'timebase_offset': 0.0,
            'timebase_mode': 'MAIN',
            
            # Acquisition settings
            'sample_rate': 1e6,
            'memory_depth': 'AUTO',
            'acquire_type': 'NORMal',
            'acquire_averages': 1,
            
            # Trigger settings
            'trigger_mode': 'EDGE',
            'trigger_sweep': 'AUTO',
            'trigger_source': 'CHANnel1',
            'trigger_level': 0.0,
            'trigger_slope': 'POS',
            
            # Instrument info - MATCH namedtuple field names
            'instrument_id': 'RIGOL DHO804',  
            'model': 'DHO804',                
            'serial': 'Unknown',              
            'firmware': 'Unknown',            
            
            # Timing - ADD missing fields
            'acquisition_time': datetime.datetime.now().isoformat(),
            'waveform_start': 0,              
            'waveform_stop': 1199,            
            
            'header_source': 'default'
        }
    
    # Core waveform properties
    @property
    def num_samples(self):
        """Number of samples in waveform"""
        return self._data.get('points', 1200)
    
    @property
    def dt(self):
        """Time increment between samples"""
        return self._data.get('x_increment', 1e-6)
    
    @property
    def t0(self):
        """Time of first sample"""
        return self._data.get('x_origin', 0.0)
    
    @property
    def timebase(self):
        """Timebase scale (s/div)"""
        return self._data.get('timebase_scale', 1e-6)
    
    @property
    def vertical_gain(self):
        """Vertical gain (V/LSB)"""
        return self._data.get('y_increment', 0.01)
    
    @property
    def vertical_offset(self):
        """Vertical offset"""
        return self._data.get('y_origin', 0.0)
    
    @property
    def vertical_coupling(self):
        """Vertical coupling"""
        return self._data.get('channel_coupling', 'DC')
    
    @property
    def sample_rate(self):
        """Sample rate (Sa/s)"""
        return self._data.get('sample_rate', 1e6)
    
    @property
    def time_array(self):
        """Time array for waveform"""
        if self._time_array is None:
            try:
                num_samples = self.num_samples
                dt = self.dt
                t0 = self.t0
                
                if num_samples > 0 and dt > 0:
                    self._time_array = np.arange(num_samples) * dt + t0
                else:
                    self._time_array = np.arange(1200) * 1e-6  # Default fallback
                    
            except Exception as e:
                self._time_array = np.arange(1200) * 1e-6  # Default fallback
                
        return self._time_array
    
    @property
    def channel_name(self):
        """Channel name (alias for channel)"""
        return self._data.get('channel', 'CHANnel1')

    @property  
    def model(self):
        """Scope model"""
        return self._data.get('model', 'DHO804')

    @property
    def memory_depth(self):
        """Memory depth setting"""
        return self._data.get('memory_depth', 'AUTO')

    @property
    def acquisition_time(self):
        """Acquisition timestamp"""
        return self._data.get('acquisition_time', datetime.datetime.now().isoformat())
    
    @property
    def averages(self):
        """Number of averages"""
        return self._data.get('acquire_averages', 1)

    @property
    def nominal_bits(self):
        """Nominal bit resolution"""
        format_val = self._data.get('format', 0)
        return 8 if format_val == 0 else 16  # BYTE=8 bits, WORD=16 bits

    @property
    def vertical_units(self):
        """Vertical units"""
        return self._data.get('channel_units', 'V')

    @property
    def horizontal_units(self):
        """Horizontal units"""
        return 's'  # Always seconds for time domain

    @property
    def scaling_info(self):
        """Voltage scaling information"""
        return f"{self.vertical_gain} V/LSB, offset: {self.vertical_offset} V"

    @property
    def timing_info(self):
        """Timing information"""
        return f"dt = {self.dt*1e6:.3f} µs, start: {self.t0*1e6:.3f} µs"
    
    def get_acquisition_time_dict(self):
        """Get acquisition time as dictionary"""
        try:
            if 'acquisition_time' in self._data:
                # Parse ISO format timestamp
                dt = datetime.datetime.fromisoformat(self._data['acquisition_time'].replace('Z', '+00:00'))
            else:
                dt = datetime.datetime.now()
            
            return {
                'year': dt.year,
                'month': dt.month,
                'day': dt.day,
                'hour': dt.hour,
                'minute': dt.minute,
                'second': dt.second,
                'microsecond': dt.microsecond
            }
        except Exception:
            # Fallback to current time
            dt = datetime.datetime.now()
            return {
                'year': dt.year,
                'month': dt.month,
                'day': dt.day,
                'hour': dt.hour,
                'minute': dt.minute,
                'second': dt.second,
                'microsecond': dt.microsecond
            }
    
    def convert_raw_to_voltage(self, raw_data):
        """Convert raw data to voltage"""
        y_ref = self._data.get('y_reference', 127.0)
        y_gain = self.vertical_gain  
        y_offset = self.vertical_offset  

        return (raw_data - y_ref) * y_gain + y_offset
    
    def to_dict(self):
        """Convert header to dictionary"""
        return self._data.copy()
    
    @classmethod
    def from_dict(cls, header_dict):
        """Create header from dictionary"""
        return cls(hdr_data=header_dict)
    
    @classmethod
    def from_preamble_string(cls, preamble_str):
        """Create header from Rigol preamble string"""
        try:
            values = [x.strip() for x in preamble_str.split(',')]
            if len(values) >= 10:
                header_dict = {
                    'format': int(float(values[0])),
                    'type': int(float(values[1])),
                    'points': int(float(values[2])),
                    'count': int(float(values[3])),
                    'x_increment': float(values[4]),
                    'x_origin': float(values[5]),
                    'x_reference': float(values[6]),
                    'y_increment': float(values[7]),
                    'y_origin': float(values[8]),
                    'y_reference': float(values[9]),
                    'header_source': 'preamble_string'
                }
                return cls(hdr_data=header_dict)
        except Exception as e:
            print(f"Error parsing preamble string: {e}")
        
        return cls()  # Return default header
    
    def dump(self):
        """Dump all header fields for debugging"""
        s = ""
        for key, value in sorted(self._data.items()):
            s += f"{str(type(value)).ljust(20)}{str(key).ljust(25)}{str(value)}\n"
        return s
    
    def __str__(self):
        """String representation"""
        return f"RigolScopeHeader({self.num_samples} samples, {self.dt*1e6:.1f}µs/sample)"
    
    def __repr__(self):
        """Detailed representation"""
        return f"RigolScopeHeader(samples={self.num_samples}, dt={self.dt}, source={self._data.get('header_source', 'unknown')})"

# Utility functions for header processing
def compare_rigol_trigger_times(header1, header2, tolerance_seconds=1.0, debug=False):
    """Compare trigger times of two Rigol headers"""
    try:
        time1 = header1.get_acquisition_time_dict()
        time2 = header2.get_acquisition_time_dict()
        
        dt1 = datetime.datetime(time1['year'], time1['month'], time1['day'],
                              time1['hour'], time1['minute'], time1['second'],
                              time1['microsecond'])
        dt2 = datetime.datetime(time2['year'], time2['month'], time2['day'],
                              time2['hour'], time2['minute'], time2['second'],
                              time2['microsecond'])
        
        diff = abs((dt2 - dt1).total_seconds())
        
        if debug:
            print(f'Rigol trigger time difference: {diff} seconds')
        
        return diff <= tolerance_seconds
        
    except Exception as e:
        if debug:
            print(f"Error comparing trigger times: {e}")
        return False