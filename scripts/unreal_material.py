import os
import sys
import typing
import uuid
import functools


from . import unreal_engine
from .. import configuration

from blend_converter import utils as bc_utils



if 'bpy' in sys.modules:

    import bpy

    from blend_converter.blender import bpy_utils
    from blend_converter.blender import bpy_material



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
            if node.be('ShaderNodeTexImage'):

                if not node.image:
                    continue

                if node.image.source != 'FILE':
                   continue

                if not node.image.filepath:
                    continue

                filepath = bpy_utils.get_block_abspath(node.image)

                if not os.path.exists(filepath):
                    continue

                if not os.path.isfile(filepath):
                    continue

                return filepath

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
    bpy_material.convert_materials_to_principled([object])
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


def sanitize_material_names():
    """ To satisfy Unreal's asset naming requirement. """

    for material in bpy.data.materials:

        sanitized_name = configuration.get_ascii_underscored(material.name)

        if sanitized_name == material.name:
            continue

        name = sanitized_name
        index = 2
        while name in bpy.data.materials:
            name = sanitized_name + f'_{index}'

        material.name = name


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
    task.save = False

    task.filename = os_path
    task.destination_path = ue_dir
    task.destination_name = dest_ue_name

    factory = unreal.TextureFactory()

    task.factory = factory
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    asset: unreal.Texture = unreal_engine.get_task_assets(task)[0]

    for key, value in editor_property.items():
        asset.set_editor_property(key, value)

    unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty = False)

    return asset



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

    if unreal_engine.is_in_memory_asset(asset_path):
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
            unreal_engine.show_nt_message('Static switch not set!', message)
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
            unreal_engine.show_nt_message('Static switch not set!', message)
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

    imported_skeletal_materials: typing.Dict[str, unreal.SkeletalMaterial] = {str(m.get_editor_property('imported_material_slot_name')): m for m in asset.get_editor_property('materials')}

    for imported_material_slot_name, imported_skeletal_material in imported_skeletal_materials.items():

        new_material = materials.get(imported_material_slot_name)
        if not new_material:
            print(f"Material does not exist: {imported_material_slot_name}")
            continue

        # to preserve imported_material_slot_name
        copy: unreal.SkeletalMaterial = imported_skeletal_material.copy()

        copy.set_editor_property('material_slot_name', imported_material_slot_name)
        copy.set_editor_property('material_interface', new_material)

        array.append(copy)

    asset.set_editor_property('materials', array)
