#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Rigol DHO800/DHO900 Scope Communication Class
Consolidated telnet communication for Rigol DHO series oscilloscopes.

Based on RoGeorge's original functions with DHO compatibility
@author: RoGeorge, enhanced and consolidated for DHO series
"""

import time
import numpy as np
import logging
from telnetlib_receive_all import Telnet
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import socket

RIGOL_CHANNELS = ['CHANnel1', 'CHANnel2', 'CHANnel3', 'CHANnel4'] 
RIGOL_MATH_CHANNELS = ['MATH1', 'MATH2', 'MATH3', 'MATH4']
RIGOL_VALID_TRACES = ['C1', 'C2', 'C3', 'C4', 'MATH1', 'MATH2', 'MATH3', 'MATH4']

class RigolScope:
    """Consolidated class for Rigol DHO800/DHO900 series oscilloscopes via telnet"""
    
    def __init__(self, ipv4_addr, verbose=True, timeout=5000):
        """Initialize connection to Rigol scope"""
        self.verbose = verbose
        self.ip_address = ipv4_addr
        self.scope_ip = ipv4_addr
        self.port = 5555
        self.timeout = timeout / 1000.0
        self.tn = None
        self.connected = False
        
        self.idn_string = ''
        self.model = ''
        self.serial = ''
        self.firmware = ''
        self.valid_trace_names = ()
        self.offscale_fraction = 0.005
        
        self.channels = ['CHANnel1', 'CHANnel2', 'CHANnel3', 'CHANnel4']
        self.math_channels = ['MATH1', 'MATH2', 'MATH3', 'MATH4']
        self.channel_map = {
            'C1': 'CHANnel1', 'C2': 'CHANnel2', 
            'C3': 'CHANnel3', 'C4': 'CHANnel4'
        }
        
        self.rm_status = self.rm_open(ipv4_addr)
        if not self.rm_status:
            raise(RuntimeError('Failed to connect to scope'))
        
        self._discover_valid_traces()
        self.scope_series = self._detect_scope_series()
        self.current_header_data = {}  
        self.manufacturer = ''

    def command(self, scpi, timeout=20, binary_data=False):
        """Send SCPI command to Rigol scope via telnet"""
        
        if scpi.endswith('?'):
            self.tn.write((scpi + "\n").encode("utf-8"))
            
            if binary_data or ':WAVeform:DATA?' in scpi.upper() or ':DISPlay:DATA?' in scpi.upper():
                try:
                    response = b""
                    start_time = time.time()
                    max_total_timeout = timeout
                    max_idle_timeout = 3.0
                    last_data_time = start_time
                    
                    header_attempts = 0
                    while not response.startswith(b'#') and time.time() - start_time < max_total_timeout:
                        try:
                            chunk = self.tn.read_some()
                            if chunk:
                                response += chunk
                                last_data_time = time.time()
                            else:
                                if time.time() - last_data_time > max_idle_timeout:
                                    header_attempts += 1
                                    if header_attempts > 3:
                                        break
                                    self.tn.write(b"\n")
                                    time.sleep(0.5)
                                    last_data_time = time.time()
                                else:
                                    time.sleep(0.05)
                        except Exception as e:
                            time.sleep(0.05)
                    
                    if not response.startswith(b'#'):
                        raise TimeoutError(f"No TMC header received after {header_attempts} attempts")
                    
                    if len(response) < 2:
                        raise ValueError(f"TMC header too short: {len(response)} bytes")
                    
                    try:
                        length_digits = int(chr(response[1]))
                        if length_digits < 1 or length_digits > 9:
                            raise ValueError(f"Invalid TMC length digits: {length_digits}")
                    except (ValueError, IndexError) as e:
                        raise ValueError(f"Cannot parse TMC header: {e}")
                    
                    header_length = 2 + length_digits
                    
                    retry_count = 0
                    while len(response) < header_length and time.time() - start_time < max_total_timeout:
                        try:
                            chunk = self.tn.read_some()
                            if chunk:
                                response += chunk
                                last_data_time = time.time()
                                retry_count = 0
                            else:
                                if time.time() - last_data_time > max_idle_timeout:
                                    retry_count += 1
                                    if retry_count > 5:
                                        break
                                    time.sleep(0.2)
                                    last_data_time = time.time()
                                else:
                                    time.sleep(0.05)
                        except Exception as e:
                            time.sleep(0.05)
                    
                    if len(response) < header_length:
                        raise ValueError(f"Incomplete TMC header: got {len(response)}, need {header_length}")
                    
                    try:
                        data_length_str = response[2:header_length].decode('ascii')
                        data_length = int(data_length_str)
                        if data_length <= 0:
                            raise ValueError(f"Invalid data length: {data_length}")
                    except Exception as e:
                        raise ValueError(f"Cannot parse data length: {e}")
                    
                    total_expected = header_length + data_length
                    
                    last_progress = 0
                    retry_count = 0
                    
                    while len(response) < total_expected and time.time() - start_time < max_total_timeout:
                        try:
                            remaining = total_expected - len(response)
                            chunk_size = min(remaining, 32768)
                            
                            chunk = self.tn.read_some()
                            if chunk:
                                response += chunk
                                last_data_time = time.time()
                                retry_count = 0
                                
                                progress = (len(response) / total_expected) * 100
                                if progress - last_progress >= 10 and self.verbose:
                                    print(f"<:> Data transfer: {progress:.1f}% ({len(response)}/{total_expected})")
                                    last_progress = progress
                                
                            else:
                                if time.time() - last_data_time > max_idle_timeout:
                                    retry_count += 1
                                    if retry_count > 10:
                                        break
                                    time.sleep(0.5)
                                    last_data_time = time.time()
                                else:
                                    time.sleep(0.02)
                                    
                        except Exception as e:
                            time.sleep(0.05)
                    
                    completion_percentage = (len(response) / total_expected * 100) if total_expected > 0 else 0
                    
                    if len(response) >= total_expected:
                        if self.verbose:
                            print(f"<:> Transfer complete: {len(response)} bytes (100.0%)")
                        return response
                    elif completion_percentage >= 90.0:
                        if self.verbose:
                            print(f"<:> Transfer mostly complete: {completion_percentage:.1f}%")
                        missing = total_expected - len(response)
                        if missing < data_length // 10:
                            response += b'\x80' * missing
                            return response
                        else:
                            raise TimeoutError(f"Too much data missing: {completion_percentage:.1f}%")
                    else:
                        raise TimeoutError(f"Transfer failed: got {len(response)}/{total_expected} bytes ({completion_percentage:.1f}%)")
                        
                except Exception as e:
                    raise RuntimeError(f"Binary data read failed: {e}")
            
            else:
                try:
                    response = self.tn.read_until(b"\n", timeout)
                    if response:
                        return response.decode("utf-8", errors='ignore').strip()
                    else:
                        return ""
                except Exception as e:
                    return ""
        
        else:
            try:
                self.tn.write((scpi + "\n").encode("utf-8"))
                if any(cmd in scpi.upper() for cmd in [':TRIGger:', ':ACQuire:', ':CHANnel:', ':TIMebase:']):
                    time.sleep(0.05)
                return ""
            except Exception as e:
                return "command error"

    def get_memory_depth(self):
        """Get scope memory depth"""
        try:
            response = self.command(':ACQuire:MDEPth?')
            if not response:
                return 12000
            
            response = response.strip()
            if 'E' in response.upper() or 'e' in response:
                return int(float(response))
            else:
                return int(response)
        except (ValueError, TypeError) as e:
            return 12000

    def check_scope_response(self):
        """Check if scope is responding properly"""
        try:
            idn = self.command('*IDN?')
            return bool(idn and 'RIGOL' in idn.upper())
        except Exception as e:
            return False

    def get_sample_rate(self):
        """Get actual sample rate from scope"""
        try:
            response = self.command(':ACQuire:SRATe?')
            if response and response.strip():
                try:
                    return float(response.strip()) 
                except ValueError:
                    pass
            
            timebase_response = self.command(':TIMebase:MAIN:SCALe?')
            memory_depth = self.get_memory_depth()
            
            if timebase_response:
                timebase = float(timebase_response.strip())
                total_time = 10.0 * timebase
                sample_rate = memory_depth / total_time
                return sample_rate
            
            return 1e6
        except Exception as e:
            return 1e6

    def clear_telnet_buffer(self):
        """Clear any remaining data in telnet buffer"""
        try:
            start_time = time.time()
            bytes_cleared = 0
            
            while time.time() - start_time < 1.0:
                try:
                    chunk = self.tn.read_some()
                    if chunk:
                        bytes_cleared += len(chunk)
                    else:
                        break  
                except:
                    break
            
            if bytes_cleared > 0 and self.verbose:
                print(f"<:> Cleared {bytes_cleared} bytes from telnet buffer")
        except Exception as e:
            if self.verbose:
                print(f"Buffer clear error: {e}")

    def get_timebase_scale(self):
        """Get current timebase scale"""
        try:
            response = self.command(':TIMebase:MAIN:SCALe?')
            return float(response.strip()) if response else 1e-6
        except:
            return 1e-6

    def __repr__(self):
        return f"RigolScope({self.ip_address})"
    
    def __str__(self):
        txt = f"Rigol DHO Scope at {self.ip_address}\n"
        txt += f"Model: {self.model}\n"
        txt += f"Serial: {self.serial}\n"
        txt += f"Firmware: {self.firmware}\n"
        
        displayed = self.displayed_traces()
        for tr in displayed:
            scale = self.vertical_scale(tr)
            txt += f"{tr}: {scale}V/div\n"
        
        timebase = self.get_timebase_scale()
        txt += f"Timebase: {timebase}s/div\n"
        
        memory_depth = self.max_samples()
        txt += f"Memory depth: {memory_depth} points\n"
        
        return txt
    
    def __bool__(self):
        return self.connected and self.rm_status
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__del__()
    
    def __del__(self):
        self.disconnect()
    
    def rm_open(self, ipv4_addr) -> bool:
        """Open connection to Rigol scope"""
        if self.tn is not None:
            return True
        
        if self.verbose:
            print(f'<:> attempting to connect to Rigol scope at {ipv4_addr}')
        
        try:
            self.tn = Telnet(ipv4_addr, self.port, timeout=self.timeout)
            self.connected = True
            
            self.idn_string = self.command("*IDN?")
            if self.idn_string == "command error":
                raise ConnectionError("Scope not responding to commands")
            
            id_parts = self.idn_string.strip().split(',')
            if len(id_parts) >= 4:
                self.manufacturer = id_parts[0]
                self.model = id_parts[1] 
                self.serial = id_parts[2]
                self.firmware = id_parts[3]
            
            if self.verbose:
                print(f'<:> {self.idn_string}')
            
            return True
            
        except Exception as e:
            if self.verbose:
                print(f'Scope not found at "{ipv4_addr}": {e}')
            return False
    
    def rm_close(self):
        self.disconnect()
    
    def disconnect(self):
        """Close telnet connection"""
        if self.tn:
            self.tn.close()
            self.tn = None
            self.connected = False
            if self.verbose:
                print("Disconnected from Rigol scope")
    
    def screen_dump(self, fig_name='Rigol Screen', white_background=False, png_fn='rigol_screen_dump.png', 
                show_plot=True):
        """Screen dump using raw telnet socket methods"""
        
        try:
            try:
                self.tn.read_very_eager()
            except:
                pass
            
            command_str = ':DISPlay:DATA?\n'
            self.tn.write(command_str.encode('ascii'))
            
            sock = self.tn.get_socket()
            sock.settimeout(10.0)
            
            header_data = b''
            while len(header_data) < 11:
                try:
                    chunk = sock.recv(11 - len(header_data))
                    if not chunk:
                        raise ValueError("Connection closed while reading header")
                    header_data += chunk
                except socket.timeout:
                    raise ValueError("Timeout reading TMC header")
            
            if not header_data.startswith(b'#'):
                raise ValueError(f"Invalid TMC header: {header_data}")
            
            num_digits = int(chr(header_data[1]))
            byte_count_str = header_data[2:2+num_digits].decode('ascii')
            byte_count = int(byte_count_str)
            
            if self.verbose:
                print(f'<:> TMC header: #{num_digits}{byte_count_str} ({byte_count} bytes expected)')
            
            png_data = header_data[11:]
            bytes_needed = byte_count - len(png_data)
            
            while bytes_needed > 0:
                try:
                    chunk_size = min(bytes_needed, 8192)
                    chunk = sock.recv(chunk_size)
                    
                    if not chunk:
                        raise ValueError("Connection closed while reading data")
                    
                    png_data += chunk
                    bytes_needed -= len(chunk)
                    
                    if self.verbose and len(png_data) % 20000 == 0:
                        progress = (len(png_data) / byte_count) * 100
                        print(f'<:> Progress: {len(png_data)}/{byte_count} bytes ({progress:.1f}%)')
                        
                except socket.timeout:
                    raise ValueError(f"Timeout reading data. Got {len(png_data)}/{byte_count} bytes")
            
            if not png_data.startswith(b'\x89PNG'):
                raise ValueError(f"Invalid PNG signature. First 10 bytes: {png_data[:10]}")
            
            with open(png_fn, 'wb') as f:
                f.write(png_data)
            
            if self.verbose:
                print(f'<:> Screenshot saved as {png_fn} ({len(png_data)} bytes)')
            
            if show_plot:
                try:
                    img = mpimg.imread(png_fn)
                    plt.figure(fig_name, figsize=(12, 8))
                    plt.imshow(img)
                    plt.axis('off')
                    plt.title(f'Rigol DHO804 Screen Capture')
                    plt.tight_layout()
                    plt.show()
                except Exception as e:
                    print(f"Error displaying image: {e}")
            
            return png_fn
            
        except Exception as e:
            print(f"Screen capture failed: {e}")
            return None

    def write_status_msg(self, message):
        """Write status message"""
        if self.verbose:
            print(f"<:> Status: {message}")

    def validate_channel(self, Cn) -> str:
        """Validate and convert channel name"""
        if isinstance(Cn, str):
            if Cn in ['C1', 'C2', 'C3', 'C4']:
                return f'CHANnel{Cn[1]}'
            elif Cn.startswith('CHANnel') and Cn[-1] in '1234':
                return Cn
        elif isinstance(Cn, int) and 1 <= Cn <= 4:
            return f'CHANnel{Cn}'
        
        raise RuntimeError(f'Invalid channel: {Cn}. Must be C1-C4 or CHANnel1-CHANnel4')
    
    def validate_trace(self, tr) -> str:
        """Validate trace name"""
        if isinstance(tr, int) and 1 <= tr <= 4:
            return f'C{tr}'
        
        if tr in self.valid_trace_names:
            return tr
        
        if tr in self.channel_map:
            return tr
        
        raise RuntimeError(f'validate_trace(): trace name "{tr}" is unknown')

    def _discover_valid_traces(self):
        """Discover which traces are available on this scope"""
        if len(self.valid_trace_names) == 0:
            valid_traces = []
            
            for trace in ['C1', 'C2', 'C3', 'C4']:
                try:
                    response = self.command(f":{self.validate_channel(trace)}:DISPlay?")
                    if response != "command error":
                        valid_traces.append(trace)
                except:
                    pass
            
            for trace in ['MATH1', 'MATH2', 'MATH3', 'MATH4']:
                try:
                    response = self.command(f":{trace}:DISPlay?")
                    if response != "command error":
                        valid_traces.append(trace)
                except:
                    pass
            
            self.valid_trace_names = tuple(valid_traces)
            if self.verbose:
                print(f'<:> Valid traces: {self.valid_trace_names}')

    def get_expanded_name(self, trace):
        """Get expanded channel name for HDF5 storage"""
        name_map = {
            'C1': 'Channel1', 'C2': 'Channel2', 
            'C3': 'Channel3', 'C4': 'Channel4',
            'MATH1': 'Math1', 'MATH2': 'Math2',
            'MATH3': 'Math3', 'MATH4': 'Math4'
        }
        return name_map.get(trace, trace)

    def max_samples(self, N=0) -> int:
        """Get maximum samples from scope settings only"""
        if N > 0:
            if self.verbose:
                print(f"<:> Setting memory depth not supported - use scope front panel")
            return N
        
        try:
            return self.get_memory_depth()
        except Exception as e:
            if self.verbose:
                print(f"Error getting memory depth: {e}")
            return 1000

    def displayed_channels(self) -> tuple:
        """Return displayed CHANNELS only"""
        channels = []
        
        for ch_abbrev in ['C1', 'C2', 'C3', 'C4']:
            try:
                ch_full = self.validate_channel(ch_abbrev)
                response = self.command(f":{ch_full}:DISPlay?")
                if response.strip() == "1":
                    channels.append(ch_abbrev)
            except:
                pass
        
        return tuple(channels)
    
    def displayed_traces(self) -> tuple:
        """Return displayed TRACES including math"""
        traces = []
        
        for trace in ['C1', 'C2', 'C3', 'C4']:
            try:
                ch_full = self.validate_channel(trace)
                response = self.command(f":{ch_full}:DISPlay?")
                if response.strip() == "1":
                    traces.append(trace)
            except:
                pass
        
        for trace in ['MATH1', 'MATH2', 'MATH3', 'MATH4']:
            try:
                response = self.command(f":{trace}:DISPlay?")
                if response.strip() == "1":
                    traces.append(trace)
            except:
                pass
        
        return tuple(traces)

    def vertical_scale(self, trace) -> float:
        """Get vertical scale setting"""
        trace_validated = self.validate_trace(trace)
        
        if trace_validated in ['C1', 'C2', 'C3', 'C4']:
            ch_full = self.validate_channel(trace_validated)
            response = self.command(f":{ch_full}:SCALe?")
        else:
            response = self.command(f":{trace_validated}:SCALe?")
        
        return float(response.strip())
    
    def set_vertical_scale(self, trace, scale) -> float:
        """Set vertical scale"""
        trace_validated = self.validate_trace(trace)
        
        if trace_validated in ['C1', 'C2', 'C3', 'C4']:
            ch_full = self.validate_channel(trace_validated)
            self.command(f":{ch_full}:SCALe {scale}")
        else:
            self.command(f":{trace_validated}:SCALe {scale}")
        
        return self.vertical_scale(trace)

    def averaging_count(self) -> int:
        """Get averaging count"""
        response = self.command(":ACQuire:AVERages?")
        return int(response.strip())
    
    def set_averaging_count(self, NSweeps=1):
        """Set averaging count"""
        if NSweeps < 1:
            NSweeps = 1
        if NSweeps > 1000000:
            NSweeps = 1000000
        
        if NSweeps > 1:
            self.command(":ACQuire:TYPE AVERages")
            self.command(f":ACQuire:AVERages {NSweeps}")
        else:
            self.command(":ACQuire:TYPE NORMal")
    
    def max_averaging_count(self) -> tuple:
        """Get max averaging count across displayed channels"""
        NSweeps = self.averaging_count()
        displayed = self.displayed_channels()
        
        if not displayed:
            raise RuntimeError('max_averaging_count(): no displayed channels')
        
        return NSweeps, displayed[0]

    def wait_for_max_sweeps(self, aux_text='', timeout=100):
        """Wait for averaging to complete"""
        NSweeps, channel = self.max_averaging_count()
        
        if self.verbose:
            print(f"NSweeps is {NSweeps}")
        
        self.write_status_msg(aux_text + f'Waiting for averaging({NSweeps}) to complete')
        
        if NSweeps == 1:
            if self.verbose:
                print('"SINGLE" mode acquisition...')
            
            self.command(":CLEar")
            time.sleep(0.05)
            
            print('      Starting single sweep acquisition...', end='', flush=True)
            
            self.set_trigger_mode('SINGLE')
            
            start_time = time.time()
            scope_stopped = False
            
            while time.time() - start_time < timeout:
                time.sleep(0.01)
                status = self.command(":TRIGger:STATus?").strip()
                
                if status in ['STOP', 'TD']:
                    scope_stopped = True
                    break
            
            print(' Complete!' if scope_stopped else ' Timed out!')
            
            timed_out = not scope_stopped
            n = 1 if scope_stopped else 0
            
        else:
            if self.verbose:
                print(f'"NORM" acquisition with scope internal averaging over {NSweeps} sweeps.')
            timed_out, n = self.wait_for_sweeps(channel, NSweeps, timeout)
        
        if timed_out:
            msg = f'averaging timed out at:{n}/{NSweeps} after {timeout:.1f}s'
        else:
            msg = f'averaging({NSweeps}), completed, got {n}'
        
        self.write_status_msg(aux_text + msg)
        return timed_out, n
    
    def wait_for_sweeps(self, channel, NSweeps, timeout=100, sleep_interval=0.1):
        """Wait for scope internal averaging to complete"""
        channel = self.validate_trace(channel)
        
        self.set_averaging_count(NSweeps)
        
        self.command(":CLEar")
        time.sleep(0.25)
        self.set_trigger_mode('NORM')
        
        timeout_time = time.time() + timeout
        print(f'      Waiting for {NSweeps} sweeps: 0/{NSweeps}', end='', flush=True)
        
        timed_out = True
        
        while time.time() < timeout_time:
            time.sleep(sleep_interval)
            
            try:
                acq_status = self.command(":TRIGger:STATus?").strip()
                
                if acq_status in ['STOP', 'TD']:
                    current_count = self.averaging_count()
                    if current_count >= NSweeps:
                        timed_out = False
                        break
                        
            except Exception as e:
                if self.verbose:
                    print(f'Error checking averaging status: {e}')
                time.sleep(0.1)
        
        self.set_trigger_mode('STOP')
        final_count = NSweeps if not timed_out else 0
        print(f'\r      Waiting for {NSweeps} sweeps: {final_count}/{NSweeps} - Complete!')
        
        return timed_out, final_count

    def parse_header(self, hdr, trace_bytes):
        """Parse header and return sample info"""
        if hdr['comm_type'] not in [0, 1]:
            raise RuntimeError(f"Invalid comm_type: {hdr['comm_type']}")

        if trace_bytes.startswith(b'#'):
            try:
                length_digits = int(chr(trace_bytes[1]))
                data_length = int(trace_bytes[2:2+length_digits].decode('ascii'))
                
                if hdr['comm_type'] == 0:
                    NSamples = data_length
                else:
                    NSamples = data_length // 2
                    
                ndx0 = 2 + length_digits
                
            except Exception as e:
                if self.verbose:
                    print(f"TMC parsing error: {e}")
                raise RuntimeError(f"Failed to parse TMC header: {e}")
        else:
            NSamples = hdr['wave_array_1']
            ndx0 = 0

        if NSamples == 0:
            raise RuntimeError("NSamples = 0 - no data available")
        
        return NSamples, ndx0
        
    def acquire_bytes(self, trace, seg=0):
        """Force RAW mode to get all memory points"""
        trace = self.validate_trace(trace)

        if self.verbose:
            print(f'\n<:> reading {trace} from scope')

        t0 = time.time()

        try:
            self.clear_telnet_buffer()
            time.sleep(0.1)
            
            if trace in ['C1', 'C2', 'C3', 'C4']:
                ch_full = self.validate_channel(trace)
                self.command(f':WAVeform:SOURce {ch_full}')
            else:
                self.command(f':WAVeform:SOURce {trace}')
            
            time.sleep(0.2)
            
            self.command(':WAVeform:MODE RAW')
            time.sleep(0.2)
            
            self.command(':WAVeform:FORMat BYTE')
            time.sleep(0.1)
            
            self.command(':WAVeform:STARt 1')
            time.sleep(0.1)
            self.command(':WAVeform:STOP MAX')
            time.sleep(0.2)
            
            mode_check = self.command(':WAVeform:MODE?')
            if mode_check.strip() != 'RAW':
                print(f"    WARNING: Still in {mode_check.strip()} mode, not RAW")
            
            preamble = self.command(':WAVeform:PREamble?')
            if preamble:
                values = preamble.split(',')
                if len(values) >= 3:
                    expected_points = int(float(values[2]))
                    print(f"    RAW mode expects: {expected_points:,} points")
            
            if self.verbose:
                print("   Requesting waveform data...")

            trace_bytes = self.command(':WAVeform:DATA?', timeout=15, binary_data=True)
            
            preamble_str = self.command(':WAVeform:PREamble?', timeout=5)
            if not preamble_str or ',' not in preamble_str:
                raise RuntimeError("Failed to get valid preamble")
            
            header_bytes = preamble_str.encode('utf-8')

            t1 = time.time()
            if self.verbose:
                print(f'    .............................{t1-t0:.1f} sec')

            return trace_bytes, header_bytes

        except Exception as e:
            raise RuntimeError(f"acquire_bytes failed for {trace}: {e}")
    
    def get_header_bytes(self, trace):
        """Get header bytes for trace"""
        if trace in self.current_header_data:
            return self.current_header_data[trace]
        else:
            _, header_bytes = self.acquire_bytes(trace)
            return header_bytes

    def acquire(self, trace, seg=0, raw=False):
        """Acquire scope data"""
        
        try:
            trace_bytes, header_bytes = self.acquire_bytes(trace, seg)
            
            hdr = self.translate_header_bytes(header_bytes)
            NSamples, ndx0 = self.parse_header(hdr, trace_bytes)
            
            if self.verbose:
                print('<:> computing data values')
            
            t0 = time.time()
            
            if hdr['comm_type'] == 0:
                if trace_bytes.startswith(b'#'):
                    try:
                        length_digits = int(chr(trace_bytes[1]))
                        data_length = int(trace_bytes[2:2+length_digits].decode('ascii'))
                        ndx0 = 2 + length_digits
                        
                        binary_data = trace_bytes[ndx0:ndx0 + data_length]
                        raw_adc = np.frombuffer(binary_data, dtype=np.uint8)
                        
                        if len(raw_adc) == 0:
                            raise RuntimeError("No binary data received")
                        
                        if raw:
                            data = raw_adc
                        else:
                            data = (raw_adc.astype(np.float32) - hdr['y_reference']) * hdr['y_increment'] + hdr['y_origin']
                            
                    except Exception as e:
                        raise RuntimeError(f"Error parsing TMC data for {trace}: {e}")
                else:
                    raise RuntimeError(f"Invalid TMC header for {trace}")
            else:
                raise NotImplementedError("WORD data format not yet supported")
            
            t1 = time.time()
            if self.verbose:
                print(f'    .............................{t1-t0:.1f} sec')
            
            return data, header_bytes
            
        except Exception as e:
            raise RuntimeError(f"Complete acquire failure for {trace}: {e}")

    def _create_rigol_header_bytes(self, preamble_str, trace):
        """Create header from preamble string"""
        return preamble_str.encode('utf-8')

    def translate_header_bytes(self, header_bytes):
        """Translate header bytes to dictionary"""
        try:
            if isinstance(header_bytes, bytes):
                preamble_str = header_bytes.decode('utf-8')
            else:
                preamble_str = str(header_bytes)
        
            values = preamble_str.split(',')
            
            if len(values) >= 10:
                try:
                    format_val = int(float(values[0]))
                    points_val = int(float(values[2]))
                    
                    return {
                        'points': points_val,
                        'format': format_val,
                        'x_increment': float(values[4]),
                        'x_origin': float(values[5]),
                        'y_increment': float(values[7]),
                        'y_origin': float(values[8]),
                        'y_reference': float(values[9]),
                        'trace': 'C1',
                        'comm_type': format_val,
                        'wave_array_1': points_val,
                        'vertical_gain': float(values[7]),
                        'vertical_offset': float(values[8]),
                        'horiz_interval': float(values[4]),
                        'horiz_offset': float(values[5]),
                        'subarray_count': 1,
                        'sweeps_per_acq': 1
                    }
                except (ValueError, IndexError) as e:
                    raise RuntimeError(f"Header parsing error: {e}")
            
            raise ValueError("Invalid preamble format")
            
        except Exception as e:
            raise RuntimeError(f"Error translating header: {e}")

    def get_current_displayed_traces(self):
        """Get currently displayed traces - fresh check"""
        traces = []
        
        for trace in ['C1', 'C2', 'C3', 'C4']:
            try:
                ch_full = self.validate_channel(trace)
                response = self.command(f":{ch_full}:DISPlay?")
                if response and response.strip() == "1":
                    traces.append(trace)
            except:
                pass
        
        for trace in ['MATH1', 'MATH2', 'MATH3', 'MATH4']:
            try:
                response = self.command(f":{trace}:DISPlay?")
                if response and response.strip() == "1":
                    traces.append(trace)
            except:
                pass
        
        return tuple(traces)

    def time_array(self, trace):
        """Create time array without calling acquire_bytes"""
        try:
            if trace in ['C1', 'C2', 'C3', 'C4']:
                ch_full = self.validate_channel(trace)
                self.command(f':WAVeform:SOURce {ch_full}')
            else:
                self.command(f':WAVeform:SOURce {trace}')
            
            preamble_str = self.command(':WAVeform:PREamble?')
            values = preamble_str.split(',')
            
            if len(values) >= 6:
                points = int(float(values[2]))
                x_increment = float(values[4])
                x_origin = float(values[5])
                
                return np.linspace(x_origin, x_origin + points * x_increment, points, endpoint=False)
            else:
                raise ValueError("Invalid preamble format")
                
        except Exception as e:
            raise RuntimeError(f"time_array error: {e}")
        
    def set_trigger_mode(self, trigger_mode) -> str:
        """Set trigger mode"""
        prev_mode = self.command(":TRIGger:SWEep?").strip()
        
        mode_map = {
            'AUTO': 'AUTO',
            'NORM': 'NORMal',
            'SINGLE': 'SINGle', 
            'STOP': 'STOP'
        }
        
        if trigger_mode in mode_map:
            rigol_mode = mode_map[trigger_mode]
            self.command(f":TRIGger:SWEep {rigol_mode}")
            
            for i in range(25):
                actual = self.command(":TRIGger:SWEep?").strip()
                if actual.upper().startswith(trigger_mode[:3].upper()):
                    break
                if self.verbose:
                    print(f'set_trigger_mode({trigger_mode}) attempt {i}: got {actual}')
                time.sleep(0.1)
        
        return prev_mode
    
    def get_actual_acquisition_points(self, channel='C1'):
        """Get the actual number of points that will be acquired"""
        try:
            if channel:
                channel_num = channel[-1]
                self.command(f':WAVeform:SOURce CHANnel{channel_num}')
            
            preamble_response = self.command(':WAVeform:PREamble?')
            
            if preamble_response:
                preamble_data = preamble_response.strip().split(',')
                if len(preamble_data) >= 3:
                    actual_points = int(float(preamble_data[2]))
                    
                    if self.verbose:
                        print(f'<:> Actual acquisition points: {actual_points}')
                    
                    return actual_points
            
            return None
            
        except Exception as e:
            if self.verbose:
                print(f'Error getting actual points: {e}')
            return None

    def safe_scale_change(self, trace, new_scale):
        """Safely change channel scale without hanging scope"""
        trace_validated = self.validate_trace(trace)
        
        if trace_validated in ['C1', 'C2', 'C3', 'C4']:
            ch_full = self.validate_channel(trace_validated)
            
            try:
                current_scale = self.command(f':{ch_full}:SCALe?').strip()
                if self.verbose:
                    print(f"   Current {trace} scale: {current_scale} V/div")
            except:
                current_scale = "unknown"
            
            try:
                self.command(':STOP')
                time.sleep(0.1)
                
                self.command(f':{ch_full}:SCALe {new_scale}')
                time.sleep(0.2)
                
                actual_scale = self.command(f':{ch_full}:SCALe?').strip()
                
                self.command(':RUN')
                time.sleep(0.2)
                
                if self.verbose:
                    print(f"   Changed {trace} scale: {current_scale} -> {actual_scale} V/div")
                
                return current_scale, actual_scale
                
            except Exception as e:
                try:
                    self.command(':RUN')
                except:
                    pass
                raise RuntimeError(f"Scale change failed: {e}")
        
        else:
            raise ValueError(f"Scale change not supported for {trace}")
    
    def _detect_scope_series(self):
        """Detect scope series from IDN string"""
        if 'MSO5' in self.idn_string:
            return 'MSO5000'
        elif 'DHO8' in self.idn_string or 'DHO9' in self.idn_string:
            return 'DHO800/900'
        else:
            return 'UNKNOWN'
