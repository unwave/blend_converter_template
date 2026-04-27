import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if not ROOT in sys.path:
    sys.path.append(ROOT)


import configuration

from scripts import bake as scripts_bake
from scripts import export as scripts_export
from scripts import panda3d_engine as scripts_panda3d


def get_gltf_settings():

    from blend_converter.blender import bpy_export

    return bpy_export.S_GLTF(
        export_tangents = True,
        export_cameras = True,
        export_extras = True,
        export_yup = False,
        export_apply = True,
        export_force_sampling = True,
        export_lights = True,
    )


def convert_to_static_mesh(
            *,
            blender_executable: str,
            blend_path: str,
            intermediate_root: str,
            result_root: str,
        ):

    from blend_converter.blender.executor import Blender
    from blend_converter.python.executor import Python
    from blend_converter.blender import bpy_utils
    from blend_converter.blender import bpy_data
    from blend_converter import common


    blend_path: common.File = common.File(blend_path)

    # the paths should be on the same drive
    gltf_path = os.path.join(intermediate_root, blend_path.dir_name, blend_path.dir_name + '.gltf')
    bam_path = os.path.join(result_root, blend_path.dir_name, blend_path.dir_name + '.bam' )

    # prevents :express(warning): Filename is incorrect case: and writing extra .bam.pz if the file exists
    bam_path = os.path.realpath(bam_path)


    blender = Blender(blender_executable)
    python = Python(sys.executable)

    program = common.Program(
        blend_path = blend_path,
        result_path = bam_path,
        blender_executable = blender.binary_path,
        settings_path = os.path.join(blend_path.dir, 'bc_instructions.ini'),
    )

    program.tags.add('panda3d')

    program._prog_type = 'P3D STATIC 👾'

    program.run(blender, bpy_data.open_mainfile, blend_path)

    program.run(blender, scripts_bake.reveal_collections)

    program.run(blender, scripts_panda3d.assign_collision_placeholders)
    program.run(blender, scripts_panda3d.assign_curve_placeholders)

    program.run(blender, scripts_export.scene_clean_up)
    program.run(blender, scripts_export.delete_unused_materials)
    program.run(blender, scripts_export.remove_unused_uv_layouts)
    program.run(blender, bpy_utils.remove_all_node_groups_from_materials)
    program.run(blender, scripts_export.remove_animations)

    program.run(blender, bpy_utils.use_backface_culling)
    program.run(blender, scripts_export.triangulate_geometry, program.run(blender, scripts_bake.get_target_objects))


    settings = scripts_panda3d.S_Gltf_2_Bam(skip_axis_conversion = True)

    program.run(blender, scripts_panda3d.export_gltf, gltf_path, get_gltf_settings(), settings)

    program.run(python, scripts_panda3d.run_gltf2bam, gltf_path, bam_path, settings)

    program.run(python, scripts_panda3d.convert_collision_placeholders, bam_path)
    program.run(python, scripts_panda3d.convert_curve_placeholders, bam_path)

    return program


def convert_to_skeletal_mesh(
            blender_executable: str,
            blend_path: str,
            intermediate_root: str,
            result_root: str,
        ):

    from blend_converter.blender.executor import Blender
    from blend_converter.python.executor import Python
    from blend_converter.blender import bpy_utils
    from blend_converter.blender import bpy_data
    from blend_converter import common
    from blend_converter import utils


    blend_path: common.File = common.File(blend_path)

    # the paths should be on the same drive
    gltf_path = os.path.join(intermediate_root, blend_path.dir_name, blend_path.dir_name + '.gltf')
    bam_path = os.path.join(result_root, blend_path.dir_name, blend_path.dir_name + '.bam' )

    # prevents :express(warning): Filename is incorrect case: and writing extra .bam.pz if the file exists
    bam_path = os.path.realpath(bam_path)


    blender = Blender(blender_executable)
    python = Python(sys.executable)

    program = common.Program(
        blend_path = blend_path,
        result_path = gltf_path,
        blender_executable = blender.binary_path,
        settings_path = os.path.join(blend_path.dir, 'bc_instructions.ini'),
    )

    program.tags.add('panda3d')

    program._prog_type = 'P3D SKELETAL 👾'

    program.run(blender, bpy_data.open_mainfile, blend_path)

    program.run(blender, scripts_bake.reveal_collections)
    program.run(blender, scripts_export.scene_clean_up)
    program.run(blender, scripts_export.remove_unused_uv_layouts)
    program.run(blender, bpy_utils.remove_all_node_groups_from_materials)
    program.run(blender, scripts_export.remove_animations)
    program.run(blender, bpy_utils.use_backface_culling)
    program.run(blender, scripts_export.triangulate_geometry, program.run(blender, scripts_bake.get_target_objects))
    program.run(blender, scripts_export.delete_unused_materials)
    program.run(blender, scripts_bake.create_game_rig_and_bake_actions, False)
    program.run(blender, scripts_export.rename_all_armatures)

    settings = scripts_panda3d.S_Gltf_2_Bam(skip_axis_conversion = True)

    program.run(blender, scripts_panda3d.export_gltf, gltf_path, get_gltf_settings(), settings)

    program.run(python, scripts_panda3d.run_gltf2bam, gltf_path, bam_path, settings)

    return program


def convert_to_animation(
            blender_executable: str,
            blend_path,
            intermediate_root: str,
            result_root: str,
        ):


    from blend_converter.blender.executor import Blender
    from blend_converter.python.executor import Python
    from blend_converter.blender import bpy_data
    from blend_converter import common

    blend_path = common.File(blend_path)

    # the paths should be on the same drive
    gltf_path = os.path.join(intermediate_root, blend_path.dir_name, blend_path.dir_name + '.gltf')
    bam_path = os.path.join(result_root, blend_path.dir_name, blend_path.dir_name + '.bam' )

    # prevents :express(warning): Filename is incorrect case: and writing extra .bam.pz if the file exists
    bam_path = os.path.realpath(bam_path)


    blender = Blender(blender_executable)
    python = Python(sys.executable)

    program = common.Program(
        blend_path = blend_path,
        result_path = gltf_path,
        blender_executable = blender.binary_path,
        settings_path = os.path.join(blend_path.dir, 'bc_instructions.ini'),
    )

    program.tags.add('panda3d')

    program._prog_type = 'P3D ANIMATION 👾'

    program.run(blender, bpy_data.open_mainfile, blend_path)

    program.run(blender, scripts_export.make_local)
    program.run(blender, scripts_bake.create_game_rig_and_bake_actions)
    program.run(blender, scripts_export.delete_non_armature_objects)
    program.run(blender, scripts_export.rename_all_armatures)


    settings = scripts_panda3d.S_Gltf_2_Bam(skip_axis_conversion = True)

    program.run(blender, scripts_panda3d.export_gltf, gltf_path, get_gltf_settings(), settings)

    program.run(python, scripts_panda3d.run_gltf2bam, gltf_path, bam_path, settings)


    return program


def get_anim_programs(root = configuration.Folder.BLEND_ANIMATION):

    from blend_converter import utils
    programs = utils.Appendable_Dict()

    for folder in configuration.get_folders(root):

        rig_name = os.path.basename(folder)

        for blend_file in configuration.get_blends(folder):

            animation_name = os.path.splitext(os.path.basename(blend_file))[0]

            programs.append(convert_to_animation(blend_file, rig_name, animation_name))


    return programs


def get_panda3d_kwargs(
            blender_executable: str,
            main_root: str,
            root = configuration.Folder.INTERMEDIATE_BLEND_STATIC
        ):

    root = os.path.join(main_root, *root)

    from blend_converter import utils

    arguments = []

    asset_folders = configuration.get_folders(root)

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
                intermediate_root = os.path.join(main_root, *configuration.Folder.INTERMEDIATE_PANDA3D_STATIC),
                result_root = os.path.join(main_root, *configuration.Folder.PANDA3D_STATIC),
            ))


    return arguments
