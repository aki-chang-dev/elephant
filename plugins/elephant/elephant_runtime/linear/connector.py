"""The minimal immutable-argument port to the connected Linear tools."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from .models import LinearTool


class LinearConnector(Protocol):
    def call(
        self,
        tool: LinearTool,
        arguments: tuple[tuple[str, object], ...],
    ) -> Mapping[str, object]: ...
