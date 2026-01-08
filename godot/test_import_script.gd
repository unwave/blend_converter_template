@tool
extends EditorScenePostImport


func _post_import(scene: Node) -> Object:

    print("hello world")
    
    
    var static_body = StaticBody3D.new()

    static_body.name = 'StaticBody3D'
    
    scene.add_child(static_body)
    static_body.owner = scene


    var static_meshes = scene.find_children("COL_*", "", true)

    

    for mesh in static_meshes:

        var shape = mesh.get_child(0)

        var transform = shape.transform

        shape.reparent(static_body)
        shape.owner = scene

        shape.transform = mesh.transform

        shape.name = 'CollisionShape3D'

        mesh.queue_free()

    
    return scene
