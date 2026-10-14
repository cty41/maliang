# Art Pilot

[English](README.en.md) | [简体中文](README.md)

马良仓库内的视觉探索示例与生产门禁回归。库代码、脚本和文档使用 MIT；用户自有精选图片使用 CC-BY-4.0，具体来源与署名见资产清单。图片展示、用户偏好、技术检查、正式生产采用是不同事实，不互相替代。

## 运行边界

操作说明仅提供 Windows PowerShell 路线，本机使用验证环境为 Windows 11 x64。按 [开发环境说明](../../CONTRIBUTING.md#development-environment) 准备环境后，从仓库根目录使用当前已安装马良的 Python 执行命令：

```powershell
python -m pip install ".[test]"
python -m pytest tests examples/art-pilot/tests
```

CI 配置为 GitHub 托管 Windows Server x64（`windows-2025`），不是 Windows 11；本机通过不等于托管 CI 通过，未推送的工作流修改没有新的托管运行结果。此范围不删除脚本便携分支，也不否定历史跨平台 CI 结果。

不需要示例目录自身的 `.venv`、外部源码目录、Codex 登录或图像服务。禁止通过 `PYTHONPATH`、editable install 或 `sys.path` 注入替代独立安装验证。已有环境可直接执行测试，无须重复安装。

合成回归在临时目录创建 PNG、模拟 receipt 与人工决定 fixture，覆盖冻结输入、完整 acceptance、两版本、编辑/派生、导入/失败、旧证据错配、缺技术/人审项拒绝和采用投影。测试中的批准不是生产认可。

## 当前入口与门禁

- `scripts/production.py`：prepare → **外部实际执行** → complete / fail；另有 import、derive、technical、review、adopt。
- prepare、import 和 acceptance 必须提供权威 `--contract --draft --design`；重新编译并核对执行字段，不允许删改 packet 来省略必需项。
- 请求冻结完整 prompt、任务、参数、输入图哈希和顺序，以及合同 / Draft 原字节。没有手填 `--required-*` 或 `--decide approve` 的放行路径。
- 未知验收方法、重复 ID、缺身份项均报错。技术结果不能替代风格、身份或姿态的人类判断。
- 事件与产物不可覆盖；旧候选证据不能用于新候选。采用仅更新 current projection。
- 公开示例不提供旧 `record_generation.py`、`run_flow.py`、`review_check.py`；回归验证实际提供的入口拒绝旧批准捷径，不执行不存在的文件。

Agent 不得自称人类或编写真实批准证据。库和脚本尚未实现 Codex provider 执行桥。

## 精选图片与历史

共享风格参考为 `characters/shared/poet-idle-dr-style.png`，获选游隼为 `characters/falcon-idle/raw/codex-idle.png`；凤头鹰与各图的哈希、压缩参数及署名以资产清单为准。这些是仓库展示资料，不是离线回归先决条件。

旧 V03 回执不能证明图片参考实际提交，也不能证明实际 prompt 与冻结包一致；不得复用为当前资产的生产证据。V04 与 Codex 外部试作只描述有证据的输入、输出和用户反馈，不补造执行链。量化派生拥有新字节和新哈希，不能继承原图的 immutable approval / delivery。

## 发行与安装验证

wheel 不包含 art-pilot。sdist 保留本中文 README.md、脚本和合成测试，排除英文 README.en.md、真实 characters、production 记录、本机锁、policy 与历史 docs；因此 sdist 中不提供真实图片展示及运行手册。真实资产完整性检查属于仓库验证，不是发行包安装前提。

构建由维护者执行 `python -m build`（默认先构建 sdist，再从 sdist 构建 wheel）。随后使用实际产物路径：

```powershell
python examples/art-pilot/scripts/smoke_wheel.py --wheel dist/maliang_game_art-0.1.0-py3-none-any.whl
```

烟测用当前 `sys.executable` 创建临时隔离环境，安装指定 wheel 与依赖，从临时目录以 `-I` 导入，核对全部包资源哈希、schema 与模板、执行 CLI 帮助，最后删除环境。离线运行加 `--wheelhouse <已有依赖wheel目录>`；不指定时 pip 可从配置的索引下载依赖。

本机锁不随公开示例分发；需要精确源码/wheel核对时自行生成，不能把作者机器的安装路径当公共锁。仓库内 [运行手册](docs/runbook.md) 及其英文配对是生产流程与证据限制的权威文档。
