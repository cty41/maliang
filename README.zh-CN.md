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

代码采用 MIT；`examples/poet-cast/` 按 CC BY 4.0 提供，并通过
`assets.json` 固定六个来源文件的哈希。自动测试仍只使用合成 fixture；
授权示例的来源与署名见其 `ATTRIBUTION.md`。其他信息详见英文 `README.md`、
`SECURITY.md`、`CONTRIBUTING.md` 与 `EXTRACTED_FROM.md`。
