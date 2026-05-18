import os
import sys
import typing
import operator
import collections

from . import unreal_material
from .. import configuration

from ..scripts import bake as bake_scripts
from blend_converter import utils as bc_utils


if 'bpy' in sys.modules:

    import bpy
    import mathutils

    from blend_converter.blender import bpy_utils
    from blend_converter.blender import bpy_context
    from blend_converter.blender import bpy_material
    from blend_converter.blender import bpy_action
    from blend_converter.blender import bpy_uv



if 'unreal' in sys.modules:
    import unreal
elif not typing.TYPE_CHECKING:
    unreal = bc_utils.Dummy()


from blend_converter import tool_settings


if typing.TYPE_CHECKING:
    # need only __init__ hints
    import dataclasses

    import typing_extensions
else:
    class dataclasses:
        dataclass = lambda x: x


def rename_objects_for_unreal(prefix: str):
    """
    Match the recommended FBX naming conventions. In order to make the collision shape recognition to work.
    https://dev.epicgames.com/documentation/en-us/unreal-engine/fbx-static-mesh-pipeline-in-unreal-engine?application_version=5.5#collision
    """

    for index, top_layer in enumerate(bpy.context.view_layer.layer_collection.children, start = 1):

        name = prefix + '_' + configuration.get_ascii_underscored(top_layer.name) + f'_{str(index).zfill(2)}'

        collision_index = 1

        for object in top_layer.collection.all_objects:

            if object.get(configuration.UNREAL_COLLISION_PROP_KEY):
                object.name = f'{object[configuration.UNREAL_COLLISION_PROP_KEY]}_{name}_{str(collision_index).zfill(2)}'
                collision_index += 1
            else:
                object.name = name


def is_in_memory_asset(asset_path: str):
    """ For debugging. """
    asset_registry: unreal.AssetRegistry = unreal.AssetRegistryHelpers.get_asset_registry()
    asset_registry.scan_files_synchronous([asset_path], force_rescan=True)
    return asset_registry.get_asset_by_object_path(asset_path, include_only_on_disk_assets=True) == asset_registry.get_asset_by_object_path(asset_path, include_only_on_disk_assets=False)


def get_import_task(options, filename: str, destination_path: str, destination_name: str):

    task = unreal.AssetImportTask()

    task.set_editor_property('automated', True)
    task.set_editor_property('replace_existing', True)
    task.set_editor_property('replace_existing_settings', True)
    task.set_editor_property('save', False)

    task.set_editor_property('options', options)

    task.set_editor_property('filename', filename)
    task.set_editor_property('destination_path', destination_path)
    task.set_editor_property('destination_name', destination_name)

    return task


def get_static_mesh_import_data(asset_path: str) -> unreal.FbxStaticMeshImportData:
    """ The settings are smilingly ignored on a re-import, even with `replace_existing_settings = True`. """

    asset: unreal.StaticMesh = unreal.load_asset(asset_path)
    if asset:
        return asset.get_editor_property('asset_import_data')
    else:
        return unreal.FbxStaticMeshImportData()


def get_skeletal_mesh_import_data(asset_path: str) -> unreal.FbxSkeletalMeshImportData:
    """ The settings are smilingly ignored on a re-import, even with `replace_existing_settings = True`. """

    asset: unreal.SkeletalMesh = unreal.load_asset(asset_path)
    if asset:
        return asset.get_editor_property('asset_import_data')
    else:
        return unreal.FbxSkeletalMeshImportData()


def get_animation_import_data(asset_path: str) -> unreal.FbxAnimSequenceImportData:
    """ The settings are smilingly ignored on a re-import, even with `replace_existing_settings = True`. """

    asset: unreal.AnimationAsset = unreal.load_asset(asset_path)
    if asset:
        return asset.get_editor_property('asset_import_data')
    else:
        return unreal.FbxAnimSequenceImportData()


@dataclasses.dataclass
class S_Unreal_Fbx(tool_settings.Settings):

    fbx_path: str = ''

    destination_folder: str = ''
    destination_name: str = ''

    material_definitions: dict = None
    has_custom_collisions: bool = False

    skeleton_asset_path: str = ''

    frame_rate: int = 0

    @property
    def _asset_path(self):
        return unreal.Paths.combine((self.destination_folder, self.destination_name))


def import_static_mesh(settings: S_Unreal_Fbx):

    settings = S_Unreal_Fbx._from_dict(settings)


    options = unreal.FbxImportUI()

    options.set_editor_property('import_mesh', True)
    options.set_editor_property('import_textures', False)
    options.set_editor_property('import_materials', False)
    options.set_editor_property('import_as_skeletal', False)
    options.set_editor_property('import_animations', False)

    options.set_editor_property('automated_import_should_detect_type', False)
    options.set_editor_property('mesh_type_to_import', unreal.FBXImportType.FBXIT_STATIC_MESH)

    options.set_editor_property('reset_to_fbx_on_material_conflict', True)

    import_data = get_static_mesh_import_data(settings._asset_path)
    import_data.set_editor_property('combine_meshes', True)
    import_data.set_editor_property('auto_generate_collision', not settings.has_custom_collisions)
    import_data.set_editor_property('reorder_material_to_fbx_order', True)
    options.set_editor_property('static_mesh_import_data', import_data)


    task = get_import_task(options, settings.fbx_path, settings.destination_folder, settings.destination_name)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])


    asset: unreal.StaticMesh = get_task_assets(task)[0]

    materials = unreal_material.create_materials(settings.material_definitions, settings.destination_folder, is_skeletal = False)
    unreal_material.set_static_mesh_materials(asset, materials.values())

    unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty = False)

    unreal.log(f"Static Mesh imported: {settings}")


def import_skeletal_mesh(settings: S_Unreal_Fbx):

    settings = S_Unreal_Fbx._from_dict(settings)

    options = unreal.FbxImportUI()

    options.set_editor_property('import_mesh', True)
    options.set_editor_property('import_textures', False)
    options.set_editor_property('import_materials', False)
    options.set_editor_property('import_as_skeletal', True)
    options.set_editor_property('import_animations', False)

    options.set_editor_property('automated_import_should_detect_type', False)
    options.set_editor_property('mesh_type_to_import', unreal.FBXImportType.FBXIT_SKELETAL_MESH)

    options.set_editor_property('reset_to_fbx_on_material_conflict', True)

    import_data = get_skeletal_mesh_import_data(settings._asset_path)
    import_data.set_editor_property('reorder_material_to_fbx_order', True)
    options.set_editor_property('skeletal_mesh_import_data', import_data)


    task = get_import_task(options, settings.fbx_path, settings.destination_folder, settings.destination_name)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    asset: unreal.SkeletalMesh = get_task_assets(task)[0]

    materials = unreal_material.create_materials(settings.material_definitions, settings.destination_folder, is_skeletal = True)
    unreal_material.set_skeletal_mesh_materials(asset, materials)


    unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty = False)

    if asset.skeleton:
        unreal.EditorAssetLibrary.save_loaded_asset(asset.skeleton, only_if_is_dirty = False)

    if asset.physics_asset:
        unreal.EditorAssetLibrary.save_loaded_asset(asset.physics_asset, only_if_is_dirty = False)


    unreal.log(f"Skeletal Mesh imported: {settings}")



def import_anim_sequence(settings: S_Unreal_Fbx):

    settings = S_Unreal_Fbx._from_dict(settings)


    options = unreal.FbxImportUI()

    options.set_editor_property('import_mesh', False)
    options.set_editor_property('import_textures', False)
    options.set_editor_property('import_materials', False)
    options.set_editor_property('import_as_skeletal', False)
    options.set_editor_property('import_animations', True)

    options.set_editor_property('automated_import_should_detect_type', False)
    options.set_editor_property('mesh_type_to_import', unreal.FBXImportType.FBXIT_ANIMATION)

    skeleton = unreal.load_asset(settings.skeleton_asset_path)
    if not skeleton:
        raise Exception(f"Fail to load Skeleton: {settings}")

    options.set_editor_property('skeleton', skeleton)

    import_data = get_animation_import_data(settings._asset_path)
    import_data.set_editor_property('use_default_sample_rate', False)
    import_data.set_editor_property('custom_sample_rate', settings.frame_rate)
    options.set_editor_property('anim_sequence_import_data', import_data)

    task = get_import_task(options, settings.fbx_path, settings.destination_folder, settings.destination_name)
    task.save = True
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    unreal.log(f"Animation Sequence imported: {settings}")


def show_nt_message(title, message):

    if os.name != 'nt':
        return

    if unreal.SystemLibrary.is_unattended() or not unreal.is_editor():
        return

    import subprocess

    code = f"import ctypes, sys; ctypes.windll.user32.MessageBoxW(0, sys.argv[1], sys.argv[2], 0x10 | 0x40000)"

    subprocess.Popen([unreal.get_interpreter_executable_path(), '-c', code, str(message), str(title)], creationflags = subprocess.CREATE_NO_WINDOW)


def get_bone_custom_shapes():

    shapes: typing.Set[bpy.types.Object] = set()

    for o in bpy.data.objects:

        if o.type != 'ARMATURE':
            continue

        for bone in o.pose.bones:
            if bone.custom_shape:
                shapes.add(bone.custom_shape)

    return shapes


def reduce_to_single_mesh(collection_name: str):

    view_layer_objects = bpy_utils.get_view_layer_objects()

    collision_shapes = set(o for o in view_layer_objects if o.get(configuration.UNREAL_COLLISION_PROP_KEY))

    mesh_objects = set(o for o in view_layer_objects if o.type == 'MESH')
    mesh_objects -= get_bone_custom_shapes()
    mesh_objects -= collision_shapes

    with bpy_context.Focus(mesh_objects):
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')

    bpy.data.batch_remove([o for o in bpy.data.objects if not(o in mesh_objects or o in collision_shapes)])

    bpy.data.batch_remove(bpy.data.collections)

    if not mesh_objects:
        return

    with bpy_context.Focus(mesh_objects):
        bpy.ops.object.transform_apply()

    single_object = bpy_utils.join_objects(mesh_objects)

    with bpy_context.Focus(single_object):
        bpy.ops.object.material_slot_remove_unused()

    bpy_context.Focus([single_object] + list(collision_shapes)).__enter__().visible_collection.name = collection_name


def get_group_to_face_indexes_map(mesh: 'bpy.types.Object'):

    vert_to_face_map: typing.Dict[int, typing.Set[int]] = collections.defaultdict(set)
    for face in mesh.data.polygons:
        for vert in face.vertices:
            vert_to_face_map[vert].add(face.index)

    result: typing.Dict[str, typing.Set[int]] = collections.defaultdict(set)

    for vert in mesh.data.vertices:

        group_indexes: typing.List[int] = list(map(operator.attrgetter('group'), vert.groups))

        for index in group_indexes:

            result[mesh.vertex_groups[index].name].update(vert_to_face_map[vert.index])

    return result


def get_face_group_map(mesh: 'bpy.types.Object'):

    face_to_groups: typing.Dict[int, typing.Set[str]] = collections.defaultdict(set)

    group_to_faces = get_group_to_face_indexes_map(mesh)

    for group, face_indexes in group_to_faces.items():
        for index in face_indexes:
            face_to_groups[index].add(group)

    return face_to_groups, group_to_faces


def get_group_to_center(
        mesh: 'bpy.types.Object',
        names: typing.Set[str],
        group_to_faces: typing.Dict[str, typing.Set[int]],
        vertex_to_groups: typing.Dict[int, typing.Dict[int, float]]
    ):

    result: typing.Dict[str, mathutils.Vector] = {}

    for name in names:

        face_indexes = group_to_faces[name]
        group_index = mesh.vertex_groups.get(name).index

        locations: typing.List[mathutils.Vector] = []
        weights: typing.List[float] = []

        for index in face_indexes:
            polygon = mesh.data.polygons[index]
            locations.append(polygon.center)
            weights.append(sum(vertex_to_groups[vertex].get(group_index, 0) for vertex in polygon.vertices) / len(polygon.vertices))

        try:
            group_center = mathutils.Vector([
                bpy_uv.get_weighted_percentile(tuple(map(operator.itemgetter(0), locations)), 0.5, weights),
                bpy_uv.get_weighted_percentile(tuple(map(operator.itemgetter(1), locations)), 0.5, weights),
                bpy_uv.get_weighted_percentile(tuple(map(operator.itemgetter(2), locations)), 0.5, weights),
            ])
        except RuntimeWarning as e:
            print(e)
            group_center = sum((l for l in locations), start = mathutils.Vector()) / len(locations)


        pairs = list(zip(face_indexes, locations))
        pairs.sort(key = lambda x: (x[1] - group_center).length_squared)

        result[name] = pairs[0][1]

    return result


def ensure_bone_count_limit_per_material(limit = 75, max_attempts = 100):
    """
    NOTE: Run `unassign_deform_bones_with_missing_weights` before this one.

    https://github.com/SpeculativeCoder/UnrealEngine/blob/3acb62c7fc6f65e94d3b41397087a3d3530ee8c6/Engine/Source/Runtime/Engine/Public/GPUSkinVertexFactory.h#L29
    ```cpp
    enum
    {
        MAX_GPU_BONE_MATRICES_UNIFORMBUFFER = 75,
    };

    BEGIN_GLOBAL_SHADER_PARAMETER_STRUCT(FBoneMatricesUniformShaderParameters,)
        SHADER_PARAMETER_ARRAY(FMatrix3x4, BoneMatrices, [MAX_GPU_BONE_MATRICES_UNIFORMBUFFER])
    END_GLOBAL_SHADER_PARAMETER_STRUCT()
    ```

    https://github.com/SpeculativeCoder/UnrealEngine/blob/3acb62c7fc6f65e94d3b41397087a3d3530ee8c6/Engine/Source/Runtime/Engine/Private/GPUSkinVertexFactory.cpp#L309
    ```cpp
    static FBoneMatricesUniformShaderParameters GBoneUniformStruct;
    ...
    check(NumBones * sizeof(FMatrix3x4) <= sizeof(GBoneUniformStruct));
    ```

    https://dev.epicgames.com/documentation/en-us/unreal-engine/skeletal-mesh-rendering-paths-in-unreal-engine?application_version=5.7

    By default, the maximum bones per Section is set to 65536. Mobile platforms have a capped maximum of 75 bones per Section.
    """

    armatures = bake_scripts.get_armature_objects()

    with bpy_context.Focus(armatures):

        for armature in armatures:

            deform_bone_names = set(b.name for b in armature.data.bones if b.use_deform)

            for mesh in bake_scripts.get_objects_for_armature(armature):

                face_to_groups, group_to_faces = get_face_group_map(mesh)
                deform_group_names = {group.name for group in mesh.vertex_groups if group.name in deform_bone_names}
                print(f"Bone count: {len(deform_group_names)}")


                deform_groups = deform_group_names.intersection(group_to_faces)

                vertex_to_groups: typing.Dict[int, typing.Dict[int, float]] = {vert.index: {g.group: g.weight for g in vert.groups} for vert in mesh.data.vertices}

                group_to_center = get_group_to_center(mesh, deform_groups, group_to_faces, vertex_to_groups)

                def get_sorted_face_indexes(group_name: str):
                    group_center = group_to_center[group_name]
                    polygons = mesh.data.polygons
                    return sorted(group_to_faces[group_name], key = lambda i: (polygons[i].center - group_center).length_squared)

                group_to_sorted_indexes = {name: get_sorted_face_indexes(name) for name in deform_groups}


                def get_connected_groups(group_name: str):

                    groups = set()

                    for i in group_to_faces[group_name]:
                        groups.update(deform_group_names.intersection(face_to_groups[i]))

                    return len(groups)

                group_to_connected_count = {name: get_connected_groups(name) for name in deform_groups}


                has_over_limit_materials = True
                attempt_count = 0
                good_materials = set()

                while has_over_limit_materials:

                    if attempt_count > max_attempts:
                        raise Exception(f"Fail to split materials: {mesh.name_full}")

                    has_over_limit_materials = False


                    material_index_to_face_indexes_map: typing.Dict[int, typing.List[int]] = collections.defaultdict(list)
                    for face in mesh.data.polygons:
                        material_index_to_face_indexes_map[face.material_index].append(face.index)


                    for material_slot in mesh.material_slots:

                        if material_slot.slot_index in good_materials:
                            continue

                        face_indexes = set(material_index_to_face_indexes_map[material_slot.slot_index])


                        groups: typing.Set[str] = set()
                        for index in face_indexes:
                            groups.update(deform_group_names.intersection(face_to_groups[index]))


                        if len(groups) <= limit:
                            good_materials.add(material_slot.slot_index)
                            continue

                        bc_utils.print_in_color(bc_utils.get_color_code(224, 51, 29, 10, 10, 10),
                            f"Bone limit per material excited."
                            "\n\t" f"Limit: {limit}"
                            "\n\t" f"Object: {mesh.name_full}"
                            "\n\t" f"Slot Index: {material_slot.slot_index}"
                            "\n\t" f"Material: {material_slot.material.name_full}"
                            "\n\t" f"Bone count: {len(groups)}"
                        )

                        has_over_limit_materials = True

                        mesh.data.materials.append(None)
                        new_slot = mesh.material_slots[-1]
                        new_slot.material = material_slot.material


                        sorted_groups = list(groups)
                        sorted_groups.sort(key = group_to_connected_count.get, reverse = True)


                        def assign_new_material():

                            faces_assigned = 0
                            groups_in_new_material = set()
                            processed_faces = set()

                            for start in sorted_groups:

                                stack = [start]
                                processed = set()

                                while stack:

                                    group = stack.pop()

                                    if group in processed:
                                        continue

                                    processed.add(group)

                                    for i in group_to_sorted_indexes[group]:

                                        if not i in face_indexes:
                                            continue

                                        if i in processed_faces:
                                            continue

                                        processed_faces.add(i)

                                        new_groups = deform_group_names.intersection(face_to_groups[i])

                                        if len(new_groups | groups_in_new_material) > limit:
                                            continue

                                        mesh.data.polygons[i].material_index = new_slot.slot_index
                                        faces_assigned += 1

                                        groups_in_new_material.update(new_groups)

                                        stack.extend(new_groups)



                        assign_new_material()

                        break

                    attempt_count += 1


def limit_total_bone_weights(limit = 4):

    for armature in bake_scripts.get_armature_objects():

        for mesh in bake_scripts.get_objects_for_armature(armature):

            with bpy_context.Focus(mesh, 'WEIGHT_PAINT'):
                bpy.ops.object.vertex_group_normalize_all(group_select_mode='BONE_DEFORM', lock_active=False)
                bpy.ops.object.vertex_group_limit_total(group_select_mode='BONE_DEFORM', limit=limit)


def join_all_mesh_objects(collection_name: str, objects: typing.List['bpy.types.Object']):

    mesh_objects = set(o for o in objects if o.type == 'MESH')

    with bpy_context.Focus(mesh_objects):
        bpy.context.view_layer.objects.active = list(mesh_objects)[0]
        bpy.ops.object.transform_apply()
        bpy.ops.object.join()
        bpy.ops.object.material_slot_remove_unused()

    all_objects = bpy_utils.get_view_layer_objects()

    bpy.data.batch_remove(bpy.data.collections)

    bpy_context.Focus(all_objects).__enter__().visible_collection.name = collection_name


def scale_armature(factor: float):

    bpy.context.scene.tool_settings.use_keyframe_insert_auto = False  # this is for the inspection

    if bpy.context.scene.unit_settings.system == 'NONE':
        bpy.context.scene.unit_settings.scale_length = 1

    bpy.context.scene.unit_settings.system = 'METRIC'

    scale_length = bpy.context.scene.unit_settings.scale_length

    bpy.context.scene.unit_settings.scale_length = 1/factor

    factor *= scale_length

    for window_manager in bpy.data.window_managers:
        for window in window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    for region in area.regions:
                        if region.type == 'WINDOW':
                            space_data: bpy.types.SpaceView3D = area.spaces.active
                            space_data.clip_start *= factor
                            space_data.clip_end *= factor

    bpy_utils.make_object_data_unique(bpy.data.objects)

    with bpy_context.Focus(bpy.data.objects):
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        bpy.ops.transform.resize(value=(factor, factor, factor))
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    for action in bpy.data.actions:
        for fcurve in bpy_action.iter_fcurves(action):
            if fcurve.data_path.endswith('location'):
                for key in fcurve.keyframe_points:
                    key.co.y *= factor
                    key.handle_left.y *= factor
                    key.handle_right.y *= factor


def get_frame_rate():
    return bpy.context.scene.render.fps / bpy.context.scene.render.fps_base


def ensure_single_root_bone(name = f"__bc_root", assign_default_weights = False):
    """ Create a default single root bone to satisfy the Unreal Engine's requirement. """

    def are_all_vertices_have_groups(object: bpy.types.Object, bone_names: set[str]):
        return all(not set(object.vertex_groups[group.group].name for group in v.groups).isdisjoint(bone_names) for v in object.data.vertices)

    def create_root_vertex_group(object: bpy.types.Object, bone_names: set[str], root_bone_name: str):
        default_group = object.vertex_groups.new(name = root_bone_name)
        default_group.add([v.index for v in object.data.vertices if set(object.vertex_groups[group.group].name for group in v.groups).isdisjoint(bone_names)], 1, 'ADD')

    for armature in bake_scripts.get_armature_objects():

        tree = bpy_action.get_bone_tree(armature)

        has_multiple_root_bones = len(tree[1]) > 1
        if not has_multiple_root_bones:
            continue

        use_deform = False

        if assign_default_weights:
            meshes = bake_scripts.get_objects_for_armature(armature)
            bone_names = {bone.name for bone in armature.data.bones}
            for mesh in meshes:
                if not are_all_vertices_have_groups(mesh, bone_names):
                    create_root_vertex_group(mesh, bone_names, name)
                    use_deform = use_deform or True

        with bpy_context.Focus(armature, 'EDIT'):

            edit_bones = armature.data.edit_bones

            root_bone = edit_bones.new(name)
            root_bone.use_deform = use_deform
            root_bone.head = (0, 0, 0)
            root_bone.tail = (0, 1, 0)

            for bone in edit_bones:
                if not bone.parent:
                    bone.parent = root_bone


def join_path(*paths):
    path = os.path.join(*paths).replace(os.sep, '/')
    path = path.lstrip('/')
    return '/' + path


if hasattr(unreal.AssetImportTask, 'get_objects'):

    def get_task_assets(task: unreal.AssetImportTask):
        return task.get_objects()

else:

    def get_task_assets(task: unreal.AssetImportTask):
        return [unreal.EditorAssetLibrary.load_asset(path) for path in task.imported_object_paths]
