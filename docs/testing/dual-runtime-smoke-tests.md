# Elephant Dual-Runtime Smoke Tests

Run these cases after installing or updating Elephant. Start a new host session before testing. Use a disposable repository or branch for cases that write artifacts.

## 1. kickoff preflight

**Hosts:** Claude Code, Codex  
**Request:** explicitly invoke `elephant:kickoff` in a repository where one required Superpowers skill is unavailable.  
**Expected:** Elephant names the missing canonical skill, gives host-appropriate installation guidance, and creates no spec, roadmap, or profile artifact.

Repeat with all dependencies available. Expected: Elephant detects the first incomplete inception phase and invokes its canonical Elephant sub-skill.

## 2. neutral profile output

**Hosts:** Claude Code, Codex  
**Request:** invoke `elephant:init-profile` in a fixture repository with a roadmap, specs, and unambiguous repository conventions.  
**Expected:** after the single confirmation checkpoint, Elephant writes `.agents/elephant/delivery-profile.md`. It does not create a runtime-specific profile path.

## 3. instruction conflict

**Hosts:** Claude Code, Codex  
**Fixture:** root `AGENTS.md` requires merge commits while root `CLAUDE.md` requires squash merges.  
**Request:** invoke `elephant:init-profile`.  
**Expected:** the confirmation draft shows both candidate `finish.integration` values with source paths. Elephant waits for the user's resolution and does not silently prefer the active host.

## 4. missing profile

**Hosts:** Claude Code, Codex  
**Request:** invoke `elephant:ship-story` for a valid roadmap ID without `.agents/elephant/delivery-profile.md`.  
**Expected:** Elephant stops before research or artifact creation and directs the user to `kickoff` or `init-profile`.

## 5. non-UI bypass

**Hosts:** Claude Code, Codex  
**Fixture:** design gate enabled; slice spec §6 sensitivity is exactly `Low`.  
**Request:** invoke `elephant:ship-story` for the slice.  
**Expected:** phase detection skips the design gate and proceeds from the refined spec to planning.

## 6. manual design resume

**Hosts:** Claude Code, Codex  
**Fixture:** UI slice with `design.provider: manual`.  
**Request:** invoke `elephant:ship-story`.  
**Expected first run:** Elephant commits and pushes the `Refined` spec, reports the exact design directory and handoff fields, then stops.

Place design artifacts plus `design-handoff.md` in the directory and give the human ready signal.

**Expected resume:** Elephant verifies the non-empty directory, handoff file, and human signal, then continues to planning. Missing any one condition keeps the story at the design phase.

## 7. claude-design handoff

**Host:** Claude Code with DesignSync available  
**Fixture:** UI slice with `design.provider: claude-design` and valid `claude_design.project_ref` plus `slice_to_design_mapping`.  
**Request:** give the human ready signal and resume `elephant:ship-story`.  
**Expected:** Elephant pulls the mapped design, writes or validates `design-handoff.md`, applies the common gate, and continues.

Repeat with either provider field unresolved. Expected: Elephant stops and requests the exact missing value instead of guessing.

## 8. sequential research fallback

**Hosts:** a Claude Code or Codex session without worker delegation  
**Fixture:** a story with mature industry precedent and research depth set to three scopes.  
**Request:** approve the announced research.  
**Expected:** Elephant executes the same three scopes sequentially in the current agent, synthesizes them once, and continues to brainstorming without changing the requested scope.
