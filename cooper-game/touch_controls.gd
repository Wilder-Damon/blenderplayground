extends Control
## On-screen controls for phones/tablets: drag on the left half to waddle (virtual joystick),
## drag on the right half to turn the camera, and buttons for zoomies and hop.

signal hop
signal photo

const RADIUS := 90.0

var move := Vector2.ZERO       # like Input.get_vector: x right, y down (so up = forward)
var zoomies := false
var cam_drag := 0.0            # accumulated yaw change, consumed by main.gd each frame

var _stick_id := -1
var _stick_origin := Vector2.ZERO
var _cam_id := -1
var _buttons: Array[Button] = []


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	var zoom := _make_button("Zoomies", Vector2(-330, -150))
	zoom.button_down.connect(func(): zoomies = true)
	zoom.button_up.connect(func(): zoomies = false)
	var jump := _make_button("Hop", Vector2(-170, -150))
	jump.pressed.connect(func(): hop.emit())
	var snap := _make_button("Photo", Vector2(-170, -290))
	snap.pressed.connect(func(): photo.emit())


func _make_button(label: String, offset: Vector2) -> Button:
	var b := Button.new()
	b.text = label
	b.anchor_left = 1.0; b.anchor_right = 1.0; b.anchor_top = 1.0; b.anchor_bottom = 1.0
	b.offset_left = offset.x; b.offset_top = offset.y
	b.offset_right = offset.x + 140; b.offset_bottom = offset.y + 110
	b.add_theme_font_size_override("font_size", 30)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.1, 0.07, 0.05, 0.45)
	sb.set_corner_radius_all(55)
	b.add_theme_stylebox_override("normal", sb)
	var sp := sb.duplicate() as StyleBoxFlat
	sp.bg_color = Color(0.89, 0.52, 0.23, 0.7)
	b.add_theme_stylebox_override("pressed", sp)
	b.add_theme_stylebox_override("hover", sb)
	b.focus_mode = Control.FOCUS_NONE
	add_child(b)
	_buttons.append(b)
	return b


func _over_button(p: Vector2) -> bool:
	for b in _buttons:
		if b.get_global_rect().grow(12).has_point(p):
			return true
	return false


func _input(event: InputEvent) -> void:
	if event is InputEventScreenTouch:
		var t := event as InputEventScreenTouch
		if t.pressed:
			if _over_button(t.position):
				return
			if t.position.x < size.x * 0.45 and _stick_id == -1:
				_stick_id = t.index
				_stick_origin = t.position
			elif _cam_id == -1:
				_cam_id = t.index
		else:
			if t.index == _stick_id:
				_stick_id = -1
				move = Vector2.ZERO
			if t.index == _cam_id:
				_cam_id = -1
		queue_redraw()
	elif event is InputEventScreenDrag:
		var d := event as InputEventScreenDrag
		if d.index == _stick_id:
			move = ((d.position - _stick_origin) / RADIUS).limit_length(1.0)
			queue_redraw()
		elif d.index == _cam_id:
			cam_drag -= d.relative.x * 0.008


func _draw() -> void:
	if _stick_id != -1:
		draw_circle(_stick_origin, RADIUS, Color(1, 1, 1, 0.14))
		draw_circle(_stick_origin + move * RADIUS, 38, Color(1, 1, 1, 0.5))
	else:
		# idle hint where the thumb usually goes
		var hint := Vector2(150, size.y - 170)
		draw_arc(hint, RADIUS, 0, TAU, 48, Color(1, 1, 1, 0.22), 3.0)
		draw_circle(hint, 30, Color(1, 1, 1, 0.18))
