import sys
import os
import typing


ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if not ROOT in sys.path:
    sys.path.append(ROOT)

import configuration


if 'bpy' in sys.modules:
    import bpy
    from blend_converter.blender import bpy_utils
    from blend_converter import tool_settings
    from blend_converter.blender import bpy_context
    from blend_converter.blender import bpy_mesh
    from blend_converter.blender import bpy_modifier
    from blend_converter.blender import blend_inspector


def make_low_poly_and_cage(target_triangles = 15000):

    objects: typing.List[typing.Tuple[bpy.types.Object, bpy.types.Object, bpy.types.Object]] = []

    for high in bpy_utils.get_view_layer_objects():

        if high.type != 'MESH':
            continue

        name = high.name

        high.name = name + '(high poly)'
        high.color = (1, 0, 0, 1)

        bpy_context.call_for_object(high, bpy.ops.object.shade_smooth, keep_sharp_edges = False)

        print(f"Creating low poly for: {name}")
        low = bpy_mesh.get_decimated_copy(high, target_triangles = target_triangles)
        apply_weighted_smooth(low, sharp=False)
        low.name = name + '(low poly)'

        print(f"Creating cage for: {name}")
        cage = bpy_mesh.make_bake_cage(low)
        cage.name = name + '(cage)'

        objects.append((high, low, cage))

    return objects


def apply_weighted_smooth(object: 'bpy.types.Object', sharp = True, sharp_degrees = 45):

    if sharp:
        bpy_modifier.apply_smooth_by_angle(object, sharp_degrees)
        bpy_modifier.apply_weighted_normal(object, keep_sharp = True, mode = 'FACE_AREA_WITH_ANGLE')
    else:
        bpy_context.call_for_object(object, bpy.ops.object.shade_smooth, keep_sharp_edges = False)
        bpy_modifier.apply_weighted_normal(object)


def the_bake(objects: 'typing.List[typing.Tuple[bpy.types.Object, bpy.types.Object, bpy.types.Object]]', result_dir: str):

    from blend_converter.blender import bpy_bake
    from blend_converter.blender import bake_settings
    from blend_converter.blender import bpy_uv
    from blend_converter.blender import bc_script
    import os

    bake_types = [
        bake_settings.Normal_Native(use_remove_inward_normals=True),
        bake_settings.Base_Color(),
    ]

    uv_layer_name = bc_script.get_uuid1_hex()

    _settings = tool_settings.Bake(
        resolution = 3000,
        image_dir = os.path.join(result_dir, 'textures'),
        bake_types = bake_types,
        use_selected_to_active=True,
        uv_layer_name = uv_layer_name,
    )

    for high, low, cage in objects:

        settings = _settings._get_copy()

        settings.max_ray_distance = max(low.evaluated_get(bpy.context.evaluated_depsgraph_get()).dimensions) * 1/3
        settings.cage_object_name = cage.name

        bpy_uv.unwrap([low], uv_layer_name)

        bpy_uv.pack([low], tool_settings.Pack_UVs(uv_layer_name=uv_layer_name))

        bpy_utils.convert_materials_to_principled([low])

        bpy.context.view_layer.objects.active = low

        bpy_bake.bake([high, low], settings)
