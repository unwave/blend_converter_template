import os


import configuration

import scripts_bake
import scripts_export


def convert_to_static_mesh(blend_path: str):
    """ export as a fbx static mesh """

    from blend_converter.blender import Blender, bc_script
    from blend_converter.blender.formats.blend import open_mainfile
    from blend_converter.blender.formats.gltf import export_gltf, Settings_GLTF
    from blend_converter import common


    blend_path: common.File = common.File(blend_path)

    gltf_path = os.path.join(configuration.Folder.GLTF_STATIC, blend_path.dir_name, blend_path.dir_name + '.gltf')

    blender = Blender(configuration.BLENDER_EXECUTABLE)

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
    program.run(blender, scripts_export.rename_objects_for_unreal, 'SM')
    program.run(blender, scripts_export.add_export_timestamp)

    program.run(blender, export_gltf, gltf_path, Settings_GLTF(export_format='GLTF_SEPARATE', export_keep_originals=True))

    program.run(blender, scripts_export.add_gd_import_script, gltf_path)

    return program


def convert_to_skeletal_mesh(blend_path: str):
    """ export as a fbx skeletal mesh """

    from blend_converter.blender import Blender, bc_script
    from blend_converter.blender.formats.blend import open_mainfile
    from blend_converter.blender.formats.gltf import export_gltf, Settings_GLTF
    from blend_converter import common
    from blend_converter import utils


    blend_path: common.File = common.File(blend_path)

    gltf_path = os.path.join(configuration.Folder.GLTF_SKELETAL, blend_path.dir_name, blend_path.dir_name + '.gltf')

    blender = Blender(configuration.BLENDER_EXECUTABLE)

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
    program.run(blender, scripts_bake.create_game_rig_and_bake_actions)
    program.run(blender, scripts_export.rename_objects_for_unreal, 'SK')
    program.run(blender, scripts_export.rename_all_armatures)
    program.run(blender, scripts_export.add_export_timestamp)

    program.run(blender, export_gltf, gltf_path, Settings_GLTF(export_format='GLTF_SEPARATE', export_keep_originals=True))

    program.run(blender, scripts_export.add_gd_import_script, gltf_path)

    return program


def convert_to_animation(blend_path, rig_name: str, animation_name: str):
    """ export as an animation only fbx file """

    from blend_converter.blender import Blender, bc_script
    from blend_converter.blender.formats.blend import open_mainfile
    from blend_converter.blender.formats.gltf import export_gltf, Settings_GLTF
    from blend_converter import common

    blend_path = common.File(blend_path)

    gltf_path = os.path.join(configuration.Folder.GLTF_ANIMATION, blend_path.dir_name, blend_path.dir_name + '.gltf')

    blender = Blender(configuration.BLENDER_EXECUTABLE)

    program = common.Program(
        blend_path = blend_path,
        result_path = gltf_path,
        blender_executable = blender.binary_path,
    )

    program.tags.add('gltf')

    program._prog_type = 'ANIMATION 👾'

    program.run(blender, open_mainfile, blend_path)

    program.run(blender, scripts_export.rename_objects_for_unreal, 'SK')
    program.run(blender, scripts_export.make_local_and_delete_non_armature_objects)
    program.run(blender, scripts_export.add_export_timestamp)
    program.run(blender, scripts_bake.create_game_rig_and_bake_actions)
    program.run(blender, scripts_export.rename_all_armatures)

    program.run(blender, export_gltf, gltf_path, Settings_GLTF(export_format='GLTF_SEPARATE', export_keep_originals=True))

    program.run(blender, scripts_export.add_gd_import_script, gltf_path)

    return program


def get_anim_programs():

    from blend_converter import utils
    programs = utils.Appendable_Dict()

    for folder in configuration.get_folders(configuration.Folder.BLEND_ANIM):

        rig_name = os.path.basename(folder)

        for blend_file in configuration.get_blends(folder):

            animation_name = os.path.splitext(os.path.basename(blend_file))[0]

            programs.append(convert_to_animation(blend_file, rig_name, animation_name))


    return programs


def get_programs():

    from blend_converter import utils
    programs = utils.Appendable_Dict()

    asset_folders = [file for file in os.scandir(configuration.Folder.INTERMEDIATE) if file.is_dir()]

    for folder in asset_folders:

        last_blend = utils.get_last_blend(folder)
        if not last_blend:
            continue

        if folder.name.startswith('SK_'):
            programs.append(convert_to_skeletal_mesh(last_blend))
        elif folder.name.startswith('GROUP_SM_'):
            # split into multiple fbx with shared materials
            pass
            # programs.append(convert_to_fbx_GROUP_SM(baked_model.result_path))
        elif folder.name.startswith('SM_'):
            programs.append(convert_to_static_mesh(last_blend))
        else:
            import warnings
            warnings.warn(f"Unexpected folder prefix: {folder.name}")


    return programs
