import sys
import os
import typing

from blend_converter import settings_base

if 'bpy' in sys.modules:
    import bpy
    from blend_converter.blender import bpy_utils
    from blend_converter import tool_settings
    from blend_converter.blender import bpy_context
    from blend_converter.blender import bpy_mesh
    from blend_converter.blender import bpy_modifier
    from blend_converter.blender import blend_inspector
    from blend_converter.blender import bpy_material


class S_Low_Poly(settings_base.Settings):


    target_triangles: int = 15000
    """
    Target amount of triangles in the low Poly mesh.

    #### Default: `15000`
    """


    cage_offset_ratio: float = 0.05
    """
    The cage expand ratio relative to the absolute size of the model.

    #### Default: `0.05`
    """


    voxel_count: int = 200
    """
    Resolution of the cage expand guiding mesh.

    #### Default: `200`
    """


    apply_smooth_by_angle: bool = True
    """
    Whether or not to apply Smooth By Angle to the low poly mesh.

    #### Default: `True`
    """


    sharp_degrees: float = 90 * 0.95
    """
    The degrees of Smooth By Angle if applied.

    #### Default: `90 * 0.95`
    """



def make_low_poly_and_cage(settings: S_Low_Poly):

    settings = S_Low_Poly()._update(settings)

    objects: typing.List[typing.Tuple[bpy.types.Object, bpy.types.Object, bpy.types.Object]] = []

    for high in bpy.context.scene.objects:

        if high.type != 'MESH':
            continue

        name = high.name

        high.name = name + '(high poly)'
        high.color = (1, 0, 0, 1)

        bpy_context.call_for_object(high, bpy.ops.object.shade_smooth, keep_sharp_edges = False)

        print(f"Creating low poly for: {name}")
        low = bpy_mesh.get_decimated_copy(high, target_triangles = settings.target_triangles)
        low.name = name + '(low poly)'


        if settings.apply_smooth_by_angle:
            bpy_modifier.apply_smooth_by_angle(low, settings.sharp_degrees)
            bpy_modifier.apply_weighted_normal(low, keep_sharp = True, mode = 'FACE_AREA_WITH_ANGLE')
        else:
            bpy_modifier.apply_weighted_normal(low)


        print(f"Creating cage for: {name}")
        cage = bpy_mesh.make_bake_cage(low, cage_offset_ratio = settings.cage_offset_ratio, voxel_count = settings.voxel_count)
        cage.name = name + '(cage)'

        objects.append((high, low, cage))

    return objects


def the_bake(
        objects: 'typing.List[typing.Tuple[bpy.types.Object, bpy.types.Object, bpy.types.Object]]',
        result_dir: str,
        width = 4096,
        height = 4096,
    ):

    from blend_converter.blender import bpy_bake
    from blend_converter.blender import bake_settings
    from blend_converter.blender import bpy_uv
    import os

    bake_types = [
        bake_settings.S_Normal_Native(use_remove_inward_normals=True),
        bake_settings.S_Base_Color(),
    ]

    uv_layer_name = bpy_utils.get_uuid1_hex()

    _settings = tool_settings.S_Bake(
        width = width,
        height = height,
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

        pack_settings = tool_settings.S_Pack_UVs(width = width, height = height, uv_layer_name=uv_layer_name)
        bpy_uv.pack([low], pack_settings)
        bpy_uv.ensure_pixel_per_island([low], pack_settings)

        bpy_material.convert_materials_to_principled([low])

        bpy.context.view_layer.objects.active = low

        images = bpy_bake.bake([high, low], settings)

        low.data.materials.clear()
        low.data.materials.append(bpy_material.create_material(low.name, uv_layer_name, images, k_map_identifier=settings._K_MAP_IDENTIFIER))


def delete_non_low_poly(objects: 'typing.List[typing.Tuple[bpy.types.Object, bpy.types.Object, bpy.types.Object]]'):

    for high, _, cage in objects:
        bpy.data.batch_remove([high, cage])


def convert_to_mesh():

    for object in bpy_utils.get_meshable_objects(bpy.context.scene.objects):
        bpy_utils.convert_to_mesh(object)
