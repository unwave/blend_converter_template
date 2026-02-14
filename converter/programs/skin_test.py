import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if not ROOT in sys.path:
    sys.path.append(ROOT)


import configuration

from scripts import bake as scripts_bake


def get_skin_test(
            blender_executable: str,
            blend_path,
            result_root = configuration.Folder.INTERMEDIATE_BLEND_SKIN_TEST,
        ):
    """ For iterative testing of skinning and weight panting quality, same as the baking but simplified and faster by disregarding materials """

    from blend_converter.blender.executor import Blender
    from blend_converter.blender import bc_script
    from blend_converter.blender.formats.blend import open_mainfile, save_as_mainfile
    from blend_converter import common
    from blend_converter import utils

    blend_path = common.File(blend_path)

    asset_folder = os.path.join(result_root, blend_path.dir_name)

    result_path = os.path.join(asset_folder, blend_path.dir_name + '.blend')

    blender = Blender(blender_executable)

    program = common.Program(
        blend_path = blend_path,
        result_path = result_path,
        blender_executable = blender_executable,
    )

    program._prog_type = 'SKIN TEST 🧐'

    program.run(blender, open_mainfile, blend_path)

    objects = program.run(blender, scripts_bake.get_target_objects)

    program.run(blender, scripts_bake.reset_timeline)
    program.run(blender, scripts_bake.apply_modifiers, objects, '.*', ignore_type = ['ARMATURE'])
    program.run(blender, bc_script.apply_scale, objects)
    program.run(blender, scripts_bake.join_objects)

    program.run(blender, save_as_mainfile, result_path)

    return program


def get_skin_test_kwargs(
            blender_executable: str,
            root = configuration.Folder.BLEND_SKELETAL,
        ):

    from blend_converter import utils

    arguments = []

    asset_folders = configuration.get_folders(root)

    for folder in asset_folders:

        if folder.name.startswith('_'):  # temp or WIP assets to ignore
            continue

        last_blend = utils.get_last_blend(folder)
        if not last_blend:
            continue

        arguments.append(dict(
            blender_executable = blender_executable,
            blend_path = last_blend,
        ))

    return arguments
