import bapsf_motion as bmotion
import h5py
import time
import traceback
import warnings
import xarray as xr

from multi_scope_acquisition import (
    load_experiment_config,
    MultiScopeAcquisition,
    single_shot_acquisition,
)


def configure_bmotion_hdf5_group(hdf5_path: str, total_shots: int):
    with h5py.File(hdf5_path, 'a') as f:
        ctl_grp = f.require_group('Control')
        pos_grp = ctl_grp.require_group('Positions')

        # # Save motion_list from bmotion
        # ds = pos_grp.create_dataset('motion_list', data=motion_list.values)
        #
        # # print("adding coords to attributes")
        # for coord in motion_list.coords:
        #     ds.attrs[coord] = np.array(motion_list.coords[coord])
        #
        # # print("adding ml atts to attr")
        # for key, val in motion_list.attrs.items():
        #     ds.attrs[key] = val

        # Create structured array to save actual achieved positions
        # (like position_manager)
        pos_grp.create_dataset(
            'positions_array',
            shape=(total_shots,),
            dtype=[('shot_num', '>u4'), ('x', '>f4'), ('y', '>f4')],
        )


def run_acquisition_bmotion(hdf5_path, toml_path, config_path):
    print('Starting acquisition at', time.ctime())

    config = load_experiment_config(config_path)
    nshots = config.getint('nshots', 'num_duplicate_shots', fallback=1)

    # =======================================================================
    print("Loading TOML configuration...", end='')
    run_manager = bmotion.actors.RunManager(toml_path, auto_run=True)
    print("✓")

    # Print and select from all available motion lists
    print(f"\nAvailable motion groups ({len(run_manager.mgs)}):")
    if not run_manager.mgs:
        raise RuntimeError("No motion groups found in TOML configuration")

    motion_groups = run_manager.mgs
    for mg_key, mg in motion_groups.items():
        motion_list_size = 0 if mg.mb.motion_list is None else mg.mb.motion_list.shape[0]
        print(f"  {mg_key}: {mg.config['name']} -- {motion_list_size} positions")

    # Prompt user to select a motion list
    while True:
        try:
            selection = int(input(f"Select motion group [first column value]: "))
            if 0 <= selection <= len(motion_groups):
                break
            else:
                print(f"Please enter a number between 1 and {len(motion_groups)}.")
        except KeyboardInterrupt as err:
            print('\n______Halted due to Ctrl-C______', '  at', time.ctime())
            run_manager.terminate()
            raise KeyboardInterrupt from err
        except ValueError as err:
            run_manager.terminate()
            raise ValueError("Invalid selection") from err

    selected_key = selection
    if selected_key not in motion_groups:
        selected_key = f"{selected_key}"
        if selected_key not in motion_groups:
            raise RuntimeError(
                f"The specified motion group key '{selected_key}' does not exist.  "
                f"Available motion group keys:  {motion_groups.keys()}"
            )

    selected_mg = motion_groups[selected_key]
    motion_list = selected_mg.mb.motion_list
    if motion_list is None:
        raise RuntimeError(f"Selected motion group '{selected_key}' has no motion list")
    if not isinstance(motion_list, xr.DataArray):
        raise RuntimeError(
            f"Selected motion group '{selected_key}' has invalid motion list type")
    elif motion_list.size == 0:
        raise RuntimeError(
            f"Selected motion group '{selected_key}' has an empty motion list")

    motion_list_size = motion_list.shape[
        0]  # shape is (N, 2) for a 2D probe drive, N == number of positions

    print(f"Using motion group '{selected_key}' with {motion_list_size} positions")
    print(f"Number of shots per position: {nshots}")
    total_shots = motion_list_size * nshots
    print(f"Total shots: {total_shots}")
    # =======================================================================

    with MultiScopeAcquisition(hdf5_path,
                               config) as msa:  # Initialize multi-scope acquisition
        try:
            print("Initializing HDF5 file...", end='')
            msa.initialize_hdf5_base()
            print("✓")

            print("\nStarting initial acquisition...")
            active_scopes = msa.initialize_scopes()
            if not active_scopes:
                raise RuntimeError(
                    "No valid data found from any scope. Aborting acquisition.")


            # create position group in hdf5
            configure_bmotion_hdf5_group(hdf5_path, total_shots)

            # Main acquisition loop
            shot_num = 1  # 1-based shot numbering
            for motion_index in range(motion_list_size):
                try:
                    print(
                        f"\nMoving to position {motion_index + 1}/{motion_list_size}...")
                    try:
                        selected_mg.move_ml(motion_index)
                    except ValueError as err:
                        warnings.warn(
                            f"Motion list index {motion_index} is out of range. "
                            f"NO MOTION DONE.\n [{err}]."
                        )

                    # wait for motion to stop
                    time.sleep(.5)
                    while selected_mg.is_moving:
                        time.sleep(.5)

                    # Get current position after movement
                    current_position = selected_mg.position
                    position_values = current_position.value  # Get numerical values
                except KeyboardInterrupt:
                    run_manager.terminate()
                    print('\n______Halted due to Ctrl-C______', '  at', time.ctime())
                    raise
                except Exception as e:
                    run_manager.terminate()  # TODO: not sure this is the right place to terminate
                    print(
                        f"Error occurred while moving to position {motion_index + 1}: {str(e)}")
                    traceback.print_exc()
                    raise RuntimeError from e

                print(f"Current position: {current_position}")

                for n in range(nshots):
                    acquisition_loop_start_time = time.time()
                    try:
                        single_shot_acquisition(msa, active_scopes, shot_num)

                        with h5py.File(hdf5_path,
                                       'a') as f:  # Update positions_array with actual achieved position
                            pos_arr = f['Control/Positions/positions_array']
                            pos_arr[shot_num - 1] = (shot_num, position_values[0],
                                                     position_values[1])

                    except KeyboardInterrupt:
                        raise KeyboardInterrupt
                    except (ValueError, RuntimeError) as e:
                        print(f'\nSkipping shot {shot_num} - {str(e)}')

                        with h5py.File(hdf5_path,
                                       'a') as f:  # Create empty shot group with explanation
                            for scope_name in msa.scope_ips:
                                scope_group = f[scope_name]
                                shot_group = scope_group.create_group(f'shot_{shot_num}')
                                shot_group.attrs['skipped'] = True
                                shot_group.attrs['skip_reason'] = str(e)
                                shot_group.attrs['acquisition_time'] = time.ctime()

                            # Still update positions_array for skipped shots
                            pos_array = f['Control/Positions/positions_array']
                            pos_array[shot_num - 1] = (shot_num, position_values[0],
                                                       position_values[1])

                    except Exception as e:
                        print(f'\nMotion failed for shot {shot_num} - {str(e)}')

                        with h5py.File(hdf5_path,
                                       'a') as f:  # Create empty shot group with explanation
                            for scope_name in msa.scope_ips:
                                scope_group = f[scope_name]
                                shot_group = scope_group.create_group(f'shot_{shot_num}')
                                shot_group.attrs['skipped'] = True
                                shot_group.attrs[
                                    'skip_reason'] = f"Motion failed: {str(e)}"
                                shot_group.attrs['acquisition_time'] = time.ctime()

                            # Still update positions_array for failed shots
                            pos_array = f['Control/Positions/positions_array']
                            pos_array[shot_num - 1] = (shot_num, position_values[0],
                                                       position_values[1])

                    # Calculate and display remaining time
                    if shot_num > 1:
                        time_per_shot = (time.time() - acquisition_loop_start_time)
                        remaining_shots = total_shots - shot_num
                        remaining_time = remaining_shots * time_per_shot
                        print(
                            f' | Remaining: {remaining_time / 3600:.2f}h ({remaining_shots} shots)')
                    else:
                        print()

                    shot_num += 1  # Always increment shot number

        except KeyboardInterrupt:
            print('\n______Halted due to Ctrl-C______', '  at', time.ctime())
            raise
        finally:
            run_manager.terminate()
