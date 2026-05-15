import os

from .. import configuration

from ..scripts import bake as scripts_bake
from ..scripts import export as scripts_export
from ..scripts import unreal_engine as scripts_unreal



def get_program(
            blender_executable: str,
            blend_path,
            rig_name: str,
            animation_name: str,
            fbx_root: str,
            root_destination_folder: str,
            skeletal_root_destination_folder: str,
        ):
    """ export as an animation only fbx file """

    from blend_converter.unreal import Unreal
    from blend_converter.blender.executor import Blender
    from blend_converter.blender import bpy_data
    from blend_converter.blender import bpy_export
    from blend_converter import common

    blend_path = common.File(blend_path)

    rig_name = configuration.get_ascii_underscored(rig_name)
    animation_name = configuration.get_ascii_underscored(animation_name)

    fbx_path = os.path.join(fbx_root, rig_name, animation_name + '.fbx')

    unreal = Unreal()
    blender = Blender(blender_executable)

    program = common.Program(
        blend_path = blend_path,
        result_path = fbx_path,
        blender_executable = blender.binary_path,
        settings_path = os.path.join(blend_path.dir, 'bc_instructions.ini'),
    )

    program.tags.add('unreal')

    program._prog_type = 'UNREAL ANIMATION 👾'

    program.run(blender, scripts_export.check_if_writable, fbx_path)

    program.run(blender, bpy_data.open_mainfile, blend_path)

    program.run(blender, scripts_export.make_local)
    program.run(blender, scripts_bake.create_game_rig_and_bake_actions, scripts_bake.S_Deform_Armature())
    program.run(blender, scripts_unreal.ensure_single_root_bone)
    program.run(blender, scripts_export.delete_non_armature_objects)
    program.run(blender, scripts_export.rename_all_armatures)

    program.run(blender, scripts_unreal.rename_objects_for_unreal, 'SK')

    program.run(blender, scripts_unreal.scale_armature)


    program.run(blender, bpy_export.export_fbx, fbx_path, bpy_export.S_Fbx(
        add_leaf_bones = False,
        # bake_anim_force_startend_keying=True,
        # bake_anim_use_all_bones=False,
        # bake_anim_use_nla_strips=False,
        # bake_anim_use_all_actions=False,
    ))


    ue_fbx_settings = scripts_unreal.S_Unreal_Fbx(
        fbx_path = fbx_path,
        destination_folder =  scripts_unreal.join_path(root_destination_folder, rig_name),
        destination_name = f'A_{rig_name}_{animation_name}',
        skeleton_asset_path = scripts_unreal.join_path(skeletal_root_destination_folder, rig_name, f'{rig_name}_Skeleton'),
        frame_rate = program.run(blender, scripts_unreal.get_frame_rate)
    )

    program.run(unreal, scripts_unreal.import_anim_sequence, ue_fbx_settings)

    return program


def get_arguments(
            blender_executable: str,
            source_root: str,
            fbx_root: str,
            root_destination_folder: str = configuration.Folder.UNREAL_ANIMATION,
            skeletal_root_destination_folder: str = configuration.Folder.UNREAL_SKELETAL,
        ):


    from blend_converter import utils

    arguments = []

    for rig_folder in configuration.get_folders(source_root):

        rig_name = os.path.basename(rig_folder)

        for anim_folder in configuration.get_folders(rig_folder):

            animation_name = os.path.basename(anim_folder)

            last_blend = utils.get_last_blend(anim_folder)
            if not last_blend:
                continue

            arguments.append(dict(
                blender_executable = blender_executable,
                blend_path = last_blend,
                rig_name = rig_name,
                animation_name = animation_name,
                fbx_root = fbx_root,
                root_destination_folder = root_destination_folder,
                skeletal_root_destination_folder = skeletal_root_destination_folder,
            ))


    return arguments
