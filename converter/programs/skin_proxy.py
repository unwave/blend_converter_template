import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if not ROOT in sys.path:
    sys.path.append(ROOT)


import configuration

from scripts import export as scripts_export
from scripts import rig as scripts_rig


def get_skin_proxy(blend_path):
    """ a proxy to use in external tools like Mixamo and further re-integration, prioritizing a base clean topology """

    from blend_converter.blender import Blender
    from blend_converter.blender.formats.blend import open_mainfile
    from blend_converter.blender.formats.fbx import export_fbx, Settings_Fbx
    from blend_converter import common
    from blend_converter import utils

    blend_path = common.File(blend_path)

    asset_folder = os.path.join(configuration.Folder.INTERMEDIATE_BLEND_SKIN_PROXY, blend_path.dir_name)

    result_path = os.path.join(asset_folder, blend_path.dir_name + '.fbx')

    blender = Blender(configuration.BLENDER_EXECUTABLE)

    program = common.Program(
        blend_path = blend_path,
        result_path = result_path,
        blender_executable = blender.binary_path,
    )

    program._prog_type = 'SKIN PROXY 🤸'

    program.run(blender, open_mainfile, blend_path)

    program.run(blender, scripts_rig.convert_rig_proxy)
    program.run(blender, scripts_export.scene_clean_up)

    program.run(blender, export_fbx, result_path, Settings_Fbx(bake_anim = False, object_types = {'MESH'}, use_mesh_modifiers = False, use_selection = True))

    return program


def get_skin_proxy_kwargs():

    from blend_converter import utils

    arguments = []

    asset_folders = [file for file in os.scandir(configuration.Folder.BLEND_SKELETAL) if file.is_dir()]

    for folder in asset_folders:

        if folder.name.startswith('_'):  # temp or WIP assets to ignore
            continue

        last_blend = utils.get_last_blend(folder)
        if not last_blend:
            continue

        arguments.append(dict(blend_path = last_blend))

    return arguments
