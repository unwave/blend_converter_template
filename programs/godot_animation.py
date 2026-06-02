import os



from .. import configuration

from ..scripts import bake as scripts_bake
from ..scripts import export as scripts_export
from ..scripts import godot as scripts_godot


def get_program(
            blender_executable: str,
            blend_path,
            rig_name: str,
            animation_name: str,
            result_root: str,
        ):


    from blend_converter.blender.executor import Blender
    from blend_converter.blender import bpy_data
    from blend_converter.blender import bpy_export
    from blend_converter import common

    blend_path = common.File(blend_path)

    rig_name = configuration.get_ascii_underscored(rig_name)
    animation_name = configuration.get_ascii_underscored(animation_name)

    gltf_path = os.path.join(result_root, rig_name, animation_name + '.gltf')

    blender = Blender(blender_executable)

    program = common.Program(
        blend_path = blend_path,
        result_path = gltf_path,
        blender_executable = blender.binary_path,
        settings_path = os.path.join(blend_path.dir, 'bc_instructions.ini'),
    )

    program.tags.add('godot')

    program.label = 'GODOT ANIMATION 👾'

    program.run(blender, bpy_data.open_mainfile, blend_path)

    program.run(blender, scripts_godot.rename_objects_for_godot, 'SK')
    program.run(blender, scripts_export.make_local)
    program.run(blender, scripts_godot.add_export_timestamp)
    program.run(blender, scripts_bake.create_game_rig_and_bake_actions, scripts_bake.S_Deform_Armature())
    program.run(blender, scripts_export.delete_non_armature_objects)
    program.run(blender, scripts_export.rename_all_armatures)

    program.run(blender, bpy_export.export_gltf, gltf_path, bpy_export.S_GLTF(export_format='GLTF_SEPARATE', use_visible = True))

    program.run(blender, scripts_godot.set_gd_import_script, gltf_path, '', is_instruction_enabled = False)

    return program


def get_arguments(
            blender_executable: str,
            source_root: str,
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
                rig_name = rig_name,
                animation_name = animation_name,
                result_root = result_root,
            ))


    return arguments
