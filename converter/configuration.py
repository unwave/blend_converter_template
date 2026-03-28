import os
import typing
import re


from blend_converter import utils as bc_utils


def get_ascii_underscored(string: str):
    r"""
    For creating slug names in the Unreal Engine style.

    >A folder name may not contain any of the following characters: \:*?"<>l',.&!~@#/[]
    """

    string = re.sub(r'([A-Za-z]+)(\d+)', r'\1_\2', string)
    string = re.sub(r'(\d+)([A-Za-z]+)', r'\1_\2', string)
    string = re.sub(r'([A-Z]+)([A-Z][a-z0-9])', r'\1_\2', string)
    string = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', string)
    string = re.sub(r'[^a-zA-Z0-9]+', '_', string)
    string = re.sub(r'_+', '_', string)
    string = string.strip('_')
    string = string.lower()
    string = bc_utils.ensure_valid_basename(string)
    return string


class Folder:

    ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


    ## blender source
    SCAN = os.path.join(ROOT, 'blends', 'scan')

    BLEND_STATIC = os.path.join(ROOT, 'blends', 'static')
    BLEND_SKELETAL = os.path.join(ROOT, 'blends', 'skeletal')

    BLEND_RIG = os.path.join(ROOT, 'blends', 'rig')
    BLEND_ANIMATION = os.path.join(ROOT, 'blends', 'animation')

    # blender intermediate
    INTERMEDIATE_SCAN = os.path.join(ROOT, 'intermediate', 'blends', 'scan')

    INTERMEDIATE_BLEND_STATIC = os.path.join(ROOT, 'intermediate', 'blends', 'static')
    INTERMEDIATE_BLEND_SKELETAL = os.path.join(ROOT, 'intermediate', 'blends', 'skeletal')

    INTERMEDIATE_BLEND_SKIN_TEST = os.path.join(ROOT, 'intermediate', 'blends', 'skin_test')
    INTERMEDIATE_BLEND_SKIN_PROXY = os.path.join(ROOT, 'intermediate', 'blends', 'skin_proxy')


    ## godot
    GODOT_GLTF_STATIC = os.path.join(ROOT, 'godot', 'gltf', 'static')
    GODOT_GLTF_SKELETAL = os.path.join(ROOT, 'godot', 'gltf', 'skeletal')
    GODOT_GLTF_ANIMATION = os.path.join(ROOT, 'godot', 'gltf', 'animation')


    ## unreal
    INTERMEDIATE_UNREAL_STATIC = os.path.join(ROOT, 'intermediate', 'unreal', 'static')
    INTERMEDIATE_UNREAL_SKELETAL = os.path.join(ROOT, 'intermediate', 'unreal', 'skeletal')
    INTERMEDIATE_UNREAL_ANIMATION = os.path.join(ROOT, 'intermediate', 'unreal', 'animation')

    UNREAL_STATIC = '/Game/blend_converter/static/'
    UNREAL_SKELETAL = '/Game/blend_converter/skeletal/'
    UNREAL_ANIMATION = '/Game/blend_converter/animation/'


    ## panda3d
    INTERMEDIATE_PANDA3D_STATIC = os.path.join(ROOT, 'intermediate', 'panda3d', 'static')
    INTERMEDIATE_PANDA3D_SKELETAL = os.path.join(ROOT, 'intermediate', 'panda3d', 'skeletal')
    INTERMEDIATE_PANDA3D_ANIMATION = os.path.join(ROOT, 'intermediate', 'panda3d', 'animation')

    PANDA3D_STATIC = os.path.join(ROOT, 'panda3d', 'blend_converter', 'static')
    PANDA3D_SKELETAL = os.path.join(ROOT, 'panda3d', 'blend_converter', 'skeletal')
    PANDA3D_ANIMATION = os.path.join(ROOT, 'panda3d', 'blend_converter', 'animation')



def get_folders(folder: os.PathLike):
    if os.path.exists(folder):
        return [file for file in os.scandir(folder) if file.is_dir() and not file.name.startswith('_')]
    else:
        return []


def get_blends(folder: os.PathLike):
    return [file for file in os.scandir(folder) if file.is_file() and not file.name.startswith('_') and file.name.endswith('.blend')]


IGNORE_PREFIX = ('#', '__bc')

ORIGIN_PREFIX = 'ORIGIN'


ATOOL_COLLISION_OBJECT_PROP_KEY = 'atool_collision_object_type'
""" The property name of collision shape type in the Atool addon. """

ATOOL_COLLISION_MASS_PROP_KEY = 'atool_collision_mass'

class Atool_Collision_Shape:
    SPHERE = 'SPHERE'
    BOX = 'BOX'
    CYLINDER = 'CYLINDER'
    CAPSULE = 'CAPSULE'
    CONE = 'CONE'
    MESH = 'MESH'
    CONVEX_HULL = 'CONVEX_HULL'
    COMPOUND = 'COMPOUND'


COLLISION_IDENTIFIER_PROP_KEY = '__bc_collision_shape'
""" Collision shape types that would be used in this pipeline, matching the Atool's ones. """

UNREAL_COLLISION_PROP_KEY = '__bc_ue_collision_shape_type'
""" Prefixes of the Unreal Engine supported collision shape types. (UBX_, UCP_, USP_, UCX_) """
