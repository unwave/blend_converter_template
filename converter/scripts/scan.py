import sys
import os


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


def make_low_poly_and_cage():

    high_poly = bpy_utils.get_view_layer_objects()[0]
    high_poly.name = 'HIGH'
    high_poly.color = (1, 0, 0, 1)

    bpy_context.call_for_object(high_poly, bpy.ops.object.shade_smooth, keep_sharp_edges = False)

    print()
    print('LOW POLY...')
    low_poly = bpy_mesh.get_decimated_copy(high_poly, target_triangles = blend_inspector.get_value('target_triangles', 15000))
    apply_weighted_smooth(low_poly, sharp=False)
    low_poly.name = 'LOW'

    print()
    print('CAGE...')
    bake_cage = bpy_mesh.make_bake_cage(low_poly, cage_offset = blend_inspector.get_value('cage_offset', 0.15))
    bake_cage.name = 'CAGE'


def apply_weighted_smooth(object: 'bpy.types.Object', sharp = True, sharp_degrees = 45):

    if sharp:
        bpy_modifier.apply_smooth_by_angle(object, sharp_degrees)
        bpy_modifier.apply_weighted_normal(object, keep_sharp = True, mode = 'FACE_AREA_WITH_ANGLE')
    else:
        bpy_context.call_for_object(object, bpy.ops.object.shade_smooth, keep_sharp_edges = False)
        bpy_modifier.apply_weighted_normal(object)


def the_bake(result_dir: str):

    from blend_converter.blender import bpy_bake
    from blend_converter.blender import bake_settings
    from blend_converter.blender import bpy_uv
    from blend_converter.blender import bc_script
    import os

    bake_types = [
        bake_settings.Normal_Native(use_remove_inward_normals=True),
        bake_settings.Base_Color(),
        [bake_settings.AO_Diffuse(), bake_settings.AOV(name='Inside_AO', is_color=False), bake_settings.AOV(name='Pointiness', is_color=False)]
    ]

    uv_layer_name = bc_script.get_uuid1_hex()

    max_ray_distance = max(bpy.data.objects['LOW'].evaluated_get(bpy.context.evaluated_depsgraph_get()).dimensions) * 1/3

    settings = tool_settings.Bake(
        resolution = 3000,
        image_dir = os.path.join(result_dir, 'textures'),
        bake_types = bake_types,
        use_selected_to_active=True,
        cage_object_name='CAGE',
        max_ray_distance = max_ray_distance,
        uv_layer_name = uv_layer_name,
    )

    bpy_uv.unwrap([bpy.data.objects['LOW']], uv_layer_name)

    bpy_uv.pack([bpy.data.objects['LOW']], tool_settings.Pack_UVs(uv_layer_name=uv_layer_name))

    bpy_utils.convert_materials_to_principled([bpy.data.objects['LOW']])

    bpy.context.view_layer.objects.active = bpy.data.objects['LOW']
    objects = [bpy.data.objects['HIGH'], bpy.data.objects['LOW']]

    bpy_bake.bake(objects, settings)
