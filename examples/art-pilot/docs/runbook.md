# Runbook — 冻结请求与精确候选门禁

所有命令从马良仓库根目录执行，`python` 指当前环境的解释器；不依赖特定盘符、用户名或外部源码。下列生产命令是操作模板，不是声称已完成的真实调用。先准备自己的合法输入，使用全新 attempt 和输出路径；不要修改精选图片或补写历史回执。

## 0. 环境与可复现范围

```text
python -m pip install ".[test]"
python -m pytest tests examples/art-pilot/tests
python -m build
python examples/art-pilot/scripts/smoke_wheel.py --wheel dist/maliang_game_art-0.1.0-py3-none-any.whl
```

默认 build 从 sdist 构建 wheel。smoke 使用 `sys.executable` 创建临时环境，按平台选择 `Scripts/python.exe` 或 `bin/python`，安装 wheel 并验证包内全部资源；不读取本机历史 lock、不导入工作树源码。传 `--wheelhouse <已有目录>` 可禁止索引访问。未指定时安装依赖可能联网下载，不涉及上传。

如需长期的示例专用环境，可先准备依赖 wheelhouse，再运行精确源码/wheel核对工具。以下路径相对仓库根目录，`.wheelhouse` 是自行准备的本机目录：

```text
python examples/art-pilot/scripts/lock_environment.py --source-repo . --wheel dist/maliang_game_art-0.1.0-py3-none-any.whl --wheelhouse .wheelhouse --dry-run
python examples/art-pilot/scripts/lock_environment.py --source-repo . --wheel dist/maliang_game_art-0.1.0-py3-none-any.whl --wheelhouse .wheelhouse
```

dry-run 只核对并打印，不创建环境、安装或写锁。实际运行生成示例本机 `.venv` 和 `maliang.lock.json`，均不要提交。工具复用已有环境，但仍核对每个安装资源；陈旧 wheel 默认拒绝。`--record-existing-test-install` 只能记录已有测试安装差异，不能认证生产就绪。锁记录观察时的提交/dirty状态与真实字节，不伪造历史构建时刻。

sdist 仅包含 art-pilot 脚本、合成测试、README，不包含本手册、真实图片、生产历史、本机锁或 policy。真实资产 hash / 来源审计属于仓库检查；所有行为回归使用临时合成 fixture。

## 0.1 一条命令跑通合成离线闭环

前提：按上节安装当前源码及依赖，使用该环境的 Python；执行练习本身不联网、
不调用生图服务，也不需要图片、登录或外部凭证。从仓库根目录复制运行：

```text
python -I examples/art-pilot/scripts/offline_demo.py --project work/art-pilot/synthetic-demo-001
```

脚本在单独的 Git-ignored 项目目录中准备最小合同/Draft、编译设计、调用现有
production CLI 的 prepare，再用 Pillow 创建 16×16 合成色块并绑定模拟 receipt，
执行 technical、synthetic human fixture 和 adopt。它不从测试模块导入 fixture，
也不读取或修改精选图片。首次成功退出 0，stdout 输出 JSON：`status` 为
`synthetic-adopted`，`synthetic` 为 true，`realProviderExecution` 和
`realHumanApproval` 均为 false，`project` 为实际绝对路径。

输出目录包含：

- `contract.json`、`draft.json`、`design.json`、`parameters.json`：可检查的执行输入；无参考图或 debug 导引。
- `synthetic-image.png`、`synthetic-receipt.json`、`synthetic-human.json`：明确标记的测试素材/回执/人审 fixture。
- `production/attempts/synthetic-001/`、`production/events/`、`production/technical/`：现有门禁生成的记录。
- `production/current/synthetic-demo.json`：仅合成项目内的 adopted 投影。
- `synthetic-demo.json`、`demo-result.json`：合成边界声明和产物路径清单。

**这不是实际生图、艺术通过或人类批准。** `actorType: human` 和 pass 值只为测试
既有审核协议，reviewer 明确为 `synthetic-fixture-human`，statement 明确无人审图；
不要把这些 fixture 复制进真实项目或当作真实人的决定。色块不需要满足鸟类美术要求，
其艺术项的 pass 是模拟数据，不是工具作出的视觉判断。

目标路径必须不存在（即使空目录也拒绝）。重复运行非零退出且不覆盖已有文件；
要再练习请改为新的 `work/art-pilot/synthetic-demo-002` 等路径。运行中断可能保留
部分记录；同样用新目录重跑，不删除或覆盖旧证据。下面第 1–4 节是**真实项目的
操作模板**，仍须真实输入、执行证据和人类决定，不得使用上面的合成批准替代。

## 1. 准备权威输入

在自己的项目目录准备 `family-contract.json`、`draft.json`、`backend-params.json`，使用已安装库 `python -m maliang_art design compile --help` 查看编译参数，输出全新的 `packet/design.json`。不得把任意文字 prompt 当作 compiled prompt。

所有 production source 参数相对 `--project` 根目录，不是相对 design.json；绝对路径、`..` 越界被拒绝。以下以自行准备的 `work/art-pilot` 为项目根目录，不假定该目录或文件已经存在。

如使用精选样例，仓库参考路径为 `characters/shared/poet-idle-dr-style.png`，最终游隼为 `characters/falcon-idle/raw/codex-idle.png`（相对 `examples/art-pilot`）。先按资产清单核对当前派生哈希，并将合法参考复制到自己的项目；Draft 必须填写实际项目相对路径和当前字节哈希，不复用压缩前引用。参考的职责、允许借用与禁止借用需明确。

## 2. prepare / acceptance

```text
python -I examples/art-pilot/scripts/production.py --project work/art-pilot prepare --attempt bird-001 --contract family-contract.json --draft draft.json --design packet/design.json --parameters backend-params.json --provider actual-provider --model unknown
python -I examples/art-pilot/scripts/production.py --project work/art-pilot acceptance --contract family-contract.json --draft draft.json --design packet/design.json
```

prepare 重新编译合同 / Draft 并核对 prompt、任务、输入顺序/职责、acceptance、designId、targets；冻结输入图及权威源字节。未知 method、重复 ID、缺身份项报错。`alpha-bounds` 对应 automatic，human 项必须由真实人类决定。没有手填 required 或 approve 开关。

编辑仍须提供编辑任务自己的合同 / Draft / design，加 `--parent <精确父attempt>` 与 `--instruction <明确修改>`；父图作为第一张 edit-source，之后保持参考顺序。编辑记录不冒称原始生成。

## 3. 外部执行与完成

库和脚本不自动调用图像服务。执行器必须读取 `production/attempts/<id>/prepared.json`，真实提交冻结 prompt、参数和输入图，并保留可核验工具记录。Codex provider 执行桥仍未实现，登录不是离线回归先决条件。

成功回执必须包含：`preparedEventId`（原样）、`invocation`（完整对象，非字符串）、`outcome: "success"`、真实 `artifactSha256`、真实 `executionEvidence`。

```text
python -I examples/art-pilot/scripts/production.py --project work/art-pilot complete --attempt bird-001 --receipt receipt.json --image output.png
```

失败使用 `fail --attempt bird-001 --category timeout --message <真实错误摘要>`，不能用失败调用编造成功图。complete 精确匹配准备事件、完整 invocation 与输出哈希，但手拼 receipt 本身不证明真实执行。

已有外部图片使用 `import --attempt <新id> --contract ... --draft ... --design ... --image ... --provenance <真实来源> [--historical]`；不伪造 invocation、旧时间或批准。core 可能保存原始字节为 `source.bin`，这不改变图像内容，但这类生产记录不属于公开精选素材或发行包。

V03 旧回执不可信：实际未提交图片参考、实际 prompt 与冻结包不一致，不能作为可执行模板。V04 / Codex 外部试作仅保留可证明事实和用户反馈，不补造完整链。展示偏好不等于新压缩派生已满足生产采用要求。

## 4. 技术、人审与采用

```text
python -I examples/art-pilot/scripts/production.py --project work/art-pilot technical --attempt bird-001
python -I examples/art-pilot/scripts/production.py --project work/art-pilot review --attempt bird-001 --decision-file human-decision.json
```

technical 解码实际图像，运行每个必需自动谓词并绑定精确候选；尺寸、非空 alpha、边界通过不能证明艺术质量。derive 仅支持 copy / flip-x，并绑定父候选；不是原生视角生图或隐式换手认可。

人审 decision-file 必须由真实决定产生：`actorType: "human"`、真实 reviewer、候选完整 eventId/attemptId/artifact、`identityChecklist: ["identity"]`、非空真实 statement、真实带时区 decidedAt、adopt/reject/pending，以及全部必需 human 项的 pass/fail/pending/unsupported。Agent 不得为了推进流程编写真实 human pass。

采用命令模板（尖括号替换为实际事件路径，不要原样执行）：

```text
python -I examples/art-pilot/scripts/production.py --project work/art-pilot adopt --attempt bird-001 --asset bird-idle --review production/events/<human-event>.json --result production/events/<automatic-event>.json
```

每个必需 automatic 项需一个 `--result`。缺项、失败、pending/unsupported、旧人审或技术结果绑定其他候选均拒绝。满足完整门禁可直接采用，无需再次生成。事件不可覆盖，current projection 原子更新。

## 验证边界

合成测试确认行为门禁，不确认真实参考图被服务接收、不确认几何/视觉质量、不代替真实人类采用。图片为用户自有 CC-BY-4.0 资产；库、代码和文档为 MIT。授权公开、用户偏好与正式 delivery 分开记录。没有 push、上传、PR 或 merge 隐含在这些命令中。
