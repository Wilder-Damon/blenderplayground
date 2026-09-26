"""Convert a Godot --write-movie AVI to MP4 and dump a few frames as PNGs, using Blender's sequencer.

blender --background --factory-startup --python tools/movie_convert.py -- captures/autoplay.avi [frame frame ...]
"""
import bpy, os, sys

args = sys.argv[sys.argv.index("--") + 1:]
src = os.path.abspath(args[0])
frames = [int(a) for a in args[1:]] or [1, 150, 300, 450, 600]
base = os.path.splitext(src)[0]

sc = bpy.context.scene
sc.sequence_editor_create()
strips = sc.sequence_editor.strips if hasattr(sc.sequence_editor, "strips") else sc.sequence_editor.sequences
strip = strips.new_movie("clip", src, channel=1, frame_start=1)
sc.frame_start, sc.frame_end = 1, strip.frame_final_end - 1
sc.render.fps = 30
clip = bpy.data.movieclips.load(src) if False else None
sc.render.resolution_x, sc.render.resolution_y = 1280, 720
sc.render.resolution_percentage = 100

img = sc.render.image_settings
if hasattr(img, "media_type"):
    img.media_type = "IMAGE"
img.file_format = "PNG"
for f in frames:
    if f <= sc.frame_end:
        sc.frame_set(f)
        sc.render.filepath = f"{base}_f{f:04d}.png"
        bpy.ops.render.render(write_still=True)

if hasattr(img, "media_type"):
    img.media_type = "VIDEO"
img.file_format = "FFMPEG"
sc.render.ffmpeg.format = "MPEG4"; sc.render.ffmpeg.codec = "H264"
sc.render.ffmpeg.constant_rate_factor = "HIGH"
sc.render.filepath = base + ".mp4"
bpy.ops.render.render(animation=True)
print("[CONVERT] frames", sc.frame_end, "->", sc.render.filepath)
