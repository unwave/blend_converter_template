import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if not ROOT in sys.path:
    sys.path.append(ROOT)


import configuration

from scripts import bake as scripts_bake


def get_skin_test(blend_path):
    """ For iterative testing of skinning and weight panting quality, same as the baking but simplified and faster by disregarding materials """

    from blend_converter.blender import Blender, bc_script
    from blend_converter.blender.formats.blend import open_mainfile, save_as_mainfile
    from blend_converter import common
    from blend_converter import utils

    blend_path = common.File(blend_path)

    asset_folder = os.path.join(configuration.Folder.INTERMEDIATE_BLEND_SKIN_TEST, blend_path.dir_name)

    result_path = os.path.join(asset_folder, blend_path.dir_name + '.blend')

    blender = Blender(configuration.BLENDER_EXECUTABLE)

    program = common.Program(
        blend_path = blend_path,
        result_path = result_path,
        blender_executable = blender.binary_path,
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


def get_programs():

    from blend_converter import utils
    programs = utils.Appendable_Dict()

    asset_folders = [file for file in os.scandir(configuration.Folder.BLEND_SKELETAL) if file.is_dir()]

    for folder in asset_folders:

        if folder.name.startswith('_'):  # temp or WIP assets to ignore
            continue

        last_blend = utils.get_last_blend(folder)
        if not last_blend:
            continue

        programs.append(get_skin_test(last_blend))

    return programs
