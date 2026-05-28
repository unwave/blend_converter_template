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
            rig_name: str,
            animation_name: str,
            result_root: str,
        ):


    from blend_converter.blender.executor import Blender
    from blend_converter.python.executor import Python
    from blend_converter.blender import bpy_data
    from blend_converter import common

    blend_path = common.File(blend_path)

    # the paths should be on the same drive
    gltf_path = os.path.join(intermediate_root, rig_name, animation_name + '.gltf')
    bam_path = os.path.join(result_root, rig_name, animation_name + '.bam' )

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


def get_arguments(
            blender_executable: str,
            source_root: str,
            intermediate_root: str,
            result_root: str,
        ):


    arguments = []

    for rig_folder in configuration.get_folders(source_root):

        rig_name = os.path.basename(rig_folder)

        for anim_folder in configuration.get_folders(rig_folder):

            animation_name = os.path.basename(anim_folder)

            blend_path = configuration.get_blend(anim_folder)
            if not blend_path:
                continue

            arguments.append(dict(
                blender_executable = blender_executable,
                blend_path = blend_path,
                intermediate_root = intermediate_root,
                rig_name = rig_name,
                animation_name = animation_name,
                result_root = result_root,
            ))


    return arguments
