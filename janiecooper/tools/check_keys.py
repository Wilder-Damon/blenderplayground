"""Check a character's motion for frame-to-frame jumps (flicker) in final.blend.
blender --background final.blend --python tools/check_keys.py -- CooperRig
"""
import bpy, sys
name = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "CooperRig"
ob = bpy.data.objects[name]
sc = bpy.context.scene
prev = None; worst = (0, 0)
for f in range(sc.frame_start, sc.frame_end + 1):
    sc.frame_set(f)
    p = ob.matrix_world.translation.copy()
    if prev is not None:
        step = (p - prev).length
        if step > worst[0]:
            worst = (step, f)
    prev = p
print(f"[KEYS] {name}: largest frame-to-frame move {worst[0]*100:.1f} cm at frame {worst[1]} (walking ~5 cm/frame)")
