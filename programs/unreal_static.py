import os

from .. import configuration

from ..scripts import bake as scripts_bake
from ..scripts import export as scripts_export
from ..scripts import unreal_engine as scripts_unreal



def get_program(
            blender_executable: str,
            blend_path: str,
            result_root: str,
            root_dist_dir: str,
        ):
    """ export as a fbx static mesh """

    from blend_converter.unreal import Unreal
    from blend_converter.blender.executor import Blender
    from blend_converter.blender import bpy_utils
    from blend_converter.blender import bpy_data
    from blend_converter.blender import bpy_export
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
        settings_path = os.path.join(blend_path.dir, 'bc_instructions.ini'),
    )

    program.tags.add('unreal')

    program._prog_type = 'UNREAL STATIC 👾'

    program.run(blender, scripts_export.check_if_writable, fbx_path)

    program.run(blender, bpy_data.open_mainfile, blend_path)

    program.run(blender, scripts_bake.reveal_collections)
    has_custom_collisions = program.run(blender, scripts_export.convert_all_collision_shapes)
    program.run(blender, scripts_export.convert_collisions_to_convex)
    program.run(blender, scripts_export.scene_clean_up)
    program.run(blender, scripts_export.remove_unused_uv_layouts)
    program.run(blender, bpy_utils.remove_all_node_groups_from_materials)
    program.run(blender, scripts_export.remove_animations)
    program.run(blender, bpy_utils.use_backface_culling)
    program.run(blender, scripts_export.delete_unused_materials)

    program.run(blender, scripts_unreal.reduce_to_single_mesh, dir_name)
    program.run(blender, scripts_export.triangulate_geometry, program.run(blender, scripts_bake.get_target_objects))
    program.run(blender, scripts_unreal.rename_objects_for_unreal, 'SM')

    material_definitions = program.run(blender, scripts_unreal.sanitize_material_names)
    material_definitions = program.run(blender, scripts_unreal.get_material_definitions_for_single_object)


    program.run(blender, bpy_export.export_fbx, fbx_path, bpy_export.S_Fbx(
        mesh_smooth_type = 'SMOOTH_GROUP'
    ))

    _, stem, _ = utils.split_path(fbx_path)

    fbx_settings = scripts_unreal.S_Unreal_Fbx(
        fbx_path = fbx_path,
        dist_name = stem,
        dist_dir = scripts_unreal.join_path(root_dist_dir, stem),
        material_definitions = material_definitions,
        has_custom_collisions = has_custom_collisions
    )

    program.run(unreal, scripts_unreal.import_static_mesh, fbx_settings)

    return program


def get_arguments(
            blender_executable: str,
            root: str,
            result_root: str,
            root_dist_dir: str = configuration.Folder.UNREAL_STATIC,
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
            root_dist_dir = root_dist_dir,
        ))


    return arguments
