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
    from blend_converter.blender import bpy_context


def convert_rig_proxy():
    """
    This is used to create a proxy mesh, which is used to create armatures and distribute weights in 3rd party applications to import back into Blender.
    The target objects should have a `rig_proxy` custom property set to a truthy value.
    """

    objects = [object for object in bpy_utils.get_view_layer_objects() if object.get('rig_proxy')]

    bpy_context.Focus(objects).__enter__()

    for object in objects:
        if object.data.shape_keys:
            for key_block in reversed(object.data.shape_keys.key_blocks):
                object.shape_key_remove(key_block)

    bpy_utils.apply_modifiers(objects, include_name='.+rig_proxy')

    for object in objects:
        object.animation_data_clear()
        object.modifiers.clear()
        object.vertex_groups.clear()
        object.data.materials.clear()

        for color_attribute in list(object.data.color_attributes):
            if color_attribute.is_internal or color_attribute.is_required:
                continue
            object.data.color_attributes.remove(color_attribute)


    bpy_utils.make_object_data_unique(objects)

    bpy.ops.object.transform_apply(location = True, rotation = True, scale = True)

    bpy.data.batch_remove(set(bpy.data.objects) - set(objects))
