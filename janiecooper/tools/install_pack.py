import bpy, sys, os
zip_path = sys.argv[sys.argv.index("--") + 1]
from bl_ext.user_default.mpfb.services.assetservice import AssetService
from bl_ext.user_default.mpfb.services.locationservice import LocationService
data_dir = LocationService.get_user_data()
print("[PACK] user data dir:", data_dir)
print("[PACK] check:", AssetService.check_asset_pack_zip(zip_path))
print("[PACK] result:", AssetService.fix_and_extract_asset_pack_zip(zip_path, data_dir))
for sub in sorted(os.listdir(data_dir)):
    p = os.path.join(data_dir, sub)
    if os.path.isdir(p):
        print("[PACK]", sub, len(os.listdir(p)))
