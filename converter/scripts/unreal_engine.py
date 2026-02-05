import os
import sys
import typing
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if not ROOT in sys.path:
    sys.path.append(ROOT)


import configuration


if 'bpy' in sys.modules:
    import bpy
    from blend_converter.blender import bpy_utils
    from blend_converter.blender import bpy_context


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


def get_material_definitions_for_single_object():
    """ This is used to recreate the materials inside Unreal. """

    from blend_converter.blender import bpy_node

    object = next((o for o in bpy_utils.get_view_layer_objects() if o.type == 'MESH'), None)
    if not object:
        return []

    definitions = []

    used_names = set()

    def ensure_unique_name(name: str):

        orig_name = name
        index = 2
        while name in used_names:
            name = orig_name + '_' + str(index).zfill(2)
            index += 1

        used_names.add(name)

        return name

    bpy_utils.convert_materials_to_principled([object])


    for material_slot in object.material_slots:

        assert material_slot.material
        assert material_slot.material.node_tree

        definition = {}
        definition['textures'] = textures = {}

        material = material_slot.material

        name = ensure_unique_name(configuration.get_ascii_underscored(material.name))
        definition['name'] = name
        material.name = name

        tree = bpy_node.Shader_Tree_Wrapper(material.node_tree)

        principled =  tree.output[0]

        node = next((node for node in principled.inputs['Base Color'].descendants if node.be('ShaderNodeTexImage')), None)
        if node:
            textures['base_color'] = bpy_utils.get_block_abspath(node.image)
        else:
            textures['base_color'] = None

        node = next((node for node in principled.inputs['Metallic'].descendants if node.be('ShaderNodeTexImage')), None)
        if node:
            textures['orma'] = bpy_utils.get_block_abspath(node.image)
        else:
            textures['orma'] = None

        node = next((node for node in principled.inputs['Normal'].descendants if node.be('ShaderNodeTexImage')), None)
        if node:
            textures['normal'] = bpy_utils.get_block_abspath(node.image)
        else:
            textures['normal'] = None

        node = next((node for node in principled.inputs[bpy_node.Socket_Identifier.EMISSION].descendants if node.be('ShaderNodeTexImage')), None)
        if node:
            textures['emission'] = bpy_utils.get_block_abspath(node.image)
        else:
            textures['emission'] = None


        definition['is_alpha'] = bool(principled['Alpha'] or principled.inputs['Alpha'].default_value != 1)

        definitions.append(definition)

    return definitions


def import_texture(os_path: str, ue_dir: str, name: typing.Optional[str] = None) -> 'unreal.Texture':

    if name:
        dest_ue_name = name
    else:
        dest_ue_name = os.path.splitext(os.path.basename(os_path))[0]

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

    return unreal.load_asset(task.imported_object_paths[0])


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


@dataclasses.dataclass
class Settings_Unreal_Material_Instance(tool_settings.Settings):

    name: str = ''
    dir: str = ''

    base_color_filepath: str = ''
    _base_color_param_name: str = 'BaseColor'

    orma_filepath: str = ''
    _orma_param_name: str = 'ORMA'

    normal_filepath: str = ''
    _normal_param_name: str = 'Normal'

    emission_filepath: str = ''
    _emission_param_name: str = 'Emission'

    is_alpha: bool = False
    is_skeletal: bool = False


    @property
    def _asset_path(self):
        return unreal.Paths.combine([self.dir, self.name])


def create_material_instance(settings: Settings_Unreal_Material_Instance):

    unreal.EditorAssetLibrary.make_directory(settings.dir)

    if is_in_memory_asset(settings._asset_path):
        raise Exception(f"In memory asset, restart Unreal Engine: {settings._asset_path}")  # TODO: testing


    do_replace = unreal.EditorAssetLibrary.does_asset_exist(settings._asset_path)
    if do_replace:
        asset_name = settings.name + f"_TEMP_{uuid.uuid1().hex}"
    else:
        asset_name = settings.name


    factory = unreal.MaterialInstanceConstantFactoryNew()
    material_instance: unreal.MaterialInstanceConstant = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name=asset_name,
        package_path=settings.dir,
        asset_class=unreal.MaterialInstanceConstant,
        factory=factory,
    )


    if not material_instance:
        raise Exception(f"Fail to create Material Instance: {settings._asset_path}")


    has_manual_permutations = unreal.EditorAssetLibrary.does_directory_exist('/Game/Materials/manual_permutations')

    if has_manual_permutations:
        parent_material_path = get_parent_material_permutation_path(
            is_alpha = settings.is_alpha,
            is_skeletal = settings.is_skeletal,
            has_normal = settings.normal_filepath,
            has_emission = settings.emission_filepath,
        )

    else:
        parent_material_path = get_parent_material_path(
            is_alpha = settings.is_alpha,
            is_skeletal = settings.is_skeletal,
            has_normal = settings.normal_filepath,
            has_emission = settings.emission_filepath,
        )

    parent_material = unreal.load_asset(parent_material_path)
    if not parent_material:
        raise Exception(f"Fail to load material from path: {parent_material_path}")

    material_instance.set_editor_property('parent', parent_material)


    if settings.normal_filepath:
        normal_texture = import_texture(settings.normal_filepath, settings.dir)
        normal_texture.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_NORMALMAP)
        normal_texture.set_editor_property('flip_green_channel', True)
        normal_texture.set_editor_property('srgb', False)  # ensuring that the pre/post change notifications are called
        unreal.EditorAssetLibrary.save_loaded_asset(normal_texture, only_if_is_dirty = False)
        unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(material_instance, settings._normal_param_name, normal_texture)

        try:
            if not has_manual_permutations:
                unreal.MaterialEditingLibrary.set_material_instance_static_switch_parameter_value(material_instance, 'use_normal', True)
        except AttributeError as e:
            message = f"The static switch 'use_normal' is not set for material: {settings.name}. Need UE 5.0+."
            show_nt_message('Static switch not set!', message)
            print(message)



    if settings.base_color_filepath:
        base_color_texture = import_texture(settings.base_color_filepath, settings.dir)
        base_color_texture.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_DEFAULT)
        unreal.EditorAssetLibrary.save_loaded_asset(base_color_texture, only_if_is_dirty = False)
        unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(material_instance, settings._base_color_param_name, base_color_texture)


    if settings.orma_filepath:
        orm_texture = import_texture(settings.orma_filepath, settings.dir)
        orm_texture.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_MASKS)
        orm_texture.set_editor_property('srgb', False)  # ensuring that the pre/post change notifications are called
        unreal.EditorAssetLibrary.save_loaded_asset(orm_texture, only_if_is_dirty = False)
        unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(material_instance, settings._orma_param_name, orm_texture)


    if settings.emission_filepath:
        emission_texture = import_texture(settings.emission_filepath, settings.dir)
        emission_texture.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_DEFAULT)
        unreal.EditorAssetLibrary.save_loaded_asset(emission_texture, only_if_is_dirty = False)
        unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(material_instance, settings._emission_param_name, emission_texture)

        try:
            if not has_manual_permutations:
                unreal.MaterialEditingLibrary.set_material_instance_static_switch_parameter_value(material_instance, 'use_emission', True)
        except AttributeError as e:
            message = f"The static switch 'use_emission' is not set for material: {settings.name}. Need UE 5.0+."
            show_nt_message('Static switch not set!', message)
            print(message)


    unreal.EditorAssetLibrary.save_loaded_asset(material_instance, only_if_is_dirty = False)

    if do_replace:
        old_asset = unreal.load_asset(settings._asset_path)
        if old_asset:
            unreal.EditorAssetLibrary.consolidate_assets(material_instance, [old_asset])
            # https://forums.unrealengine.com/t/fix-redirectors-via-python/124785
            unreal.EditorAssetLibrary.delete_asset(settings._asset_path)  # deleting redirect
            unreal.EditorAssetLibrary.rename_asset(material_instance.get_full_name(), settings._asset_path)
        else:
            # not tested
            unreal.EditorAssetLibrary.delete_asset(settings._asset_path)
            unreal.EditorAssetLibrary.rename_asset(material_instance.get_full_name(), settings._asset_path)


    unreal.log(f"Materials Instance created: {settings}")

    return material_instance


def create_materials(material_definitions: typing.List[dict], result_dir: str, is_skeletal: bool):

    materials_settings: typing.List[unreal.MaterialInstanceConstant] = []

    for definition in material_definitions:

        materials_settings.append(
            Settings_Unreal_Material_Instance(
                name = 'MI_' + definition['name'],
                dir = result_dir,
                base_color_filepath = definition['textures']['base_color'],
                orma_filepath = definition['textures']['orma'],
                normal_filepath =  definition['textures']['normal'],
                emission_filepath= definition['textures']['emission'],
                is_alpha = definition['is_alpha'],
                is_skeletal = is_skeletal,
            )
        )

    return [create_material_instance(material_settings) for material_settings in materials_settings]


def set_static_mesh_materials(asset: unreal.StaticMesh, materials: typing.List[unreal.MaterialInstanceConstant]):

    for index, material in enumerate(materials):
        unreal.StaticMesh.set_material(asset, index, material)


def set_skeletal_mesh_materials(asset: unreal.SkeletalMesh, materials: typing.List[unreal.MaterialInstanceConstant]):

    array = unreal.Array(unreal.SkeletalMaterial)

    skeletal_material: unreal.SkeletalMaterial
    for skeletal_material in asset.get_editor_property('materials'):

        # to preserve imported_material_slot_name
        copy: unreal.SkeletalMaterial = skeletal_material.copy()

        imported_material_slot_name = str(skeletal_material.get_editor_property('imported_material_slot_name'))

        for new_material in materials:

            material_name = str(new_material.get_name()).split('_', maxsplit=1)[1]

            if material_name == imported_material_slot_name:
                copy.set_editor_property('material_slot_name', imported_material_slot_name)
                copy.set_editor_property('material_interface', new_material)
                break

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

    material_definitions: list = ()
    has_custom_collisions: bool = False

    skeleton_asset_path: str = ''


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
    options.set_editor_property('static_mesh_import_data', import_data)
    import_data.set_editor_property('combine_meshes', True)
    import_data.set_editor_property('auto_generate_collision', not settings.has_custom_collisions)


    task = get_import_task(options, settings.fbx_path, settings.dist_dir, settings.dist_name)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])


    asset: unreal.StaticMesh = unreal.load_asset(settings._asset_path)

    materials = create_materials(settings.material_definitions, settings.dist_dir, is_skeletal = False)
    set_static_mesh_materials(asset, materials)

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
    options.set_editor_property('skeletal_mesh_import_data', import_data)


    task = get_import_task(options, settings.fbx_path, settings.dist_dir, settings.dist_name)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    asset: unreal.SkeletalMesh = unreal.load_asset(settings._asset_path)

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
    import_data.set_editor_property('import_uniform_scale', 100)
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
