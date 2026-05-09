import os

from .. import configuration

from ..scripts import bake as scripts_bake
from ..scripts import export as scripts_export
from ..scripts import unreal_engine as scripts_unreal


def get_program(
            blender_executable: str,
            blend_path: str,
            result_root: str,
        ):
    """ export as a fbx skeletal mesh """

    from blend_converter.blender.executor import Blender
    from blend_converter.blender import bpy_utils
    from blend_converter.blender import bpy_data
    from blend_converter.blender import bpy_export
    from blend_converter import common


    blend_path: common.File = common.File(blend_path)

    dir_name = configuration.get_ascii_underscored(blend_path.dir_name)

    fbx_path = os.path.join(result_root, dir_name, dir_name + '.fbx')

    blender = Blender(blender_executable)

    program = common.Program(
        blend_path = blend_path,
        result_path = fbx_path,
        blender_executable = blender.binary_path,
        settings_path = os.path.join(blend_path.dir, 'bc_instructions.ini'),
    )

    program.tags.add('fbx')

    program._prog_type = 'FBX SKELETAL'

    program.run(blender, scripts_export.check_if_writable, fbx_path)

    program.run(blender, bpy_data.open_mainfile, blend_path)

    program.run(blender, scripts_bake.reveal_collections)
    program.run(blender, scripts_export.scene_clean_up)
    program.run(blender, scripts_export.remove_unused_uv_layouts)
    program.run(blender, bpy_utils.remove_all_node_groups_from_materials)
    program.run(blender, scripts_export.remove_animations)
    program.run(blender, bpy_utils.use_backface_culling)
    program.run(blender, scripts_export.delete_unused_materials)
    program.run(blender, scripts_bake.create_game_rig_and_bake_actions, False)
    program.run(blender, scripts_unreal.ensure_single_root_bone)

    program.run(blender, scripts_unreal.rename_objects_for_unreal, 'SK')
    program.run(blender, scripts_export.rename_all_armatures)

    objects = program.run(blender, scripts_bake.get_target_objects)

    program.run(blender, scripts_unreal.join_all_mesh_objects, dir_name, objects)
    program.run(blender, scripts_export.triangulate_geometry, objects)

    program.run(blender, scripts_unreal.limit_total_bone_weights, 8)
    program.run(blender, scripts_unreal.ensure_bone_count_limit_per_material)

    program.run(blender, scripts_unreal.scale_armature, 1)

    program.run(blender, scripts_export.remove_other_object_types, ['MESH', 'ARMATURE'])

    program.run(blender, scripts_export.save_blend_with_repack, fbx_path + '.blend')

    program.run(blender, bpy_export.export_fbx, fbx_path, bpy_export.S_Fbx(
        add_leaf_bones = False,
        bake_anim = False,
    ))

    return program


def get_arguments(
            blender_executable: str,
            main_root: str,
            root = configuration.Folder.INTERMEDIATE_BLEND_SKELETAL,
            result_root = configuration.Folder.FBX_SKELETAL,
        ):

    from blend_converter import utils

    root = os.path.join(main_root, *root)
    result_root = os.path.join(main_root, *result_root)


    arguments = []

    for folder in configuration.get_folders(root):

        last_blend = utils.get_last_blend(folder)
        if not last_blend:
            continue

        arguments.append(dict(
            blender_executable = blender_executable,
            blend_path = last_blend,
            result_root = result_root,
        ))


    return arguments
