"""Optional interactive viewer (requires the OCC display extras).

Importing this module does not pull in any GUI dependency; the display is only
created when :func:`show` is called. Used for ad-hoc visual sanity checks; it is
never invoked by the automated pipeline.
"""

from __future__ import annotations

from ..infrastructure.logging import get_logger

logger = get_logger(__name__)


def show(*shapes) -> None:  # pragma: no cover - interactive only
    """Display one or more shapes in a simple OCC viewer.

    Args:
        *shapes: TopoDS shapes to display.
    """
    try:
        from OCC.Display.SimpleGui import init_display
    except Exception as exc:  # noqa: BLE001
        logger.error("Viewer unavailable (OCC display extras not installed): %s", exc)
        return
    display, start_display, _add_menu, _add_fn = init_display()
    for s in shapes:
        if s is not None:
            display.DisplayShape(s, update=True)
    display.FitAll()
    start_display()
