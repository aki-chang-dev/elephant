from __future__ import annotations

import ctypes
import errno
import os
import sys


class AtomicRenameUnavailable(OSError):
    """The host cannot provide the required single-step rename primitive."""


_libc = ctypes.CDLL(None, use_errno=True)
_renameatx_np = getattr(_libc, "renameatx_np", None)
if _renameatx_np is not None:
    _renameatx_np.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    _renameatx_np.restype = ctypes.c_int
_renameat2 = getattr(_libc, "renameat2", None)
if _renameat2 is not None:
    _renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    _renameat2.restype = ctypes.c_int

_DARWIN_RENAME_SWAP = 0x00000002
_DARWIN_RENAME_EXCL = 0x00000004
_DARWIN_RENAME_NOFOLLOW_ANY = 0x00000010
_DARWIN_RENAME_RESOLVE_BENEATH = 0x00000020
_LINUX_RENAME_NOREPLACE = 0x00000001
_LINUX_RENAME_EXCHANGE = 0x00000002


def _raise_native_error(source: str, target: str) -> None:
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise FileExistsError(error_number, os.strerror(error_number), target)
    if error_number in {errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP}:
        raise AtomicRenameUnavailable(
            error_number,
            "filesystem lacks the required atomic rename primitive",
        )
    raise OSError(error_number, os.strerror(error_number), f"{source} -> {target}")


def _native_rename(parent_fd: int, source: str, target: str, *, exchange: bool) -> None:
    source_bytes = os.fsencode(source)
    target_bytes = os.fsencode(target)
    if b"/" in source_bytes or b"/" in target_bytes or not source_bytes or not target_bytes:
        raise ValueError("atomic container names must be direct children")
    ctypes.set_errno(0)
    if sys.platform == "darwin" and _renameatx_np is not None:
        mode = _DARWIN_RENAME_SWAP if exchange else _DARWIN_RENAME_EXCL
        flags = mode | _DARWIN_RENAME_NOFOLLOW_ANY | _DARWIN_RENAME_RESOLVE_BENEATH
        result = _renameatx_np(
            parent_fd,
            source_bytes,
            parent_fd,
            target_bytes,
            flags,
        )
    elif sys.platform.startswith("linux") and _renameat2 is not None:
        flags = _LINUX_RENAME_EXCHANGE if exchange else _LINUX_RENAME_NOREPLACE
        result = _renameat2(
            parent_fd,
            source_bytes,
            parent_fd,
            target_bytes,
            flags,
        )
    else:
        raise AtomicRenameUnavailable(
            errno.ENOTSUP,
            "host lacks macOS renameatx_np or Linux renameat2",
        )
    if result != 0:
        _raise_native_error(source, target)


def atomic_exchange(parent_fd: int, first: str, second: str) -> None:
    _native_rename(parent_fd, first, second, exchange=True)


def atomic_noreplace(parent_fd: int, source: str, target: str) -> None:
    _native_rename(parent_fd, source, target, exchange=False)
