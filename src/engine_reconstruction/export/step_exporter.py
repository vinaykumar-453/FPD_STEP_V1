"""Stage 13 — export the reconstruction to STEP AP214.

Writes a single ``RB3135.step`` whose root compound holds the three nodes:

* the watertight sewn engine shell (26 faces),
* a compound of the 13 per-component shells,
* a compound of the reconstructed CFD density shells.

The schema is AP214IS and units are metres (the FPD coordinate units).

Two backends are available:

* ``STEPControl_Writer`` (default) — robust across OCC builds. The named
  structure is conveyed by the nested-compound hierarchy.
* ``STEPCAFControl_Writer`` (XCAF, ``use_xcaf=True``) — embeds product *names*,
  but the XCAF document driver segfaults in some conda-forge OCC 7.9 builds, so
  it is opt-in. When enabled and unavailable it cannot be caught (a C++ crash),
  hence the conservative default.
"""

# The XCAF backend's pythonocc-core stubs (TDocStd_Document, TDataStd_Name.Set,
# AddShape) are imperfect; the plain STEPControl backend is fully typed.
# mypy: disable-error-code="arg-type, call-overload, misc"
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..geometry import occ_utils, solid_builder
from ..infrastructure.exceptions import ExportError
from ..infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ExportResult:
    """Outcome of a STEP export."""

    path: Path
    schema: str
    backend: str
    nodes: list[str] = field(default_factory=list)
    ok: bool = False


def _set_schema(schema: str) -> None:
    from OCC.Core.Interface import Interface_Static

    Interface_Static.SetCVal("write.step.schema", schema)
    Interface_Static.SetCVal("write.step.unit", "M")


def _export_plain(path: Path, nodes: list[tuple[str, object]], schema: str) -> ExportResult:
    """Write a root compound of the named nodes using STEPControl_Writer."""
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer

    root = solid_builder.make_compound([shape for _, shape in nodes])
    _set_schema(schema)
    writer = STEPControl_Writer()
    writer.Transfer(root, STEPControl_AsIs)
    status = writer.Write(str(path))
    if status != IFSelect_RetDone:
        raise ExportError(f"STEP write failed (status={status}) for {path}")
    return ExportResult(path, schema, "STEPControl", [n for n, _ in nodes], ok=True)


def _export_xcaf(path: Path, nodes: list[tuple[str, object]], schema: str) -> ExportResult:
    """Write a named XCAF product structure (opt-in; may be unavailable)."""
    from OCC.Core.BinXCAFDrivers import binxcafdrivers
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPCAFControl import STEPCAFControl_Writer
    from OCC.Core.STEPControl import STEPControl_AsIs
    from OCC.Core.TCollection import TCollection_ExtendedString
    from OCC.Core.TDataStd import TDataStd_Name
    from OCC.Core.TDocStd import TDocStd_Document
    from OCC.Core.XCAFApp import XCAFApp_Application
    from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool

    app = XCAFApp_Application.GetApplication()
    binxcafdrivers.DefineFormat(app)
    doc = TDocStd_Document(TCollection_ExtendedString("BinXCAF"))
    app.InitDocument(doc)
    shape_tool = XCAFDoc_DocumentTool.ShapeTool(doc.Main())
    for name, shape in nodes:
        TDataStd_Name.Set(shape_tool.AddShape(shape, False), TCollection_ExtendedString(name))

    _set_schema(schema)
    writer = STEPCAFControl_Writer()
    writer.Transfer(doc, STEPControl_AsIs)
    if writer.Write(str(path)) != IFSelect_RetDone:
        raise ExportError(f"XCAF STEP write failed for {path}")
    return ExportResult(path, schema, "STEPCAFControl", [n for n, _ in nodes], ok=True)


def export_step(
    path: Path,
    nodes: list[tuple[str, object]],
    schema: str = "AP214IS",
    use_xcaf: bool = False,
) -> ExportResult:
    """Export an ordered list of named geometry nodes to one STEP file.

    Args:
        path: Output ``.step`` path.
        nodes: Ordered ``(name, shape)`` pairs; ``None`` shapes are dropped. The
            first surviving node is the primary (e.g. the watertight engine
            assembly); the rest are auxiliary (pylon trim, density zones).
        schema: STEP schema identifier ("AP214IS" or "AP242DIS").
        use_xcaf: Use the XCAF backend to embed product names (opt-in).

    Returns:
        An :class:`ExportResult`.

    Raises:
        ExportError: If writing fails or no geometry is supplied.
    """
    occ_utils.require_occ()
    nodes = [(name, shape) for name, shape in nodes if shape is not None]
    if not nodes:
        raise ExportError("export_step requires at least one non-empty node")

    path.parent.mkdir(parents=True, exist_ok=True)
    backend = _export_xcaf if use_xcaf else _export_plain
    result = backend(path, nodes, schema)
    logger.info(
        "Exported STEP (%s, %s) -> %s [nodes: %s]",
        schema,
        result.backend,
        path,
        ", ".join(result.nodes),
    )
    return result
