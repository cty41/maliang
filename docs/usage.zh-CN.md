# 马良使用参考

[English](usage.md) | [简体中文](usage.zh-CN.md) | [快速入门](../README.zh-CN.md)

本页是库和 CLI 的参考：版本、命令、输出语义和安全边界。第一次接触请先看
[入门教程](getting-started.zh-CN.md)和[核心概念](concepts.zh-CN.md)；接入 Agent 见
[Agent 接入](agent-setup.zh-CN.md)。[art-pilot 示例](../examples/art-pilot/README.md) 及其
[运行手册](../examples/art-pilot/docs/runbook.md) 负责真实项目流程；
离线练习不是服务调用或人工批准的证据。

## 安装与版本

需要 **Python 3.10+**。发行名为 **`maliang-game-art`**，导入名为
**`maliang_art`**，命令行为 **`maliang-art`**。PyPI 上已有的 `maliang`
是无关项目，不是本工具包。Pillow 支持范围为 `>=10.4,<13`。

要使用当前功能和仓库示例，请按[快速入门](../README.zh-CN.md#快速开始)
中的单一源码路线安装。本指南命令均在激活该环境后，从仓库根目录运行。
安装依赖可能联网；设计编译和演示本身不联网。

已发布的 v0.1.0 tag 提供确定性 JSON 编码与稳定 ID、路径约束、避免覆盖冲突的
不可变发布、合成姿态草图渲染、素材绑定、审核规则校验，以及不绑定服务商的
调用（invocation）、交付（delivery）和失败（failure）记录。
重点是安全记录，而不是生成素材。只有在特意复现旧版本时，才使用以下安装命令：

```console
python -m pip install "maliang-game-art @ git+https://github.com/cty41/maliang.git@v0.1.0"
```

**不要用该旧版安装来运行本指南的当前源码示例。** 下面的 `design` 和 `flow`
是当前源码功能，不属于 v0.1.0；介绍这些功能不表示已有新发行版。
下文的预览尺寸规则也针对当前源码。

仓库相对链接指向的指南和 [Agent skill](../skills/maliang-art/SKILL.md) 需要
源码 checkout。wheel 不携带它们；sdist 不携带 skill 和运行手册。
加载或安装 skill 的方式由宿主决定：链接不会自动安装，也不会授予生图权限。
设计规格记录决策和待办，不是可执行 API。文档导航见 [llms.txt](../llms.txt)，
开发说明见 [CONTRIBUTING.md](../CONTRIBUTING.md) 和 [AGENTS.md](../AGENTS.md)。

## Agent 与 LLM 配置

**马良本身没有模型服务或 API key 配置。** 模型、图像工具和登录都归宿主管理。
分步检查清单（checkout 路径、解释器、资产根目录、工具核对和审核门禁）见
[Agent 接入](agent-setup.zh-CN.md)。

## 离线练习与真实项目

源码安装后，[快速入门](../README.zh-CN.md#快速开始) 使用
`examples/art-pilot/scripts/offline_demo.py`，在已被 Git 忽略的
`work/art-pilot/` 下创建新项目。成功时退出码为 0，打印 `synthetic-adopted`。
已有目录（包括空目录）会被拒绝；再运行时请换新后缀。
其中的合成图和模拟人类决定的测试记录**不是真实的服务调用或人工批准**。

包内 `maliang-art` / `python -m maliang_art` CLI **没有 `production` 子命令**。
仓库示例另提供：

```console
python -I examples/art-pilot/scripts/production.py --help
```

它支持准备（`prepare`）、完成/失败（`complete`/`fail`）、导入（`import`）、
派生（`derive`）、技术审核（`technical`）、人工审核（`review`）和采用（`adopt`）。
全局 `--project` 放在子命令之前；输入路径相对该项目根目录。
产物说明和真实项目模板以[运行手册](../examples/art-pilot/docs/runbook.md) 为准，
不要把合成练习当成生产教程。实际生成/编辑仍由外部宿主执行。
自动 Codex provider 桥尚未交付，合成人审测试记录也不是实际批准。

## 设计校验与编译

可以先校验和编译仓库内的样例，无需自己编写 JSON：

```console
python -m maliang_art design validate --contract examples/art-pilot/characters/falcon-idle/family-contract.json --draft examples/art-pilot/characters/falcon-idle/draft-example.json
python -m maliang_art design compile --contract examples/art-pilot/characters/falcon-idle/family-contract.json --draft examples/art-pilot/characters/falcon-idle/draft-example.json --output-dir work/art-pilot/readme-design
```

两条命令成功时退出码均为 0。compile 打印含 `"packet": "design.json"` 和
`"guides": []` 的清单。产物位于已忽略的 `work/art-pilot/`，是执行简报，
而不是生成的图片或已批准角色。修改输入时使用新的输出目录。

自己的设计应按以下 schema 提供明确的合同与草案 JSON：
[art-family-contract.schema.json](../schemas/v1/art-family-contract.schema.json) 和
[sprite-slice-draft.schema.json](../schemas/v1/sprite-slice-draft.schema.json)。

```console
maliang-art design validate --contract family.json --draft slice.json
maliang-art design compile --contract family.json --draft slice.json --output-dir work/design-v1
```

`validate` 成功返回 JSON `{ "valid": true, "diagnostics": [] }`，退出码为 0。
无效/不完整记录、文件缺失或 JSON 格式错误返回退出码 1，以及含 `path`、
`code`、`message` 的 JSON 诊断；不会猜测缺失的美术决定。
`compile` 使用相同的视觉需求校验，发布 `design.json`，包含完整 prompt、
视图/状态任务、继承后的目标尺寸、有序参考职责/哈希、待执行验收项和语境板布局。

默认不渲染图片：`imageInputs` 只包含声明的参考图，并保持原有顺序。
家族 `variants` 和部件数字坐标不必填；拓扑部件可以用 `id` 和可选
`description` 描述物种结构。形体意图须由家族允许，而非由调试渲染器决定。
支持的相机模式各自对应固定的显式 profile：`isometric`（North=UL、South=DR、
East=UL+flipX、West=DR+flipX）、`side`（East=R、West=R+flipX）、`top-down`
（North=U、South=D、East=R、West=R+flipX）和 `front`（South=F）。不用的方向写
`none`，其语境板格子标为 `not-applicable`。任务只能使用该模式的原生视角；含
`flipX` 的 profile 须由项目接受镜像派生方向。提示词包含模式与所需视角的白话说明
`cameraGuide`。
编译准备的是执行简报，不是批准设计。

色板和艺术判断仍待人工审核；语境板只有布局，不代表未来候选图片。
参考路径、哈希和借用职责**仅作声明**：本命令不读取/核验或复制参考图。
空参考允许从零探索。后端参数和参考图是否实际提交，须由执行适配器绑定核验。
design 命令不会调用网络/生图后端、作出人工批准或采用候选。

### 可选的调试几何图

现有 capsule/ball 渲染器只通过可选调试模式调用：

```console
maliang-art design compile --contract family.json --draft slice.json --output-dir work/debug-v1 --debug-geometry
```

此模式需要明确的数字 variants 和部件 anchor/size，校验布局边界，并额外发布
`guides/*.png`。产物标记为 **debug-layout**、**unapproved**、
**not-generation-input**，绝不进入 `imageInputs`。
椭圆占位和屏幕方向三角只展示代码布局，不能证明物种、角色剪影、相机投影、
动作姿态、画风、核心量测或跨视图/状态一致性。其坐标也不会成为生图指令。
视觉探索无需先选定或批准调试图。

### 输出与重复运行

成功输出 JSON 文件清单；发布/路径错误非零退出并写入 stderr。
相同输入重复执行不会改变已有字节；同一路径的不同字节被拒绝。
不可变发布以单个文件为单位，**不是多文件事务**：调试运行中断/失败可能留下
导引图，相同输入重跑可继续完成。修改简报或调试模式时应使用新的输出目录。
演示会拒绝任何已有项目目录，而编译可在原输出目录中继续完成相同的工作；两者不同。

## 姿态、记录和审核 CLI

除仓库内的 poet-cast 示例外，以下命令使用自行提供的记录文件。
选择姿态的命令写在一行，便于在 Windows PowerShell 中使用。

```console
maliang-art pose render-options --spec draft.json --output board.png --preview-dir previews --preview-size 160x90
maliang-art pose select-option --spec draft.json --option-id arc-a --output-card card.json --reviewer art-director --reason "Readable silhouette" --rejected-reason "arc-b=Weaker contact" --selected-at 2026-01-01T12:00:00Z
maliang-art records validate draft.json --schema pose-draft
maliang-art records validate invocation.json --schema invocation
maliang-art records validate delivery.json --schema delivery --root . --verify
maliang-art records validate examples/poet-cast/draft.json --schema pose-draft
maliang-art records check path/to/record-tree
maliang-art review validate rule review-rule.json --authority-reviewer art-director
```

姿态画布由记录定义。当前源码中，`render_preview` 和 CLI 默认预览为画布半尺寸；
超过 **4,194,304 像素预算**时等比缩小并向下取整，保留完整画布、不裁切。
256×256 画布默认仍为 128×128。显式 `--preview-size WIDTHxHEIGHT` 超预算会被拒绝。
方案板和预览图的内存分配均有上限，防止过大的记录耗尽内存。

`pose select-option` 必须显式填写 reviewer，但不绑定特定人员。
每个未选方案都需要一个原因。已有输出不可变：相同内容重复执行成功，
同一路径的不同内容会失败。

## Python API

```python
from maliang_art import canonical_bytes, stable_id, write_immutable_json
from maliang_art.records import validate_artifact
from maliang_art.workflow import validate_invocation, validate_delivery, validate_failure
```

纯审核 API 位于 `maliang_art.review`；结构化接口位于 `maliang_art.ports`，
JSON/Pillow 适配器位于 `maliang_art.adapters`。
带版本的 JSON Schema 随包提供，位于 `schemas/v1/`。

### 原画与认人特征

原画可以和游戏内资产用不同风格，例如水墨原画配胶囊小人。两者之间由四种记录连接：
`concept-style-guide`、`character-concept`、`identity-markers`，以及
`derived-usage`（半身头像或宣传图）。`records check` 会校验这些记录，并报告跨记录问题：
状态为 frozen 的认人特征必须引用已审批的原画；半身头像要求原画已审批且有图，
裁切框不能超出原画尺寸。

`concept review <记录目录> --concept <id>` 会输出一份 Markdown 确认单，列出图片、
每条人工风格检查项、每个认人特征，以及结论选项。加 `--format questions` 时输出同样内容的
AskQuestion JSON：风格检查和认人特征是多选题“哪些不满足”，末尾是“全部满足”和“有其他问题”；
结论是单选（通过、不通过、需修改）。带 `forms` 的特征只在对应形态出现。`concept.decision_from_answers`
负责映射答案，包括 `other` 下的自填文字：勾了不满足项或写了其他问题却选通过会报错；不通过和“需修改”
都按 rejected 记录，不满足项和自填文字写入备注。传入题目时，题目里没有的选项 id 会报错。`concept approve <记录.json> --decision approved|rejected`
用来记录结论：可以用 `--image` 和 `--root` 绑定图片；审批人自动取 git 的 `user.name` 和 `user.email`，
取不到时用操作系统登录名，来源记录在 `reviewerSource` 字段里。agent 只有在用户已经在会话里
明确回复确认单之后，才能执行 approve。

```python
from maliang_art.concept import draft_identity_findings, markers_to_identity, palette_findings
from maliang_art.concept import reading_to_markers, reading_to_style_rules
```

`markers_to_identity` 用每个特征的 `capsuleTranslation` 生成 sprite-slice draft 的
`identity` 块；`draft_identity_findings` 报告 draft 缺少的必须保留特征；
`palette_findings` 把调用方提供的不透明像素颜色计数与特征色板比较。这些函数都不生图，
也不判断“像不像”。合成示例见 `examples/art-pilot/characters/concept-demo`。

`art-reading` 记录从一张已绑定哈希的原图里读出了什么：身份特征、配色角色，以及风格条目
（剪影、比例、描线、明暗光照、材质、构图、气质），每条标明是 `host-model-observed`（宿主模型观察）
还是 `human-confirmed`（人工确认）。标为 confirmed 的 reading 要求身份特征全部经人工确认；
外部参考必须是 `style-only`，不能带身份特征。带 `readingIds` 的 frozen 特征清单只能引用已确认的
身份类 reading，角色必须一致；自有原画的 reading 还必须对应清单引用的、已审批的那张原画图片。
`reading_to_markers` 起草特征清单，`capsuleTranslation` 仍由人填写；冻结时会拒绝留着占位文字的清单，
并要求至少一条必须保留的特征；
`reading_to_style_rules` 起草由人工检查的风格规则。看图由宿主模型完成，马良只做校验和绑定。

### 美术方向问询

需求宽泛时，用 `intake start|next|answer|draft` 按项目自己的问询目录（`art-direction-catalog` schema）
逐轮提问。`next` 输出下一轮题目，格式可直接交给提问工具：题目按“后改代价从高到低”排序，
只包含前置条件已经满足的维度，每个选项都写明后果和风险。`answer` 记录选项或文字、来源
（`catalog-option`、`ai-suggested-option`、`user-text` 或 `ai-inferred-confirmed`），
以及当时实际展示的选项。固定维度拒绝 AI 推荐的选项；选到终止项时问询结束。闸门题（`gate: true`，
即含终止项或后续题目依赖它的题）拒绝纯 `user-text`：要把用户的话对应到某个选项，经确认后记为
`ai-inferred-confirmed`。`draft`
把已选项映射成风格规则和家族契约字段，并列出未决维度，不填默认值。马良不调用大模型，
提问由宿主 agent 完成。示例见 `examples/art-pilot/intake/art-direction-catalog.json`。

## 状态机

`maliang_art.statemachine` 加载 YAML 策略，描述状态、转换、可选步骤及项目策略值，
然后在内存中计算转换结果。`StateMachine.apply` 返回转换记录，**不把该记录
发布到磁盘**；内置图像步骤仍可能写入或覆盖调用方提供的图片路径。
后续步骤失败不会回滚之前的图片写入。
默认模板为 `draft → review → done/rejected`，审批人列表默认为空，由项目自行填写。

```console
maliang-art flow show-default-template
maliang-art flow validate path/to/policy.yaml
maliang-art flow transitions path/to/policy.yaml --state draft
```

```python
from maliang_art.statemachine import load_policy, StateMachine
```

项目提供 YAML 策略和审核人信息；库不写死项目身份、画布尺寸或审批人。
策略 schema 使用稳定标识 `urn:maliang:schema:state-machine-policy:v1`，
源码文件是 [state-machine-policy.schema.json](../schemas/v1/state-machine-policy.schema.json)，
不是 v0.1.0 tag 中的资源。

## 安全与范围

文件系统威胁模型及漏洞私密报告方式见 [SECURITY.md](../SECURITY.md)。
使用调用方有权限控制、并禁止不可信人员写入的根目录。如果攻击者能在读写期间
重命名或改写目录，通用路径检查无法消除时序竞争风险。
不要在持久保存的调用 `request`、交付 `metadata` 或失败 `details` 中写入秘密；
适配器必须先移除这些信息。

Git 精确忽略本机锁 `examples/art-pilot/maliang.lock.json`、生产记录
`examples/art-pilot/production/` 和临时输出 `work/art-pilot/`。
忽略规则不会删除已跟踪文件，也不能替代发布前的隐私审查。

- 记录内路径是仓库相对 POSIX 路径。
- SHA-256 字段绑定文件字节，不证明可信度、作者身份或使用许可。
- 发布使用临时文件加“仅在目标不存在时创建”的硬链接，使并发发布相同内容安全，
  内容冲突时拒绝发布。硬链接拒绝、清理等待时限，以及报错后仍可能保留已创建目标
  的情况，详见安全政策。
- 行为测试使用合成数据。另有独立完整性/来源测试核对带署名的
  `examples/poet-cast/` 教程及其六个由哈希绑定的来源项目文件。
  这些检查不证明真实生图或批准。

代码与 Python 发行包采用 MIT。仅存在于仓库的 `examples/poet-cast/` 教程
不会打入 sdist，仍采用 CC BY 4.0；见其
[ATTRIBUTION.md](../examples/poet-cast/ATTRIBUTION.md)、
[assets.json](../examples/poet-cast/assets.json)、[REUSE.toml](../REUSE.toml) 和
[CC-BY-4.0.txt](../LICENSES/CC-BY-4.0.txt)。项目来源另见
[EXTRACTED_FROM.md](../EXTRACTED_FROM.md)。
