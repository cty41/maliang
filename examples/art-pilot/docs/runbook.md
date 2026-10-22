# Runbook — 冻结请求与精确候选门禁

[English](runbook.en.md) | [简体中文](runbook.md)

本手册与英文配对是生产流程的权威文档。所有命令从马良仓库根目录执行，`python` 指当前环境的解释器；不依赖特定盘符、用户名或外部源码。下列生产命令是操作模板，不是声称已完成的真实调用。先准备自己的合法输入，使用全新 attempt 和输出路径；不要修改精选图片或补写历史回执。

## 0. 环境与可复现范围

操作说明仅提供 Windows PowerShell 路线，本机使用验证环境为 Windows 11 x64。首次使用先按 [开发环境说明](../../../CONTRIBUTING.md#development-environment) 创建并激活环境。

CI 配置为 GitHub 托管 Windows Server x64（`windows-2025`），不是 Windows 11；本机通过不等于托管 CI 通过，未推送的工作流修改没有新的托管运行结果。此范围不否定历史跨平台 CI 结果。

```powershell
python -m pip install ".[test]"
python -m pytest tests examples/art-pilot/tests
python -m build
python examples/art-pilot/scripts/smoke_wheel.py --wheel dist/maliang_game_art-0.1.0-py3-none-any.whl
```

默认 build 从 sdist 构建 wheel。smoke 使用 `sys.executable` 创建临时环境，在 Windows 选择 `Scripts/python.exe`，安装 wheel 并验证包内全部资源；不读取本机历史 lock、不导入工作树源码。脚本仍保留其他平台选择 `bin/python` 的便携分支；这是实现事实，不是本轮提供或验证的 Unix 操作路线。传 `--wheelhouse <已有目录>` 可禁止索引访问。未指定时安装依赖可能联网下载，不涉及上传。

如需长期的示例专用环境，可先准备依赖 wheelhouse，再运行精确源码/wheel核对工具。以下路径相对仓库根目录，`.wheelhouse` 是自行准备的本机目录：

```powershell
python examples/art-pilot/scripts/lock_environment.py --source-repo . --wheel dist/maliang_game_art-0.1.0-py3-none-any.whl --wheelhouse .wheelhouse --dry-run
python examples/art-pilot/scripts/lock_environment.py --source-repo . --wheel dist/maliang_game_art-0.1.0-py3-none-any.whl --wheelhouse .wheelhouse
```

dry-run 只核对并打印，不创建环境、安装或写锁。实际运行生成示例本机 `.venv` 和 `maliang.lock.json`，均不要提交。工具复用已有环境，但仍核对每个安装资源；陈旧 wheel 默认拒绝。`--record-existing-test-install` 只能记录已有测试安装差异，不能认证生产就绪。锁记录观察时的提交/dirty状态与真实字节，不伪造历史构建时刻。

sdist 仅包含 art-pilot 脚本、合成测试、中文 README.md，不包含英文 README.en.md、双语运行手册、真实图片、生产历史、本机锁或 policy。真实资产 hash / 来源审计属于仓库检查；所有行为回归使用临时合成 fixture。

## 0.0 美术方向问询（需求宽泛时）

需求只有一句话，比如“可爱点的动物战棋”时，先做问询，不要直接编写 draft。

1. agent 先用一两句话复述自己的理解，然后运行 `python -m maliang_art intake start <目录> <intake.json> --request "<用户原话>"`。示例目录是 `intake/art-direction-catalog.json`。
2. 反复运行 `intake next <目录> <intake.json>`，用提问工具把返回的题目发给用户。用户每回答一题，就运行一次 `intake answer`，直到结果为 done。
3. 选到终止项（比如 3D）时，问询会停下并给出原因，不再继续。
4. 最后运行 `intake draft`，得到风格规则和家族契约的字段草稿，以及还没决定的维度（open）。之后再进入第 1 节，或者进入 0.2 节的原画流程。

问询目录是项目自己的数据，可以按需要增删。agent 只能在标为 suggestable 的维度上追加推荐选项，并且要标明这是 AI 推荐；从用户原话里预填的答案，必须先请用户确认；不能替用户作答。

## 0.1 一条命令跑通合成离线闭环

前提：按上节安装当前源码及依赖，使用该环境的 Python；执行练习本身不联网、
不调用生图服务，也不需要图片、登录或外部凭证。从仓库根目录复制运行：

```powershell
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

## 0.2 原画先行（可选）

原画和游戏内资产风格差异较大时，比如水墨原画配胶囊小人，先走原画轨道：

1. 写 `concept-style-guide`，再为每个形态写一份 `character-concept`，初始状态为 pending、image 为 null。
2. 用户单独授权后生成原画。运行 `python -m maliang_art concept review <记录目录> --concept <id> --format questions` 输出三道确认题（风格检查多选、认人特征多选、结论单选），agent 交给提问工具让用户作答；没有提问工具时，去掉 `--format questions` 输出 Markdown 确认单，原样贴到会话里。认人特征按 `forms` 只列当前形态适用的项。结论选“需修改”时按 rejected 记录，不满足项写入 `--note`。用户作答之后，agent 才能运行 `python -m maliang_art concept approve <concept.json> --decision approved --image <图片路径> --root <项目根>`。审批人自动取 git 的 user.name 和 user.email，取不到时用操作系统登录名，来源记录在 `reviewerSource` 字段里。用户没有明确回复时，不执行 approve。
3. 从定稿原画提炼 `identity-markers`，冻结为 frozen；每个特征都要写明 `capsuleTranslation`。提炼时先写一份 `art-reading`：绑定原图路径和哈希，宿主模型看出来的条目记为 `host-model-observed`，用户确认过的才改为 `human-confirmed`。身份类条目全部经用户确认后，reading 才能标为 confirmed，再用 `reading_to_markers` 起草特征清单，并在 `readingIds` 里引用它。外部参考图（照片、他人作品截图）只能写成 `style-only` 的 reading，只借风格，不借身份。
4. 第 1 节的 draft 中，`identity` 由特征清单生成。不要把原画当参考图输入胶囊资产。
5. 半身头像和宣传图写成 `derived-usage`，同样需要人工审批。

用 `python -m maliang_art records check <记录目录>` 检查记录。合成示例 `characters/concept-demo`（示例苍鹭，两种形态）如实停在“等待原画人工定稿”这一步。

## 1. 准备权威输入

在自己的项目目录准备 `family-contract.json`、`draft.json`、`backend-params.json`，使用已安装库 `python -m maliang_art design compile --help` 查看编译参数，输出全新的 `packet/design.json`。不得把任意文字 prompt 当作 compiled prompt。

所有 production source 参数相对 `--project` 根目录，不是相对 design.json；绝对路径、`..` 越界被拒绝。以下以自行准备的 `work/art-pilot` 为项目根目录，不假定该目录或文件已经存在。

如使用精选样例，仓库参考路径为 `characters/shared/poet-idle-dr-style.png`，最终游隼为 `characters/falcon-idle/raw/codex-idle.png`（相对 `examples/art-pilot`）。先按资产清单核对当前派生哈希，并将合法参考复制到自己的项目；Draft 必须填写实际项目相对路径和当前字节哈希，不复用压缩前引用。参考的职责、允许借用与禁止借用需明确。

## 2. prepare / acceptance

```powershell
python -I examples/art-pilot/scripts/production.py --project work/art-pilot prepare --attempt bird-001 --contract family-contract.json --draft draft.json --design packet/design.json --parameters backend-params.json --provider actual-provider --model unknown --character bird
python -I examples/art-pilot/scripts/production.py --project work/art-pilot acceptance --contract family-contract.json --draft draft.json --design packet/design.json
```

prepare 重新编译合同 / Draft 并核对 prompt、任务、输入顺序/职责、acceptance、designId、targets；冻结输入图及权威源字节。未知 method、重复 ID、缺身份项报错。`alpha-bounds` 对应 automatic，human 项必须由真实人类决定。没有手填 required 或 approve 开关。

编辑仍须提供编辑任务自己的合同 / Draft / design，加 `--parent <精确父attempt>` 与 `--instruction <明确修改>`；父图作为第一张 edit-source，之后保持参考顺序。编辑记录不冒称原始生成。

## 3. 外部执行与完成

库和脚本不自动调用图像服务。执行器必须读取 `production/attempts/<id>/prepared.json`，真实提交冻结 prompt、参数和输入图，并保留可核验工具记录。Codex provider 执行桥仍未实现，登录不是离线回归先决条件。

`--character` 必填。角色首次 prepare 写入不可覆盖的 `production/host-locks/<角色>.json`，此后该角色所有 prepare 的 `--provider` 与 `--model` 必须一致；`--parent` 必须属于同一角色且同一生图宿主；derive 继承父角色。没有强制切换开关，换宿主请新建角色。项目里已有其他角色的锁时，未加锁的角色 ID 会报错，除非用 `--new-character` 确认确实是新角色，这样拼错的角色名不会静默新建锁。以 `cursor` 开头的 provider 必须正好是 `cursor-desktop`。

### Cursor 执行（半自动）

以 `--provider cursor-desktop` prepare 后（参数文件仅允许 `aspect_ratio`：1:1、4:3、3:4、16:9、9:16），运行 `cursor-packet --attempt <id>`，把输出的 `call` 原样交给 Cursor GenerateImage，不要手抄 prompt。用户授权并生成后运行 `cursor-complete --attempt <id> --output <工具报告路径>`；失败用 `cursor-fail --attempt <id> --message <原因>`。回执证据级别为 `host-agent-attested`：MaLiang 无法调用 Cursor 工具，也不读取 Cursor 会话记录，模型与计费保持 unknown。

成功回执必须包含：`preparedEventId`（原样）、`invocation`（完整对象，非字符串）、`outcome: "success"`、真实 `artifactSha256`、真实 `executionEvidence`。

```powershell
python -I examples/art-pilot/scripts/production.py --project work/art-pilot complete --attempt bird-001 --receipt receipt.json --image output.png
```

失败使用 `fail --attempt bird-001 --category timeout --message <真实错误摘要>`，不能用失败调用编造成功图。complete 精确匹配准备事件、完整 invocation 与输出哈希，但手拼 receipt 本身不证明真实执行。

已有外部图片使用 `import --attempt <新id> --contract ... --draft ... --design ... --image ... --provenance <真实来源> [--historical]`；不伪造 invocation、旧时间或批准。core 可能保存原始字节为 `source.bin`，这不改变图像内容，但这类生产记录不属于公开精选素材或发行包。

V03 旧回执不可信：实际未提交图片参考、实际 prompt 与冻结包不一致，不能作为可执行模板。V04 / Codex 外部试作仅保留可证明事实和用户反馈，不补造完整链。展示偏好不等于新压缩派生已满足生产采用要求。

## 4. 技术、人审与采用

```powershell
python -I examples/art-pilot/scripts/production.py --project work/art-pilot technical --attempt bird-001
python -I examples/art-pilot/scripts/production.py --project work/art-pilot review --attempt bird-001 --decision-file human-decision.json
```

technical 解码实际图像，运行每个必需自动谓词并绑定精确候选；尺寸、非空 alpha、边界通过不能证明艺术质量。derive 支持 copy / flip-x / matte-resize，并绑定父候选；不是原生视角生图或隐式换手认可。

matte-resize 是确定性后处理，不是重新生图：父图尺寸须等于冻结 `sourceSize`；从画布四边泛洪，只把与边缘连通且颜色在容差内的背景设为透明（内部相近颜色保留）；按 `outputSize / sourceSize` 等比 LANCZOS 缩放，主体底边对齐 `groundY`、水平中心对齐 `anchorX`，输出 PNG。背景色默认取四角中位数，可用 `--key-color #RRGGBB` 指定，`--tolerance` 默认 24。抠图为空、主体碰源图边缘或放置越出画布均报错且不创建 attempt；仅适合纯色背景，复杂背景应失败而非硬凑。派生记录保存全部参数；派生图是新候选，必须重新 technical 与真实人审，父图人审不能复用。

```powershell
python -I examples/art-pilot/scripts/production.py --project work/art-pilot derive --attempt bird-001-sprite --parent bird-001 --operation matte-resize
```

人审 decision-file 必须由真实决定产生：`actorType: "human"`、真实 reviewer、候选完整 eventId/attemptId/artifact、`identityChecklist: ["identity"]`、非空真实 statement、真实带时区 decidedAt、adopt/reject/pending，以及全部必需 human 项的 pass/fail/pending/unsupported。Agent 不得为了推进流程编写真实 human pass。

审核前用 `preview` 以绝对路径列出每张图：

```powershell
python -I examples/art-pilot/scripts/production.py --project work/art-pilot preview --attempt bird-001
python -I examples/art-pilot/scripts/production.py --project work/art-pilot revisions --character bird
```

`preview` 按真实格式取扩展名写入 `work/<project>/previews/<attemptId>.<ext>`，并打印候选（含 sha256）、宿主输出副本和查看副本的绝对路径，不写任何事件。查看副本不是证据，审核仍绑定候选的 sha256。`revisions` 列出该角色所有被拒 `review-quick` 决定的 issues 和 note，作为下一次请求的 prompt 素材。

对话里转述的选择用 `review-quick`，不需要 decision file：

```powershell
python -I examples/art-pilot/scripts/production.py --project work/art-pilot review-quick --attempt bird-001 --choice reject --issues pose,palette --note "expression too angry" --quote "not pass, the face is off"
```

`--choice` 为 pass 或 reject，`--quote`（用户原话）必填。`--issues` 只接受该候选的必需 human 验收 ID，记为 `fail`；reject 时其余项保持 `pending`，pass 时全部记 `pass`（pass 不能带 issues 或 note）。reviewer 默认取 git `user.name <user.email>`，没有则取系统用户，也可用 `--reviewer` 指定；时间取当前时间。冻结在 `production/quick-reviews/` 的证据记录 `capturedVia: "host-chat"` 与 `revisionNotes`，报告可据此区分手写 decision file：这是 agent 对真实对话选择的转述，来源强度低于人亲手写的文件。修订意见只作为下一次请求的 prompt 来源，不会自动改动冻结的 markers 或 style 规则。

采用命令模板（尖括号替换为实际事件路径，不要原样执行）：

```powershell
python -I examples/art-pilot/scripts/production.py --project work/art-pilot adopt --attempt bird-001 --asset bird-idle --review production/events/<human-event>.json --result production/events/<automatic-event>.json
```

每个必需 automatic 项需一个 `--result`。缺项、失败、pending/unsupported、旧人审或技术结果绑定其他候选均拒绝。满足完整门禁可直接采用，无需再次生成。事件不可覆盖，current projection 原子更新。

## 验证边界

合成测试确认行为门禁，不确认真实参考图被服务接收、不确认几何/视觉质量、不代替真实人类采用。图片为用户自有 CC-BY-4.0 资产；库、代码和文档为 MIT。授权公开、用户偏好与正式 delivery 分开记录。没有 push、上传、PR 或 merge 隐含在这些命令中。
