import typing


if not hasattr(typing, 'Literal'):
    import typing_extensions
    typing.Literal = typing_extensions.Literal


from blend_converter import common

class UV_Unwrap:

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


class Quality:

    preset: typing.Literal['manual', 'preview'] = 'manual'


class Config(common.Config_Base):

    quality: Quality

    uv_unwrap: UV_Unwrap
