# Elephant Claude Code and Codex Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Elephant a single-source plugin that installs and runs in Claude Code and Codex without requiring Claude-specific paths, invocation tools, worker types, or design tooling.

**Architecture:** Keep one `plugins/elephant/skills/` tree and add parallel Claude and Codex packaging around it. Express runtime differences through one compatibility reference and a neutral `.agents/elephant/delivery-profile.md`; enforce the boundary with a standard-library Python validator and regression tests.

**Tech Stack:** Markdown Agent Skills, JSON plugin manifests, Python 3 standard library (`unittest`, `json`, `pathlib`, `re`), Git, Codex plugin/skill validators.

## Global Constraints

- Claude Code and Codex load the same five Elephant skills from `plugins/elephant/skills/`.
- `.agents/elephant/delivery-profile.md` is the only supported delivery-profile path.
- Do not read, migrate, or dual-write `.claude/delivery-profile.md`.
- Superpowers remains an external peer dependency.
- `manual` is the cross-platform default design provider.
- `claude-design` is an optional provider; Claude-specific terms stay inside its adapter and Claude installation documentation.
- `agent-assisted` is only a documented future extension point.
- Core workflows must degrade to sequential research when worker delegation is unavailable.
- No MCP server, hook, or duplicated runtime-specific skill tree is introduced.

---

### Task 1: Compatibility Validator Foundation

**Files:**
- Create: `tests/test_compatibility.py`
- Create: `scripts/validate-compatibility.py`

**Interfaces:**
- Produces: `validate_repository(root: pathlib.Path) -> list[str]`
- Produces: CLI exit code `0` with `Elephant compatibility validation passed.` or exit code `1` with one error per line.
- Consumes: repository root supplied through `--root`, defaulting to the parent of `scripts/`.

- [ ] **Step 1: Write failing validator tests**

Create `tests/test_compatibility.py` with tests that import the script by file path and assert:

```python
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).parents[1] / "scripts" / "validate-compatibility.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("compatibility_validator", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CompatibilityValidatorTests(unittest.TestCase):
    def test_current_repository_passes(self):
        validator = load_validator()
        self.assertEqual([], validator.validate_repository(Path(__file__).parents[1]))

    def test_missing_codex_manifest_is_reported(self):
        validator = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "plugins/elephant/skills/demo").mkdir(parents=True)
            (root / "plugins/elephant/skills/demo/SKILL.md").write_text(
                "---\nname: demo\ndescription: Use when testing.\n---\n",
                encoding="utf-8",
            )
            errors = validator.validate_repository(root)
            self.assertIn("missing Codex plugin manifest", errors)

    def test_forbidden_core_coupling_is_reported(self):
        validator = load_validator()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "plugins/elephant/skills/demo/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text(
                "---\nname: demo\ndescription: Use when testing.\n---\n"
                "Dispatch via the Skill tool.\n",
                encoding="utf-8",
            )
            errors = validator.validate_repository(root)
            self.assertTrue(
                any("Claude-only core phrase" in error for error in errors),
                errors,
            )
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python3 -m unittest tests/test_compatibility.py -v
```

Expected: import failure because `scripts/validate-compatibility.py` does not exist.

- [ ] **Step 3: Implement the validator**

Create a validator that:

- parses both marketplace JSON files and both plugin manifests;
- checks shared plugin name/version and Codex `skills: "./skills/"`;
- resolves Codex `source.path` from the repository root and requires `plugins/elephant`;
- parses every `SKILL.md` frontmatter for non-empty `name` and `description`;
- scans shared skill/reference text for `.claude/delivery-profile.md`, `via the Skill tool`, `` `Explore` ``, and `claudemd_refresh_targets`;
- permits Claude-specific terms in `.claude-plugin/**`, README host-specific sections, and the explicitly named Claude Design adapter text;
- returns all errors instead of stopping after the first one.

The CLI skeleton is:

```python
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = validate_repository(args.root.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Elephant compatibility validation passed.")
    return 0
```

- [ ] **Step 4: Run tests and inspect expected compatibility failures**

Run:

```bash
python3 -m unittest tests/test_compatibility.py -v
```

Expected: fixture tests pass; `test_current_repository_passes` fails with missing Codex packaging and current Claude-only coupling errors. This is the RED proof for Tasks 2–4.

- [ ] **Step 5: Commit validator foundation**

```bash
git add tests/test_compatibility.py scripts/validate-compatibility.py
git commit -m "test: add dual-runtime compatibility validator"
```

### Task 2: Dual Plugin Packaging

**Files:**
- Create: `.agents/plugins/marketplace.json`
- Create: `plugins/elephant/.codex-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `plugins/elephant/.claude-plugin/plugin.json`
- Modify: `tests/test_compatibility.py`

**Interfaces:**
- Consumes: `validate_repository(root)`.
- Produces: matching `elephant` manifests at version `0.2.0`.
- Produces: Codex marketplace source `{ "source": "local", "path": "./plugins/elephant" }`.

- [ ] **Step 1: Add packaging assertions**

Extend the test suite to assert that both manifests have the same `name` and `version`, the Codex manifest declares `skills: "./skills/"`, and the Codex marketplace entry contains:

```python
{
    "name": "elephant",
    "source": {"source": "local", "path": "./plugins/elephant"},
    "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    },
    "category": "Productivity",
}
```

- [ ] **Step 2: Run the packaging tests and verify RED**

Run:

```bash
python3 -m unittest tests/test_compatibility.py -v
```

Expected: failure because the Codex files are absent and the Claude manifest is still `0.1.0`.

- [ ] **Step 3: Add the Codex manifest and marketplace**

Create a Codex manifest with required publisher/interface metadata, `skills: "./skills/"`, and no MCP/apps/hooks fields. Create the repo marketplace with top-level `name: "elephant"`, `interface.displayName: "Elephant"`, and the policy-bearing local entry above.

Update the Claude manifest to `0.2.0` and keep its existing publisher metadata. Preserve Claude's marketplace shape while updating copy to say the shared workflow supports Claude Code and Codex.

- [ ] **Step 4: Run packaging tests and validators**

Run:

```bash
python3 -m unittest tests/test_compatibility.py -v
python3 /Users/aki/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/elephant
```

Expected: packaging assertions pass; repository compatibility may still fail only on skill coupling addressed next; Codex plugin validation passes.

- [ ] **Step 5: Commit dual packaging**

```bash
git add .agents/plugins/marketplace.json .claude-plugin/marketplace.json \
  plugins/elephant/.codex-plugin/plugin.json plugins/elephant/.claude-plugin/plugin.json \
  tests/test_compatibility.py
git commit -m "feat: add Codex plugin packaging"
```

### Task 3: Neutral Runtime and Profile Contracts

**Files:**
- Create: `plugins/elephant/references/runtime-compatibility.md`
- Modify: `plugins/elephant/skills/init-profile/SKILL.md`
- Modify: `plugins/elephant/skills/ship-story/delivery-profile-schema.md`
- Modify: `tests/test_compatibility.py`

**Interfaces:**
- Produces: the sole profile path `.agents/elephant/delivery-profile.md`.
- Produces: `instruction_refresh_targets`.
- Produces design providers `manual` and `claude-design`.
- Produces runtime fallback rules for skill invocation and worker delegation.

- [ ] **Step 1: Add neutral-contract tests**

Add assertions that:

```python
profile_path = ".agents/elephant/delivery-profile.md"
self.assertIn(profile_path, init_profile_text)
self.assertIn(profile_path, ship_story_text)
self.assertNotIn(".claude/delivery-profile.md", shared_workflow_text)
self.assertIn("instruction_refresh_targets", schema_text)
self.assertIn("provider", schema_text)
self.assertIn("handoff_file", schema_text)
```

Also assert `runtime-compatibility.md` documents canonical skill names, sequential worker fallback, `AGENTS.md`, `CLAUDE.md`, and the two supported design providers.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python3 -m unittest tests/test_compatibility.py -v
```

Expected: failures on the old profile path, missing neutral field, and missing runtime reference.

- [ ] **Step 3: Write the runtime compatibility reference**

Document:

- explicit invocation uses each host's native skill selection syntax;
- workflows refer to canonical skill names and never assume a host-specific Skill tool;
- delegation uses bounded workers when available and sequential scopes otherwise;
- persistent instructions may come from `AGENTS.md` and `CLAUDE.md`, with provenance and conflict confirmation;
- Superpowers is a required peer dependency and preflight failures stop before artifacts;
- `manual` works everywhere and `claude-design` is optional.

- [ ] **Step 4: Rewrite profile discovery and schema**

Update `init-profile` to write only the neutral path, mine both instruction families, preserve source provenance, and surface conflicts. Rename closeout fields and replace the DesignSync-shaped schema with the provider-independent gate contract.

Keep reconciliation behavior for an existing neutral profile, but do not inspect the old Claude path.

- [ ] **Step 5: Run tests and validators**

Run:

```bash
python3 -m unittest tests/test_compatibility.py -v
python3 scripts/validate-compatibility.py
```

Expected: neutral contract assertions pass; remaining errors identify orchestration and template coupling handled in Task 4.

- [ ] **Step 6: Commit neutral contracts**

```bash
git add plugins/elephant/references/runtime-compatibility.md \
  plugins/elephant/skills/init-profile/SKILL.md \
  plugins/elephant/skills/ship-story/delivery-profile-schema.md \
  tests/test_compatibility.py
git commit -m "refactor: define runtime-neutral delivery contract"
```

### Task 4: Runtime-Neutral Orchestration and Design Gate

**Files:**
- Modify: `plugins/elephant/skills/kickoff/SKILL.md`
- Modify: `plugins/elephant/skills/author-product-spec/SKILL.md`
- Modify: `plugins/elephant/skills/decompose-roadmap/SKILL.md`
- Modify: `plugins/elephant/skills/ship-story/SKILL.md`
- Modify: `plugins/elephant/skills/ship-story/slice-template.md`
- Modify: `tests/test_compatibility.py`

**Interfaces:**
- Consumes: runtime capability rules and neutral profile schema from Task 3.
- Produces: preflight behavior for required Superpowers skills.
- Produces: provider-independent design gate validation.
- Produces: sequential research fallback.

- [ ] **Step 1: Add orchestration behavior assertions**

Test for these observable contracts:

- kickoff and ship-story mention preflighting required Superpowers skills;
- ship-story specifies bounded workers with sequential fallback;
- ship-story requires `design-handoff.md`;
- ship-story supports only `manual` and `claude-design`;
- shared workflow and template text contain no old profile path, Skill tool dispatch, `Explore` worker requirement, or “Claude Code” engineering audience.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python3 -m unittest tests/test_compatibility.py -v
```

Expected: failures point to kickoff Skill tool wording, ship-story worker/design assumptions, old closeout fields, and the slice template's Claude Code audience.

- [ ] **Step 3: Neutralize skill orchestration**

Make these focused edits:

- kickoff preflights the three Elephant sub-skills and required Superpowers dependencies, invokes canonical names, and uses the neutral profile path;
- author-product-spec and decompose-roadmap use host-neutral invocation language;
- ship-story reads the neutral profile, treats worker delegation as optional acceleration, and uses canonical Superpowers skill names;
- closeout refreshes `instruction_refresh_targets`;
- unsupported providers fail with the supported list.

- [ ] **Step 4: Implement the common design handoff gate**

For `manual`:

1. commit and push the Refined spec;
2. stop with the exact design directory and `design-handoff.md` requirements;
3. resume only when artifacts exist and the human signal is present.

For `claude-design`:

1. commit and push the Refined spec;
2. wait for the human signal;
3. use the configured DesignSync project/mapping;
4. pull artifacts;
5. generate or validate the same handoff file;
6. enter the common gate.

Replace “Claude Code” in `slice-template.md` with “coding agent” while retaining Claude Design only as an example provider where relevant.

- [ ] **Step 5: Run the complete regression suite**

Run:

```bash
python3 -m unittest tests/test_compatibility.py -v
python3 scripts/validate-compatibility.py
```

Expected: all tests and compatibility checks pass.

- [ ] **Step 6: Commit orchestration compatibility**

```bash
git add plugins/elephant/skills tests/test_compatibility.py
git commit -m "refactor: make Elephant workflows runtime-neutral"
```

### Task 5: Dual-Host Documentation and Smoke Cases

**Files:**
- Modify: `README.md`
- Create: `docs/testing/dual-runtime-smoke-tests.md`
- Modify: `tests/test_compatibility.py`

**Interfaces:**
- Produces: exact Claude Code and Codex install/invocation instructions.
- Produces: eight repeatable smoke cases with expected outcomes.

- [ ] **Step 1: Add documentation assertions**

Assert README contains separate `Claude Code` and `Codex` install sections, the neutral profile path, Superpowers prerequisite, manual design flow, optional Claude Design provider, and a new-session instruction after plugin reinstall.

Assert the smoke document names all eight cases from the approved design:

```text
kickoff preflight
neutral profile output
instruction conflict
missing profile
non-UI bypass
manual design resume
claude-design handoff
sequential research fallback
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python3 -m unittest tests/test_compatibility.py -v
```

Expected: README and smoke-case assertions fail.

- [ ] **Step 3: Rewrite README and add smoke cases**

Document the shared architecture, host-specific marketplace installation, explicit `$elephant:...` Codex invocations and Claude slash/skill invocations, reinstall behavior, the neutral profile, and both design providers.

For each smoke case record prerequisites, request, expected artifact/stop/resume behavior, and host coverage.

- [ ] **Step 4: Run documentation and repository validation**

Run:

```bash
python3 -m unittest tests/test_compatibility.py -v
python3 scripts/validate-compatibility.py
python3 /Users/aki/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/elephant
```

Expected: all pass.

- [ ] **Step 5: Commit documentation**

```bash
git add README.md docs/testing/dual-runtime-smoke-tests.md tests/test_compatibility.py
git commit -m "docs: add dual-runtime setup and smoke tests"
```

### Task 6: Skill Validation, Codex Installation, and Final Verification

**Files:**
- Modify only if validation exposes a defect in files from Tasks 1–5.

**Interfaces:**
- Consumes: complete repository.
- Produces: installed `elephant` Codex plugin from the repo marketplace.
- Produces: clean Git status and recorded verification evidence in command output.

- [ ] **Step 1: Validate every skill**

Run:

```bash
for skill in plugins/elephant/skills/*; do
  python3 /Users/aki/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$skill"
done
```

Expected: every skill reports valid.

- [ ] **Step 2: Run all deterministic checks**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate-compatibility.py
python3 /Users/aki/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/elephant
git diff --check
```

Expected: all commands pass with no warnings or whitespace errors.

- [ ] **Step 3: Install the repo marketplace and plugin**

Inspect configured marketplaces and add the repository marketplace root if needed:

```bash
codex plugin marketplace list
codex plugin marketplace add /Users/aki/Documents/Maio/elephant
codex plugin add elephant@elephant
codex plugin list
```

Expected: the local `elephant` marketplace is visible and the `elephant` plugin is installed/enabled. If the marketplace already exists, do not add a duplicate; reinstall the plugin from the existing local source.

- [ ] **Step 4: Verify skill discovery in a fresh Codex process**

Start a non-mutating Codex check that asks for the installed Elephant skill inventory and neutral profile path. Confirm the response names all five skills and `.agents/elephant/delivery-profile.md`.

If the installed plugin is cached at the previous version, update its Codex cachebuster with the plugin-creator helper, reinstall, and repeat the check in a new process.

- [ ] **Step 5: Review changes and commit validation fixes**

Run:

```bash
git status --short
git diff --stat origin/main...HEAD
git log --oneline origin/main..HEAD
```

If validation required fixes, commit them with:

```bash
git add README.md .agents/plugins/marketplace.json .claude-plugin/marketplace.json \
  plugins/elephant scripts/validate-compatibility.py \
  tests/test_compatibility.py docs/testing/dual-runtime-smoke-tests.md
git commit -m "fix: satisfy dual-runtime validation"
```

- [ ] **Step 6: Final verification and push**

Run the complete deterministic check set once more, verify `git status --short` is empty, then:

```bash
git push origin main
```

Expected: `main` and `origin/main` are synchronized. Report that Claude Code activation and live DesignSync behavior remain the documented post-reinstall host smoke checks because they cannot execute inside a Codex-only session.
