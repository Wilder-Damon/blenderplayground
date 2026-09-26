extends SceneTree
# godot --headless --path . --script tools/inspect_anim.gd  -> prints animations and a few track paths per model

func _init() -> void:
	for f in ["res://assets/janie.glb", "res://assets/cooper.glb"]:
		var scene: Node = load(f).instantiate()
		for ap in scene.find_children("*", "AnimationPlayer", true, false):
			var p := ap as AnimationPlayer
			for n in p.get_animation_list():
				var a := p.get_animation(n)
				var paths := []
				for t in min(a.get_track_count(), 4):
					paths.append(str(a.track_get_path(t)))
				print("[ANIM] %s: '%s' len=%.2f tracks=%d %s" % [f, n, a.length, a.get_track_count(), paths])
		for sk in scene.find_children("*", "Skeleton3D", true, false):
			var s := sk as Skeleton3D
			print("[SKEL] %s: %s bones, first: %s" % [f, s.get_bone_count(), s.get_bone_name(0)])
		scene.free()
	quit()
