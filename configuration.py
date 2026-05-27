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

    UNREAL_STATIC = '/Game/blend_converter/static/'
    UNREAL_SKELETAL = '/Game/blend_converter/skeletal/'
    UNREAL_ANIMATION = '/Game/blend_converter/animations/'



def get_folders(folder: os.PathLike):
    if os.path.exists(folder):
        return [file for file in os.scandir(folder) if file.is_dir() and not file.name.startswith('_')]
    else:
        return []


def get_blends(folder: os.PathLike):
    return [file for file in os.scandir(folder) if file.is_file() and not file.name.startswith('_') and file.name.endswith('.blend')]


def get_blend(folder: os.PathLike):
    return bc_utils.get_last_blend(folder)


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
