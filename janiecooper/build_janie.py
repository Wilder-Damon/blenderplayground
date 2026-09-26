"""Janie: MPFB (MakeHuman) character styled from the family's reference photo.

Shoulder-length straight hair, darker roots blending to caramel/honey, ends flipping out;
warm medium-light skin; dark brown eyes; berry-rose lips; casual park outfit.

Usage: blender --background --python build_janie.py -- [preview]
"""
import bpy, os, sys, math
from mathutils import Vector

from bl_ext.user_default.mpfb.services.humanservice import HumanService
from bl_ext.user_default.mpfb.services.locationservice import LocationService
from bl_ext.user_default.mpfb.services.objectservice import ObjectService

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = LocationService.get_user_data()

def asset(kind, name, ext="mhclo"):
    return os.path.join(DATA, kind, name, f"{name}.{ext}")

MACROS = {
    "gender": 0.0,        # female
    "age": 0.64,          # mid-40s on MakeHuman's age scale
    "muscle": 0.42,
    "weight": 0.56,
    "proportions": 0.55,
    "height": 0.33,       # ~163 cm
    "cupsize": 0.5,
    "firmness": 0.5,
    # MakeHuman face-structure blend: Janie is Korean
    "race": {"asian": 1.0, "caucasian": 0.0, "african": 0.0},
}

def find_child(basemesh, kind):
    return ObjectService.find_object_of_type_amongst_nearest_relatives(basemesh, kind)

def principled(ob):
    for slot in ob.material_slots:
        m = slot.material
        if m and m.use_nodes:
            for n in m.node_tree.nodes:
                if n.type == "BSDF_PRINCIPLED":
                    yield m, n

def style_hair(hair):
    """Replace the stock hair material with a root-to-tip gradient: dark brown roots -> caramel/honey ends."""
    m = bpy.data.materials.new("JanieHair"); m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; L = nt.links
    b = N["Principled BSDF"]
    b.inputs["Roughness"].default_value = 0.5
    try:
        b.inputs["Sheen Weight"].default_value = 0.1
        b.inputs["Specular IOR Level"].default_value = 0.35
    except KeyError:
        pass
    # vertical gradient in object space: dark brown roots -> caramel -> honey ends
    tc = N.new("ShaderNodeTexCoord")
    sep = N.new("ShaderNodeSeparateXYZ"); L.new(tc.outputs["Generated"], sep.inputs["Vector"])
    ramp = N.new("ShaderNodeValToRGB"); cr = ramp.color_ramp
    cr.elements[0].position = 0.15; cr.elements[0].color = (0.16, 0.065, 0.022, 1)  # honey ends
    cr.elements[1].position = 0.85; cr.elements[1].color = (0.018, 0.008, 0.005, 1) # dark roots
    mid = cr.elements.new(0.5); mid.color = (0.075, 0.03, 0.012, 1)                 # caramel
    L.new(sep.outputs["Z"], ramp.inputs["Fac"])
    col = ramp.outputs["Color"]
    # use the stock texture's strand detail (as brightness) and its alpha for the strand cards
    old = hair.material_slots[0].material if hair.material_slots else None
    img = None
    if old and old.use_nodes:
        img = next((n.image for n in old.node_tree.nodes if n.type == "TEX_IMAGE" and n.image), None)
    if img:
        it = N.new("ShaderNodeTexImage"); it.image = img
        uv = N.new("ShaderNodeUVMap"); L.new(uv.outputs["UV"], it.inputs["Vector"])
        bw = N.new("ShaderNodeRGBToBW"); L.new(it.outputs["Color"], bw.inputs["Color"])
        gain = N.new("ShaderNodeMath"); gain.operation = "MULTIPLY"; gain.inputs[1].default_value = 2.2
        L.new(bw.outputs["Val"], gain.inputs[0])
        mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        L.new(col, next(s for s in mix.inputs if s.name == "A" and s.type == "RGBA"))
        comb = N.new("ShaderNodeCombineXYZ")
        for k in "XYZ":
            L.new(gain.outputs[0], comb.inputs[k])
        L.new(comb.outputs["Vector"], next(s for s in mix.inputs if s.name == "B" and s.type == "RGBA"))
        col = next(o for o in mix.outputs if o.type == "RGBA")
        L.new(it.outputs["Alpha"], b.inputs["Alpha"])
        if hasattr(m, "surface_render_method"):
            m.surface_render_method = "DITHERED"
    L.new(col, b.inputs["Base Color"])
    hair.data.materials.clear(); hair.data.materials.append(m)

def lengthen_hair(hair, head_top_z, extra=0.07):
    """Stretch the lower part of the bob down to shoulder length and flip the ends outward slightly."""
    me = hair.data
    zs = [v.co.z for v in me.vertices]
    zmin, zmax = min(zs), max(zs)
    for v in me.vertices:
        t = (zmax - v.co.z) / max(zmax - zmin, 1e-6)          # 0 at crown, 1 at the ends
        if t > 0.45:
            k = (t - 0.45) / 0.55
            v.co.z -= extra * k
            flip = 0.018 * k ** 3                                # ends flick outwards
            r = Vector((v.co.x, v.co.y, 0))
            if r.length > 1e-6:
                v.co += r.normalized() * flip

def recolor(ob, rgb, keep_texture=False, rough=None):
    for m, b in principled(ob):
        if not keep_texture:
            for l in list(b.inputs["Base Color"].links):
                m.node_tree.links.remove(l)
        b.inputs["Base Color"].default_value = (*rgb, 1)
        if rough is not None:
            b.inputs["Roughness"].default_value = rough

def build():
    human = HumanService.create_human(macro_detail_dict=MACROS, scale=0.1)
    human.name = "Janie"
    HumanService.set_character_skin(os.path.join(DATA, "skins", "middleage_asian_female", "middleage_asian_female.mhmat"),
                                    human, skin_type="ENHANCED_SSS")
    rig = HumanService.add_builtin_rig(human, "mixamo")   # rig first, so clothes/hair get skinned to it
    HumanService.add_mhclo_asset(asset("eyes", "high-poly"), human, asset_type="Eyes", material_type="PROCEDURAL_EYES")
    for kind, name in (("eyebrows", "eyebrow010"), ("eyelashes", "eyelashes02"), ("teeth", "teeth_base"), ("tongue", "tongue01")):
        path = asset(kind, name)
        if not os.path.exists(path):
            cands = [d for d in os.listdir(os.path.join(DATA, kind)) if os.path.isdir(os.path.join(DATA, kind, d))]
            path = asset(kind, cands[0])
        HumanService.add_mhclo_asset(path, human, asset_type=kind.capitalize())
    hair = HumanService.add_mhclo_asset(asset("hair", "bob02"), human, asset_type="Hair", subdiv_levels=0)
    top = HumanService.add_mhclo_asset(asset("clothes", "female_casualsuit01"), human, asset_type="Clothes")
    shoes = HumanService.add_mhclo_asset(asset("clothes", "shoes05"), human, asset_type="Clothes")
    return human, rig, hair, top, shoes

def style_outfit(outfit, waist_z):
    """Keep the jeans texture, but make the t-shirt a plain soft cream (no logo)."""
    me = outfit.data
    attr = me.attributes.new("is_top", "FLOAT", "POINT")
    for i, v in enumerate(me.vertices):
        z = (outfit.matrix_world @ v.co).z
        attr.data[i].value = max(0.0, min(1.0, (z - waist_z) / 0.03))
    for m, b in principled(outfit):
        nt = m.node_tree; N = nt.nodes; L = nt.links
        src = b.inputs["Base Color"].links[0].from_socket if b.inputs["Base Color"].links else None
        at = N.new("ShaderNodeAttribute"); at.attribute_name = "is_top"
        mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"
        a_in = next(s for s in mix.inputs if s.name == "A" and s.type == "RGBA")
        b_in = next(s for s in mix.inputs if s.name == "B" and s.type == "RGBA")
        if src:
            L.new(src, a_in)
        b_in.default_value = (0.72, 0.68, 0.60, 1)
        L.new(at.outputs["Fac"], mix.inputs["Factor"])
        L.new(next(o for o in mix.outputs if o.type == "RGBA"), b.inputs["Base Color"])

def group_input(m, name, value):
    for n in m.node_tree.nodes:
        if n.type == "GROUP" and name in n.inputs:
            n.inputs[name].default_value = value

def style_face(human, eyes):
    """Warmer skin, berry-rose lips, dark brown eyes (MPFB material group inputs)."""
    for s in human.material_slots:
        m = s.material
        if not m:
            continue
        if m.name.endswith(".lips"):
            group_input(m, "colorMixIn", (0.55, 0.06, 0.16, 1))
            group_input(m, "colorMixInStrength", 0.5)
            group_input(m, "Roughness", 0.3)
        elif not m.name.endswith(("nails",)):
            group_input(m, "colorMixIn", (0.95, 0.62, 0.42, 1))   # warm, a touch deeper
            group_input(m, "colorMixInStrength", 0.14)
            group_input(m, "Brightness", -0.04)
    for s in eyes.material_slots:
        m = s.material
        group_input(m, "IrisMajorColor", (0.10, 0.045, 0.018, 1))
        group_input(m, "IrisMinorColor", (0.035, 0.016, 0.008, 1))
        group_input(m, "IrisSection4Color", (0.012, 0.008, 0.006, 1))
        group_input(m, "EyeWhiteColor", (0.85, 0.82, 0.8, 1))

def head_position(rig):
    pb = next(b for b in rig.pose.bones if b.name.lower().endswith("head"))
    return rig.matrix_world @ pb.head, rig.matrix_world @ pb.tail

def preview(human, rig, hair, outfit):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.view_settings.view_transform = "AgX"
    w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.45, 0.47, 0.5, 1)
    w.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.5
    bpy.ops.mesh.primitive_plane_add(size=10)
    hh, ht = head_position(rig)
    face = hh + Vector((0, 0, 0.06))
    for name, off, e, s in (("Key", (-0.9, -1.2, 0.6), 120, 1.2), ("Fill", (1.2, -1.0, 0.1), 45, 1.5), ("Rim", (0.4, 1.2, 0.6), 90, 0.8)):
        l = bpy.data.lights.new(name, "AREA"); l.energy = e; l.size = s
        o = bpy.data.objects.new(name, l); o.location = face + Vector(off); sc.collection.objects.link(o)
        o.rotation_euler = (face - o.location).to_track_quat("-Z", "Y").to_euler()
    os.makedirs(os.path.join(HERE, "renders"), exist_ok=True)
    shots = (("portrait", face + Vector((0.12, -0.75, 0.02)), face, 85, 800, 1000),
             ("full", Vector((0.8, -3.6, 1.0)), Vector((0, 0, 0.85)), 50, 800, 1000))
    for tag, loc, tgt, lens, rx, ry in shots:
        cd = bpy.data.cameras.new(tag); cd.lens = lens
        cam = bpy.data.objects.new(tag, cd); cam.location = loc; sc.collection.objects.link(cam)
        cam.rotation_euler = (tgt - loc).to_track_quat("-Z", "Y").to_euler()
        sc.camera = cam
        sc.render.resolution_x, sc.render.resolution_y = rx, ry
        sc.render.filepath = os.path.join(HERE, "renders", f"janie_{tag}.png")
        bpy.ops.render.render(write_still=True)

if __name__ == "__main__":
    bpy.ops.wm.read_factory_settings(use_empty=True)
    human, rig, hair, top, shoes = build()
    bpy.context.view_layer.update()
    hh, _ = head_position(rig)
    style_hair(hair)
    lengthen_hair(hair, hh.z)
    style_outfit(top, waist_z=hh.z * 0.62)
    style_face(human, find_child(human, "Eyes"))
    from bl_ext.user_default.mpfb.services.faceservice import FaceService
    print("[JANIE] faceunits installed:", FaceService.is_faceunits01_installed(),
          "expressions:", FaceService.list_available_expressions()[:20])
    zs = [(human.matrix_world @ v.co).z for v in human.data.vertices]
    print("[JANIE] height m:", round(max(zs) - min(zs), 3), "head z", round(hh.z, 3))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "janie.blend"))
    if "preview" in sys.argv:
        preview(human, rig, hair, top)
