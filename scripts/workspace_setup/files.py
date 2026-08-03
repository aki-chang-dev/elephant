from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
from typing import Any

from scripts.workspace_core import validate_profile, validate_workspace
from scripts.workspace_core.config import (
    EXTERNAL_BINDING_FIELDS,
    FORBIDDEN_STORY_KEYS,
    PROFILE_SCHEMA,
    PROVIDER_CHOICES,
    WORKSPACE_SCHEMA,
)

from .models import ConfirmedTopology


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
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


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
    path: str
    body: str
    disposition: str
    expected_prior_fingerprint: str | None
    desired_fingerprint: str


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


def _inside_root(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _confined_target(root: Path, path: str) -> Path:
    parts = _output_parts(path)
    current = root
    for index, part in enumerate(parts):
        candidate = current / part
        if candidate.is_symlink():
            raise ValueError(f"repository containment rejected symlink component {path}")
        if candidate.exists():
            try:
                resolved = candidate.resolve(strict=True)
            except OSError as error:
                raise ValueError(f"repository containment could not resolve {path}") from error
            if not _inside_root(root, resolved):
                raise ValueError(f"repository containment rejected {path}")
            if index < len(parts) - 1 and not resolved.is_dir():
                raise ValueError(f"repository containment rejected non-directory parent {path}")
            current = resolved
        else:
            current = candidate
    if not _inside_root(root, current):
        raise ValueError(f"repository containment rejected {path}")
    return current


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


def plan_local_writes(
    root: object,
    documents: Mapping[str, str],
    *,
    expected_fingerprints: Mapping[str, str] | None = None,
) -> tuple[LocalWrite, ...]:
    """Classify confined local writes without mutating the repository."""
    repository_root = _resolved_root(root)
    if not isinstance(documents, Mapping):
        raise ValueError("documents: expected mapping")
    expected = {} if expected_fingerprints is None else dict(expected_fingerprints)
    unknown_fingerprints = set(expected) - set(documents)
    if unknown_fingerprints:
        raise ValueError(
            f"semantic overwrite fingerprint has no document: {sorted(unknown_fingerprints)[0]}"
        )

    writes: list[LocalWrite] = []
    for path in sorted(documents):
        target = _confined_target(repository_root, path)
        body = _validate_local_body(path, documents[path])
        desired_fingerprint = _document_fingerprint(body)
        if target.exists():
            if not target.is_file():
                raise ValueError(f"repository containment rejected non-file target {path}")
            current_body = target.read_text(encoding="utf-8")
            current_fingerprint = _document_fingerprint(current_body)
            if hmac.compare_digest(current_fingerprint, desired_fingerprint):
                disposition = "unchanged"
                prior = current_fingerprint
            else:
                supplied = expected.get(path)
                if (
                    not isinstance(supplied, str)
                    or _SHA256.fullmatch(supplied) is None
                    or not hmac.compare_digest(supplied, current_fingerprint)
                ):
                    raise ValueError(
                        f"semantic overwrite of {path} requires exact prior fingerprint"
                    )
                disposition = "replace"
                prior = current_fingerprint
        else:
            disposition = "create"
            prior = None
        writes.append(
            LocalWrite(
                repository_root=str(repository_root),
                path=path,
                body=body,
                disposition=disposition,
                expected_prior_fingerprint=prior,
                desired_fingerprint=desired_fingerprint,
            )
        )
    return tuple(writes)


def _ensure_confined_parent(root: Path, path: str) -> Path:
    parts = _output_parts(path)
    current = root
    for part in parts[:-1]:
        candidate = current / part
        if candidate.is_symlink():
            raise ValueError(f"repository containment rejected symlink component {path}")
        if candidate.exists():
            resolved = candidate.resolve(strict=True)
            if not _inside_root(root, resolved) or not resolved.is_dir():
                raise ValueError(f"repository containment rejected {path}")
            current = resolved
            continue
        try:
            candidate.mkdir()
        except FileExistsError:
            pass
        if candidate.is_symlink():
            raise ValueError(f"repository containment rejected symlink component {path}")
        resolved = candidate.resolve(strict=True)
        if not _inside_root(root, resolved) or not resolved.is_dir():
            raise ValueError(f"repository containment rejected {path}")
        current = resolved
    return current


def _observed_fingerprint(target: Path, path: str) -> str | None:
    if target.is_symlink():
        raise ValueError(f"repository containment rejected symlink target {path}")
    if not target.exists():
        return None
    if not target.is_file():
        raise ValueError(f"repository containment rejected non-file target {path}")
    return _document_fingerprint(target.read_text(encoding="utf-8"))


def _recheck_write(target: Path, write: LocalWrite) -> None:
    observed = _observed_fingerprint(target, write.path)
    if write.disposition == "create":
        valid = observed is None
    elif write.disposition in {"unchanged", "replace"}:
        expected = write.expected_prior_fingerprint
        valid = (
            observed is not None
            and expected is not None
            and hmac.compare_digest(observed, expected)
        )
    else:
        raise ValueError(f"local write disposition {write.disposition!r} is invalid")
    if not valid:
        raise ValueError(
            f"semantic overwrite guard changed before applying {write.path}"
        )


def apply_local_write(root: object, write: LocalWrite) -> None:
    """Apply one planned local write through a sibling fsynced temporary file."""
    if not isinstance(write, LocalWrite):
        raise TypeError("write: expected LocalWrite")
    repository_root = _resolved_root(root)
    if str(repository_root) != write.repository_root:
        raise ValueError("local write does not belong to the planned repository root")
    _validate_local_body(write.path, write.body)
    if not hmac.compare_digest(
        _document_fingerprint(write.body), write.desired_fingerprint
    ):
        raise ValueError("local write body does not match planned document fingerprint")
    target = _confined_target(repository_root, write.path)
    _recheck_write(target, write)
    if write.disposition == "unchanged":
        return

    parent = _ensure_confined_parent(repository_root, write.path)
    target = parent / PurePosixPath(write.path).name
    _recheck_write(target, write)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(write.body)
            handle.flush()
            os.fsync(handle.fileno())
        _recheck_write(target, write)
        os.replace(temporary, target)
        directory_descriptor = os.open(str(parent), os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        if temporary.exists():
            temporary.unlink()
