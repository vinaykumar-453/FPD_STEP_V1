#!/usr/bin/env python
"""Repo-root entry point so ``python engine_pipeline.py`` just works.

Adds ``src`` to the import path and delegates to the package pipeline. Prefer
running inside the ``rb3135`` conda environment (pythonocc-core is required):

    conda run -n rb3135 python engine_pipeline.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from engine_reconstruction.pipeline.engine_pipeline import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
