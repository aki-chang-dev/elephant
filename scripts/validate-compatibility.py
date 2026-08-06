#!/usr/bin/env python3
"""Validate Elephant's shared minimal Claude Code and Codex plugin contract."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys


PLUGIN = Path("plugins/elephant")
EXPECTED_RUNTIME_EXPORTS = frozenset(
    {
        "WORKSPACE_SCHEMA",
        "PlanningScope",
        "ProductRoute",
        "WorkspaceMapError",
        "planning_scope",
        "resolve_product",
        "validate_workspace_map",
    }
)
REQUIRED_SKILLS = (
    "author-product-spec",
    "author-technical-contract",
    "decompose-roadmap",
    "kickoff",
    "setup-workspace",
    "shape-story",
    "ship-story",
)
REQUIRED_ASSETS = (
    "plugins/elephant/.codex-plugin/plugin.json",
    "plugins/elephant/.claude-plugin/plugin.json",
    ".agents/plugins/marketplace.json",
    ".claude-plugin/marketplace.json",
    "plugins/elephant/elephant_runtime/__init__.py",
    "plugins/elephant/elephant_runtime/workspace_map.py",
    "plugins/elephant/elephant_runtime/installed_smoke.py",
    "plugins/elephant/references/information-routing.md",
    "plugins/elephant/references/delivery-assurance.md",
    "plugins/elephant/references/linear-planning.md",
    "plugins/elephant/references/notion-knowledge.md",
    "plugins/elephant/skills/shape-story/product-contract-template.md",
    "plugins/elephant/skills/author-technical-contract/technical-contract-template.md",
    "plugins/elephant/skills/shape-story/reviewers/product-ux-critic.md",
    "plugins/elephant/skills/shape-story/reviewers/copy-critic.md",
    "plugins/elephant/skills/author-technical-contract/reviewers/architecture.md",
    "plugins/elephant/skills/author-technical-contract/reviewers/domain-data.md",
    "plugins/elephant/skills/author-technical-contract/reviewers/security-operations.md",
    "plugins/elephant/skills/author-technical-contract/reviewers/product-conformance.md",
    "plugins/elephant/skills/author-technical-contract/reviewers/test.md",
    "plugins/elephant/skills/author-technical-contract/reviewers/technical-adjudicator.md",
    "plugins/elephant/skills/ship-story/reviewers/implementation-conformance.md",
)
FORBIDDEN_SUPERSEDED_ASSETS = (
    "plugins/elephant/elephant_runtime/linear/",
    "plugins/elephant/elephant_runtime/workspace_core/",
    "plugins/elephant/elephant_runtime/workspace_setup/",
    "scripts/workspace_core/",
    "scripts/workspace_setup/",
    "scripts/validate-linear-provider.py",
    "scripts/smoke-installed-setup-workspace.py",
    "plugins/elephant/references/providers/linear.md",
    "plugins/elephant/references/workspace/",
    "plugins/elephant/references/runtime-compatibility.md",
    "plugins/elephant/skills/init-profile/",
    "plugins/elephant/skills/ship-story/delivery-profile-schema.md",
    "plugins/elephant/skills/ship-story/slice-template.md",
    "plugins/elephant/skills/decompose-roadmap/roadmap-template.md",
    "plugins/elephant/skills/author-product-spec/spec-system-template.md",
    "docs/testing/linear-provider-sandbox.json",
    "docs/testing/linear-provider-sandbox.md",
    "docs/testing/setup-workspace-final-forward-smoke.md",
)
FORBIDDEN_ACTIVE_COUPLING = (
    ".claude/delivery-profile.md",
    "elephant_runtime.workspace_setup",
    "elephant_runtime.workspace_core",
    "elephant_runtime.linear",
    "legacy-mixed",
)


def _load_json(path: Path, errors: list[str]) -> dict[str, object] | None:
    if not path.is_file():
        errors.append(f"missing JSON asset: {path}")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid JSON asset {path}: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"JSON asset must be an object: {path}")
        return None
    return value


def _validate_required_assets(root: Path, errors: list[str]) -> None:
    for relative in REQUIRED_ASSETS:
        if not (root / relative).is_file():
            errors.append(f"missing required asset: {relative}")
    for skill in REQUIRED_SKILLS:
        path = root / PLUGIN / "skills" / skill / "SKILL.md"
        if not path.is_file():
            errors.append(f"missing required skill: {skill}")


def _validate_forbidden_assets(root: Path, errors: list[str]) -> None:
    for relative in FORBIDDEN_SUPERSEDED_ASSETS:
        path = root / relative.rstrip("/")
        if relative.endswith("/"):
            remains = path.is_dir() and any(
                item.is_file() and "__pycache__" not in item.parts
                for item in path.rglob("*")
            )
        else:
            remains = path.exists()
        if remains:
            errors.append(f"superseded asset remains: {relative.rstrip('/')}")


def _validate_manifests(root: Path, errors: list[str]) -> None:
    codex = _load_json(root / PLUGIN / ".codex-plugin/plugin.json", errors)
    claude = _load_json(root / PLUGIN / ".claude-plugin/plugin.json", errors)
    codex_marketplace = _load_json(root / ".agents/plugins/marketplace.json", errors)
    claude_marketplace = _load_json(root / ".claude-plugin/marketplace.json", errors)
    if not all((codex, claude, codex_marketplace, claude_marketplace)):
        return
    assert codex is not None and claude is not None
    assert codex_marketplace is not None and claude_marketplace is not None
    if codex.get("name") != "elephant" or claude.get("name") != "elephant":
        errors.append("both plugin manifests must use name elephant")
    if codex.get("version") != claude.get("version"):
        errors.append("plugin manifest versions differ")
    if codex.get("skills") != "./skills/":
        errors.append("Codex manifest must expose ./skills/")
    for label, marketplace in (
        ("Codex", codex_marketplace),
        ("Claude", claude_marketplace),
    ):
        plugins = marketplace.get("plugins")
        if not isinstance(plugins, list) or not plugins:
            errors.append(f"{label} marketplace has no plugin entry")
        elif not isinstance(plugins[0], dict) or plugins[0].get("name") != "elephant":
            errors.append(f"{label} marketplace plugin name must be elephant")


def _validate_skill_frontmatter(root: Path, errors: list[str]) -> None:
    for skill in REQUIRED_SKILLS:
        path = root / PLUGIN / "skills" / skill / "SKILL.md"
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n") or "\n---\n" not in text[4:]:
            errors.append(f"invalid skill frontmatter: {path.relative_to(root)}")
            continue
        frontmatter = text.split("\n---\n", 1)[0]
        if f"name: {skill}" not in frontmatter:
            errors.append(f"skill name mismatch: {path.relative_to(root)}")
        if "description:" not in frontmatter:
            errors.append(f"skill description missing: {path.relative_to(root)}")
        for phrase in FORBIDDEN_ACTIVE_COUPLING:
            if phrase in text:
                errors.append(
                    f"active skill contains superseded coupling {phrase}: "
                    f"{path.relative_to(root)}"
                )


def _validate_runtime(root: Path, errors: list[str]) -> None:
    package_root = root / PLUGIN / "elephant_runtime"
    if not package_root.is_dir():
        errors.append("missing minimal elephant_runtime package")
        return
    package_name = f"_elephant_runtime_validation_{abs(hash(root.resolve()))}"
    spec = importlib.util.spec_from_file_location(
        package_name,
        package_root / "__init__.py",
        submodule_search_locations=[str(package_root)],
    )
    if spec is None or spec.loader is None:
        errors.append("cannot load minimal elephant_runtime package")
        return
    package = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = package
    try:
        spec.loader.exec_module(package)
        map_spec = importlib.util.spec_from_file_location(
            f"{package_name}.workspace_map",
            package_root / "workspace_map.py",
        )
        if map_spec is None or map_spec.loader is None:
            errors.append("cannot load workspace_map runtime")
            return
        workspace_map = importlib.util.module_from_spec(map_spec)
        sys.modules[map_spec.name] = workspace_map
        map_spec.loader.exec_module(workspace_map)
        if getattr(package, "__all__", None) != ["workspace_map"]:
            errors.append("elephant_runtime exports must be exactly workspace_map")
        if frozenset(getattr(workspace_map, "__all__", ())) != EXPECTED_RUNTIME_EXPORTS:
            errors.append("workspace_map public exports differ from the minimal contract")
    except Exception as exc:
        errors.append(f"minimal runtime import failed: {exc}")
    finally:
        for name in tuple(sys.modules):
            if name == package_name or name.startswith(f"{package_name}."):
                sys.modules.pop(name, None)


def validate_repository(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    _validate_required_assets(root, errors)
    _validate_forbidden_assets(root, errors)
    _validate_manifests(root, errors)
    _validate_skill_frontmatter(root, errors)
    _validate_runtime(root, errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    errors = validate_repository(Path(args.root))
    if errors:
        for error in errors:
            print(error)
        return 1
    print("Elephant compatibility validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
