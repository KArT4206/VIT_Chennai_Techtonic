"""Export the neutral official GNM Head v3 to a lossless NumPy interchange file for Blender.

    PYTHONPATH=vendor/GNM env/bin/python export_gnm.py model/v3_0/gnm_head.npz build/gnm_head_neutral.npz

Exactly the arrays GNM provides, in GNM's order and dtype: template vertices (identity = 0,
expression = 0, no pose), quads, triangles, face-corner UDIM UVs, tiles, every vertex group,
skinning weights, joints and parents. No welding, reordering, remeshing or triangulation.
"""

import hashlib
import os
import sys

import numpy as np
from gnm.shape import gnm_numpy


def main(src, dst):
    g = gnm_numpy.GNM.from_custom_file(src)
    sha = hashlib.sha256(open(src, "rb").read()).hexdigest()
    names = [str(n) for n in g.vertex_group_names]
    masks = np.stack([np.asarray(g.vertex_group_mask(n)).astype(np.uint8) for n in names])
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    np.savez(dst,
             vertices=np.asarray(g.template_vertex_positions),
             quads=np.asarray(g.quads),
             triangles=np.asarray(g.triangles),
             quad_uvs_udim=np.asarray(g.quad_uvs_udim),
             quad_uvs=np.asarray(g.quad_uvs),
             quad_udim_tiles=np.asarray(g.quad_udim_tiles),
             group_names=np.array(names),
             group_masks=masks,
             skinning_weights=np.asarray(g.skinning_weights),       # (J, V)
             joint_names=np.array([str(n) for n in g.joint_names]),
             joint_parents=np.asarray(g.joint_parent_indices),
             joint_positions=np.asarray(g.template_joint_positions),
             source_sha256=np.array(sha), version=np.array(str(g.version)))
    print("exported", dst, "from", src, "sha256", sha)
    print("dtypes:", np.asarray(g.template_vertex_positions).dtype, np.asarray(g.quad_uvs_udim).dtype)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
