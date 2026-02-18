import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if not ROOT in sys.path:
    sys.path.append(ROOT)


import configuration

from scripts import scan as scripts_scan


def get_scan_program(blender_executable: str, blend_path, result_dir):

    from blend_converter.blender.formats.blend import open_mainfile, save_as_mainfile
    from blend_converter.blender.executor import Blender
    from blend_converter import common

    import os

    blend_path = common.File(blend_path)

    result_path = os.path.join(result_dir, blend_path.dir_name + '.blend')

    blender = Blender(blender_executable)

    program = common.Program(
        blend_path = blend_path,
        result_path = result_path,
        blender_executable = blender_executable
    )

    program._prog_type = 'HIGH POLY ✂️'

    program.run(blender, open_mainfile, blend_path)

    objects = program.run(blender, scripts_scan.make_low_poly_and_cage)

    program.run(blender, scripts_scan.the_bake, objects, result_dir)

    program.run(blender, scripts_scan.delete_non_low_poly, objects)

    program.run(blender, save_as_mainfile, result_path)

    return program


def get_prebake_kwargs(
        blender_executable: str,
        root = configuration.Folder.HIGH_POLY,
        result_root = configuration.Folder.LOW_POLY,
    ):

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
