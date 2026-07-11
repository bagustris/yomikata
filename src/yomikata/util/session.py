"""Desktop session introspection helpers."""

from __future__ import annotations

import os
from collections.abc import Mapping


def is_wayland_session(environ: Mapping[str, str] | None = None) -> bool:
    """Return True if the current desktop session is Wayland.

    Args:
        environ: Environment mapping to inspect. Defaults to ``os.environ``;
            injectable so tests need not mutate the process environment.
    """
    env = os.environ if environ is None else environ
    return env.get("XDG_SESSION_TYPE", "").strip().lower() == "wayland"
