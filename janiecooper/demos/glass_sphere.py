import bpy, os, math

# Start from an empty scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# --- Render settings (Cycles for proper glass refraction) ---
scene.render.engine = 'CYCLES'
# Use the NVIDIA GPU via OptiX (RTX cores); fall back to CPU if unavailable
cprefs = bpy.context.preferences.addons["cycles"].preferences
try:
    cprefs.compute_device_type = 'OPTIX'
    cprefs.refresh_devices()
    gpus = [d for d in cprefs.devices if d.type == 'OPTIX']
    for d in cprefs.devices:
        d.use = d.type == 'OPTIX'
    scene.cycles.device = 'GPU' if gpus else 'CPU'
except TypeError:
    scene.cycles.device = 'CPU'
# OpenImageDenoise gives cleaner glass than the OptiX denoiser, and runs on RTX GPUs too
scene.cycles.denoiser = 'OPENIMAGEDENOISE'
print("Render device:", scene.cycles.device)
scene.cycles.samples = 128
scene.cycles.use_denoising = True
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "glass_sphere.png")
scene.view_settings.view_transform = 'AgX'

# --- World: soft gradient studio backdrop ---
world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
wn = world.node_tree.nodes
wl = world.node_tree.links
bg = wn["Background"]
grad = wn.new("ShaderNodeTexGradient")
coord = wn.new("ShaderNodeTexCoord")
ramp = wn.new("ShaderNodeValToRGB")
ramp.color_ramp.elements[0].color = (0.02, 0.02, 0.03, 1)
ramp.color_ramp.elements[1].color = (0.35, 0.4, 0.5, 1)
mapping = wn.new("ShaderNodeMapping")
mapping.inputs["Rotation"].default_value = (0, math.radians(-90), 0)
wl.new(coord.outputs["Generated"], mapping.inputs["Vector"])
wl.new(mapping.outputs["Vector"], grad.inputs["Vector"])
wl.new(grad.outputs["Fac"], ramp.inputs["Fac"])
wl.new(ramp.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 0.6

# --- Checkered floor ---
bpy.ops.mesh.primitive_plane_add(size=40)
floor = bpy.context.object
fmat = bpy.data.materials.new("Checker")
fmat.use_nodes = True
fn = fmat.node_tree.nodes
fbsdf = fn["Principled BSDF"]
checker = fn.new("ShaderNodeTexChecker")
checker.inputs["Scale"].default_value = 40
checker.inputs["Color1"].default_value = (0.9, 0.9, 0.9, 1)
checker.inputs["Color2"].default_value = (0.05, 0.05, 0.05, 1)
fmat.node_tree.links.new(checker.outputs["Color"], fbsdf.inputs["Base Color"])
fbsdf.inputs["Roughness"].default_value = 0.25
floor.data.materials.append(fmat)

# --- Glass sphere ---
bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(0, 0, 1), segments=64, ring_count=32)
sphere = bpy.context.object
bpy.ops.object.shade_smooth()
gmat = bpy.data.materials.new("Glass")
gmat.use_nodes = True
gbsdf = gmat.node_tree.nodes["Principled BSDF"]
gbsdf.inputs["Base Color"].default_value = (0.85, 0.95, 1.0, 1)
gbsdf.inputs["Roughness"].default_value = 0.0
gbsdf.inputs["IOR"].default_value = 1.45
gbsdf.inputs["Transmission Weight"].default_value = 1.0
sphere.data.materials.append(gmat)

# --- Studio lights ---
def area_light(name, loc, rot, energy, size, color=(1, 1, 1)):
    data = bpy.data.lights.new(name, 'AREA')
    data.energy = energy
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    obj.location = loc
    obj.rotation_euler = [math.radians(a) for a in rot]
    scene.collection.objects.link(obj)

area_light("Key", (4, -3, 5), (45, 0, 50), 800, 3, (1.0, 0.95, 0.9))
area_light("Fill", (-5, -2, 3), (60, 0, -70), 250, 4, (0.8, 0.9, 1.0))
area_light("Rim", (0, 5, 4), (-50, 0, 180), 500, 2)

# --- Camera ---
cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 50
cam = bpy.data.objects.new("Camera", cam_data)
cam.location = (0, -7, 2.6)
scene.collection.objects.link(cam)
scene.camera = cam
target = bpy.data.objects.new("Target", None)
target.location = (0, 0, 0.9)
scene.collection.objects.link(target)
track = cam.constraints.new('TRACK_TO')
track.target = target
track.track_axis = 'TRACK_NEGATIVE_Z'
track.up_axis = 'UP_Y'

# Only render the still when run directly (turntable.py reuses this scene)
if __name__ == "__main__":
    bpy.ops.render.render(write_still=True)
    print("Saved:", scene.render.filepath)
