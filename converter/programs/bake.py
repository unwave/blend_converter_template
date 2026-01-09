import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if not ROOT in sys.path:
    sys.path.append(ROOT)


import configuration

from scripts import bake as scripts_bake
from scripts import export as scripts_export


def get_unwrap_settings(config: configuration.Config):


    from blend_converter import tool_settings

    if config.quality.preset == 'preview':

        return tool_settings.Unwrap_UVs()

    else:

        settings = tool_settings.Unwrap_UVs(
            use_brute_force_unwrap = True,
        )

        # unwrap methods
        bfu_preset = config.uv_unwrap.bfu_preset
        bfu_method = config.uv_unwrap.bfu_method

        if bfu_method != 'NONE':
            settings.brute_unwrap_methods = ['NONE']
        elif bfu_preset == 'active_render':
            settings.brute_unwrap_methods = ['active_render', 'active_render_minimal_stretch']
        elif bfu_preset == 'mof_only':
            settings.brute_unwrap_methods = ['mof_default', 'mof_separate_hard_edges', 'mof_use_normal']
        elif bfu_preset == 'just_unwrap':
            settings.brute_unwrap_methods = ['just_minimal_stretch', 'just_conformal']

        return settings


def get_uv_pack_settings(config: configuration.Config):


    from blend_converter import tool_settings

    if config.quality.preset == 'preview':

        return tool_settings.Pack_UVs(
            # TODO: add use the efficient packer engine setting
        )

    else:

        settings = tool_settings.Pack_UVs(
            use_uv_packer_for_pre_packing = config.blend_bake.uv_packer_pin,
            uv_packer_addon_pin_largest_island = config.blend_bake.uv_packer_pin,
        )

        return settings


def get_ministry_of_flat_settings(config: configuration.Config):

    from blend_converter import tool_settings

    if config.quality.preset == 'preview':

        return tool_settings.Ministry_Of_Flat(
            ignore_default_settings = True,
            timeout = 10,
        )

    else:
        return tool_settings.Ministry_Of_Flat(
            ignore_default_settings = True,
            timeout = config.uv_unwrap.timeout,
            use_normal = config.uv_unwrap.use_normal,
            stretch = config.uv_unwrap.stretch,
            separate_hard_edges = config.uv_unwrap.separate_hard_edges,
        )



def get_texture_bake_settings(config: configuration.Config, texture_name_prefix: str):

    from blend_converter import tool_settings

    if config.quality.preset == 'preview':

        return tool_settings.Bake(
            samples=1,
            texture_name_prefix = texture_name_prefix,
            use_smart_texture_interpolation = False,
        )

    else:

        return tool_settings.Bake(
            resolution_multiplier = config.blend_bake.resolution_multiplier,
            samples = config.blend_bake.bake_samples,
            texture_name_prefix = texture_name_prefix
        )


def get_bake_settings(config: configuration.Config, textures_folder: str, pre_bake_labels: list):

    from blend_converter import tool_settings

    if config.quality.preset == 'preview':

        return tool_settings.Bake_Materials(

            ignore_default_settings = True,
            image_dir = textures_folder,

            texel_density = config.blend_bake.texel_density // 2,
            min_resolution = config.blend_bake.min_resolution // 2,
            max_resolution = config.blend_bake.max_resolution // 2,

            denoise_all = False,
            ao_bake_use_normals = False,

            uv_layer_reuse = tool_settings.DEFAULT_UV_LAYER_NAME,
            convert_materials = False,  # converting earlier
        )

    else:

        return tool_settings.Bake_Materials(

            ignore_default_settings = True,
            image_dir = textures_folder,

            texel_density = config.blend_bake.texel_density,
            min_resolution = config.blend_bake.min_resolution,
            max_resolution = config.blend_bake.max_resolution,

            denoise_all = True,
            faster_ao_bake = config.blend_bake.faster_ao_bake,

            pre_bake_labels = pre_bake_labels,

            uv_layer_reuse = tool_settings.DEFAULT_UV_LAYER_NAME,
            convert_materials = False,  # converting earlier
        )


def get_texture_prefix(folder_name: str):
    """ TODO: should be a visible warning """

    if folder_name.lower() != configuration.get_ascii_underscored(folder_name):
        raise Exception(f"Invalid folder name: {repr(folder_name.lower())} != {repr(configuration.get_ascii_underscored(folder_name))}")

    texture_prefix = 'T_' + str(folder_name).removeprefix('GROUP_').removeprefix('SPLIT_')

    if texture_prefix.lower() != configuration.get_ascii_underscored(texture_prefix):
        raise Exception(f"Invalid texture_prefix: {repr(folder_name.lower())} != {repr(configuration.get_ascii_underscored(texture_prefix))}")

    return texture_prefix


def get_bake_program(blend_path, top_folder: str, textures_folder: str):
    """ Convert to an exportable blend file, e.g. bake materials, apply modifiers. """


    from blend_converter.blender import Blender, bc_script
    from blend_converter.blender.formats.blend import open_mainfile, save_as_mainfile
    from blend_converter import common
    from blend_converter import tool_settings


    blend_path = common.File(blend_path)

    result_path = os.path.join(top_folder, blend_path.dir_name, blend_path.dir_name + '.blend')

    print(result_path)

    blender = Blender(configuration.BLENDER_EXECUTABLE)

    program = common.Program(
        blend_path = blend_path,
        result_path = result_path,
        blender_executable = blender.binary_path,
    )

    program._prog_type = 'BAKE 🍪'

    program.config = configuration.Config(os.path.join(blend_path.dir, 'bc_config.ini'))


    program.run(blender, open_mainfile, blend_path)

    program.run(blender, scripts_bake.reset_timeline)
    program.run(blender, scripts_bake.find_missing)
    program.run(blender, scripts_bake.reveal_collections)

    objects = program.run(blender, scripts_bake.get_target_objects)

    program.run(blender, scripts_bake.check_for_reserved_uv_layout_name, objects)

    program.run(blender, scripts_bake.apply_modifiers)

    program.run(blender, bc_script.clean_up_topology_and_triangulate_ngons, objects)
    program.run(blender, bc_script.unwrap,
        objects,
        uv_layer_reuse = 'REUSE',
        settings = get_unwrap_settings(program.config),
        ministry_of_flat_settings = get_ministry_of_flat_settings(program.config)
    )

    program.run(blender, scripts_bake.apply_modifiers, scripts_bake.Modifier_Type.POST_UNWRAP)

    program.run(blender, scripts_bake.convert_materials, objects)

    pre_bake_labels = program.run(blender, bc_script.label_mix_shader_nodes, objects)

    program.run(blender, bc_script.bisect_by_mirror_modifiers, objects)

    program.run(blender, bc_script.scale_uv_to_world_per_uv_island, objects, tool_settings.DEFAULT_UV_LAYER_NAME)
    program.run(blender, bc_script.scale_uv_to_world_per_uv_layout, objects, tool_settings.DEFAULT_UV_LAYER_NAME)

    objects = program.run(blender, bc_script.pack_copy_bake,
        objects,
        get_bake_settings(program.config, textures_folder, pre_bake_labels),
        bake_settings = get_texture_bake_settings(program.config, get_texture_prefix(blend_path.dir_name)),
        pack_settings = get_uv_pack_settings(program.config),
    )

    program.run(blender, scripts_bake.apply_modifiers, scripts_bake.Modifier_Type.POST_BAKE)

    program.run(blender, bc_script.apply_scale, objects)
    program.run(blender, scripts_bake.join_objects)

    program.run(blender, scripts_bake.make_paths_relative)
    program.run(blender, save_as_mainfile, result_path)


    return program


def convert_to_blend_RIG(blend_path):
    """ for use a linked rig + mesh for creating animations """

    from blend_converter.blender import Blender, bc_script
    from blend_converter.blender.formats.blend import open_mainfile, save_as_mainfile
    from blend_converter import common

    blend_path = common.File(blend_path)

    asset_folder = os.path.join(configuration.Folder.BLEND_RIG, blend_path.dir_name)

    result_path = os.path.join(asset_folder, blend_path.dir_name + '.blend')

    blender = Blender(configuration.BLENDER_EXECUTABLE)

    program = common.Program(
        blend_path = blend_path,
        result_path = result_path,
        blender_executable = blender.binary_path,
    )

    program._prog_type = 'RIG 🦴'

    program.run(blender, open_mainfile, blend_path)

    # program.run(blender, script.scene_clean_up)
    program.run(blender, scripts_export.remove_unused_uv_layouts)
    program.run(blender, bc_script.remove_all_node_groups_from_materials)
    # program.run(blender, script.remove_animations)
    program.run(blender, bc_script.use_backface_culling)

    program.run(blender, save_as_mainfile, result_path)

    return program



def get_programs():

    from blend_converter import utils, common
    programs = utils.Appendable_Dict()

    asset_folders = [file for file in os.scandir(configuration.Folder.BLEND_STATIC) if file.is_dir()]


    def get_baked(path: os.PathLike, folder: str, resources_folder: str):

        dir_name = os.path.basename(os.path.dirname(path))

        # can store the textures in the final location to avoid copies
        # for glTF export_keep_originals=True can be used then
        texture_folder = os.path.join(resources_folder, dir_name, 'textures')

        baked_model = get_bake_program(path, folder, texture_folder)
        programs.append(baked_model)
        return baked_model


    for folder in asset_folders:

        if folder.name.startswith('_'):  # temp or WIP assets to ignore
            continue

        last_blend = utils.get_last_blend(folder)
        if not last_blend:
            continue

        if folder.name.startswith('GROUP_'):
            raise NotImplementedError("split into multiple fbx with shared materials")
        elif folder.name.startswith('SPLIT_'):
            raise NotImplementedError("split into multiple fbx with independent materials")
        else:
            baked_model = get_baked(last_blend, configuration.Folder.INTERMEDIATE_STATIC, configuration.Folder.INTERMEDIATE_STATIC)


    return programs
