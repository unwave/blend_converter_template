""" The asset conversion app. """

import sys
import os
import time
import typing
import json


from blend_converter import common


if typing.TYPE_CHECKING:
    from blend_converter import updater


def except_hook(exc_type, exc_value, exc_traceback):
    import traceback
    traceback.print_exception(exc_type, exc_value, exc_traceback)
    sys.excepthook = sys.__excepthook__

    print()
    input('Press Enter to exit.')


def get_func_name(entry: 'updater.Program_Entry'):
    return getattr(entry.program, '_prog_type', 'NONE')


def main(definitions: typing.List[common.Program_Definition]):

    is_using_terminal = not {'PROMPT', 'TERM_PROGRAM', 'TERM', 'TERMINAL_EMULATOR'}.isdisjoint(os.environ)

    if not is_using_terminal:
        sys.excepthook = except_hook

    from blend_converter.gui import updater_ui
    from blend_converter import updater
    updater.UPDATE_DELAY = 0

    print('conversion app start:', time.strftime('%Y.%m.%d %H:%M:%S'))
    columns = [
        ('func', 170, get_func_name),
    ]
    app = updater_ui.Main_Frame.get_app(definitions, columns)

    import psutil
    physical_core_count = psutil.cpu_count(logical=False)

    app.main_frame.updater.total_max_parallel_executions = physical_core_count
    app.main_frame.updater.default_max_parallel_executions = physical_core_count
    app.main_frame.updater.set_max_parallel_executions_per_program_tag('gltf', physical_core_count)
    app.main_frame.updater.set_max_parallel_executions_per_program_tag('unreal', 1)

    if not is_using_terminal:
        sys.excepthook = sys.__excepthook__

    app.MainLoop()

def get_program_paths():
    ROOT = os.path.join(os.path.dirname(__file__))

    return dict(
        static = (os.path.join(ROOT, 'programs', 'bake.py'), 'get_bake_program', 'get_static_kwargs'),
        skeletal = (os.path.join(ROOT, 'programs', 'bake.py'), 'get_bake_program', 'get_skeletal_kwargs'),
        godot = (os.path.join(ROOT, 'programs', 'godot.py'), 'convert_to_static_mesh', 'get_godot_kwargs'),
        ue_static = (os.path.join(ROOT, 'programs', 'unreal_engine.py'), 'convert_to_unreal_static_mesh', 'get_static_unreal_kwargs'),
        ue_skeletal = (os.path.join(ROOT, 'programs', 'unreal_engine.py'), 'convert_to_unreal_skeletal_mesh', 'get_skeletal_unreal_kwargs'),
        ue_animation = (os.path.join(ROOT, 'programs', 'unreal_engine.py'), 'convert_to_unreal_animation', 'get_unreal_animation_kwargs'),
        skin_test = (os.path.join(ROOT, 'programs', 'skin_test.py'), 'get_skin_test', 'get_skin_test_kwargs'),
        skin_proxy = (os.path.join(ROOT, 'programs', 'skin_proxy.py'), 'get_skin_proxy', 'get_skin_proxy_kwargs'),
        scan = (os.path.join(ROOT, 'programs', 'scan.py'), 'get_scan_program', 'get_scan_kwargs'),
        rig = (os.path.join(ROOT, 'programs', 'rig.py'), 'get_rig', 'get_rig_kwargs'),
        panda3d = (os.path.join(ROOT, 'programs', 'panda3d_engine.py'), 'convert_to_static_mesh', 'get_panda3d_kwargs'),
    )


if __name__ == '__main__':

    programs = get_program_paths()

    print(sys.argv)
    print()


    try:
        argument = sys.argv[1]
    except IndexError:
        argument = None

    import app_launcher

    launch_options = None

    if argument:
        try:
            launch_options = app_launcher.Launch_Options._from_json(argument)
        except json.decoder.JSONDecodeError:
            pass


    if not launch_options:
        launch_options = app_launcher.get_user_choice(list(programs))
        sys.argv.append(launch_options._to_json())


    if not launch_options.blender_executable or not os.path.exists(launch_options.blender_executable):
        raise Exception(f"The Blender executable path does not exists: {repr(launch_options.blender_executable)}")


    if not launch_options.main_root or not os.path.exists(launch_options.main_root):
        raise Exception(f"The root path does not exists: {repr(launch_options.main_root)}")


    main([
        common.Program_Definition(*programs[n], kwargs=dict(
            blender_executable = launch_options.blender_executable,
            main_root = launch_options.main_root,
        ))
        for n in launch_options.program_names
    ])
