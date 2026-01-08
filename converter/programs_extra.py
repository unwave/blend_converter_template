import os


import configuration

import scripts_bake
import scripts_export


def convert_to_blend_SKIN_TEST(blend_path):
    """ For iterative testing of skinning and weight panting quality, same as the baking but simplified and faster by disregarding materials """

    from blend_converter.blender import Blender, bc_script
    from blend_converter.blender.formats.blend import open_mainfile, save_as_mainfile
    from blend_converter import common
    from blend_converter import utils

    blend_path = common.File(blend_path)

    asset_folder = os.path.join(configuration.Folder.INTERMEDIATE, 'SKIN_TEST_' + blend_path.dir_name )

    result_path = os.path.join(asset_folder, blend_path.dir_name)

    blender = Blender(configuration.BLENDER_EXECUTABLE)

    program = common.Program(
        blend_path = blend_path,
        result_path = result_path,
        blender_executable = blender.binary_path,
    )

    program._prog_type = 'SKIN_TEST 🧐'

    program.run(blender, open_mainfile, blend_path)

    objects = program.run(blender, scripts_bake.get_target_objects)

    program.run(blender, scripts_bake.reset_timeline)
    program.run(blender, scripts_bake.apply_modifiers, scripts_bake.Modifier_Type.POST_UNWRAP)
    program.run(blender, scripts_bake.apply_modifiers, scripts_bake.Modifier_Type.POST_BAKE)
    program.run(blender, bc_script.apply_scale, objects)
    program.run(blender, scripts_bake.join_objects)

    program.run(blender, save_as_mainfile, result_path)

    return program


def convert_to_blend_SKIN_PROXY(blend_path):
    """ a proxy to use in external tools like Mixamo and further re-integration, prioritizing a base clean topology """

    from blend_converter.blender import Blender
    from blend_converter.blender.formats.blend import open_mainfile
    from blend_converter.blender.formats.fbx import export_fbx, Settings_Fbx
    from blend_converter import common
    from blend_converter import utils

    blend_path = common.File(blend_path)

    asset_folder = os.path.join(configuration.Folder.BLEND_PROXY, blend_path.dir_name)

    result_path = os.path.join(asset_folder, blend_path.dir_name + '.fbx')

    blender = Blender(configuration.BLENDER_EXECUTABLE)

    program = common.Program(
        blend_path = blend_path,
        result_path = result_path,
        blender_executable = blender.binary_path,
    )

    program._prog_type = 'SKIN_PROXY 🤸‍♀️'

    program.run(blender, open_mainfile, blend_path)

    program.run(blender, scripts_export.convert_rig_proxy)

    program.run(blender, export_fbx, result_path, Settings_Fbx(bake_anim = False, object_types = {'MESH'}, use_mesh_modifiers = False, use_selection = True))

    return program


def get_programs():

    from blend_converter import utils
    programs = utils.Appendable_Dict()

    asset_folders = [file for file in os.scandir(configuration.Folder.BLEND_MAIN) if file.is_dir()]

    for folder in asset_folders:

        if folder.name.startswith('_'):  # temp or WIP assets to ignore
            continue

        if folder.name.startswith('SK_'):
            programs.append(convert_to_blend_SKIN_TEST(folder))
            programs.append(convert_to_blend_SKIN_PROXY(folder))

    return programs
