import os

from .. import configuration

from ..scripts import bake as scripts_bake
from ..programs.bake import get_program as get_bake_program


def get_program(*args, create_game_rig = False, **kwargs):

    program = get_bake_program(*args, **kwargs)

    blender = program.instructions[-1].executor

    program.run(blender, scripts_bake.unassign_deform_bones_with_missing_weights, instruction_insert_index = -1, is_instruction_enabled = create_game_rig)
    program.run(blender, scripts_bake.create_game_rig_and_bake_actions, scripts_bake.S_Deform_Armature(), False, instruction_insert_index = -1, is_instruction_enabled = create_game_rig)

    return program


def get_arguments(
            blender_executable: str,
            source_root: str,
            result_root: str,
            create_game_rig: bool,
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
            textures_folder = None,
            is_skeletal = True,
            skip_bake = True,
            create_game_rig = create_game_rig,
        ))

    return arguments
