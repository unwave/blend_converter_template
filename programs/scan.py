import os

from .. import configuration

from ..scripts import scan as scripts_scan


def get_program(blender_executable: str, blend_path, result_dir):

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

    program.label = 'SCAN 🗿'

    program.run(blender, bpy_data.open_mainfile, blend_path)

    program.run(blender, scripts_scan.convert_to_mesh)

    objects = program.run(blender, scripts_scan.make_low_poly_and_cage, scripts_scan.S_Low_Poly())

    program.run(blender, scripts_scan.the_bake, objects, result_dir)

    program.run(blender, scripts_scan.delete_non_low_poly, objects)

    program.run(blender, bpy_data.save_as_mainfile, result_path)

    return program


def get_arguments(
        blender_executable: str,
        source_root: str,
        result_root: str,
    ):


    arguments = []

    for folder in configuration.get_folders(source_root):

        blend_path = configuration.get_blend(folder)
        if not blend_path:
            continue

        arguments.append(dict(
            blender_executable = blender_executable,
            blend_path = blend_path,
            result_dir = os.path.join(result_root, folder.name),
        ))


    return arguments
