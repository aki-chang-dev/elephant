from __future__ import annotations

from collections.abc import Mapping
import json
import os
from pathlib import Path

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


def _read_json(path: Path, problems: list[str]) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        problems.append(f"{path}: invalid JSON ({error.msg})")
    except OSError as error:
        problems.append(f"{path}: cannot read manifest ({error})")
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


def _safe_workspace_matches(root: Path, pattern: str, problems: list[str]) -> tuple[Path, ...]:
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
    directories: set[Path] = set()
    try:
        for match in root.glob(pattern):
            directory = match.parent if match.name == "package.json" else match
            if directory.is_dir() and _is_allowed_directory(root, directory):
                directories.add(directory)
    except ValueError as error:
        problems.append(f"package.json: invalid workspace pattern {pattern!r}: {error}")
        return ()
    return tuple(sorted(directories, key=lambda item: _relative(root, item)))


def _walk_files(root: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    for directory, names, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        names[:] = [
            name
            for name in names
            if _is_allowed_directory(root, current / name)
        ]
        files.extend(current / filename for filename in filenames)
    return tuple(sorted(files, key=lambda item: _relative(root, item)))


def _instruction_paths(root: Path) -> tuple[str, ...]:
    return tuple(
        _relative(root, path)
        for path in _walk_files(root)
        if path.name in {"AGENTS.md", "CLAUDE.md"}
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


def discover_repository(root: Path | str) -> RepositoryDiscovery:
    resolved_root = Path(root).resolve()
    problems: list[str] = []
    root_manifest_path = resolved_root / "package.json"
    if root_manifest_path.is_symlink():
        problems.append(f"{root_manifest_path}: root package.json must not be a symlink")
        root_manifest = {}
    elif root_manifest_path.is_file():
        root_manifest = _read_json(root_manifest_path, problems)
    else:
        problems.append(f"{root_manifest_path}: missing package.json")
        root_manifest = {}
    if root_manifest is None:
        root_manifest = {}
    if not isinstance(root_manifest, Mapping):
        problems.append(f"{root_manifest_path}: manifest must be a JSON object")
        root_manifest = {}

    package_directories: set[Path] = set()
    for pattern in _workspace_patterns(root_manifest, problems):
        package_directories.update(_safe_workspace_matches(resolved_root, pattern, problems))
    for parent_name in ("apps", "packages"):
        parent = resolved_root / parent_name
        if parent.is_dir() and not parent.is_symlink():
            package_directories.update(
                child
                for child in parent.iterdir()
                if child.is_dir() and _is_allowed_directory(resolved_root, child)
            )

    unit_data: list[tuple[WorkspaceUnit, Mapping[str, object]]] = []
    instructions = _instruction_paths(resolved_root) if resolved_root.is_dir() else ()
    for directory in sorted(package_directories, key=lambda item: _relative(resolved_root, item)):
        manifest_path = directory / "package.json"
        if not manifest_path.is_file() or manifest_path.is_symlink():
            continue
        manifest = _read_json(manifest_path, problems)
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
        scoped_instructions = tuple(
            instruction for instruction in instructions if instruction == "AGENTS.md" or instruction == "CLAUDE.md" or instruction.startswith(f"{path}/")
        )
        unit_data.append((
            WorkspaceUnit(path, package_name, _relative(resolved_root, manifest_path), scoped_instructions, tuple(sorted(evidence, key=lambda item: (item.ref, item.value)))),
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

    files = _walk_files(resolved_root) if resolved_root.is_dir() else ()
    product_documents = tuple(
        _relative(resolved_root, path)
        for path in files
        if path.is_file() and _relative(resolved_root, path).startswith("docs/")
    )
    deployment_evidence = tuple(
        _relative(resolved_root, path)
        for path in files
        if path.is_file() and path.name in _DEPLOYMENT_FILENAMES
    )
    return RepositoryDiscovery(
        root=str(resolved_root),
        repository_candidate=_repository_candidate(resolved_root, root_manifest),
        workspace_units=tuple(unit for unit, _ in unit_data),
        dependencies=dependencies,
        instruction_paths=instructions,
        product_document_paths=product_documents,
        deployment_evidence=deployment_evidence,
        problems=tuple(sorted(problems)),
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
        objects.append(ExternalObject(**values))
    return ExternalDiscovery(
        objects=tuple(sorted(objects, key=lambda item: (item.provider, item.kind, item.key, item.external_id)))
    )
