import os

from .. import configuration

from ..scripts import bake as scripts_bake


def get_program(
        *,
        blender_executable: str,
        blend_path: str,
        result_root: str,
    ):

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

    program._prog_type = 'TEST DEFORM RIG ☠️'

    program.run(blender, bpy_data.open_mainfile, blend_path)

    program.run(blender, scripts_bake.set_legacy_ik_solver)
    program.run(blender, scripts_bake.delete_undefined_nodes)

    program.run(blender, scripts_bake.reveal_collections)

    program.run(blender, scripts_bake.unassign_deform_bones_with_missing_weights)
    program.run(blender, scripts_bake.create_game_rig_and_bake_actions, False)

    program.run(blender, bpy_data.save_as_mainfile, result_path)

    return program


def get_arguments(
            blender_executable: str,
            root: str,
            result_root: str,
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
            result_root = result_root,
        ))

    return arguments
