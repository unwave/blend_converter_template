import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if not ROOT in sys.path:
    sys.path.append(ROOT)


import configuration

from scripts import scan as scripts_scan


def get_scan_program(blender_executable: str, blend_path, result_dir):

    from blend_converter.blender import bpy_data
    from blend_converter.blender.executor import Blender
    from blend_converter import common

    import os

    blend_path = common.File(blend_path)

    result_path = os.path.join(result_dir, blend_path.dir_name + '.blend')

    blender = Blender(blender_executable)

    program = common.Program(
        blend_path = blend_path,
        result_path = result_path,
        blender_executable = blender_executable,
        settings_path = os.path.join(blend_path.dir, 'bc_instructions.ini'),
    )

    program._prog_type = 'SCAN 🗿'

    program.run(blender, bpy_data.open_mainfile, blend_path)

    program.run(blender, scripts_scan.convert_to_mesh)

    objects = program.run(blender, scripts_scan.make_low_poly_and_cage)

    program.run(blender, scripts_scan.the_bake, objects, result_dir)

    program.run(blender, scripts_scan.delete_non_low_poly, objects)

    program.run(blender, bpy_data.save_as_mainfile, result_path)

    return program


def get_scan_kwargs(
        blender_executable: str,
        main_root: str,
        root = configuration.Folder.SCAN,
        result_root = configuration.Folder.INTERMEDIATE_SCAN,
    ):

    root = os.path.join(main_root, *root)
    result_root = os.path.join(main_root, *result_root)

    from blend_converter import utils

    arguments = []

    asset_folders = configuration.get_folders(root)

    for folder in asset_folders:

        last_blend = utils.get_last_blend(folder)
        if not last_blend:
            continue

        arguments.append(dict(
            blender_executable = blender_executable,
            blend_path = last_blend,
            result_dir = os.path.join(result_root, folder.name),
        ))


    return arguments
