from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import errno
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
from typing import Any

from scripts.workspace_core import validate_profile, validate_workspace
from scripts.workspace_core.config import (
    EXTERNAL_BINDING_FIELDS,
    FORBIDDEN_STORY_KEYS,
    PROFILE_SCHEMA,
    PROVIDER_CHOICES,
    WORKSPACE_SCHEMA,
)

from .models import ConfirmedTopology, OperationKind, SetupOperation


WORKSPACE_PATH = ".agents/elephant/workspace.yaml"
PROFILE_DIRECTORY = ".agents/elephant/profiles"
_PROFILE_SECTIONS = (
    "context",
    "design_gate",
    "research",
    "execution",
    "verification",
    "finish",
    "language",
)
_PRODUCT_KEY = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


def _constrained_value(value: object, *, field: str = "document") -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"constrained YAML {field}: mapping keys must be strings")
            result[key] = _constrained_value(item, field=f"{field}.{key}")
        return result
    if isinstance(value, (list, tuple)):
        return [
            _constrained_value(item, field=f"{field}[{index}]")
            for index, item in enumerate(value)
        ]
    raise TypeError(
        f"constrained YAML {field}: unsupported value {type(value).__name__}"
    )


def render_yaml(document: object) -> str:
    """Render the deliberately constrained JSON-compatible YAML subset."""
    normalized = _constrained_value(document)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        separators=(",", ": "),
    ) + "\n"


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"constrained YAML: duplicate mapping key {key}")
        result[key] = value
    return result


def load_rendered_yaml(body: str) -> dict[str, object]:
    """Load only canonical output accepted by :func:`render_yaml`."""
    if not isinstance(body, str):
        raise TypeError("constrained YAML body must be a string")
    try:
        document = json.loads(body, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError("constrained YAML body is invalid") from error
    if not isinstance(document, dict):
        raise ValueError("constrained YAML document must be a mapping")
    normalized = _constrained_value(document)
    if render_yaml(normalized) != body:
        raise ValueError("constrained YAML body is not canonical")
    return normalized


def _require_mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) for key in value
    ):
        raise ValueError(f"{field}: expected string-keyed mapping")
    return value


def _validated_providers(value: object) -> dict[str, str]:
    providers = _require_mapping(value, "providers")
    if set(providers) != set(PROVIDER_CHOICES):
        raise ValueError("providers: expected all logical provider selections")
    normalized: dict[str, str] = {}
    for logical, choices in PROVIDER_CHOICES.items():
        provider = providers[logical]
        if not isinstance(provider, str) or provider not in choices:
            raise ValueError(f"providers.{logical}: unsupported provider")
        normalized[logical] = provider
    return normalized


def _verified_bindings(
    value: object,
    providers: Mapping[str, str],
) -> tuple[
    dict[str, dict[str, object]],
    dict[str, Mapping[str, object]],
    dict[str, Mapping[str, object]],
]:
    receipts = _require_mapping(value, "bindings")
    external = {provider for provider in providers.values() if provider != "git"}
    if set(receipts) != external:
        raise ValueError("bindings: exact verified binding receipts required")
    output: dict[str, dict[str, object]] = {}
    story_refs: dict[str, Mapping[str, object]] = {}
    knowledge_refs: dict[str, Mapping[str, object]] = {}
    for provider in sorted(external):
        receipt = _require_mapping(receipts.get(provider), f"bindings.{provider}")
        if receipt.get("verified") is not True:
            raise ValueError(f"bindings.{provider}: verified binding receipt required")
        values = _require_mapping(receipt.get("values"), f"bindings.{provider}.values")
        required_fields = EXTERNAL_BINDING_FIELDS.get(provider)
        if required_fields is None:
            raise ValueError(f"bindings.{provider}: unsupported external provider")
        if set(values) != set(required_fields):
            raise ValueError(f"bindings.{provider}: exact verified binding fields required")
        normalized_values: dict[str, object] = {}
        for field in required_fields:
            opaque_id = values[field]
            if not isinstance(opaque_id, str) or not opaque_id.strip():
                raise ValueError(f"bindings.{provider}.{field}: verified binding ID required")
            normalized_values[field] = opaque_id
        output[provider] = normalized_values
        if "story_refs" in receipt:
            story_refs[provider] = _require_mapping(
                receipt["story_refs"], f"bindings.{provider}.story_refs"
            )
        if "knowledge_refs" in receipt:
            knowledge_refs[provider] = _require_mapping(
                receipt["knowledge_refs"], f"bindings.{provider}.knowledge_refs"
            )
    return output, story_refs, knowledge_refs


def _product_reference(
    provider: str,
    product_key: str,
    references: Mapping[str, Mapping[str, object]],
    kind: str,
) -> str:
    if provider == "git":
        return f"git:{kind}:{product_key}"
    provider_refs = references.get(provider)
    value = provider_refs.get(product_key) if provider_refs is not None else None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"bindings.{provider}: verified {kind} reference required for {product_key}"
        )
    return value


def _profile_settings(value: object, field: str) -> dict[str, object]:
    settings = _require_mapping(value, field)
    if set(settings) != set(_PROFILE_SECTIONS):
        raise ValueError(f"{field}: all seven profile settings mappings are required")
    result: dict[str, object] = {}
    for section in _PROFILE_SECTIONS:
        result[section] = dict(_require_mapping(settings[section], f"{field}.{section}"))
    _reject_story_content(result, field)
    return result


def _reject_story_content(value: object, field: str) -> None:
    if isinstance(value, Mapping):
        forbidden = FORBIDDEN_STORY_KEYS & set(value)
        if forbidden:
            raise ValueError(f"{field}: story data key {sorted(forbidden)[0]} is forbidden")
        for key, item in value.items():
            _reject_story_content(item, f"{field}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_story_content(item, f"{field}[{index}]")


def _validated_product_key(key: object) -> str:
    if (
        not isinstance(key, str)
        or _PRODUCT_KEY.fullmatch(key) is None
        or key == "engineering"
    ):
        raise ValueError(f"product key {key!r} cannot safely form a profile basename")
    return key


def _validate_document(document: dict[str, object], kind: str) -> None:
    problems = validate_workspace(document) if kind == "workspace" else validate_profile(document)
    if problems:
        raise ValueError(f"generated {kind} document is invalid: {problems[0]}")


def _validate_topology_links(topology: ConfirmedTopology) -> None:
    product_keys = {product.key for product in topology.products}
    domain_keys = {domain.key for domain in topology.domains}
    product_links: set[tuple[str, str]] = set()
    domain_links: set[tuple[str, str]] = set()
    for product in topology.products:
        if len(product.domain_keys) != len(set(product.domain_keys)):
            raise ValueError(f"topology: duplicate domain link for product {product.key}")
        for domain_key in product.domain_keys:
            if domain_key not in domain_keys:
                raise ValueError(f"topology: unknown domain key {domain_key}")
            product_links.add((product.key, domain_key))
    for domain in topology.domains:
        if len(domain.product_keys) != len(set(domain.product_keys)):
            raise ValueError(f"topology: duplicate product link for domain {domain.key}")
        for product_key in domain.product_keys:
            if product_key not in product_keys:
                raise ValueError(f"topology: unknown product key {product_key}")
            domain_links.add((product_key, domain.key))
    if product_links != domain_links:
        raise ValueError("topology: product and domain links must be reciprocal")


def build_local_documents(
    topology: ConfirmedTopology,
    providers: Mapping[str, str],
    bindings: Mapping[str, object],
    product_profile_settings: Mapping[str, object],
    engineering_profile_settings: Mapping[str, object],
) -> dict[str, str]:
    """Build schema-valid, story-free v3 workspace and profile documents."""
    if not isinstance(topology, ConfirmedTopology):
        raise TypeError("topology: expected ConfirmedTopology")
    if not isinstance(topology.repository_id, str) or not topology.repository_id.strip():
        raise ValueError("topology: stable repository ID required")
    selected = _validated_providers(providers)
    binding_values, story_refs, knowledge_refs = _verified_bindings(bindings, selected)
    supplied_product_settings = _require_mapping(
        product_profile_settings, "product profile settings"
    )
    raw_product_keys = [product.key for product in topology.products]
    if len(raw_product_keys) != len(set(raw_product_keys)):
        raise ValueError("topology: duplicate product key")
    raw_domain_keys = [domain.key for domain in topology.domains]
    if len(raw_domain_keys) != len(set(raw_domain_keys)):
        raise ValueError("topology: duplicate domain key")
    _validate_topology_links(topology)
    product_keys = {_validated_product_key(product.key) for product in topology.products}
    if set(supplied_product_settings) != product_keys:
        raise ValueError("product profile settings: exact settings required for every product")

    products: dict[str, object] = {}
    profiles: dict[str, dict[str, object]] = {}
    for product in topology.products:
        key = _validated_product_key(product.key)
        products[key] = {
            "profile": f"{PROFILE_DIRECTORY}/{key}.yaml",
            "story_ref": _product_reference(
                selected["story_store"], key, story_refs, "story"
            ),
            "knowledge_ref": _product_reference(
                selected["product_knowledge_store"], key, knowledge_refs, "knowledge"
            ),
            "primary_domains": list(product.domain_keys),
        }
        profile = {
            "schema": PROFILE_SCHEMA,
            "kind": "product",
            "product": key,
            **_profile_settings(
                supplied_product_settings[key], f"product profile settings.{key}"
            ),
        }
        _validate_document(profile, "profile")
        profiles[f"{PROFILE_DIRECTORY}/{key}.yaml"] = profile

    domains = {
        domain.key: {
            "scopes": list(domain.scopes),
            "instruction_paths": list(domain.instruction_paths),
            "verification": list(domain.verification),
            "products": list(domain.product_keys),
        }
        for domain in topology.domains
    }
    engineering = {
        "schema": PROFILE_SCHEMA,
        "kind": "engineering",
        "product": None,
        "behavior_preservation_required": True,
        **_profile_settings(engineering_profile_settings, "engineering profile settings"),
    }
    _validate_document(engineering, "profile")
    workspace = {
        "schema": WORKSPACE_SCHEMA,
        "repository": {"id": topology.repository_id},
        "providers": selected,
        "bindings": binding_values,
        "products": products,
        "domains": domains,
        "engineering_profile": f"{PROFILE_DIRECTORY}/engineering.yaml",
    }
    _reject_story_content(workspace, "workspace")
    _validate_document(workspace, "workspace")

    documents = {WORKSPACE_PATH: render_yaml(workspace)}
    documents.update(
        (path, render_yaml(profile)) for path, profile in sorted(profiles.items())
    )
    documents[f"{PROFILE_DIRECTORY}/engineering.yaml"] = render_yaml(engineering)
    return dict(sorted(documents.items()))


@dataclass(frozen=True)
class LocalWrite:
    repository_root: str
    repository_device: int
    repository_inode: int
    operation: SetupOperation
    path: str
    body: str
    disposition: str
    expected_prior_fingerprint: str | None
    desired_fingerprint: str
    body_fingerprint: str


@dataclass(frozen=True)
class LocalWriteOutcome:
    operation_id: str
    path: str
    states: tuple[str, ...]
    observed_fingerprint: str


@dataclass(frozen=True)
class LocalTransactionResult:
    outcomes: tuple[LocalWriteOutcome, ...]


class LocalTransactionError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        operation: SetupOperation | None,
        cause: BaseException,
        outcomes: tuple[LocalWriteOutcome, ...],
    ) -> None:
        self.detail = message
        self.operation = operation
        self.cause = cause
        self.outcomes = outcomes
        super().__init__(message)


def _output_parts(path: object) -> tuple[str, ...]:
    if not isinstance(path, str) or "\\" in path:
        raise ValueError(f"setup output path {path!r} is not allowed")
    pure = PurePosixPath(path)
    parts = pure.parts
    allowed = path == WORKSPACE_PATH or (
        len(parts) == 4
        and parts[:3] == (".agents", "elephant", "profiles")
        and parts[3].endswith(".yaml")
        and parts[3] != ".yaml"
        and "/" not in parts[3]
    )
    if not allowed or str(pure) != path:
        raise ValueError(f"setup output path {path!r} is not allowed")
    return parts


def _resolved_root(root: object) -> Path:
    try:
        path = Path(root)
    except TypeError as error:
        raise ValueError("repository root must be a path") from error
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ValueError("repository root must exist") from error
    if not resolved.is_dir():
        raise ValueError("repository root must be a directory")
    return resolved


def _document_fingerprint(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _validate_local_body(path: str, body: object) -> str:
    if not isinstance(body, str):
        raise ValueError(f"setup output path {path}: body must be a string")
    document = load_rendered_yaml(body)
    problems = (
        validate_workspace(document)
        if path == WORKSPACE_PATH
        else validate_profile(document)
    )
    if problems:
        raise ValueError(f"setup output path {path}: invalid document: {problems[0]}")
    _reject_story_content(document, path)
    return body


_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_FILE_READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW
_FILE_CREATE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW


def _same_inode(first: os.stat_result, second: os.stat_result) -> bool:
    return (
        first.st_dev == second.st_dev
        and first.st_ino == second.st_ino
        and stat.S_IFMT(first.st_mode) == stat.S_IFMT(second.st_mode)
    )


def _open_root(root: Path, expected: tuple[int, int] | None = None) -> int:
    descriptor = os.open(str(root), _DIRECTORY_FLAGS)
    observed = os.fstat(descriptor)
    if not stat.S_ISDIR(observed.st_mode):
        os.close(descriptor)
        raise ValueError("repository containment requires a directory root")
    if expected is not None and (observed.st_dev, observed.st_ino) != expected:
        os.close(descriptor)
        raise ValueError("planned repository root changed before local transaction")
    return descriptor


def _open_child_directory(parent_fd: int, name: str, path: str) -> int:
    try:
        descriptor = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent_fd)
    except OSError as error:
        if error.errno in {errno.ELOOP, errno.ENOTDIR}:
            raise ValueError(
                f"repository containment rejected parent component {path}"
            ) from error
        raise
    observed = os.fstat(descriptor)
    if not stat.S_ISDIR(observed.st_mode):
        os.close(descriptor)
        raise ValueError(f"repository containment rejected parent component {path}")
    return descriptor


def _open_existing_parent(root_fd: int, path: str) -> int | None:
    current = os.dup(root_fd)
    try:
        for name in _output_parts(path)[:-1]:
            try:
                child = _open_child_directory(current, name, path)
            except FileNotFoundError:
                os.close(current)
                return None
            os.close(current)
            current = child
        return current
    except BaseException:
        try:
            os.close(current)
        except OSError:
            pass
        raise


def _read_all(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = os.read(descriptor, 65536)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _read_target(parent_fd: int | None, path: str) -> bytes | None:
    if parent_fd is None:
        return None
    name = _output_parts(path)[-1]
    try:
        before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"repository containment rejected non-file target {path}")
    try:
        descriptor = os.open(name, _FILE_READ_FLAGS, dir_fd=parent_fd)
    except OSError as error:
        raise ValueError(f"repository containment rejected target {path}") from error
    try:
        opened = os.fstat(descriptor)
        after = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if not _same_inode(before, opened) or not _same_inode(opened, after):
            raise ValueError(f"repository containment target changed during read {path}")
        return _read_all(descriptor)
    finally:
        os.close(descriptor)


def _thaw_document(value: object) -> object:
    if isinstance(value, tuple):
        if all(
            isinstance(item, tuple)
            and len(item) == 2
            and isinstance(item[0], str)
            for item in value
        ):
            return {key: _thaw_document(item) for key, item in value}
        return [_thaw_document(item) for item in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    raise ValueError(
        f"local document: unsupported approved value {type(value).__name__}"
    )


def _operation_body(operation: SetupOperation) -> str:
    payload = dict(operation.payload)
    if "document" not in payload:
        raise ValueError(f"local write {operation.operation_id} has no document payload")
    document = payload["document"]
    if isinstance(document, str):
        return _validate_local_body(operation.target_key, document)
    thawed = _thaw_document(document)
    return _validate_local_body(operation.target_key, render_yaml(thawed))


def _classify_write(
    operation: SetupOperation,
    body: str,
    current: bytes | None,
) -> tuple[str, str | None]:
    current_fingerprint = (
        hashlib.sha256(current).hexdigest() if current is not None else None
    )
    desired_fingerprint = _document_fingerprint(body)
    prior = operation.expected_prior_fingerprint
    if current is None:
        if prior is not None:
            raise ValueError(
                f"semantic overwrite prior fingerprint is stale for {operation.target_key}"
            )
        return "create", None
    if prior is not None and not hmac.compare_digest(prior, current_fingerprint or ""):
        raise ValueError(
            f"semantic overwrite of {operation.target_key} requires exact prior fingerprint"
        )
    if hmac.compare_digest(current_fingerprint or "", desired_fingerprint):
        return "unchanged", current_fingerprint
    if prior is None:
        raise ValueError(
            f"semantic overwrite of {operation.target_key} requires exact prior fingerprint"
        )
    return "replace", current_fingerprint


def plan_local_writes(
    root: object,
    operations: tuple[SetupOperation, ...],
) -> tuple[LocalWrite, ...]:
    """Preflight every approved local operation without local mutation."""
    repository_root = _resolved_root(root)
    if not isinstance(operations, tuple) or not all(
        isinstance(operation, SetupOperation) for operation in operations
    ):
        raise TypeError("operations: expected SetupOperation tuple")
    if not all(operation.kind is OperationKind.WRITE_LOCAL for operation in operations):
        raise ValueError("operations: expected only write_local operations")
    paths = [operation.target_key for operation in operations]
    if len(paths) != len(set(paths)):
        raise ValueError("operations: duplicate setup output path")
    ordered = tuple(
        sorted(operations, key=lambda item: (item.target_key == WORKSPACE_PATH, item.target_key))
    )
    root_fd = _open_root(repository_root)
    root_stat = os.fstat(root_fd)
    writes: list[LocalWrite] = []
    try:
        for operation in ordered:
            _output_parts(operation.target_key)
            body = _operation_body(operation)
            parent_fd = _open_existing_parent(root_fd, operation.target_key)
            try:
                current = _read_target(parent_fd, operation.target_key)
            finally:
                if parent_fd is not None:
                    os.close(parent_fd)
            disposition, prior = _classify_write(operation, body, current)
            writes.append(
                LocalWrite(
                    repository_root=str(repository_root),
                    repository_device=root_stat.st_dev,
                    repository_inode=root_stat.st_ino,
                    operation=operation,
                    path=operation.target_key,
                    body=body,
                    disposition=disposition,
                    expected_prior_fingerprint=prior,
                    desired_fingerprint=operation.desired_fingerprint,
                    body_fingerprint=_document_fingerprint(body),
                )
            )
    finally:
        os.close(root_fd)
    return tuple(writes)


@dataclass
class _PreparedWrite:
    write: LocalWrite
    parent_fd: int
    parent_parts: tuple[str, ...]
    parent_identity: tuple[int, int]
    prior_body: bytes | None
    temporary_name: str | None = None


def _ensure_parent(
    root_fd: int,
    path: str,
    created: list[tuple[int, str, tuple[int, int]]],
) -> int:
    current = os.dup(root_fd)
    try:
        for name in _output_parts(path)[:-1]:
            try:
                child = _open_child_directory(current, name, path)
            except FileNotFoundError:
                made_directory = False
                try:
                    os.mkdir(name, 0o755, dir_fd=current)
                    made_directory = True
                except FileExistsError:
                    pass
                child = _open_child_directory(current, name, path)
                if made_directory:
                    child_stat = os.fstat(child)
                    created.append(
                        (os.dup(current), name, (child_stat.st_dev, child_stat.st_ino))
                    )
            os.close(current)
            current = child
        return current
    except BaseException:
        try:
            os.close(current)
        except OSError:
            pass
        raise


def _revalidate_parent(root_fd: int, prepared: _PreparedWrite) -> None:
    current = os.dup(root_fd)
    try:
        for name in prepared.parent_parts:
            child = _open_child_directory(current, name, prepared.write.path)
            os.close(current)
            current = child
        observed = os.fstat(current)
        if (observed.st_dev, observed.st_ino) != prepared.parent_identity:
            raise ValueError(
                f"repository containment parent changed for {prepared.write.path}"
            )
    finally:
        try:
            os.close(current)
        except OSError:
            pass


def _write_bytes(descriptor: int, body: bytes) -> None:
    offset = 0
    while offset < len(body):
        written = os.write(descriptor, body[offset:])
        if written <= 0:
            raise OSError("temporary local write made no progress")
        offset += written


def _create_temporary(parent_fd: int, target_name: str, body: bytes, label: str) -> str:
    for _ in range(32):
        name = f".{target_name}.{label}-{secrets.token_hex(8)}.tmp"
        try:
            descriptor = os.open(
                name,
                _FILE_CREATE_FLAGS,
                0o600,
                dir_fd=parent_fd,
            )
        except FileExistsError:
            continue
        try:
            _write_bytes(descriptor, body)
            os.fsync(descriptor)
        except BaseException:
            os.close(descriptor)
            try:
                os.unlink(name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
            raise
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass
        return name
    raise OSError("could not allocate sibling local temporary file")


def _unlink_temporary(parent_fd: int, name: str | None) -> None:
    if name is None:
        return
    try:
        os.unlink(name, dir_fd=parent_fd)
    except FileNotFoundError:
        pass


def _recheck_prepared(prepared: _PreparedWrite) -> None:
    current = _read_target(prepared.parent_fd, prepared.write.path)
    observed = hashlib.sha256(current).hexdigest() if current is not None else None
    if prepared.write.disposition == "create":
        valid = observed is None
    else:
        expected = prepared.write.expected_prior_fingerprint
        valid = (
            observed is not None
            and expected is not None
            and hmac.compare_digest(observed, expected)
        )
    if not valid:
        raise ValueError(
            f"semantic overwrite guard changed before applying {prepared.write.path}"
        )


def _outcome(
    prepared: _PreparedWrite,
    states: tuple[str, ...],
) -> LocalWriteOutcome:
    try:
        current = _read_target(prepared.parent_fd, prepared.write.path)
        fingerprint = hashlib.sha256(current).hexdigest() if current is not None else ""
    except BaseException:
        fingerprint = ""
    return LocalWriteOutcome(
        operation_id=prepared.write.operation.operation_id,
        path=prepared.write.path,
        states=states,
        observed_fingerprint=fingerprint,
    )


def _cleanup_created_directories(
    created: list[tuple[int, str, tuple[int, int]]],
) -> None:
    for parent_fd, name, identity in reversed(created):
        try:
            observed = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if (
                stat.S_ISDIR(observed.st_mode)
                and (observed.st_dev, observed.st_ino) == identity
            ):
                os.rmdir(name, dir_fd=parent_fd)
        except (FileNotFoundError, OSError):
            pass
        finally:
            os.close(parent_fd)


def _rollback_transaction(
    prepared: tuple[_PreparedWrite, ...],
    applied: list[_PreparedWrite],
    states: dict[str, list[str]],
) -> tuple[LocalWriteOutcome, ...]:
    applied_paths = {item.write.path for item in applied}
    for item in reversed(applied):
        try:
            target_name = _output_parts(item.write.path)[-1]
            if item.prior_body is None:
                os.unlink(target_name, dir_fd=item.parent_fd)
            else:
                rollback_name = _create_temporary(
                    item.parent_fd, target_name, item.prior_body, "rollback"
                )
                try:
                    os.replace(
                        rollback_name,
                        target_name,
                        src_dir_fd=item.parent_fd,
                        dst_dir_fd=item.parent_fd,
                    )
                finally:
                    _unlink_temporary(item.parent_fd, rollback_name)
            os.fsync(item.parent_fd)
            states[item.write.path].append("rolled_back")
        except BaseException:
            states[item.write.path].append("rollback_failed")
    for item in prepared:
        if item.write.path not in applied_paths:
            if item.write.disposition == "unchanged":
                states[item.write.path].append("durable")
            else:
                states[item.write.path].append("rolled_back")
    return tuple(_outcome(item, tuple(states[item.write.path])) for item in prepared)


def apply_local_write(
    root: object,
    writes: tuple[LocalWrite, ...],
) -> LocalTransactionResult:
    """Apply the complete local document set as one confined transaction."""
    if not isinstance(writes, tuple) or not all(
        isinstance(write, LocalWrite) for write in writes
    ):
        raise TypeError("writes: expected LocalWrite tuple")
    if not writes:
        return LocalTransactionResult(())
    repository_root = _resolved_root(root)
    expected_root = (
        writes[0].repository_device,
        writes[0].repository_inode,
    )
    if any(
        write.repository_root != str(repository_root)
        or (write.repository_device, write.repository_inode) != expected_root
        for write in writes
    ):
        raise ValueError("local write does not belong to the planned repository root")
    for write in writes:
        _validate_local_body(write.path, write.body)
        if not hmac.compare_digest(
            _document_fingerprint(write.body), write.body_fingerprint
        ):
            raise ValueError("local write body does not match planned document fingerprint")

    root_fd = _open_root(repository_root, expected_root)
    prepared: list[_PreparedWrite] = []
    created: list[tuple[int, str, tuple[int, int]]] = []
    applied: list[_PreparedWrite] = []
    states = {write.path: [] for write in writes}
    failed_write: LocalWrite | None = None
    try:
        # Re-preflight the full set before creating a directory or temporary.
        prior_bodies: dict[str, bytes | None] = {}
        for write in writes:
            failed_write = write
            parent_fd = _open_existing_parent(root_fd, write.path)
            try:
                prior_bodies[write.path] = _read_target(parent_fd, write.path)
            finally:
                if parent_fd is not None:
                    os.close(parent_fd)
            disposition, prior = _classify_write(
                write.operation, write.body, prior_bodies[write.path]
            )
            if disposition != write.disposition or prior != write.expected_prior_fingerprint:
                raise ValueError(
                    f"semantic overwrite guard changed before applying {write.path}"
                )

        for write in writes:
            failed_write = write
            parent_fd = _ensure_parent(root_fd, write.path, created)
            parent_stat = os.fstat(parent_fd)
            prepared.append(
                _PreparedWrite(
                    write=write,
                    parent_fd=parent_fd,
                    parent_parts=_output_parts(write.path)[:-1],
                    parent_identity=(parent_stat.st_dev, parent_stat.st_ino),
                    prior_body=prior_bodies[write.path],
                )
            )

        for item in prepared:
            failed_write = item.write
            _revalidate_parent(root_fd, item)
            _recheck_prepared(item)
            if item.write.disposition != "unchanged":
                item.temporary_name = _create_temporary(
                    item.parent_fd,
                    _output_parts(item.write.path)[-1],
                    item.write.body.encode("utf-8"),
                    "stage",
                )

        for item in prepared:
            failed_write = item.write
            if item.write.disposition == "unchanged":
                continue
            _revalidate_parent(root_fd, item)
            _recheck_prepared(item)
            target_name = _output_parts(item.write.path)[-1]
            assert item.temporary_name is not None
            os.replace(
                item.temporary_name,
                target_name,
                src_dir_fd=item.parent_fd,
                dst_dir_fd=item.parent_fd,
            )
            item.temporary_name = None
            states[item.write.path].append("applied")
            applied.append(item)
            _revalidate_parent(root_fd, item)

        fsynced: set[tuple[int, int]] = set()
        for item in prepared:
            failed_write = item.write
            if item.parent_identity not in fsynced:
                os.fsync(item.parent_fd)
                fsynced.add(item.parent_identity)
        outcomes: list[LocalWriteOutcome] = []
        for item in prepared:
            states[item.write.path].append("durable")
            outcomes.append(_outcome(item, tuple(states[item.write.path])))
        return LocalTransactionResult(tuple(outcomes))
    except BaseException as error:
        for item in prepared:
            _unlink_temporary(item.parent_fd, item.temporary_name)
            item.temporary_name = None
        outcomes = _rollback_transaction(tuple(prepared), applied, states)
        raise LocalTransactionError(
            str(error) or type(error).__name__,
            operation=failed_write.operation if failed_write is not None else None,
            cause=error,
            outcomes=outcomes,
        ) from error
    finally:
        for item in prepared:
            _unlink_temporary(item.parent_fd, item.temporary_name)
            os.close(item.parent_fd)
        os.close(root_fd)
        if applied and all(states[item.write.path][-1:] == ["durable"] for item in applied):
            for parent_fd, _, _ in created:
                os.close(parent_fd)
        else:
            _cleanup_created_directories(created)
