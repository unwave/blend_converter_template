import os
import sys
import typing
import uuid
import operator
import collections
import functools


ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if not ROOT in sys.path:
    sys.path.append(ROOT)


import configuration

from scripts import bake as bake_scripts


if 'bpy' in sys.modules:
    import bpy
    from blend_converter.blender import bpy_utils
    from blend_converter.blender import bpy_context
    from blend_converter import utils as bc_utils


if 'unreal' in sys.modules:
    import unreal
elif typing.TYPE_CHECKING:
    import unreal
else:

    class dummy:

        def __getattribute__(self, key):
            return self

        def __getattr___(self, key):
            return self

        def __getitem__(self, key):
            return self

        def __call__(self, *args, **kwargs):

            if len(args) == 1 and callable(args[0]):
                return args[0]
            else:
                return self

    unreal = dummy()


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


@dataclasses.dataclass
class S_Material_Definition(tool_settings.Settings):

    base_color: str = ''
    orma: str = ''
    normal: str = ''
    emission: str = ''

    is_alpha: bool = False


def get_material_definition(material: 'bpy.types.Material'):

    from blend_converter.blender import bpy_node

    result = S_Material_Definition()

    tree = bpy_node.Shader_Tree_Wrapper(material.node_tree)
    principled =  tree.output[0]

    def get_first_image(socket_identifier: str):

        for node in principled.inputs[socket_identifier].descendants:
            if node.be('ShaderNodeTexImage') and node.image:
                return bpy_utils.get_block_abspath(node.image)

        return ''

    result.base_color = get_first_image('Base Color')
    result.orma = get_first_image('Metallic')
    result.normal = get_first_image('Normal')
    result.emission = get_first_image(bpy_node.Socket_Identifier.EMISSION)

    result.is_alpha = bool(principled['Alpha'] or principled.inputs['Alpha'].default_value != 1)

    return result


def get_material_definitions_for_single_object():
    """ This is used to recreate the materials inside Unreal. """

    used_slot_names: typing.Set[str] = set()
    index_to_name: typing.Dict[int, str] = {}
    slot_name_to_name: typing.Dict[str, str] = {}
    name_to_definition: typing.Dict[str, S_Material_Definition] = {}


    object = next((o for o in bpy_utils.get_view_layer_objects() if o.type == 'MESH'), None)
    if not object:
        return dict(slot_name_to_name = slot_name_to_name, name_to_definition = name_to_definition)


    def ensure_unique_name(name: str, index = 2):

        orig_name = name
        while name in used_slot_names:
            name = orig_name + '_' + str(index).zfill(2)
            index += 1

        used_slot_names.add(name)

        return name


    # standardize the materials
    bpy_utils.convert_materials_to_principled([object])
    assert all(s.material and s.material.node_tree for s in object.material_slots)


    # collect material definitions
    for slot in object.material_slots:

        definition = name_to_definition.get(slot.material.name)
        if definition is None:
            name_to_definition[slot.material.name] = get_material_definition(slot.material)._to_dict()

        index_to_name[slot.slot_index] = slot.material.name


    # make so if a material is used more than once the socket will have a number suffix for clarity
    seen = set()
    has_multiple_users = set()
    for material_name in index_to_name.values():

        if material_name in seen and not material_name in has_multiple_users:
            used_slot_names.add(material_name)
            has_multiple_users.add(material_name)

        seen.add(material_name)


    # map slot names to material names
    # Unreal uses the material names as the slot names and merges slots with the same materials
    # so we have to duplicate them to make unique
    for slot in object.material_slots:

        material_name = index_to_name[slot.slot_index]

        name = ensure_unique_name(configuration.get_ascii_underscored(material_name), index = 1 if material_name in has_multiple_users else 2)

        slot.material = slot.material.copy()

        existing_material = bpy.data.materials.get(name)
        if existing_material:
            existing_material.name += '(renamed)'

        slot.material.name = name

        slot_name_to_name[name] = material_name


    return dict(slot_name_to_name = slot_name_to_name, name_to_definition = name_to_definition)


@functools.lru_cache(None)
def import_texture(os_path: str, ue_dir: str, name: typing.Optional[str] = None, **editor_property) -> 'unreal.Texture':

    if name:
        dest_ue_name = name
    else:
        dest_ue_name = 'T_' + os.path.splitext(os.path.basename(os_path))[0]

    task = unreal.AssetImportTask()

    task.automated = True
    task.replace_existing = True
    task.replace_existing_settings = True
    task.save = True

    task.filename = os_path
    task.destination_path = ue_dir
    task.destination_name = dest_ue_name

    factory = unreal.TextureFactory()

    task.factory = factory
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    assert len(task.imported_object_paths) == 1

    asset = unreal.load_asset(task.imported_object_paths[0])

    for key, value in editor_property.items():
        asset.set_editor_property(key, value)

    unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty = False)

    return asset


def is_in_memory_asset(asset_path: str):
    """ For debugging. """
    asset_registry: unreal.AssetRegistry = unreal.AssetRegistryHelpers.get_asset_registry()
    asset_registry.scan_files_synchronous([asset_path], force_rescan=True)
    return asset_registry.get_asset_by_object_path(asset_path, include_only_on_disk_assets=True) == asset_registry.get_asset_by_object_path(asset_path, include_only_on_disk_assets=False)


class UE_Material:
    """
    https://forums.unrealengine.com/t/setting-static-switch-parameters-of-a-material-instance-in-python/136415
    BUG: material instances not respecting static switches in ES 3.1
    BUG: could not set static switches in UE 4
    FIXME: This is not optimal but to keep things simple.
    """

    OPAQUE = '/Game/Materials/base/M_SM_opaque'
    ALPHA = '/Game/Materials/base/M_SK_dithered_alpha'


class UE_Material_Permutations:

    O_SM_C_ORM = '/Game/Materials/manual_permutations/opaque/static/M_O_SM_C_ORM'
    O_SM_C_ORM_E = '/Game/Materials/manual_permutations/opaque/static/MI_O_SM_C_ORM_E'
    O_SM_C_ORM_N = '/Game/Materials/manual_permutations/opaque/static/MI_O_SM_C_ORM_N'
    O_SM_C_ORM_N_E = '/Game/Materials/manual_permutations/opaque/static/MI_O_SM_C_ORM_N_E'

    O_SK_C_ORM = '/Game/Materials/manual_permutations/opaque/skeletal/M_O_SK_C_ORM'
    O_SK_C_ORM_E = '/Game/Materials/manual_permutations/opaque/skeletal/MI_O_SK_C_ORM_E'
    O_SK_C_ORM_N = '/Game/Materials/manual_permutations/opaque/skeletal/MI_O_SK_C_ORM_N'
    O_SK_C_ORM_N_E = '/Game/Materials/manual_permutations/opaque/skeletal/MI_O_SK_C_ORM_N_E'

    A_SM_C_ORMA = '/Game/Materials/manual_permutations/alpha/static/M_A_SM_C_ORMA'
    A_SM_C_ORMA_E = '/Game/Materials/manual_permutations/alpha/static/MI_A_SM_C_ORMA_E'
    A_SM_C_ORMA_N = '/Game/Materials/manual_permutations/alpha/static/MI_A_SM_C_ORMA_N'
    A_SM_C_ORMA_N_E = '/Game/Materials/manual_permutations/alpha/static/MI_A_SM_C_ORMA_N_E'

    A_SK_C_ORMA = '/Game/Materials/manual_permutations/alpha/skeletal/M_A_SK_C_ORMA'
    A_SK_C_ORMA_E = '/Game/Materials/manual_permutations/alpha/skeletal/MI_A_SK_C_ORMA_E'
    A_SK_C_ORMA_N = '/Game/Materials/manual_permutations/alpha/skeletal/MI_A_SK_C_ORMA_N'
    A_SK_C_ORMA_N_E = '/Game/Materials/manual_permutations/alpha/skeletal/MI_A_SK_C_ORMA_N_E'


def get_parent_material_path(is_alpha = False, is_skeletal = False, has_normal = False, has_emission = False):

    if is_alpha:
        return UE_Material.ALPHA
    else:
        return UE_Material.OPAQUE


def get_parent_material_permutation_path(is_alpha = False, is_skeletal = False, has_normal = False, has_emission = False):

    name = []

    if is_alpha:
        name.append('A')
    else:
        name.append('O')

    if is_skeletal:
        name.append('SK')
    else:
        name.append('SM')

    name.append('C')

    if is_alpha:
        name.append('ORMA')
    else:
        name.append('ORM')

    if has_normal:
        name.append('N')

    if has_emission:
        name.append('E')

    return getattr(UE_Material_Permutations, '_'.join(name))


class Material_Parameter:

    BASE_COLOR = 'BaseColor'
    ORMA = 'ORMA'
    NORMAL = 'Normal'
    EMISSION = 'Emission'


def create_material_instance(*,
            asset_name: str,
            package_path: str,
            base_color_filepath = '',
            orma_filepath = '',
            normal_filepath = '',
            emission_filepath = '',
            is_alpha = False,
            is_skeletal = False,
        ) -> unreal.MaterialInstanceConstant:

    unreal.EditorAssetLibrary.make_directory(package_path)

    asset_path = unreal.Paths.combine([package_path, asset_name])  # TODO: might not be correct

    if is_in_memory_asset(asset_path):
        raise Exception(f"In memory asset, restart Unreal Engine: {asset_path}")  # TODO: testing


    do_replace = unreal.EditorAssetLibrary.does_asset_exist(asset_path)
    if do_replace:
        asset_name = asset_name + f"_TEMP_{uuid.uuid1().hex}"
    else:
        asset_name = asset_name


    factory = unreal.MaterialInstanceConstantFactoryNew()
    material_instance: unreal.MaterialInstanceConstant = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name=asset_name,
        package_path=package_path,
        asset_class=unreal.MaterialInstanceConstant,
        factory=factory,
    )


    if not material_instance:
        raise Exception(f"Fail to create Material Instance: {asset_path}")


    has_manual_permutations = unreal.EditorAssetLibrary.does_directory_exist('/Game/Materials/manual_permutations')

    if has_manual_permutations:
        parent_material_path = get_parent_material_permutation_path(
            is_alpha = is_alpha,
            is_skeletal = is_skeletal,
            has_normal = normal_filepath,
            has_emission = emission_filepath,
        )

    else:
        parent_material_path = get_parent_material_path(
            is_alpha = is_alpha,
            is_skeletal = is_skeletal,
            has_normal = normal_filepath,
            has_emission = emission_filepath,
        )

    parent_material = unreal.load_asset(parent_material_path)
    if not parent_material:
        raise Exception(f"Fail to load material from path: {parent_material_path}")

    material_instance.set_editor_property('parent', parent_material)


    if normal_filepath:
        texture = import_texture(
            normal_filepath,
            package_path,
            compression_settings = unreal.TextureCompressionSettings.TC_NORMALMAP,
            flip_green_channel = True,
            srgb = False,
        )
        unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(material_instance, Material_Parameter.NORMAL, texture)

        try:
            if not has_manual_permutations:
                unreal.MaterialEditingLibrary.set_material_instance_static_switch_parameter_value(material_instance, 'use_normal', True)
        except AttributeError as e:
            message = f"The static switch 'use_normal' is not set for material: {asset_name}. Need UE 5.0+."
            show_nt_message('Static switch not set!', message)
            print(message)



    if base_color_filepath:
        texture = import_texture(
            base_color_filepath,
            package_path,
            compression_settings = unreal.TextureCompressionSettings.TC_DEFAULT,
        )
        unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(material_instance, Material_Parameter.BASE_COLOR, texture)


    if orma_filepath:
        texture = import_texture(
            orma_filepath,
            package_path,
            compression_settings = unreal.TextureCompressionSettings.TC_MASKS,
            srgb = False,
        )
        unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(material_instance, Material_Parameter.ORMA, texture)


    if emission_filepath:
        texture = import_texture(
            emission_filepath,
            package_path,
            compression_settings = unreal.TextureCompressionSettings.TC_DEFAULT,
        )
        unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(material_instance, Material_Parameter.EMISSION, texture)

        try:
            if not has_manual_permutations:
                unreal.MaterialEditingLibrary.set_material_instance_static_switch_parameter_value(material_instance, 'use_emission', True)
        except AttributeError as e:
            message = f"The static switch 'use_emission' is not set for material: {asset_name}. Need UE 5.0+."
            show_nt_message('Static switch not set!', message)
            print(message)


    unreal.EditorAssetLibrary.save_loaded_asset(material_instance, only_if_is_dirty = False)

    if do_replace:
        old_asset = unreal.load_asset(asset_path)
        if old_asset:
            unreal.EditorAssetLibrary.consolidate_assets(material_instance, [old_asset])
            # https://forums.unrealengine.com/t/fix-redirectors-via-python/124785
            unreal.EditorAssetLibrary.delete_asset(asset_path)  # deleting redirect
            unreal.EditorAssetLibrary.rename_asset(material_instance.get_full_name(), asset_path)
        else:
            # not tested
            unreal.EditorAssetLibrary.delete_asset(asset_path)
            unreal.EditorAssetLibrary.rename_asset(material_instance.get_full_name(), asset_path)


    return material_instance


def create_materials(material_definitions: dict, package_path: str, is_skeletal: bool) -> typing.Dict[str, unreal.MaterialInstanceConstant]:

    import_texture.cache_clear()

    name_to_material: typing.Dict[str, unreal.MaterialInstanceConstant] = {}

    for key, value in material_definitions['name_to_definition'].items():

        definition = S_Material_Definition._from_dict(value)

        name_to_material[key] = create_material_instance(
            asset_name = 'MI_' + key,
            package_path = package_path,
            base_color_filepath = definition.base_color,
            orma_filepath = definition.orma,
            normal_filepath = definition.normal,
            emission_filepath = definition.emission,
            is_alpha = definition.is_alpha,
            is_skeletal = is_skeletal,
        )

    return {slot_name: name_to_material[name] for slot_name, name in material_definitions['slot_name_to_name'].items()}


def set_static_mesh_materials(asset: unreal.StaticMesh, materials: typing.List[unreal.MaterialInstanceConstant]):

    for index, material in enumerate(materials):
        unreal.StaticMesh.set_material(asset, index, material)


def set_skeletal_mesh_materials(asset: unreal.SkeletalMesh, materials: typing.Dict[str, unreal.MaterialInstanceConstant]):

    array = unreal.Array(unreal.SkeletalMaterial)

    skeletal_materials: typing.Dict[str, unreal.SkeletalMaterial] = {str(m.get_editor_property('imported_material_slot_name')): m for m in asset.get_editor_property('materials')}

    for slot_name, material in materials.items():

        # to preserve imported_material_slot_name
        copy: unreal.SkeletalMaterial = skeletal_materials[slot_name].copy()

        copy.set_editor_property('material_slot_name', slot_name)
        copy.set_editor_property('material_interface', material)

        array.append(copy)

    asset.set_editor_property('materials', array)


def get_import_task(options, filename: str, destination_path: str, destination_name: str):

    task = unreal.AssetImportTask()

    task.set_editor_property('automated', True)
    task.set_editor_property('replace_existing', True)
    task.set_editor_property('replace_existing_settings', True)
    task.set_editor_property('save', True)

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
class Settings_Unreal_Fbx(tool_settings.Settings):

    fbx_path: str = ''

    dist_dir: str = ''
    dist_name: str = ''

    material_definitions: dict = None
    has_custom_collisions: bool = False

    skeleton_asset_path: str = ''

    frame_rate: int = 0

    @property
    def _asset_path(self):
        return unreal.Paths.combine((self.dist_dir, self.dist_name))


def import_static_mesh(settings: Settings_Unreal_Fbx):

    settings = Settings_Unreal_Fbx._from_dict(settings)


    options = unreal.FbxImportUI()

    options.set_editor_property('import_mesh', True)
    options.set_editor_property('import_textures', False)
    options.set_editor_property('import_materials', False)
    options.set_editor_property('import_as_skeletal', False)
    options.set_editor_property('import_animations', False)

    options.set_editor_property('automated_import_should_detect_type', False)
    options.set_editor_property('mesh_type_to_import', unreal.FBXImportType.FBXIT_STATIC_MESH)

    import_data = get_static_mesh_import_data(settings._asset_path)
    import_data.set_editor_property('combine_meshes', True)
    import_data.set_editor_property('auto_generate_collision', not settings.has_custom_collisions)
    import_data.set_editor_property('reorder_material_to_fbx_order', True)
    options.set_editor_property('static_mesh_import_data', import_data)


    task = get_import_task(options, settings.fbx_path, settings.dist_dir, settings.dist_name)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])


    asset: unreal.StaticMesh = unreal.load_asset(settings._asset_path)

    materials = create_materials(settings.material_definitions, settings.dist_dir, is_skeletal = False)
    set_static_mesh_materials(asset, materials.values())

    unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty = False)

    unreal.log(f"Static Mesh imported: {settings}")


def import_skeletal_mesh(settings: Settings_Unreal_Fbx):

    settings = Settings_Unreal_Fbx._from_dict(settings)

    options = unreal.FbxImportUI()

    options.set_editor_property('import_mesh', True)
    options.set_editor_property('import_textures', False)
    options.set_editor_property('import_materials', False)
    options.set_editor_property('import_as_skeletal', False)
    options.set_editor_property('import_animations', False)

    options.set_editor_property('automated_import_should_detect_type', False)
    options.set_editor_property('mesh_type_to_import', unreal.FBXImportType.FBXIT_SKELETAL_MESH)


    import_data = get_skeletal_mesh_import_data(settings._asset_path)
    import_data.set_editor_property('reorder_material_to_fbx_order', True)
    options.set_editor_property('skeletal_mesh_import_data', import_data)


    task = get_import_task(options, settings.fbx_path, settings.dist_dir, settings.dist_name)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    assert len(task.imported_object_paths) == 1

    asset: unreal.SkeletalMesh = unreal.load_asset(task.imported_object_paths[0])

    materials = create_materials(settings.material_definitions, settings.dist_dir, is_skeletal = True)
    set_skeletal_mesh_materials(asset, materials)

    unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty = False)

    unreal.log(f"Skeletal Mesh imported: {settings}")


def import_skeleton(settings: Settings_Unreal_Fbx):

    settings = Settings_Unreal_Fbx._from_dict(settings)

    options = unreal.FbxImportUI()

    options.set_editor_property('import_mesh', False)
    options.set_editor_property('import_textures', False)
    options.set_editor_property('import_materials', False)
    options.set_editor_property('import_as_skeletal', True)
    options.set_editor_property('import_animations', False)

    options.set_editor_property('automated_import_should_detect_type', False)
    # options.set_editor_property('mesh_type_to_import', unreal.FBXImportType.FBXIT_SKELETAL_MESH)


    # import_data = get_skeletal_mesh_import_data(settings._asset_path)
    # options.set_editor_property('skeletal_mesh_import_data', import_data)


    task = get_import_task(options, settings.fbx_path, settings.dist_dir, settings.dist_name)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])


    unreal.log(f"Skeletal Mesh imported: {settings}")


def import_anim_sequence(settings: Settings_Unreal_Fbx):

    settings = Settings_Unreal_Fbx._from_dict(settings)


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

    task = get_import_task(options, settings.fbx_path, settings.dist_dir, settings.dist_name)
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


def ensure_bone_count_limit_per_material(limit = 75, max_attempts = 50):
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

                        def get_connected_groups(group_name: str):

                            groups = set()

                            for i in group_to_faces[group_name]:
                                groups.update(deform_group_names.intersection(face_to_groups[i]))

                            return len(groups)

                        sorted_groups.sort(key = get_connected_groups, reverse = True)


                        def assign_new_material():

                            faces_assigned = 0
                            half_of_faces = len(face_indexes) // 2

                            for start in sorted_groups:

                                stack = [start]
                                processed = set()

                                while stack:

                                    group = stack.pop()

                                    if group in processed:
                                        continue

                                    processed.add(group)

                                    for i in sorted(group_to_faces[group]):

                                        if not i in face_indexes:
                                            continue

                                        mesh.data.polygons[i].material_index = new_slot.slot_index
                                        faces_assigned += 1

                                        if faces_assigned >= half_of_faces:
                                            return

                                        stack.extend(deform_group_names.intersection(face_to_groups[i]))

                                    if len(processed) >= limit:
                                        return

                        assign_new_material()

                        break

                    attempt_count += 1


def limit_total_bone_weights(limit = 4):

    for armature in bake_scripts.get_armature_objects():

        for mesh in bake_scripts.get_objects_for_armature(armature):

            with bpy_context.Focus(mesh, 'WEIGHT_PAINT'):
                bpy.ops.object.vertex_group_normalize_all(group_select_mode='BONE_DEFORM', lock_active=False)
                bpy.ops.object.vertex_group_limit_total(group_select_mode='BONE_DEFORM', limit=limit)


def join_all_mesh_objects(collection_name: str):

    view_layer_objects = bpy_utils.get_view_layer_objects()

    collision_shapes = set(o for o in view_layer_objects if o.get(configuration.UNREAL_COLLISION_PROP_KEY))

    mesh_objects = set(o for o in view_layer_objects if o.type == 'MESH')
    mesh_objects -= get_bone_custom_shapes()
    mesh_objects -= collision_shapes

    with bpy_context.Focus(mesh_objects):
        bpy.context.view_layer.objects.active = list(mesh_objects)[0]
        bpy.ops.object.transform_apply()
        bpy.ops.object.join()

    with bpy_context.Focus(bpy.context.view_layer.objects.active):
        bpy.ops.object.material_slot_remove_unused()

    all_objects = bpy_utils.get_view_layer_objects()

    bpy.data.batch_remove(bpy.data.collections)

    bpy_context.Focus(all_objects).__enter__().visible_collection.name = collection_name


def scale_armature(factor = 100):

    bpy.context.scene.tool_settings.use_keyframe_insert_auto = False  # this is for the inspection

    bpy.context.scene.unit_settings.scale_length = 1/factor

    for window_manager in bpy.data.window_managers:
        for window in window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    for region in area.regions:
                        if region.type == 'WINDOW':
                            space_data: bpy.types.SpaceView3D = area.spaces.active
                            space_data.clip_start *= factor
                            space_data.clip_end *= factor

    with bpy_context.Focus(bpy.data.objects):
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        bpy.ops.transform.resize(value=(factor, factor, factor))
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    for action in bpy.data.actions:
        for fcurve in action.fcurves:
            if fcurve.data_path.endswith('location'):
                for key in fcurve.keyframe_points:
                    key.co.y *= factor
                    key.handle_left.y *= factor
                    key.handle_right.y *= factor


def get_frame_rate():
    return bpy.context.scene.render.fps / bpy.context.scene.render.fps_base
