import os
import sys

from .. import configuration

from ..scripts import bake as scripts_bake
from ..scripts import export as scripts_export
from ..scripts import panda3d_engine as scripts_panda3d



def get_program(
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

    program.label = 'P3D ANIMATION 👾'

    program.run(blender, bpy_data.open_mainfile, blend_path)

    program.run(blender, scripts_export.make_local)
    program.run(blender, scripts_bake.create_game_rig_and_bake_actions, scripts_bake.S_Deform_Armature())
    program.run(blender, scripts_export.delete_non_armature_objects)
    program.run(blender, scripts_export.rename_all_armatures)


    settings = scripts_panda3d.S_Gltf_2_Bam(skip_axis_conversion = True)

    program.run(blender, scripts_panda3d.export_gltf, gltf_path, scripts_panda3d.get_gltf_settings(), settings)

    program.run(python, scripts_panda3d.run_gltf2bam, gltf_path, bam_path, settings)


    return program


def get_anim_programs(source_root: str):

    from blend_converter import utils
    programs = utils.Appendable_Dict()

    for folder in configuration.get_folders(source_root):

        rig_name = os.path.basename(folder)

        for blend_file in configuration.get_blends(folder):

            animation_name = os.path.splitext(os.path.basename(blend_file))[0]

            programs.append(get_program(blend_file, rig_name, animation_name))


    return programs


def get_arguments(
            blender_executable: str,
            source_root: str,
            intermediate_root: str,
            result_root: str,
        ):

    from blend_converter import utils

    arguments = []

    asset_folders = configuration.get_folders(source_root)

    for folder in asset_folders:

        last_blend = utils.get_last_blend(folder)
        if not last_blend:
            continue

        arguments.append(dict(
            blender_executable = blender_executable,
            blend_path = last_blend,
            intermediate_root = intermediate_root,
            result_root = result_root,
        ))


    return arguments
