import os



from .. import configuration

from ..scripts import bake as scripts_bake
from ..scripts import export as scripts_export
from ..scripts import godot as scripts_godot


def get_program(
            blender_executable: str,
            blend_path: str,
            result_root: str,
        ):


    from blend_converter.blender.executor import Blender
    from blend_converter.blender import bpy_utils
    from blend_converter.blender import bpy_data
    from blend_converter.blender import bpy_export
    from blend_converter import common


    blend_path: common.File = common.File(blend_path)

    gltf_path = os.path.join(result_root, blend_path.dir_name, blend_path.dir_name + '.gltf')

    blender = Blender(blender_executable)

    program = common.Program(
        blend_path = blend_path,
        result_path = gltf_path,
        blender_executable = blender.binary_path,
        settings_path = os.path.join(blend_path.dir, 'bc_instructions.ini'),
    )

    program.tags.add('godot')

    program._prog_type = 'GODOT STATIC 👾'

    program.run(blender, bpy_data.open_mainfile, blend_path)

    program.run(blender, scripts_bake.reveal_collections)
    program.run(blender, scripts_export.convert_all_collision_shapes)
    program.run(blender, scripts_export.convert_collisions_to_convex)
    program.run(blender, scripts_export.scene_clean_up)
    program.run(blender, scripts_export.remove_unused_uv_layouts)
    program.run(blender, bpy_utils.remove_all_node_groups_from_materials)
    program.run(blender, scripts_export.remove_animations)
    program.run(blender, bpy_utils.use_backface_culling)
    program.run(blender, scripts_export.triangulate_geometry, program.run(blender, scripts_bake.get_target_objects))
    program.run(blender, scripts_export.delete_unused_materials)
    program.run(blender, scripts_godot.rename_objects_for_godot, 'SM')
    program.run(blender, scripts_godot.add_export_timestamp)

    program.run(blender, bpy_export.export_gltf, gltf_path, bpy_export.S_GLTF(export_format='GLTF_SEPARATE'))

    program.run(blender, scripts_godot.set_gd_import_script, gltf_path, '', is_instruction_enabled = False)

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

        last_blend = utils.get_last_blend(folder)
        if not last_blend:
            continue

        arguments.append(dict(
            blender_executable = blender_executable,
            blend_path = last_blend,
            result_root = result_root,
        ))


    return arguments
