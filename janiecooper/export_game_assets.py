"""Export the park, Cooper and Janie as glTF (.glb) for the Godot game in ../cooper-game.

Run on final.blend (it already has everything combined and animated):
  blender --background final.blend --python export_game_assets.py
Outputs to ../cooper-game/assets/.
"""
import bpy, os, math

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "cooper-game", "assets"))
os.makedirs(OUT, exist_ok=True)
sc = bpy.context.scene

def flatten_procedural_materials():
    """glTF can't carry Blender's procedural shaders: replace noise/ramp colour setups with their average colour."""
    for m in bpy.data.materials:
        if not m.use_nodes:
            continue
        nt = m.node_tree
        for b in [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"]:
            sock = b.inputs["Base Color"]
            if not sock.is_linked:
                continue
            src = sock.links[0].from_node
            if src.type in ("VERTEX_COLOR", "TEX_IMAGE", "GROUP"):
                continue                      # these export fine (vertex colours, image textures)
            ramps = [n for n in nt.nodes if n.type == "VALTORGB"]
            if not ramps:
                continue
            els = ramps[0].color_ramp.elements
            avg = [sum(e.color[i] for e in els) / len(els) for i in range(3)]
            for l in list(sock.links):
                nt.links.remove(l)
            sock.default_value = (*avg, 1)
        for b in [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"]:
            nrm = b.inputs["Normal"]
            for l in list(nrm.links):
                if l.from_node.type == "BUMP":
                    nt.links.remove(l)

flatten_procedural_materials()

MAX_TEX = int(os.environ.get("GAME_MAX_TEXTURE", "1024"))

def shrink_textures(limit):
    """Downscale big image textures (Janie's MakeHuman maps are 2-4K) so the web build stays small."""
    for img in bpy.data.images:
        if img.source != "FILE":
            continue
        w, h = img.size
        if max(w, h) > limit:
            s = limit / max(w, h)
            img.scale(max(1, int(w * s)), max(1, int(h * s)))
            print("[EXPORT] texture", img.name, f"{w}x{h} ->", tuple(img.size))

shrink_textures(MAX_TEX)


def select_only(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.hide_set(False); o.hide_render = False
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]

def export(name, objs, animations=False):
    select_only(objs)
    path = os.path.join(OUT, name + ".glb")
    kw = dict(filepath=path, use_selection=True, export_format="GLB", export_apply=True,
              export_yup=True, export_animations=animations, export_image_format="AUTO")
    try:
        bpy.ops.export_scene.gltf.get_rna_type().properties["export_vertex_color"]
        kw["export_vertex_color"] = "ACTIVE"          # Cooper's coat colours live in a colour attribute
    except KeyError:
        kw["export_colors"] = True
    if animations:
        kw.update(export_animation_mode="ACTIONS", export_force_sampling=True)
    bpy.ops.export_scene.gltf(**kw)
    print("[EXPORT]", name, round(os.path.getsize(path) / 1e6, 2), "MB")

def descendants(root):
    out = [root]
    for c in root.children_recursive:
        out.append(c)
    return out

# ---- clear the film-only animation (walk along the path, camera, title) so characters export in place
for ob in bpy.data.objects:
    if ob.type == "ARMATURE" and ob.animation_data:
        pass
cooper = bpy.data.objects["CooperRig"]
janie = next(o for o in bpy.data.objects if o.type == "ARMATURE" and o.name.startswith("Janie"))

def reset_object_motion(rig):
    """Keep the bone (walk-cycle) keys, drop the object-level path keys, and trim to one gait cycle."""
    act = rig.animation_data.action
    # remove fcurves that move/rotate the whole object (path following)
    for fcs in _fcurve_collections(act):
        for fc in list(fcs):
            if not fc.data_path.startswith("pose.bones"):
                fcs.remove(fc)
    rig.location = (0, 0, 0); rig.rotation_euler = (0, 0, 0)
    act.name = rig.name + "_Walk"
    return act

def _fcurve_collections(act):
    if hasattr(act, "fcurves") and len(getattr(act, "fcurves", [])) >= 0:
        try:
            yield act.fcurves
            return
        except Exception:
            pass
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for bag in strip.channelbags:
                yield bag.fcurves

for rig in (cooper, janie):
    reset_object_motion(rig)

# one clean looping cycle for each character (frames chosen to match the procedural gait periods)
FPS = 24
cooper_cycle = round(FPS / 2.6)                          # Cooper's step cycle
janie_cycle = round(2 * 0.68 / 1.15 * FPS)               # Janie's stride cycle
sc.frame_start = 1

# Cooper
sc.frame_end = 1 + cooper_cycle * 2
export("cooper", descendants(cooper), animations=True)
# Janie
sc.frame_end = 1 + janie_cycle
export("janie", descendants(janie), animations=True)

# Park: everything that isn't a character, camera, light or title
skip = set(descendants(cooper)) | set(descendants(janie))
park = [o for o in sc.objects if o.type == "MESH" and o not in skip and o.visible_get()]
export("park", park)
print("[EXPORT] cycles: cooper", cooper_cycle, "janie", janie_cycle)
