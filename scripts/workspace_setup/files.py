from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import errno
import fcntl
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
from .container import (
    ABSENT_LOCAL_CONTAINER_FINGERPRINT,
    ContainerObservation,
    clone_directory,
    fingerprint_container_at,
    fingerprint_container_descriptor,
    fingerprint_local_container,
    observe_container_at,
)
from .atomic_switch import atomic_exchange, atomic_noreplace


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
    expected_container_fingerprint: str


@dataclass(frozen=True)
class LocalWriteOutcome:
    operation_id: str
    path: str
    states: tuple[str, ...]
    observed_fingerprint: str


@dataclass(frozen=True)
class LocalContainerOutcome:
    disposition: str
    prior_fingerprint: str
    desired_fingerprint: str
    observed_fingerprint: str
    owner_id: str
    retained_stage_name: str | None = None
    retained_stage_fingerprint: str = ""
    retained_stage_device: int | None = None
    retained_stage_inode: int | None = None
    retained_stage_path_attested: bool | None = None


@dataclass(frozen=True)
class LocalTransactionResult:
    outcomes: tuple[LocalWriteOutcome, ...]
    container: LocalContainerOutcome


class LocalTransactionError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        operation: SetupOperation | None,
        cause: BaseException,
        outcomes: tuple[LocalWriteOutcome, ...],
        container: LocalContainerOutcome,
    ) -> None:
        self.detail = message
        self.operation = operation
        self.cause = cause
        self.outcomes = outcomes
        self.container = container
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
    expected_container_fingerprint: str,
) -> tuple[LocalWrite, ...]:
    """Preflight every approved local operation without local mutation."""
    repository_root = _resolved_root(root)
    if not isinstance(operations, tuple) or not all(
        isinstance(operation, SetupOperation) for operation in operations
    ):
        raise TypeError("operations: expected SetupOperation tuple")
    if not all(operation.kind is OperationKind.WRITE_LOCAL for operation in operations):
        raise ValueError("operations: expected only write_local operations")
    if (
        not isinstance(expected_container_fingerprint, str)
        or len(expected_container_fingerprint) != 64
        or any(
            character not in "0123456789abcdef"
            for character in expected_container_fingerprint
        )
    ):
        raise ValueError("expected container fingerprint must be a lowercase SHA-256")
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
        observed_container_fingerprint = fingerprint_container_at(root_fd)
        if not hmac.compare_digest(
            observed_container_fingerprint, expected_container_fingerprint
        ):
            raise ValueError("approved local container fingerprint is stale")
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
                    expected_container_fingerprint=expected_container_fingerprint,
                )
            )
    finally:
        os.close(root_fd)
    return tuple(writes)


def _write_bytes(descriptor: int, body: bytes) -> None:
    offset = 0
    while offset < len(body):
        written = os.write(descriptor, body[offset:])
        if written <= 0:
            raise OSError("temporary local write made no progress")
        offset += written


def _new_stage_directory(root_fd: int, owner_id: str) -> tuple[str, int]:
    owner_tag = hashlib.sha256(owner_id.encode("utf-8")).hexdigest()[:16]
    for _ in range(32):
        name = f".agents.setup-stage-{owner_tag}-{secrets.token_hex(8)}"
        try:
            os.mkdir(name, 0o700, dir_fd=root_fd)
        except FileExistsError:
            continue
        os.fsync(root_fd)
        descriptor = os.open(name, _DIRECTORY_FLAGS, dir_fd=root_fd)
        return name, descriptor
    raise OSError("could not allocate local container stage")


@dataclass(frozen=True)
class _RetainedStage:
    name: str
    descriptor: int
    device: int
    inode: int


def _bind_stage_descriptor(name: str, descriptor: int) -> _RetainedStage:
    observed = os.fstat(descriptor)
    if not stat.S_ISDIR(observed.st_mode):
        raise ValueError("local recovery stage descriptor is not a directory")
    return _RetainedStage(name, descriptor, observed.st_dev, observed.st_ino)


def _stage_path_matches(
    root_fd: int,
    stage: _RetainedStage,
    *,
    name: str | None = None,
) -> bool:
    try:
        observed = os.stat(
            stage.name if name is None else name,
            dir_fd=root_fd,
            follow_symlinks=False,
        )
    except OSError:
        return False
    return (
        stat.S_ISDIR(observed.st_mode)
        and observed.st_dev == stage.device
        and observed.st_ino == stage.inode
    )


def _select_retained_stage(
    root_fd: int,
    preferred: _RetainedStage | None,
    candidates: tuple[_RetainedStage | None, ...],
) -> _RetainedStage | None:
    if preferred is None:
        return None
    for candidate in (preferred,) + candidates:
        if candidate is not None and _stage_path_matches(root_fd, candidate):
            return candidate
    return preferred


def _stage_write(stage_fd: int, write: LocalWrite) -> None:
    parts = _output_parts(write.path)
    if parts[0] != ".agents":
        raise ValueError("local write is outside the staged container")
    current = os.dup(stage_fd)
    try:
        for name in parts[1:-1]:
            try:
                child = _open_child_directory(current, name, write.path)
            except FileNotFoundError:
                os.mkdir(name, 0o755, dir_fd=current)
                os.fsync(current)
                child = _open_child_directory(current, name, write.path)
            os.close(current)
            current = child
        target = parts[-1]
        mode = 0o600
        try:
            observed = os.stat(target, dir_fd=current, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            if not stat.S_ISREG(observed.st_mode):
                raise ValueError(
                    f"local container has unsupported target {write.path}"
                )
            mode = stat.S_IMODE(observed.st_mode)
        descriptor = os.open(
            target,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
            mode,
            dir_fd=current,
        )
        try:
            _write_bytes(descriptor, write.body.encode("utf-8"))
            os.fchmod(descriptor, mode)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.fsync(current)
    finally:
        os.close(current)


def _local_outcomes_from_observation(
    writes: tuple[LocalWrite, ...],
    state: str,
    observation: ContainerObservation,
) -> tuple[LocalWriteOutcome, ...]:
    file_fingerprints = dict(observation.file_fingerprints)
    return tuple(
        LocalWriteOutcome(
            operation_id=write.operation.operation_id,
            path=write.path,
            states=(state,),
            observed_fingerprint=file_fingerprints.get(
                "/".join(_output_parts(write.path)[1:]),
                "",
            ),
        )
        for write in writes
    )


def _observe_active_container(root_fd: int) -> ContainerObservation:
    try:
        return observe_container_at(root_fd)
    except BaseException:
        return ContainerObservation("", ())


def _retained_stage_fingerprint(
    root_fd: int,
    retained_stage: _RetainedStage | None,
) -> str:
    del root_fd
    if retained_stage is None:
        return ""
    try:
        return fingerprint_container_descriptor(retained_stage.descriptor)
    except BaseException:
        return ""


def _container_outcome(
    disposition: str,
    prior: str,
    desired: str,
    observed: str,
    owner_id: str,
    retained_stage_name: str | None = None,
    retained_stage_fingerprint: str = "",
    retained_stage_device: int | None = None,
    retained_stage_inode: int | None = None,
    retained_stage_path_attested: bool | None = None,
) -> LocalContainerOutcome:
    return LocalContainerOutcome(
        disposition,
        prior,
        desired,
        observed,
        owner_id,
        retained_stage_name,
        retained_stage_fingerprint,
        retained_stage_device,
        retained_stage_inode,
        retained_stage_path_attested,
    )


def _final_transaction_evidence(
    root_fd: int,
    writes: tuple[LocalWrite, ...],
    state: str,
    disposition: str,
    prior: str,
    desired: str,
    owner_id: str,
    retained_stage: _RetainedStage | None,
    stage_candidates: tuple[_RetainedStage | None, ...] = (),
) -> tuple[tuple[LocalWriteOutcome, ...], LocalContainerOutcome]:
    retained_stage = _select_retained_stage(
        root_fd,
        retained_stage,
        stage_candidates,
    )
    # Bracket the active snapshot so a one-time interleaving in either tree is
    # reflected by the later observation rather than mixed into stale evidence.
    _retained_stage_fingerprint(root_fd, retained_stage)
    observation = _observe_active_container(root_fd)
    retained_fingerprint = _retained_stage_fingerprint(root_fd, retained_stage)
    retained_path_attested = (
        None
        if retained_stage is None
        else _stage_path_matches(root_fd, retained_stage)
    )
    if retained_path_attested is False:
        # The identity-loss event may itself race both trees. Discard every
        # earlier fingerprint and report only explicit post-detection snapshots:
        # the exact retained descriptor first, then active state once. There is
        # deliberately no later name-based attestation; this is observed
        # evidence, not a guarantee against mutations after return.
        retained_fingerprint = _retained_stage_fingerprint(root_fd, retained_stage)
        observation = _observe_active_container(root_fd)
    outcomes = _local_outcomes_from_observation(writes, state, observation)
    return outcomes, _container_outcome(
        disposition,
        prior,
        desired,
        observation.fingerprint,
        owner_id,
        (
            retained_stage.name
            if retained_stage is not None and retained_path_attested
            else None
        ),
        retained_fingerprint,
        retained_stage.device if retained_stage is not None else None,
        retained_stage.inode if retained_stage is not None else None,
        retained_path_attested,
    )


def _restate_transaction_evidence(
    outcomes: tuple[LocalWriteOutcome, ...],
    container: LocalContainerOutcome,
    state: str,
    disposition: str,
) -> tuple[tuple[LocalWriteOutcome, ...], LocalContainerOutcome]:
    return (
        tuple(
            LocalWriteOutcome(
                outcome.operation_id,
                outcome.path,
                (state,),
                outcome.observed_fingerprint,
            )
            for outcome in outcomes
        ),
        _container_outcome(
            disposition,
            container.prior_fingerprint,
            container.desired_fingerprint,
            container.observed_fingerprint,
            container.owner_id,
            container.retained_stage_name,
            container.retained_stage_fingerprint,
            container.retained_stage_device,
            container.retained_stage_inode,
            container.retained_stage_path_attested,
        ),
    )


def _require_recovery_path_attested(
    outcomes: tuple[LocalWriteOutcome, ...],
    container: LocalContainerOutcome,
    operation: SetupOperation,
) -> None:
    if container.retained_stage_path_attested is not False:
        return
    error = ValueError("local recovery stage path identity was lost")
    raise LocalTransactionError(
        str(error),
        operation=operation,
        cause=error,
        outcomes=outcomes,
        container=container,
    ) from error


def _rollback_container_exchange(
    root_fd: int,
    candidate_stage: _RetainedStage,
    displaced_stage: _RetainedStage,
    desired_fingerprint: str,
) -> tuple[str, _RetainedStage]:
    try:
        active = fingerprint_container_at(root_fd)
    except BaseException:
        active = ""
    if (
        not hmac.compare_digest(active, desired_fingerprint)
        or not _stage_path_matches(root_fd, displaced_stage)
    ):
        return "rollback_failed", displaced_stage
    try:
        atomic_exchange(root_fd, ".agents", displaced_stage.name)
        retained_stage = candidate_stage
        os.fsync(root_fd)
    except BaseException:
        return "rollback_failed", displaced_stage
    try:
        staged_active = fingerprint_container_descriptor(
            candidate_stage.descriptor
        )
    except BaseException:
        staged_active = ""
    if not hmac.compare_digest(staged_active, desired_fingerprint):
        if not _stage_path_matches(root_fd, candidate_stage):
            return "rollback_failed", retained_stage
        try:
            atomic_exchange(root_fd, ".agents", candidate_stage.name)
            retained_stage = displaced_stage
            os.fsync(root_fd)
        except BaseException:
            return "rollback_failed", retained_stage
        return "rollback_failed", retained_stage
    return "rolled_back", retained_stage


def apply_local_write(
    root: object,
    writes: tuple[LocalWrite, ...],
    *,
    owner_id: str | None = None,
) -> LocalTransactionResult:
    """Commit one complete staged ``.agents`` tree with one atomic switch."""
    if not isinstance(writes, tuple) or not all(
        isinstance(write, LocalWrite) for write in writes
    ):
        raise TypeError("writes: expected LocalWrite tuple")
    repository_root = _resolved_root(root)
    transaction_owner = (
        f"local-{secrets.token_hex(12)}" if owner_id is None else owner_id
    )
    if not isinstance(transaction_owner, str) or not transaction_owner.strip():
        raise ValueError("local transaction owner_id must be nonblank")
    transaction_owner = transaction_owner.strip()
    if not writes:
        observed = fingerprint_local_container(repository_root)
        return LocalTransactionResult(
            (),
            _container_outcome(
                "unchanged", observed, observed, observed, transaction_owner
            ),
        )
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
    expected_container_fingerprint = writes[0].expected_container_fingerprint
    if any(
        write.expected_container_fingerprint != expected_container_fingerprint
        for write in writes
    ):
        raise ValueError("local writes disagree on approved container authority")
    for write in writes:
        _validate_local_body(write.path, write.body)
        if not hmac.compare_digest(
            _document_fingerprint(write.body), write.body_fingerprint
        ):
            raise ValueError("local write body does not match planned document fingerprint")

    root_fd = _open_root(repository_root, expected_root)
    stage_name: str | None = None
    candidate_stage: _RetainedStage | None = None
    prior_stage: _RetainedStage | None = None
    retained_stage: _RetainedStage | None = None
    desired_container_fingerprint = ""
    switched = False
    failed_write: LocalWrite | None = None
    try:
        try:
            fcntl.flock(root_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            outcomes, container = _final_transaction_evidence(
                root_fd,
                writes,
                "not_applied",
                "not_applied",
                expected_container_fingerprint,
                "",
                transaction_owner,
                None,
            )
            raise LocalTransactionError(
                "repository setup lock is held by another owner",
                operation=writes[0].operation,
                cause=error,
                outcomes=outcomes,
                container=container,
            ) from error

        observed_prior = fingerprint_container_at(root_fd)
        if not hmac.compare_digest(
            observed_prior, expected_container_fingerprint
        ):
            raise ValueError("approved local container fingerprint is stale")

        stage_name, candidate_fd = _new_stage_directory(root_fd, transaction_owner)
        try:
            candidate_stage = _bind_stage_descriptor(stage_name, candidate_fd)
        except BaseException:
            os.close(candidate_fd)
            raise
        retained_stage = candidate_stage
        if observed_prior == ABSENT_LOCAL_CONTAINER_FINGERPRINT:
            os.fchmod(candidate_stage.descriptor, 0o755)
            os.fsync(candidate_stage.descriptor)
        else:
            source_fd = _open_child_directory(root_fd, ".agents", ".agents")
            try:
                prior_stage = _bind_stage_descriptor(stage_name, source_fd)
            except BaseException:
                os.close(source_fd)
                raise
            clone_directory(source_fd, candidate_stage.descriptor)
            if not hmac.compare_digest(
                fingerprint_container_descriptor(candidate_stage.descriptor),
                observed_prior,
            ):
                raise ValueError("staged local container is not an exact clone")

        for write in writes:
            failed_write = write
            _stage_write(candidate_stage.descriptor, write)
        os.fsync(candidate_stage.descriptor)
        desired_container_fingerprint = fingerprint_container_descriptor(
            candidate_stage.descriptor
        )

        current_prior = fingerprint_container_at(root_fd)
        if not hmac.compare_digest(current_prior, observed_prior):
            raise ValueError("approved local container changed before commit")
        if hmac.compare_digest(desired_container_fingerprint, observed_prior):
            outcomes, container = _final_transaction_evidence(
                root_fd,
                writes,
                "durable",
                "unchanged",
                observed_prior,
                desired_container_fingerprint,
                transaction_owner,
                retained_stage,
                (candidate_stage, prior_stage),
            )
            _require_recovery_path_attested(
                outcomes,
                container,
                failed_write.operation if failed_write else writes[0].operation,
            )
            if not hmac.compare_digest(
                container.observed_fingerprint,
                desired_container_fingerprint,
            ):
                outcomes, container = _restate_transaction_evidence(
                    outcomes,
                    container,
                    "not_applied",
                    "not_applied",
                )
                error = ValueError("active local container changed before completion")
                raise LocalTransactionError(
                    str(error),
                    operation=failed_write.operation if failed_write else writes[0].operation,
                    cause=error,
                    outcomes=outcomes,
                    container=container,
                ) from error
            return LocalTransactionResult(
                outcomes,
                container,
            )

        if observed_prior == ABSENT_LOCAL_CONTAINER_FINGERPRINT:
            atomic_noreplace(root_fd, stage_name, ".agents")
            retained_stage = None
            stage_name = None
        else:
            if prior_stage is None:
                raise ValueError("approved prior container descriptor is missing")
            descriptor_prior = fingerprint_container_descriptor(
                prior_stage.descriptor
            )
            if (
                not hmac.compare_digest(descriptor_prior, observed_prior)
                or not _stage_path_matches(root_fd, prior_stage, name=".agents")
            ):
                raise ValueError("approved local container changed before commit")
            atomic_exchange(root_fd, ".agents", stage_name)
            retained_stage = prior_stage
        switched = True
        os.fsync(root_fd)

        if observed_prior != ABSENT_LOCAL_CONTAINER_FINGERPRINT:
            try:
                displaced_prior = fingerprint_container_descriptor(
                    prior_stage.descriptor
                )
            except BaseException:
                displaced_prior = ""
            if not hmac.compare_digest(displaced_prior, observed_prior):
                disposition, retained_stage = _rollback_container_exchange(
                    root_fd,
                    candidate_stage,
                    prior_stage,
                    desired_container_fingerprint,
                )
                outcomes, container = _final_transaction_evidence(
                    root_fd,
                    writes,
                    disposition,
                    disposition,
                    observed_prior,
                    desired_container_fingerprint,
                    transaction_owner,
                    retained_stage,
                    (candidate_stage, prior_stage),
                )
                raise LocalTransactionError(
                    "atomically displaced container failed approved CAS",
                    operation=failed_write.operation if failed_write else writes[0].operation,
                    cause=ValueError("displaced prior container fingerprint mismatch"),
                    outcomes=outcomes,
                    container=container,
                )

        success_disposition = (
            "created"
            if observed_prior == ABSENT_LOCAL_CONTAINER_FINGERPRINT
            else "replaced"
        )
        outcomes, container = _final_transaction_evidence(
            root_fd,
            writes,
            "durable",
            success_disposition,
            observed_prior,
            desired_container_fingerprint,
            transaction_owner,
            retained_stage,
            (candidate_stage, prior_stage),
        )
        _require_recovery_path_attested(
            outcomes,
            container,
            failed_write.operation if failed_write else writes[0].operation,
        )
        if not hmac.compare_digest(
            container.observed_fingerprint,
            desired_container_fingerprint,
        ):
            outcomes, container = _restate_transaction_evidence(
                outcomes,
                container,
                "commit_failed",
                "commit_failed",
            )
            error = ValueError("active local container differs after atomic switch")
            raise LocalTransactionError(
                str(error),
                operation=failed_write.operation if failed_write else writes[0].operation,
                cause=error,
                outcomes=outcomes,
                container=container,
            ) from error
        return LocalTransactionResult(
            outcomes,
            container,
        )
    except LocalTransactionError:
        raise
    except BaseException as error:
        disposition = "commit_failed" if switched else "not_applied"
        outcomes, container = _final_transaction_evidence(
            root_fd,
            writes,
            disposition,
            disposition,
            expected_container_fingerprint,
            desired_container_fingerprint,
            transaction_owner,
            retained_stage,
            (candidate_stage, prior_stage),
        )
        raise LocalTransactionError(
            str(error) or type(error).__name__,
            operation=failed_write.operation if failed_write is not None else None,
            cause=error,
            outcomes=outcomes,
            container=container,
        ) from error
    finally:
        closed_descriptors: set[int] = set()
        for stage in (candidate_stage, prior_stage):
            if stage is None or stage.descriptor in closed_descriptors:
                continue
            os.close(stage.descriptor)
            closed_descriptors.add(stage.descriptor)
        os.close(root_fd)
