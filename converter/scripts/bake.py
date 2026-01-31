""" Functions that are meant to convert the Blender data to an exportable format, with the result saved as an intermediate blend file. """

import os
import sys
import typing


ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if not ROOT in sys.path:
    sys.path.append(ROOT)

import configuration

from blend_converter import utils as bc_utils


if 'bpy' in sys.modules:
    import bpy
    from blend_converter import tool_settings
    from blend_converter.blender import bpy_utils
    from blend_converter.blender import bpy_context
    from blend_converter.blender import bpy_action



def get_bone_custom_shapes():

    shapes: typing.Set[bpy.types.Object] = set()

    for o in bpy.data.objects:

        if o.type != 'ARMATURE':
            continue

        for bone in o.pose.bones:
            if bone.custom_shape:
                shapes.add(bone.custom_shape)

    return shapes


def get_target_objects():


    objects: typing.List[bpy.types.Object] = []

    custom_shapes = get_bone_custom_shapes()


    for o in bpy_utils.get_meshable_objects(bpy_utils.get_view_layer_objects()):

        if o.name.startswith('#'):
            continue

        if any(c.name.startswith('#') for c in o.users_collection):
            continue

        if o.get(configuration.ATOOL_COLLISION_OBJECT_PROP_KEY) is not None:
            continue

        if o in custom_shapes:
            continue

        objects.append(o)

    return objects


def hid_non_target_objects():


    custom_shapes = get_bone_custom_shapes()
    for object in custom_shapes:
        object.hide_set(True)


    for object in bpy.data.objects:
        if object.name.startswith('#'):
            object.hide_set(True)


    def traverse(layer_collection: bpy.types.LayerCollection):

        for layer in layer_collection.children:

            if layer.name.startswith('#'):
                layer.hide_viewport = True

            traverse(layer)

    traverse(bpy.context.view_layer.layer_collection)



def find_missing():
    bpy.ops.file.find_missing_files(directory=os.path.dirname(bpy.data.filepath))


def reset_timeline():
    bpy.context.scene.frame_set(1)


def convert_empty_to_mesh(empty: 'bpy.types.Object'):

    # create object
    object = bpy.data.objects.new(empty.name, object_data=bpy.data.meshes.new(empty.name))

    for collection in empty.users_collection:
        collection.objects.link(object)

    depsgraph = bpy.context.evaluated_depsgraph_get()

    object.matrix_world = empty.evaluated_get(depsgraph).matrix_world

    # reparent to
    for other_object in bpy.data.objects:

        if other_object.parent != empty:
            continue

        with bpy_context.Focus([object, other_object]):
            bpy.context.view_layer.objects.active = object
            bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)

    bpy.data.objects.remove(empty)

    return object


def ensure_name(object: 'bpy.types.Object', name: str):


    existing_object = bpy.data.objects.get(name)
    if existing_object:
        existing_object.name += 'RENAMED'

    object.name = name

    assert object.name == name


    existing_mesh = bpy.data.meshes.get(name)
    if existing_mesh:
        existing_mesh.name += 'RENAMED'

    object.data.name = name

    assert object.data.name == name


def join_objects():
    """
    All mesh objects inside a collection will be joined into a single one, but if a collection starts with:

	`#`: collection and its content will be ignored

	`-`: join as if the all the objects of the collection would belong to the parent collection, use for organizational purposes

	`!`: direct child objects of the collection won't be joined
    """


    def traverse_passthrough_collection(layer_collection: bpy.types.LayerCollection):

        objects = []

        if not layer_collection.name.startswith('-'):
            return objects

        if layer_collection.name.startswith(configuration.IGNORE_PREFIX):
            return objects

        objects.extend(layer_collection.collection.objects)

        for child_layer in layer_collection.children:
            objects.extend(traverse_passthrough_collection(child_layer))

        return objects


    def traverse(layer_collection: bpy.types.LayerCollection):

        result = []

        if layer_collection.collection.name.startswith(configuration.IGNORE_PREFIX):
            return result

        objects = list(layer_collection.collection.objects)

        for child_layer in layer_collection.children:
            objects.extend(traverse_passthrough_collection(child_layer))

        meshable_objects = bpy_utils.get_meshable_objects(bc_utils.deduplicate(objects))


        if layer_collection.name.startswith('!'):
            result.extend(meshable_objects)
        elif meshable_objects:
            empty_origin = next((o for o in layer_collection.collection.objects if o.type == 'EMPTY' and o.name.startswith(configuration.ORIGIN_PREFIX)), None)

            armatures = []
            for object in meshable_objects:
                for modifier in reversed(object.modifiers):
                    if modifier.type == 'ARMATURE':
                        modifier.show_viewport = False
                        armatures.append(modifier.object)
                        break

            if armatures:
                assert len(set(armatures)) == 1
                armature = armatures[0]
            else:
                armature = None

            if empty_origin:
                origin = convert_empty_to_mesh(empty_origin)
                joined_object = bpy_utils.join_objects(meshable_objects, join_into=origin, name=layer_collection.name)
            else:
                joined_object = bpy_utils.join_objects(meshable_objects, name=layer_collection.name)

            if armature:
                joined_object.modifiers.new(name = 'Armature', type = 'ARMATURE').object = armature

            result.append(joined_object)

        for child_layer in layer_collection.children:

            if child_layer.name.startswith('-'):
                continue

            result.extend(traverse(child_layer))


        return result


    return traverse(bpy.context.view_layer.layer_collection)


class Modifier_Type:

    POST_UNWRAP = 'PU'
    POST_BAKE = 'PB'


def apply_modifiers(objects: typing.List['bpy.types.Object'], modifier_type_prefix: str = '', ignore_type = set()):
    if not modifier_type_prefix:
        pattern = '|'.join([Modifier_Type.POST_UNWRAP, Modifier_Type.POST_BAKE])
        bpy_utils.apply_modifiers(objects, ignore_name = pattern, ignore_type = ignore_type)
    else:
        bpy_utils.apply_modifiers(objects, include_name = modifier_type_prefix, ignore_type = ignore_type)


def delete_hidden_modifiers(objects: typing.List['bpy.types.Object']):

    for object in objects:
        for modifier in list(object.modifiers):
            if not modifier.show_viewport:
                object.modifiers.remove(modifier)


def convert_materials(objects):

    bpy_utils.convert_materials_to_principled(objects)
    bpy_utils.make_material_independent_from_object(objects)


def reveal_collections():
    """
    Recursively traverse and unhide collections according to the ignore prefix.

    `bpy_utils.get_view_layer_objects()` will include hidden objects, but not from disabled layers.
    Whether or not an object should be processed depends on the ignore prefix, not visibility in viewport.
    Because for the sake of export, whether a collection layer is hidden or disabled, it's the same.
    """

    def traverse(layer_collection: bpy.types.LayerCollection):

        for layer in layer_collection.children:

            layer.exclude = False
            layer.hide_viewport = False

            traverse(layer)

    traverse(bpy.context.view_layer.layer_collection)


def get_armature_objects():

    objects: typing.List[bpy.types.Object] = []

    for object in bpy_utils.get_view_layer_objects():

        if not object.visible_get():
            continue

        if object.type != 'ARMATURE':
            continue

        objects.append(object)

    return objects


def get_objects_for_armature(armature: 'bpy.types.Object'):

    objects: typing.List[bpy.types.Object] = []

    for object in bpy.data.objects:
        if armature is object.parent:
            objects.append(object)

    return objects


def create_game_rig_and_bake_actions():


    for armature in get_armature_objects():

        meshes = get_objects_for_armature(armature)

        # bpy_action.unassign_deform_bones_with_missing_weights(armature, meshes)

        deform_root = armature['BC_deform_root']
        control_root = armature['BC_control_root']

        new = bpy_action.create_simplified_armature_and_constrain(armature, deform_root, control_root, meshes)

        for collection in armature.users_collection:
            collection.objects.link(new)

        for action in bpy_utils.get_compatible_armature_actions([armature]):
            bpy_action.bake_single_action(armature, action, new)

        for mesh in meshes:

            if mesh.parent == armature:
                mesh.parent = new

            for modifier in mesh.modifiers:
                if isinstance(modifier, bpy.types.ArmatureModifier):
                    modifier.object = new

        bpy.data.objects.remove(armature)


def make_paths_relative():

    bpy.ops.file.make_paths_relative()


def apply_shape_keys(objects: typing.List['bpy.types.Object']):

    for object in objects:

        if not hasattr(object.data, 'shape_keys'):
            continue

        if not object.data.shape_keys:
            continue

        bpy_context.call_for_object(object, bpy.ops.object.shape_key_remove, all=True, apply_mix=True)


def delete_undefined_nodes():
    """
    This can stop the `Dependency cycle detected` spam in materials.

    `NTShader Nodetree/NTREE_OUTPUT() depends on`
    `MA<MATERIAL_NAME>/MATERIAL_UPDATE() via 'Material -> Node'`
    `NTShader Nodetree/NTREE_OUTPUT() via 'Material's NTree'`

    """

    from blend_converter.blender import bpy_node

    for material in bpy.data.materials:

        if not material.node_tree:
            continue

        tree = bpy_node.Shader_Tree_Wrapper(material.node_tree)
        tree.delete_nodes_with_reconnect(tree.get_by_bl_idname('NodeUndefined'))


def make_data_local():
    """ To be able to enter the EDIT mode. """

    if bpy.context.active_object:
        # RuntimeError: Operator bpy.ops.object.make_local.poll() failed, context is incorrect
        # if the object is in EDIT mode
        with bpy_context.Focus(bpy.context.active_object):
            bpy.ops.object.make_local(type='ALL')
    else:
        bpy.ops.object.make_local(type='ALL')


def set_legacy_ik_solver():
    """
    This can reduce `Dependency cycle detected` spam in rigs.

    Specifically the Tears of Steel Quad Bot rig prints millions of lines of spam.
    It costs hundreds of megabytes of RAM and the log file size.

    NOTE: this can undesirably change the result of the armature modifier
    """

    if bpy.data.version >= (2, 80):
        return

    state = bpy_context.State().__enter__()

    for object in bpy.data.objects:
        if object.type == 'ARMATURE':
            state.set(object.pose, 'ik_solver', 'LEGACY')

    return state
