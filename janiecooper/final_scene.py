"""Janie & Cooper at Niguel Heights Park - final shot.

Run on park.blend:  blender --background park.blend --python final_scene.py -- [stills|render]
Map data (c) OpenStreetMap contributors, ODbL.
"""
import bpy, json, math, os, sys
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
MODE = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "stills"
sc = bpy.context.scene
FPS, FRAMES = 24, 288          # 12 seconds
WALK_SPEED = 1.15              # m/s

# ------------------------------------------------ path along the park's concrete loop
data = json.load(open(os.path.join(HERE, "park", "park_area.json"), encoding="utf-8"))
LAT0, LON0 = 33.55828, -117.70470
KX, KY = 111320 * math.cos(math.radians(LAT0)), 110540
def xy(p): return Vector(((p["lon"] - LON0) * KX, (p["lat"] - LAT0) * KY))
loop = max((e for e in data["elements"] if e.get("tags", {}).get("highway") == "footway"),
           key=lambda e: len(e.get("geometry", [])))
pts = [xy(p) for p in loop["geometry"]]

def resample(pts, step=0.25):
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int((b - a).length / step))
        out += [a.lerp(b, k / n) for k in range(1, n + 1)]
    return out
path = resample(pts)
need = WALK_SPEED * FRAMES / FPS + 2
best, best_i = 1e9, 0
FOCUS = Vector((12.0, -12.0))   # open stretch of path with the lawn and playground behind
PARK_CENTRE = Vector((0.0, 0.0))
for i in range(0, len(path) - int(need / 0.25) - 1, 4):     # straightest, most central stretch
    j = i + int(need / 0.25)
    a, b = path[i], path[j]
    straight = sum((p - a).length for p in path[i:j + 1:4]) * 0 + ((b - a).length - need) ** 2
    turn = abs(math.atan2(*(path[i + 8] - path[i]).yx) - math.atan2(*(b - path[j - 8]).yx))
    score = straight * 4 + turn * 20 + ((a + b) / 2 - FOCUS).length * 0.6
    if score < best:
        best, best_i = score, i
seg = path[best_i:best_i + int(need / 0.25) + 1]
print("[FINAL] walk segment", seg[0], "->", seg[-1])

def along(dist):
    k = max(0, min(len(seg) - 2, dist / 0.25))
    i = int(k); f = k - i
    p = seg[i].lerp(seg[i + 1], f)
    d = (seg[min(i + 4, len(seg) - 1)] - seg[max(i - 4, 0)]).normalized()
    return p, d

# ------------------------------------------------ bring in the characters
def append_all(blend, prefix):
    with bpy.data.libraries.load(os.path.join(HERE, blend), link=False) as (src, dst):
        dst.objects = [n for n in src.objects]
    objs = [o for o in dst.objects if o is not None]
    coll = bpy.data.collections.new(prefix); sc.collection.children.link(coll)
    for o in objs:
        if o.type in ("MESH", "ARMATURE", "META") and not o.name.startswith(("Key", "Fill", "Rim", "front", "side", "portrait", "full", "Plane")):
            coll.objects.link(o)
    return objs

janie_objs = append_all("janie.blend", "JanieChar")
jrig = next(o for o in janie_objs if o.type == "ARMATURE")
cooper_objs = append_all("cooper.blend", "CooperChar")
crig = next(o for o in cooper_objs if o.name == "CooperRig")

# ------------------------------------------------ Janie walk cycle (procedural)
pb = jrig.pose.bones
for b in pb:
    b.rotation_mode = "XYZ"
STRIDE = 0.68
CYCLE = 2 * STRIDE / WALK_SPEED * FPS           # frames per full gait cycle
def key(bone, frame, x=None, z=None):
    b = pb[bone]; e = b.rotation_euler
    if x is not None: e.x = math.radians(x)
    if z is not None: e.z = math.radians(z)
    b.keyframe_insert("rotation_euler", frame=frame)

for f in range(1, FRAMES + 2, 2):
    ph = 2 * math.pi * f / CYCLE
    s, c = math.sin(ph), math.cos(ph)
    # legs: thigh swing, knee bends during the forward swing
    key("mixamorig:LeftUpLeg", f, x=-24 * s)
    key("mixamorig:RightUpLeg", f, x=24 * s)
    key("mixamorig:LeftLeg", f, x=6 + 38 * max(0, c) ** 1.5)
    key("mixamorig:RightLeg", f, x=6 + 38 * max(0, -c) ** 1.5)
    key("mixamorig:LeftFoot", f, x=10 * s)
    key("mixamorig:RightFoot", f, x=-10 * s)
    # arms relaxed at the sides, swinging opposite to the legs
    key("mixamorig:LeftArm", f, z=-55, x=-14 * s)
    key("mixamorig:RightArm", f, z=55, x=14 * s)
    key("mixamorig:LeftForeArm", f, z=-12)
    key("mixamorig:RightForeArm", f, z=12)
    key("mixamorig:Spine", f, z=0, x=2)
    key("mixamorig:Head", f, x=-3)

# ------------------------------------------------ Cooper waddle (procedural)
cpb = crig.pose.bones
for b in cpb:
    b.rotation_mode = "XYZ"
CCYCLE = FPS / 2.6                                  # quick little steps
for f in range(1, FRAMES + 2, 2):
    ph = 2 * math.pi * f / CCYCLE
    s = math.sin(ph)
    for name, sign in (("legFL", 1), ("legBR", 1), ("legFR", -1), ("legBL", -1)):
        cpb[name].rotation_euler.x = math.radians(22 * sign * s)
        cpb[name].keyframe_insert("rotation_euler", frame=f)
    cpb["spine"].rotation_euler.y = math.radians(4 * s)          # side-to-side waddle
    cpb["spine"].keyframe_insert("rotation_euler", frame=f)
    cpb["head"].rotation_euler.z = math.radians(5 * math.sin(ph / 2))
    cpb["head"].keyframe_insert("rotation_euler", frame=f)

# ------------------------------------------------ move both along the path
SUN_TO = Vector((-0.94, -0.34))                       # horizontal direction towards the sun
p0, d0 = along(0)
perp0 = Vector((-d0.y, d0.x))
outward = (p0 - PARK_CENTRE).normalized()
cam_side = perp0 if perp0.dot(outward) > 0 else -perp0   # camera outside the path, looking in across the park
for f in range(1, FRAMES + 2, 2):
    dist = WALK_SPEED * (f - 1) / FPS
    p, d = along(dist)
    heading = math.atan2(d.y, d.x)
    jrig.location = (p.x, p.y, 0.0)
    jrig.rotation_euler = (0, 0, heading + math.pi / 2)        # Janie's rest pose faces -Y
    jrig.keyframe_insert("location", frame=f); jrig.keyframe_insert("rotation_euler", frame=f)
    cp = p + d * 0.35 - cam_side * 0.75                            # Cooper at her far side, a little ahead
    crig.location = (cp.x, cp.y, 0.0)
    crig.rotation_euler = (0, math.radians(0), heading - math.pi / 2)  # Cooper's rest pose faces +Y
    crig.keyframe_insert("location", frame=f); crig.keyframe_insert("rotation_euler", frame=f)

# ------------------------------------------------ Cooper's beach ball: Janie tosses it ahead, it bounces and rolls, Cooper chases
BALL_R = 0.20
def beach_ball_material():
    m = bpy.data.materials.new("BeachBall"); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    b = N["Principled BSDF"]; b.inputs["Roughness"].default_value = 0.25
    tc = N.new("ShaderNodeTexCoord")
    grad = N.new("ShaderNodeTexGradient"); grad.gradient_type = "RADIAL"   # angle around the ball's axis, 0..1
    L.new(tc.outputs["Object"], grad.inputs["Vector"])
    ramp = N.new("ShaderNodeValToRGB"); ramp.color_ramp.interpolation = "CONSTANT"
    cols = [(0.95, 0.35, 0.05), (0.92, 0.9, 0.85), (0.85, 0.08, 0.06), (0.97, 0.72, 0.10), (0.92, 0.9, 0.85), (0.95, 0.35, 0.05)]
    els = ramp.color_ramp.elements
    els[0].position = 0.0; els[0].color = (*cols[0], 1)
    els[1].position = 1 / 6; els[1].color = (*cols[1], 1)
    for k in range(2, 6):
        e = els.new(k / 6); e.color = (*cols[k], 1)
    L.new(grad.outputs["Fac"], ramp.inputs["Fac"]); L.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return m

bpy.ops.mesh.primitive_uv_sphere_add(radius=BALL_R, segments=48, ring_count=24)
ball = bpy.context.active_object; ball.name = "BeachBall"
bpy.ops.object.shade_smooth()
ball.data.materials.append(beach_ball_material())
ball_pivot = bpy.data.objects.new("BallPivot", None); sc.collection.objects.link(ball_pivot)
ball.parent = ball_pivot; ball.location = (0, 0, 0)

THROW, LAND = 118, 146                     # Janie releases at THROW, first bounce at LAND
def ball_pos(f):
    """Ball (x, y, z) and heading for frame f."""
    dist_j = WALK_SPEED * (f - 1) / FPS
    if f < THROW:                          # held at Janie's side (small, mostly hidden by her hand)
        p, d = along(dist_j)
        side = Vector((-d.y, d.x))
        q = p - side * 0.22
        return Vector((q.x, q.y, 0.95)), d
    p_throw, d = along(WALK_SPEED * (THROW - 1) / FPS)
    land_dist = WALK_SPEED * (THROW - 1) / FPS + 3.2
    if f <= LAND:                          # arc from her hand to the path ahead
        t = (f - THROW) / (LAND - THROW)
        dd = WALK_SPEED * (THROW - 1) / FPS + 3.2 * t
        p, d = along(dd)
        z = (0.95 * (1 - t)) + BALL_R * t + 1.1 * math.sin(math.pi * t)
        return Vector((p.x, p.y, z)), d
    # after landing: rolls ahead, a couple of shrinking bounces, slowly let Cooper close in
    t = (f - LAND) / FPS
    dd = land_dist + WALK_SPEED * 0.85 * t + 0.6 * (1 - math.exp(-2.5 * t))
    p, d = along(dd)
    bounce = abs(math.sin(t * math.pi * 2.2)) * 0.35 * math.exp(-2.8 * t)
    return Vector((p.x, p.y, BALL_R + bounce)), d

prev = None; roll = 0.0
for f in range(1, FRAMES + 2):
    pos, d = ball_pos(f)
    if prev is not None and f > THROW:
        roll += (Vector((pos.x, pos.y)) - Vector((prev.x, prev.y))).length / BALL_R
    prev = pos
    ball_pivot.location = pos
    ball_pivot.rotation_euler = (0, 0, math.atan2(d.y, d.x))
    ball.rotation_euler = (0, roll, 0)      # roll about the pivot's sideways axis
    if f % 2 == 1:
        ball_pivot.keyframe_insert("location", frame=f); ball_pivot.keyframe_insert("rotation_euler", frame=f)
        ball.keyframe_insert("rotation_euler", frame=f)

# Cooper spots the ball and chases it: after the throw he pulls ahead of Janie toward it
for f in range(THROW, FRAMES + 2, 2):
    t = min(1.0, (f - THROW) / 40)
    bp, d = ball_pos(f)
    jp, _ = along(WALK_SPEED * (f - 1) / FPS)
    target = Vector((bp.x, bp.y)) - d * 0.75                 # just behind the ball
    home = jp + d * 0.35 - cam_side * 0.75
    cp = home.lerp(target, t * 0.85)
    crig.location = (cp.x, cp.y, 0.0)
    crig.rotation_euler = (0, 0, math.atan2(d.y, d.x) - math.pi / 2)
    crig.keyframe_insert("location", frame=f); crig.keyframe_insert("rotation_euler", frame=f)

# ------------------------------------------------ camera: aerial glide down into a tracking shot
target = bpy.data.objects.new("CamTarget", None); sc.collection.objects.link(target)
cd = bpy.data.cameras.new("Hero"); cd.lens = 32; cd.clip_end = 3000
cam = bpy.data.objects.new("Hero", cd); sc.collection.objects.link(cam)
tr = cam.constraints.new("TRACK_TO"); tr.target = target; tr.track_axis = "TRACK_NEGATIVE_Z"; tr.up_axis = "UP_Y"
def cam_key(f, loc, tgt, lens):
    cam.location = loc; cam.keyframe_insert("location", frame=f)
    target.location = tgt; target.keyframe_insert("location", frame=f)
    cd.lens = lens; cd.keyframe_insert("lens", frame=f)
def mid(f):
    p, d = along(WALK_SPEED * (f - 1) / FPS)
    return p - cam_side * 0.35, d
m1, d1 = mid(1); m100, _ = mid(100); m150, _ = mid(150); mE, dE = mid(FRAMES)
def v3(v2, z): return Vector((v2.x, v2.y, z))
cam_key(1,   v3(m1 + cam_side * 70 - d1 * 45, 48), v3(m1, 0.0), 30)
cam_key(60,  v3(m1 + cam_side * 30 - d1 * 18, 16), v3(mid(60)[0], 0.4), 32)
cam_key(115, v3(m100 + cam_side * 7 - d1 * 2.5, 2.4), v3(m100, 0.85), 38)
cam_key(170, v3(m150 + cam_side * 4.6 + d1 * 0.6, 1.35), v3(m150, 0.8), 40)
cam_key(FRAMES, v3(mE + cam_side * 4.2 + dE * 1.6, 1.25), v3(mE, 0.8), 42)
sc.camera = cam
for ob in (cam, target, cd):
    ad = ob.animation_data
    if ad and ad.action:
        pass  # default Bezier easing gives a smooth glide

# ------------------------------------------------ title card that fades in at the end
def text_obj(body, size, offset, align="CENTER"):
    cu = bpy.data.curves.new(body[:10], "FONT"); cu.body = body; cu.size = size
    cu.align_x = align; cu.align_y = "CENTER"
    ob = bpy.data.objects.new(body[:10], cu); sc.collection.objects.link(ob)
    ob.parent = cam; ob.location = offset
    return ob
tm = bpy.data.materials.new("TitleInk"); tm.use_nodes = True
N = tm.node_tree.nodes; L = tm.node_tree.links
for n in list(N):
    if n.type != "OUTPUT_MATERIAL":
        N.remove(n)
em = N.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (1.0, 0.93, 0.82, 1); em.inputs["Strength"].default_value = 1.4
tp = N.new("ShaderNodeBsdfTransparent")
mx = N.new("ShaderNodeMixShader")
L.new(tp.outputs[0], mx.inputs[1]); L.new(em.outputs[0], mx.inputs[2])
L.new(mx.outputs[0], N["Material Output"].inputs["Surface"])
if hasattr(tm, "surface_render_method"):
    tm.surface_render_method = "BLENDED"
fac = mx.inputs["Fac"]
fac.default_value = 0.0; fac.keyframe_insert("default_value", frame=205)
fac.default_value = 1.0; fac.keyframe_insert("default_value", frame=240)
title = text_obj("Janie & Cooper", 0.062, (0, 0.175, -1.0))
sub = text_obj("Niguel Heights Park  Â·  Laguna Niguel", 0.024, (0, 0.125, -1.0))
credit = text_obj("Map data Â© OpenStreetMap contributors", 0.012, (0.37, -0.2, -1.0), "RIGHT")
for t in (title, sub, credit):
    t.data.materials.append(tm)
# soft drop shadow behind the title lines so they read against the bright sky
sm = tm.copy(); sm.name = "TitleShadow"
em2 = next(n for n in sm.node_tree.nodes if n.type == "EMISSION")
em2.inputs["Color"].default_value = (0.02, 0.012, 0.008, 1); em2.inputs["Strength"].default_value = 0.0
mx2 = next(n for n in sm.node_tree.nodes if n.type == "MIX_SHADER")
fc = sm.node_tree.animation_data.action if sm.node_tree.animation_data else None
for t, dx in ((title, 0.0025), (sub, 0.0015)):
    sh = t.copy(); sh.data = t.data.copy(); sc.collection.objects.link(sh)
    sh.data.materials.clear(); sh.data.materials.append(sm)
    sh.location = (t.location.x + dx, t.location.y - dx, t.location.z - 0.002)
mx2.inputs["Fac"].default_value = 0.0; mx2.inputs["Fac"].keyframe_insert("default_value", frame=205)
mx2.inputs["Fac"].default_value = 0.55; mx2.inputs["Fac"].keyframe_insert("default_value", frame=240)

# ------------------------------------------------ render settings
sc.frame_start, sc.frame_end = 1, FRAMES
sc.render.fps = FPS
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
sc.eevee.taa_render_samples = 24
sc.render.use_motion_blur = True
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "final.blend"))

if MODE == "stills":
    os.makedirs(os.path.join(HERE, "renders"), exist_ok=True)
    for f in (1, 90, 150, 280):
        sc.frame_set(f)
        sc.render.filepath = os.path.join(HERE, "renders", f"final_f{f:03d}.png")
        bpy.ops.render.render(write_still=True)
        print("[FINAL] still", f)
else:
    img = sc.render.image_settings
    if hasattr(img, "media_type"):
        img.media_type = "VIDEO"
    img.file_format = "FFMPEG"
    sc.render.ffmpeg.format = "MPEG4"; sc.render.ffmpeg.codec = "H264"
    sc.render.ffmpeg.constant_rate_factor = "HIGH"
    sc.render.filepath = os.path.join(HERE, "Janie_and_Cooper_Niguel_Heights_Park.mp4")
    bpy.ops.render.render(animation=True)
    print("[FINAL] done", sc.render.filepath)
