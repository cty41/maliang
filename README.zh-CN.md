# 马良（MaLiang）

[English](README.md) | [简体中文](README.zh-CN.md)

**把游戏美术想法整理成清楚的制作要求，再记录结果和审核。**

马良是一个轻量 Python 工具包，用于准备角色美术简报、检查记录，
并追踪具体哪张图片经过审核和采用。你可以直接使用，也可以让 Agent 操作。
LLM 和图像工具由你选择的宿主提供；马良本身不调用图像生成服务。

## 它从哪里来

马良从 **Tactics 的美术工具**中提取并通用化，让其他项目也能复用
姿态草图和美术审核流程，不必把原项目的身份与规则整套搬过去。
来源见[提取记录](EXTRACTED_FROM.md)。

## 从源码开始体验

需要 **Windows PowerShell、Python 3.10+ 和 Git**。本地使用已在
**Windows 11 x64** 验证；GitHub CI 的 `windows-2025` 是 Windows Server x64，
不是 Windows 11。请安装当前源码：已发布的 **v0.1.0** tag 不包含当前的
`design` 和 `flow` 命令。克隆和安装可能需要联网。

```powershell
git clone https://github.com/cty41/maliang.git
cd maliang
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install .
```

保持环境激活，从仓库根目录运行离线演示：

```powershell
python -I examples/art-pilot/scripts/offline_demo.py --project work/art-pilot/synthetic-demo-001
```

成功时退出码为 0，并打印含 `synthetic-adopted` 的 JSON 报告。
演示在 `work/art-pilot/synthetic-demo-001` 下创建样例记录和一张很小的合成图；
这**不是真实的服务调用或人工批准**。这次练习无需自己编写合同，也不需要生图服务。
**已有目录会被拒绝**，空目录也不例外。再次运行请换一个新后缀，
不要把演示指向已有项目。

## 接入 Agent 或 LLM

模型、登录和图像工具在**你选择的宿主**里配置，不是在马良里配置。
让 Agent 读取下载的源码目录中的 `skills/maliang-art/SKILL.md`；
无需先安装技能。告诉它源码目录的完整路径、
已安装马良的 Python 解释器，以及单独的资产项目根目录。
按[接入步骤](docs/usage.zh-CN.md#agent-与-llm-配置)核对实际工具，再发起外部请求。

例如：“先读我源码目录中的马良 skill，帮我准备一张游隼待机角色图。
先确认路径和可用工具，停在生图前，让我审核制作要求。”你可以换成自己的角色想法。

## 用它制作自己的美术

从角色、视图、姿态和限制条件开始。马良校验并编译简报，由获得授权的
外部图像工具实际执行；随后检查具体产物，并在采用前取得真实人工审核。
[使用指南](docs/usage.zh-CN.md)介绍设计命令、CLI/API 和安全边界；
[生产运行手册](examples/art-pilot/docs/runbook.md)给出详细操作流程。
如果宿主只能准备文本和记录，就停在准备阶段。

## 去哪里看例子

- [art-pilot](examples/art-pilot/README.md)：离线练习和整理后的真实图片示例，
  包括选定的游隼与共用风格参考。展示图片和历史反馈不等于当前生产批准证据。
- [poet-cast](examples/poet-cast/ATTRIBUTION.md)：带来源署名的原项目教程。
- [文档导航](llms.txt)：其他参考。上述指南、运行手册和 skill 需要源码 checkout，
  wheel 不携带它们。

代码与发行包：[MIT](LICENSE)。poet-cast 教程：[CC BY 4.0](examples/poet-cast/ATTRIBUTION.md)。
素材许可：[REUSE.toml](REUSE.toml)。
