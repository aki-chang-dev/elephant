from __future__ import annotations

import errno
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat


_TREE_DOMAIN = b"elephant-local-container/v1\0"
ABSENT_LOCAL_CONTAINER_FINGERPRINT = hashlib.sha256(
    _TREE_DOMAIN + b"absent"
).hexdigest()
_DIRECTORY_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_DIRECTORY", 0)
    | getattr(os, "O_NOFOLLOW", 0)
)
_FILE_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)


@dataclass(frozen=True)
class ContainerObservation:
    fingerprint: str
    file_fingerprints: tuple[tuple[str, str], ...]


def _frame(hasher: object, value: bytes) -> None:
    hasher.update(len(value).to_bytes(8, "big"))
    hasher.update(value)


def _identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        stat.S_IFMT(value.st_mode),
        stat.S_IMODE(value.st_mode),
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _stable_entry(
    parent_fd: int,
    name: str,
    before: os.stat_result,
    opened: os.stat_result,
) -> None:
    try:
        after = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError as error:
        raise ValueError("local container changed during fingerprint") from error
    if _identity(before) != _identity(opened) or _identity(opened) != _identity(after):
        raise ValueError("local container changed during fingerprint")


def _hash_directory(
    descriptor: int,
    hasher: object,
    prefix: bytes,
    file_fingerprints: dict[str, str],
) -> None:
    directory_before = os.fstat(descriptor)
    try:
        names = sorted(os.listdir(descriptor), key=os.fsencode)
    except OSError as error:
        raise ValueError("local container directory cannot be enumerated") from error
    for name in names:
        encoded_name = os.fsencode(name)
        path = encoded_name if not prefix else prefix + b"/" + encoded_name
        try:
            before = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        except FileNotFoundError as error:
            raise ValueError("local container changed during fingerprint") from error
        mode = stat.S_IMODE(before.st_mode).to_bytes(4, "big")
        if stat.S_ISDIR(before.st_mode):
            _frame(hasher, b"directory")
            _frame(hasher, path)
            _frame(hasher, mode)
            try:
                child_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=descriptor)
            except OSError as error:
                raise ValueError(
                    f"local container has unsupported entry {os.fsdecode(path)}"
                ) from error
            try:
                opened = os.fstat(child_fd)
                _hash_directory(child_fd, hasher, path, file_fingerprints)
                stable = os.fstat(child_fd)
                if _identity(opened) != _identity(stable):
                    raise ValueError("local container changed during fingerprint")
                _stable_entry(descriptor, name, before, stable)
            finally:
                os.close(child_fd)
        elif stat.S_ISREG(before.st_mode):
            if before.st_nlink != 1:
                raise ValueError(
                    f"local container hard link is unsupported: {os.fsdecode(path)}"
                )
            _frame(hasher, b"file")
            _frame(hasher, path)
            _frame(hasher, mode)
            try:
                child_fd = os.open(name, _FILE_FLAGS, dir_fd=descriptor)
            except OSError as error:
                raise ValueError(
                    f"local container has unsupported entry {os.fsdecode(path)}"
                ) from error
            try:
                opened = os.fstat(child_fd)
                content = hashlib.sha256()
                length = 0
                while True:
                    chunk = os.read(child_fd, 65536)
                    if not chunk:
                        break
                    content.update(chunk)
                    length += len(chunk)
                stable = os.fstat(child_fd)
                _stable_entry(descriptor, name, before, stable)
            finally:
                os.close(child_fd)
            _frame(hasher, length.to_bytes(8, "big"))
            _frame(hasher, content.digest())
            file_fingerprints[os.fsdecode(path)] = content.hexdigest()
        else:
            raise ValueError(
                f"local container has unsupported entry {os.fsdecode(path)}"
            )
    directory_after = os.fstat(descriptor)
    if _identity(directory_before) != _identity(directory_after):
        raise ValueError("local container changed during fingerprint")


def observe_container_at(
    root_fd: int,
    name: str = ".agents",
) -> ContainerObservation:
    try:
        before = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
    except FileNotFoundError:
        return ContainerObservation(ABSENT_LOCAL_CONTAINER_FINGERPRINT, ())
    if not stat.S_ISDIR(before.st_mode):
        raise ValueError("local container has unsupported .agents shape")
    try:
        descriptor = os.open(name, _DIRECTORY_FLAGS, dir_fd=root_fd)
    except OSError as error:
        if error.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise ValueError("local container symlink is unsupported") from error
        raise ValueError("local container cannot be opened") from error
    try:
        observation = observe_container_descriptor(descriptor)
        stable = os.fstat(descriptor)
        _stable_entry(root_fd, name, before, stable)
        return observation
    finally:
        os.close(descriptor)


def observe_container_descriptor(descriptor: int) -> ContainerObservation:
    """Observe the exact directory referenced by an already-owned descriptor."""
    opened = os.fstat(descriptor)
    if not stat.S_ISDIR(opened.st_mode):
        raise ValueError("local container descriptor is not a directory")
    hasher = hashlib.sha256()
    hasher.update(_TREE_DOMAIN)
    _frame(hasher, b"directory")
    _frame(hasher, stat.S_IMODE(opened.st_mode).to_bytes(4, "big"))
    file_fingerprints: dict[str, str] = {}
    _hash_directory(descriptor, hasher, b"", file_fingerprints)
    stable = os.fstat(descriptor)
    if _identity(opened) != _identity(stable):
        raise ValueError("local container changed during fingerprint")
    return ContainerObservation(
        hasher.hexdigest(),
        tuple(sorted(file_fingerprints.items())),
    )


def fingerprint_container_at(root_fd: int, name: str = ".agents") -> str:
    return observe_container_at(root_fd, name).fingerprint


def fingerprint_container_descriptor(descriptor: int) -> str:
    return observe_container_descriptor(descriptor).fingerprint


def fingerprint_local_container(root: object) -> str:
    try:
        resolved = Path(root).resolve(strict=True)
    except (OSError, TypeError) as error:
        raise ValueError("repository root must exist") from error
    if not resolved.is_dir():
        raise ValueError("repository root must be a directory")
    root_fd = os.open(str(resolved), _DIRECTORY_FLAGS)
    try:
        return fingerprint_container_at(root_fd)
    finally:
        os.close(root_fd)


def _copy_bytes(source_fd: int, destination_fd: int) -> None:
    while True:
        chunk = os.read(source_fd, 65536)
        if not chunk:
            return
        offset = 0
        while offset < len(chunk):
            written = os.write(destination_fd, chunk[offset:])
            if written <= 0:
                raise OSError("local container copy made no progress")
            offset += written


def clone_directory(source_fd: int, destination_fd: int) -> None:
    """Clone a validated regular-file/directory tree and durably stage entries."""
    source_before = os.fstat(source_fd)
    os.fchmod(destination_fd, stat.S_IMODE(source_before.st_mode))
    for name in sorted(os.listdir(source_fd), key=os.fsencode):
        before = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
        if stat.S_ISDIR(before.st_mode):
            os.mkdir(name, stat.S_IMODE(before.st_mode), dir_fd=destination_fd)
            os.fsync(destination_fd)
            child_source = os.open(name, _DIRECTORY_FLAGS, dir_fd=source_fd)
            child_destination = os.open(
                name, _DIRECTORY_FLAGS, dir_fd=destination_fd
            )
            try:
                opened = os.fstat(child_source)
                clone_directory(child_source, child_destination)
                stable = os.fstat(child_source)
                _stable_entry(source_fd, name, before, stable)
                if _identity(opened) != _identity(stable):
                    raise ValueError("local container changed during clone")
            finally:
                os.close(child_destination)
                os.close(child_source)
        elif stat.S_ISREG(before.st_mode):
            if before.st_nlink != 1:
                raise ValueError(
                    f"local container hard link is unsupported: {name}"
                )
            source_file = os.open(name, _FILE_FLAGS, dir_fd=source_fd)
            try:
                opened = os.fstat(source_file)
                destination_file = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    stat.S_IMODE(before.st_mode),
                    dir_fd=destination_fd,
                )
                try:
                    _copy_bytes(source_file, destination_file)
                    os.fchmod(destination_file, stat.S_IMODE(before.st_mode))
                    os.fsync(destination_file)
                finally:
                    os.close(destination_file)
                stable = os.fstat(source_file)
                _stable_entry(source_fd, name, before, stable)
                if _identity(opened) != _identity(stable):
                    raise ValueError("local container changed during clone")
            finally:
                os.close(source_file)
            os.fsync(destination_fd)
        else:
            raise ValueError(
                f"local container has unsupported entry {name}"
            )
    os.fsync(destination_fd)
    source_after = os.fstat(source_fd)
    if _identity(source_before) != _identity(source_after):
        raise ValueError("local container changed during clone")
