import bpy
for ob in bpy.data.objects:
    if ob.type != "MESH":
        continue
    print("[OBJ]", ob.name, "verts", len(ob.data.vertices), "shape keys", len(ob.data.shape_keys.key_blocks) if ob.data.shape_keys else 0)
    for s in ob.material_slots:
        m = s.material
        if not m or not m.use_nodes:
            continue
        print("   [MAT]", m.name, "method", getattr(m, "surface_render_method", "?"))
        for n in m.node_tree.nodes:
            if n.type == "GROUP":
                ins = [(i.name, tuple(round(x, 3) for x in i.default_value) if hasattr(i, "default_value") and hasattr(i.default_value, "__len__") else getattr(i, "default_value", None)) for i in n.inputs if not i.is_linked]
                print("      [GROUP]", n.node_tree.name, ins[:30])
            if n.type == "TEX_IMAGE" and n.image:
                print("      [IMG]", n.image.name, n.image.size[:], "alpha-linked", any(l.from_socket.name == "Alpha" for l in m.node_tree.links if l.from_node == n))
print("[EXPR]", [p for p in dir(__import__("bl_ext.user_default.mpfb.services.faceservice", fromlist=["x"]).FaceService) if not p.startswith("_")])
