import bpy, math, os
from mathutils import Vector
HERE = os.path.dirname(bpy.data.filepath)
rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
pb = rig.pose.bones
print("[BONES]", [b.name for b in pb][:40])
def rot(name, axis, deg):
    b = pb[name]; b.rotation_mode = "XYZ"
    e = list(b.rotation_euler); e["XYZ".index(axis)] = math.radians(deg); b.rotation_euler = e
# test: left thigh +30 about X, left arm +50 about Z, right arm +50 about X
rot("mixamorig:LeftUpLeg", "X", -35)
rot("mixamorig:RightLeg", "X", 50)
rot("mixamorig:LeftArm", "Z", -45)
rot("mixamorig:RightArm", "Z", 45)
sc = bpy.context.scene
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.5
sc.render.engine = "BLENDER_EEVEE"; sc.eevee.taa_render_samples = 8
for tag, loc in (("front", (0, -4, 1.0)), ("side", (4, 0, 1.0))):
    cd = bpy.data.cameras.new(tag); cd.lens = 40
    cam = bpy.data.objects.new(tag, cd); cam.location = loc; sc.collection.objects.link(cam)
    cam.rotation_euler = (Vector((0, 0, 0.9)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam; sc.render.resolution_x, sc.render.resolution_y = 400, 500
    sc.render.filepath = os.path.join(HERE, "renders", f"pose_{tag}.png")
    bpy.ops.render.render(write_still=True)
