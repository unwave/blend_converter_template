"""
Special scripts that are meant to solve issues in the test assets without keeping modified copies.
The issues are better to be solved in the original source blend files.
This is an effort to be less biased toward the source data.
But impractical to be generalized.
"""

import os
import sys
import typing



from blend_converter import common


if 'bpy' in sys.modules:
    import bpy
    from blend_converter.blender import bpy_utils
    from blend_converter.blender import bpy_node


ENABLED = os.path.exists(os.path.join(os.path.expanduser('~'), '.bc_template_custom_per_asset'))


def fix(blender, program: common.Program):

    if not ENABLED:
        return

    if os.path.basename(os.path.dirname(program.blend_path)).startswith('assetcoop_'):
        program.run(blender, set_color_attribute_materials)



def set_color_attribute_materials():
    """ This is so some test assets won't look boring. """


    def has_materials(object: bpy.types.Object):

        for slot in object.material_slots:

            if not slot.material:
                return False

            if not slot.material.node_tree:
                return False

            tree = bpy_node.Shader_Tree_Wrapper(slot.material.node_tree)

            if not tree.output:
                return False

            principled = tree.output['Surface']
            if not principled:
                return False

            if (
                    # the default material
                    principled.be('ShaderNodeBsdfPrincipled')
                    and
                    not principled.descendants
                    and
                    principled.inputs['Base Color'].is_close((0.8, 0.8, 0.8, 1))
                ):
                return False

            return True
        else:
            return False


    for object in bpy_utils.get_view_layer_objects():

        if object.type != 'MESH':
            continue

        color_attribute = next((a.name for a in object.data.color_attributes if a.name.lower().startswith('col')), None)
        if not color_attribute:
            continue

        if has_materials(object):
            continue

        object.data.materials.clear()

        material = bpy.data.materials.new('__bc_color_attribute')
        if bpy.app.version < (5, 0):
            material.use_nodes = True

        tree = bpy_node.Shader_Tree_Wrapper(material.node_tree)

        principled = tree.output['Surface']
        principled.inputs['Base Color'].new('ShaderNodeAttribute', attribute_name = color_attribute)
        principled.inputs['Roughness'].set_default_value(0.8)

        object.data.materials.append(material)
