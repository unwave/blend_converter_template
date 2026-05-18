import os

from .. import configuration

from ..scripts import export as scripts_export
from ..scripts import rig as scripts_rig


def get_program(
            blender_executable: str,
            blend_path,
            result_root: str,
        ):
    """ a proxy to use in external tools like Mixamo and further re-integration, prioritizing a base clean topology """

    from blend_converter.blender.executor import Blender
    from blend_converter.blender import bpy_data
    from blend_converter.blender import bpy_export
    from blend_converter import common
    from blend_converter import utils

    blend_path = common.File(blend_path)

    asset_folder = os.path.join(result_root, blend_path.dir_name)

    result_path = os.path.join(asset_folder, blend_path.dir_name + '.fbx')

    blender = Blender(blender_executable)

    program = common.Program(
        blend_path = blend_path,
        result_path = result_path,
        blender_executable = blender_executable,
        settings_path = os.path.join(blend_path.dir, 'bc_instructions.ini'),
    )

    program.label = 'SKIN PROXY 🤸'

    program.run(blender, bpy_data.open_mainfile, blend_path)

    program.run(blender, scripts_rig.convert_rig_proxy)
    program.run(blender, scripts_export.scene_clean_up)

    program.run(blender, bpy_export.export_fbx, result_path, bpy_export.S_Fbx(bake_anim = False, object_types = {'MESH'}, use_mesh_modifiers = False, use_selection = True))

    return program


def get_arguments(
            blender_executable: str,
            source_root: str,
            result_root: str,
        ):

    from blend_converter import utils

    arguments = []

    asset_folders = configuration.get_folders(source_root)

    for folder in asset_folders:

        if folder.name.startswith('_'):  # temp or WIP assets to ignore
            continue

        last_blend = utils.get_last_blend(folder)
        if not last_blend:
            continue

        arguments.append(dict(
            blender_executable = blender_executable,
            blend_path = last_blend,
            result_root = result_root,
        ))

    return arguments
