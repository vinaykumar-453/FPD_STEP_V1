"""Centralised, injectable configuration.

A single immutable :class:`Config` object is threaded through every stage
(dependency injection); there is no global mutable configuration state. Defaults
target the RB3135 dataset but every path/tolerance is overridable via
:mod:`engine_reconstruction.infrastructure.settings`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Default location of the 88 FPD files on this workstation.
DEFAULT_FPD_DIR = Path("/Users/vinaykumar/Downloads/ICEM_CAD_working_directory_spoof/FPD")
# Optional CSV that can override/validate auto-derived classification & adjacency.
DEFAULT_TOPOLOGY_CSV = Path(
    "/Users/vinaykumar/Downloads/ICEM_CAD_working_directory_spoof/PY/rb3135_topology.csv"
)


@dataclass(frozen=True)
class Config:
    """Immutable configuration for one pipeline run."""

    # --- Paths ---------------------------------------------------------------
    fpd_dir: Path = DEFAULT_FPD_DIR
    output_dir: Path = Path("output")
    topology_csv: Path | None = DEFAULT_TOPOLOGY_CSV
    step_filename: str = "RB3135.step"

    # --- Behaviour switches --------------------------------------------------
    use_topology_csv_override: bool = True  # hybrid: auto-derive + optional CSV
    downsample: bool = False  # full-resolution fitting by default
    include_pylon: bool = True  # sew the pylon fairing into the engine assembly
    # The next two are OFF by default: the pylon cut/trim planes (~43 m) and the
    # CFD density cylinders are huge auxiliary surfaces that bury the engine in a
    # viewer. The default output is the clean watertight engine only.
    include_pylon_aux: bool = False  # pylon cut/trim faces as a separate node
    include_density_zones: bool = False  # CFD density zones as a separate node
    include_component_compound: bool = False  # avoid duplicate overlapping geometry
    strict_watertight: bool = False  # best-effort: always write the STEP, just report

    # --- Numerical tolerances (metres) --------------------------------------
    bspline_tol: float = 1e-4
    bspline_degree_min: int = 3
    bspline_degree_max: int = 8
    area_deviation_pass_pct: float = 0.25
    area_deviation_fail_pct: float = 1.0
    face_tol: float = 1e-6
    duplicate_point_tol: float = 1e-9
    seam_match_rms_tol: float = 5e-3  # boundary pair considered coincident
    free_edge_open_boundary_tol: float = 1e-2  # classify free edge vs known open bnd

    # Progressive sewing tolerance ladder (metres).
    sewing_tolerances: tuple[float, ...] = (
        1e-3,
        5e-3,
        1e-2,
        2.5e-2,
        5e-2,
        0.1,
        0.2,
        0.5,
        1.0,
    )

    # --- Downsampling -------------------------------------------------------
    max_points_per_dir: int = 400  # only used when downsample=True (engine)
    # Pylon surfaces are cosmetic and can be huge (the heatshield is ~2.8M pts);
    # always cap them so B-spline fitting stays tractable.
    pylon_fit_cap: int = 250

    # --- Misc ----------------------------------------------------------------
    expected_fpd_count: int = 88
    random_seed: int = 0

    def resolved_output_dir(self) -> Path:
        """Return the output directory as an absolute path (not created here)."""
        return self.output_dir.resolve()

    def step_path(self) -> Path:
        return self.resolved_output_dir() / self.step_filename

    def reports_dir(self) -> Path:
        return self.resolved_output_dir() / "reports"
