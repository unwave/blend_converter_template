import os
import sys
import typing
import re

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if not ROOT in sys.path:
    sys.path.append(ROOT)

import configuration


if 'bpy' in sys.modules:
    import bpy


def add_export_timestamp():
    """
    To ensure the Godot re-import will be triggered.

    When re-baking textures, the uv repacking is different and the textures are getting re-imported, but not the model, because only `.bin` file is changing, not the `.gltf`.

    #### This requires `export_extras` to be `True`.

    https://github.com/godotengine/godot/issues/90659
    https://github.com/godotengine/godot/issues/105499
    """

    import datetime
    import uuid

    bpy.context.scene['export_datetime_now'] = datetime.datetime.now().astimezone().isoformat(' ', 'seconds')
    bpy.context.scene['export_uuid'] = str(uuid.uuid1())


def set_gd_import_script(gltf_path: str, script_path: str):

    import_name = gltf_path + '.import'

    param = f'import_script/path="{script_path}"'
    re_param = re.compile(r'^import_script\/path=.+')

    if os.path.exists(import_name):

        lines = []

        needs_write = False

        with open(import_name, 'r') as f:

            for line in f.readlines():

                if re_param.match(line):

                    if line.startswith(param):
                        lines.append(line)
                    else:
                        needs_write = True
                        lines.append(param + '\n')
                else:
                    lines.append(line)

        if needs_write:

            with open(import_name + '@', 'w') as f:
                f.write(''.join(lines))

            os.replace(import_name + '@', import_name)

    else:

        with open(import_name, 'w') as f:
            f.write('[params]' + '\n' + param + '\n')


def rename_objects_for_godot(prefix: str):
    """
    Match the recommended FBX naming conventions. In order to make the collision shape recognition to work.
    https://dev.epicgames.com/documentation/en-us/unreal-engine/fbx-static-mesh-pipeline-in-unreal-engine?application_version=5.5#collision
    """

    for index, top_layer in enumerate(bpy.context.view_layer.layer_collection.children, start = 1):

        name = prefix + '_' + configuration.get_ascii_underscored(top_layer.name) + f'_{str(index).zfill(2)}'

        collision_index = 1

        for object in top_layer.collection.all_objects:

            if object.get(configuration.UNREAL_COLLISION_PROP_KEY):
                object.name = f'COL_{top_layer.name}_{str(collision_index).zfill(2)}-convcolonly'
                collision_index += 1
            else:
                object.name = name
