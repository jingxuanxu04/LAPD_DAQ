# -*- coding: utf-8 -*-
"""
Enhanced GUI for visualizing Rigol HDF5 scope data
Supports both old and new shot-based formats for diamagnetic measurements
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import numpy as np
import os
from read_rigol_data import (
    read_rigol_hdf5_data_universal, detect_hdf5_format, 
    list_available_shots, list_available_channels_new_format,
    list_available_channels_old_format, analyze_diamagnetic_shot,
    examine_hdf5_file, get_file_info_new_format
)
import h5py

class RigolDataVisualizer:
    def __init__(self, root):
        self.root = root
        self.root.title("Rigol Diamagnetic Data Visualizer")
        self.root.geometry("1400x900")
        
        # Data storage
        self.current_file = None
        self.file_format = None
        self.data_channels = {}
        self.time_arrays = {}
        self.current_shot = 1
        self.available_shots = []
        self.available_channels = []
        
        self.setup_gui()
        
    def setup_gui(self):
        """Setup the enhanced GUI layout"""
        
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Control panel (left side) - made wider
        control_frame = ttk.LabelFrame(main_frame, text="Controls", padding="5")
        control_frame.grid(row=0, column=0, rowspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        control_frame.configure(width=300)  # Fixed width
        
        # File selection
        ttk.Button(control_frame, text="Open HDF5 File", command=self.open_file).grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.file_label = ttk.Label(control_frame, text="No file selected", wraplength=280)
        self.file_label.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Format display
        self.format_label = ttk.Label(control_frame, text="Format: Unknown", foreground="blue")
        self.format_label.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=2)
        
        # Shot selection (for new format)
        self.shot_frame = ttk.LabelFrame(control_frame, text="Shot Selection", padding="3")
        self.shot_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Label(self.shot_frame, text="Shot:").grid(row=0, column=0, sticky=tk.W)
        self.shot_var = tk.IntVar(value=1)
        self.shot_spinbox = tk.Spinbox(self.shot_frame, from_=1, to=1, textvariable=self.shot_var,
                                      command=self.on_shot_changed, width=10)
        self.shot_spinbox.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        self.shot_info_label = ttk.Label(self.shot_frame, text="No shots available")
        self.shot_info_label.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        # Channel selection
        ttk.Label(control_frame, text="Channels:").grid(row=4, column=0, sticky=tk.W, pady=(10, 0))
        
        self.channel_frame = ttk.Frame(control_frame)
        self.channel_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Analysis controls
        analysis_frame = ttk.LabelFrame(control_frame, text="Analysis", padding="3")
        analysis_frame.grid(row=6, column=0, sticky=(tk.W, tk.E), pady=5)
        
        ttk.Button(analysis_frame, text="Analyze Current Shot", 
                  command=self.analyze_current_shot).grid(row=0, column=0, sticky=(tk.W, tk.E), pady=2)
        
        ttk.Button(analysis_frame, text="Compare Shots", 
                  command=self.compare_shots_dialog).grid(row=1, column=0, sticky=(tk.W, tk.E), pady=2)
        
        # Plot options
        plot_options_frame = ttk.LabelFrame(control_frame, text="Plot Options", padding="3")
        plot_options_frame.grid(row=7, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.grid_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(plot_options_frame, text="Show Grid", variable=self.grid_var, 
                       command=self.update_plot).grid(row=0, column=0, sticky=tk.W)
        
        self.legend_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(plot_options_frame, text="Show Legend", variable=self.legend_var, 
                       command=self.update_plot).grid(row=1, column=0, sticky=tk.W)
        
        self.trigger_line_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(plot_options_frame, text="Show Trigger Line", variable=self.trigger_line_var,
                       command=self.update_plot).grid(row=2, column=0, sticky=tk.W)
        
        # Time and voltage units
        ttk.Label(plot_options_frame, text="Time Units:").grid(row=3, column=0, sticky=tk.W, pady=(10, 0))
        self.time_unit_var = tk.StringVar(value="milliseconds")
        time_combo = ttk.Combobox(plot_options_frame, textvariable=self.time_unit_var, 
                                 values=["seconds", "milliseconds", "microseconds"], width=12)
        time_combo.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=2)
        time_combo.bind('<<ComboboxSelected>>', lambda e: self.update_plot())
        
        ttk.Label(plot_options_frame, text="Voltage Units:").grid(row=5, column=0, sticky=tk.W, pady=(5, 0))
        self.voltage_unit_var = tk.StringVar(value="millivolts")
        voltage_combo = ttk.Combobox(plot_options_frame, textvariable=self.voltage_unit_var,
                                   values=["volts", "millivolts", "microvolts"], width=12)
        voltage_combo.grid(row=6, column=0, sticky=(tk.W, tk.E), pady=2)
        voltage_combo.bind('<<ComboboxSelected>>', lambda e: self.update_plot())
        
        # Update and export buttons
        ttk.Button(control_frame, text="Update Plot", command=self.update_plot).grid(row=8, column=0, sticky=(tk.W, tk.E), pady=10)
        ttk.Button(control_frame, text="Export Data", command=self.export_data).grid(row=9, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # Info display (top right)
        info_frame = ttk.LabelFrame(main_frame, text="File Info", padding="5")
        info_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N), pady=(0, 10))
        
        self.info_text = tk.Text(info_frame, height=10, width=60)
        info_scrollbar = ttk.Scrollbar(info_frame, orient="vertical", command=self.info_text.yview)
        self.info_text.configure(yscrollcommand=info_scrollbar.set)
        
        self.info_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        info_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Plot area (bottom right)
        plot_frame = ttk.LabelFrame(main_frame, text="Waveform Plot", padding="5")
        plot_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        plot_frame.columnconfigure(0, weight=1)
        plot_frame.rowconfigure(0, weight=1)
        
        # Create matplotlib figure
        self.fig = Figure(figsize=(10, 6), dpi=100)
        self.ax = self.fig.add_subplot(111)
        
        # Create canvas
        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Navigation toolbar
        toolbar_frame = ttk.Frame(plot_frame)
        toolbar_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        
        try:
            toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
            toolbar.update()
        except Exception as e:
            print(f"Warning: Could not create navigation toolbar: {e}")
        
        # Initialize plot
        self.ax.set_title("No data loaded")
        self.ax.set_xlabel("Time")
        self.ax.set_ylabel("Voltage") 
        self.canvas.draw()
        
    def open_file(self):
        """Open and load HDF5 file"""
        file_path = filedialog.askopenfilename(
            title="Select Rigol HDF5 File",
            filetypes=[("HDF5 files", "*.h5"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                self.load_file(file_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file:\n{str(e)}")
                import traceback
                traceback.print_exc()
    
    def load_file(self, file_path):
        """Load data from HDF5 file"""
        self.current_file = file_path
        self.file_format = detect_hdf5_format(file_path)
        
        # Update file label
        filename = os.path.basename(file_path)
        self.file_label.config(text=f"File: {filename}")
        self.format_label.config(text=f"Format: {self.file_format}")
        
        # Load shots and channels based on format
        if self.file_format == 'new_shot_based':
            self.available_shots = list_available_shots(file_path)
            if self.available_shots:
                self.current_shot = 1
                self.shot_var.set(1)
                self.shot_spinbox.config(to=len(self.available_shots))
                self.shot_info_label.config(text=f"Shots available: {len(self.available_shots)}")
                self.available_channels = list_available_channels_new_format(file_path, 1)
            else:
                self.shot_info_label.config(text="No shots found")
                self.available_channels = []
        else:
            self.available_channels = list_available_channels_old_format(file_path)
            self.shot_info_label.config(text="Old format - no shot selection")
            
        # Create channel checkboxes
        self.create_channel_checkboxes()
        
        # Load data for current shot
        self.load_current_shot_data()
        
        # Update displays
        self.update_info_display()
        self.update_plot()
    
    def create_channel_checkboxes(self):
        """Create channel selection checkboxes"""
        for widget in self.channel_frame.winfo_children():
            widget.destroy()
        
        self.channel_vars = {}
        for i, channel in enumerate(self.available_channels):
            var = tk.BooleanVar(value=True)
            self.channel_vars[channel] = var
            ttk.Checkbutton(self.channel_frame, text=channel, variable=var,
                          command=self.update_plot).grid(row=i, column=0, sticky=tk.W)
    
    def load_current_shot_data(self):
        """Load data for current shot"""
        if not self.current_file or not self.available_channels:
            return
            
        self.data_channels = {}
        self.time_arrays = {}
        
        for channel in self.available_channels:
            try:
                if self.file_format == 'new_shot_based':
                    signal, time = read_rigol_hdf5_data_universal(
                        self.current_file, channel, self.current_shot)
                else:
                    signal, time = read_rigol_hdf5_data_universal(
                        self.current_file, channel, 0)  # position_index for old format
                
                self.data_channels[channel] = signal
                self.time_arrays[channel] = time
                
            except Exception as e:
                print(f"Error loading {channel}: {e}")
    
    def on_shot_changed(self):
        """Handle shot selection change"""
        if self.file_format != 'new_shot_based':
            return
            
        try:
            new_shot = self.shot_var.get()
            if new_shot != self.current_shot and new_shot <= len(self.available_shots):
                self.current_shot = new_shot
                self.load_current_shot_data()
                self.update_plot()
        except Exception as e:
            print(f"Error changing shot: {e}")
    
    def update_info_display(self):
        """Update the info text display"""
        if not self.current_file:
            return
        
        info_text = f"File: {os.path.basename(self.current_file)}\n"
        info_text += f"Format: {self.file_format}\n"
        info_text += f"Path: {self.current_file}\n\n"
        
        if self.file_format == 'new_shot_based':
            info_text += f"Current Shot: {self.current_shot}\n"
            info_text += f"Total Shots: {len(self.available_shots)}\n\n"
            
            # Get file info
            try:
                file_info = get_file_info_new_format(self.current_file)
                if 'sample_rate' in file_info:
                    info_text += f"Sample Rate: {file_info['sample_rate']/1e6:.2f} MSa/s\n"
                if 'time_range' in file_info:
                    time_span = file_info['time_range'][1] - file_info['time_range'][0]
                    info_text += f"Time Span: {time_span*1000:.1f} ms\n"
                if 'time_points' in file_info:
                    info_text += f"Time Points: {file_info['time_points']}\n"
                info_text += "\n"
            except Exception as e:
                info_text += f"File info error: {e}\n\n"
        
        # Channel info
        for channel, data in self.data_channels.items():
            if data is not None and len(data) > 0:
                time_array = self.time_arrays.get(channel)
                
                # Voltage stats
                v_min, v_max = np.min(data), np.max(data)
                v_rms = np.sqrt(np.mean(data**2))
                v_pk_pk = v_max - v_min
                
                info_text += f"{channel}:\n"
                info_text += f"  Samples: {len(data)}\n"
                info_text += f"  Range: {v_min*1000:.2f} to {v_max*1000:.2f} mV\n"
                info_text += f"  Peak-to-Peak: {v_pk_pk*1000:.2f} mV\n"
                info_text += f"  RMS: {v_rms*1000:.2f} mV\n"
                
                # Trigger analysis (assume center is trigger)
                if len(data) > 10:
                    center = len(data) // 2
                    pre_mean = np.mean(data[:center])
                    post_mean = np.mean(data[center:])
                    response = post_mean - pre_mean
                    info_text += f"  Trigger Response: {response*1000:.3f} mV\n"
                
                info_text += "\n"
        
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(1.0, info_text)
    
    def update_plot(self):
        """Update the plot with current settings"""
        if not self.data_channels:
            self.ax.clear()
            self.ax.set_title("No data loaded")
            self.ax.set_xlabel("Time")
            self.ax.set_ylabel("Voltage")
            self.canvas.draw()
            return
        
        self.ax.clear()
        
        # Get scaling factors
        time_scale, time_label = self.get_time_scaling()
        voltage_scale, voltage_label = self.get_voltage_scaling()
        
        # Plot selected channels
        colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown']
        plot_count = 0
        
        for channel, data in self.data_channels.items():
            if channel in self.channel_vars and self.channel_vars[channel].get():
                if data is not None and len(data) > 0:
                    time_data = self.time_arrays.get(channel)
                    
                    if time_data is not None:
                        time_plot = time_data * time_scale
                        voltage_plot = data * voltage_scale
                        
                        # Ensure arrays match in length
                        min_length = min(len(time_plot), len(voltage_plot))
                        time_plot = time_plot[:min_length]
                        voltage_plot = voltage_plot[:min_length]
                        
                        color = colors[plot_count % len(colors)]
                        self.ax.plot(time_plot, voltage_plot, 
                                   label=f"{channel} ({min_length} pts)", 
                                   color=color, linewidth=1.0)
                        plot_count += 1
        
        # Add trigger line at center (for new format)
        if (self.trigger_line_var.get() and self.file_format == 'new_shot_based' 
            and plot_count > 0):
            # Find time at center
            first_channel = next(iter(self.data_channels.keys()))
            if first_channel in self.time_arrays:
                time_data = self.time_arrays[first_channel]
                if len(time_data) > 0:
                    center_time = time_data[len(time_data) // 2] * time_scale
                    self.ax.axvline(x=center_time, color='red', linestyle='--', 
                                  alpha=0.7, label='Trigger')
        
        # Set labels and title
        self.ax.set_xlabel(f'Time ({time_label})')
        self.ax.set_ylabel(f'Voltage ({voltage_label})')
        
        if self.file_format == 'new_shot_based':
            title = f'Shot {self.current_shot} - {os.path.basename(self.current_file) if self.current_file else ""}'
        else:
            title = f'Rigol Data - {os.path.basename(self.current_file) if self.current_file else ""}'
        self.ax.set_title(title)
        
        # Grid and legend
        if self.grid_var.get():
            self.ax.grid(True, alpha=0.3)
        
        if self.legend_var.get() and plot_count > 0:
            self.ax.legend()
        
        # Auto-scale
        if plot_count > 0:
            self.ax.relim()
            self.ax.autoscale()
        else:
            self.ax.text(0.5, 0.5, 'No valid data to plot', 
                        transform=self.ax.transAxes, ha='center', va='center')
        
        self.canvas.draw()
    
    def get_time_scaling(self):
        """Get time scaling factor and label"""
        unit = self.time_unit_var.get()
        if unit == "milliseconds":
            return 1000, "ms"
        elif unit == "microseconds":
            return 1e6, "µs"
        else:  # seconds
            return 1, "s"
    
    def get_voltage_scaling(self):
        """Get voltage scaling factor and label"""
        unit = self.voltage_unit_var.get()
        if unit == "millivolts":
            return 1000, "mV"
        elif unit == "microvolts":
            return 1e6, "µV"
        else:  # volts
            return 1, "V"
    
    def analyze_current_shot(self):
        """Analyze the current shot"""
        if not self.current_file or not self.available_channels:
            messagebox.showwarning("Warning", "No data to analyze")
            return
        
        try:
            if self.file_format == 'new_shot_based':
                analysis = analyze_diamagnetic_shot(self.current_file, self.current_shot, 
                                                  self.available_channels)
                self.show_analysis_results(analysis)
            else:
                messagebox.showinfo("Info", "Analysis not implemented for old format yet")
                
        except Exception as e:
            messagebox.showerror("Error", f"Analysis failed:\n{str(e)}")
    
    def show_analysis_results(self, analysis):
        """Show analysis results in a new window"""
        results_window = tk.Toplevel(self.root)
        results_window.title(f"Analysis Results - Shot {analysis['shot_number']}")
        results_window.geometry("500x400")
        
        # Create text widget with scrollbar
        text_frame = ttk.Frame(results_window, padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        text_widget = tk.Text(text_frame, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Format analysis results
        results_text = f"Analysis Results - Shot {analysis['shot_number']}\n"
        results_text += "=" * 50 + "\n\n"
        
        # Time info
        time_info = analysis['time_info']
        results_text += f"Time Information:\n"
        results_text += f"  Sample Rate: {time_info['sample_rate']/1e6:.2f} MSa/s\n"
        results_text += f"  Time Span: {time_info['time_span']*1000:.2f} ms\n"
        results_text += f"  Points: {time_info['time_points']}\n\n"
        
        # Channel analysis
        for channel, ch_data in analysis['channels'].items():
            if 'stats' in ch_data:
                stats = ch_data['stats']
                results_text += f"{channel} Statistics:\n"
                results_text += f"  Mean: {stats['mean']*1000:.3f} mV\n"
                results_text += f"  Peak-to-Peak: {stats['peak_to_peak']*1000:.3f} mV\n"
                results_text += f"  RMS: {stats['rms']*1000:.3f} mV\n"
                results_text += f"  Pre-trigger: {stats['pre_trigger_mean']*1000:.3f} mV\n"
                results_text += f"  Post-trigger: {stats['post_trigger_mean']*1000:.3f} mV\n"
                results_text += f"  Trigger Response: {stats['trigger_response']*1000:.3f} mV\n\n"
        
        # Correlations
        if 'correlations' in analysis['analysis']:
            results_text += "Channel Correlations:\n"
            for pair, corr in analysis['analysis']['correlations'].items():
                results_text += f"  {pair}: {corr:.3f}\n"
        
        text_widget.insert(1.0, results_text)
        text_widget.config(state=tk.DISABLED)
    
    def compare_shots_dialog(self):
        """Open dialog to compare different shots"""
        if self.file_format != 'new_shot_based' or len(self.available_shots) < 2:
            messagebox.showwarning("Warning", "Need at least 2 shots in new format for comparison")
            return
        
        # Create comparison window
        comp_window = tk.Toplevel(self.root)
        comp_window.title("Compare Shots")
        comp_window.geometry("300x200")
        
        ttk.Label(comp_window, text="Select shots to compare:").pack(pady=10)
        
        # Shot selection
        shot_frame = ttk.Frame(comp_window)
        shot_frame.pack(pady=10)
        
        ttk.Label(shot_frame, text="Shot 1:").grid(row=0, column=0, padx=5)
        shot1_var = tk.IntVar(value=1)
        shot1_spin = tk.Spinbox(shot_frame, from_=1, to=len(self.available_shots), 
                               textvariable=shot1_var, width=10)
        shot1_spin.grid(row=0, column=1, padx=5)
        
        ttk.Label(shot_frame, text="Shot 2:").grid(row=1, column=0, padx=5, pady=5)
        shot2_var = tk.IntVar(value=min(2, len(self.available_shots)))
        shot2_spin = tk.Spinbox(shot_frame, from_=1, to=len(self.available_shots), 
                               textvariable=shot2_var, width=10)
        shot2_spin.grid(row=1, column=1, padx=5, pady=5)
        
        def do_comparison():
            shot1 = shot1_var.get()
            shot2 = shot2_var.get()
            if shot1 == shot2:
                messagebox.showwarning("Warning", "Please select different shots")
                return
            self.compare_shots(shot1, shot2)
            comp_window.destroy()
        
        ttk.Button(comp_window, text="Compare", command=do_comparison).pack(pady=10)
    
    def compare_shots(self, shot1, shot2):
        """Compare two shots side by side"""
        comp_window = tk.Toplevel(self.root)
        comp_window.title(f"Shot Comparison: {shot1} vs {shot2}")
        comp_window.geometry("1200x600")
        
        # Create matplotlib figure with subplots
        fig = Figure(figsize=(12, 6), dpi=100)
        ax1 = fig.add_subplot(121)
        ax2 = fig.add_subplot(122)
        
        # Get scaling
        time_scale, time_label = self.get_time_scaling()
        voltage_scale, voltage_label = self.get_voltage_scaling()
        
        # Load and plot both shots
        colors = ['blue', 'red', 'green', 'orange']
        
        for shot_num, ax in [(shot1, ax1), (shot2, ax2)]:
            ax.set_title(f'Shot {shot_num}')
            ax.set_xlabel(f'Time ({time_label})')
            ax.set_ylabel(f'Voltage ({voltage_label})')
            
            for i, channel in enumerate(self.available_channels):
                try:
                    signal, time = read_rigol_hdf5_data_universal(
                        self.current_file, channel, shot_num)
                    
                    if signal is not None and time is not None:
                        time_plot = time * time_scale
                        voltage_plot = signal * voltage_scale
                        
                        color = colors[i % len(colors)]
                        ax.plot(time_plot, voltage_plot, color=color, label=channel)
                        
                except Exception as e:
                    print(f"Error plotting {channel} for shot {shot_num}: {e}")
            
            ax.grid(True, alpha=0.3)
            ax.legend()
            
            # Add trigger line
            if len(time) > 0:
                center_time = time[len(time) // 2] * time_scale
                ax.axvline(x=center_time, color='red', linestyle='--', alpha=0.7)
        
        # Create canvas
        canvas = FigureCanvasTkAgg(fig, master=comp_window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def export_data(self):
        """Export current shot data to CSV"""
        if not self.data_channels:
            messagebox.showwarning("Warning", "No data to export")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Export Data",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                # Prepare data for export
                export_data = []
                headers = []
                
                # Get time array from first channel
                first_channel = next(iter(self.time_arrays.keys()))
                time_array = self.time_arrays[first_channel]
                export_data.append(time_array)
                headers.append("Time_s")
                
                for channel, data in self.data_channels.items():
                    if data is not None:
                        export_data.append(data)
                        headers.append(f"{channel}_V")
                
                # Save to CSV
                export_array = np.column_stack(export_data)
                header_line = ','.join(headers)
                
                if self.file_format == 'new_shot_based':
                    header_line = f"# Shot {self.current_shot}\n" + header_line
                
                np.savetxt(file_path, export_array, delimiter=',', 
                          header=header_line, comments='')
                
                messagebox.showinfo("Success", f"Data exported to {file_path}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export data:\n{str(e)}")

def main():
    """Main function to run the enhanced visualizer"""
    root = tk.Tk()
    app = RigolDataVisualizer(root)
    root.mainloop()

if __name__ == '__main__':
    main()