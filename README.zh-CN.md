# 马良（MaLiang）

**把视觉意图变成可审计的游戏美术。**

MaLiang 是一个面向游戏美术工作流的轻量、供应商无关 Python 工具包。
发行名为 **`maliang-game-art`**，导入名为 **`maliang_art`**，命令行为
**`maliang-art`**。

v0.1 提供确定性 JSON 编码与稳定 ID、路径约束、并发安全的不可变发布、
素材哈希记录、合成姿态草图渲染、Review 规则验证，以及供应商无关的
invocation/delivery/failure 记录。它不负责直接调用任何图像生成服务。

## 安装与使用

```console
python -m pip install "maliang-game-art @ git+https://github.com/cty41/maliang.git@v0.1.0"
maliang-art pose render-options --spec draft.json --output board.png
maliang-art records validate draft.json --schema pose-draft
maliang-art records validate examples/poet-cast/draft.json --schema pose-draft
maliang-art records check path/to/record-tree
```

`maliang-game-art` 是发行名；v0.1.0 通过 GitHub tag 发布，不冒用 PyPI 上
已有且无关的 `maliang` 项目名。

选择姿态时必须显式填写 reviewer，并为每个未选方案提供原因；工具不绑定
任何特定人员。相同内容可幂等发布到同一路径，不同内容会触发碰撞错误。

## 离线设计 CLI（源码版本）

以下 `flow` 和 `design` 命令属于当前源码功能，不包含在上面的已发布
v0.1.0 tag 中；这不表示已有新发行版。安装当前源码：

```console
git clone https://github.com/cty41/maliang.git
cd maliang
python -m pip install .
```

按 `schemas/v1/art-family-contract.schema.json` 与
`schemas/v1/sprite-slice-draft.schema.json` 提供明确的合同和草案 JSON：

```console
maliang-art design validate --contract family.json --draft slice.json
maliang-art design compile --contract family.json --draft slice.json --output-dir work/design-v1
```

`validate` 成功返回 JSON `{ "valid": true, "diagnostics": [] }`，退出码为 0。
无效/不完整记录、文件缺失或 JSON 格式错误返回退出码 1，以及含 `path`、
`code`、`message` 的 JSON 诊断；不会猜测缺失的美术决定。`compile` 使用相同
视觉需求校验，发布 `design.json`，包含完整 prompt、视图/状态任务、继承后的
目标尺寸、有序参考职责/哈希、待执行验收项和语境板布局。默认不渲染图片；
`imageInputs` 只包含声明的参考图，并保持原有顺序。家族 `variants` 和部件数字
坐标不再必填；拓扑部件可以用 `id` 和可选 `description` 描述物种结构。
形体意图须由家族允许，不受调试渲染器能力限制。相机仍支持显式 isometric
DR/UL profile，镜像派生方向须由项目接受。编译准备的是执行简报，不是批准设计。

现有 capsule/ball 渲染器仅通过可选调试模式调用：

```console
maliang-art design compile --contract family.json --draft slice.json --output-dir work/debug-v1 --debug-geometry
```

此模式需要明确的数字 variants 和部件 anchor/size，校验布局边界，并额外发布
`guides/*.png`。产物标记为 **debug-layout**、**unapproved**、
**not-generation-input**，绝不进入 `imageInputs`。椭圆占位和屏幕方向三角只展示
代码布局，不能证明物种、角色剪影、DR/UL 投影、动作姿态、画风、核心量测或
跨视图/状态一致性，其坐标也不会成为生图指令。视觉探索无需先选定或批准调试图。

成功输出 JSON 文件清单；发布碰撞/路径错误非零退出并写入 stderr。
相同输入可重复执行且不改已有字节；同一路径的不同字节被拒绝。
不可变发布以单个文件为单位，**不是多文件事务**：调试运行中断/失败可能留下
导引，相同输入重跑可继续完成。修改简报或调试模式时应使用新的输出目录。

色板和艺术裁决仍待人工审核；语境板只有布局，不伪造未来成图。
参考路径、哈希和借用职责仅作声明，本命令不读取/核验或复制参考图；
空参考允许从零探索。后端参数和参考图是否实际提交，须由执行适配器绑定核验。
不会调用网络/生图后端、自动作出人工批准或采用候选。目前不提供 production
CLI；生成执行与绑定精确图像的人工决定是独立项目步骤。

当前源码中，姿态 API `render_preview` 和 CLI 默认预览为画布半尺寸；超过
4,194,304 像素预算时等比缩小并向下取整，保留完整画布、不裁切。
显式 `--preview-size WIDTHxHEIGHT` 超预算仍拒绝，256² 画布默认仍为 128²。

## 状态机内核（源码版本）

完成上面的源码安装后运行：

```console
maliang-art flow show-default-template
maliang-art flow validate path/to/policy.yaml
maliang-art flow transitions path/to/policy.yaml --state draft
```

`maliang_art.statemachine` 用 YAML 策略描述状态、转换、可选步骤与项目策略
（如审批人列表），并在内存中求值转换。`StateMachine.apply` 返回转换记录，
**不**把该记录发布到磁盘；内置图像步骤仍可能写入调用方提供的图片路径。
内置默认模板为 `draft → review → done/rejected`，`approvers` 默认为空，
由项目自行填写。

```python
from maliang_art.statemachine import load_policy, StateMachine
```

库不写死项目身份、画布尺寸或审批人。策略 schema 使用稳定标识
`urn:maliang:schema:state-machine-policy:v1`，对应源码文件
`schemas/v1/state-machine-policy.schema.json`，不指向 v0.1.0 中不存在的文件。

Git 精确忽略本机锁 `examples/art-pilot/maliang.lock.json`、生产记录
`examples/art-pilot/production/` 与临时输出 `work/art-pilot/`。
忽略规则不会删除已跟踪文件，也不能替代发布前隐私审查。

代码与 Python 发行包采用 MIT；仅存在于仓库、不会打入 sdist 的
`examples/poet-cast/` 按 CC BY 4.0 提供，并通过 `assets.json` 固定六个
来源文件的哈希。行为测试使用合成 fixture；另有独立完整性/来源测试核对
授权示例，其来源与署名见 `ATTRIBUTION.md`。其他信息详见英文 `README.md`、
`SECURITY.md`、`CONTRIBUTING.md` 与 `EXTRACTED_FROM.md`。
