---
feature: state-machine-core
status: delivered
updated: 2026-09-10
branch: feat/state-machine-core
commits: 00d772ffe57c610c3217b8294d6b2794df175ca2..2e845ab
---

# 状态机内核（State Machine Core）

## Report

**What was built** — MaLiang 新增 `maliang_art.statemachine`：YAML 策略加载与校验、可插拔步骤注册表（内置 `chroma-key` / `align-canvas`）、内存态状态机 `StateMachine.apply`（返回带稳定 ID 的转换记录，但不发布该记录；返回 dict 仍可被调用方修改）、默认策略模板 `draft → review → done/rejected`（`approvers: []`），以及 CLI `flow validate|show-default-template|transitions`。项目身份、画布尺寸与审批人值均不进库。

**当前状态** — 实现提交 2e845ab 随 feat/state-machine-core 经 main 的 62cceff（PR #1）合并；后续 641d34a 经 5c5fa08（PR #2）修复内置图像步骤串联与逐步深快照。`apply` 不发布转换 JSON，但内置步骤可写入/覆盖显式图片路径；步骤失败不回滚之前的图片写入。下述验证是原交付时记录，本轮未重新执行构建或远端 CI。

**Verification** — `pytest tests/ -q`：200 passed，3 skipped（Windows symlink）。`python -m build --wheel` 成功，wheel 含 `maliang_art/statemachine/templates/default-policy.yaml` 与 schemas。CLI 三条命令手工冒烟通过。独立 reviewer 两轮：首轮 8 项 critical 全部修复后，复审确认 FIXED 且无新 critical。

**Journey log** —
- 术语定为「状态机内核」，避免与 Godot runtime 语义冲突。
- 策略/机制分离：库只提供机制与空审批人模板，项目自带 YAML。
- 显式 `null` 与键缺失必须区分；空 approvers 可 load、apply 时 fail-closed。
- wheel 对包内 templates 使用自动打包；`force-include` 仅用于包外 `schemas`，重复 force-include 会导致双写失败。
- Pillow 兼容用 `getattr(image, "get_flattened_data", image.getdata)`，不能只调用 12.1+ API。

## [S1] 问题

马良 v0.1 能记账（姿态证明、Review 校验、不可变 JSON 发布），但**不能跑流程**。

一个美术资产从「草稿」到「正式」通常要走状态：生成 → 预处理 → 审查 → 批准/否决 → 正式。现在这件事只能：

1. 在项目 Python 代码里写死 `if state != "ingested": raise ...`（如 tactics 七千行管线），或
2. 每个项目重写一套。

结果是：**策略**（有哪些状态、谁可以批、抠图用什么幕色）和**机制**（如何求值转换、如何执行步骤、如何留审计记录）搅在一起。改一个项目规则要改库代码，无法复用。

用户已确认的定位：

- 术语：**状态机内核**（不用「引擎」，避免与 Godot 混淆）
- 范围：**内核 + 默认策略模板**（机制进马良；项目身份、尺寸、审批人不进马良）
- 配置：**YAML**（可读性优先；马良为此增加 PyYAML 依赖）
- 边界：不迁移 tactics；不写死项目；现有 JSON 记录类型不变

## [S2] 设计

### 2.1 模块与文件清单

实现时**只允许**新增/修改下列路径（测试文件见 T6）：

```text
src/maliang_art/statemachine/__init__.py
src/maliang_art/statemachine/config.py
src/maliang_art/statemachine/machine.py
src/maliang_art/statemachine/steps.py
src/maliang_art/statemachine/records.py
src/maliang_art/statemachine/templates/default-policy.yaml
schemas/v1/state-machine-policy.schema.json
src/maliang_art/cli.py                          # 仅追加 flow 子命令
pyproject.toml                                  # 依赖 + 包数据
README.md / README.zh-CN.md                     # 使用说明
tests/test_statemachine_config.py
tests/test_statemachine_steps.py
tests/test_statemachine_machine.py
tests/test_statemachine_cli.py
```

**禁止**修改：`core.py`、`pose.py`、`review.py`、`records.py`、`workflow.py`、`ports.py`、`adapters.py` 的既有行为。

### 2.2 公开导出

`maliang_art.statemachine.__init__` 必须导出且仅导出：

```python
__all__ = [
    "PolicyValidationError",
    "StateTransitionError",
    "StateMachine",
    "StepRegistry",
    "load_policy",
    "PolicyModel",
    "TransitionDecl",
    "StepDecl",
    "builtin_template_path",
    "default_template_text",
]
```

- `PolicyValidationError`、`StateTransitionError` 在 `config.py` / `machine.py` 定义，均 `class X(MaLiangError)`。
- `load_policy` 支持 `str | Path`，返回 `PolicyModel`。
- `builtin_template_path()` 返回包内 `templates/default-policy.yaml` 的 `Path`。
- `default_template_text()` 返回该文件 UTF-8 文本。

`maliang_art.__init__` 的 `__all__` **不**强制扩展 statemachine（保持 v0.1 表面稳定）；用户从 `maliang_art.statemachine` 导入。

### 2.3 数据模型（config.py）

```python
@dataclass(frozen=True)
class StepDecl:
    step_id: str
    action: str
    params: Mapping[str, Any]   # 除 action 外的键的浅拷贝

@dataclass(frozen=True)
class TransitionDecl:
    transition_id: str
    from_states: tuple[str, ...]
    to_state: str
    step_ids: tuple[str, ...]           # 可为空元组
    approver_in: str | None             # require.approverIn，无则 None

@dataclass(frozen=True)
class PolicyModel:
    schema_version: int                 # 恒为 1
    name: str
    states: tuple[str, ...]             # 声明顺序
    transitions: tuple[TransitionDecl, ...]
    steps: Mapping[str, StepDecl]       # step_id -> decl
    policy: Mapping[str, Any]           # 原 policy 节浅拷贝，只读视图约定
    source_path: str | None             # 来源路径，内存构造时为 None

    def transition(self, transition_id: str) -> TransitionDecl:
        """未知 id 抛 PolicyValidationError。"""

    def approver_list(self, path: str) -> list[str]:
        """解析 policy 内 dotted path；不存在或非列表/空/含非 str 抛 PolicyValidationError。"""
```

### 2.4 YAML 加载与校验（config.py）

加载：

1. 读文件：`Path(path).read_text(encoding="utf-8")`。
2. 解析：`yaml.safe_load(text)`（禁止 `yaml.load`）。
3. 结果必须是 `dict`，否则 `PolicyValidationError("policy root must be a mapping")`。

字段级规则（每条失败信息以英文、具体字段名开头，风格对齐现有 MaLiang 错误）：

| # | 规则 | 错误信息（必须包含） |
| --- | --- | --- |
| 1 | 顶层键 ⊆ `{schemaVersion,name,states,transitions,steps,policy}` | `policy fields are invalid` |
| 2 | `schemaVersion` 是 int 且 `== 1`（bool 不算） | `unsupported policy schemaVersion` |
| 3 | `name` 非空 str | `name must be non-empty text` |
| 4 | `states` 是非空 dict；每个 key 匹配 `^[A-Za-z][A-Za-z0-9_-]{0,63}$` | `states must be a non-empty mapping` / `state name is invalid` |
| 5 | 状态值若是 dict，键 ⊆ `{description}`；description 若存在须为 str | `state fields are invalid` |
| 6 | `transitions` 是非空 list | `transitions must be a non-empty list` |
| 7 | 每条 transition 是 dict；键 ⊆ `{id,from,to,steps,require}`；必有 `id,from,to` | `transition fields are invalid` |
| 8 | `id` 匹配 `^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$` 且策略内唯一 | `transition id is invalid` / `transition id is duplicated` |
| 9 | `from` 为非空 list[str]，每项 ∈ states | `transition from must be a non-empty list of known states` |
| 10 | `to` 为 str 且 ∈ states | `transition to must be a known state` |
| 11 | `steps` 若存在：为 list[str]，每项 ∈ steps 映射；省略视作 `[]` | `transition steps are invalid` |
| 12 | `require` 若存在：必须是 dict；键 ⊆ `{approverIn}`；`approverIn` 非空 str | `transition require is invalid` |
| 13 | 若 `approverIn` 存在：值必须是 dotted path（如 `policy.approvers`）；按 `.` 切分后第一段必须是 `policy`，后续段在 `policy` map 中可解析 | `approverIn path is invalid` |
| 14 | 解析出的审批人：非空 `list`，每项非空 `str`；**空列表在 load 时合法**（apply 时再失败） | — |
| 15 | `steps` 若存在：非空 dict；每项为 dict；键 ⊆ `{action}` ∪ 任意额外参数键；`action` 非空 str 且 ∈ registry | `step fields are invalid` / `unknown step action` |
| 16 | `policy` 若存在：必须是 dict | `policy must be a mapping` |

`load_policy(path, *, registry: StepRegistry | None = None)`：

- `registry is None` 时使用 `StepRegistry.with_builtins()`。
- 校验通过返回 `PolicyModel`。
- 文件不存在 / 解析失败：`PolicyValidationError` 带原因（`cannot load policy: ...`）。

JSON Schema `schemas/v1/state-machine-policy.schema.json` 与上述结构对齐（供外部工具/测试对照）；**运行时不强制走 jsonschema**，与现有 `records.py` 手写校验风格一致。

### 2.5 步骤协议与内置步骤（steps.py）

```python
class Step(Protocol):
    action: str
    def run(self, params: Mapping[str, Any], context: Mapping[str, Any]) -> Mapping[str, Any]: ...

class StepRegistry:
    @classmethod
    def with_builtins(cls) -> "StepRegistry": ...
    def register(self, action: str, step: Step) -> None:
        """action 须匹配 ^[A-Za-z][A-Za-z0-9_-]{0,63}$ 且未占用；重复注册同 action 抛 MaLiangError。"""
    def get(self, action: str) -> Step:
        """未知 action 抛 MaLiangError(unknown step action)。"""
    def actions(self) -> tuple[str, ...]: ...
```

**ChromaKeyStep**（`action = "chroma-key"`）：

- 要求 params 含 `key`：`str`，`#RRGGBB` 或 `RRGGBB`（加载后规范为无 `#` 大写六位 hex）。
- `tolerance`：`int`，默认 `0`，范围 `0–255`。
- 非法 params → `MaLiangError`（带字段名）。
- `context["image_path"]` 缺失或 `None` → `{"skipped": True}`。
- 有图时：
  1. `Image.open(path).convert("RGBA")`
  2. 像素距离 `dist² = (r-k_r)²+(g-k_g)²+(b-k_b)² ≤ tolerance²` → `(0,0,0,0)`
  3. 已是 alpha=0 → RGB 清零
  4. 写出：`context["image_out"]` 若存在且为 str 用之，否则覆盖 `image_path`
  5. 返回 `{"changed_pixels": int, "output": str}`

**AlignCanvasStep**（`action = "align-canvas"`）：

- params：`canvas` 必须是长度 2 的 list，元素为 `1..8192` 的 **int**（`type(x) is int`）。
- 无 `image_path` → `{"skipped": True}`。
- 有图时：RGBA 打开，`thumbnail` 等比缩到画布内，新建 `Image.new("RGBA", (w,h), (0,0,0,0))`，居中粘贴。
- 输出路径规则同 chroma-key。
- 返回 `{"size": [w, h], "output": str}`。

步骤**不**调用马良不可变发布，但会按上述路径规则写入图片，可能覆盖输入或中间输出。`apply` 不落盘仅指不发布返回的转换记录，不代表无文件副作用；没有跨步骤事务回滚。

### 2.6 状态机（machine.py）

```python
@dataclass(frozen=True)
class TransitionResult:
    record: dict[str, Any]
    record_id: str

class StateMachine:
    def __init__(self, policy: PolicyModel, registry: StepRegistry | None = None) -> None: ...
    def transitions_from(self, state: str) -> tuple[TransitionDecl, ...]: ...
    def can_apply(self, state: str, transition_id: str) -> bool: ...
    def apply(
        self,
        record: Mapping[str, Any],
        transition_id: str,
        *,
        reviewer: str,
        applied_at: str,
        context: Mapping[str, Any] | None = None,
        clock: Clock | None = None,
    ) -> TransitionResult: ...
```

**注意**：`applied_at` 为**必填关键字参数**（不从 clock 默认生成时钟，避免隐式依赖）；若 `clock` 传入且调用方希望用它，调用方自行 `clock.now_iso8601()` 传入。本实现不把 Clock 接进 apply 默认路径，减少范围。

`apply` 前置校验顺序（短路，第一条失败即抛）：

1. `record` 是 Mapping；含 `schemaVersion`（int==1）、`assetId`（非空 str）、`state`（str）。
2. `reviewer` 非空 str。
3. `applied_at` 非空 str，且 `datetime.fromisoformat` 可解析、`tzinfo is not None`（对齐 pose 卡片时间戳规则）。
4. `transition_id` 存在于 policy；否则 `StateTransitionError("unknown transition")`。
5. `record["state"] ∈ transition.from_states`；否则 `StateTransitionError("transition is not allowed from current state")`。
6. 若 `approver_in` 非 None：`policy.approver_list(path)`；`reviewer not in list` → `StateTransitionError("reviewer is not allowed")`。
   - 空列表 → 同样「not allowed」（fail-closed）。
7. 依次执行 `transition.step_ids`：
   - `step = registry.get(action)`（action 来自 `policy.steps[step_id].action`）
   - `detail = step.run(decl.params, run_context)`；run_context 初始为 context 外层副本。
   - detail 必须是 Mapping，否则抛错；收集时立即深拷贝，后续共享数据变化不得改变证据快照。
   - 具体内置 ChromaKeyStep / AlignCanvasStep 成功后，将 output 作为后续 image_path；不凭自定义步骤同名字段推断图像传递。
   - 配置 image_out 时复用该中间目的文件；未配置时仍可原地处理。此操作不是文件事务。
   - 单步失败包装为 StateTransitionError，不返回成功 TransitionResult；先前步骤已写入图片不自动回滚。
   - 返回记录与输入数据脱离，但不阻止调用方主动修改返回的 dict。

成功返回：

```python
payload_for_id = {
    "assetId": record["assetId"],
    "fromState": record["state"],
    "toState": transition.to_state,
    "transitionId": transition.transition_id,
    "reviewer": reviewer,
    "appliedAt": applied_at,
    "stepResults": step_results,  # list[dict]
}
new_record = {
    "schemaVersion": 1,
    "assetId": record["assetId"],
    "state": transition.to_state,
    "transitionId": transition.transition_id,
    "reviewer": reviewer,
    "appliedAt": applied_at,
    "stepResults": step_results,
}
record_id = stable_id("state-transition", payload_for_id)  # 与 workflow.py 前缀风格一致的 kebab prefix
new_record = {"schemaVersion": 1, "transitionRecordId": record_id, **{k: v for k, v in new_record.items() if k != "schemaVersion"}}
```

`step_results` 每项：

```python
{
    "stepId": decl.step_id,
    "action": decl.action,
    "ok": True,
    "detail": dict(detail),
}
```

`TransitionResult.record` 为上式完整 dict；`TransitionResult.record_id` 即 `transitionRecordId`。

**不调用** `write_immutable_json`。

### 2.7 转换记录辅助（records.py）

仅保留最小函数，避免与 `maliang_art.records` 混淆：

```python
def transition_payload_id(payload: Mapping[str, Any]) -> str:
    return stable_id("state-transition", payload)
```

`machine.py` 使用此函数。

### 2.8 默认模板

文件 `src/maliang_art/statemachine/templates/default-policy.yaml` 内容**必须**为：

```yaml
schemaVersion: 1
name: default-art-pipeline
states:
  draft:
  review:
  done:
  rejected:
transitions:
  - id: submit-for-review
    from: [draft]
    to: review
  - id: approve
    from: [review]
    to: done
    require:
      approverIn: policy.approvers
  - id: reject
    from: [review]
    to: rejected
    require:
      approverIn: policy.approvers
policy:
  approvers: []
```

（`submit-for-review` **不**写 `steps` 键；`steps` 顶层键整体省略。）

打包：模板位于 `src/maliang_art/statemachine/templates/`，由 hatchling 按
Python 包内数据自动打进 wheel（与 `schemas/` 不同——schemas 在包外，故仍需
`force-include`）。**不要**对 templates 再写 `force-include`，否则会与自动
包含冲突导致 wheel 双写同一路径。

```toml
[tool.hatch.build.targets.wheel.force-include]
"schemas" = "maliang_art/schemas"
```

### 2.9 CLI（cli.py 追加）

```text
maliang-art flow validate <path>
  - load_policy(path)；成功 stdout: "valid policy: {name}"；exit 0
  - 失败：parser.error 或现有 main 错误路径，exit 非 0

maliang-art flow show-default-template
  - stdout 写出 default_template_text()；exit 0

maliang-art flow transitions <path> --state <state>
  - 加载策略；打印每行一条：
    "{transition_id} -> {to_state}"
  - 仅打印 from 含该 state 的转换
  - 若该 state 不在 states：报错 exit 非 0
  - 无匹配转换：不打印行，exit 0
```

`build_parser()` 增加 `flow` 组与三个子命令；handler 命名对齐现有 `_pose_*`、`_records_*` 风格：`_flow_validate`、`_flow_show_default_template`、`_flow_transitions`。

### 2.10 依赖与打包（pyproject.toml）

```toml
dependencies = ["Pillow>=10.4,<13", "PyYAML>=6,<7"]
```

test extra 不变（pytest、build、jsonschema 仍为测试用）。

README.md / README.zh-CN.md 各增加一小节「State machine core」/「状态机内核」：

- 一句定位
- CLI 三行示例
- Python 导入行：`from maliang_art.statemachine import load_policy, StateMachine`

### 2.11 测试契约（T6）

| 文件 | 必须覆盖 |
| --- | --- |
| `test_statemachine_config.py` | 模板可加载；§2.4 规则 1–15 各至少一例失败且信息含关键字；空 approvers 加载成功；dotted path 非 `policy.` 开头失败 |
| `test_statemachine_steps.py` | `with_builtins` 含 `chroma-key`/`align-canvas`；无 image_path skipped；临时 PNG 去幕后角落 alpha=0；canvas 贴合尺寸正确；非法 key/canvas 报错；重复 register 报错 |
| `test_statemachine_machine.py` | draft→review 成功且 record 字段/stable id 符合 §2.6；非 draft 拒绝；未知转换拒绝；approve 在空 approvers 拒绝；填入 approvers 后成功；step 失败不返回成功；steps 顺序体现在 stepResults |
| `test_statemachine_cli.py` | validate 模板 exit 0 且含 name；validate 非法文件非 0；show-default-template 含 `default-art-pipeline`；transitions `--state draft` 含 `submit-for-review`；未知 state 非 0 |

测试 fixture 一律写在 `tmp_path` 下的 YAML 字符串，**不**引用任何外部游戏资产。

### 2.12 错误与安全边界

- 策略路径由调用方传入，本功能**不做** MaLiang `contained_path` 约束（与 `pose.render` 读 `--spec` 一致：信任调用方给出的路径）。
- YAML 只用 `safe_load`。
- 不执行策略里的任意代码；步骤只能是 registry 里已注册的 handler。
- `appliedAt` 不自动写入凭证；文档提示调用方勿在 `context` 里放密钥（与 SECURITY.md 一致）。

## [S3] 范围外

- 迁移 tactics 管线、系列预算、合同/job、provenance、Godot 检查。
- `apply` 的 CLI 封装与记录目录约定。
- 完整图像 QA 门禁（四角、150px 可读等）。
- 修改既有 JSON schema 或 v0.1 API 行为。
- YAML 化现有 pose/review/workflow 记录。
- 图形化编辑器。
- 在 `maliang_art.__init__` 顶层强制 re-export statemachine。

## Tasks

- [x] T1: 实现 `config.py` + `PolicyModel` + `schemas/v1/state-machine-policy.schema.json` — 验收：§2.4 全表可测；模板可 `load_policy`；非法规则错误信息含指定关键字。 (covers: §2.3–2.4)
- [x] T2: 实现 `steps.py`（Protocol、Registry、两个内置步骤）— 验收：§2.5 行为与返回值形状。 (covers: §2.5)
- [x] T3: 实现 `machine.py` + `records.transition_payload_id` — 验收：§2.6 校验顺序、`TransitionResult`、stable id；不发布转换记录（内置步骤仍可写图片，无事务回滚）。 (covers: §2.6–2.7; depends: T1, T2)
- [x] T4: 默认模板 + `builtin_template_path` / `default_template_text` + 包数据 — 验收：内容与 §2.8 一致；空 approvers 时 apply 拒绝。 (covers: §2.8; depends: T1)
- [x] T5: CLI 三个 flow 命令 — 验收：§2.9 输出与退出码。 (covers: §2.9; depends: T1, T4)
- [x] T6: 测试套件 — 验收：§2.11 覆盖；全量 pytest 通过（允许 Windows symlink skip）。 (covers: §2.11; depends: T1–T5)
- [x] T7: `pyproject.toml`（PyYAML）+ README 双语节 + wheel 构建 — 验收：wheel 含模板；build 成功。 (covers: §2.2, §2.10; depends: T1–T5)
