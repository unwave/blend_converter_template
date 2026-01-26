import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if not ROOT in sys.path:
    sys.path.append(ROOT)


import configuration

from scripts import export as scripts_export


def get_rig(blend_path):
    """ for use a linked rig + mesh for creating animations """

    from blend_converter.blender.executor import Blender
    from blend_converter.blender import bc_script
    from blend_converter.blender.formats.blend import open_mainfile
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

    program.run(blender, scripts_export.remove_unused_uv_layouts)
    program.run(blender, bc_script.remove_all_node_groups_from_materials)
    program.run(blender, bc_script.use_backface_culling)

    program.run(blender, scripts_export.save_blend_with_repack, result_path)

    return program


def get_rig_kwargs():

    from blend_converter import utils

    arguments = []

    for folder in configuration.get_folders(configuration.Folder.INTERMEDIATE_BLEND_SKELETAL):

        last_blend = utils.get_last_blend(folder)
        if not last_blend:
            continue

        arguments.append(dict(blend_path = last_blend))


    return arguments
