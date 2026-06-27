"""Shared OpenCASCADE helpers: shape exploration, area, edge/face mapping.

Centralises the small amount of OCC boilerplate (topology traversal, edge->face
mapping, bounding boxes) used by the geometry, validation, and export layers, so
those modules stay focused on their own logic.

Importing this module requires pythonocc-core; a clear
:class:`OCCNotAvailableError` is raised otherwise.
"""

# pythonocc-core ships incomplete stubs for the indexed-map constructors and
# explorer return types used here; runtime behaviour is correct.
# mypy: disable-error-code="arg-type, call-arg"
from __future__ import annotations

import numpy as np

from ..infrastructure.exceptions import OCCNotAvailableError

try:
    from OCC.Core.BRep import BRep_Tool
    from OCC.Core.BRepGProp import brepgprop
    from OCC.Core.GProp import GProp_GProps
    from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_VERTEX
    from OCC.Core.TopExp import TopExp_Explorer, topexp
    from OCC.Core.TopoDS import TopoDS_Edge, TopoDS_Face, TopoDS_Shape
    from OCC.Core.TopTools import (
        TopTools_IndexedDataMapOfShapeListOfShape,
        TopTools_IndexedMapOfShape,
    )

    _OCC = True
except ImportError:  # pragma: no cover - environment-dependent
    _OCC = False


def require_occ() -> None:
    """Raise if pythonocc-core is not importable."""
    if not _OCC:
        raise OCCNotAvailableError(
            "pythonocc-core is required for this operation. "
            "Install it from conda-forge (see environment.yml)."
        )


def iter_faces(shape: TopoDS_Shape) -> list[TopoDS_Face]:
    """Return all faces of a shape."""
    require_occ()
    out: list[TopoDS_Face] = []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        out.append(exp.Current())
        exp.Next()
    return out


def count_subshapes(shape: TopoDS_Shape) -> dict[str, int]:
    """Return counts of unique faces, edges, and vertices."""
    require_occ()
    counts = {}
    for label, typ in (("faces", TopAbs_FACE), ("edges", TopAbs_EDGE), ("vertices", TopAbs_VERTEX)):
        m = TopTools_IndexedMapOfShape()
        topexp.MapShapes(shape, typ, m)
        counts[label] = m.Size()
    return counts


def edge_face_map(shape: TopoDS_Shape) -> TopTools_IndexedDataMapOfShapeListOfShape:
    """Return the edge -> incident-faces map for a shape."""
    require_occ()
    m = TopTools_IndexedDataMapOfShapeListOfShape()
    topexp.MapShapesAndAncestors(shape, TopAbs_EDGE, TopAbs_FACE, m)
    return m


def free_and_shared_edges(
    shape: TopoDS_Shape,
) -> tuple[list[TopoDS_Edge], list[TopoDS_Edge]]:
    """Partition edges into (free, shared) by incident-face count.

    A *free* edge is used by exactly one face; a *shared* edge by two or more.
    Edges with no faces (degenerate) are ignored.
    """
    require_occ()
    m = edge_face_map(shape)
    free: list[TopoDS_Edge] = []
    shared: list[TopoDS_Edge] = []
    for i in range(1, m.Size() + 1):
        edge = m.FindKey(i)
        n_faces = m.FindFromIndex(i).Size()
        if n_faces == 1:
            free.append(edge)
        elif n_faces >= 2:
            shared.append(edge)
    return free, shared


def surface_area(shape: TopoDS_Shape) -> float:
    """Return the total surface area of all faces in a shape."""
    require_occ()
    props = GProp_GProps()
    brepgprop.SurfaceProperties(shape, props)
    return float(props.Mass())


def edge_sample_points(edge: TopoDS_Edge, n: int = 12) -> np.ndarray:
    """Sample ``n`` points along an edge's 3D curve, returning an ``(n, 3)`` array."""
    require_occ()
    curve, first, last = BRep_Tool.Curve(edge)
    if curve is None:
        return np.empty((0, 3))
    ts = np.linspace(first, last, n)
    pts = np.empty((n, 3))
    for k, t in enumerate(ts):
        p = curve.Value(float(t))
        pts[k] = (p.X(), p.Y(), p.Z())
    return pts


def edge_endpoints(edge: TopoDS_Edge) -> tuple[np.ndarray, np.ndarray]:
    """Return the two endpoints of an edge as ``(3,)`` arrays."""
    require_occ()
    pts = edge_sample_points(edge, 2)
    if pts.shape[0] < 2:
        return np.zeros(3), np.zeros(3)
    return pts[0], pts[-1]


def _polyline_max_dist(a: np.ndarray, b: np.ndarray) -> float:
    """Symmetric max nearest-point distance between two point sets."""
    if a.size == 0 or b.size == 0:
        return float("inf")
    # a -> b
    d_ab = np.sqrt(((a[:, None, :] - b[None, :, :]) ** 2).sum(axis=2)).min(axis=1).max()
    d_ba = np.sqrt(((b[:, None, :] - a[None, :, :]) ** 2).sum(axis=2)).min(axis=1).max()
    return float(max(d_ab, d_ba))


def coincident_free_edge_pairs(
    shape: TopoDS_Shape,
    tol: float,
    n_samples: int = 10,
) -> list[tuple[int, int, float]]:
    """Find pairs of free edges that are geometrically coincident.

    A coincident free-edge pair means two faces meet there but the seam did not
    sew into a shared edge — i.e. an unsewn interface. Genuine open boundaries
    have *no* coincident partner and are therefore excluded.

    Returns:
        List of ``(i, j, distance)`` index pairs into the free-edge list whose
        symmetric max nearest distance is within ``tol``.
    """
    require_occ()
    free, _ = free_and_shared_edges(shape)
    if len(free) < 2:
        return []
    samples = [edge_sample_points(e, n_samples) for e in free]
    # Prefilter by edge midpoint distance to keep the O(n^2) loop cheap.
    mids = np.array([s.mean(axis=0) if s.size else np.full(3, np.inf) for s in samples])
    finite = np.isfinite(mids).all(axis=1)
    pairs: list[tuple[int, int, float]] = []
    n = len(free)
    for i in range(n):
        if not finite[i]:
            continue
        for j in range(i + 1, n):
            if not finite[j]:
                continue
            if np.linalg.norm(mids[i] - mids[j]) > max(tol * 50, 0.5):
                continue
            d = _polyline_max_dist(samples[i], samples[j])
            if d <= tol:
                pairs.append((i, j, d))
    return pairs
