"""Build a :class:`Config` from defaults, environment variables, and CLI args.

Environment variables (all optional) override defaults:
  * ``RB3135_FPD_DIR``         -> Config.fpd_dir
  * ``RB3135_OUTPUT_DIR``      -> Config.output_dir
  * ``RB3135_TOPOLOGY_CSV``    -> Config.topology_csv ("none" disables override)
  * ``RB3135_DOWNSAMPLE``      -> Config.downsample (1/true/yes)
  * ``RB3135_NO_DENSITY``      -> include_density_zones = False
"""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

from .config import Config


def _as_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config(**overrides: object) -> Config:
    """Return a :class:`Config`, layering env vars then explicit keyword overrides.

    Args:
        **overrides: Explicit field overrides (highest precedence).

    Returns:
        A new immutable :class:`Config`.
    """
    cfg = Config()

    env_fpd = os.environ.get("RB3135_FPD_DIR")
    if env_fpd:
        cfg = replace(cfg, fpd_dir=Path(env_fpd))

    env_out = os.environ.get("RB3135_OUTPUT_DIR")
    if env_out:
        cfg = replace(cfg, output_dir=Path(env_out))

    env_csv = os.environ.get("RB3135_TOPOLOGY_CSV")
    if env_csv is not None:
        if env_csv.strip().lower() == "none":
            cfg = replace(cfg, topology_csv=None, use_topology_csv_override=False)
        else:
            cfg = replace(cfg, topology_csv=Path(env_csv))

    env_ds = _as_bool(os.environ.get("RB3135_DOWNSAMPLE"))
    if env_ds is not None:
        cfg = replace(cfg, downsample=env_ds)

    if _as_bool(os.environ.get("RB3135_NO_DENSITY")):
        cfg = replace(cfg, include_density_zones=False)

    if overrides:
        cfg = replace(cfg, **overrides)  # type: ignore[arg-type]

    return cfg
