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
            block_type = block.get("type")
            if block_type == "text":
                return self._decode_unpadded_text(block.get("text"))
            if block_type != "resource":
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
        except Exception:
            raise RuntimeError("attachment content could not be decoded") from None

    @staticmethod
    def _content(response: object) -> tuple[Mapping[str, object], ...]:
        if not isinstance(response, Mapping):
            raise ValueError
        content = response.get("content")
        if not isinstance(content, list) or not all(isinstance(item, Mapping) for item in content):
            raise ValueError
        return tuple(content)

    @staticmethod
    def _decode_unpadded_text(value: object) -> bytes:
        if (
            not isinstance(value, str)
            or not value
            or "=" in value
            or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/" for character in value)
        ):
            raise ValueError
        decoded = base64.b64decode(value + "=" * (-len(value) % 4), validate=True)
        if base64.b64encode(decoded).decode("ascii").rstrip("=") != value:
            raise ValueError
        return decoded
