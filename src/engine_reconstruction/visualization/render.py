"""Headless rendering of a reconstructed shape/STEP to PNG snapshots.

OpenCASCADE's offscreen viewer needs a Cocoa/GUI context (unavailable in
headless runs), so this module tessellates the B-Rep with
``BRepMesh_IncrementalMesh`` and draws the triangles with matplotlib's Agg
backend — fully headless. Intended for quick visual verification, not
publication-quality rendering.

Requires ``matplotlib`` (a dev/visualization extra, not a core dependency).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..geometry import occ_utils
from ..infrastructure.logging import get_logger

logger = get_logger(__name__)


def _triangles(shape, deflection: float) -> np.ndarray:
    """Tessellate a shape and return an ``(n, 3, 3)`` array of triangle vertices."""
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
    from OCC.Core.TopLoc import TopLoc_Location
    from OCC.Core.TopoDS import topods

    BRepMesh_IncrementalMesh(shape, deflection, False, 0.8, True)
    tris: list = []
    for face in occ_utils.iter_faces(shape):
        face = topods.Face(face)
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation(face, loc)
        if tri is None:
            continue
        trsf = loc.Transformation()
        nodes = np.array(
            [
                (lambda p: (p.X(), p.Y(), p.Z()))(tri.Node(i).Transformed(trsf))
                for i in range(1, tri.NbNodes() + 1)
            ]
        )
        for i in range(1, tri.NbTriangles() + 1):
            a, b, c = tri.Triangle(i).Get()
            tris.append([nodes[a - 1], nodes[b - 1], nodes[c - 1]])
    return np.array(tris)


def render_shape(
    shape,
    out_prefix: Path,
    deflection: float = 0.06,
    max_triangles: int = 45000,
) -> list[Path]:
    """Render a shape to iso/side/front PNGs and return the written paths."""
    occ_utils.require_occ()
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    tris = _triangles(shape, deflection)
    if tris.size == 0:
        raise ValueError("no triangles produced; cannot render")
    if len(tris) > max_triangles:
        tris = tris[:: int(np.ceil(len(tris) / max_triangles))]

    pts = tris.reshape(-1, 3)
    ctr = (pts.min(axis=0) + pts.max(axis=0)) / 2
    rad = (pts.max(axis=0) - pts.min(axis=0)).max() / 2
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for elev, azim, tag, title in (
        (18, -60, "iso", "isometric"),
        (8, -90, "side", "side"),
        (2, 0, "front", "front (down axis)"),
    ):
        fig = plt.figure(figsize=(11, 7))
        ax = fig.add_subplot(111, projection="3d")
        coll = Poly3DCollection(tris, alpha=1.0)
        coll.set_facecolor((0.72, 0.74, 0.78))
        coll.set_edgecolor((0.35, 0.36, 0.40))
        coll.set_linewidth(0.05)
        ax.add_collection3d(coll)
        ax.set_xlim(ctr[0] - rad, ctr[0] + rad)
        ax.set_ylim(ctr[1] - rad, ctr[1] + rad)
        ax.set_zlim(ctr[2] - rad, ctr[2] + rad)
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(elev=elev, azim=azim)
        ax.set_axis_off()
        ax.set_title(f"RB3135 reconstruction — {title}")
        fig.tight_layout()
        path = out_prefix.with_name(f"{out_prefix.name}_{tag}.png")
        fig.savefig(path, dpi=130, bbox_inches="tight")
        plt.close(fig)
        written.append(path)
        logger.info("Wrote render %s", path)
    return written


def render_step(step_path: Path, out_prefix: Path, **kwargs) -> list[Path]:
    """Read a STEP file and render it to PNG snapshots."""
    occ_utils.require_occ()
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_Reader

    reader = STEPControl_Reader()
    if reader.ReadFile(str(step_path)) != IFSelect_RetDone:
        raise ValueError(f"failed to read STEP: {step_path}")
    reader.TransferRoots()
    return render_shape(reader.OneShape(), out_prefix, **kwargs)
