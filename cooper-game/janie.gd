extends Node3D
## Janie: strolls the park's real concrete loop path. When Cooper is bringing the ball back she stops,
## walks over to meet him, then throws it again and carries on along the path.

signal fetched

const SPEED := 0.95
const CATCH_RADIUS := 1.9
const CALL_RADIUS := 14.0         # ball this close + Cooper with it -> she comes to meet him
const MEET_SPEED := 1.1

var ball: RigidBody3D
var cooper: Node3D
var throw_targets: Array[Vector3] = []
var _points: Array[Vector3] = []
var _lengths: Array[float] = []
var _total := 0.0
var _dist := 0.0
var _pause := 0.0
var _anim: AnimationPlayer
var _walk := ""
var _model: Node3D
var _meeting := false


func setup(model: Node3D, path_points: Array[Vector3], start_fraction: float) -> void:
	_model = model
	model.rotation.y = PI            # the Janie model faces +Z; turn her to face -Z (forward)
	add_child(model)
	var players := model.find_children("*", "AnimationPlayer", true, false)
	if players.size() > 0:
		_anim = players[0]
		var names := _anim.get_animation_list()
		if names.size() > 0:
			_walk = names[0]
			_anim.get_animation(_walk).loop_mode = Animation.LOOP_LINEAR
			_anim.play(_walk)
	_points = path_points
	_lengths = [0.0]
	for i in range(1, _points.size()):
		_total += _points[i].distance_to(_points[i - 1])
		_lengths.append(_total)
	_dist = _total * start_fraction
	_place()


func _process(delta: float) -> void:
	var to_ball := ball.global_position - global_position if ball else Vector3.INF
	to_ball.y = 0.0
	var cooper_has_it := cooper != null and ball != null and cooper.global_position.distance_to(ball.global_position) < 1.5
	if _pause > 0.0:
		_pause -= delta
		if _anim: _anim.pause()
		if _pause <= 0.0:
			_resync_to_path()
	elif cooper_has_it and to_ball.length() < CALL_RADIUS:
		# come and meet Cooper
		global_position += to_ball.normalized() * MEET_SPEED * delta
		rotation.y = lerp_angle(rotation.y, atan2(-to_ball.x, -to_ball.z), 0.2)
		if _anim and _walk != "" and not _anim.is_playing():
			_anim.play(_walk)
		_meeting = true
	else:
		if _meeting:
			_resync_to_path()
		_dist = fmod(_dist + SPEED * delta, _total)
		if _anim and _walk != "" and not _anim.is_playing():
			_anim.play(_walk)
		_place()
	if ball and _pause <= 0.0 and ball.global_position.distance_to(global_position + Vector3(0, 0.3, 0)) < CATCH_RADIUS:
		_throw()


func _resync_to_path() -> void:
	# after wandering off to meet Cooper, carry on from the nearest point of the loop
	_meeting = false
	var best := 0
	var best_d := INF
	for i in _points.size():
		var d := _points[i].distance_squared_to(global_position)
		if d < best_d:
			best_d = d
			best = i
	_dist = _lengths[best]


func _place() -> void:
	var i := _lengths.bsearch(_dist) - 1
	i = clampi(i, 0, _points.size() - 2)
	var seg := _lengths[i + 1] - _lengths[i]
	var f := 0.0 if seg <= 0.0 else (_dist - _lengths[i]) / seg
	var p := _points[i].lerp(_points[i + 1], f)
	global_position = p
	var d := (_points[i + 1] - _points[i]).normalized()
	rotation.y = lerp_angle(rotation.y, atan2(-d.x, -d.z), 0.15)


func _throw() -> void:
	_pause = 1.2
	fetched.emit()
	var target: Vector3 = throw_targets.pick_random() if throw_targets.size() > 0 else global_position + Vector3(8, 0, 8)
	var start := global_position + Vector3(0, 1.3, 0)
	var flight := 1.3
	var v := (target - start) / flight
	v.y = 0.5 * ProjectSettings.get_setting("physics/3d/default_gravity") * flight + (target.y - start.y) / flight
	ball.global_position = start
	ball.linear_velocity = v
	ball.angular_velocity = Vector3(randf_range(-6, 6), randf_range(-6, 6), randf_range(-6, 6))
