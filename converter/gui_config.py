import typing


if not hasattr(typing, 'Literal'):
    import typing_extensions
    typing.Literal = typing_extensions.Literal


from blend_converter import common


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
