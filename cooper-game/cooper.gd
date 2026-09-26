extends CharacterBody3D
## Cooper: waddles relative to the camera, hops, does zoomies, and shoves the beach ball.

const WALK_SPEED := 3.2
const ZOOMIES_SPEED := 5.5
const HOP_VELOCITY := 3.2
const PUSH := 1.4

var camera_yaw := 0.0            # set by main.gd so input is camera-relative
var autopilot_target = null      # Vector3 or null; used by the --autopilot demo mode
var touch_vector := Vector2.ZERO # from the on-screen joystick (phones/tablets)
var touch_zoomies := false
var touch_hop := false
var _model: Node3D
var _anim: AnimationPlayer
var _walk := ""
var _gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity")


func setup(model: Node3D) -> void:
	_model = model
	add_child(model)
	# the coat colours are stored as vertex colours: make sure the imported materials use them
	for node in model.find_children("*", "MeshInstance3D", true, false):
		var mesh: Mesh = (node as MeshInstance3D).mesh
		for i in mesh.get_surface_count():
			var mat: Material = mesh.surface_get_material(i)
			if mat is StandardMaterial3D and mesh.surface_get_format(i) & Mesh.ARRAY_FORMAT_COLOR:
				(mat as StandardMaterial3D).vertex_color_use_as_albedo = true
	var players := model.find_children("*", "AnimationPlayer", true, false)
	if players.size() > 0:
		_anim = players[0]
		var names := _anim.get_animation_list()
		if names.size() > 0:
			# the glTF carries every action in the .blend; use this character's own walk cycle
			_walk = names[0]
			for n in names:
				if n.contains("Cooper"):
					_walk = n
			_anim.get_animation(_walk).loop_mode = Animation.LOOP_LINEAR
	var shape := CollisionShape3D.new()
	var capsule := CapsuleShape3D.new()
	capsule.radius = 0.24
	capsule.height = 0.62
	shape.shape = capsule
	shape.position.y = 0.31
	add_child(shape)


func _physics_process(delta: float) -> void:
	var input := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	if autopilot_target != null:
		var to: Vector3 = autopilot_target - global_position
		to.y = 0.0
		input = Vector2(to.x, to.z).rotated(camera_yaw) if to.length() > 0.2 else Vector2.ZERO
		input = input.limit_length(1.0)
	if touch_vector.length() > 0.1:
		input = touch_vector
	var dir := Vector3(input.x, 0.0, input.y).rotated(Vector3.UP, camera_yaw)
	var speed := ZOOMIES_SPEED if (Input.is_action_pressed("zoomies") or touch_zoomies) else WALK_SPEED

	velocity.x = dir.x * speed
	velocity.z = dir.z * speed
	if is_on_floor():
		if Input.is_action_just_pressed("hop") or touch_hop:
			velocity.y = HOP_VELOCITY
	else:
		velocity.y -= _gravity * delta
	touch_hop = false
	move_and_slide()

	# shove anything light we bump into (the beach ball)
	for i in get_slide_collision_count():
		var c := get_slide_collision(i)
		var body := c.get_collider()
		if body is RigidBody3D:
			var n := -c.get_normal()
			n.y = max(n.y, 0.15)
			body.apply_central_impulse(n.normalized() * PUSH * max(Vector2(velocity.x, velocity.z).length(), 1.0) * delta * 10.0)

	# face the direction of travel, waddle faster when running
	var flat := Vector2(velocity.x, velocity.z)
	if flat.length() > 0.1:
		var target_yaw := atan2(-velocity.x, -velocity.z)
		_model.rotation.y = lerp_angle(_model.rotation.y, target_yaw, 10.0 * delta)
		if _anim and _walk != "":
			if not _anim.is_playing():
				_anim.play(_walk)
			_anim.speed_scale = flat.length() / WALK_SPEED
	elif _anim and _anim.is_playing():
		_anim.pause()
