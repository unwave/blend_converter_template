from __future__ import annotations

import os
import typing
import re

from blend_converter import common
from blend_converter import utils as bc_utils

BLENDER_EXECUTABLE = r'C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe'
BLENDER_VERSION = (4, 4)


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

    GLTF_STATIC = os.path.join(ROOT, 'godot', 'gltf', 'static')
    GLTF_SKELETAL = os.path.join(ROOT, 'godot', 'gltf', 'skeletal')
    GLTF_ANIMATION = os.path.join(ROOT, 'godot', 'gltf', 'animation')

    INTERMEDIATE_UNREAL_SM = os.path.join(ROOT, 'intermediate', 'unreal', 'SM')
    INTERMEDIATE_UNREAL_SK = os.path.join(ROOT, 'intermediate', 'unreal', 'SK')
    INTERMEDIATE_UNREAL_A = os.path.join(ROOT, 'intermediate', 'unreal', 'A')


def get_folders(folder: os.PathLike):
    return [file for file in os.scandir(folder) if file.is_dir() and not file.name.startswith('_')]


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


class Blend_Bake:

    resolution_multiplier: float = 1.0

    bake_samples: int = 1

    uv_packer_pin: bool = False

    faster_ao_bake: bool = True

    texel_density: int = 512

    min_resolution: int = 128

    max_resolution: int = 4096


class UV_Unwrap:

    use_normal: bool = False

    stretch: bool = True

    timeout: int = 10

    separate_hard_edges = False


    bfu_preset: typing.Literal[

        'active_render',
        'mof_only',
        'just_unwrap',
        'default',

        ] = 'default'

    bfu_method: typing.Literal[
        'active_render',
        'active_render_minimal_stretch',

        'mof_default',
        'mof_separate_hard_edges',
        'mof_use_normal',

        'just_minimal_stretch',
        'just_conformal',

        'smart_project_reunwrap',
        'smart_project_conformal',

        'cube_project_reunwrap',
        'cube_project_conformal',

        'NONE',
        ] = 'NONE'


class Gltf_Export:

    export_animation_mode: typing.Literal['NLA_TRACKS', 'ACTIONS'] = 'ACTIONS'


class Quality:

    preset: typing.Literal['manual', 'preview'] = 'manual'


class Config(common.Config_Base):

    quality: Quality

    blend_bake: Blend_Bake

    gltf_export: Gltf_Export

    uv_unwrap: UV_Unwrap
