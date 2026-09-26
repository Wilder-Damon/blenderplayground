import bpy
rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
for n in ("mixamorig:LeftUpLeg", "mixamorig:LeftLeg", "mixamorig:LeftArm"):
    b = rig.pose.bones[n]
    print("[LEG]", n, "locks", tuple(b.lock_rotation), "mode", b.rotation_mode, "constraints", [c.type for c in b.constraints],
          "vg-weighted verts", sum(1 for v in rig.children[0].data.vertices for g in v.groups if rig.children[0].vertex_groups[g.group].name == n) if rig.children else "?")
print("[LEG] children", [(c.name, [m.type for m in c.modifiers]) for c in rig.children][:6])
