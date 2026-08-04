"""Strict host-side boundary for opaque Linear attachment responses."""

from __future__ import annotations

import base64
from typing import Mapping


class HostAttachmentContentReader:
    """Decode one host-attested MCP resource blob for the requested attachment."""

    def read(self, response: object, *, attachment_id: str) -> bytes:
        if not isinstance(attachment_id, str) or not attachment_id.strip():
            raise RuntimeError("attachment content could not be decoded")
        try:
            content = self._content(response)
            if len(content) != 1:
                raise ValueError
            block = content[0]
            if block.get("type") != "resource":
                raise ValueError
            resource = block.get("resource")
            if not isinstance(resource, Mapping):
                raise ValueError
            metadata = resource.get("_meta")
            if not isinstance(metadata, Mapping):
                raise ValueError
            if metadata.get("linear_attachment_id") != attachment_id:
                raise ValueError
            blob = resource.get("blob")
            if not isinstance(blob, str) or not blob:
                raise ValueError
            return base64.b64decode(blob, validate=True)
        except (TypeError, ValueError, UnicodeError):
            raise RuntimeError("attachment content could not be decoded") from None

    @staticmethod
    def _content(response: object) -> tuple[Mapping[str, object], ...]:
        if not isinstance(response, Mapping):
            raise ValueError
        content = response.get("content")
        if not isinstance(content, list) or not all(isinstance(item, Mapping) for item in content):
            raise ValueError
        return tuple(content)
