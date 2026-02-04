import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if not ROOT in sys.path:
    sys.path.append(ROOT)


import configuration

from scripts import bake as scripts_bake
from scripts import export as scripts_export
from scripts import unreal_engine as scripts_unreal


class Hierarchy:

    STATIC = '/Game/static_meshes/'
    SKELETAL = '/Game/skeletal_meshes/'
    ANIM = '/Game/animations/'

    @staticmethod
    def join(*paths):
        path = os.path.join(*paths).replace(os.sep, '/')
        path = path.lstrip('/')
        return '/' + path



def convert_to_unreal_static_mesh(
            blender_executable: str,
            blend_path: str,
            result_root = configuration.Folder.INTERMEDIATE_UNREAL_SM,
        ):
    """ export as a fbx static mesh """

    from blend_converter.unreal import Unreal
    from blend_converter.blender.executor import Blender
    from blend_converter.blender import bc_script
    from blend_converter.blender.formats.blend import open_mainfile
    from blend_converter.blender.formats.fbx import export_fbx, Settings_Fbx
    from blend_converter import common
    from blend_converter import utils


    blend_path: common.File = common.File(blend_path)

    dir_name = configuration.get_ascii_underscored(blend_path.dir_name)

    fbx_path = os.path.join(result_root, dir_name, dir_name + '.fbx')

    unreal = Unreal()
    blender = Blender(blender_executable)

    program = common.Program(
        blend_path = blend_path,
        result_path = fbx_path,
        blender_executable = blender.binary_path,
    )

    program.tags.add('unreal')

    program._prog_type = 'SM 👾'

    program.run(blender, open_mainfile, blend_path)

    program.run(blender, scripts_bake.reveal_collections)
    has_custom_collisions = program.run(blender, scripts_export.convert_all_collision_shapes)
    program.run(blender, scripts_export.convert_collisions_to_convex)
    program.run(blender, scripts_export.scene_clean_up)
    program.run(blender, scripts_export.remove_unused_uv_layouts)
    program.run(blender, bc_script.remove_all_node_groups_from_materials)
    program.run(blender, scripts_export.remove_animations)
    program.run(blender, bc_script.use_backface_culling)
    program.run(blender, scripts_export.triangulate_geometry)
    program.run(blender, scripts_export.delete_unused_materials)

    program.run(blender, scripts_unreal.reduce_to_single_mesh, dir_name)
    program.run(blender, scripts_unreal.rename_objects_for_unreal, 'SM')

    material_definitions = program.run(blender, scripts_unreal.get_material_definitions_for_single_object)

    program.run(blender, export_fbx, fbx_path, Settings_Fbx(
        mesh_smooth_type = 'SMOOTH_GROUP'
    ))

    _, stem, _ = utils.split_path(fbx_path)

    fbx_settings = scripts_unreal.Settings_Unreal_Fbx(
        fbx_path = fbx_path,
        dist_name = stem,
        dist_dir = Hierarchy.join(Hierarchy.STATIC, stem),
        material_definitions = material_definitions,
        has_custom_collisions = has_custom_collisions
    )

    program.run(unreal, scripts_unreal.import_static_mesh, fbx_settings)

    return program


def convert_to_unreal_skeletal_mesh(
            blender_executable: str,
            blend_path: str,
            result_root = configuration.Folder.INTERMEDIATE_UNREAL_SK,
        ):
    """ export as a fbx skeletal mesh """

    from blend_converter.unreal import Unreal
    from blend_converter.blender.executor import Blender
    from blend_converter.blender import bc_script
    from blend_converter.blender.formats.blend import open_mainfile
    from blend_converter.blender.formats.fbx import export_fbx, Settings_Fbx
    from blend_converter import common
    from blend_converter import utils


    blend_path: common.File = common.File(blend_path)

    dir_name = configuration.get_ascii_underscored(blend_path.dir_name)

    fbx_path = os.path.join(result_root, dir_name, dir_name + '.fbx')

    unreal = Unreal()
    blender = Blender(blender_executable)

    program = common.Program(
        blend_path = blend_path,
        result_path = fbx_path,
        blender_executable = blender.binary_path,
    )

    program.tags.add('unreal')

    program._prog_type = 'SK 👾'

    program.run(blender, open_mainfile, blend_path)

    program.run(blender, scripts_bake.reveal_collections)
    program.run(blender, scripts_export.scene_clean_up)
    program.run(blender, scripts_export.remove_unused_uv_layouts)
    program.run(blender, bc_script.remove_all_node_groups_from_materials)
    program.run(blender, scripts_export.remove_animations)
    program.run(blender, bc_script.use_backface_culling)
    program.run(blender, scripts_export.triangulate_geometry)
    program.run(blender, scripts_export.delete_unused_materials)
    program.run(blender, scripts_bake.create_game_rig_and_bake_actions)
    program.run(blender, bc_script.create_default_root_bone)

    program.run(blender, scripts_unreal.rename_objects_for_unreal, 'SK')
    program.run(blender, scripts_export.rename_all_armatures)


    material_definitions = program.run(blender, scripts_unreal.get_material_definitions_for_single_object)

    program.run(blender, export_fbx, fbx_path, Settings_Fbx(
        add_leaf_bones = False,
        bake_anim=False,
        mesh_smooth_type = 'SMOOTH_GROUP',
    ))

    _, stem, _ = utils.split_path(fbx_path)

    fbx_settings = scripts_unreal.Settings_Unreal_Fbx(
        fbx_path = fbx_path,
        dist_name = stem,
        dist_dir = Hierarchy.join(Hierarchy.SKELETAL, stem),
        material_definitions = material_definitions,
    )

    program.run(unreal, scripts_unreal.import_skeletal_mesh, fbx_settings)

    return program


def convert_to_unreal_animation(
            blender_executable: str,
            blend_path,
            rig_name: str,
            animation_name: str,
            result_root = configuration.Folder.INTERMEDIATE_UNREAL_A,
        ):
    """ export as an animation only fbx file """

    from blend_converter.unreal import Unreal
    from blend_converter.blender.executor import Blender
    from blend_converter.blender import bc_script
    from blend_converter.blender.formats.blend import open_mainfile
    from blend_converter.blender.formats.fbx import export_fbx, Settings_Fbx
    from blend_converter import common

    blend_path = common.File(blend_path)

    rig_name = configuration.get_ascii_underscored(rig_name)
    animation_name = configuration.get_ascii_underscored(animation_name)

    fbx_path = os.path.join(result_root, rig_name, animation_name + '.fbx')

    unreal = Unreal()
    blender = Blender(blender_executable)

    program = common.Program(
        blend_path = blend_path,
        result_path = fbx_path,
        blender_executable = blender.binary_path,
    )

    program.tags.add('unreal')

    program._prog_type = 'A 👾'

    program.run(blender, open_mainfile, blend_path)

    program.run(blender, scripts_export.make_local_and_delete_non_armature_objects)
    program.run(blender, scripts_bake.create_game_rig_and_bake_actions)
    program.run(blender, scripts_export.rename_all_armatures)

    program.run(blender, scripts_unreal.rename_objects_for_unreal, 'SK')

    program.run(blender, export_fbx, fbx_path, Settings_Fbx(
        add_leaf_bones = False,
        # bake_anim_force_startend_keying=True,
        # bake_anim_use_all_bones=False,
        # bake_anim_use_nla_strips=False,
        # bake_anim_use_all_actions=False,
    ))


    ue_fbx_settings = scripts_unreal.Settings_Unreal_Fbx(
        fbx_path = fbx_path,
        dist_dir =  Hierarchy.join(Hierarchy.ANIM, rig_name),
        dist_name = f'A_{rig_name}_{animation_name}',
        skeleton_asset_path = Hierarchy.join(Hierarchy.SKELETAL, rig_name, f'{rig_name}_Skeleton'),
    )

    program.run(unreal, scripts_unreal.import_anim_sequence, ue_fbx_settings)

    return program


def get_unreal_kwargs(blender_executable: str, root: str):

    from blend_converter import utils

    arguments = []

    if os.path.exists(root):
        asset_folders = [file for file in os.scandir(root) if file.is_dir()]
    else:
        asset_folders = []

    for folder in asset_folders:

        last_blend = utils.get_last_blend(folder)
        if not last_blend:
            continue

        if folder.name.startswith('GROUP_'):
            raise NotImplementedError("split into multiple fbx with shared materials")
        elif folder.name.startswith('SPLIT_'):
            raise NotImplementedError("split into multiple fbx with independent materials")
        else:
            arguments.append(dict(
                blender_executable = blender_executable,
                blend_path = last_blend,
            ))


    return arguments


def get_static_unreal_kwargs(
            blender_executable: str,
            root = configuration.Folder.INTERMEDIATE_BLEND_STATIC,
        ):
    return get_unreal_kwargs(blender_executable, root)


def get_skeletal_unreal_kwargs(
            blender_executable: str,
            root = configuration.Folder.INTERMEDIATE_BLEND_SKELETAL,
        ):
    return get_unreal_kwargs(blender_executable, root)


def get_unreal_animation_kwargs(
            blender_executable: str,
            root: str,
            result_root = configuration.Folder.INTERMEDIATE_UNREAL_A,
        ):

    from blend_converter import utils

    arguments = []

    for rig_folder in configuration.get_folders(root):

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
                result_root = result_root,
            ))


    return arguments
