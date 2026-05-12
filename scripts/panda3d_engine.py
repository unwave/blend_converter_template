import sys
import os
import json
import typing



from .. import configuration


from blend_converter import tool_settings


if typing.TYPE_CHECKING:
    from blend_converter.blender import bpy_export


if 'panda3d' in sys.modules:
    from panda3d import core
    from panda3d import bullet


if 'bpy' in sys.modules:
    import bpy
    from blend_converter.blender import bpy_utils


if typing.TYPE_CHECKING:
    import dataclasses
else:
    class dataclasses:
        dataclass = lambda x: x


COLLISION_SHAPE_DATA = '__bc_collision_shape_data'

class Collision_Shape_Data:
    MASS = 'mass'
    """ Used only for compound shape type. """

    X = 'x'
    Y = 'y'
    Z = 'z'
    RADIUS = 'radius'
    HEIGHT = 'height'


OBJECT_TYPE = '__bc_blender_object_type'

class Object_Type:
    CURVE = 'CURVE'
    NURBS = 'NURBS'

CURVE_DATA = '__bc_curves_data'

class Curve_Data:
    ORDER = 'order'
    KNOTS = 'knots'
    POINTS = 'points'


class Bam_Edit:


    def __init__(self, bam_path: str):
        self.bam_path = bam_path


    def __enter__(self):

        # If panda3d.bullet is not imported in the editing process the bam will be written with losses.
        from panda3d import core
        from panda3d import bullet

        loader: core.Loader = core.Loader.get_global_ptr()
        flags = core.LoaderOptions(core.LoaderOptions.LF_no_cache)

        bam_path = core.Filename.from_os_specific(self.bam_path)
        panda_node = loader.load_sync(bam_path, flags)

        self.root_node = core.NodePath(panda_node)

        return self.root_node


    def __exit__(self , type, value, traceback):

        from panda3d import core

        is_success = self.root_node.write_bam_file(core.Filename.from_os_specific(self.bam_path))
        if not is_success:
            raise Exception(f'Error writing file: {self.bam_path}')


def assign_curve_placeholders():
    """ Collect curves data information to be late recrated inside panda3d."""

    for object in bpy_utils.get_view_layer_objects():

        if not isinstance(object.data, bpy.types.Curve):
            continue

        object[OBJECT_TYPE] = object.type

        splines = []

        for spline in object.data.splines:

            if spline.type not in (Object_Type.NURBS,):
                raise NotImplementedError(f"Not supported curve type: {spline.type} in {object}")

            knots_num = spline.point_count_u + spline.order_u
            knots = [i/(knots_num - 1) for i in range(knots_num)]

            if spline.use_endpoint_u:

                for i in range(spline.order_u - 1):
                    knots[i] = 0.0
                    knots[-(i + 1)] = 1.0

                for i in range(knots_num - (spline.order_u * 2) + 2):
                    knots[i + spline.order_u - 1] = i/(knots_num - (spline.order_u * 2) + 1)

            splines.append({
                Curve_Data.ORDER: spline.order_u,
                Curve_Data.KNOTS: knots,
                Curve_Data.POINTS: [tuple(point.co) for point in spline.points],  # type: ignore[reportArgumentType]
            })

        object[CURVE_DATA] = json.dumps(splines)


def assign_collision_placeholders():

    for object in bpy_utils.get_view_layer_objects():


        collision_object_type = object.get(configuration.ATOOL_COLLISION_OBJECT_PROP_KEY)
        if not collision_object_type:
            continue

        bpy_utils.focus(object)
        bpy.ops.object.make_single_user(object=True, obdata=True)
        object.rotation_mode = 'XYZ'

        object[configuration.COLLISION_IDENTIFIER_PROP_KEY] = collision_object_type

        if object.type in bpy_utils.TO_MESH_COMPATIBLE_OBJECT_TYPES:
            bpy_utils.convert_to_mesh(object)
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

            vertices = object.data.vertices

            object[COLLISION_SHAPE_DATA] = json.dumps({
                Collision_Shape_Data.MASS: object.get(configuration.ATOOL_COLLISION_MASS_PROP_KEY, 0),
                Collision_Shape_Data.X: vertices[0].co[0] * 2,
                Collision_Shape_Data.Y: vertices[1].co[1] * 2,
                Collision_Shape_Data.Z: vertices[2].co[2] * 2,
                Collision_Shape_Data.RADIUS: max(vertices[0].co[0], vertices[1].co[1]),
                Collision_Shape_Data.HEIGHT: vertices[2].co[2] * 2,
            })

        # compound collision shapes
        else:
            object[COLLISION_SHAPE_DATA] = json.dumps(dict(
                mass = object.get(configuration.ATOOL_COLLISION_MASS_PROP_KEY, 0),
            ))



def convert_curve_placeholders(filepath: str):
    with Bam_Edit(filepath) as root:
        _convert_curve_placeholders(root)


def _convert_curve_placeholders(node_path: 'core.NodePath'):

    for placeholder_np in node_path.find_all_matches(f'={OBJECT_TYPE}={Object_Type.CURVE}'):

        assert len(placeholder_np.children) == 0

        curve_data = json.loads(placeholder_np.get_tag(CURVE_DATA))

        for spline in curve_data:

            curve = core.NurbsCurve()

            curve.set_order(spline[Curve_Data.ORDER])

            for point in spline[Curve_Data.POINTS]:
                curve.append_cv(core.LVector4f(*point))

            for index, knot in enumerate(spline[Curve_Data.KNOTS]):
                curve.set_knot(index, knot)

            curve.recompute()

            placeholder_np.parent.attach_new_node(curve)

        placeholder_np.remove_node()


def get_bullet_shape(node_path: 'core.NodePath'):
    """ Gets the result of an export of `.blend` -> `.gltf` -> `.bam` for a shape place holder and constructs a panda3d bullet shape. """

    type = node_path.get_tag(configuration.COLLISION_IDENTIFIER_PROP_KEY)
    data = json.loads(node_path.get_tag(COLLISION_SHAPE_DATA))

    if type == configuration.Atool_Collision_Shape.SPHERE:
        shape = bullet.BulletSphereShape(radius=data[Collision_Shape_Data.RADIUS])
    elif type == configuration.Atool_Collision_Shape.BOX:
        shape = bullet.BulletBoxShape(halfExtents=(data[Collision_Shape_Data.X]/2, data[Collision_Shape_Data.Y]/2, data[Collision_Shape_Data.Z]/2))
    elif type == configuration.Atool_Collision_Shape.CYLINDER:
        shape = bullet.BulletCylinderShape(radius=data[Collision_Shape_Data.RADIUS], height=data[Collision_Shape_Data.HEIGHT])
    elif type == configuration.Atool_Collision_Shape.CAPSULE:
        shape = bullet.BulletCapsuleShape(radius=data[Collision_Shape_Data.RADIUS], height=data[Collision_Shape_Data.HEIGHT])
    elif type == configuration.Atool_Collision_Shape.CONE:
        shape = bullet.BulletConeShape(radius=data[Collision_Shape_Data.RADIUS], height=data[Collision_Shape_Data.HEIGHT])

    elif type == configuration.Atool_Collision_Shape.MESH:

        mesh_shape = bullet.BulletTriangleMesh()
        for geom_np in node_path.find_all_matches('**/+GeomNode'):
            for geom in geom_np.node().get_geoms():
                mesh_shape.add_geom(geom)

        shape = bullet.BulletTriangleMeshShape(mesh_shape, dynamic=False)

    elif type == configuration.Atool_Collision_Shape.CONVEX_HULL:

        shape = bullet.BulletConvexHullShape()
        for geom_np in node_path.find_all_matches('**/+GeomNode'):
            for geom in geom_np.node().get_geoms():
                shape.add_geom(geom)

    else:
        raise NotImplementedError(f"Not expected collision shape: {type}")

    return shape


def convert_collision_placeholders(filepath: str):
    with Bam_Edit(filepath) as root:
        _convert_collision_placeholders(root)


def _convert_collision_placeholders(node_path: 'core.NodePath'):
    """ Find and replace all compound shape placeholders with BulletRigidBodyNode. """

    for compound_shape_np in node_path.find_all_matches(f'**/={configuration.COLLISION_IDENTIFIER_PROP_KEY}={configuration.Atool_Collision_Shape.COMPOUND};+h+s'):

        shapes: typing.List[bullet.BulletShape] = []
        shape_transforms: typing.List[core.TransformState] = []

        for shape_np in compound_shape_np.find_all_matches(f'**/={configuration.COLLISION_IDENTIFIER_PROP_KEY};+h+s'):

            shape = get_bullet_shape(shape_np)

            shape_transforms.append(shape_np.get_transform(compound_shape_np))
            shapes.append(shape)

            shape_np.remove_node()

        if not shapes:
            shapes = [bullet.BulletBoxShape(core.Vec3(0.5, 0.5, 0.5))]

        bullet_node = bullet.BulletRigidBodyNode(compound_shape_np.name)
        collision_shape_center = compound_shape_np.get_pos()

        for shape, shape_transform in zip(shapes, shape_transforms):
            xform = shape_transform.set_pos(shape_transform.get_pos() - collision_shape_center)
            bullet_node.add_shape(shape, xform = xform)

        compound_shape_data = json.loads(compound_shape_np.get_tag(COLLISION_SHAPE_DATA))
        bullet_node.set_mass(compound_shape_data[Collision_Shape_Data.MASS])

        bullet_node_np = core.NodePath(bullet_node)
        bullet_node_np.set_pos(collision_shape_center)
        bullet_node_np.reparent_to(compound_shape_np.parent)

        for child in compound_shape_np.children:
            child.reparent_to(bullet_node_np)

        bullet_node.copy_tags(compound_shape_np.node())

        compound_shape_np.remove_node()



@dataclasses.dataclass
class S_Gltf_2_Bam(tool_settings.Settings):
    """ `panda3d-gltf`'s .gltf to .bam settings """


    collision_shapes: str = 'builtin'
    """
    The physics engine to build collision solids for: `'builtin'` or `'bullet'`.

    #### Default: `'builtin'`
    `cmd`: `--collision-shapes`
    """

    print_scene: bool = False
    """
    Print the converted scene graph to stdout.

    #### Default: `False`
    `cmd`: `--print-scene`
    """

    skip_axis_conversion: bool = False
    """
    Do not perform axis-conversion (useful if glTF data is already Z-Up).

    #### Default: `False`
    `cmd`: `--skip-axis-conversion`
    """

    no_srgb: bool = False
    """
    Do not load textures as sRGB textures (only for glTF pipelines).

    If `False`: do not load textures as sRGB.

    #### Default: `False`
    `cmd`: `--no-srgb`
    """

    textures: str = 'ref'
    """
    How to handle external textures: `'ref'` or `'copy'`.

    * `ref`: ref — reference external textures
    * `copy`: copy — copy textures

    embedded textures will remain embedded

    #### Default: `'ref'`
    `cmd`: `--textures`
    """

    legacy_materials: bool = False
    """
    If `False`, use PBR materials.

    #### Default: `False`
    `cmd`: `--legacy-materials`
    """

    animations: str = 'embed'
    """
    How to handle animation data: `'embed'` or `'separate'` or `'skip'`.

    If `embed`: keep animations in the same BAM file.

    #### Default: `'embed'`
    `cmd`: `--animations`
    """

    flatten_nodes: bool = False
    """
    Attempt to flatten resulting node structure.

    #### Default: `False`
    `cmd`: `--flatten-nodes`
    """

    invisible_collisions_collection: str = 'InvisibleCollisions'
    """
    Name of a collection in blender whose collision objects will be exported without a visible geom node.

    #### Default: `'InvisibleCollisions'`
    """


    def _get_cli_command(self):

        command: typing.List[str] = []

        for key, value in self.items():

            spec = self._get_attribute_spec(key)

            cmd = spec.cmd
            if cmd is None:
                continue

            if isinstance(value, bool):
                if value:
                    command.append(cmd)
            elif isinstance(value, str):
                command.append(cmd)
                command.append(value)
            else:
                raise Exception(f"Unexpected attribute: {key} {value}")

        return command


def get_gltf_settings():

    from blend_converter.blender import bpy_export

    return bpy_export.S_GLTF(
        export_tangents = True,
        export_cameras = True,
        export_extras = True,
        export_yup = False,
        export_apply = True,
        export_force_sampling = True,
        export_lights = True,
    )


def export_physics(gltf_data, invisible_collisions_collection: str):
    """ https://github.com/Moguri/blend2bam/blob/master/blend2bam/blend2gltf/blender28_script.py """

    physics_extensions = ['BLENDER_physics', 'PANDA3D_physics_collision_shapes']
    gltf_data.setdefault('extensionsUsed', []).extend(physics_extensions)


    objs = [
        (bpy.data.objects[gltf_node['name']], gltf_node)
        for gltf_node in gltf_data['nodes']
        if gltf_node['name'] in bpy.data.objects
    ]

    objs = [
        i for i in objs
        if getattr(i[0], 'rigid_body')
    ]

    for obj, gltf_node in objs:
        if 'extensions' not in gltf_node:
            gltf_node['extensions'] = {}

        rbody = obj.rigid_body
        bounds = [obj.dimensions[i] / gltf_node.get('scale', (1, 1, 1))[i] for i in range(3)]
        collision_layers = sum(layer << i for i, layer in enumerate(rbody.collision_collections))
        shape_type = rbody.collision_shape.upper()
        if shape_type in ('CONVEX_HULL', 'MESH'):
            meshrefs = [idx for idx, mesh in enumerate(gltf_data.get('meshes', ())) if mesh['name'] == obj.data.name]
            if not meshrefs:
                continue
            meshref = meshrefs[0]
        else:
            meshref = None

        # BLENDER_physics
        physics = {
            'collisionShapes': [{
                'shapeType': shape_type,
                'boundingBox': bounds,
                'primaryAxis': "Z",
            }],
            'mass': rbody.mass,
            'static': rbody.type == 'PASSIVE',
            'collisionGroups': collision_layers,
            'collisionMasks': collision_layers,
        }
        if meshref is not None:
            physics['collisionShapes'][0]['mesh'] = meshref
        gltf_node['extensions']['BLENDER_physics'] = physics

        # PANDA3D_physics_collision_shapes
        collision_shapes = {
            'shapes': [{
                'type': shape_type,
                'boundingBox': bounds,
                'primaryAxis': "Z",
            }],
            'groups': collision_layers,
            'masks': collision_layers,
            'intangible': rbody.type == 'PASSIVE',
        }
        if meshref is not None:
            collision_shapes['shapes'][0]['mesh'] = meshref
        gltf_node['extensions']['PANDA3D_physics_collision_shapes'] = collision_shapes

        # Remove the visible mesh from the gltf_node if the object
        # is in a specific collection
        if any(x.name == invisible_collisions_collection for x in obj.users_collection) and "mesh" in gltf_node:
            del gltf_node["mesh"]


def get_block_realpath(block: 'typing.Union[bpy.types.Image, bpy.types.Library]'):
    return os.path.realpath(bpy.path.abspath(block.filepath, library = block.library))


def get_image_path(name):

    # TODO: what if image is from a library
    image = bpy.data.images.get(name)

    if not image:
        return None

    if image.source != 'FILE':
        return None

    return os.path.realpath(bpy.path.abspath(image.filepath, library = image.library))


def validate_image_paths(gltf_data: dict, gltf_path: str):

    from urllib.parse import unquote, quote

    gltf_dir = os.path.dirname(gltf_path)

    for img in gltf_data.get('images', ()):

        path = get_image_path(img['name'])
        if not path:
            print(f"No Blender image for the image by name: {img}")
            continue

        uri = img.get('uri')
        if uri:
            path_from_uri = os.path.abspath(os.path.join(gltf_dir, unquote(uri).replace('/', os.sep)))
            try:
                os.path.samefile(path, path_from_uri)
            except Exception as e:
                raise Exception(f"{path} and {path_from_uri} are different files or do not exist.") from e

        try:
            # https://github.com/Moguri/panda3d-gltf/blob/95e2621d21792d522b5c939251f07a01259ffd69/gltf/cli.py#L121
            # converter = Converter(src, settings=settings)
            # https://github.com/Moguri/panda3d-gltf/blob/95e2621d21792d522b5c939251f07a01259ffd69/gltf/_converter.py#L133
            # self.filedir = Filename(filepath.get_dirname())
            # https://github.com/Moguri/panda3d-gltf/blob/95e2621d21792d522b5c939251f07a01259ffd69/gltf/_converter.py#L611
            # fulluri = Filename(self.filedir, uri)
            # path = os.path.relpath(path, gltf_dir)
            path = os.path.abspath(path)
        except ValueError as e:
            raise Exception(f"The image path must be relative to the glTF file: {path} {gltf_dir}") from e

        img['uri'] = quote(path)


def export_gltf(filepath: str, gltf_settings: 'bpy_export.S_GLTF', gltf2bam_settings: S_Gltf_2_Bam):

    result_dir = os.path.dirname(filepath)
    os.makedirs(result_dir, exist_ok=True)

    rna_type = bpy.ops.export_scene.gltf.get_rna_type()
    export_options_keys = rna_type.properties.keys()
    export_format_options = [item.identifier for item in rna_type.properties['export_format'].enum_items_static]


    from blend_converter.blender import bpy_export

    gltf_settings = bpy_export.S_GLTF._from_dict(gltf_settings)
    gltf2bam_settings = S_Gltf_2_Bam._from_dict(gltf2bam_settings)


    gltf_settings.export_animations = gltf2bam_settings.animations != 'skip'


    if gltf2bam_settings.textures == 'embed':
        if 'GLTF_EMBEDDED' in export_format_options:
            gltf_settings.export_format = 'GLTF_EMBEDDED'
        else:
            gltf_settings.export_format = 'GLTF_SEPARATE'
            print("GLTF_EMBEDDED option is not supported.")
    else:
        gltf_settings.export_format = 'GLTF_SEPARATE'


    if 'export_keep_originals' in export_options_keys:
        gltf_settings.export_keep_originals = gltf2bam_settings.textures == 'ref'
    if 'use_mesh_edges' in export_options_keys:
        gltf_settings.use_mesh_edges = True
    if 'use_mesh_vertices' in export_options_keys:
        gltf_settings.use_mesh_vertices = True
    if 'export_optimize_animation_size' in export_options_keys:
        gltf_settings.export_optimize_animation_size = False
    if 'convert_lighting_mode' in export_options_keys:
        gltf_settings.convert_lighting_mode = 'RAW'
    if 'export_import_convert_lighting_mode' in export_options_keys:
        gltf_settings.export_import_convert_lighting_mode = 'RAW'
    if 'export_try_sparse_sk' in export_options_keys:
        gltf_settings.export_try_sparse_sk = False


    if 'export_keep_originals' in export_options_keys:

        # case if the setting are getting updated
        if gltf2bam_settings.textures == 'ref' and gltf_settings.export_keep_originals == False:
            message = "Cannot reference textures that will being deleted with the temporal glTF file when `export_keep_originals == False`. When `export_keep_originals == False` use `textures == 'copy'`."
            print('Warning:', message)
            gltf_settings.export_keep_originals = True
            # raise Exception(message)


        if gltf_settings.export_keep_originals or gltf2bam_settings.textures == 'ref':
            for image in bpy.data.images:
                if image.filepath:
                    try:
                        os.path.relpath(os.path.realpath(filepath), get_block_realpath(image))
                    except ValueError as e:
                        gltf_settings.export_keep_originals = False
                        gltf2bam_settings.textures = 'copy'
                        message = f"Cannot export a gltf keeping an original image with no possible relative path to the gltf file being written: {image} {image.filepath}"
                        print('Warning:', message)
                        # raise Exception(message) from e


    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter('default')

        print("GLTF:", gltf_settings)

        bpy.ops.export_scene.gltf(filepath = filepath, **gltf_settings)


    with open(filepath) as gltf_file:
        gltf_data = json.load(gltf_file)

    export_physics(gltf_data, gltf2bam_settings.invisible_collisions_collection)

    if gltf2bam_settings.textures in ('ref', 'copy'):
        validate_image_paths(gltf_data, filepath)

    with open(filepath, 'w') as gltf_file:
        json.dump(gltf_data, gltf_file)



def run_gltf2bam(gltf_path: str, bam_path: str, settings: S_Gltf_2_Bam, executable = 'gltf2bam'):

    command = [executable, gltf_path, bam_path, *S_Gltf_2_Bam._from_dict(settings)._get_cli_command()]

    from blend_converter import utils
    print("CLI:", utils.get_command_from_list(command))

    import subprocess
    subprocess.run(command, check=True)
