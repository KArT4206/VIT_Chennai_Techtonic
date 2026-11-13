"""Portrait lighting rig shared by GNM and MakeHuman renders (identical conditions).

Large soft key (0.9 m square softbox, 1.1 m from the face, 40 deg to camera-left of the subject's
right, 25 deg up), weaker broad fill (key:fill ~ 3:1), a rim from behind, and a dim neutral world.
No per-model tricks (no light linking): catchlights are the softbox's real reflection.
"""

import math

import bpy
from mathutils import Vector

KEY_W, FILL_W, RIM_W, WORLD = 55.0, 14.0, 22.0, 0.35


def build(scene, mid, forward, up=Vector((0, 0, 1)), name="Portrait"):
    """mid: eye midpoint (world); forward: direction the face looks (world)."""
    for o in [o for o in bpy.data.objects if o.name.startswith(name)]:
        bpy.data.objects.remove(o)
    w = bpy.data.worlds.new(name + "World"); scene.world = w; w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.26, 0.27, 0.28, 1); bg.inputs["Strength"].default_value = WORLD
    f = forward.normalized(); r = f.cross(up).normalized()
    def light(tag, az, el, dist, size, energy, shape="SQUARE"):
        d = (f * math.cos(math.radians(az)) + r * math.sin(math.radians(az))) * math.cos(math.radians(el)) + up * math.sin(math.radians(el))
        ld = bpy.data.lights.new(name + tag, "AREA"); ld.shape = shape; ld.size = size; ld.energy = energy
        ob = bpy.data.objects.new(name + tag, ld); ob.location = mid + d * dist
        ob.rotation_euler = (mid - ob.location).to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(ob)
        return ob
    light("Key", -40, 25, 1.1, 0.9, KEY_W)
    light("Fill", 45, 5, 1.3, 1.2, FILL_W)
    light("Rim", 150, 35, 1.0, 0.5, RIM_W)
