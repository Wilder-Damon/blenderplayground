"""Pose-test Janie's arms at a walk extreme, front + side close-ups.
blender --background janie.blend --python tools/arm_test.py -- <armZ> <swing> <foreBend> <foreAxis> <tag>
"""
import bpy, math, os, sys
from mathutils import Vector
a = sys.argv[sys.argv.index("--") + 1:]
arm_z, swing, fore, fore_axis, tag = float(a[0]), float(a[1]), float(a[2]), a[3], a[4]
HERE = os.path.dirname(bpy.data.filepath)
rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
pb = rig.pose.bones
for b in pb: b.rotation_mode = "XYZ"
def rot(name, **k):
    e = pb[name].rotation_euler
    for ax, v in k.items(): setattr(e, ax, math.radians(v))
# mid-stride: left leg forward, right arm forward
rot("mixamorig:LeftUpLeg", x=-24); rot("mixamorig:RightUpLeg", x=24)
rot("mixamorig:LeftLeg", x=6); rot("mixamorig:RightLeg", x=30)
rot("mixamorig:LeftArm", z=-arm_z, x=-swing); rot("mixamorig:RightArm", z=arm_z, x=swing)
s = 1 if fore_axis.startswith("+") else -1; ax = fore_axis[-1].lower()
rot("mixamorig:LeftForeArm", **{ax: fore * s}); rot("mixamorig:RightForeArm", **{ax: -fore * s if ax == "z" else fore * s})
sc = bpy.context.scene
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.4
sc.render.engine = "BLENDER_EEVEE"; sc.eevee.taa_render_samples = 16
sc.view_settings.view_transform = "AgX"
for view, loc in (("front", (0, -3.2, 1.0)), ("side", (3.2, 0, 1.0))):
    cd = bpy.data.cameras.new(view); cd.lens = 50
    cam = bpy.data.objects.new(view, cd); cam.location = loc; sc.collection.objects.link(cam)
    cam.rotation_euler = (Vector((0, 0, 0.95)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam; sc.render.resolution_x, sc.render.resolution_y = 360, 560
    sc.render.filepath = os.path.join(HERE, "renders", f"arm_{tag}_{view}.png")
    bpy.ops.render.render(write_still=True)
