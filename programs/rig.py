import os


from .. import configuration

from ..scripts import export as scripts_export
from ..scripts import bake as scripts_bake


def get_program(
            blender_executable: str,
            blend_path,
            result_root: str,
        ):
    """ for use a linked rig + mesh for creating animations """

    from blend_converter.blender.executor import Blender
    from blend_converter.blender import bpy_utils
    from blend_converter.blender import bpy_data
    from blend_converter import common

    blend_path = common.File(blend_path)

    asset_folder = os.path.join(result_root, blend_path.dir_name)

    result_path = os.path.join(asset_folder, blend_path.dir_name + '.blend')

    blender = Blender(blender_executable)

    program = common.Program(
        blend_path = blend_path,
        result_path = result_path,
        blender_executable = blender_executable,
        settings_path = os.path.join(blend_path.dir, 'bc_instructions.ini'),
    )

    program._prog_type = 'RIG 🦴'

    program.run(blender, bpy_data.open_mainfile, blend_path)

    program.run(blender, scripts_export.remove_unused_uv_layouts)
    program.run(blender, bpy_utils.remove_all_node_groups_from_materials)
    program.run(blender, bpy_utils.use_backface_culling)

    program.run(blender, scripts_export.save_blend_with_repack, result_path)

    return program


def get_arguments(
            blender_executable: str,
            source_root: str,
            result_root: str,
        ):

    from blend_converter import utils

    arguments = []

    for folder in configuration.get_folders(source_root):

        last_blend = utils.get_last_blend(folder)
        if not last_blend:
            continue

        arguments.append(dict(
            blender_executable = blender_executable,
            blend_path = last_blend,
            result_root = result_root,
        ))


    return arguments
