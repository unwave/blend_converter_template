""" Functions that are meant to be applied at the final stages, right before the expert. """

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


def is_using_uv_layer(node_tree: 'bpy.types.ShaderNodeTree', uv_layer_name: str):

    from blend_converter.blender import bpy_node

    tree = bpy_node.Shader_Tree_Wrapper(node_tree)

    for node in tree.output.descendants:
        if node.be('ShaderNodeUVMap') and uv_layer_name == node.uv_map:
            return True

    return False


def remove_unused_uv_layouts():
    """ https://godotforums.org/d/36084-blender-to-godot-import-uses-the-wrong-uv-map """

    from blend_converter.blender import bpy_utils

    for object in bpy_utils.get_unique_mesh_objects(bpy_utils.get_view_layer_objects()):

        if len(object.data.uv_layers) <= 1:
            continue

        for uv_layer_name in object.data.uv_layers.keys():

            for material_slot in object.material_slots:

                material = material_slot.material
                if not material:
                    continue

                if not material.node_tree:
                    continue

                if is_using_uv_layer(material.node_tree, uv_layer_name):
                    break
            else:
                object.data.uv_layers.remove(object.data.uv_layers[uv_layer_name])


def scene_clean_up():
    """ Cleaning up the scene from temporal and auxiliary objects before the expert. """

    for object in list(bpy.data.objects):
        if object.name.startswith(configuration.IGNORE_PREFIX):
            bpy.data.objects.remove(object)

    def traverse(layer_collection: bpy.types.LayerCollection):
        """ Recursively traverse and delete commented out objects and collections. """

        for layer in layer_collection.children:

            traverse(layer)

            if layer.collection.name.startswith(configuration.IGNORE_PREFIX):

                objects = set(o for o in layer.collection.objects if not o.get(configuration.COLLISION_IDENTIFIER_PROP_KEY))

                bpy.data.batch_remove(objects)

                if not layer.collection.objects and not any(c.objects for c in layer.collection.children_recursive):
                    bpy.data.collections.remove(layer.collection)

            elif layer.exclude:
                layer.exclude = False

    traverse(bpy.context.view_layer.layer_collection)

    bpy.ops.outliner.orphans_purge()


def make_local():

    bpy.ops.object.make_local(type='ALL')

def delete_non_armature_objects():
    """ This is used for animation only blend files. To export as only an armature and an action. """

    bpy.data.batch_remove([o for o in bpy.data.objects if o.type != 'ARMATURE'])

    bpy.ops.outliner.orphans_purge()


def remove_animations():

    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)

    for armature in [object for object in bpy.data.objects if object.type == 'ARMATURE']:

        for bone in armature.pose.bones:
            bone.location = (0, 0, 0)
            bone.rotation_quaternion = (1, 0, 0, 0)
            bone.rotation_axis_angle = (0, 0, 1, 0)
            bone.rotation_euler = (0, 0, 0)
            bone.scale = (1, 1, 1)

    for object in bpy.data.objects:
        object.animation_data_clear()


def export_collections_as_fbx_static_meshes(result_dir: str):

    from blend_converter.blender.formats.fbx import export_fbx, Settings_Fbx
    from blend_converter.blender import bpy_context
    from blend_converter import utils as bc_utils

    meshes_dir = os.path.join(result_dir, 'SM')
    os.makedirs(meshes_dir, exist_ok=True)

    for collection in bpy.context.scene.collection.children:

        all_objects = list(collection.all_objects)

        with bpy_context.Isolate_Focus(all_objects):

            bpy.ops.object.location_clear(clear_delta=False)

            settings = Settings_Fbx(
                use_active_collection = False,

                embed_textures = False,
                use_mesh_modifiers = False,
                mesh_smooth_type = 'OFF',

                global_scale = 0.01,
                axis_forward = '-Y',
                axis_up = 'Z',

                bake_anim = False,
            )

            base_name = bc_utils.ensure_valid_basename(collection.name).replace(' ', '_').replace('-', '_')

            model_path = os.path.join(meshes_dir, 'SM_' + base_name + '.fbx')

            bpy.context.scene.name = collection.name

            export_fbx(model_path, settings)


def triangulate_geometry(objects: typing.Optional[typing.List['bpy.types.Object']] = None):
    """ Clean up and triangulate mesh objects in order to resolve an issue with complex N-gons being broken after FBX export. """

    if objects is None:
        objects = bpy_utils.get_view_layer_objects()

    for object in bpy_utils.get_unique_mesh_objects(objects):

        # the box collision must not be triangulated, Otherwise Unreal Engine doesn't recognize it
        if object.get(configuration.UNREAL_COLLISION_PROP_KEY):
            continue

        if object.name.startswith('#'):
            continue

        if any(c.name.startswith('#') for c in object.users_collection):
            continue

        if object.get(configuration.ATOOL_COLLISION_OBJECT_PROP_KEY) is not None:
            continue

        with bpy_context.Focus(object):

            with bpy_context.Focus(object, mode = 'EDIT'):
                bpy.ops.mesh.reveal()
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.delete_loose()
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.dissolve_degenerate()

            modifier: bpy.types.TriangulateModifier = object.modifiers.new(name = 'triangulate_geometry', type='TRIANGULATE')
            modifier.quad_method = 'FIXED'  # says that this is the best for the keep normals
            modifier.keep_custom_normals = True
            bpy.ops.object.modifier_apply(modifier=modifier.name)


def get_top_layer_to_all_children_map():
    """ Get a dictionary of first level layer collections and all their child layer collections. """

    top_layer_to_children = {}

    for top_layer in bpy.context.view_layer.layer_collection.children:

        pool = list(top_layer.children)
        seen = set()
        children = []

        while pool:

            layer_collection = pool.pop()

            if layer_collection in seen:
                continue
            seen.add(layer_collection)

            children.append(layer_collection)
            pool.extend(layer_collection.children)

        top_layer_to_children[top_layer] = set(children)

    return top_layer_to_children


def convert_collision_shape(object: 'bpy.types.Object', collision_type: str):
    """
    Convert Atool collision shape into Unreal Engine recognizable collision shape.
    https://dev.epicgames.com/documentation/en-us/unreal-engine/fbx-static-mesh-pipeline-in-unreal-engine?application_version=5.5#collision
    """


    def get_dimensions(mesh: bpy.types.Mesh):
        vertices = mesh.vertices
        return dict(
            x = vertices[0].co[0] * 2,
            y = vertices[1].co[1] * 2,
            z = vertices[2].co[2] * 2,
            radius = max(vertices[0].co[0], vertices[1].co[1]),
            height = vertices[2].co[2] * 2,
        )


    def get_layer_collection(collection: bpy.types.Collection):

        pool = [bpy.context.view_layer.layer_collection]
        seen = set()

        while pool:

            layer_collection = pool.pop()
            if layer_collection.collection == collection:
                return layer_collection

            if layer_collection in seen:
                continue
            seen.add(layer_collection)

            pool.extend(layer_collection.children)


    def get_object_layer_collection(object: bpy.types.Object):
        for collection in object.users_collection:
            layer_collection = get_layer_collection(collection)
            if layer_collection:
                return object


    # find to which top layer collection object belongs to and set it active
    object_layer_collection = get_object_layer_collection(object)
    top_layer_to_children = get_top_layer_to_all_children_map()

    for top_layer, child_layers in top_layer_to_children.items():
        if object_layer_collection in child_layers:
            bpy.context.view_layer.active_layer_collection = top_layer
            break


    dimensions = get_dimensions(object.data)


    with bpy_context.Focus(object):
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)


    if collision_type == 'BOX':

        bpy.ops.mesh.primitive_cube_add()
        box = bpy.context.active_object

        box.location = object.location
        box.rotation_euler = object.rotation_euler
        box.scale = (dimensions['x']/2, dimensions['y']/2, dimensions['z']/2)

        box[configuration.COLLISION_IDENTIFIER_PROP_KEY] = collision_type
        box[configuration.UNREAL_COLLISION_PROP_KEY] = 'UBX'

        box.name = 'Box_Collision'
        box.display_type = 'WIRE'
        box.hide_render = True

        bpy.data.objects.remove(object)

    elif collision_type == 'SPHERE':

        bpy.ops.mesh.primitive_uv_sphere_add(radius=dimensions['radius'], location=object.location)

        sphere = bpy.context.active_object
        sphere.rotation_euler = object.rotation_euler

        sphere[configuration.COLLISION_IDENTIFIER_PROP_KEY] = collision_type
        sphere[configuration.UNREAL_COLLISION_PROP_KEY] = 'USP'

        sphere.name = 'Sphere_Collision'
        sphere.display_type = 'WIRE'
        sphere.hide_render = True

        bpy.data.objects.remove(object)

    elif collision_type == 'CAPSULE':

        disttance_from_center = dimensions['height']/2 - dimensions['radius']

        bpy.ops.mesh.primitive_uv_sphere_add(radius=dimensions['radius'], location=object.location)
        sphere1 = bpy.context.active_object
        sphere1.rotation_euler = object.rotation_euler
        bpy.ops.transform.translate(value=(0, 0, disttance_from_center), orient_type='LOCAL', orient_matrix_type='LOCAL')

        bpy.ops.mesh.primitive_uv_sphere_add(radius=dimensions['radius'], location=object.location)
        sphere2 = bpy.context.active_object
        sphere2.rotation_euler = object.rotation_euler
        bpy.ops.transform.translate(value=(0, 0, -disttance_from_center), orient_type='LOCAL', orient_matrix_type='LOCAL')

        capsule = bpy.data.objects.new('Capuse_Shape', bpy.data.meshes.new("Capuse_Shape"))

        capsule.location = object.location
        capsule.rotation_euler = object.rotation_euler

        bpy_utils.join_objects([sphere1, sphere2], join_into=capsule)

        bpy.context.view_layer.active_layer_collection.collection.objects.link(capsule)

        capsule[configuration.COLLISION_IDENTIFIER_PROP_KEY] = collision_type
        capsule[configuration.UNREAL_COLLISION_PROP_KEY] = 'UCP'

        capsule.name = 'Capsule_Collision'
        capsule.display_type = 'WIRE'
        capsule.hide_render = True

        bpy.data.objects.remove(object)

    elif collision_type == 'CONVEX_HULL':

        object = bpy_utils.convert_to_mesh(object)

        del object[configuration.ATOOL_COLLISION_OBJECT_PROP_KEY]

        object[configuration.COLLISION_IDENTIFIER_PROP_KEY] = collision_type
        object[configuration.UNREAL_COLLISION_PROP_KEY] = 'UCX'

        for collection in list(object.users_collection):
            collection.objects.unlink(object)

        bpy.context.view_layer.active_layer_collection.collection.objects.link(object)

        object.data.materials.clear()
        object.name = 'Convex_Collision'
        object.display_type = 'WIRE'
        object.hide_render = True

        with bpy_context.Focus(object):
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    else:

        raise Exception(f"Unexpected collision type '{collision_type}' for object: {object.name_full}")


def convert_all_collision_shapes():
    """ Convert all Atool collision shapes into Unreal Engine collision shapes. """

    collisions_count = 0

    for object in bpy_utils.get_view_layer_objects():

        collision_type = object.get(configuration.ATOOL_COLLISION_OBJECT_PROP_KEY)
        if collision_type:
            convert_collision_shape(object, collision_type)
            collisions_count += 1

    print(f"Custom collisions count: {collisions_count}")

    return bool(collisions_count)


def convert_collisions_to_convex():
    """
    Convert the Unreal Engine recognizable collision shapes into the convex type collision shapes to resolve the issue with non uniform scale.
    https://forums.unrealengine.com/t/box-collision-non-uniform-scale-issue/382743
    """

    for object in bpy_utils.get_view_layer_objects():

        if not object.get(configuration.UNREAL_COLLISION_PROP_KEY):
            continue

        if object.get(configuration.UNREAL_COLLISION_PROP_KEY) == 'CONVEX_HULL':
            continue

        object[configuration.COLLISION_IDENTIFIER_PROP_KEY] = 'CONVEX_HULL'
        object[configuration.UNREAL_COLLISION_PROP_KEY] = 'UCX'

        object = bpy_utils.convert_to_mesh(object)

        with bpy_context.Focus(object):
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

        with bpy_context.Focus(object,  mode='EDIT'):
            bpy.ops.mesh.reveal()
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.convex_hull()
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.quads_convert_to_tris(quad_method='BEAUTY', ngon_method='BEAUTY')


def rename_all_armatures():
    """
    Unreal Engine checks if the root bone name is "Armature" and does not created an extra root bone in this case.
    This is a special hack in the Unreal Engine FBX exporter just for Blender. 😽
    """

    for object in bpy_utils.get_view_layer_objects():

        if object.type != 'ARMATURE':
            continue

        object.name = 'Armature'


def save_blend_with_repack(filepath: str):

    if bpy.app.version >= (2, 80):
        bpy.context.preferences.use_preferences_save = False
        bpy.context.preferences.filepaths.save_version = 0
    else:
        bpy.context.user_preferences.filepaths.save_version = 0

    if bpy.data.filepath and os.path.exists(filepath) and os.path.samefile(filepath, bpy.data.filepath):
        raise Exception(f"Must not save the blend file in the same location: {filepath}")

    os.makedirs(os.path.dirname(filepath), exist_ok = True)

    bpy.ops.outliner.orphans_purge()
    try:
        bpy.ops.file.pack_all()
    except RuntimeError as e:
        print(e)

    try:
        bpy.ops.wm.save_as_mainfile(filepath=filepath, compress=True, copy=False)
    except RuntimeError as e:
        print(e)

    bpy.ops.file.unpack_all(method='WRITE_LOCAL')

    try:
        bpy.ops.wm.save_mainfile()
    except RuntimeError as e:
        print(e)

    print(f"Blend is saved in path: {filepath}")


def delete_unused_materials():

    for object in bpy.data.objects:

        if not hasattr(object, 'material_slots'):
            continue

        if not object.material_slots:
            continue

        with bpy_context.Focus(object):
            bpy.ops.object.material_slot_remove_unused()
