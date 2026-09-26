shader_type spatial;
// Classic beach ball: six coloured panels around the vertical axis, white caps (Cooper's orange/white/red ball).

varying vec3 local_pos;

void vertex() {
	local_pos = VERTEX;
}

void fragment() {
	vec3 p = normalize(local_pos);
	float a = atan(p.z, p.x) / (2.0 * PI) + 0.5;
	int panel = int(floor(a * 6.0));
	vec3 cols[6] = vec3[](
		vec3(0.95, 0.35, 0.05), vec3(0.95, 0.93, 0.88), vec3(0.85, 0.08, 0.06),
		vec3(0.97, 0.75, 0.10), vec3(0.95, 0.93, 0.88), vec3(0.95, 0.35, 0.05));
	vec3 c = cols[panel % 6];
	if (abs(p.y) > 0.9) {
		c = vec3(0.95, 0.93, 0.88);
	}
	ALBEDO = c;
	ROUGHNESS = 0.25;
	SPECULAR = 0.6;
}
