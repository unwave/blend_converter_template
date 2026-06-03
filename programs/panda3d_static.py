import os
import sys

from .. import configuration

from ..scripts import bake as scripts_bake
from ..scripts import export as scripts_export
from ..scripts import panda3d_engine as scripts_panda3d



def get_program(
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

    program.label = 'P3D STATIC 👾'

    program.run(blender, bpy_data.open_mainfile, blend_path)


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

    program.run(blender, scripts_panda3d.export_gltf, gltf_path, scripts_panda3d.get_gltf_settings(), settings)

    program.run(python, scripts_panda3d.run_gltf2bam, gltf_path, bam_path, settings)

    program.run(python, scripts_panda3d.convert_collision_placeholders, bam_path)
    program.run(python, scripts_panda3d.convert_curve_placeholders, bam_path)

    return program


def get_arguments(
            blender_executable: str,
            source_root: str,
            intermediate_root: str,
            result_root: str,
        ):


    arguments = []

    for folder in configuration.get_folders(source_root):

        blend_path = configuration.get_blend(folder)
        if not blend_path:
            continue

        arguments.append(dict(
            blender_executable = blender_executable,
            blend_path = blend_path,
            intermediate_root = intermediate_root,
            result_root = result_root,
        ))


    return arguments
