import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if not ROOT in sys.path:
    sys.path.append(ROOT)


import configuration

from scripts import bake as scripts_bake
from scripts import export as scripts_export
from scripts import godot as scripts_godot


def convert_to_static_mesh(
            blender_executable: str,
            blend_path: str,
            result_root = configuration.Folder.GODOT_GLTF_STATIC,
        ):
    """ export as a fbx static mesh """

    from blend_converter.blender.executor import Blender
    from blend_converter.blender import bc_script
    from blend_converter.blender.formats.blend import open_mainfile
    from blend_converter.blender.formats.gltf import export_gltf, Settings_GLTF
    from blend_converter import common


    blend_path: common.File = common.File(blend_path)

    gltf_path = os.path.join(result_root, blend_path.dir_name, blend_path.dir_name + '.gltf')

    blender = Blender(blender_executable)

    program = common.Program(
        blend_path = blend_path,
        result_path = gltf_path,
        blender_executable = blender.binary_path,
    )

    program.tags.add('gltf')

    program._prog_type = 'STATIC 👾'

    program.run(blender, open_mainfile, blend_path)

    program.run(blender, scripts_bake.reveal_collections)
    program.run(blender, scripts_export.convert_all_collision_shapes)
    program.run(blender, scripts_export.convert_collisions_to_convex)
    program.run(blender, scripts_export.scene_clean_up)
    program.run(blender, scripts_export.remove_unused_uv_layouts)
    program.run(blender, bc_script.remove_all_node_groups_from_materials)
    program.run(blender, scripts_export.remove_animations)
    program.run(blender, bc_script.use_backface_culling)
    program.run(blender, scripts_export.triangulate_geometry)
    program.run(blender, scripts_export.delete_unused_materials)
    program.run(blender, scripts_godot.rename_objects_for_godot, 'SM')
    program.run(blender, scripts_godot.add_export_timestamp)

    program.run(blender, export_gltf, gltf_path, Settings_GLTF(export_format='GLTF_SEPARATE'))

    program.run(blender, scripts_godot.set_gd_import_script, gltf_path, 'res://test_import_script.gd')

    return program


def convert_to_skeletal_mesh(
            blender_executable: str,
            blend_path: str,
            result_root = configuration.Folder.GODOT_GLTF_SKELETAL,
        ):
    """ export as a fbx skeletal mesh """

    from blend_converter.blender.executor import Blender
    from blend_converter.blender import bc_script
    from blend_converter.blender.formats.blend import open_mainfile
    from blend_converter.blender.formats.gltf import export_gltf, Settings_GLTF
    from blend_converter import common
    from blend_converter import utils


    blend_path: common.File = common.File(blend_path)

    gltf_path = os.path.join(result_root, blend_path.dir_name, blend_path.dir_name + '.gltf')

    blender = Blender(blender_executable)

    program = common.Program(
        blend_path = blend_path,
        result_path = gltf_path,
        blender_executable = blender.binary_path,
    )

    program.tags.add('gltf')

    program._prog_type = 'SKELETAL 👾'

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
    program.run(blender, scripts_godot.rename_objects_for_godot, 'SK')
    program.run(blender, scripts_export.rename_all_armatures)
    program.run(blender, scripts_godot.add_export_timestamp)

    program.run(blender, export_gltf, gltf_path, Settings_GLTF(export_format='GLTF_SEPARATE'))

    program.run(blender, scripts_godot.set_gd_import_script, gltf_path, 'res://test_import_script.gd')

    return program


def convert_to_animation(
            blender_executable: str,
            blend_path,
            rig_name: str,
            animation_name: str,
            result_root = configuration.Folder.GODOT_GLTF_ANIMATION,
        ):
    """ export as an animation only fbx file """

    from blend_converter.blender.executor import Blender
    from blend_converter.blender import bc_script
    from blend_converter.blender.formats.blend import open_mainfile
    from blend_converter.blender.formats.gltf import export_gltf, Settings_GLTF
    from blend_converter import common

    blend_path = common.File(blend_path)

    gltf_path = os.path.join(result_root, blend_path.dir_name, blend_path.dir_name + '.gltf')

    blender = Blender(blender_executable)

    program = common.Program(
        blend_path = blend_path,
        result_path = gltf_path,
        blender_executable = blender.binary_path,
    )

    program.tags.add('gltf')

    program._prog_type = 'ANIMATION 👾'

    program.run(blender, open_mainfile, blend_path)

    program.run(blender, scripts_godot.rename_objects_for_godot, 'SK')
    program.run(blender, scripts_export.make_local)
    program.run(blender, scripts_godot.add_export_timestamp)
    program.run(blender, scripts_bake.create_game_rig_and_bake_actions)
    program.run(blender, scripts_export.delete_non_armature_objects)
    program.run(blender, scripts_export.rename_all_armatures)

    program.run(blender, export_gltf, gltf_path, Settings_GLTF(export_format='GLTF_SEPARATE'))

    program.run(blender, scripts_godot.set_gd_import_script, gltf_path, 'res://test_import_script.gd')

    return program


def get_anim_programs(root = configuration.Folder.BLEND_ANIM):

    from blend_converter import utils
    programs = utils.Appendable_Dict()

    for folder in configuration.get_folders(root):

        rig_name = os.path.basename(folder)

        for blend_file in configuration.get_blends(folder):

            animation_name = os.path.splitext(os.path.basename(blend_file))[0]

            programs.append(convert_to_animation(blend_file, rig_name, animation_name))


    return programs


def get_godot_kwargs(
            blender_executable: str,
            root = configuration.Folder.INTERMEDIATE_BLEND_STATIC
        ):

    from blend_converter import utils

    arguments = []

    asset_folders = [file for file in os.scandir(root) if file.is_dir()]

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
