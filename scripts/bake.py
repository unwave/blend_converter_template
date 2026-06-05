""" Functions that are meant to convert the Blender data to an exportable format, with the result saved as an intermediate blend file. """

import os
import sys
import typing
import uuid


from .. import configuration

from blend_converter import utils as bc_utils
from blend_converter import settings_base


if 'bpy' in sys.modules:
    import bpy
    from blend_converter import tool_settings
    from blend_converter.blender import bpy_utils
    from blend_converter.blender import bpy_context
    from blend_converter.blender import bpy_action
    from blend_converter.blender import bpy_material
    from blend_converter.blender import bpy_modifier


if typing.TYPE_CHECKING:
    import dataclasses
else:
    class dataclasses:
        dataclass = lambda x: x


@dataclasses.dataclass
class S_Target_Objects(settings_base.Settings):


    only_meshable: bool = True
    """
    If True — only the objects that can be converted to mesh are considered.

    #### Default: `True`
    """


    only_visible: bool = True
    """
    If True — only the visible objects are considered.

    #### Default: `True`
    """


    exclude_hashtag: bool = True
    """
    Exclude objects that have their names or any collection's name, they are inside, starting with `#`.

    #### Default: `True`
    """


    exclude_custom_shape: bool = True
    """
    Exclude objects that are used as custom shapes for bones.

    #### Default: `True`
    """


    exclude_property_name: list = [configuration.ATOOL_COLLISION_OBJECT_PROP_KEY, configuration.UNREAL_COLLISION_PROP_KEY]
    """
    Exclude objects that have any custom property matching any name in the list.

    #### Default: `[configuration.ATOOL_COLLISION_OBJECT_PROP_KEY, configuration.UNREAL_COLLISION_PROP_KEY]`
    """


    exclude_mesh_deform: bool = True
    """
    Exclude objects that are used as deformers for Mesh Deform modifiers.

    #### Default: `True`
    """


    exclude_no_polygons: bool = True
    """
    Exclude objects that will not have polygons.

    #### Default: `True`
    """


    exclude_displayed_as_wire: bool = True
    """
    Exclude objects that are displayed as `Wire`.

    #### Default: `True`
    """


    exclude_displayed_as_bounds: bool = True
    """
    Exclude objects that are displayed as `Bounds`.

    #### Default: `True`
    """


def get_bone_custom_shapes():

    shapes: typing.Set[bpy.types.Object] = set()

    for o in bpy.data.objects:

        if o.type != 'ARMATURE':
            continue

        for bone in o.pose.bones:
            if bone.custom_shape:
                shapes.add(bone.custom_shape)

    return shapes


def get_mesh_deformers():

    result: typing.Set[bpy.types.Object] = set()

    for o in bpy.data.objects:
        for modifier in o.modifiers:
            if modifier.type == 'MESH_DEFORM' and modifier.object:
                result.add(modifier.object)

    return result


def will_have_polygons(object: 'bpy.types.Object', depsgraph: 'bpy.types.Depsgraph'):

    evaluated = object.evaluated_get(depsgraph)
    has_polygons = bool(evaluated.to_mesh().polygons)
    evaluated.to_mesh_clear()

    return has_polygons


def get_target_objects(settings: S_Target_Objects = None):

    settings = S_Target_Objects()._update(settings)


    all_objects = bpy.context.scene.objects

    result: typing.List[bpy.types.Object] = []


    custom_shapes = get_bone_custom_shapes()
    mesh_deformers = get_mesh_deformers()
    SENTINEL = object()
    depsgraph = bpy.context.evaluated_depsgraph_get()

    meshable_objects = set(bpy_utils.get_meshable_objects(all_objects))


    for o in all_objects:


        if settings.only_meshable:

            if not o in meshable_objects:
                continue


        if settings.only_visible:

            if not o.visible_get():
                continue


        if settings.exclude_hashtag:

            if o.name.strip().startswith('#'):
                continue

            if any(c.name.strip().startswith('#') for c in o.users_collection):
                continue


        if any(o.get(name, SENTINEL) is not SENTINEL for name in settings.exclude_property_name):
            continue


        if settings.exclude_custom_shape:

            if o in custom_shapes:
                continue


        if settings.exclude_mesh_deform:

            if o in mesh_deformers:
                continue


        if settings.exclude_no_polygons:

            if o in meshable_objects:

                if not will_have_polygons(o, depsgraph):
                    continue


        if settings.exclude_displayed_as_wire:

            if o.display_type == 'WIRE':
                continue


        if settings.exclude_displayed_as_bounds:

            if o.display_type == 'BOUNDS':
                continue


        result.append(o)


    return result


def hide_other_objects(objects: typing.List['bpy.types.Object']):


    visible_objects = set(objects)

    for object in objects:
        armature = object.find_armature()
        if armature:
            visible_objects.add(armature)


    for object in bpy.context.scene.objects:

        if object not in visible_objects:
            if object.visible_get():
                object.hide_set(True)


def reveal_objects(collection_name: str, objects: typing.List['bpy.types.Object']):

    focus = bpy_context.Focus(objects).__enter__()
    focus.visible_collection.name = collection_name
    focus.references.__exit__(None, None, None)


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


def join_objects(objects: typing.List['bpy.types.Object']):
    """
    All mesh objects inside a collection will be joined into a single one, but if a collection starts with:

    `#`: collection and its content will be ignored

    `-`: join as if the all the objects of the collection would belong to the parent collection, use for organizational purposes

    `!`: direct child objects of the collection won't be joined
    """


    def traverse_passthrough_collection(layer_collection: bpy.types.LayerCollection):

        objects: typing.List[bpy.types.Object] = []

        if not layer_collection.name.startswith('-'):
            return objects

        if layer_collection.name.startswith(configuration.IGNORE_PREFIX):
            return objects

        objects.extend(layer_collection.collection.objects)

        for child_layer in layer_collection.children:
            objects.extend(traverse_passthrough_collection(child_layer))

        return objects


    def get_target_objects(layer_collection: bpy.types.LayerCollection):

        result: typing.List[bpy.types.Object] = []

        result.extend(layer_collection.collection.objects)

        for child_layer in layer_collection.children:
            result.extend(traverse_passthrough_collection(child_layer))

        result = [o for o in result if o in objects]

        return bc_utils.deduplicate(result)


    def traverse(layer_collection: bpy.types.LayerCollection):

        result = []

        if layer_collection.collection.name.startswith(configuration.IGNORE_PREFIX):
            return result

        target_objects = get_target_objects(layer_collection)

        if layer_collection.name.startswith('!'):
            result.extend(target_objects)
        elif target_objects:
            empty_origin = next((o for o in layer_collection.collection.objects if o.type == 'EMPTY' and o.name.startswith(configuration.ORIGIN_PREFIX)), None)

            if empty_origin:
                origin = convert_empty_to_mesh(empty_origin)
                joined_object = bpy_utils.join_objects(target_objects, join_into=origin, name=layer_collection.name)
            else:
                joined_object = bpy_utils.join_objects(target_objects, name=layer_collection.name)

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


def get_modelling_modifiers(object: 'bpy.types.Object'):

    result = []

    for modifier in list(object.modifiers):

        if modifier.name.startswith(Modifier_Type.POST_UNWRAP):
            continue

        if modifier.name.startswith(Modifier_Type.POST_BAKE):
            continue

        result.append(modifier.name)

    return result


def get_post_unwrap_modifiers(object: 'bpy.types.Object'):

    result = []

    for modifier in list(object.modifiers):

        if not modifier.name.startswith(Modifier_Type.POST_UNWRAP):
            continue

        result.append(modifier.name)

    return result


def get_post_bake_modifiers(object: 'bpy.types.Object'):

    result = []

    for modifier in list(object.modifiers):

        if not modifier.name.startswith(Modifier_Type.POST_BAKE):
            continue

        result.append(modifier.name)

    return result


def get_armature_modifier(object: 'bpy.types.Object'):

    for modifier in reversed(object.modifiers):
        if modifier.type == 'ARMATURE':
            return modifier.name


def _apply_modifiers(filter_func: typing.Callable, objects: typing.List['bpy.types.Object'], preserve_armature: bool):

    with bpy_context.Focus(objects):

        for object in objects:

            modifiers_to_apply = filter_func(object)
            if not modifiers_to_apply:
                continue

            if preserve_armature:
                armature_modifier = get_armature_modifier(object)
                if armature_modifier in modifiers_to_apply:
                    modifiers_to_apply.remove(armature_modifier)

            for name in modifiers_to_apply:
                bpy_modifier.apply_modifier(object.modifiers[name])


def apply_modeling_modifiers(objects: typing.List['bpy.types.Object'], preserve_armature = False):
    _apply_modifiers(get_modelling_modifiers, objects, preserve_armature)


def apply_post_unwrap_modifiers(objects: typing.List['bpy.types.Object'], preserve_armature = False):
    _apply_modifiers(get_post_unwrap_modifiers, objects, preserve_armature)


def apply_post_bake_modifiers(objects: typing.List['bpy.types.Object'], preserve_armature = False):
    _apply_modifiers(get_post_bake_modifiers, objects, preserve_armature)


def delete_hidden_modifiers(objects: typing.List['bpy.types.Object']):

    for object in objects:
        for modifier in list(object.modifiers):
            if not modifier.show_viewport:
                object.modifiers.remove(modifier)


def get_armature_objects():

    objects: typing.List[bpy.types.Object] = []

    for object in bpy.context.scene.objects:

        if not object.visible_get():
            continue

        if object.type != 'ARMATURE':
            continue

        objects.append(object)

    return objects


def get_objects_for_armature(armature: 'bpy.types.Object'):

    objects: typing.List[bpy.types.Object] = []

    for object in bpy.data.objects:

        if object.type != 'MESH':
            continue

        if armature is object.parent or any(m.type == 'ARMATURE' and m.object is armature for m in object.modifiers):
            objects.append(object)

    return objects


class S_Deform_Armature(settings_base.Settings):


    deform_root_bone: str = ''
    """
    The name of the deformed root bone.

    The bone also must have `use_deform = True`.

    #### Default: `''`
    """


    control_root_bone: str = ''
    """
    The name of the control root bone.
    Used for the root motion in game engines.

    #### Default: `''`
    """


    k_deform_root: str = '__bc_deform_root'
    """
    Another way to define the deformed root bone.

    Assign a custom property of any type with the name to a single Edit bone to mark the deform root bone.

    #### Default: `'__bc_deform_root'`
    """


    k_control_root: str = '__bc_control_root'
    """
    Another way to define the control root bone.

    Assign a custom property of any type with the name to a single Edit bone to mark the control root bone."

    #### Default: `'__bc_control_root'`
    """


def get_root_bones(armature: 'bpy.types.Object', settings: S_Deform_Armature):

    sentinel = object()

    deform_root = armature.data.bones.get(settings.deform_root_bone)

    if deform_root and not deform_root.use_deform:
        print(
            f"The deform root bone specified is not used as such."
            "\n\t" f"Armature: {armature.name_full}"
            "\n\t" f"Bone: {settings.deform_root_bone}"
        )
        deform_root = None

    if settings.deform_root_bone and not deform_root:
        print(
            f"The deform root bone specified was not found."
            "\n\t" f"Armature: {armature.name_full}"
            "\n\t" f"Bone: {settings.deform_root_bone}"
        )

    if not deform_root:

        roots = [b for b in armature.data.bones if b.get(settings.k_deform_root, sentinel) is not sentinel]
        if len(roots) > 1:
            raise Exception(
                f"Multiple deform roots."
                "\n\t" f"Armature: {armature.name_full}"
                "\n\t" f"Bones: {roots}"
            )
        elif not roots:
            deform_root = None
        else:
            deform_root = roots[0]


    control_root = armature.data.bones.get(settings.control_root_bone)

    if control_root and control_root.use_deform:
        print(
            f"The control root bone specified must not be deform."
            "\n\t" f"Armature: {armature.name_full}"
            "\n\t" f"Bone: {settings.control_root_bone}"
        )
        control_root = None

    if settings.control_root_bone and not control_root:
        print(
                f"The control root bone specified was not found."
                "\n\t" f"Armature: {armature.name_full}"
                "\n\t" f"Bone: {settings.control_root_bone}"
            )

    if not control_root:

        roots = [b for b in armature.data.bones if b.get(settings.k_control_root, sentinel) is not sentinel]
        if len(roots) > 1:
            raise Exception(
                f"Multiple control roots."
                "\n\t" f"Armature: {armature.name_full}"
                "\n\t" f"Bones: {roots}"
            )
        elif not roots:
            control_root = None
        else:
            control_root = roots[0]


    if deform_root and control_root:
        return deform_root.name, control_root.name


    names = set(b.name for b in armature.data.bones)

    if (
            'Hips' in names
            and
            'Ctrl_Master' in names
            and
            armature.data.bones['Hips'].parent is None
            and
            armature.data.bones['Ctrl_Master'].parent is None
        ):

        print(f"Mixamo rig detected: {armature.name_full}")
        return 'Hips', 'Ctrl_Master'


    if deform_root:
        deform_root_message = f"Deform root: {deform_root.name}"
    else:
        deform_root_message = f"Assign a custom property of any type with name '{settings.k_deform_root}' to a single Edit bone to mark the deform root bone."

    if control_root:
        control_root_message = f"Deform root: {control_root.name}"
    else:
        control_root_message = f"Assign a custom property of any type with name '{settings.k_control_root}' to a single Edit bone to mark the control root bone."

    bc_utils.print_in_color(bc_utils.get_color_code(224, 51, 29, 10, 10, 10),
        f"Fail to find specified deform or control root bones in the control armature."
        "\n\t" f"Armature: '{armature.name_full}'"
        "\n\t" f"{deform_root_message}"
        "\n\t" f"{control_root_message}"
    )


    if not deform_root:
        deform_root_name = bpy_action.find_deform_root(armature)

    if not control_root:
        control_root_name = ''

    print("Deform root bone:", deform_root_name)
    print("Control root bone:", control_root_name)
    return deform_root_name, control_root_name



def unassign_deform_bones_with_missing_weights():

    for armature in get_armature_objects():
        meshes = get_objects_for_armature(armature)
        bpy_action.unassign_deform_bones_with_missing_weights(armature, meshes)


def add_copy_uniform_scale(bone: 'bpy.types.PoseBone', target: 'bpy.types.Object', subtarget: str):

    constraint: bpy.types.CopyScaleConstraint = bone.constraints.new('COPY_SCALE')
    constraint.target = target
    constraint.subtarget = subtarget

    constraint.use_make_uniform = True



def bake_animation(
        armatures: typing.List['bpy.types.Object'],
        frame_start: typing.Optional[int] = None,
        frame_end: typing.Optional[int] = None,
        step = 1,
        do_reset_pose_to_rest = False,
        settings: 'bpy_action.S_Action_Bake' = None
    ):


    with bpy_context.Focus(armatures):

        if do_reset_pose_to_rest:
            for object in armatures:
                bpy_action.reset_pose_to_rest(object)

        for object in armatures:
            if not object.animation_data:
                object.animation_data_create()


        if frame_start is None:
            frame_start = bpy.context.scene.frame_start

        if frame_end is None:
            frame_end = bpy.context.scene.frame_end


        settings = bpy_action.S_Action_Bake()._update(settings)
        for key in [key for key in bpy_action.S_Action_Bake.__dict__ if not key.startswith('_')]:
            setattr(settings, key, getattr(settings, key))


        from bpy_extras import anim_utils

        return anim_utils.bake_action_objects(
            [(a, None) for a in armatures],
            frames = range(frame_start, frame_end + 1, step),
            bake_options = anim_utils.BakeOptions(**settings)
        )[0]


def create_game_rig_and_bake_actions(settings: S_Deform_Armature, do_bake_animation = True):

    settings = S_Deform_Armature()._update(settings)

    baked_actions = []

    for armature in get_armature_objects():

        meshes = get_objects_for_armature(armature)


        with bpy_context.Focus(armature), bpy_context.State() as state:

            state.set(armature.data, 'pose_position','REST')
            armature.update_tag()
            bpy.context.view_layer.update()

            deform_root, control_root = get_root_bones(armature, settings)


        if not deform_root:
            continue

        new = bpy_action.create_simplified_armature_and_constrain(armature, deform_root, control_root, meshes)

        with bpy_context.Focus(new, 'POSE'):
            for pose_bone in new.pose.bones:
                copy_transform = pose_bone.constraints[0]
                add_copy_uniform_scale(pose_bone, copy_transform.target, copy_transform.subtarget)

        for collection in armature.users_collection:
            collection.objects.link(new)

        if not bpy_utils.get_compatible_armature_actions([armature]):
            print(f"No compatible animations found for the source armature: {armature.name_full}")

        if do_bake_animation:
            baked_actions.append(bake_animation([new]))


        with bpy_context.Focus(meshes + [new]):
            bpy.context.view_layer.objects.active = new
            bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)

        for mesh in meshes:
            for modifier in mesh.modifiers:
                if isinstance(modifier, bpy.types.ArmatureModifier):
                    if modifier.object == armature:
                        modifier.object = new

        bpy.data.objects.remove(armature)

    bpy.data.batch_remove([a for a in bpy.data.actions if not a in baked_actions])


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


def convert_to_mesh_non_mesh_objects(objects: typing.List['bpy.types.Object']):

    mesh_objects = []

    for object in objects:

        if object.type == 'MESH':
            mesh_objects.append(object)
        else:
            mesh_objects.append(bpy_utils.convert_to_mesh(object))

    return mesh_objects


def apply_particle_systems(objects: typing.List['bpy.types.Object']):

    for object in objects:

        for modifier in object.modifiers:

            if modifier.type != 'PARTICLE_SYSTEM':
                continue

            with bpy_context.Focus(object), bpy_context.State() as state:

                for other in object.modifiers:
                    if other.name != modifier.name:
                        state.set(other, 'show_viewport', False)

                bpy.ops.object.duplicates_make_real()

                object.modifiers.remove(modifier)


def delete_empty_meshes(objects: typing.List['bpy.types.Object']):

    for object in objects:
        if object.type == 'MESH' and not object.data.vertices:
            bpy.data.objects.remove(object)


def get_x_resolution(resolution: int = 1024):
    return resolution

def get_y_resolution(resolution: int = 1024):
    return resolution

def get_alpha_x_resolution(resolution: int = 1024):
    return resolution

def get_alpha_y_resolution(resolution: int = 1024):
    return resolution

def get_target_objects_settings(settings: S_Target_Objects):
    return settings


def limit_bendy_bones(maximum = 3):
    """ Cap the maximum amount of bendy bone segments per bone. """

    for armature in get_armature_objects():

        for bone in armature.data.bones:

            bone.bbone_segments = min(bone.bbone_segments, maximum)
