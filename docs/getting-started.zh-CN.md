# 入门教程

[English](getting-started.md) | [简体中文](getting-started.zh-CN.md) | [快速入门](../README.zh-CN.md)

本教程约需 15 分钟，全程不调用任何图像服务。你会先运行离线演示、看懂它写出的文件，
再编译一份真实的样例简报。不熟悉的术语见[核心概念](concepts.zh-CN.md)。

## 1. 安装

按[快速开始](../README.zh-CN.md#快速开始)克隆仓库、创建 `.venv` 并安装当前源码。
以下命令都在激活该环境后，从仓库根目录运行。

## 2. 运行离线演示并看懂输出

```powershell
python -I examples/art-pilot/scripts/offline_demo.py --project work/art-pilot/tutorial-001
```

它会打印含 `"status": "synthetic-adopted"` 的 JSON 报告。项目目录已存在时会被拒绝，
每次运行请换一个新后缀。`work/art-pilot/tutorial-001` 下会出现：

| 文件 | 含义 |
| --- | --- |
| `contract.json`、`draft.json`、`parameters.json` | 本应由人编写的输入 |
| `design.json` | 编译后的简报 |
| `synthetic-image.png` | 代替真实图片的小色块 |
| `synthetic-receipt.json` | 模拟的“宿主”执行记录 |
| `synthetic-human.json` | 伪造的人工决定，仅为测试数据 |
| `production/events/` | 不可变事件记录，每步一条 |
| `production/current/synthetic-demo.json` | 已采用的当前投影 |

演示用替身走完了整个生命周期。报告中的 `realProviderExecution: false` 和
`realHumanApproval: false` 正说明了这一点：它展示的是流程管道，不是真实美术。

## 3. 编译真实样例简报

仓库中的游隼样例是一套整理好的合同和草案：

```powershell
python -m maliang_art design validate --contract examples/art-pilot/characters/falcon-idle/family-contract.json --draft examples/art-pilot/characters/falcon-idle/draft-example.json
python -m maliang_art design compile --contract examples/art-pilot/characters/falcon-idle/family-contract.json --draft examples/art-pilot/characters/falcon-idle/draft-example.json --output-dir work/art-pilot/tutorial-design
```

`validate` 打印 `"valid": true`；`compile` 打印含 `"packet": "design.json"` 的清单。
打开 `work/art-pilot/tutorial-design/design.json`，先看这些字段：

- `prompt`：宿主会发给图像工具的文本指令。
- `tasks` 和 `targets`：要产出哪些视图/状态，以及尺寸。
- `imageInputs` 和 `references`：按顺序声明的参考图。
- `acceptance`：结果被采用前仍待完成的检查。

校验失败时，JSON `diagnostics` 会为每个问题给出 `path`、`code` 和 `message`。
马良不会猜测缺失的美术决定。

## 4. 改成你自己的角色

把两个游隼文件复制到新目录，修改角色、视图和限制条件，反复运行 `validate`
直到通过。[核心概念](concepts.zh-CN.md#你需要编写的输入)列出的 schema 说明了每个字段。
每次修改输入后，编译到新的输出目录。

## 5. 获得真实图片

把简报交给宿主带图像工具的 Agent。[Agent 接入](agent-setup.zh-CN.md)说明要告诉它什么、
要核对什么。[生产运行手册](../examples/art-pilot/docs/runbook.md)说明如何绑定结果、
技术检查、人工审核和采用。
