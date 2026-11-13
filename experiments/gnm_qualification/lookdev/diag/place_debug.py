import bpy, sys, os
sys.argv = [sys.argv[0], '--', 'gnm', 'gnm_lookdev_strands.blend', '/tmp/x', '1']
src = open('compare_lookdev.py').read().split('def pose(')[0]
exec(compile(src, 'compare_head', 'exec'))
for n in ('GNM_Head', 'GNM_Rig', 'GNM_Hair'):
    o = bpy.data.objects[n]; print('DBG', n, 'mw_rot', tuple(round(x, 3) for x in o.matrix_world.to_euler()), 'loc', tuple(round(x, 3) for x in o.matrix_world.translation))
print('DBG mid', tuple(round(c, 4) for c in mid), 'gnm mid world', tuple(round(c, 4) for c in (G.rig.matrix_world @ G.mid)))
print('DBG camera', sc.camera.name, tuple(round(x, 3) for x in sc.camera.matrix_world.translation), tuple(round(x, 3) for x in sc.camera.matrix_world.to_euler()))
