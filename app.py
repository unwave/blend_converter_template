""" The asset conversion app. """

import sys
import os
import time
import typing
import json


from blend_converter import common


ROOT = os.path.join(os.path.dirname(__file__))

IS_USING_TERMINAL = not {'PROMPT', 'TERM_PROGRAM', 'TERM', 'TERMINAL_EMULATOR'}.isdisjoint(os.environ)


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


def launch_converter(program_collections: typing.List[common.Program_Collection]):

    from blend_converter.gui import updater_ui
    from blend_converter import updater
    updater.UPDATE_DELAY = 0

    print('conversion app start:', time.strftime('%Y.%m.%d %H:%M:%S'))
    columns = [
        ('func', 170, get_func_name),
    ]
    app = updater_ui.Main_Frame.get_app(program_collections, columns)

    import psutil
    physical_core_count = psutil.cpu_count(logical=False)

    app.main_frame.updater.total_max_parallel_executions = physical_core_count
    app.main_frame.updater.default_max_parallel_executions = physical_core_count
    app.main_frame.updater.set_max_parallel_executions_per_program_tag('gltf', physical_core_count)
    app.main_frame.updater.set_max_parallel_executions_per_program_tag('unreal', 1)

    if not IS_USING_TERMINAL:
        sys.excepthook = sys.__excepthook__

    app.MainLoop()


def get_program_paths():

    from .programs import bake
    from .programs import godot_static
    from .programs import godot_skeletal
    from .programs import godot_animation
    from .programs import unreal_static
    from .programs import unreal_skeletal
    from .programs import unreal_animation
    from .programs import skin_test
    from .programs import skin_proxy
    from .programs import test_deform_rig
    from .programs import scan
    from .programs import rig
    from .programs import panda3d_static
    from .programs import panda3d_skeletal
    from .programs import fbx_static
    from .programs import fbx_skeletal
    from .programs import fbx_animation

    return dict(
        static = [bake.get_program, bake.get_static_arguments],
        skeletal = [bake.get_program, bake.get_skeletal_arguments],
        godot_static = [godot_static.get_program, godot_static.get_arguments],
        godot_skeletal = [godot_skeletal.get_program, godot_skeletal.get_arguments],
        godot_animation = [godot_animation.get_program, godot_animation.get_arguments],
        ue_static = [unreal_static.get_program, unreal_static.get_arguments],
        ue_skeletal = [unreal_skeletal.get_program, unreal_skeletal.get_arguments],
        ue_animation = [unreal_animation.get_program, unreal_animation.get_arguments],
        skin_test = [skin_test.get_program, skin_test.get_arguments],
        skin_proxy = [skin_proxy.get_program, skin_proxy.get_arguments],
        test_deform_rig = [test_deform_rig.get_program, test_deform_rig.get_arguments],
        scan = [scan.get_program, scan.get_arguments],
        rig = [rig.get_program, rig.get_arguments],
        panda3d_static = [panda3d_static.get_program, panda3d_static.get_arguments],
        panda3d_skeletal = [panda3d_skeletal.get_program, panda3d_skeletal.get_arguments],
        fbx_static = [fbx_static.get_program, fbx_static.get_arguments],
        fbx_skeletal = [fbx_skeletal.get_program, fbx_skeletal.get_arguments],
        fbx_animation = [fbx_animation.get_program, fbx_animation.get_arguments],
    )


def load_program_collections():

    try:
        raw_argument = sys.argv[1]
    except IndexError:
        return None

    try:
        argument = json.loads(raw_argument)
    except json.decoder.JSONDecodeError as e:
        print(raw_argument)
        print(e)
        return None

    try:
        return [common.Program_Collection.from_dict(**x) for x in argument]
    except Exception as e:
        print(argument)
        print(e)
        return None


def main():

    print(sys.argv)
    print()

    program_collection = load_program_collections()

    if program_collection:

        if not IS_USING_TERMINAL:
            sys.excepthook = except_hook

        launch_converter(program_collection)

    else:
        from . import app_launcher
        app_launcher.start_launcher(get_program_paths())
