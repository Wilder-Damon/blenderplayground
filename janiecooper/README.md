# Janie & Cooper at Niguel Heights Park

A short Blender animation of Janie walking Cooper (our English bulldog) at golden hour in
Niguel Heights Park, Laguna Niguel. Everything is built from Python scripts run headless in
Blender 5.2, so the scene can be rebuilt and improved from code.

## Build order

All scripts are run from this folder with Blender in background mode:

```powershell
$blender = "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"

& $blender --background --factory-startup --python build_park.py -- stills   # -> park.blend (+ renders/park_*.png)
& $blender --background --factory-startup --python build_cooper.py          # -> cooper.blend (+ renders/cooper_*.png)
& $blender --background --python build_janie.py -- preview                   # -> janie.blend (needs MPFB, see below)
& $blender --background park.blend --python final_scene.py -- stills         # test frames -> renders/final_f*.png
& $blender --background park.blend --python final_scene.py -- render         # -> Janie_and_Cooper_Niguel_Heights_Park.mp4
```

| Script | What it does |
|---|---|
| `build_park.py` | Builds the park and surrounding streets/houses from OpenStreetMap data in `park/`, golden-hour sky and sun, EEVEE settings |
| `build_cooper.py` | Cooper: metaball body, coat colours from photos, face details, corduroy cap, simple walking rig |
| `build_janie.py` | Janie: MPFB (MakeHuman) character, hair colour, outfit, Mixamo-compatible rig |
| `final_scene.py` | Combines everything: walk path along the real footpath, procedural walk cycles, camera move, title card, render |
| `tools/` | Setup and debugging helpers (asset pack install, rig pose tests, material inspection) |
| `demos/` | The first glass-sphere test render and turntable |

## Requirements

- Blender 5.2 LTS; an NVIDIA RTX GPU is used automatically for Cycles (OptiX) where relevant.
- **MPFB 2** add-on (from extensions.blender.org) plus the **MakeHuman system assets** pack (CC0).
  Install the pack with `tools/install_pack.py`. The downloaded zips live in `addons/` locally and are not committed.

## Credits and licences

- Map data © OpenStreetMap contributors, available under the Open Database Licence (ODbL).
  `park/*.json` are OpenStreetMap extracts; the final video carries the attribution.
- Human base mesh and assets: MakeHuman / MPFB (CC0 assets; MPFB is GPL-3.0).

## Status / ideas

- Cooper: v5 (bulldog head with jowls/underbite, photo-matched markings, barrel chest, corduroy cap).
  Video v2 uses this Cooper; v1 kept for comparison. Still to try: folded rose ears, visible forehead wrinkles, fur.
- Janie: generic MakeHuman face; reads as her through hair, colouring and outfit at mid distance.
  Future: stylised (animated-film) version with her smile, or a proper hair-curve hairstyle.
- Park: grass detail, house windows/garage doors, Cooper's beach ball from the park photo.
