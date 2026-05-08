import os

from .. import configuration

from ..scripts import bake as scripts_bake
from ..scripts import custom_per_blend


def get_texture_prefix(folder_name: str):

    folder_name = str(folder_name)

    return configuration.get_ascii_underscored(folder_name)


def get_bake_program(
            blender_executable: str,
            blend_path,
            top_folder: str,
            textures_folder: str,
            is_skeletal: bool,
        ):
    """ Convert to an exportable blend file, e.g. bake materials, apply modifiers. """

    from blend_converter.blender.executor import Blender
    from blend_converter.blender import bpy_uv
    from blend_converter.blender import bpy_utils
    from blend_converter.blender import bpy_data
    from blend_converter import common
    from blend_converter import tool_settings


    blend_path = common.File(blend_path)

    result_path = os.path.join(top_folder, blend_path.dir_name, blend_path.dir_name + '.blend')

    print(result_path)

    blender = Blender(blender_executable, timeout = 30 * 60)

    program = common.Program(
        blend_path = blend_path,
        result_path = result_path,
        blender_executable = blender.binary_path,
        settings_path = os.path.join(blend_path.dir, 'bc_instructions.ini'),
    )

    if is_skeletal:
        program._prog_type = 'BAKE SKELETAL 🍪'
    else:
        program._prog_type = 'BAKE STATIC 🍪'


    program.run(blender, bpy_data.open_mainfile, blend_path)

    program.run(blender, scripts_bake.make_data_local)

    program.run(blender, scripts_bake.set_legacy_ik_solver)
    program.run(blender, scripts_bake.delete_undefined_nodes)

    custom_per_blend.fix(blender, program)

    if is_skeletal:
        program.run(blender, scripts_bake.validate_root_bones)
        program.run(blender, scripts_bake.reset_timeline)

    program.run(blender, scripts_bake.find_missing)
    program.run(blender, scripts_bake.reveal_collections)

    program.run(blender, scripts_bake.apply_particle_systems, program.run(blender, scripts_bake.get_target_objects))

    objects = program.run(blender, scripts_bake.get_target_objects)


    program.run(blender, scripts_bake.delete_hidden_modifiers, objects)

    objects = program.run(blender, scripts_bake.convert_to_mesh_non_mesh_objects, objects)

    ignore_type = ['ARMATURE'] if is_skeletal else []

    if not is_skeletal:
        program.run(blender, scripts_bake.apply_shape_keys, objects)

    program.run(blender, scripts_bake.apply_modifiers, objects, ignore_type = ignore_type)

    program.run(blender, scripts_bake.delete_empty_meshes, program.run(blender, scripts_bake.get_target_objects))
    objects = program.run(blender, scripts_bake.get_target_objects)

    program.run(blender, bpy_utils.clean_up_topology_and_triangulate_ngons, objects)

    uv_layer_name = program.run(blender, bpy_utils.get_uuid1_hex)

    x_resolution = program.run(blender, scripts_bake.get_x_resolution)
    y_resolution = program.run(blender, scripts_bake.get_y_resolution)

    program.run(blender, bpy_uv.unwrap,
        objects,
        uv_layer_name = uv_layer_name,
        uv_layer_reuse = 'REUSE',
        settings = tool_settings.S_Unwrap_UVs(uv_layer_name = uv_layer_name),
        ministry_of_flat_settings = tool_settings.S_Ministry_Of_Flat(timeout = 10, texture_resolution = y_resolution),
    )

    program.run(blender, bpy_uv.reunwrap_bad_uvs, objects, uv_layer_name = uv_layer_name)

    program.run(blender, scripts_bake.apply_modifiers, objects, scripts_bake.Modifier_Type.POST_UNWRAP, ignore_type = ignore_type)

    program.run(blender, bpy_utils.bisect_by_mirror_modifiers, objects)

    program.run(blender, bpy_uv.scale_uv_to_world_per_uv_island, objects, uv_layer_name)
    program.run(blender, bpy_uv.scale_uv_to_world_per_uv_layout, objects, uv_layer_name)

    tasks = program.run(blender, bpy_utils.pack_and_task,
        objects,
        tool_settings.S_Bake_Materials(
            image_dir = textures_folder,
            uv_layer_bake = uv_layer_name,
            width = x_resolution,
            height = y_resolution,
        ),
        bake_settings = tool_settings.S_Bake(
            texture_name_prefix = get_texture_prefix(blend_path.dir_name),
            uv_layer_name = uv_layer_name,
            width = x_resolution,
            height = y_resolution,
        ),
        pack_settings = tool_settings.S_Pack_UVs(
            uv_layer_name = uv_layer_name,
            width = x_resolution,
            height = y_resolution,
        ),
    )

    pre_bake_labels = program.run(blender, bpy_utils.label_mix_shader_nodes, objects)

    program.run(blender, bpy_utils.copy_and_bake, objects, tasks, pre_bake_labels = pre_bake_labels)

    program.run(blender, bpy_utils.assign_new_materials, objects, tasks)

    program.run(blender, scripts_bake.apply_modifiers, objects, scripts_bake.Modifier_Type.POST_BAKE, ignore_type = ignore_type)

    program.run(blender, bpy_utils.apply_scale, objects)
    program.run(blender, scripts_bake.join_objects, objects)

    if is_skeletal:
         program.run(blender, scripts_bake.unassign_deform_bones_with_missing_weights)

    program.run(blender, bpy_utils.select_uv_layer, objects, uv_layer_name)
    program.run(blender, scripts_bake.hide_non_target_objects)

    program.run(blender, scripts_bake.make_paths_relative)
    program.run(blender, bpy_data.save_as_mainfile, result_path)


    return program


def get_static_kwargs(
            blender_executable: str,
            main_root: str,
            root = configuration.Folder.BLEND_STATIC,
            result_root = configuration.Folder.INTERMEDIATE_BLEND_STATIC,
        ):

    root = os.path.join(main_root, *root)
    result_root = os.path.join(main_root, *result_root)

    from blend_converter import utils

    arguments = []

    asset_folders = configuration.get_folders(root)


    def get_baked(path: os.PathLike, folder: str, resources_folder: str):

        dir_name = os.path.basename(os.path.dirname(path))

        # can store the textures in the final location to avoid copies
        # for glTF export_keep_originals=True can be used then
        texture_folder = os.path.join(resources_folder, dir_name, 'textures')

        return dict(
            blender_executable = blender_executable,
            blend_path = path,
            top_folder = folder,
            textures_folder = texture_folder,
            is_skeletal = False,
        )


    for folder in asset_folders:

        if folder.name.startswith('_'):  # temp or WIP assets to ignore
            continue

        last_blend = utils.get_last_blend(folder)
        if not last_blend:
            continue

        arguments.append(get_baked(last_blend, result_root, result_root))


    return arguments


def get_skeletal_kwargs(
            blender_executable: str,
            main_root: str,
            root = configuration.Folder.BLEND_SKELETAL,
            result_root = configuration.Folder.INTERMEDIATE_BLEND_SKELETAL,
        ):

    root = os.path.join(main_root, *root)
    result_root = os.path.join(main_root, *result_root)

    from blend_converter import utils

    arguments = []

    asset_folders = configuration.get_folders(root)


    def get_baked(path: os.PathLike, folder: str, resources_folder: str):

        dir_name = os.path.basename(os.path.dirname(path))

        # can store the textures in the final location to avoid copies
        # for glTF export_keep_originals=True can be used then
        texture_folder = os.path.join(resources_folder, dir_name, 'textures')

        return dict(
            blender_executable = blender_executable,
            blend_path = path,
            top_folder = folder,
            textures_folder = texture_folder,
            is_skeletal = True,
        )


    for folder in asset_folders:

        if folder.name.startswith('_'):  # temp or WIP assets to ignore
            continue

        last_blend = utils.get_last_blend(folder)
        if not last_blend:
            continue

        arguments.append(get_baked(last_blend, result_root, result_root))


    return arguments
