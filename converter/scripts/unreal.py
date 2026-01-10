import os
import sys
import typing

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if not ROOT in sys.path:
    sys.path.append(ROOT)

import configuration


if 'bpy' in sys.modules:
    import bpy
    from blend_converter.blender import bpy_utils


def get_material_definitions_for_single_object():
    """ This is used to recreate the materials inside Unreal. """

    from blend_converter.blender import bpy_node

    object = bpy_utils.get_view_layer_objects()[0]

    material_definitions = []

    for material_slot in object.material_slots:

        assert material_slot.material
        assert material_slot.material.node_tree

        material_definition = {}
        material_definition['textures'] = textures = {}

        material = material_slot.material

        tree = bpy_node.Shader_Tree_Wrapper(material.node_tree)

        node = next((node for node in tree.output[0].inputs['Base Color'].descendants if node.be('ShaderNodeTexImage')), None)
        if node:
            textures['base_color'] = bpy_utils.get_block_abspath(node.image)
        else:
            textures['base_color'] = None

        node = next((node for node in tree.output[0].inputs['Metallic'].descendants if node.be('ShaderNodeTexImage')), None)
        if node:
            textures['orm'] = bpy_utils.get_block_abspath(node.image)
        else:
            textures['orm'] = None

        node = next((node for node in tree.output[0].inputs['Normal'].descendants if node.be('ShaderNodeTexImage')), None)
        if node:
            textures['normal'] = bpy_utils.get_block_abspath(node.image)
        else:
            textures['normal'] = None

        material_definitions.append(material_definition)

    return material_definitions
