# Agent 与 LLM 接入

[English](agent-setup.md) | [简体中文](agent-setup.zh-CN.md) | [快速入门](../README.zh-CN.md)

**马良本身没有模型服务或 API key 配置。** 文本模型、生图/编辑工具和登录，
都在你选择的宿主中配置。不存在需要填写的马良模型字段或凭据文件。
不要把 API key 或订阅 token 复制进马良记录或提示词。

无需安装或自动发现 skill，只要把文件指给 Agent 即可。
在 checkout 根目录开会话时，`AGENTS.md` 已经会把使用请求引到 skill；在其他目录开会话时，
需要把 skill 路径告诉 Agent。

## 检查清单

1. **安装当前源码**，见[快速开始](../README.zh-CN.md#快速开始)。
2. **把 checkout 的绝对路径告诉 Agent**，让它读取该 checkout 中的
   `skills/maliang-art/SKILL.md` 和[运行手册](../examples/art-pilot/docs/runbook.md)。
   确认该目录包含 `pyproject.toml`、`src/maliang_art` 和运行手册。不要从 skill
   安装位置或 Agent 当前工作目录猜测 checkout。
3. **明确已安装当前马良的 Python 解释器。** 激活环境后，在 checkout 根目录执行
   （不会调用图像服务）：

```powershell
python -c "import sys; print(sys.executable)"
python -m maliang_art design validate --help
python -m maliang_art design compile --help
python -I examples/art-pilot/scripts/production.py --help
```

4. **让 Agent 使用该解释器**，并以 checkout 为工作目录；Shell 激活状态不一定传递到
   另一个宿主进程。必要时用 PowerShell 的 `&` 运算符调用解释器绝对路径。导入或命令
   失败时，取得许可后修正安装；不要注入源码路径掩盖不兼容的环境。
5. **另行约定资产项目根目录**，例如 `work/` 下的新目录（`work/` 已被 Git 忽略）。它不是马良
   源码根目录，即使位于 checkout 内也要区分。在示例子命令之前传入 `--project`；
   示例输入路径相对它解析。使用新输出路径，不覆盖源图。
6. **检查宿主实际暴露的工具及参数定义**：能否生图/编辑、按顺序附加真实图片文件或字节、
   保留提示词和参数、返回并显示产物？模型名、登录、订阅或提示词里的图片路径都不能
   证明这些能力。缺少所需的图片输入/输出时，停在准备阶段并报告缺口；不要偷偷把
   图片编辑改成纯文本操作。
7. **先审核冻结后的请求，再单独授权执行。** 生图是宿主操作，不是马良调用；没有自动
   Codex provider 桥。只绑定实际结果与执行证据，对同一候选做技术检查，展示给人看，
   等待真实人工决定。Agent 和合成测试记录都不能代替批准或绕过采用门禁。

## 第一次请求示例

“读取我 MaLiang checkout 中的 skill，确认 checkout、解释器和资产根目录，帮我准备
角色简报。核对可用图像工具，生图前先停下来让我审核。”请提供真实路径和美术目标，
不要假设 Agent 已经知道。

## 可选：安装 skill

只有确实需要时，才核对宿主当前的导入/发现机制，按该机制接入整个 `skills/maliang-art`
（含 locales），另行配置 checkout，并在宿主内验证激活。复制目录不等于成功发现；
这些说明不会自动安装，也不代表已经通过宿主激活测试。
