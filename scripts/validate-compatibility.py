#!/usr/bin/env python3
"""Validate Elephant's shared Claude Code and Codex plugin contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re


PLUGIN = Path("plugins/elephant")
CODEX_MANIFEST = PLUGIN / ".codex-plugin/plugin.json"
CLAUDE_MANIFEST = PLUGIN / ".claude-plugin/plugin.json"
CODEX_MARKETPLACE = Path(".agents/plugins/marketplace.json")
CLAUDE_MARKETPLACE = Path(".claude-plugin/marketplace.json")

FORBIDDEN_CORE_PHRASES = (
    ".claude/delivery-profile.md",
    "via the Skill tool",
    "`Explore`",
    "claudemd_refresh_targets",
)

REQUIRED_V2_ASSETS = (
    "shape-story/SKILL.md",
    "shape-story/product-contract-template.md",
    "shape-story/reviewers/product-ux-critic.md",
    "shape-story/reviewers/copy-critic.md",
    "author-technical-contract/SKILL.md",
    "author-technical-contract/technical-contract-template.md",
    "author-technical-contract/reviewers/architecture.md",
    "author-technical-contract/reviewers/domain-data.md",
    "author-technical-contract/reviewers/security-operations.md",
    "author-technical-contract/reviewers/product-conformance.md",
    "author-technical-contract/reviewers/test.md",
    "author-technical-contract/reviewers/technical-adjudicator.md",
    "ship-story/reviewers/implementation-conformance.md",
)


def _load_json(path: Path, label: str, errors: list[str]) -> dict | None:
    if not path.is_file():
        errors.append(f"missing {label}")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid {label}: {exc}")
        return None
    if not isinstance(value, dict):
        errors.append(f"invalid {label}: root must be an object")
        return None
    return value


def _validate_frontmatter(path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---(?:\n|\Z)", text, re.DOTALL)
    if not match:
        errors.append(f"{path}: missing YAML frontmatter")
        return
    frontmatter = match.group(1)
    for field in ("name", "description"):
        field_match = re.search(rf"(?m)^{field}:\s*(.+?)\s*$", frontmatter)
        if not field_match or not field_match.group(1).strip("\"' "):
            errors.append(f"{path}: missing frontmatter field {field}")


def _validate_manifests(root: Path, errors: list[str]) -> None:
    codex = _load_json(root / CODEX_MANIFEST, "Codex plugin manifest", errors)
    claude = _load_json(root / CLAUDE_MANIFEST, "Claude plugin manifest", errors)
    if codex is None or claude is None:
        return
    if codex.get("name") != claude.get("name"):
        errors.append("plugin manifest names differ")
    if codex.get("version") != claude.get("version"):
        errors.append("plugin manifest versions differ")
    if codex.get("skills") != "./skills/":
        errors.append('Codex plugin manifest must set skills to "./skills/"')


def _validate_marketplaces(root: Path, errors: list[str]) -> None:
    codex = _load_json(root / CODEX_MARKETPLACE, "Codex marketplace", errors)
    _load_json(root / CLAUDE_MARKETPLACE, "Claude marketplace", errors)
    if codex is None:
        return
    entries = codex.get("plugins")
    if not isinstance(entries, list):
        errors.append("Codex marketplace plugins must be an array")
        return
    elephant = next(
        (entry for entry in entries if isinstance(entry, dict) and entry.get("name") == "elephant"),
        None,
    )
    if elephant is None:
        errors.append("Codex marketplace is missing the elephant entry")
        return
    expected_source = {"source": "local", "path": "./plugins/elephant"}
    if elephant.get("source") != expected_source:
        errors.append("Codex marketplace elephant source is invalid")
    source_path = elephant.get("source", {}).get("path")
    if isinstance(source_path, str):
        resolved = (root / source_path).resolve()
        if resolved != (root / PLUGIN).resolve():
            errors.append("Codex marketplace source does not resolve to plugins/elephant")
    expected_policy = {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}
    if elephant.get("policy") != expected_policy:
        errors.append("Codex marketplace elephant policy is invalid")
    if elephant.get("category") != "Productivity":
        errors.append("Codex marketplace elephant category must be Productivity")


def _validate_skills(root: Path, errors: list[str]) -> None:
    skills_root = root / PLUGIN / "skills"
    if not skills_root.is_dir():
        errors.append("missing shared skills directory")
        return
    skill_files = sorted(skills_root.glob("*/SKILL.md"))
    if not skill_files:
        errors.append("shared skills directory contains no skills")
        return
    for path in skill_files:
        _validate_frontmatter(path, errors)
        text = path.read_text(encoding="utf-8")
        for phrase in FORBIDDEN_CORE_PHRASES:
            if phrase in text:
                relative = path.relative_to(root)
                errors.append(
                    f"{relative}: Claude-only core phrase is forbidden: {phrase}"
                )


def _validate_v2_assets(root: Path, errors: list[str]) -> None:
    skills_root = root / PLUGIN / "skills"
    for relative in REQUIRED_V2_ASSETS:
        path = skills_root / relative
        if not path.is_file():
            errors.append(
                f"missing required v2 asset: {(PLUGIN / 'skills' / relative).as_posix()}"
            )


def validate_repository(root: Path) -> list[str]:
    """Return every compatibility error found below *root*."""
    errors: list[str] = []
    _validate_manifests(root, errors)
    _validate_marketplaces(root, errors)
    _validate_skills(root, errors)
    _validate_v2_assets(root, errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args()
    errors = validate_repository(args.root.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Elephant compatibility validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
