"""Build Niguel Heights Park (Laguna Niguel, CA) from OpenStreetMap data.

Map data (c) OpenStreetMap contributors, ODbL. Look-dev from the family's own park photo:
blue mesh benches, wide concrete path, mown lawn, tan block wall with white railing,
stucco houses with terracotta roofs, palms, trees with white-painted trunks.

Usage: blender --background --python build_park.py -- [stills]
"""
import bpy, bmesh, json, math, os, random, sys
from mathutils import Vector, Matrix, noise

HERE = os.path.dirname(os.path.abspath(__file__))
random.seed(7)
bpy.ops.wm.read_factory_settings(use_empty=True)

# ---------------------------------------------------------------- OSM data
data = json.load(open(os.path.join(HERE, "park", "park_area.json"), encoding="utf-8"))
LAT0, LON0 = 33.55828, -117.70470
KX = 111320 * math.cos(math.radians(LAT0))
KY = 110540

def xy(p):
    return Vector(((p["lon"] - LON0) * KX, (p["lat"] - LAT0) * KY))

def pts_of(e):
    if "geometry" in e:
        return [xy(p) for p in e["geometry"]]
    return [xy(e)]

park_poly, playground_poly = None, None
footways, roads, buildings, benches, tables = [], [], [], [], []
for e in data["elements"]:
    t = e.get("tags", {})
    if t.get("leisure") == "park" and t.get("name") == "Niguel Heights Park":
        park_poly = pts_of(e)[:-1]
    elif t.get("leisure") == "playground":
        playground_poly = pts_of(e)[:-1]
    elif t.get("highway") == "footway":
        footways.append(pts_of(e))
    elif t.get("highway") in ("residential", "primary", "service"):
        roads.append((t["highway"], t.get("name", ""), pts_of(e)))
    elif "building" in t and e["type"] == "way":
        buildings.append((t, pts_of(e)[:-1]))
    elif t.get("amenity") == "bench":
        benches.append(pts_of(e)[0])
    elif t.get("leisure") == "picnic_table":
        tables.append(pts_of(e)[0])

# ---------------------------------------------------------------- geometry helpers
def point_in_poly(p, poly):
    inside, j = False, len(poly) - 1
    for i in range(len(poly)):
        a, b = poly[i], poly[j]
        if (a.y > p.y) != (b.y > p.y) and p.x < (b.x - a.x) * (p.y - a.y) / (b.y - a.y + 1e-12) + a.x:
            inside = not inside
        j = i
    return inside

def dist_to_seg(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-9)))
    return (a + ab * t - p).length, a + ab * t

def dist_to_lines(p, lines):
    best, bp = 1e9, None
    for pts in lines:
        for a, b in zip(pts, pts[1:]):
            d, q = dist_to_seg(p, a, b)
            if d < best:
                best, bp = d, q
    return best, bp

def box(V, F, M, c, s, rz=0.0, mi=0):
    """Append an oriented box (centre c, size s, rotation about Z) to vertex/face lists."""
    base = len(V)
    cr, sr = math.cos(rz), math.sin(rz)
    for dx, dy, dz in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)):
        lx, ly = dx * s[0] / 2, dy * s[1] / 2
        V.append((c[0] + lx * cr - ly * sr, c[1] + lx * sr + ly * cr, c[2] + dz * s[2] / 2))
    for f in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):
        F.append(tuple(base + i for i in f))
        M.append(mi)

def make_obj(name, V, F, mats, M=None, smooth=False, coll=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(V, [], F)
    me.update()
    for m in mats:
        me.materials.append(m)
    if M:
        me.polygons.foreach_set("material_index", M)
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    ob = bpy.data.objects.new(name, me)
    (coll or bpy.context.scene.collection).objects.link(ob)
    return ob

def ribbon(pts, width, z, closed=False):
    if closed and (pts[0] - pts[-1]).length < 0.01:
        pts = pts[:-1]
    n = len(pts)
    V, F = [], []
    for i, p in enumerate(pts):
        a = pts[(i - 1) % n] if (closed or i > 0) else p
        b = pts[(i + 1) % n] if (closed or i < n - 1) else p
        d = (b - a).normalized()
        nrm = Vector((-d.y, d.x)) * width / 2
        V += [(p.x + nrm.x, p.y + nrm.y, z), (p.x - nrm.x, p.y - nrm.y, z)]
    for i in range(n if closed else n - 1):
        j = (i + 1) % n
        F.append((2 * i, 2 * j, 2 * j + 1, 2 * i + 1))
    return V, F

def polygon_obj(name, poly, z, mat):
    V = [(p.x, p.y, z) for p in poly]
    ob = make_obj(name, V, [tuple(range(len(V)))], [mat])
    if ob.data.polygons[0].normal.z < 0:
        ob.data.flip_normals()
    return ob

def collection(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c

# ---------------------------------------------------------------- materials
def mat(name, color, rough=0.6, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m

def socket(node, name, kind):
    return next(s for s in node.inputs if s.name == name and s.type == kind)

def varied_mat(name, c1, c2, scale=0.3, rough=0.8, bump=0.0, bump_scale=30.0, stripes=None, per_object=False):
    """Principled material whose colour varies with noise (and optional mowing stripes)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    b = N["Principled BSDF"]
    b.inputs["Roughness"].default_value = rough
    tc = N.new("ShaderNodeTexCoord")
    nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = scale; nz.inputs["Detail"].default_value = 6
    L.new(tc.outputs["Object"], nz.inputs["Vector"])
    ramp = N.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c1, 1)
    ramp.color_ramp.elements[1].color = (*c2, 1)
    fac = nz.outputs["Fac"]
    if per_object:  # shift each instance's colour a little
        oi = N.new("ShaderNodeObjectInfo")
        add = N.new("ShaderNodeMath"); add.operation = "MULTIPLY_ADD"
        add.inputs[1].default_value = 0.6
        L.new(oi.outputs["Random"], add.inputs[0]); L.new(fac, add.inputs[2])
        add.inputs[1].default_value = 0.5
        fac = add.outputs[0]
    L.new(fac, ramp.inputs["Fac"])
    col = ramp.outputs["Color"]
    if stripes:
        wave = N.new("ShaderNodeTexWave"); wave.wave_type = "BANDS"; wave.bands_direction = "X"
        wave.inputs["Scale"].default_value = stripes; wave.wave_profile = "SAW"
        wave.inputs["Distortion"].default_value = 0.0
        L.new(tc.outputs["Object"], wave.inputs["Vector"])
        step = N.new("ShaderNodeMath"); step.operation = "GREATER_THAN"; step.inputs[1].default_value = 0.5
        L.new(wave.outputs["Fac"], step.inputs[0])
        mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        L.new(col, socket(mix, "A", "RGBA"))
        rgb = N.new("ShaderNodeMix"); rgb.data_type = "RGBA"
        socket(rgb, "A", "RGBA").default_value = (0.93, 0.95, 0.92, 1)
        socket(rgb, "B", "RGBA").default_value = (1.04, 1.04, 1.0, 1)
        L.new(step.outputs[0], rgb.inputs["Factor"])
        L.new(next(o for o in rgb.outputs if o.type == "RGBA"), socket(mix, "B", "RGBA"))
        col = next(o for o in mix.outputs if o.type == "RGBA")
    L.new(col, b.inputs["Base Color"])
    if bump:
        nz2 = N.new("ShaderNodeTexNoise"); nz2.inputs["Scale"].default_value = bump_scale
        L.new(tc.outputs["Object"], nz2.inputs["Vector"])
        bp = N.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = bump
        L.new(nz2.outputs["Fac"], bp.inputs["Height"]); L.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m

M_GRASS   = varied_mat("Lawn", (0.10, 0.26, 0.04), (0.20, 0.38, 0.07), scale=0.08, rough=0.9, bump=0.25, bump_scale=60, stripes=0.22)
M_GROUND  = varied_mat("Yards", (0.13, 0.22, 0.06), (0.30, 0.30, 0.14), scale=0.05, rough=0.95, bump=0.2)
M_ASPHALT = varied_mat("Asphalt", (0.05, 0.05, 0.055), (0.09, 0.09, 0.095), scale=2, rough=0.85, bump=0.1, bump_scale=200)
M_CONCRETE= varied_mat("Concrete", (0.58, 0.56, 0.52), (0.68, 0.66, 0.62), scale=1.5, rough=0.8, bump=0.08, bump_scale=120)
M_RUBBER  = varied_mat("PlayRubber", (0.12, 0.22, 0.42), (0.16, 0.28, 0.5), scale=3, rough=0.9, bump=0.1, bump_scale=150)
M_BENCH   = mat("BenchBlue", (0.02, 0.09, 0.45), 0.35, 0.3)
M_BLACK   = mat("BlackMetal", (0.02, 0.02, 0.02), 0.4, 0.6)
M_WOOD    = mat("TableTop", (0.35, 0.22, 0.12), 0.7)
M_WALLBLK = varied_mat("BlockWall", (0.60, 0.48, 0.34), (0.70, 0.58, 0.42), scale=4, rough=0.9, bump=0.15, bump_scale=80)
M_WHITE   = mat("WhiteRail", (0.85, 0.85, 0.83), 0.35, 0.2)
M_ROOF    = varied_mat("Terracotta", (0.45, 0.14, 0.06), (0.62, 0.24, 0.10), scale=0.8, rough=0.7, bump=0.3, bump_scale=15)
M_STUCCO  = [varied_mat(f"Stucco{i}", c, tuple(min(1, v * 1.08) for v in c), scale=1, rough=0.9, bump=0.05, bump_scale=200)
             for i, c in enumerate([(0.80, 0.70, 0.55), (0.86, 0.80, 0.66), (0.78, 0.64, 0.50), (0.88, 0.85, 0.78)])]
M_BARK    = varied_mat("Bark", (0.16, 0.11, 0.07), (0.28, 0.20, 0.13), scale=8, rough=0.95, bump=0.4, bump_scale=20)
M_TRUNKWHT= mat("TrunkPaint", (0.82, 0.82, 0.78), 0.8)
M_LEAF    = varied_mat("Leaves", (0.07, 0.18, 0.04), (0.20, 0.32, 0.08), scale=0.9, rough=0.75, bump=0.5, bump_scale=6, per_object=True)
M_PALMLF  = varied_mat("PalmFronds", (0.10, 0.24, 0.05), (0.28, 0.36, 0.10), scale=1.2, rough=0.6, per_object=True)
M_PALMTR  = varied_mat("PalmTrunk", (0.30, 0.25, 0.18), (0.42, 0.36, 0.27), scale=6, rough=0.95, bump=0.6, bump_scale=4)
M_PLAYRED = mat("PlayRed", (0.55, 0.06, 0.04), 0.4)
M_PLAYYEL = mat("PlayYellow", (0.85, 0.55, 0.05), 0.4)
M_PLAYPST = mat("PlayPosts", (0.08, 0.25, 0.12), 0.35, 0.4)
M_WINDOW  = mat("Window", (0.02, 0.025, 0.03), 0.08)

# ---------------------------------------------------------------- scene
def build():
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"

    C_GROUND = collection("Ground")
    # base ground + park lawn
    # ground: flat neighbourhood that rises into rolling hills beyond ~400 m
    V, F, n, S = [], [], 140, 3500.0
    for j in range(n + 1):
        for i in range(n + 1):
            x, y = -S / 2 + S * i / n, -S / 2 + S * j / n
            r = math.hypot(x, y)
            t = max(0.0, min(1.0, (r - 380) / 600)); t = t * t * (3 - 2 * t)
            hgt = t * (70 + 55 * noise.noise(Vector((x / 700, y / 700, 0.3))) + 18 * noise.noise(Vector((x / 180, y / 180, 1.7))))
            # open towards the ocean (WSW, where the sun sets) so the low sun isn't blocked
            toward_sun = (x * -0.94 + y * -0.34) / max(r, 1)
            hgt *= 1 - 0.92 * max(0.0, toward_sun) ** 0.6
            V.append((x, y, -0.06 + max(0.0, hgt)))
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            F.append((a, a + 1, a + n + 2, a + n + 1))
    make_obj("Yards", V, F, [M_GROUND], coll=C_GROUND, smooth=True)
    lawn = polygon_obj("ParkLawn", park_poly, 0.0, M_GRASS)
    C_GROUND.objects.link(lawn); sc.collection.objects.unlink(lawn)
    pg = polygon_obj("PlaygroundSurface", playground_poly, 0.04, M_RUBBER)
    C_GROUND.objects.link(pg); sc.collection.objects.unlink(pg)

    # roads (asphalt) with concrete sidewalks either side
    width = {"residential": 11, "primary": 22, "service": 5}
    V, F, M = [], [], []
    for kind, name, pts in roads:
        w = width[kind]
        v, f = ribbon(pts, w, 0.01); o = len(V)
        V += v; F += [tuple(i + o for i in q) for q in f]; M += [0] * len(f)
        if kind != "service":
            v, f = ribbon(pts, w + 3.2, 0.02); o = len(V)
            V += v; F += [tuple(i + o for i in q) for q in f]; M += [1] * len(f)
    # sidewalk ribbon is wider and slightly higher: cut its middle by drawing asphalt higher
    for i, (a, b, c, d) in enumerate(F):
        if M[i] == 0:
            for k in (a, b, c, d):
                V[k] = (V[k][0], V[k][1], 0.025)
    make_obj("Streets", V, F, [M_ASPHALT, M_CONCRETE], M, coll=C_GROUND)

    # park footpaths (wide concrete, like the photo)
    V, F = [], []
    for pts in footways:
        closed = (pts[0] - pts[-1]).length < 0.01
        v, f = ribbon(pts, 2.4, 0.03, closed); o = len(V)
        V += v; F += [tuple(i + o for i in q) for q in f]
        for p in (pts[0], pts[-1]):  # round-ish caps where paths join
            box(V, F, [], (p.x, p.y, 0.028), (2.4, 2.4, 0.004), 0)
    make_obj("Footpaths", V, F, [M_CONCRETE], coll=C_GROUND)

    # ------------------------------------------------ park furniture
    C_FURN = collection("ParkFurniture")
    def nearest_path_dir(p):
        _, q = dist_to_lines(p, footways)
        d = (q - p)
        return math.atan2(d.y, d.x) if d.length > 0.01 else 0.0

    V, F, M = [], [], []
    for p in benches:
        yaw = nearest_path_dir(p) - math.pi / 2   # seat faces the path
        def local(dx, dy, dz):
            c, s = math.cos(yaw), math.sin(yaw)
            return (p.x + dx * c - dy * s, p.y + dx * s + dy * c, dz)
        box(V, F, M, local(0, 0, 0.45), (1.8, 0.45, 0.05), yaw, 0)          # seat
        box(V, F, M, local(0, -0.26, 0.78), (1.8, 0.05, 0.36), yaw, 0)      # back
        for sx in (-0.75, 0.75):
            box(V, F, M, local(sx, 0.1, 0.22), (0.06, 0.06, 0.44), yaw, 1)
            box(V, F, M, local(sx, -0.24, 0.4), (0.06, 0.06, 0.8), yaw, 1)
    for p in tables:
        yaw = random.uniform(0, math.pi)
        def local(dx, dy, dz):
            c, s = math.cos(yaw), math.sin(yaw)
            return (p.x + dx * c - dy * s, p.y + dx * s + dy * c, dz)
        box(V, F, M, local(0, 0, 0.76), (2.0, 0.8, 0.05), yaw, 2)
        for sy in (-0.65, 0.65):
            box(V, F, M, local(0, sy, 0.45), (2.0, 0.3, 0.04), yaw, 2)
        for sx in (-0.7, 0.7):
            box(V, F, M, local(sx, 0, 0.38), (0.08, 1.5, 0.08), yaw, 1)
            box(V, F, M, local(sx, 0, 0.55), (0.08, 0.08, 0.45), yaw, 1)
    make_obj("BenchesAndTables", V, F, [M_BENCH, M_BLACK, M_WOOD], M, coll=C_FURN)

    # playground: climbing structure + slide + 4-swing set
    cx = sum(p.x for p in playground_poly) / len(playground_poly)
    cy = sum(p.y for p in playground_poly) / len(playground_poly)
    V, F, M = [], [], []
    for dx in (-1.2, 1.2):
        for dy in (-1.2, 1.2):
            box(V, F, M, (cx + dx, cy + dy, 1.6), (0.14, 0.14, 3.2), 0, 0)
    box(V, F, M, (cx, cy, 1.4), (2.6, 2.6, 0.1), 0, 1)                 # deck
    box(V, F, M, (cx, cy, 3.25), (3.0, 3.0, 0.12), 0, 2)               # roof
    # slide: a sloped chute from the deck edge down to the ground
    b0 = len(V)
    for x, z in ((cx + 1.3, 1.45), (cx + 4.3, 0.25)):
        for y in (cy - 0.4, cy + 0.4):
            V.append((x, y, z))
        for y in (cy - 0.4, cy + 0.4):
            V.append((x, y, z + 0.3))
    F += [(b0, b0 + 1, b0 + 5, b0 + 4), (b0, b0 + 4, b0 + 6, b0 + 2), (b0 + 1, b0 + 3, b0 + 7, b0 + 5)]
    M += [2, 2, 2]
    for k in range(4):                                                 # ladder rungs
        box(V, F, M, (cx - 1.45, cy, 0.3 + k * 0.35), (0.1, 0.8, 0.05), 0, 1)
    sx0 = cx + 1.0; sy0 = cy - 6.0                                      # swing set
    for ex in (-4, 4):
        for ey in (-0.9, 0.9):
            box(V, F, M, (sx0 + ex, sy0 + ey * 0.5, 1.2), (0.1, 0.1, 2.6), 0, 0)
    box(V, F, M, (sx0, sy0, 2.45), (8.2, 0.12, 0.12), 0, 0)
    for i, sx in enumerate((-2.8, -1.2, 1.2, 2.8)):
        for d in (-0.22, 0.22):
            box(V, F, M, (sx0 + sx + d, sy0, 1.55), (0.02, 0.02, 1.8), 0, 0)
        box(V, F, M, (sx0 + sx, sy0, 0.62), (0.5, 0.22 if i in (1, 2) else 0.18, 0.05 if i in (1, 2) else 0.2), 0, 3)
    make_obj("Playground", V, F, [M_PLAYPST, M_PLAYYEL, M_PLAYRED, M_BLACK], M, coll=C_FURN)

    # ------------------------------------------------ boundary wall + white railing (not along the boulevard)
    blvd = [pts for k, n, pts in roads if n == "Niguel Heights Boulevard"]
    V, F, M = [], [], []
    ring = park_poly + [park_poly[0]]
    for a, b in zip(ring, ring[1:]):
        mid = (a + b) / 2
        if dist_to_lines(mid, blvd)[0] < 14:
            continue
        seg = b - a; L = seg.length
        if L < 0.5:
            continue
        yaw = math.atan2(seg.y, seg.x)
        box(V, F, M, (mid.x, mid.y, 0.45), (L + 0.2, 0.22, 0.9), yaw, 0)
        for z in (0.95, 1.75):
            box(V, F, M, (mid.x, mid.y, z), (L, 0.05, 0.05), yaw, 1)
        n = int(L / 0.14)
        for k in range(n + 1):
            p = a + seg * (k / max(n, 1))
            box(V, F, M, (p.x, p.y, 1.35), (0.022, 0.022, 0.8), yaw, 1)
    make_obj("WallAndRailing", V, F, [M_WALLBLK, M_WHITE], M, coll=C_FURN)

    # ------------------------------------------------ houses
    C_HOUSES = collection("Houses")
    for i, (t, poly) in enumerate(buildings):
        if len(poly) < 3:
            continue
        school = t.get("building") == "school"
        h = 7.5 if school else random.choice([3.2, 3.4, 5.9, 6.2])
        bm = bmesh.new()
        vs = [bm.verts.new((p.x, p.y, 0)) for p in poly]
        try:
            f = bm.faces.new(vs)
        except ValueError:
            bm.free(); continue
        bmesh.ops.recalc_face_normals(bm, faces=[f])
        if f.normal.z < 0:
            f.normal_flip()
        c = f.calc_center_median()
        r = bmesh.ops.extrude_face_region(bm, geom=[f])
        top = [g for g in r["geom"] if isinstance(g, bmesh.types.BMFace)]
        bmesh.ops.translate(bm, vec=(0, 0, h), verts=[v for v in r["geom"] if isinstance(v, bmesh.types.BMVert)])
        n_walls = len(bm.faces)
        # eave overhang
        r = bmesh.ops.extrude_face_region(bm, geom=top)
        vv = [v for v in r["geom"] if isinstance(v, bmesh.types.BMVert)]
        top = [g for g in r["geom"] if isinstance(g, bmesh.types.BMFace)]
        cc = Vector((c.x, c.y, h))
        area = top[0].calc_area()
        grow = 1 + 0.6 / max(math.sqrt(area), 1)
        bmesh.ops.scale(bm, vec=(grow, grow, 1), space=Matrix.Translation(-cc), verts=vv)
        # hip roof
        r = bmesh.ops.extrude_face_region(bm, geom=top)
        vv = [v for v in r["geom"] if isinstance(v, bmesh.types.BMVert)]
        rise = 0.35 * math.sqrt(area) ** 0.8 if not school else 1.0
        bmesh.ops.translate(bm, vec=(0, 0, min(rise, 2.6)), verts=vv)
        bmesh.ops.scale(bm, vec=(0.25, 0.25, 1), space=Matrix.Translation(-Vector((c.x, c.y, 0))), verts=vv)
        bm.faces.ensure_lookup_table()
        me = bpy.data.meshes.new(f"House{i}")
        for k, face in enumerate(bm.faces):
            face.material_index = 0 if (k < n_walls and abs(face.normal.z) < 0.5) else 1
        bm.to_mesh(me); bm.free()
        me.materials.append(random.choice(M_STUCCO)); me.materials.append(M_ROOF)
        ob = bpy.data.objects.new(f"House{i}", me)
        C_HOUSES.objects.link(ob)

    # ------------------------------------------------ trees (a few variants, instanced)
    C_TREES = collection("Trees")
    C_PROTO = collection("TreeVariants")
    C_PROTO.hide_render = True; C_PROTO.hide_viewport = True

    def broadleaf(k):
        rnd = random.Random(100 + k)
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.26, radius2=0.2, depth=1.3,
                              matrix=Matrix.Translation((0, 0, 0.65)))
        n_white = len(bm.faces)
        bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.2, radius2=0.12, depth=2.6,
                              matrix=Matrix.Translation((0, 0, 2.6)))
        n_trunk = len(bm.faces)
        H = rnd.uniform(4.5, 6.0)
        for j in range(9):
            a = rnd.uniform(0, 2 * math.pi); rr = rnd.uniform(0.6, 1.8)
            ctr = Vector((math.cos(a) * rr, math.sin(a) * rr, H + rnd.uniform(-0.8, 1.2)))
            bmesh.ops.create_icosphere(bm, subdivisions=2, radius=rnd.uniform(1.3, 2.1), matrix=Matrix.Translation(ctr))
        bm.faces.ensure_lookup_table()
        for f_ in bm.faces[n_trunk:]:
            for v in f_.verts:
                pass
        leaf_verts = {v for f_ in bm.faces[n_trunk:] for v in f_.verts}
        for v in leaf_verts:
            v.co += v.co.normalized() * 0.0 + Vector((0, 0, 0)) + (v.co - Vector((0, 0, H))).normalized() * noise.noise(v.co * 0.9 + Vector((k, k, k))) * 0.45
        for idx, f_ in enumerate(bm.faces):
            f_.material_index = 0 if idx < n_white else (1 if idx < n_trunk else 2)
            f_.smooth = idx >= n_trunk
        me = bpy.data.meshes.new(f"TreeBroadleaf{k}")
        bm.to_mesh(me); bm.free()
        for m in (M_TRUNKWHT, M_BARK, M_LEAF):
            me.materials.append(m)
        ob = bpy.data.objects.new(me.name, me); C_PROTO.objects.link(ob)
        return me

    def palm(k):
        rnd = random.Random(200 + k)
        H = rnd.uniform(11, 16)
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.24, radius2=0.17, depth=H,
                              matrix=Matrix.Translation((0, 0, H / 2)))
        n_trunk = len(bm.faces)
        top = Vector((0, 0, H))
        nf = 16
        for j in range(nf):
            phi = j / nf * 2 * math.pi + rnd.uniform(-0.15, 0.15)
            up = rnd.uniform(0.2, 1.0) if j % 3 else rnd.uniform(0.9, 1.4)
            Lf = rnd.uniform(2.6, 3.4)
            d = Vector((math.cos(phi), math.sin(phi), 0)); side = Vector((-d.y, d.x, 0))
            segs = 8; row = []
            for s in range(segs + 1):
                t = s / segs
                p = top + d * (Lf * t) + Vector((0, 0, up * t * 1.6 - 2.4 * t * t))
                w = 0.5 * math.sin(math.pi * min(t * 1.1, 1)) + 0.04
                row.append((bm.verts.new(p + side * w), bm.verts.new(p - side * w), bm.verts.new(p + Vector((0, 0, 0.12)))))
            for s in range(segs):
                a, b = row[s], row[s + 1]
                bm.faces.new((a[0], b[0], b[2], a[2])); bm.faces.new((a[2], b[2], b[1], a[1]))
        for idx, f_ in enumerate(bm.faces):
            f_.material_index = 0 if idx < n_trunk else 1
            f_.smooth = idx >= n_trunk
        me = bpy.data.meshes.new(f"TreePalm{k}")
        bm.to_mesh(me); bm.free()
        me.materials.append(M_PALMTR); me.materials.append(M_PALMLF)
        ob = bpy.data.objects.new(me.name, me); C_PROTO.objects.link(ob)
        return me

    BL = [broadleaf(k) for k in range(4)]
    PA = [palm(k) for k in range(3)]

    def place(me, p, s=1.0):
        ob = bpy.data.objects.new(me.name + "_inst", me)
        ob.location = (p.x, p.y, 0)
        ob.rotation_euler.z = random.uniform(0, 2 * math.pi)
        ob.scale = (s, s, s * random.uniform(0.9, 1.1))
        C_TREES.objects.link(ob)

    placed = []
    def free(p, r):
        return all((p - q).length > r for q in placed)

    fences_mid = []
    # park edge trees (white-painted trunks), just inside the boundary
    ring = park_poly + [park_poly[0]]
    cx0 = sum(p.x for p in park_poly) / len(park_poly); cy0 = sum(p.y for p in park_poly) / len(park_poly)
    centre = Vector((cx0, cy0))
    for a, b in zip(ring, ring[1:]):
        seg = b - a; n = max(1, int(seg.length / 11))
        for k in range(n):
            p = a + seg * ((k + 0.5) / n)
            p = p + (centre - p).normalized() * random.uniform(4.5, 7)
            p += Vector((random.uniform(-1.5, 1.5), random.uniform(-1.5, 1.5)))
            if not point_in_poly(p, park_poly) or point_in_poly(p, playground_poly):
                continue
            if dist_to_lines(p, footways)[0] < 3.2 or min((p - q).length for q in benches + tables) < 3:
                continue
            if random.random() < 0.8 and free(p, 6):
                place(random.choice(BL), p, random.uniform(0.9, 1.2)); placed.append(p)
    # a few park palms
    for k in range(6):
        for _ in range(30):
            p = Vector((random.uniform(-80, 80), random.uniform(-45, 45)))
            if point_in_poly(p, park_poly) and dist_to_lines(p, footways)[0] > 4 and free(p, 8) and not point_in_poly(p, playground_poly):
                place(random.choice(PA), p); placed.append(p); break
    # neighbourhood: palms and shade trees in yards and along streets
    road_lines = [pts for _, _, pts in roads]
    b_polys = [poly for _, poly in buildings if len(poly) > 2]
    for _ in range(420):
        p = Vector((random.uniform(-260, 260), random.uniform(-230, 260)))
        if point_in_poly(p, park_poly) or dist_to_lines(p, road_lines)[0] < 7.5:
            continue
        if any(point_in_poly(p, bp) for bp in b_polys if (bp[0] - p).length < 40):
            continue
        if not free(p, 5):
            continue
        if random.random() < 0.35:
            place(random.choice(PA), p, random.uniform(0.85, 1.1))
        else:
            place(random.choice(BL), p, random.uniform(0.8, 1.3))
        placed.append(p)

    # ------------------------------------------------ golden-hour sky + sun
    world = bpy.data.worlds.new("GoldenHour"); sc.world = world
    world.use_nodes = True
    N = world.node_tree.nodes; bg = N["Background"]
    sky = N.new("ShaderNodeTexSky")
    for st in ("MULTIPLE_SCATTERING", "NISHITA", "SINGLE_SCATTERING"):
        try:
            sky.sky_type = st; break
        except TypeError:
            pass
    SUN_ELEV, SUN_AZ = math.radians(5), math.radians(250)   # compass azimuth: WSW, over the ocean
    sky.sun_elevation = SUN_ELEV
    sky.sun_rotation = SUN_AZ  # compass azimuth (checked with a panorama render)
    for attr, val in (("aerosol_density", 2.5), ("air_density", 1.2)):
        if hasattr(sky, attr):
            setattr(sky, attr, val)
    if hasattr(sky, "sun_disc"):
        sky.sun_disc = False
    world.node_tree.links.new(sky.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.25
    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy = 7.0; sun.color = (1.0, 0.62, 0.34); sun.angle = math.radians(1.0)
    sun_ob = bpy.data.objects.new("Sun", sun); sc.collection.objects.link(sun_ob)
    # light travels away from the sun: azimuth measured clockwise from north (+Y)
    to_x = -math.sin(SUN_AZ); to_y = -math.cos(SUN_AZ)
    direction = Vector((to_x * math.cos(SUN_ELEV), to_y * math.cos(SUN_ELEV), -math.sin(SUN_ELEV)))
    sun_ob.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    # ------------------------------------------------ render settings (EEVEE)
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            sc.render.engine = eng; break
        except TypeError:
            pass
    ee = sc.eevee
    ee.taa_render_samples = 48
    for attr, val in (("use_raytracing", True), ("use_shadows", True), ("shadow_ray_count", 2), ("use_gtao", True)):
        if hasattr(ee, attr):
            setattr(ee, attr, val)
    sc.view_settings.view_transform = "AgX"
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    sc.render.resolution_x, sc.render.resolution_y = 1280, 720
    return sc

def add_camera(sc, name, loc, target, lens=35):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_end = 2000
    cam = bpy.data.objects.new(name, cd); sc.collection.objects.link(cam)
    cam.location = loc
    d = Vector(target) - Vector(loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return cam

if __name__ == "__main__":
    sc = build()
    cams = {
        "aerial": add_camera(sc, "CamAerial", (-150, 95, 75), (0, -5, 0), 32),
        "ground": add_camera(sc, "CamGround", (30, 8, 1.5), (-40, -12, 3), 28),
        "side":   add_camera(sc, "CamSide", (40, -25, 1.6), (-20, 30, 3), 28),
    }
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "park.blend"))
    if "stills" in sys.argv:
        os.makedirs(os.path.join(HERE, "renders"), exist_ok=True)
        for k, cam in cams.items():
            sc.camera = cam
            sc.render.filepath = os.path.join(HERE, "renders", f"park_{k}.png")
            bpy.ops.render.render(write_still=True)
            print("Saved", sc.render.filepath)
