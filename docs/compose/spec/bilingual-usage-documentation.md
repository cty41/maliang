---
feature: bilingual-usage-documentation
status: delivered
updated: 2026-10-14
branch: docs/bilingual-usage
commits: 3b228f9..f570068
---

# 简明入门与双语使用文档分层

## Report

**What was built** — 本地实现、验证及独立复审完成；工作区 `D:\codes\maliang`，分支 `docs/bilingual-usage`，基线 `3b228f9`，实现提交 `f570068`。用户已授权推送并合入 main；记录范围不含随后文档收口提交。远端 CI 与合并结果以 PR 为准，不由本地验证替代。

根 README 英文78行、中文72行，按用途、Tactics 起源、Windows 安装、Agent/LLM 接入、使用和示例组织。详细用法迁入双语 usage，示例与生产手册补齐英文配对并保留原中文路径；导航与 skill 引用同步。Agent 接入明确宿主配置模型/登录/图像工具，马良自身没有模型服务或 API key 设置，支持手动读取技能说明并确认解释器和独立资产根目录，不虚构自动 provider 或技能激活。

CI 仅修改两处 runner 配置：OS 矩阵收束到 windows-2025，许可任务同样使用 windows-2025。Python 3.10–3.13 及原测试、构建、安装、分发检查全部保留；没有删除便携实现或安全测试。本机 Win11 使用验证与托管 Server CI 配置分开描述。

**Verification** — 2026-10-14 最终正文与配置完成后顺序验证，再进行独立审查：

- 本机 CIM：Windows 11 专业版 x64，10.0.26200；仓库 Python 3.14.3。
- `.venv/Scripts/python.exe -m pytest tests examples/art-pilot/tests -q`：490 passed、6 skipped，65.98秒；跳过均因本机符号链接权限。包括提取 README 演示命令的临时目录黑盒验证。
- `.venv/Scripts/python.exe -m reuse lint`：PASS，122/122。此前扫描受到上轮本机 PR 临时正文影响，已仅在 `.git/info/exclude` 排除该确切临时文件，未删除产物或改变公开许可范围。
- `.venv/Scripts/python.exe -m build`：sdist 和从 sdist 构建 wheel 均 PASS。
- `.venv/Scripts/python.exe examples/art-pilot/scripts/smoke_wheel.py --wheel dist/maliang_game_art-0.1.0-py3-none-any.whl --wheelhouse D:/codes/art-pilot/.wheelhouse`：独立临时虚拟环境安装 PASS，37项资源核验；wheel SHA-256 `b98c9798f43ab0daa4665545b702f6e6b9fabf10f4821849ad212fc319e758d0`。wheelhouse 仅本次验证环境，不是用户前提。
- `git diff --check`：PASS。
- 独立只读复审：规格符合性、正确性、一致性通过，无阻塞 P0/P1/P2；未重复运行完整验证。
- 继承 Alfred 工作区检查在本轮早期已执行：tests/run.ps1 PASS；doctor 的既有无关 fin-value dirty 状态未处理。
- 新 workflow 尚未推送或运行，不能声称 Windows Server / Python 3.10–3.13 新矩阵通过；未验证宿主安装/激活、真实生图或视觉验收。

**Journey log**

1. README 的改进不只是缩短：由维护入口清单调整为用户关心的目的、起源、安装接入、使用和实例。
2. 文档测试审查与耗时测量独立进行；确认部分弱断言与维护负担，但用户未授权整套删减，本轮不借平台调整删除它们。
3. GitHub windows-2025 是 Windows Server x64，不能代替本机 Win11 证据；保留历史跨平台 CI 事实，不再提供 Unix 使用路线。

## [S1] 问题与工作区

上一轮 agent-usage-documentation 已随 PR #3 合入 main，入口和离线示例已经存在，不重复声称这些能力待实现。但根 README 仍混合入门、CLI/API 参考、生产语义和历史版本限制，英文 212 行；中英文内容覆盖不一致，示例与运行手册缺英文版本。

用户确认本轮覆盖完整使用路径双语；开发规范和历史规格不全面翻译。沿用既定工作区 D:\codes\maliang，从刷新后的 origin/main 3b228f9 创建 docs/bilingual-usage；不另建 worktree。现有未跟踪 work/ 内容不覆盖或清理。沿用仓库 docs/ 结构和 Compose 规格位置，不另引入 .agents/docs 或平行计划体系。

## [S2] 文档层级与语言契约

根 README.md 与 README.zh-CN.md 顶部提供语言互链，每份目标不超过 90 行。按普通用户关心的问题组织：能做什么、为什么创建、如何安装并连接 Agent/LLM、如何使用、例子在哪里。起源以 EXTRACTED_FROM 的 Tactics 美术工具提取事实为准，不编造背景。给出唯一推荐的 Windows PowerShell 源码安装路线、一个可运行离线演示、预期结果与新目录要求，以及可直接给 Agent 的使用请求示例。详细安全内容移入指南，许可证仅保留页尾简短链接，不再以“接下来”混排开发规范、合规提示和用户操作。明确当前源码功能不等于 v0.1.0 发布能力，避免推荐的安装版本跑不了紧随其后的例子。首次读者不需要先编写合同 JSON 或理解内部术语才能完成演示。

本轮追加确认：面向用户的安装/运行说明仅提供 Windows 路线，标明本地使用验证环境为 Windows 11 x64。GitHub CI 使用托管 Windows Server x64（固定 windows-2025），不把它冒称 Win11。移除 Ubuntu/macOS 测试矩阵，并将许可任务改到同一 Windows runner；保留 Python 3.10–3.13 和原有测试/构建/安装/分发检查。保留实现中的便携分支和通用安全测试，不借此删除测试或重构兼容实现。历史跨平台 CI 通过的事实不抹除。

Agent/LLM 配置在双语 usage 指南中明确分工：MaLiang 本身不提供模型服务或 API key 配置，文本模型、生图/编辑能力及登录由用户选择的宿主配置。给出不依赖技能自动发现的手动读取仓库 SKILL.md 的可执行接入步骤，要求明确 MaLiang checkout、Python 解释器和独立资产根目录，并说明如何检查宿主是否有实际图片输入/输出能力；只有准备能力时停在准备阶段。可选技能安装引用宿主实际机制，不发明通用配置文件或模型字段，不自动安装，也不声称自动 Codex 桥存在。

新增 docs/usage.md 与 docs/usage.zh-CN.md，按相同主题组织安装/版本选择、设计编译、pose/records/review CLI、Python API、状态机和重要行为边界。迁移 README 现有有效内容，不丢失预览预算、引用声明与实际提交区别、debug 非生图参考、不可变发布与非事务行为等关键事实。术语、命令、退出状态与版本边界双语一致；详细命令集中维护，不在根 README 复制整套参考。

examples/art-pilot/README.md 与 docs/runbook.md 保留现有中文路径和语义以维护引用，分别新增 README.en.md 与 docs/runbook.en.md 英文配对。每对顶部互链；根英文入口链接英文，中文入口链接中文。生产流程继续以这对 runbook 为权威：离线合成练习与真实项目操作清晰区分，不新建另一套生产教程。翻译中不得将 synthetic human fixture 写成真实人审或将手动宿主路径写成自动 provider 桥。

llms.txt、AGENTS 与使用 skill 的相关入口按需同步，并明确配对语言；skill 本体仍为一个，不另建中文 skill 变体，不自动安装。CONTRIBUTING/SECURITY 仍为现有开发权威来源，本轮不做全文翻译。

## [S3] 旧文档纠偏边界

针对受迁移影响的说明与已有规格，修复死链接、过时入口、阶段状态歧义及重复当前用法；历史设计保留历史含义，不全面重写或翻译。上一轮交付事实可据提交/PR 更新，CI 状态仅凭所查询的精确提交或 job 证据更新，不以新 PR 测试倒推旧 PR 历史测试成功。

provider 自动桥、真实视觉验收、无法重新核验的外部素材源哈希仍保持未完成或证据缺失。不能为了文档整齐勾选这些工作。若发现需要功能变更的问题，单列报告，不借本轮文档整理扩功能。

## [S4] 验证与交付

扩展现有文档测试以覆盖新文件、语言互链和本地锚点有效性；允许纯历史规格不全面参与锚点校验。检查根 README 精简要求、双语推荐命令与最短离线演示一致，测试公开命令与输出而非复制生产实现。

在新临时目录执行根 README 的推荐离线演示，确认合成标识、正常退出、已有目录拒绝；既有生产安全门禁测试保持不变。运行 CONTRIBUTING 的完整 pytest tests examples/art-pilot/tests、REUSE、build、独立 wheel 烟测与 git diff --check；新增文档不改变包资源分发边界。若 sdist 包含英文 sample README，明确检查其不意外携带真实图片或私有运行产物。

验证结束后进行独立审查，分别检查规格符合性、事实正确性、双语语义和仓库一致性。未验证宿主激活或真实生成需明确报告。提交、推送和合并不沿用上一轮授权，本轮另待用户明确要求。

## [S5] 范围外

代码行为改造、provider 桥、真实生图、素材改动、安装 skill、文档站、llms-full.txt、所有历史规格/开发文档全文翻译、发布新版本。

## Tasks

- [x] T1: 精简根双语 README 并建立双语详细指南 — 验收：两份 README 各不超过 90 行，单一可运行入门路线，迁出的关键行为仍可找到且双语一致。(covers: S1, S2)
- [x] T2: 补齐示例入口和生产手册英文配对 — 验收：现有中文路径保持可用，语言互链，合成/真实边界和命令语义一致。(covers: S2)
- [x] T3: 同步导航及受影响旧文档事实 — 验收：无失效入口，无重复权威流程，不虚报历史 CI/provider/视觉验收。(covers: S2, S3; depends: T1, T2)
- [x] T6: Windows 使用与托管 CI 范围收束 — 验收：当前操作指南不再要求 Unix 步骤；CI 仅托管 Windows x64，保留四个 Python 版本及全部检查；Win11本机与Server CI证据分开，Agent接入无虚构配置。(covers: S2, S4)
- [x] T4: 文档与示例回归及完整验证 — 验收：双语链接/锚点、入门示例、pytest、许可、构建和安装烟测通过或如实报告不可用项。(covers: S4, S5; depends: T3)
- [x] T5: 独立审查及交付收口 — 验收：无阻塞项，Report 记录验证、未测范围及实际提交状态。(covers: S1, S3, S4, S5; depends: T4)
