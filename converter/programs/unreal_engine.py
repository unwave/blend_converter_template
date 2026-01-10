import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if not ROOT in sys.path:
    sys.path.append(ROOT)


import configuration

from scripts import bake as scripts_bake
from scripts import export as scripts_export
from scripts import unreal_engine as scripts_unreal




def convert_to_unreal_static_mesh(blend_path: str):
    """ export as a fbx static mesh """

    from blend_converter.unreal import Unreal
    from blend_converter.blender import Blender, bc_script
    from blend_converter.blender.formats.blend import open_mainfile
    from blend_converter.blender.formats.fbx import export_fbx, Settings_Fbx
    from blend_converter import common
    from blend_converter import utils


    blend_path: common.File = common.File(blend_path)

    fbx_path = os.path.join(configuration.Folder.INTERMEDIATE_UNREAL_SM, blend_path.dir_name, blend_path.dir_name + '.fbx')

    unreal = Unreal()
    blender = Blender(configuration.BLENDER_EXECUTABLE)

    program = common.Program(
        blend_path = blend_path,
        result_path = fbx_path,
        blender_executable = configuration.BLENDER_EXECUTABLE,
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

    program.run(blender, scripts_unreal.rename_objects_for_unreal, 'SM')

    program.run(blender, export_fbx, fbx_path)

    material_definitions = program.run(blender, scripts_unreal.get_material_definitions_for_single_object)

    _, stem, _ = utils.split_path(fbx_path)

    fbx_settings = scripts_unreal.Settings_Unreal_Fbx(
        fbx_path = fbx_path,
        dist_name = stem,
        dist_dir = f'/Game/static_meshes/{stem}/',
        material_definitions = material_definitions,
        has_custom_collisions = has_custom_collisions
    )

    program.run(unreal, scripts_unreal.import_static_mesh, fbx_settings)

    return program


def convert_to_unreal_skeletal_mesh(blend_path: str):
    """ export as a fbx skeletal mesh """

    from blend_converter.unreal import Unreal
    from blend_converter.blender import Blender, bc_script
    from blend_converter.blender.formats.blend import open_mainfile
    from blend_converter.blender.formats.fbx import export_fbx, Settings_Fbx
    from blend_converter import common
    from blend_converter import utils


    blend_path: common.File = common.File(blend_path)

    fbx_path = os.path.join(configuration.Folder.INTERMEDIATE_UNREAL_SK, blend_path.dir_name, blend_path.dir_name + '.fbx')

    unreal = Unreal()
    blender = Blender(configuration.BLENDER_EXECUTABLE)

    program = common.Program(
        blend_path = blend_path,
        result_path = fbx_path,
        blender_executable = configuration.BLENDER_EXECUTABLE,
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
    program.run(blender, scripts_bake.create_game_rig_and_bake_actions)
    program.run(blender, bc_script.create_default_root_bone)

    program.run(blender, scripts_unreal.rename_objects_for_unreal, 'SK')
    program.run(blender, scripts_export.rename_all_armatures)

    program.run(blender, export_fbx, fbx_path, Settings_Fbx(
        add_leaf_bones=True,
        bake_anim=False,
    ))

    material_definitions = program.run(blender, scripts_unreal.get_material_definitions_for_single_object)

    _, stem, _ = utils.split_path(fbx_path)

    fbx_settings = scripts_unreal.Settings_Unreal_Fbx(
        fbx_path = fbx_path,
        dist_name = stem,
        dist_dir = f'/Game/skeletal_meshes/{stem}/',
        material_definitions = material_definitions,
    )

    program.run(unreal, scripts_unreal.import_skeletal_mesh, fbx_settings)

    return program


def convert_to_unreal_animation(blend_path, rig_name: str, animation_name: str):
    """ export as an animation only fbx file """

    from blend_converter.unreal import Unreal
    from blend_converter.blender import Blender, bc_script
    from blend_converter.blender.formats.blend import open_mainfile
    from blend_converter.blender.formats.fbx import export_fbx, Settings_Fbx
    from blend_converter import common

    blend_path = common.File(blend_path)

    fbx_path = os.path.join(configuration.Folder.INTERMEDIATE_UNREAL_A, rig_name, animation_name + '.fbx')

    unreal = Unreal()
    blender = Blender(configuration.BLENDER_EXECUTABLE)

    program = common.Program(
        blend_path = blend_path,
        result_path = fbx_path,
        blender_executable = configuration.BLENDER_EXECUTABLE,
    )

    program.tags.add('unreal')

    program._prog_type = 'A 👾'

    program.run(blender, open_mainfile, blend_path)

    program.run(blender, scripts_export.make_local_and_delete_non_armature_objects)
    program.run(blender, scripts_bake.create_game_rig_and_bake_actions)
    program.run(blender, scripts_export.rename_all_armatures)

    program.run(blender, scripts_unreal.rename_objects_for_unreal, 'SK')

    program.run(blender, export_fbx, fbx_path, Settings_Fbx(
        add_leaf_bones=True,
        # bake_anim_force_startend_keying=True,
        # bake_anim_use_all_bones=False,
        # bake_anim_use_nla_strips=False,
        # bake_anim_use_all_actions=False,
    ))


    ue_fbx_settings = scripts_unreal.Settings_Unreal_Fbx(
        fbx_path = fbx_path,
        dist_dir = f'/Game/animations/{rig_name}/',
        dist_name = f'A_{rig_name}_' + animation_name,
    )

    program.run(unreal, scripts_unreal.import_anim_sequence, ue_fbx_settings)

    return program


def get_programs():

    from blend_converter import utils
    programs = utils.Appendable_Dict()

    if os.path.exists(configuration.Folder.INTERMEDIATE_BLEND_STATIC):
        asset_folders = [file for file in os.scandir(configuration.Folder.INTERMEDIATE_BLEND_STATIC) if file.is_dir()]
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
            programs.append(convert_to_unreal_static_mesh(last_blend))


    return programs
