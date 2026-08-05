"""Checkout forwarding for the plugin-shipped workspace-map runtime."""

from __future__ import annotations

from typing import Any

from scripts._elephant_runtime_forward import canonical_module


_CANONICAL = canonical_module("elephant_runtime.workspace_map")
__all__ = _CANONICAL.__all__


def __getattr__(name: str) -> Any:
    return getattr(_CANONICAL, name)


def __dir__() -> list[str]:
    return dir(_CANONICAL)
