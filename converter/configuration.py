import os
import typing
import re


from blend_converter import utils as bc_utils

BLENDER_EXECUTABLE = r'C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe'


def get_ascii_underscored(string: str):
    r"""
    For creating slag names in the Unreal Engine style.

    >A folder name may not contain any of the following characters: \:*?"<>l',.&!~@#/[]
    """

    string = re.sub(r'([A-Za-z0-9]+)(\d)', r'\1_\2', string)
    string = re.sub(r'(\d)([A-Za-z0-9]+)', r'\1_\2', string)
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

    BLEND_STATIC = os.path.join(ROOT, 'blends', 'static')
    BLEND_SKELETAL = os.path.join(ROOT, 'blends', 'skeletal')

    BLEND_RIG = os.path.join(ROOT, 'blends', 'rig')
    BLEND_ANIM = os.path.join(ROOT, 'blends', 'anim')

    BLEND_PROXY = os.path.join(ROOT, 'blends', 'proxy')

    INTERMEDIATE_BLEND_STATIC = os.path.join(ROOT, 'intermediate', 'blend', 'static')
    INTERMEDIATE_BLEND_SKELETAL = os.path.join(ROOT, 'intermediate', 'blend', 'skeletal')

    INTERMEDIATE_BLEND_SKIN_TEST = os.path.join(ROOT, 'intermediate', 'blend', 'skin_test')
    INTERMEDIATE_BLEND_SKIN_PROXY = os.path.join(ROOT, 'intermediate', 'blend', 'skin_proxy')

    GODOT_GLTF_STATIC = os.path.join(ROOT, 'godot', 'gltf', 'static')
    GODOT_GLTF_SKELETAL = os.path.join(ROOT, 'godot', 'gltf', 'skeletal')
    GODOT_GLTF_ANIMATION = os.path.join(ROOT, 'godot', 'gltf', 'animation')

    INTERMEDIATE_UNREAL_SM = os.path.join(ROOT, 'intermediate', 'unreal', 'SM')
    INTERMEDIATE_UNREAL_SK = os.path.join(ROOT, 'intermediate', 'unreal', 'SK')
    INTERMEDIATE_UNREAL_A = os.path.join(ROOT, 'intermediate', 'unreal', 'A')


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

COLLISION_IDENTIFIER_PROP_KEY = '__bc_collision_shape'
""" Collision shape types that would be used in this pipeline, matching the Atool's ones. """

UNREAL_COLLISION_PROP_KEY = '__bc_ue_collision_shape_type'
""" Prefixes of the Unreal Engine supported collision shape types. (UBX_, UCP_, USP_, UCX_) """
