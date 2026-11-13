"""Quick lookdev renders of gnm_lookdev.blend (Metal): face, eyes, 3/4, and 1:1 crops for inspection."""
import bpy, os, sys, time
from mathutils import Vector
out = sys.argv[sys.argv.index('--') + 1]; os.makedirs(out, exist_ok=True)
spp = int(sys.argv[sys.argv.index('--') + 2])
sc = bpy.context.scene; sc.cycles.samples = spp
p = bpy.context.preferences.addons['cycles'].preferences; p.compute_device_type = 'METAL'; p.get_devices()
for d in p.devices: d.use = d.type == 'METAL'
sc.cycles.device = 'GPU'
ob = bpy.data.objects['GNM_Head']; rig = bpy.data.objects['GNM_Rig']
mid = ob.matrix_world @ ((rig.data.bones['left_eye'].head_local + rig.data.bones['right_eye'].head_local) / 2)
fwd = (ob.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized(); up = Vector((0, 0, 1)); right = fwd.cross(up)
cam = bpy.data.objects['Cam']
def shot(name, pos, tgt, lens, res=1024):
    cam.location = pos; cam.rotation_euler = (tgt - pos).to_track_quat('-Z', 'Y').to_euler(); cam.data.lens = lens
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.filepath = os.path.join(out, name); t = time.time(); bpy.ops.render.render(write_still=True); print('RENDERED', name, round(time.time() - t, 1))
sc.frame_set(1)
shot('face.png', mid + fwd * 0.40, mid - up * 0.03, 60)
shot('eyes.png', mid + fwd * 0.30, mid, 105)
shot('three_quarter.png', mid + fwd * 0.33 - right * 0.24 + up * 0.02, mid - up * 0.03, 60)
shot('cheek_nose_2048.png', mid + fwd * 0.18 - right * 0.04 - up * 0.03, mid - up * 0.035 - right * 0.012, 85, 2048)
