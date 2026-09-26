extends Node
## Photo mode: a face-level close-up of Cooper with a caption + link, shared (phones) or downloaded (browsers/desktop).

const GAME_URL := "https://janie-cooper.cooper-game.workers.dev/"
const CAPTION := "Cooper's Park Run"

var main: Node3D           # main.gd (camera, cooper, hud layer, toast)
var _busy := false
var _caption_layer: CanvasLayer
var _flash: ColorRect


func _ready() -> void:
	_caption_layer = CanvasLayer.new()
	_caption_layer.layer = 5
	_caption_layer.visible = false
	add_child(_caption_layer)
	var band := ColorRect.new()
	band.color = Color(0.08, 0.05, 0.03, 0.55)
	band.anchor_top = 1.0; band.anchor_bottom = 1.0; band.anchor_right = 1.0
	band.offset_top = -92
	_caption_layer.add_child(band)
	var title := Label.new()
	title.text = CAPTION
	title.anchor_top = 1.0; title.anchor_bottom = 1.0
	title.offset_top = -86; title.offset_left = 28
	title.add_theme_font_size_override("font_size", 40)
	title.add_theme_color_override("font_color", Color(1.0, 0.9, 0.72))
	_caption_layer.add_child(title)
	var link := Label.new()
	link.text = "Play: " + GAME_URL.trim_prefix("https://").trim_suffix("/")
	link.anchor_top = 1.0; link.anchor_bottom = 1.0
	link.offset_top = -38; link.offset_left = 30
	link.add_theme_font_size_override("font_size", 22)
	link.add_theme_color_override("font_color", Color(0.95, 0.85, 0.75))
	_caption_layer.add_child(link)
	var fx := CanvasLayer.new(); fx.layer = 10; add_child(fx)
	_flash = ColorRect.new()
	_flash.color = Color(1, 1, 1, 0)
	_flash.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_flash.mouse_filter = Control.MOUSE_FILTER_IGNORE
	fx.add_child(_flash)


func take_photo() -> void:
	if _busy:
		return
	_busy = true
	var cam: Camera3D = main.camera
	var cooper: CharacterBody3D = main.cooper
	var old_xform := cam.global_transform
	var old_fov := cam.fov
	main.photo_active = true
	cooper.set_physics_process(false)
	# Cooper's model faces -Z; stand the camera in front of his face at his eye level, looking straight at him
	var model: Node3D = cooper.get_child(0)
	var fwd := -model.global_transform.basis.z
	fwd.y = 0.0
	fwd = fwd.normalized()
	var face := cooper.global_position + Vector3(0, 0.42, 0) + fwd * 0.3
	cam.fov = 38.0
	cam.global_position = face + fwd * 1.05 + Vector3(0, 0.02, 0)
	cam.look_at(face, Vector3.UP)
	main.hud_layer().visible = false
	_caption_layer.visible = true
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	var img := main.get_viewport().get_texture().get_image()
	var jpg := img.save_jpg_to_buffer(0.9)
	# restore the game view, with a camera-flash
	_caption_layer.visible = false
	main.hud_layer().visible = true
	cam.fov = old_fov
	cam.global_transform = old_xform
	cooper.set_physics_process(true)
	main.photo_active = false
	_flash.color.a = 0.85
	create_tween().tween_property(_flash, "color:a", 0.0, 0.4)
	_deliver(jpg)
	_busy = false


func _deliver(jpg: PackedByteArray) -> void:
	var name := "cooper-park-run-%s.jpg" % Time.get_datetime_string_from_system().replace(":", "-")
	if OS.has_feature("web"):
		var b64 := Marshalls.raw_to_base64(jpg)
		var js := """
(async function (b64, name, url) {
  const bin = atob(b64); const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const file = new File([bytes], name, { type: "image/jpeg" });
  const text = "Cooper at Niguel Heights Park \\ud83d\\udc36 Play Cooper's Park Run: " + url;
  if (navigator.canShare && navigator.canShare({ files: [file] })) {
    try { await navigator.share({ files: [file], text: text, title: "Cooper's Park Run" }); return "shared"; }
    catch (e) { if (e.name === "AbortError") return "cancelled"; }
  }
  const a = document.createElement("a"); a.href = URL.createObjectURL(file); a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 10000);
  return "downloaded";
})(%s, %s, %s);
""" % [JSON.stringify(b64), JSON.stringify(name), JSON.stringify(GAME_URL)]
		JavaScriptBridge.eval(js, true)
		main.show_toast("Photo taken!", 1.6)
	else:
		var dir := OS.get_system_dir(OS.SYSTEM_DIR_PICTURES)
		for a in OS.get_cmdline_user_args():
			if a.begins_with("--photo-dir="):
				dir = a.get_slice("=", 1)
		var path := dir.path_join(name)
		var f := FileAccess.open(path, FileAccess.WRITE)
		if f:
			f.store_buffer(jpg); f.close()
			main.show_toast("Photo saved to Pictures", 2.0)
			print("[PHOTO] saved ", path)
		else:
			main.show_toast("Couldn't save the photo", 2.0)
