from __future__ import annotations

from collections.abc import Mapping
import fnmatch
import json
import os
from pathlib import Path
import stat

from .models import (
    Candidate,
    Confidence,
    DependencyEdge,
    Evidence,
    ExternalDiscovery,
    ExternalObject,
    RepositoryDiscovery,
    WorkspaceUnit,
)


_EXCLUDED_DIRECTORIES = {
    ".git",
    ".worktrees",
    "node_modules",
    "build",
    "coverage",
    "dist",
    "out",
    ".next",
    ".turbo",
}
_DEPLOYMENT_FILENAMES = {
    "Dockerfile",
    "Procfile",
    "app.yaml",
    "docker-compose.yml",
    "docker-compose.yaml",
    "fly.toml",
    "netlify.toml",
    "render.yaml",
    "render.yml",
    "vercel.json",
}
_DEPENDENCY_SECTIONS = (
    "dependencies",
    "devDependencies",
    "optionalDependencies",
    "peerDependencies",
)


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_allowed_directory(root: Path, path: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    return not path.is_symlink() and not any(part in _EXCLUDED_DIRECTORIES for part in relative.parts)


def _entry_identity(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        stat.S_IFMT(value.st_mode),
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _read_confined_text(
    root: Path,
    path: Path,
    *,
    root_fd: int | None = None,
) -> str:
    """Read one in-root regular file through an identity-attested no-follow chain."""
    relative = path.relative_to(root)
    if not relative.parts:
        raise ValueError("confined file path must not be empty")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_NOFOLLOW
    descriptors = [
        os.open(root, directory_flags)
        if root_fd is None
        else os.dup(root_fd)
    ]
    bindings: list[tuple[int, str, tuple[int, int, int, int, int, int]]] = []
    try:
        parent_fd = descriptors[0]
        for part in relative.parts[:-1]:
            before = os.stat(part, dir_fd=parent_fd, follow_symlinks=False)
            if not stat.S_ISDIR(before.st_mode):
                raise ValueError("workspace path component is not a directory")
            child_fd = os.open(part, directory_flags, dir_fd=parent_fd)
            opened = os.fstat(child_fd)
            if _entry_identity(before) != _entry_identity(opened):
                os.close(child_fd)
                raise ValueError("workspace path changed during discovery")
            bindings.append((parent_fd, part, _entry_identity(opened)))
            descriptors.append(child_fd)
            parent_fd = child_fd

        filename = relative.parts[-1]
        before = os.stat(filename, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("workspace manifest is not a regular file")
        file_fd = os.open(filename, file_flags, dir_fd=parent_fd)
        descriptors.append(file_fd)
        opened = os.fstat(file_fd)
        if _entry_identity(before) != _entry_identity(opened):
            raise ValueError("workspace manifest changed during discovery")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(file_fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        if _entry_identity(opened) != _entry_identity(os.fstat(file_fd)):
            raise ValueError("workspace manifest changed during discovery")
        current_file = os.stat(filename, dir_fd=parent_fd, follow_symlinks=False)
        if _entry_identity(opened) != _entry_identity(current_file):
            raise ValueError("workspace manifest changed during discovery")
        for bound_parent, name, identity in bindings:
            current = os.stat(name, dir_fd=bound_parent, follow_symlinks=False)
            if identity != _entry_identity(current):
                raise ValueError("workspace path changed during discovery")
        return b"".join(chunks).decode("utf-8")
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _read_json(
    path: Path,
    problems: list[str],
    *,
    confined_root: Path | None = None,
    confined_root_fd: int | None = None,
) -> object | None:
    try:
        text = (
            _read_confined_text(
                confined_root,
                path,
                root_fd=confined_root_fd,
            )
            if confined_root is not None
            else path.read_text(encoding="utf-8")
        )
        return json.loads(text)
    except json.JSONDecodeError as error:
        problems.append(f"{path}: invalid JSON ({error.msg})")
    except (OSError, UnicodeDecodeError, ValueError) as error:
        problems.append(
            f"{path}: cannot read manifest without symlink traversal; "
            f"workspace path changed or is unsupported ({error})"
        )
    return None


def _workspace_patterns(manifest: object, problems: list[str]) -> tuple[str, ...]:
    if not isinstance(manifest, Mapping):
        return ()
    workspaces = manifest.get("workspaces", ())
    if isinstance(workspaces, Mapping):
        workspaces = workspaces.get("packages", ())
    if workspaces == () or workspaces is None:
        return ()
    if not isinstance(workspaces, list) or not all(isinstance(item, str) for item in workspaces):
        problems.append("package.json: workspaces must be a list of string globs")
        return ()
    return tuple(workspaces)


def _glob_parts_match(
    path_parts: tuple[str, ...],
    pattern_parts: tuple[str, ...],
) -> bool:
    if not pattern_parts:
        return not path_parts
    head = pattern_parts[0]
    if head == "**":
        return _glob_parts_match(path_parts, pattern_parts[1:]) or (
            bool(path_parts)
            and _glob_parts_match(path_parts[1:], pattern_parts)
        )
    return bool(path_parts) and fnmatch.fnmatchcase(path_parts[0], head) and (
        _glob_parts_match(path_parts[1:], pattern_parts[1:])
    )


def _pattern_can_reach_prefix(
    prefix_parts: tuple[str, ...],
    pattern_parts: tuple[str, ...],
) -> bool:
    if not prefix_parts:
        return True
    if not pattern_parts:
        return False
    head = pattern_parts[0]
    if head == "**":
        return _pattern_can_reach_prefix(prefix_parts, pattern_parts[1:]) or (
            _pattern_can_reach_prefix(prefix_parts[1:], pattern_parts)
        )
    return fnmatch.fnmatchcase(prefix_parts[0], head) and (
        _pattern_can_reach_prefix(prefix_parts[1:], pattern_parts[1:])
    )


def _descriptor_inventory(
    root: Path,
    root_fd: int,
) -> tuple[tuple[Path, ...], tuple[Path, ...], tuple[Path, ...]]:
    directories: list[Path] = []
    symlinks: list[Path] = []
    files: list[Path] = []

    def walk(directory_fd: int, parts: tuple[str, ...]) -> None:
        try:
            names = tuple(sorted(os.listdir(directory_fd)))
        except OSError as error:
            raise ValueError("repository tree changed during discovery") from error
        for name in names:
            path = root.joinpath(*parts, name)
            try:
                before = os.stat(
                    name,
                    dir_fd=directory_fd,
                    follow_symlinks=False,
                )
            except OSError as error:
                raise ValueError("repository tree changed during discovery") from error
            if stat.S_ISLNK(before.st_mode):
                symlinks.append(path)
                continue
            if stat.S_ISDIR(before.st_mode):
                if name in _EXCLUDED_DIRECTORIES:
                    continue
                try:
                    child_fd = os.open(
                        name,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=directory_fd,
                    )
                except OSError as error:
                    raise ValueError(
                        "repository directory changed during discovery"
                    ) from error
                try:
                    opened = os.fstat(child_fd)
                    if (
                        before.st_dev,
                        before.st_ino,
                        stat.S_IFMT(before.st_mode),
                    ) != (
                        opened.st_dev,
                        opened.st_ino,
                        stat.S_IFMT(opened.st_mode),
                    ):
                        raise ValueError(
                            "repository directory changed during discovery"
                        )
                    directories.append(path)
                    walk(child_fd, parts + (name,))
                    current = os.stat(
                        name,
                        dir_fd=directory_fd,
                        follow_symlinks=False,
                    )
                    if (
                        current.st_dev,
                        current.st_ino,
                        stat.S_IFMT(current.st_mode),
                    ) != (
                        opened.st_dev,
                        opened.st_ino,
                        stat.S_IFMT(opened.st_mode),
                    ):
                        raise ValueError(
                            "repository directory changed during discovery"
                        )
                finally:
                    os.close(child_fd)
                continue
            if stat.S_ISREG(before.st_mode):
                files.append(path)

    walk(root_fd, ())
    key = lambda item: _relative(root, item)
    return (
        tuple(sorted(directories, key=key)),
        tuple(sorted(symlinks, key=key)),
        tuple(sorted(files, key=key)),
    )


def _directory_inventory(
    root: Path,
    root_fd: int | None = None,
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    descriptor = (
        os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        if root_fd is None
        else os.dup(root_fd)
    )
    try:
        directories, symlinks, _ = _descriptor_inventory(root, descriptor)
        return directories, symlinks
    finally:
        os.close(descriptor)


def _safe_workspace_matches(
    root: Path,
    pattern: str,
    problems: list[str],
    inventory: tuple[Path, ...],
    symlinks: tuple[Path, ...],
) -> tuple[Path, ...]:
    candidate_pattern = Path(pattern)
    if candidate_pattern.is_absolute():
        problems.append(f"package.json: invalid workspace pattern {pattern!r}: absolute paths are not allowed")
        return ()
    if ".." in candidate_pattern.parts:
        problems.append(f"package.json: invalid workspace pattern {pattern!r}: parent traversal is not allowed")
        return ()
    if any("**" in part and part != "**" for part in candidate_pattern.parts):
        problems.append(
            f"package.json: invalid workspace pattern {pattern!r}: "
            "recursive wildcard must occupy a complete path segment"
        )
        return ()
    pattern_parts = tuple(candidate_pattern.parts)
    for symlink in symlinks:
        relative_parts = tuple(symlink.relative_to(root).parts)
        if _pattern_can_reach_prefix(relative_parts, pattern_parts):
            problems.append(
                f"package.json: workspace pattern {pattern!r} traverses symlink "
                f"{_relative(root, symlink)}"
            )
    matches: list[Path] = []
    targets_manifest = bool(pattern_parts) and pattern_parts[-1] == "package.json"
    for directory in inventory:
        relative_parts = tuple(directory.relative_to(root).parts)
        candidate_parts = (
            relative_parts + ("package.json",)
            if targets_manifest
            else relative_parts
        )
        if _glob_parts_match(candidate_parts, pattern_parts):
            matches.append(directory)
    return tuple(matches)


def _walk_files(
    root: Path,
    root_fd: int | None = None,
) -> tuple[Path, ...]:
    descriptor = (
        os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        if root_fd is None
        else os.dup(root_fd)
    )
    try:
        _, _, files = _descriptor_inventory(root, descriptor)
        return files
    finally:
        os.close(descriptor)


def _instruction_paths(
    root: Path,
    root_fd: int | None = None,
) -> tuple[str, ...]:
    return tuple(
        _relative(root, path)
        for path in _walk_files(root, root_fd)
        if path.name in {"AGENTS.md", "CLAUDE.md"}
    )


def _instruction_scope(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else ""


def _applicable_instructions(
    unit_path: str,
    instructions: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            (
                instruction
                for instruction in instructions
                if not (scope := _instruction_scope(instruction))
                or unit_path == scope
                or unit_path.startswith(f"{scope}/")
            ),
            key=lambda instruction: (
                len(Path(_instruction_scope(instruction)).parts),
                instruction,
            ),
        )
    )


def _descendant_instructions(
    unit_path: str,
    instructions: tuple[str, ...],
) -> tuple[str, ...]:
    return tuple(
        instruction
        for instruction in instructions
        if _instruction_scope(instruction).startswith(f"{unit_path}/")
    )


def _repository_candidate(root: Path, manifest: object) -> Candidate:
    repository = manifest.get("repository") if isinstance(manifest, Mapping) else None
    explicit_id = repository.get("id") if isinstance(repository, Mapping) else None
    if isinstance(explicit_id, str) and explicit_id.strip():
        identifier = explicit_id.strip()
        return Candidate(
            key=identifier,
            display_name=identifier,
            evidence=(Evidence("package.json", "package.json#repository.id", identifier),),
            confidence=Confidence.HIGH,
        )
    slug = root.name.lower().replace(" ", "-")
    return Candidate(
        key=slug,
        display_name=root.name,
        evidence=(Evidence("filesystem", str(root), slug),),
        confidence=Confidence.LOW,
    )


def _repository_product_evidence(
    root: Path,
    files: tuple[Path, ...],
    problems: list[str],
    *,
    root_fd: int | None = None,
) -> tuple[Candidate, ...]:
    candidates: list[Candidate] = []
    for path in files:
        relative = _relative(root, path)
        parts = Path(relative).parts
        if (
            len(parts) != 3
            or parts[:2] != ("docs", "products")
            or path.suffix.lower() != ".md"
        ):
            continue
        key = path.stem.strip().lower().replace(" ", "-")
        if not key:
            continue
        try:
            body = _read_confined_text(root, path, root_fd=root_fd)
        except (OSError, UnicodeDecodeError, ValueError) as error:
            problems.append(
                f"{path}: cannot read product evidence without symlink traversal "
                f"({error})"
            )
            continue
        heading = next(
            (
                line[2:].strip()
                for line in body.splitlines()
                if line.startswith("# ") and line[2:].strip()
            ),
            path.stem.replace("-", " ").title(),
        )
        candidates.append(
            Candidate(
                key=key,
                display_name=heading,
                evidence=(Evidence("repository_document", relative, heading),),
                confidence=Confidence.MEDIUM,
            )
        )
    return tuple(sorted(candidates, key=lambda value: value.key))


def _repository_document_evidence(
    root: Path,
    files: tuple[Path, ...],
    problems: list[str],
    *,
    root_fd: int | None = None,
) -> tuple[Evidence, ...]:
    evidence: list[Evidence] = []
    for path in files:
        relative = _relative(root, path)
        if not relative.startswith("docs/"):
            continue
        try:
            body = _read_confined_text(root, path, root_fd=root_fd)
        except (OSError, UnicodeDecodeError, ValueError) as error:
            problems.append(
                f"{path}: cannot attest repository document evidence ({error})"
            )
            continue
        display_name = next(
            (
                line[2:].strip()
                for line in body.splitlines()
                if line.startswith("# ") and line[2:].strip()
            ),
            path.stem.replace("-", " ").title(),
        )
        evidence.append(Evidence("repository_document", relative, display_name))
    return tuple(sorted(evidence, key=lambda value: (value.ref, value.value)))


def discover_repository(root: Path | str) -> RepositoryDiscovery:
    resolved_root = Path(root).resolve()
    root_fd = os.open(
        resolved_root,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
    )
    try:
        return _discover_repository_at(resolved_root, root_fd)
    finally:
        os.close(root_fd)


def _discover_repository_at(
    resolved_root: Path,
    root_fd: int,
) -> RepositoryDiscovery:
    problems: list[str] = []
    bound_root = os.fstat(root_fd)
    root_manifest_path = resolved_root / "package.json"
    try:
        root_manifest_stat = os.stat(
            "package.json",
            dir_fd=root_fd,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        root_manifest_stat = None
    if root_manifest_stat is not None and stat.S_ISLNK(root_manifest_stat.st_mode):
        problems.append(f"{root_manifest_path}: root package.json must not be a symlink")
        root_manifest = {}
    elif root_manifest_stat is not None and stat.S_ISREG(root_manifest_stat.st_mode):
        root_manifest = _read_json(
            root_manifest_path,
            problems,
            confined_root=resolved_root,
            confined_root_fd=root_fd,
        )
    else:
        problems.append(f"{root_manifest_path}: missing package.json")
        root_manifest = {}
    if root_manifest is None:
        root_manifest = {}
    if not isinstance(root_manifest, Mapping):
        problems.append(f"{root_manifest_path}: manifest must be a JSON object")
        root_manifest = {}

    package_directories: set[Path] = set()
    try:
        directory_inventory, directory_symlinks = _directory_inventory(
            resolved_root,
            root_fd,
        )
    except (OSError, ValueError) as error:
        problems.append(f"{resolved_root}: repository tree changed ({error})")
        directory_inventory, directory_symlinks = (), ()
    for pattern in _workspace_patterns(root_manifest, problems):
        package_directories.update(
            _safe_workspace_matches(
                resolved_root,
                pattern,
                problems,
                directory_inventory,
                directory_symlinks,
            )
        )
    package_directories.update(
        directory
        for directory in directory_inventory
        if len(directory.relative_to(resolved_root).parts) == 2
        and directory.relative_to(resolved_root).parts[0] in {"apps", "packages"}
    )

    unit_data: list[tuple[WorkspaceUnit, Mapping[str, object]]] = []
    try:
        files = _walk_files(resolved_root, root_fd)
    except (OSError, ValueError) as error:
        problems.append(f"{resolved_root}: repository files changed ({error})")
        files = ()
    instructions = tuple(
        _relative(resolved_root, path)
        for path in files
        if path.name in {"AGENTS.md", "CLAUDE.md"}
    )
    file_paths = set(files)
    for directory in sorted(package_directories, key=lambda item: _relative(resolved_root, item)):
        manifest_path = directory / "package.json"
        if manifest_path not in file_paths:
            continue
        manifest = _read_json(
            manifest_path,
            problems,
            confined_root=resolved_root,
            confined_root_fd=root_fd,
        )
        if not isinstance(manifest, Mapping):
            if manifest is not None:
                problems.append(f"{manifest_path}: manifest must be a JSON object")
            continue
        path = _relative(resolved_root, directory)
        package_name = manifest.get("name")
        if not isinstance(package_name, str) or not package_name:
            problems.append(f"{manifest_path}: package name must be a non-empty string")
            package_name = path
        evidence = []
        for section in _DEPENDENCY_SECTIONS:
            dependencies = manifest.get(section, {})
            if not isinstance(dependencies, Mapping):
                problems.append(f"{manifest_path}: {section} must be an object")
                continue
            for name, version in dependencies.items():
                if isinstance(name, str) and isinstance(version, str):
                    evidence.append(Evidence("package.json", f"{_relative(resolved_root, manifest_path)}#{section}.{name}", version))
        scoped_instructions = _applicable_instructions(path, instructions)
        descendant_instructions = _descendant_instructions(path, instructions)
        unit_data.append((
            WorkspaceUnit(
                path,
                package_name,
                _relative(resolved_root, manifest_path),
                scoped_instructions,
                tuple(sorted(evidence, key=lambda item: (item.ref, item.value))),
                descendant_instruction_paths=descendant_instructions,
            ),
            manifest,
        ))

    package_paths_by_name: dict[str, list[str]] = {}
    for unit, _ in unit_data:
        package_paths_by_name.setdefault(unit.package_name, []).append(unit.path)
    package_paths: dict[str, str] = {}
    for package_name, paths in sorted(package_paths_by_name.items()):
        if len(paths) == 1:
            package_paths[package_name] = paths[0]
        else:
            problems.append(f"duplicate workspace package name: {package_name}")
    edge_evidence: dict[tuple[str, str], list[Evidence]] = {}
    for unit, manifest in unit_data:
        for section in _DEPENDENCY_SECTIONS:
            dependencies = manifest.get(section, {})
            if not isinstance(dependencies, Mapping):
                continue
            for name, version in dependencies.items():
                target = package_paths.get(name) if isinstance(name, str) else None
                if target and target != unit.path and isinstance(version, str):
                    edge_evidence.setdefault((unit.path, target), []).append(
                        Evidence("package.json", f"{unit.manifest_path}#{section}.{name}", version)
                    )
    dependencies = tuple(
        DependencyEdge(source, target, tuple(sorted(evidence, key=lambda item: (item.ref, item.value))))
        for (source, target), evidence in sorted(edge_evidence.items())
    )

    product_document_evidence = _repository_document_evidence(
        resolved_root,
        files,
        problems,
        root_fd=root_fd,
    )
    product_documents = tuple(
        evidence.ref for evidence in product_document_evidence
    )
    deployment_evidence = tuple(
        _relative(resolved_root, path)
        for path in files
        if path.name in _DEPLOYMENT_FILENAMES
    )
    product_evidence = _repository_product_evidence(
        resolved_root,
        files,
        problems,
        root_fd=root_fd,
    )
    try:
        current_root = os.stat(resolved_root, follow_symlinks=False)
    except OSError:
        current_root = None
    if current_root is None or (
        current_root.st_dev,
        current_root.st_ino,
    ) != (
        bound_root.st_dev,
        bound_root.st_ino,
    ):
        problems.append(f"{resolved_root}: root path identity changed during discovery")
    return RepositoryDiscovery(
        root=str(resolved_root),
        repository_candidate=_repository_candidate(resolved_root, root_manifest),
        workspace_units=tuple(unit for unit, _ in unit_data),
        dependencies=dependencies,
        instruction_paths=instructions,
        product_document_paths=product_documents,
        deployment_evidence=deployment_evidence,
        problems=tuple(sorted(problems)),
        product_evidence=product_evidence,
        product_document_evidence=product_document_evidence,
    )


def normalize_external_discovery(records: object) -> ExternalDiscovery:
    if not isinstance(records, tuple):
        raise TypeError("external records: expected tuple")
    objects: list[ExternalObject] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise TypeError("external record: expected mapping")
        values: dict[str, str] = {}
        for field_name in ("provider", "kind", "key", "display_name", "external_id"):
            value = record.get(field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"external record: {field_name} must be a non-empty string")
            values[field_name] = value.strip()
        fingerprint = record.get("fingerprint", "")
        if not isinstance(fingerprint, str):
            raise ValueError("external record: fingerprint must be a string")
        values["fingerprint"] = fingerprint.strip()
        objects.append(ExternalObject(**values))
    return ExternalDiscovery(
        objects=tuple(sorted(objects, key=lambda item: (item.provider, item.kind, item.key, item.external_id, item.fingerprint)))
    )
