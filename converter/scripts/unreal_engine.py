import os
import sys
import typing
import time


ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if not ROOT in sys.path:
    sys.path.append(ROOT)


import configuration


if 'bpy' in sys.modules:
    import bpy
    from blend_converter.blender import bpy_utils


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

    object = bpy_utils.get_view_layer_objects()[0]

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


    for material_slot in object.material_slots:

        assert material_slot.material
        assert material_slot.material.node_tree

        definition = {}
        definition['textures'] = textures = {}

        material = material_slot.material

        name = ensure_unique_name(configuration.get_ascii_underscored(material.name))
        definition['name'] = name

        tree = bpy_node.Shader_Tree_Wrapper(material.node_tree)

        principled =  tree.output[0]

        node = next((node for node in principled.inputs['Base Color'].descendants if node.be('ShaderNodeTexImage')), None)
        if node:
            textures['base_color'] = bpy_utils.get_block_abspath(node.image)
        else:
            textures['base_color'] = None

        node = next((node for node in principled.inputs['Metallic'].descendants if node.be('ShaderNodeTexImage')), None)
        if node:
            textures['orm'] = bpy_utils.get_block_abspath(node.image)
        else:
            textures['orm'] = None

        node = next((node for node in principled.inputs['Normal'].descendants if node.be('ShaderNodeTexImage')), None)
        if node:
            textures['normal'] = bpy_utils.get_block_abspath(node.image)
        else:
            textures['normal'] = None


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

    return unreal.load_asset(unreal.Paths.combine([ue_dir, dest_ue_name]))


def is_in_memory_asset(asset_path: str):
    """ For debugging. """
    asset_registry: unreal.AssetRegistry = unreal.AssetRegistryHelpers.get_asset_registry()
    asset_registry.scan_files_synchronous([asset_path], force_rescan=True)
    return asset_registry.get_asset_by_object_path(asset_path, include_only_on_disk_assets=True) == asset_registry.get_asset_by_object_path(asset_path, include_only_on_disk_assets=False)



@dataclasses.dataclass
class Settings_Unreal_Material_Instance(tool_settings.Settings):

    # https://forums.unrealengine.com/t/setting-static-switch-parameters-of-a-material-instance-in-python/136415
    # have a problem with child material instances not respecting static switches in ES 3.1
    PARENT_MATERIAL = '/Game/Materials/base/M_main_orm'
    PARENT_MATERIAL_WITHOUT_NORMALS = '/Game/Materials/base/M_main_orm_no_normal'


    name: str = ''
    dir: str = ''

    base_color_filepath: str = ''
    _base_color_param_name: str = 'Base Color'

    orm_filepath: str = ''
    _orm_param_name: str = 'ORM'

    normal_filepath: str = ''
    _normal_param_name: str = 'Normal'

    # not implemented
    # emission_filepath: str = ''
    # _emission_param_name: str = 'Emission'

    is_alpha: bool = False


    @property
    def _asset_path(self):
        return unreal.Paths.combine([self.dir, self.name])


def create_material_instance(settings: Settings_Unreal_Material_Instance):

    unreal.EditorAssetLibrary.make_directory(settings.dir)

    if is_in_memory_asset(settings._asset_path):
        raise Exception(f"In memory asset, restart Unreal Engine: {settings._asset_path}")  # TODO: testing


    do_replace = unreal.EditorAssetLibrary.does_asset_exist(settings._asset_path)
    if do_replace:
        asset_name = settings.name + f"_TEMP_{time.strftime('%Y%m%d_%H%M%S')}"
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


    if settings.normal_filepath:
        material_instance.set_editor_property('parent', unreal.load_asset(settings.PARENT_MATERIAL))

        normal_texture = import_texture(settings.normal_filepath, settings.dir)
        normal_texture.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_NORMALMAP)
        normal_texture.set_editor_property('flip_green_channel', True)
        normal_texture.set_editor_property('srgb', False)  # ensuring that the pre/post change notifications are called
        unreal.EditorAssetLibrary.save_asset(normal_texture.get_full_name())
        unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(material_instance, settings._normal_param_name, normal_texture)
    else:
        material_instance.set_editor_property('parent', unreal.load_asset(settings.PARENT_MATERIAL_WITHOUT_NORMALS))

    if settings.base_color_filepath:
        base_color_texture = import_texture(settings.base_color_filepath, settings.dir)
        base_color_texture.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_DEFAULT)
        unreal.EditorAssetLibrary.save_asset(base_color_texture.get_full_name())
        unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(material_instance, settings._base_color_param_name, base_color_texture)

    if settings.orm_filepath:
        orm_texture = import_texture(settings.orm_filepath, settings.dir)
        orm_texture.set_editor_property('compression_settings', unreal.TextureCompressionSettings.TC_MASKS)
        orm_texture.set_editor_property('srgb', False)  # ensuring that the pre/post change notifications are called
        unreal.EditorAssetLibrary.save_asset(orm_texture.get_full_name())
        unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(material_instance, settings._orm_param_name, orm_texture)


    # if settings.emission_filepath:
    #     texture = import_texture(settings.emission_filepath, settings.dir)
    #     texture.compression_settings = unreal.TextureCompressionSettings.TC_DEFAULT
    #     unreal.MaterialEditingLibrary.set_material_instance_texture_parameter_value(material_instance, settings.orm_param_name, texture)
    # else:
    #     unreal.MaterialEditingLibrary.set_material_instance_static_switch_parameter_value(material_instance, settings.use_emission_param_name, False)


    unreal.EditorAssetLibrary.save_asset(material_instance.get_full_name())

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


def set_materials(asset, material_definitions, material_name: str, result_dir: str):

    materials_settings = []

    for definition in material_definitions:

        materials_settings.append(
            Settings_Unreal_Material_Instance(
                name = 'MI_' + definition['name'],
                dir = result_dir,
                base_color_filepath = definition['textures']['base_color'],
                orm_filepath = definition['textures']['orm'],
                normal_filepath =  definition['textures']['normal'],
                is_alpha = definition['is_alpha'],
            )
        )

    materials = [create_material_instance(material_settings) for material_settings in materials_settings]

    if isinstance(asset, unreal.StaticMesh):
        for index, material in enumerate(materials):
            unreal.StaticMesh.set_material(asset, index, material)

    elif isinstance(asset, unreal.SkeletalMesh):
        raise NotImplementedError()



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

    set_materials(asset, settings.material_definitions, settings.dist_name, settings.dist_dir)

    unreal.EditorAssetLibrary.save_asset(asset.get_full_name())

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

    set_materials(asset, settings.material_definitions, settings.dist_name, settings.dist_dir)

    unreal.EditorAssetLibrary.save_asset(asset.get_full_name())

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

    options.set_editor_property('skeleton', unreal.load_asset(settings._asset_path))

    # import_data = get_animation_import_data(settings._asset_path)
    # options.set_editor_property('anim_sequence_import_data', import_data)

    task = get_import_task(options, settings.fbx_path, settings.dist_dir, settings.dist_name)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    unreal.log(f"Animation Sequence imported: {settings}")
