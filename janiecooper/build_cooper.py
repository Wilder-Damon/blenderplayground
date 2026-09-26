"""Cooper, a chocolate-tri English bulldog, in a stylised animated-film look.

Built from metaball volumes -> mesh, then sculpted with a few procedural passes
(forehead wrinkles, nose roll), coloured per region from the family's photos:
chocolate back and ears, white blaze/muzzle/jowls/chest/legs, tan brows and cheek edges,
pink tongue out, rust-orange corduroy cap. Rigged with a simple armature for walking.

Usage: blender --background --python build_cooper.py
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))

def meta_radius(visible, stiffness):
    """Metaball radius whose isosurface (threshold 0.6) alone sits at `visible`."""
    return visible / math.sqrt(1 - (0.6 / stiffness) ** (1 / 3))

# Cooper faces +Y, ground at z=0. (name, centre, visible radius, ellipsoid scale, stiffness)
BODY = [
    ("chest",     (0, 0.10, 0.232), 0.168, (1.12, 1.00, 0.92), 2.0),   # deep barrel chest
    ("shoulderL", (0.095, 0.12, 0.28), 0.095, (1.0, 1.0, 1.0), 2.0),
    ("shoulderR", (-0.095, 0.12, 0.28), 0.095, (1.0, 1.0, 1.0), 2.0),
    ("belly",     (0, -0.05, 0.245), 0.140, (1.05, 1.10, 0.80), 2.0),
    ("hips",      (0, -0.18, 0.262), 0.125, (1.00, 1.00, 0.95), 2.0),   # slight roach to the back
    ("thighL",    (0.085, -0.19, 0.21), 0.080, (0.9, 1.1, 1.1), 2.0),
    ("thighR",    (-0.085, -0.19, 0.21), 0.080, (0.9, 1.1, 1.1), 2.0),
    ("tail",      (0, -0.305, 0.30), 0.028, (1.0, 1.4, 1.0), 2.0),
    ("neck",      (0, 0.205, 0.325), 0.112, (1.30, 0.80, 0.90), 2.0),
]
HEAD = [
    ("cranium",   (0, 0.275, 0.425), 0.125, (1.38, 0.95, 0.85), 3.0),
    ("cheekL",    (0.10, 0.325, 0.37), 0.080, (1.0, 0.95, 1.0), 3.0),
    ("cheekR",    (-0.10, 0.325, 0.37), 0.080, (1.0, 0.95, 1.0), 3.0),
    ("muzzle",    (0, 0.365, 0.355), 0.068, (1.60, 0.62, 0.85), 3.0),
    ("jowlL",     (0.068, 0.375, 0.305), 0.058, (0.95, 0.80, 1.30), 3.0),
    ("jowlR",     (-0.068, 0.375, 0.305), 0.058, (0.95, 0.80, 1.30), 3.0),
    ("chin",      (0, 0.385, 0.285), 0.044, (1.50, 0.90, 0.80), 3.0),   # underbite: jaw forward
    ("browL",     (0.058, 0.36, 0.44), 0.038, (1.30, 0.70, 0.60), 3.0),
    ("browR",     (-0.058, 0.36, 0.44), 0.038, (1.30, 0.70, 0.60), 3.0),
    ("noseroll",  (0, 0.378, 0.398), 0.028, (2.30, 0.70, 0.60), 3.0),   # the wrinkle roll over the nose
]
LEGS = [  # (name, top, bottom, visible radius) - short, bowed-out front legs; chunky rear
    ("legFL", (0.135, 0.14, 0.18), (0.155, 0.17, 0.03), 0.042),
    ("legFR", (-0.135, 0.14, 0.18), (-0.155, 0.17, 0.03), 0.042),
    ("legBL", (0.095, -0.20, 0.19), (0.10, -0.185, 0.03), 0.040),
    ("legBR", (-0.095, -0.20, 0.19), (-0.10, -0.185, 0.03), 0.040),
]
PAWS = [(0.158, 0.19, 0.022), (-0.158, 0.19, 0.022), (0.10, -0.165, 0.022), (-0.10, -0.165, 0.022)]

# linear-space colours matched to the photos
CHOC  = (0.045, 0.018, 0.010)
CHOC2 = (0.075, 0.032, 0.016)   # lighter chocolate on the flanks (photo 3: lilac-chocolate sheen)
WHITE = (0.70, 0.66, 0.60)
TAN   = (0.30, 0.14, 0.055)
NOSE  = (0.035, 0.018, 0.018)
PINK  = (0.60, 0.13, 0.17)
CAP   = (0.22, 0.055, 0.010)

def region_colour(p):
    x, y, z = p
    ax = abs(x)
    face = y > 0.33
    if face and z < 0.375 and ax < 0.10:                       # white muzzle, jowls, chin
        return WHITE
    if y > 0.30 and ax < 0.017 + max(0.0, 0.395 - z) * 2.2 and z < 0.56:  # narrow blaze, widening only at the muzzle
        return WHITE
    if face and 0.03 < ax < 0.085 and 0.442 < z < 0.472:       # tan brow spots above the eyes
        return TAN
    if y > 0.28 and 0.095 < ax < 0.17 and 0.32 < z < 0.41:     # tan cheek edges
        return TAN
    if 0.05 < y < 0.34 and z < 0.34 and ax < 0.12:             # white bib / throat
        return WHITE
    if z < 0.13 or (y > 0.0 and z < 0.19):                     # white belly, front legs, feet
        return WHITE
    if y < -0.12 and z < 0.18:                                 # tan on the back of the rear legs
        return TAN
    if ax > 0.12 and z < 0.3:
        return CHOC2
    return CHOC

def build_body(coll):
    mb = bpy.data.metaballs.new("CooperMB")
    mb.resolution = 0.009; mb.render_resolution = 0.009; mb.threshold = 0.6
    def ell(c, r, s, st):
        e = mb.elements.new(); e.type = "ELLIPSOID"; e.co = c
        e.radius = meta_radius(r, st); e.size_x, e.size_y, e.size_z = s; e.stiffness = st
    for _, c, r, s, st in BODY + HEAD:
        ell(c, r, s, st)
    for _, top, bot, r in LEGS:
        top, bot = Vector(top), Vector(bot)
        for k in range(4):
            e = mb.elements.new(); e.type = "BALL"; e.co = top.lerp(bot, k / 3)
            e.radius = meta_radius(r, 2.0) * 0.8; e.stiffness = 2.0
    for c in PAWS:
        ell(c, 0.036, (1.0, 1.25, 0.6), 2.0)
    ob = bpy.data.objects.new("CooperMB", mb); coll.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob); bpy.data.metaballs.remove(mb)
    body = bpy.data.objects.new("Cooper", me); coll.objects.link(body)

    # sculpt: forehead wrinkles and a crease under the nose roll
    bm = bmesh.new(); bm.from_mesh(me)
    bm.normal_update()
    for v in bm.verts:
        x, y, z = v.co
        if y > 0.30 and v.normal.y > 0.2 and abs(x) < 0.13 and 0.435 < z < 0.53:
            w = (1 - abs(x) / 0.13) * min(1, (z - 0.435) / 0.02)
            v.co -= v.normal * 0.008 * w * max(0.0, math.sin((z - 0.435) / 0.022 * math.pi * 2 + x * 25))
        if y > 0.35 and abs(x) < 0.09 and 0.378 < z < 0.388:
            v.co -= v.normal * 0.010 * (1 - abs(x) / 0.09)
    # a few smoothing passes to relax the metaball facets
    for _ in range(1):
        bmesh.ops.smooth_vert(bm, verts=bm.verts, factor=0.35, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.to_mesh(me); bm.free()

    col = me.color_attributes.new("Coat", "FLOAT_COLOR", "POINT")
    cols = [Vector(region_colour(v.co)) for v in me.vertices]
    nbrs = [[] for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices
        nbrs[a].append(b); nbrs[b].append(a)
    for _ in range(2):  # soften boundaries between coat colours a little
        cols = [(c + sum((cols[j] for j in nbrs[i]), Vector())) / (1 + len(nbrs[i])) for i, c in enumerate(cols)]
    for i, c in enumerate(cols):
        col.data[i].color = (*c, 1)
    for p in me.polygons:
        p.use_smooth = True
    m = bpy.data.materials.new("CooperCoat"); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes["Principled BSDF"]
    ca = nt.nodes.new("ShaderNodeVertexColor"); ca.layer_name = "Coat"
    nt.links.new(ca.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.55
    for k, v in (("Sheen Weight", 0.06), ("Sheen Roughness", 0.5), ("Subsurface Weight", 0.02)):
        if k in b.inputs:
            b.inputs[k].default_value = v
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 900; nz.inputs["Detail"].default_value = 2
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.12
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"]); nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    me.materials.append(m)
    sub = body.modifiers.new("Smooth", "SUBSURF"); sub.levels = 1; sub.render_levels = 1
    return body

def simple_mat(name, color, rough=0.5):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1); b.inputs["Roughness"].default_value = rough
    return m

def mesh_obj(coll, name, bm, mat, smooth=True):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = smooth
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me); coll.objects.link(ob)
    return ob

def ellipsoid(coll, name, loc, radii, mat, rot=(0, 0, 0), segs=24):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=segs // 2, radius=1)
    bmesh.ops.scale(bm, vec=radii, verts=bm.verts)
    ob = mesh_obj(coll, name, bm, mat)
    ob.location = loc; ob.rotation_euler = rot
    return ob

def add_parts(coll, body):
    """Eyes, nose, tongue, ears and cap, snapped onto the body surface with ray casts."""
    bme = body.data
    bvh = BVHTree.FromPolygons([v.co for v in bme.vertices], [p.vertices for p in bme.polygons])
    def hit(origin, direction):
        loc, n, _, _ = bvh.ray_cast(Vector(origin), Vector(direction).normalized())
        if loc is None:
            raise RuntimeError(f"ray from {origin} missed the body")
        return loc, n
    parts = []
    eye = simple_mat("Eye", (0.02, 0.008, 0.004), 0.04)
    for sx, tag in ((1, "L"), (-1, "R")):
        loc, n = hit((0.056 * sx, 1.0, 0.425), (0, -1, 0))
        parts.append(ellipsoid(coll, f"Eye{tag}", loc - n * 0.006, (0.017, 0.014, 0.015), eye))
    loc, n = hit((0, 1.0, 0.368), (0, -1, 0))
    parts.append(ellipsoid(coll, "Nose", loc + n * 0.002, (0.036, 0.018, 0.022), simple_mat("Nose", NOSE, 0.25)))
    # nostrils: two dark dimples = small darker spheres just inside the nose surface
    loc, n = hit((0.0, 1.0, 0.30), (0, -1, 0))
    parts.append(ellipsoid(coll, "Tongue", loc + Vector((0.004, 0.012, -0.03)), (0.026, 0.009, 0.042),
                           simple_mat("Tongue", PINK, 0.2), rot=(math.radians(-18), 0, math.radians(8))))
    earm = simple_mat("Ear", (0.035, 0.014, 0.008), 0.6)
    for sx, tag in ((1, "L"), (-1, "R")):  # small folded "rose" ears on the top corners of the skull
        loc, n = hit((1.0 * sx, 0.25, 0.465), (-sx, 0, 0))     # side of the skull, just under the cap
        parts.append(ellipsoid(coll, f"Ear{tag}", loc + n * 0.006 + Vector((0, 0, 0.004)), (0.01, 0.034, 0.03), earm,
                               rot=(math.radians(-15), math.radians(-35 * sx), math.radians(-10 * sx))))
    # --- rust corduroy cap: dome that fits the crown + curved brim + patch
    top, _ = hit((0, 0.285, 2.0), (0, 0, -1))
    capm = bpy.data.materials.new("CapCorduroy"); capm.use_nodes = True
    nt = capm.node_tree; b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*CAP, 1); b.inputs["Roughness"].default_value = 0.8
    if "Sheen Weight" in b.inputs: b.inputs["Sheen Weight"].default_value = 0.25
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wv = nt.nodes.new("ShaderNodeTexWave"); wv.inputs["Scale"].default_value = 55; wv.bands_direction = "X"
    nt.links.new(tc.outputs["Object"], wv.inputs["Vector"])
    bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.5
    nt.links.new(wv.outputs["Fac"], bp.inputs["Height"]); nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=40, v_segments=20, radius=1)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.02], context="VERTS")
    bmesh.ops.scale(bm, vec=(0.15, 0.125, 0.075), verts=bm.verts)
    for v in bm.verts:   # 6-panel seams: tiny creases along the meridians
        a = math.atan2(v.co.y, v.co.x)
        v.co.z -= 0.0015 * max(0.0, math.cos(a * 6)) ** 20 * (v.co.z > 0.01)
    dome = mesh_obj(coll, "CapDome", bm, capm)
    dome.location = (0, top.y + 0.006, top.z - 0.034); dome.rotation_euler.x = math.radians(-9)
    dome.modifiers.new("Thick", "SOLIDIFY").thickness = 0.006
    parts.append(dome)
    bm = bmesh.new()   # brim: half-ellipse annulus, curved down at the sides
    segs, rin, rout = 24, 0.0, 1.0
    rows = []
    for i in range(segs + 1):
        a = math.pi * i / segs
        inner = Vector((0.145 * math.cos(a), 0.118 * math.sin(a) * 0.35, 0))
        outer = Vector((0.15 * math.cos(a), 0.118 * math.sin(a) + 0.075 * math.sin(a), 0))
        for p in (inner, outer):
            p.z = -0.03 * (p.x / 0.15) ** 2 - 0.012 * (p.y / 0.19)
        rows.append((bm.verts.new(inner), bm.verts.new(outer)))
    for i in range(segs):
        bm.faces.new((rows[i][0], rows[i][1], rows[i + 1][1], rows[i + 1][0]))
    brim = mesh_obj(coll, "CapBrim", bm, capm)
    brim.location = (0, top.y + 0.055, top.z - 0.03); brim.rotation_euler.x = math.radians(-6)
    brim.modifiers.new("Thick", "SOLIDIFY").thickness = 0.007
    brim.modifiers.new("Smooth", "SUBSURF").levels = 1
    parts.append(brim)
    bm = bmesh.new(); bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=0.02)
    patch = mesh_obj(coll, "CapPatch", bm, simple_mat("Patch", (0.78, 0.76, 0.70), 0.9), smooth=False)
    patch.location = (0, top.y + 0.1, top.z + 0.005); patch.rotation_euler.x = math.radians(62)
    parts.append(patch)
    btn = ellipsoid(coll, "CapButton", (0, top.y + 0.006, top.z + 0.036), (0.012, 0.012, 0.006), capm)
    parts.append(btn)
    return parts

def build_rig(coll, body, parts):
    arm = bpy.data.armatures.new("CooperRig")
    rig = bpy.data.objects.new("CooperRig", arm); coll.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.edit_bones
    def bone(name, h, t, parent=None):
        b = eb.new(name); b.head = h; b.tail = t
        if parent: b.parent = eb[parent]; b.use_connect = False
    bone("root", (0, 0, 0), (0, 0.15, 0))
    bone("spine", (0, -0.24, 0.26), (0, 0.15, 0.27), "root")
    bone("neck", (0, 0.15, 0.27), (0, 0.25, 0.35), "spine")
    bone("head", (0, 0.25, 0.35), (0, 0.42, 0.40), "neck")
    for name, top, bot, r in LEGS:
        bone(name, top, bot, "spine")
    bpy.ops.object.mode_set(mode="OBJECT")
    body.parent = rig
    mod = body.modifiers.new("Rig", "ARMATURE"); mod.object = rig
    names = ["spine", "neck", "head"] + [l[0] for l in LEGS]
    segs = {b.name: (b.head_local, b.tail_local) for b in arm.bones}
    groups = {n: body.vertex_groups.new(name=n) for n in names}
    for v in body.data.vertices:
        d = {}
        for n in names:
            a, b = segs[n]; ab = b - a
            t = max(0, min(1, (v.co - a).dot(ab) / ab.length_squared))
            dist = (a + ab * t - v.co).length
            if n.startswith("leg") and v.co.z > 0.2:
                dist += 1.0
            d[n] = dist
        best = sorted(d.items(), key=lambda kv: kv[1])[:2]
        w0 = 1 / (best[0][1] + 1e-3) ** 4; w1 = 1 / (best[1][1] + 1e-3) ** 4
        groups[best[0][0]].add([v.index], w0 / (w0 + w1), "REPLACE")
        groups[best[1][0]].add([v.index], w1 / (w0 + w1), "REPLACE")
    for p in parts:  # face details ride on the head bone, keeping their placement
        bpy.context.view_layer.update()
        mw = p.matrix_world.copy()
        p.parent = rig; p.parent_type = "BONE"; p.parent_bone = "head"
        bpy.context.view_layer.update()
        p.matrix_world = mw
    return rig

def build(coll=None):
    coll = coll or bpy.context.scene.collection
    c = bpy.data.collections.new("Cooper"); coll.children.link(c)
    body = build_body(c)
    parts = add_parts(c, body)
    return build_rig(c, body, parts)

if __name__ == "__main__":
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    build()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "cooper.blend"))
    # studio preview (not saved into cooper.blend)
    sc.render.engine = "BLENDER_EEVEE"
    sc.view_settings.view_transform = "AgX"
    w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.58, 0.62, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35
    bpy.ops.mesh.primitive_plane_add(size=6)
    tgt = Vector((0, 0.15, 0.3))
    for name, loc, e, s in (("Key", (1.0, 1.4, 1.3), 45, 0.8), ("Fill", (-1.4, 0.9, 0.7), 14, 1.2), ("Rim", (-0.3, -1.4, 1.0), 30, 0.6)):
        l = bpy.data.lights.new(name, "AREA"); l.energy = e; l.size = s
        o = bpy.data.objects.new(name, l); o.location = loc; sc.collection.objects.link(o)
        o.rotation_euler = (tgt - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    os.makedirs(os.path.join(HERE, "renders"), exist_ok=True)
    for tag, loc, aim, lens in (("front", (0.35, 1.25, 0.42), (0, 0.2, 0.33), 55),
                                ("side", (1.35, 0.1, 0.35), (0, 0.05, 0.27), 50),
                                ("face", (0.08, 0.95, 0.44), (0, 0.34, 0.40), 85)):
        cd = bpy.data.cameras.new(tag); cd.lens = lens
        cam = bpy.data.objects.new(tag, cd); cam.location = loc; sc.collection.objects.link(cam)
        cam.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        sc.camera = cam
        sc.render.resolution_x, sc.render.resolution_y = 800, 600
        sc.render.filepath = os.path.join(HERE, "renders", f"cooper_{tag}.png")
        bpy.ops.render.render(write_still=True)
