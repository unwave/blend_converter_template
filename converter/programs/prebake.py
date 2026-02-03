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

    program.run(blender, open_mainfile, blend_path)

    program.run(blender, scripts_scan.make_low_poly_and_cage)

    program.run(blender, scripts_scan.the_bake, result_dir)

    program.run(blender, save_as_mainfile, result_path)

    return program


def get_prebake_kwargs(blender_executable: str):

    from blend_converter import utils

    arguments = []

    asset_folders = [file for file in os.scandir(configuration.Folder.BLEND_MAIN) if file.is_dir()]

    for folder in asset_folders:

        if folder.name.startswith('_'):  # temp or WIP assets to ignore
            continue

        high_poly_folder = os.path.join(folder, 'high_poly')
        low_poly_folder = os.path.join(folder, 'low_poly')

        if not os.path.exists(high_poly_folder):
            continue

        for file in os.scandir(high_poly_folder):

            if not file.is_dir():
                continue

            last_blend = utils.get_last_blend(file.path)
            if not last_blend:
                continue

            result_dir = os.path.join(low_poly_folder, file.name)

            arguments.append(dict(
                blender_executable = blender_executable,
                blend_path = last_blend,
                result_dir = result_dir,
            ))


    return arguments
