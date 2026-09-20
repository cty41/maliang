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
maliang-art flow show-default-template
maliang-art flow validate path/to/policy.yaml
maliang-art flow transitions path/to/policy.yaml --state draft
```

`maliang-game-art` 是发行名；v0.1.0 通过 GitHub tag 发布，不冒用 PyPI 上
已有且无关的 `maliang` 项目名。

选择姿态时必须显式填写 reviewer，并为每个未选方案提供原因；工具不绑定
任何特定人员。相同内容可幂等发布到同一路径，不同内容会触发碰撞错误。

## 状态机内核

`maliang_art.statemachine` 用 YAML 策略描述状态、转换、可选步骤与项目策略
（如审批人列表），并在内存中求值转换。`StateMachine.apply` 返回转换记录，
**不**把该记录发布到磁盘；内置图像步骤仍可能写入调用方提供的图片路径。
内置默认模板为 `draft → review → done/rejected`，`approvers` 默认为空，
由项目自行填写。

```python
from maliang_art.statemachine import load_policy, StateMachine
```

库不写死项目身份、画布尺寸或审批人。

代码与 Python 发行包采用 MIT；仅存在于仓库、不会打入 sdist 的
`examples/poet-cast/` 按 CC BY 4.0 提供，并通过 `assets.json` 固定六个
来源文件的哈希。行为测试使用合成 fixture；另有独立完整性/来源测试核对
授权示例，其来源与署名见 `ATTRIBUTION.md`。其他信息详见英文 `README.md`、
`SECURITY.md`、`CONTRIBUTING.md` 与 `EXTRACTED_FROM.md`。
