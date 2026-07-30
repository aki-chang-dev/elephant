# Product-First Story Skill Tests

This document preserves the representative RED worker observations used to shape the v2 skills.
Later GREEN runs use the same scenarios and compare their questions, decisions, and stated
reasoning against these records.

## RED baseline: product drift

Current `ship-story` asked about copied entities, tokens, deploy paths, status, endpoints, and
API/data contracts before completing product definition, then wrote a mixed Engineering Brief +
Design Brief.

### Verbatim RED worker questions

1. 你说的“相似 setup”是希望默认复制完整配置，还是只复制 Traffic Source、Offer 和基础跳转设置？
2. 新 Campaign 是否一律创建为 Draft，并生成全新的 tracking link，同时不复制点击、转化、部署状态、测试 token、preview token 和 delivery health？
3. Lander 的目标域名与 deploy path 不能被两个 Campaign 同时占用；复制时应自动生成新 path、暂不复制 Lander 配置，还是让用户在弹窗里选择？
4. 入口是否放在 Campaign 行的 `…` 菜单中，并先打开一个只要求确认新名称的小弹窗？
5. 复制完成后，是直接打开新 Campaign 的编辑 Sheet 让买手调整后再启用，还是留在列表并仅显示成功提示？

### Verbatim RED worker decisions

- `POST /api/campaigns/:id/duplicate` — 接收新名称，返回完整的新 Campaign。
- 请求：`{ name: string }`。响应：`{ campaign: Campaign }`。
- Campaign 本体与所有配置关联行在单个 DB transaction 内复制。
- `status='draft'`；`closing_expires_at`、`test_token`、`bypass_token` 置空。
- Lander config 生成新 ID，并将 deploy path 转换为同域名下未占用的新路径。
- `POST /api/campaigns/:id/duplicate` ↔ `DuplicateCampaignDialog`; UI 用返回对象打开 `CampaignEditSheet`。

### Verbatim RED worker ready rationale

- **Status**: Refined
- §1、§2、§5、§7 为 Code 与 Design 共识。
- §3、§4 约束实现；§6 约束复制入口、确认与完成反馈。
- **Open Design Questions**
  - 无；brainstorm 已锁定入口、确认信息、成功去向与错误反馈。

## RED baseline: invalid product idea

A roadmap-progress dashboard card exposing phase, slice ID, and implementation percentage had no
formal reject/defer disposition. Current workflow effectively approved it and specified a
roadmap-progress API plus user-visible internal delivery language.

### Verbatim RED worker questions

1. What operational decision should an operator make after viewing this progress card?
2. Which operators may see it, and is exposing internal roadmap phases and slice IDs acceptable to that audience?
3. What system is the source of truth for the current phase and active slice?
4. How exactly is “percent implementation complete” calculated: completed acceptance criteria, completed slices, engineering tasks, or a manually maintained value?
5. Where should the card appear, how frequently should it refresh, and what should it show when progress data is unavailable or stale?

### Verbatim RED worker disposition and rationale

- “Formal disposition: No. The current workflow has no explicit approve/split/defer/reject product gate. It only decomposes when scope is too large, then proceeds from brainstorming into a `Refined` spec. Effective selection: **approve**.”

### Verbatim RED worker decisions

- API shape: `{ phase, activeSliceId, completionPercent, updatedAt, status }`.
- Example UI copy included `Active slice: P-31` and `42% implemented`.
- The draft specified loading, unavailable, stale, and complete states and a Medium design sensitivity.

## RED baseline: technical overreach

A general technical author produced a strong draft but silently resolved ambiguous product meanings
for copied IDs, name suffixing, and edit-only configuration, and used self-review instead of
independent specialist review.

### Verbatim RED worker assumptions

- “IDs are not copied” means generated identity and runtime IDs: campaign ID, slug/tracking link, lander-config row IDs, deployment IDs, tokens, timestamps, and similar values. Reference IDs required to preserve configuration—traffic source, offers, landers, domains, and filter lists—remain selected.
- “User-owned configuration” is bounded by what the existing normal Create flow represents: name, traffic source, weighted offers, notes, redirect strategy, direct-access protection, and landing-page configuration including references, paths, macros, weights, purpose, and stage. Edit-only cloak, pixel, bypass/test-console, lifecycle, deployment, reporting, and postback-endpoint state are not silently carried through an otherwise unchanged Create dialog.
- The copied name is exactly `<existing name> Copy`; duplicating a copy appends another ` Copy`. No uniqueness probing or automatic numbering is introduced.
- The destination is always a new `draft`.

### Verbatim RED worker review and rationale evidence

- “No behavior beyond the approved contract is added.”
- It proposed a contract-traceability review, repository-consistency review, data-minimization review, tenant/security review, and testability/ambiguity self-review.
- “No later owner technical review is required for choices within this boundary; implementation still receives ordinary engineering/code review...”
- The same worker said it would stop only when an unresolved choice changes observable product behavior, and specifically named edit-only cloak/pixel settings and separately managed postback-endpoint configuration as an ambiguity.
