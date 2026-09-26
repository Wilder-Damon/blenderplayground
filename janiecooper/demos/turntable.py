import bpy, os, sys, math, runpy

# Usage: blender --background --python turntable.py -- [preview|full]
quality = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "preview"

here = os.path.dirname(os.path.abspath(__file__))
runpy.run_path(os.path.join(here, "glass_sphere.py"), run_name="scene")
scene = bpy.context.scene
cam = scene.camera

# --- Orbit: parent the camera to a pivot at the origin and spin it once ---
pivot = bpy.data.objects.new("Pivot", None)
scene.collection.objects.link(pivot)
cam.parent = pivot

frames = 120  # 5 s at 24 fps
scene.frame_start, scene.frame_end = 1, frames
scene.render.fps = 24
pivot.rotation_euler = (0, 0, 0)
pivot.keyframe_insert("rotation_euler", index=2, frame=1)
# Key frame N+1 at 360° so frame N is one step short of a full turn -> seamless loop
pivot.rotation_euler = (0, 0, math.radians(360))
pivot.keyframe_insert("rotation_euler", index=2, frame=frames + 1)
for fc in pivot.animation_data.action.fcurves if hasattr(pivot.animation_data.action, "fcurves") else []:
    for kp in fc.keyframe_points:
        kp.interpolation = 'LINEAR'
# Blender 5 layered actions: set linear interpolation via channelbag
action = pivot.animation_data.action
for layer in getattr(action, "layers", []):
    for strip in layer.strips:
        for bag in strip.channelbags:
            for fc in bag.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'

# --- Quality ---
if quality == "preview":
    scene.render.resolution_x, scene.render.resolution_y = 640, 360
    scene.cycles.samples = 16
else:
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    scene.cycles.samples = 128
scene.cycles.use_denoising = True

# --- Output: H.264 MP4 ---
img = scene.render.image_settings
if hasattr(img, "media_type"):
    img.media_type = 'VIDEO'
img.file_format = 'FFMPEG'
scene.render.ffmpeg.format = 'MPEG4'
scene.render.ffmpeg.codec = 'H264'
scene.render.ffmpeg.constant_rate_factor = 'HIGH'
scene.render.filepath = os.path.join(here, f"turntable_{quality}.mp4")

print(f"Rendering {frames} frames ({quality}) on {scene.cycles.device} ->", scene.render.filepath)
bpy.ops.render.render(animation=True)
print("Done:", scene.render.filepath)
