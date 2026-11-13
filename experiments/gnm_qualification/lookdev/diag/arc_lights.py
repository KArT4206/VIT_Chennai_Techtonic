"""Render the GNM side-gaze eye close-up with each light alone, to find the corneal arc source."""
import bpy, os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(bpy.data.filepath), '..')))
out = sys.argv[sys.argv.index('--') + 1]
sc = bpy.context.scene; sc.cycles.samples = 64
for o in bpy.data.objects:
    if o.type in ('MESH', 'CURVES') and not o.name.startswith('GNM'): o.hide_render = True
G = bpy.data.objects['GNM_Head']; G.hide_render = False
lights = [o for o in bpy.data.objects if o.type == 'LIGHT']
print('LIGHTS', [(l.name, l.data.type, round(l.data.energy, 2), getattr(l.data, 'size', None)) for l in lights])
w = sc.world.node_tree.nodes['Background'].inputs['Strength']; w0 = w.default_value
sc.render.use_border = True; sc.render.use_crop_to_border = True
sc.render.border_min_x, sc.render.border_max_x, sc.render.border_min_y, sc.render.border_max_y = 0.27, 0.73, 0.40, 0.58
def go(name):
    sc.render.filepath = os.path.join(out, name); bpy.ops.render.render(write_still=True)
ROOT=os.path.abspath(os.path.join(os.path.dirname(bpy.data.filepath),'..','..','..'))
sys.path.insert(0, os.path.join(ROOT,'wrapper')); sys.path.insert(0, os.path.join(ROOT,'experiments','gnm_qualification'))
import eyes, gnm_engine
Gr = gnm_engine.GNMRig(os.path.join(ROOT,'experiments','gnm_qualification','build','gnm_keys.npz'))
Gr.set_keys()
eyes._calibrate()
t = Gr.rig.matrix_world.inverted() @ eyes.target_point(1, 0)
for side in ('left','right'): Gr.set_eye_quat(side, Gr.eye_rotation(side, t))
bpy.context.view_layer.update()
go('all.png')
for l in lights:
    for o in lights: o.hide_render = o is not l
    w.default_value = 0.0; go(f'only_{l.name}.png')
for o in lights: o.hide_render = True
w.default_value = w0; go('only_world.png')
