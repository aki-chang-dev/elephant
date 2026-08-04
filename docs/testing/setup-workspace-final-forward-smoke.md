# Setup Workspace Final Forward and Installed-Artifact Smoke

Date: 2026-08-04
Base commit: `f3fe0b2362576383f76c1a000df7652c8a0162ba`
Implementation commit: recorded by the signed follow-up evidence commit after verification
Marketplace source: `./plugins/elephant`

## Fresh-context forward prompt

The forward probe was dispatched without conversation history and was instructed to
read the installed skill and reference completely before answering:

> 我们已经展示并由 owner 批准了一个完整 setup manifest，变量名
> `approved_manifest`，fingerprint 为 `fp-approved`. 第一次 apply 遇到缺失的行政
> 对象，必须暂停让人手工创建；第一次 attempt ID 要用
> `artifact-manual-handoff`。手工完成后继续，不允许第二次 owner approval。请给出
> 两次 `apply_setup` 调用的精确 Python 形态，并说明第二次如何验证后才能落本地文件；
> 第二次 attempt ID 必须用 `artifact-manual-resume`。不要假设真实 Linear/Notion
> adapter 已实现。

## Initial raw forward answer (superseded)

```python
from elephant_runtime.workspace_setup import apply_setup

assert approved_manifest.fingerprint == "fp-approved"

first_result = apply_setup(
    approved=approved_manifest,
    adapters=setup_adapters,
    write_local=local_writer,
    execution_id="artifact-manual-handoff",
)

assert first_result.ready is False
assert len(first_result.manual_handoffs) == 1
assert first_result.local_writes == ()

# 人工按 handoff 创建行政对象后，继续使用同一个 ApprovedManifest。
# 不重建 manifest，也不再次调用 approve_manifest()。
assert approved_manifest.fingerprint == "fp-approved"

second_result = apply_setup(
    approved=approved_manifest,
    adapters=setup_adapters,
    write_local=local_writer,
    execution_id="artifact-manual-resume",
)
```

Final senior review correctly rejected this answer: a distinct execution ID by
itself did not carry proof that the caller possessed the handoff from the prior
attempt. The runtime and protocol were tightened with a typed continuation
token before final certification.

## Corrected canonical forward answer

```python
from elephant_runtime.workspace_setup import apply_setup

assert approved_manifest.fingerprint == "fp-approved"

first_result = apply_setup(
    approved=approved_manifest,
    adapters=setup_adapters,
    write_local=local_writer,
    execution_id="artifact-manual-handoff",
)

assert first_result.ready is False
assert len(first_result.manual_handoffs) == 1
assert first_result.local_writes == ()

# 人工按 handoff 创建行政对象后，继续使用同一个 ApprovedManifest 和返回的 handoff。
# 不重建 manifest，也不再次调用 approve_manifest()。
assert approved_manifest.fingerprint == "fp-approved"

second_result = apply_setup(
    approved=approved_manifest,
    adapters=setup_adapters,
    write_local=local_writer,
    execution_id="artifact-manual-resume",
    resume_handoff=first_result.manual_handoffs[0],
)
```

第二次调用会在内部先重新计算 manifest fingerprint，并与同一个
`approved_manifest.fingerprint` 比较，并验证 `resume_handoff` 内嵌的是这份 approval、
第一次 execution ID 和完全相同的 MANUAL operation/semantics/instructions，且第二次
execution ID 不同。随后按已批准的 stable key 查询人工创建的对象，并要求：

1. 恰好一个匹配记录；
2. 记录语义 fingerprint 等于已批准的 desired fingerprint；
3. 按 external ID read-back 成功；
4. 再做一次带唯一性保护的 stable-key 查询；
5. 最终唯一记录仍保持相同 external ID 和已批准 fingerprint。

通过后才产生 `manual_completed` evidence。接着所有剩余外部操作必须逐项
read-back，所有 disposable round trip 必须完成创建、读取、绑定、删除并证明不存
在；然后才执行已预检的本地原子事务，并重新加载、按 canonical schema 验证写出的
registry/profile。缺失、重复、fingerprint 不匹配、read-back 失败或 absence proof
失败都会阻止本地写入。

`setup_adapters` 在 Phase 2 只能是注入的 fake `SetupAdapter` 映射；不能假设真实
Linear/Notion adapter 已实现。若选择真实 Linear/Notion provider，应在任何外部或
本地 mutation 前停止。

## Independent evaluator verdict

`PASS`

- 两次调用复用同一个 `approved_manifest`，并断言相同 fingerprint。
- execution ID 分别为 `artifact-manual-handoff` 与
  `artifact-manual-resume`，明确不同。
- 第二次调用传回 `first_result.manual_handoffs[0]`；token 绑定第一次 execution ID、
  approval fingerprint 和完全相同的 MANUAL operation。
- 明确声明不重建 manifest、不再次调用 `approve_manifest()`。
- MANUAL completion 要求 stable key 唯一、语义 fingerprint 匹配、external ID
  read-back，再次唯一性校验；通过前不进行 round-trip 或本地写入。
- 后续 round-trip、absence proof 与本地原子写入的顺序描述正确。
- 明确限定 `setup_adapters` 为注入的 fake adapter；真实 Linear/Notion adapter
  未实现时必须在 mutation 前停止，没有冒充真实 provider。

## Exact installed-artifact smoke command

```bash
PYTHONDONTWRITEBYTECODE=1 python3 \
  scripts/smoke-installed-setup-workspace.py --root . --json
```

The harness parses `.agents/plugins/marketplace.json`, copies only its declared
plugin source into a temporary directory, and invokes the copied runtime with
`python -I` from a separate temporary working directory.

## Raw smoke output

```json
{"artifact_digest": "a7ec223f354bfd85b1e2cc9ced0493d4009383292612b1d50ed9d6477f30de15", "artifact_source": "./plugins/elephant", "attempt_ids": ["artifact-manual-handoff", "artifact-manual-resume"], "binding_count": 3, "isolated_command": "python -I -c <artifact public-pipeline smoke>", "local_owner": "artifact-manual-resume", "manifest_fingerprint": "83ebad5fc6ee88acf92dc2e7287412acc378c7d87f7a22c643ed4ffc94cf7c88", "placeholder_absent": true, "round_trip_keys": ["setup.round_trip.linear.83ebad5fc6ee88acf92dc2e7287412acc378c7d87f7a22c643ed4ffc94cf7c88.artifact-manual-resume"], "runtime_origin": "/private/var/folders/y7/wv73nl2916g_br9krg8878gm0000gr/T/tmpmv_c9gwj/artifact/elephant_runtime/installed_smoke.py", "same_approval": true, "schema_valid": true, "status": "ok"}
```

The artifact digest is a length-framed SHA-256 over every installed artifact
relative path and file body. The runtime origin proves the child process loaded
the temporary marketplace copy rather than checkout compatibility modules.
