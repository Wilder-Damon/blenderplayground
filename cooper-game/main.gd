extends Node3D
## Cooper's Park Run: sets up Niguel Heights Park at golden hour, Cooper, Janie, the beach ball and the HUD.
## Map data (c) OpenStreetMap contributors, ODbL.
##
## Controls: WASD / arrows to waddle, Shift for zoomies, Space to hop, Q/E or right-mouse drag to turn the camera.
## Run with `-- --autopilot` to watch Cooper play by himself (used for testing).

const CooperScript := preload("res://cooper.gd")
const JanieScript := preload("res://janie.gd")
const TouchScript := preload("res://touch_controls.gd")

var cooper: CharacterBody3D
var janie: Node3D
var ball: RigidBody3D
var camera: Camera3D
var cam_yaw := 0.0
var fetches := 0
var score_label: Label
var toast: Label
var _toast_time := 0.0
var _intro: Control
var _autopilot := false
var _dbg_t := 0.0

# Quality presets (F2 cycles, F3 shows fps). Upscaling renders fewer pixels and FSR 2 rebuilds the detail.
const QUALITY_NAMES := ["Fast", "Balanced", "Pretty"]
var quality := 1
var fps_label: Label
var touch: Control
var _hud_layer: CanvasLayer
var _help: Label
var _env: Environment
var _sun: DirectionalLight3D


func _ready() -> void:
	_autopilot = "--autopilot" in OS.get_cmdline_user_args()
	_setup_input()
	var layout: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/park_layout.json"))
	var path := _to_godot(layout["loop_path"], 0.05)
	var boundary := _to_godot(layout["park_boundary"], 0.0)

	_setup_environment()
	add_child(load("res://assets/park.glb").instantiate())
	_add_ground()
	_add_boundary_walls(boundary)

	ball = _make_ball()
	add_child(ball)

	cooper = CharacterBody3D.new()
	cooper.set_script(CooperScript)
	add_child(cooper)
	cooper.setup(load("res://assets/cooper.glb").instantiate())

	janie = Node3D.new()
	janie.set_script(JanieScript)
	add_child(janie)
	janie.setup(load("res://assets/janie.glb").instantiate(), path, 0.62)
	janie.ball = ball
	janie.cooper = cooper
	janie.throw_targets = _lawn_targets(boundary, path)
	janie.fetched.connect(_on_fetched)
	if "--debug-janie" in OS.get_cmdline_user_args():
		for n in janie.find_children("*", "MeshInstance3D", true, false):
			var mi := n as MeshInstance3D
			print("[JANIE] mesh %s visible=%s aabb=%s skin=%s" % [mi.name, mi.is_visible_in_tree(), mi.get_aabb(), mi.skin != null])
		print("[JANIE] at ", janie.global_position, " cooper at ", cooper.global_position)

	# start: Cooper next to Janie, ball a little way out on the lawn
	cooper.global_position = janie.global_position + Vector3(1.2, 0.3, 0.8)
	ball.global_position = janie.global_position.lerp(janie.throw_targets[0], 0.5) + Vector3(0, 0.5, 0)
	cam_yaw = atan2(cooper.global_position.x - ball.global_position.x, cooper.global_position.z - ball.global_position.z)

	camera = Camera3D.new()
	camera.fov = 60.0
	camera.far = 3000.0
	add_child(camera)
	_setup_hud()


func _to_godot(pts: Array, h: float) -> Array[Vector3]:
	var out: Array[Vector3] = []
	for p in pts:
		out.append(Vector3(p[0], h, -p[1]))      # Blender (x east, y north) -> Godot (x, up, -z north)
	return out


func _setup_input() -> void:
	var binds := {
		"move_forward": [KEY_W, KEY_UP], "move_back": [KEY_S, KEY_DOWN],
		"move_left": [KEY_A, KEY_LEFT], "move_right": [KEY_D, KEY_RIGHT],
		"zoomies": [KEY_SHIFT], "hop": [KEY_SPACE], "cam_left": [KEY_Q], "cam_right": [KEY_E],
	}
	for action in binds:
		if not InputMap.has_action(action):
			InputMap.add_action(action)
		for k in binds[action]:
			var ev := InputEventKey.new()
			ev.physical_keycode = k
			InputMap.action_add_event(action, ev)


func _setup_environment() -> void:
	var sky_mat := ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color(0.32, 0.45, 0.66)
	sky_mat.sky_horizon_color = Color(1.0, 0.72, 0.48)
	sky_mat.ground_horizon_color = Color(0.72, 0.58, 0.45)
	sky_mat.ground_bottom_color = Color(0.25, 0.22, 0.2)
	sky_mat.sun_angle_max = 20.0
	var sky := Sky.new()
	sky.sky_material = sky_mat
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 0.8
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.ssao_enabled = true
	env.glow_enabled = true
	env.fog_enabled = true
	env.fog_light_color = Color(1.0, 0.8, 0.62)
	env.fog_density = 0.0025
	env.fog_sky_affect = 0.2
	_env = env
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)

	# low golden sun in the west-south-west, like the film
	var sun := DirectionalLight3D.new()
	sun.light_color = Color(1.0, 0.78, 0.55)
	sun.light_energy = 1.6
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 120.0
	add_child(sun)
	_sun = sun
	var elev := deg_to_rad(14.0)
	var az := deg_to_rad(250.0)          # compass bearing to the sun
	var to_sun := Vector3(sin(az) * cos(elev), sin(elev), -cos(az) * cos(elev))
	sun.look_at_from_position(to_sun * 100.0, Vector3.ZERO)


func _add_ground() -> void:
	var body := StaticBody3D.new()
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(2000, 1, 2000)
	shape.shape = box
	shape.position.y = -0.5
	body.add_child(shape)
	add_child(body)


func _add_boundary_walls(boundary: Array[Vector3]) -> void:
	# invisible walls along the park edge keep Cooper (and the ball) in the park
	var body := StaticBody3D.new()
	add_child(body)
	for i in range(boundary.size() - 1):
		var a := boundary[i]
		var b := boundary[i + 1]
		var seg := b - a
		if seg.length() < 0.3:
			continue
		var shape := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = Vector3(seg.length() + 0.4, 3.0, 0.4)
		shape.shape = box
		shape.position = (a + b) * 0.5 + Vector3(0, 1.5, 0)
		shape.rotation.y = atan2(-seg.z, seg.x)
		body.add_child(shape)


func _lawn_targets(boundary: Array[Vector3], path: Array[Vector3]) -> Array[Vector3]:
	# spots on the open lawn: inside the park, away from the edge
	var centre := Vector3.ZERO
	for p in boundary:
		centre += p
	centre /= boundary.size()
	var out: Array[Vector3] = []
	for p in path:
		var t := p.lerp(centre, randf_range(0.25, 0.55))
		out.append(Vector3(t.x, 0.3, t.z))
	out.shuffle()
	return out


func _make_ball() -> RigidBody3D:
	var b := RigidBody3D.new()
	b.mass = 0.25
	b.linear_damp = 0.35
	b.angular_damp = 0.5
	var pm := PhysicsMaterial.new()
	pm.bounce = 0.55
	pm.friction = 0.5
	b.physics_material_override = pm
	var shape := CollisionShape3D.new()
	var sphere := SphereShape3D.new()
	sphere.radius = 0.28
	shape.shape = sphere
	b.add_child(shape)
	var mesh := MeshInstance3D.new()
	var sm := SphereMesh.new()
	sm.radius = 0.28
	sm.height = 0.56
	mesh.mesh = sm
	var mat := ShaderMaterial.new()
	mat.shader = load("res://beach_ball.gdshader")
	mesh.material_override = mat
	b.add_child(mesh)
	b.continuous_cd = true
	return b


func _setup_hud() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	score_label = Label.new()
	score_label.position = Vector2(24, 18)
	score_label.add_theme_font_size_override("font_size", 30)
	score_label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.7))
	score_label.add_theme_constant_override("outline_size", 8)
	layer.add_child(score_label)
	toast = Label.new()
	toast.anchor_left = 0.5; toast.anchor_right = 0.5; toast.anchor_top = 0.3
	toast.offset_left = -300; toast.offset_right = 300
	toast.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	toast.add_theme_font_size_override("font_size", 44)
	toast.add_theme_color_override("font_color", Color(1.0, 0.9, 0.7))
	toast.add_theme_color_override("font_outline_color", Color(0.25, 0.1, 0.02, 0.8))
	toast.add_theme_constant_override("outline_size", 12)
	layer.add_child(toast)
	var help := Label.new()
	help.text = "WASD: waddle   Shift: zoomies   Space: hop   Q/E: camera   F2: quality   F3: fps   F11: fullscreen      Map data © OpenStreetMap contributors"
	help.anchor_top = 1.0; help.anchor_bottom = 1.0
	help.offset_top = -34; help.offset_left = 24
	help.add_theme_font_size_override("font_size", 16)
	help.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.7))
	help.add_theme_constant_override("outline_size", 6)
	layer.add_child(help)
	_hud_layer = layer
	_help = help
	if DisplayServer.is_touchscreen_available() or "--touch" in OS.get_cmdline_user_args():
		_enable_touch()
		quality = 0      # phones: favour smooth frame rate
	fps_label = Label.new()
	fps_label.anchor_left = 1.0; fps_label.anchor_right = 1.0
	fps_label.offset_left = -360; fps_label.offset_right = -20; fps_label.offset_top = 18
	fps_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	fps_label.add_theme_font_size_override("font_size", 18)
	fps_label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.7))
	fps_label.add_theme_constant_override("outline_size", 6)
	fps_label.visible = false
	layer.add_child(fps_label)
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--quality="):
			quality = clampi(int(a.get_slice("=", 1)), 0, 2)
	_apply_quality()
	_update_score()
	_show_toast("Cooper's Park Run\nBring the ball back to Janie!", 4.0)


func _apply_quality() -> void:
	var vp := get_viewport()
	if OS.has_feature("web"):
		# Browser (WebGL 2 / Compatibility renderer): no FSR 2 or SSAO; lower resolution scale is the main lever
		vp.scaling_3d_mode = Viewport.SCALING_3D_MODE_BILINEAR
		vp.scaling_3d_scale = [0.6, 0.8, 1.0][quality]
		vp.msaa_3d = Viewport.MSAA_DISABLED if quality == 0 else Viewport.MSAA_2X
		_env.ssao_enabled = false
		_env.glow_enabled = quality > 0
		_sun.directional_shadow_max_distance = [50.0, 80.0, 110.0][quality]
		return
	match quality:
		0:  # Fast: 50% resolution upscaled with FSR 2, light effects
			vp.scaling_3d_mode = Viewport.SCALING_3D_MODE_FSR2
			vp.scaling_3d_scale = 0.5
			vp.msaa_3d = Viewport.MSAA_DISABLED
			_env.ssao_enabled = false
			_env.glow_enabled = false
			_sun.directional_shadow_max_distance = 60.0
			RenderingServer.directional_shadow_atlas_set_size(2048, true)
		1:  # Balanced: 67% resolution with FSR 2 (it does its own anti-aliasing)
			vp.scaling_3d_mode = Viewport.SCALING_3D_MODE_FSR2
			vp.scaling_3d_scale = 0.67
			vp.msaa_3d = Viewport.MSAA_DISABLED
			_env.ssao_enabled = false
			_env.glow_enabled = true
			_sun.directional_shadow_max_distance = 90.0
			RenderingServer.directional_shadow_atlas_set_size(4096, true)
		2:  # Pretty: native resolution, everything on
			vp.scaling_3d_mode = Viewport.SCALING_3D_MODE_BILINEAR
			vp.scaling_3d_scale = 1.0
			vp.msaa_3d = Viewport.MSAA_2X
			_env.ssao_enabled = true
			_env.glow_enabled = true
			_sun.directional_shadow_max_distance = 120.0
			RenderingServer.directional_shadow_atlas_set_size(4096, true)


func _unhandled_key_input(event: InputEvent) -> void:
	var k := event as InputEventKey
	if k == null or not k.pressed or k.echo:
		return
	if k.physical_keycode == KEY_F2:
		quality = (quality + 1) % 3
		_apply_quality()
		_show_toast("Quality: %s" % QUALITY_NAMES[quality], 1.2)
	elif k.physical_keycode == KEY_F3:
		fps_label.visible = not fps_label.visible
	elif k.physical_keycode == KEY_F11:
		var full := DisplayServer.window_get_mode() == DisplayServer.WINDOW_MODE_FULLSCREEN
		DisplayServer.window_set_mode(DisplayServer.WINDOW_MODE_WINDOWED if full else DisplayServer.WINDOW_MODE_FULLSCREEN)


func _enable_touch() -> void:
	# on-screen joystick + buttons; also switched on the first time the screen is touched,
	# since some phones/browsers don't report a touchscreen at startup
	if touch:
		return
	touch = Control.new()
	touch.set_script(TouchScript)
	_hud_layer.add_child(touch)
	touch.hop.connect(func(): cooper.touch_hop = true)
	_help.text = "Drag left side: waddle   Drag right side: camera   Buttons: zoomies / hop      Map data © OpenStreetMap contributors"


func _input(event: InputEvent) -> void:
	if touch == null and event is InputEventScreenTouch:
		_enable_touch()
		if quality != 0:
			quality = 0
			_apply_quality()


func _update_score() -> void:
	score_label.text = "Fetches: %d" % fetches


func _show_toast(text: String, seconds: float) -> void:
	toast.text = text
	toast.modulate.a = 1.0
	_toast_time = seconds


func _on_fetched() -> void:
	fetches += 1
	print("[GAME] fetch %d at %.1fs" % [fetches, Time.get_ticks_msec() / 1000.0])
	_update_score()
	_show_toast(["Good boy, Cooper!", "Who's a good boy?!", "Again! Again!", "Best bulldog ever!"].pick_random(), 1.8)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
		cam_yaw -= event.relative.x * 0.006


func _process(delta: float) -> void:
	cam_yaw += (Input.get_action_strength("cam_left") - Input.get_action_strength("cam_right")) * 1.8 * delta
	if _autopilot:
		# steer to the far side of the ball, then push it towards Janie
		var to_janie := janie.global_position - ball.global_position
		to_janie.y = 0.0
		var behind := ball.global_position - to_janie.normalized() * 0.55
		var lined_up := (cooper.global_position - behind).length() < 0.5
		# if Cooper is on Janie's side of the ball, swing wide around it instead of bumping it the wrong way
		var rel := cooper.global_position - ball.global_position
		rel.y = 0.0
		var wrong_side := rel.dot(to_janie.normalized()) > -0.2 and rel.length() < 2.5
		if wrong_side:
			var side := to_janie.normalized().cross(Vector3.UP) * (1.0 if rel.dot(to_janie.cross(Vector3.UP)) > 0.0 else -1.0)
			cooper.autopilot_target = ball.global_position + side * 1.6 - to_janie.normalized() * 1.2
		else:
			cooper.autopilot_target = ball.global_position if lined_up else behind
		_dbg_t += delta
		if _dbg_t > 2.0:
			_dbg_t = 0.0
			print("[DBG] cooper-ball %.1f  ball-janie %.1f  ball %s  lined_up %s" % [
				cooper.global_position.distance_to(ball.global_position), to_janie.length(),
				ball.global_position.snapped(Vector3(0.1, 0.1, 0.1)), lined_up])
		# camera looks from Cooper towards Janie, so the ball and Janie are both in view
		var want := atan2(cooper.global_position.x - janie.global_position.x, cooper.global_position.z - janie.global_position.z)
		cam_yaw = lerp_angle(cam_yaw, want, 1.5 * delta)
	if touch:
		cooper.touch_vector = touch.move
		cooper.touch_zoomies = touch.zoomies
		cam_yaw += touch.cam_drag
		touch.cam_drag = 0.0
	cooper.camera_yaw = cam_yaw
	var offset := Vector3(0, 1.6, 3.6).rotated(Vector3.UP, cam_yaw)
	var want_pos := cooper.global_position + offset
	camera.global_position = camera.global_position.lerp(want_pos, clamp(5.0 * delta, 0.0, 1.0)) if camera.global_position != Vector3.ZERO else want_pos
	camera.look_at(cooper.global_position + Vector3(0, 0.45, 0))
	if touch:
		var r := get_viewport().get_visible_rect().size
		if r.y > r.x * 1.1:
			toast.text = "Turn your phone sideways
to play"
			toast.modulate.a = 1.0
			_toast_time = 0.5
	if _toast_time > 0.0:
		_toast_time -= delta
		toast.modulate.a = clamp(_toast_time / 0.6, 0.0, 1.0)
	if _autopilot and Engine.get_process_frames() % 120 == 0:
		print("[FPS] %d  (%s, quality %s)" % [Engine.get_frames_per_second(), get_viewport().get_visible_rect().size, QUALITY_NAMES[quality]])
	if fps_label.visible:
		fps_label.text = "%d fps  ·  %s  ·  F2: quality" % [Engine.get_frames_per_second(), QUALITY_NAMES[quality]]
