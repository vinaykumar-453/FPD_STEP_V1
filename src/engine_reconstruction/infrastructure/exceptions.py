"""Custom exception hierarchy for the reconstruction framework.

A single rooted hierarchy lets callers catch broad categories
(:class:`ReconstructionError`) or precise failures (e.g.
:class:`WatertightnessError`). Every stage raises a subclass so the pipeline
orchestrator can attribute failures to a stage and decide whether to hard-fail.
"""

from __future__ import annotations


class ReconstructionError(Exception):
    """Base class for all errors raised by the framework."""


# --- I/O and discovery -------------------------------------------------------
class DiscoveryError(ReconstructionError):
    """Raised when FPD file discovery fails (missing dir, no files, bad names)."""


class FpdParseError(ReconstructionError):
    """Raised when an FPD file cannot be parsed into a structured point grid."""


class UnsupportedFormatError(FpdParseError):
    """Raised when the FPD format cannot be detected or is not supported."""


# --- Grid --------------------------------------------------------------------
class GridValidationError(ReconstructionError):
    """Raised when a structured grid fails validation and must be rejected."""


# --- Topology ----------------------------------------------------------------
class TopologyError(ReconstructionError):
    """Raised when topology recovery fails (orientation, adjacency, graph)."""


class OrientationError(TopologyError):
    """Raised when a canonical grid orientation cannot be determined."""


# --- Geometry ----------------------------------------------------------------
class GeometryError(ReconstructionError):
    """Base for B-Rep geometry construction failures."""


class SurfaceFittingError(GeometryError):
    """Raised when a B-spline surface cannot be fitted to a grid."""


class FaceConstructionError(GeometryError):
    """Raised when a TopoDS_Face cannot be built or healed."""


class ShellAssemblyError(GeometryError):
    """Raised when faces cannot be sewn into a shell."""


# --- Validation --------------------------------------------------------------
class ValidationError(ReconstructionError):
    """Base for validation failures."""


class WatertightnessError(ValidationError):
    """Raised when the merged shell fails the hard manifold/watertight check.

    This is the framework's terminal failure mode: per project policy the
    pipeline hard-fails (no STEP) when an intended interface seam does not
    become a shared edge or an unexpected free edge remains.
    """


# --- Export ------------------------------------------------------------------
class ExportError(ReconstructionError):
    """Raised when STEP export fails."""


# --- Environment -------------------------------------------------------------
class OCCNotAvailableError(ReconstructionError):
    """Raised when an OpenCASCADE-dependent operation runs without pythonocc-core."""
