import bapsf_motion as bmotion
import h5py
import numpy as np
import time
import traceback
import warnings
import xarray as xr

from typing import Dict

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
            dtype=[
                ('shot_num', '>u4'),
                ('motion_group', np.bytes_, 120),
                ('x', '>f4'),
                ('y', '>f4'),
            ],
        )


def select_motion_groups(rm: bmotion.actors.RunManager):
    # Print and select from all available motion lists
    if not rm.mgs:
        raise RuntimeError("No motion groups found in TOML configuration")

    print(f"\nAvailable motion groups ({len(rm.mgs)}):")
    print(f"  Key : {'Name':<25} -- {'Size':<16}")
    for mg_key, mg in rm.mgs.items():
        motion_list_size = 0 if mg.mb.motion_list is None else mg.mb.motion_list.shape[0]
        print(
            f"{mg_key:>5} : {mg.config['name']:.25} -- {motion_list_size:6d} positions"
        )

    # Prompt user to select a motion list
    while True:
        selection = input(
            f"Select motion group(s) [^Key Column]:\n"
            f"  A - for all\n"
            f"  Space Separated Keys for each motion group (e.g. '1 3 5')"
        )

        if selection.startswith("'") or selection.startswith('"'):
            selection = selection[1:]

        if selection.endswith("'") or selection.endswith('"'):
            selection = selection[:-1]

        if selection == "A":
            selection = set(rm.mgs.keys())
            break

        selection = set(selection.split(" "))
        initial_selection = selection
        selection = []
        for item in initial_selection:
            if item == "":
                continue

            if item in rm.mgs:
                selection.append(item)
                continue

            try:
                item = int(item)

                if item in rm.mgs:
                    selection.append(item)
                else:
                    raise ValueError
            except ValueError:
                selection = None
                break

        if selection is None or len(selection) == 0:
            print(
                f"Motion Group selection was invalid '{initial_selection}'.  "
                f"SELECT AGAIN"
            )
            continue

    return selection


def select_motion_list_order(rm: bmotion.actors.RunManager, order: Dict[str, str]):
    for mg_key in order:
        mg = rm.mgs[mg_key]

        while True:
            direction = input(
                f"Motion list direction is forward for '{mg.config['name']}'.\n"
                f"Press Enter to continue, or R + Enter to reverse."
            )

            if direction == "":
                break
            elif direction == "R":
                order[mg_key] = "backward"
                print("Motion list direction is reversed.\n")
                break
            else:
                print(
                    f"Motion list direction selection was invalid '{direction}'.  "
                    f"TRY AGAIN..."
                )
                continue

    return order


def get_max_motion_list_size(rm: bmotion.actors.RunManager, mg_keys) -> int:

    sizes = []
    for key in mg_keys:
        mg = rm.mgs[key]

        if not isinstance(mg.mb.motion_list, xr.DataArray):
            raise RuntimeError(
                f"Selected motion group '{mg.config['name']}' motion "
                f"list is invalid."
            )

        if mg.mb.motion_list.size == 0:
            raise RuntimeError(
                f"Selected motion group '{mg.config['name']}' has an "
                f"empty motion list"
            )

        sizes.append(mg.mb.motion_list.shape[0])

    return int(np.max(sizes))


def move_to_index(
    index: int,
    rm: bmotion.actors.RunManager,
    ml_order_dict: Dict[str, str],
) -> None:

    for mg_key, order in ml_order_dict.items():
        mg = rm.mgs[mg_key]
        ml_size = int(mg.mb.motion_list.shape[0])

        if order == "backward":
            index = ml_size - index

        if index not in range(ml_size):
            warnings.warn(
                f"Motion list index {index} is out of range for motion "
                f"group '{mg.config['name']}'.  NO MOTION DONE."
            )
            continue

        mg.move_to(index)

    # wait for motion to stop
    time.sleep(.5)
    while rm.is_moving:
        time.sleep(.5)


def run_acquisition_bmotion(hdf5_path, toml_path, config_path):
    print('Starting acquisition at', time.ctime())

    config = load_experiment_config(config_path)
    nshots = config.getint('nshots', 'num_duplicate_shots', fallback=1)

    # =======================================================================
    print("Loading TOML configuration...", end='')
    run_manager = bmotion.actors.RunManager(toml_path, auto_run=True)
    print("✓")

    try:
        selection = select_motion_groups(run_manager)

        ml_order = dict(zip(selection, len(selection) * ["forward"]))
        ml_order = select_motion_list_order(run_manager, ml_order)
    except KeyboardInterrupt as err:
        print('\n______Halted due to Ctrl-C______', '  at', time.ctime())
        run_manager.terminate()
        raise KeyboardInterrupt from err

    max_ml_size = get_max_motion_list_size(run_manager, list(ml_order))

    print(f"Maximum motion list size is {max_ml_size}")
    print(f"Number of shots per position: {nshots}")
    total_shots = max_ml_size * nshots
    print(f"Total shots: {total_shots}")

    # Start acquisition loop
    with MultiScopeAcquisition(hdf5_path, config) as msa:
        try:
            print("Initializing HDF5 file...", end='')
            msa.initialize_hdf5_base()
            print("✓")

            print("\nStarting initial acquisition...")
            active_scopes = msa.initialize_scopes()
            if not active_scopes:
                raise RuntimeError(
                    "No valid data found from any scope. Aborting acquisition."
                )

            # create position group in hdf5
            configure_bmotion_hdf5_group(hdf5_path, total_shots)

            # Main acquisition loop
            shot_num = 1  # 1-based shot numbering
            for motion_index in range(max_ml_size):
                print(
                    f"\nMoving to position {motion_index + 1}/{max_ml_size}..."
                )

                move_to_index(
                    index=motion_index,
                    rm=run_manager,
                    ml_order_dict=ml_order,
                )

                # Get current position after movement
                current_position = selected_mg.position
                position_values = current_position.value  # Get numerical values

                print(f"Current position: {current_position}")

                for n in range(nshots):
                    acquisition_loop_start_time = time.time()
                    try:
                        single_shot_acquisition(msa, active_scopes, shot_num)

                        # Update positions_array with actual achieved position
                        with h5py.File(hdf5_path, 'a') as f:
                            pos_arr = f['Control/Positions/positions_array']
                            pos_arr[shot_num - 1] = (
                                shot_num, position_values[0], position_values[1]
                            )

                    except KeyboardInterrupt:
                        raise KeyboardInterrupt
                    except (ValueError, RuntimeError) as e:
                        print(f'\nSkipping shot {shot_num} - {str(e)}')

                        # Create empty shot group with explanation
                        with h5py.File(hdf5_path, 'a') as f:
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

                        # Create empty shot group with explanation
                        with h5py.File(hdf5_path, 'a') as f:
                            for scope_name in msa.scope_ips:
                                scope_group = f[scope_name]
                                shot_group = scope_group.create_group(f'shot_{shot_num}')
                                shot_group.attrs['skipped'] = True
                                shot_group.attrs[
                                    'skip_reason'] = f"Motion failed: {str(e)}"
                                shot_group.attrs['acquisition_time'] = time.ctime()

                            # Still update positions_array for failed shots
                            pos_array = f['Control/Positions/positions_array']
                            pos_array[shot_num - 1] = (
                                shot_num, position_values[0], position_values[1]
                            )

                    # Calculate and display remaining time
                    if shot_num > 1:
                        time_per_shot = (time.time() - acquisition_loop_start_time)
                        remaining_shots = total_shots - shot_num
                        remaining_time = remaining_shots * time_per_shot
                        print(
                            f' | Remaining: {remaining_time / 3600:.2f}h '
                            f'({remaining_shots} shots)'
                        )
                    else:
                        print()

                    shot_num += 1  # Always increment shot number

        except KeyboardInterrupt as err:
            print('\n______Halted due to Ctrl-C______', '  at', time.ctime())
            raise RuntimeError() from err
        finally:
            run_manager.terminate()
