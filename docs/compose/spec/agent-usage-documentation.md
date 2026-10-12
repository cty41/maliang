---
feature: agent-usage-documentation
status: delivered
updated: 2026-10-12
branch: docs/agent-usage
commits: 5c5fa08..74e49c1
---

# 马良 Agent 使用入口与文档一致性优化

## Report

**What was built** — 本地实现、验证和独立复审已完成，用户已授权提交、创建 PR 并合入 main。实际工作区为 `D:\codes\maliang`，分支 `docs/agent-usage`，基线为 `5c5fa08`，实现提交为 `74e49c1`；记录范围不包含后续文档收口提交。远端检查及合并结果以 PR 为准，不由本地验证代替。

新增精简开发入口 `AGENTS.md`、单个可移植使用 skill 及中英显示元数据、`llms.txt` 导航；同步双语 README、CONTRIBUTING、历史 spec 与 CLI 预览帮助。新增可直接运行的 `offline_demo.py`，通过现有生产流程脚本完成 compile → prepare → 合成结果绑定 → technical → 合成人审 fixture → adopt，并拒绝复用已有输出目录。教程、产物和最终摘要明确区分合成练习、真实 provider 执行和真实人工批准。

未新增 `llms-full.txt`，未自动安装 skill，未实现 provider 桥，未调用图片服务。六种 skill 情境仅做静态审查与回归检查，不宣称真实宿主已安装或激活。

**Verification** — 最终实现完成后顺序运行以下检查，随后才进行独立复审：

- `.venv/Scripts/python.exe -m pytest tests examples/art-pilot/tests -q`：475 passed、6 skipped；跳过项均与 Windows 符号链接权限有关。
- `.venv/Scripts/python.exe -m reuse lint`：PASS，117/117 文件覆盖，无缺失许可。
- `.venv/Scripts/python.exe -m build`：sdist 与 wheel 构建 PASS。
- `.venv/Scripts/python.exe examples/art-pilot/scripts/smoke_wheel.py --wheel dist/maliang_game_art-0.1.0-py3-none-any.whl --wheelhouse D:/codes/art-pilot/.wheelhouse`：独立临时虚拟环境安装与 CLI 烟测 PASS，验证 37 项资源。该 wheelhouse 是本次验证环境，不是用户运行前提。
- wheel SHA-256：`e3b817ef9a8ecc021e5017cfb82e1488fa0ffc8a73dcb42c72fad0e9bc05c4c6`。
- `git diff --check`：PASS。
- 独立复审：首轮发现的离线教程 P2 已修复；第二轮聚焦复审未发现新的 critical 或 P2 回归。复审为只读静态检查，未重复运行已通过的完整验证。
- Skill 结构校验：零错误；四项启发式警告涉及不随 skill 打包的仓库脚本，已通过显式 checkout 根契约与路径存在性测试覆盖。
- 未推送，未运行远程 CI；真实宿主安装、激活与真实图片生成未测试。
- 继承工作区要求的 Alfred `doctor -Quick -Json` 已运行：报告无关 `fin-value` 子模块为 dirty；未修改或清理该子模块。这不是 MaLiang 验证失败。

**Journey log**

1. 使用文档必须提供真正可复制运行的离线命令；已有合成测试不能替代用户教程，因此补齐独立 demo 和黑盒回归。
2. 外部安装的 skill 通过显式 MaLiang checkout 根定位权威 runbook，避免依赖失效的 `../../` 相对路径。
3. 历史 spec 以 Git/代码证据纠偏；手动宿主验证不升级为自动 provider API，也不补造原始生成记录或视觉批准。

## [S1] 问题与目标

用户确认“使用优于介绍”：优先可运行示例/操作流程，其次精简AGENTS.md和一个使用马良的skill，再补llms.txt导航；暂不做llms-full.txt。

现状：上轮审查修复已更新双语README的tag/源码区别、预览预算、SECURITY和部分代码说明；尚未做完整文档收口。仓库没有AGENTS.md、llms.txt、llms-full.txt或自带SKILL.md。历史spec还把已提交实现写成未提交，收口任务状态未同步；README“无production CLI”未区分包命令与仓库示例脚本。

实施沿用已选定的 `D:\codes\maliang` 工作区，刷新 `origin/main` 后从 `5c5fa08` 创建 `docs/agent-usage` 分支；未在已合并的旧修复分支继续开发，也未创建额外 worktree。

成功目标：一个没有历史聊天上下文的Agent，能分清“开发马良”和“用马良制作资产”，找到有效命令，运行一次无网络合成闭环；遇到真实生图能如实识别宿主能力、准备/记录请求、等待真实人工判断，不补造工具权限或批准。

## [S2] 文档分工与权威来源

- README.md / README.zh-CN.md：人类和Agent入口，快速安装、最短用法与导航；不是另一份完整API手册。
- CONTRIBUTING.md：开发安装/验证步骤的维护来源；AGENTS链接它而非复制冗长命令表。更新其验证入口以覆盖tests和examples/art-pilot/tests，而非默认pytest只跑库测试。
- 根AGENTS.md：给修改马良代码的Agent，写模块边界、如何取证、验证入口、素材/凭证/发布限制；不自动启动生图或承担终端用户制作教学。
- examples/art-pilot/README.md + docs/runbook.md：继续作为使用流程权威来源，修正可复制运行的命令、真实入口、失败边界；不再新建平行长教程。
- skills/maliang-art/SKILL.md：单个可安装的“使用马良制作资产”skill，引用可运行runbook与能力事实，按需读参考；不是把整份文档复制进skill，也不是马良开发规则。
- llms.txt：简短导航，链接安装、API、CLI、sample、skill及限制。标明计划文档不是已实现API；不假设Agent自动读它。
- docs/compose/spec/*.md：特性决策与交付证据，不代替日常使用入口。按代码/测试/Git证据同步状态，不能把尚未完成provider或美术验收勾为完成。
- 代码docstring、CLI --help：只同步当前实际行为。运行逻辑如发现新bug，单列修复，不在本轮借文档更新扩功能。

## [S3] 可执行使用流程优先

先验证现有示例，而非先写宣传文案：

1. 区分v0.1.0发行tag和包含flow/design的当前源码；提供隔离安装命令和跨平台Python入口，避免作者机器绝对路径。
2. 读取现有教学合同/Draft，运行design validate/compile；默认不输出几何调试图作生图参考。
3. 在ignored运行目录内，用合成素材完成prepare、离线结果绑定、technical、明确标注synthetic的human fixture和adopt闭环。说明测试用人审不是实际用户批准。
4. 显示预期输出/退出码，说明工作目录、--project位置、包内CLI与sample production.py区别。
5. 真正generation/edit单列为宿主步骤：现有库不含已交付的自动Codex桥。手工验证过的MiMo→Codex路径可以写“已验证操作方式”，不能写成maliang-art现成执行命令。真实工具不存在则停在准备任务，不把图路径写进文字冒充图片输入。
6. 审核输出先展示图片/路径再请求判断；用户“外观喜欢”与技术采用门禁分开。无法证明的模型、计费、参考提交保持unknown/attested。

无真实网络、图片生成或订阅凭证是示例测试的前提。现有批准图片可以用于repository-only展示，不强迫其他项目复用胶囊风格或tactics尺寸。

## [S4] AGENTS 与使用 skill

### AGENTS.md

控制在简短工作约定范围：读README/CONTRIBUTING/SECURITY；模块分工；纯核心与宿主执行边界；合成fixture优先；新schema不悄悄改旧语义；禁止自动提交/推送/生图/搬运凭证；必需完整验证入口。不要固化最新测试数量、历史分支名、用户姓名或本机路径。

### 单个使用 skill

建议版本控制位置skills/maliang-art/SKILL.md，不把它放根目录当全局规则。正文包含name/description、触发与不触发条件、必要输入、前置环境检查、执行步骤、失败处理、输出/人工决策边界。

触发：用户明确用马良准备/制作/审核游戏美术。非触发：普通美术讨论、仅修改马良源码、任何无关图片请求。skill不代替image_gen/image_edit工具，不借用未暴露权限，不将默认provider偏好当授权。

流程：需求与参考职责→按实际工具能力选择执行路径→完整请求冻结→真实外部调用→结果匹配→预览/检查→真实人审→采用/保留/否决。允许无已有角色图的探索，风格参考推荐但不强迫；不需要专业美术师先交model sheet。代码调试blockout不是必需设计阶段。

分发：源码skill目录为唯一维护源，文档说明如何交给支持skills的宿主安装；本轮不自动写用户全局技能目录。执行时实施者先核对宿主技能安装/发现规范。可移植skill通过配置的MaLiang项目根定位runbook，不假定安装到外部后相对../../路径仍能找到仓库；没有项目根就要求定位，不静默猜路径。

宿主支持可验证范围：MiMo当前工具边界与Codex会话能力取实际暴露信息；不承诺所有客户端都自动加载。配置/安装只描述经过核验的方法，未验证项说明未验证。

## [S5] llms 导航、过期清理与打包

新增llms.txt使用简短Markdown结构：项目一句话、版本边界、精选文档链接及用途、可选设计计划。链接以仓库可解析路径为准，后续若部署文档站再单列站点适配。无llms-full.txt生成器或大段API复制。

已有文档纠偏：

- art-pilot-merge-readiness按真实合并/CI证据收口，残余source-hash核验缺口如实说明。
- geometry-anchor-and-measure将旧阶段记录改标历史或现状，已修复项与仍待视觉验收/provider开发分开。
- repository-audit-fixes补实际提交/合并状态，不把旧缺陷描述读成现存bug。
- state-machine-core消除“apply不落盘”歧义，指明返回转换记录但内置图像步骤可写文件、无事务回滚。
- README明确“包内无production子命令；仓库sample提供production.py”。
- CLI --preview-size帮助说明默认半尺寸、预算缩小和显式超限拒绝；两处pose子命令一致。
- image-execution-providers继续标为计划，不能因手动Codex试验成功改为delivered。

新AGENTS、llms和skill纳入REUSE覆盖（MIT）；不新增素材或变更图片许可。仓库是Agent资料主要发布载体；不为本轮把skill自动装进wheel或引入插件系统。sdist若未携带skill/runbook，README明确仓库相对链接需源码checkout；校验既有发行边界不退化。

## [S6] 验证与审核

- 链接与文件存在性测试：AGENTS/llms/skill/README引用无失效文件，计划链接明确标识非功能入口。
- CLI帮助测试：实际调用--help，验证preview规则和现有命令存在，不靠静态文档假设。
- 示例黑盒：临时工作目录运行完整离线流程，与现有sample测试复用；正确拒绝缺验收、错误reference哈希、未确认的人审，不放宽门禁。
- Skill结构与行为审查：至少覆盖开发马良不触发生图、无图0→1、编辑保留源图、缺图像输入能力、结果不匹配、缺人工批准六种情境。无需真实生图，不伪造宿主已加载skill；静态验证与实际宿主安装测试明确区分。
- 新鲜pytest tests examples/art-pilot/tests、reuse lint、build、独立wheel烟测与diff check；沿用矩阵不引入新线上依赖。
- 验证结束后新独立review分别检查事实一致性、可执行性和使用/开发边界。测试和review通过再标交付；提交/推送/合并须明确授权。

## [S7] 范围外

llms-full.txt、文档站、自动全局安装skill、provider桥实现、运行逻辑重构、真实生图、改角色资产、朋友24点素材、任何凭证读取或迁移。用户已批准实施本计划，不创建计划之外的入口文件。

## Tasks

- [x] T1：验证并校正最小使用流程 — 验收：新环境临时目录可跑现有无网络样例，CLI/sample职责明确、无作者机器路径依赖。(covers: S2, S3)
- [x] T2：补AGENTS并同步CONTRIBUTING开发入口 — 验收：开发Agent可找到全量测试与安全约束，不混入用户生图流程或固定测试计数。(covers: S2, S4; depends: T1)
- [x] T3：编写单个maliang-art使用skill及分发说明 — 验收：有触发边界、必要输入、真实宿主能力核验、完整记录及人工闸门；外部安装不依赖失效相对路径；不自动安装。(covers: S3, S4; depends: T1)
- [x] T4：新增llms导航并同步README/spec/CLI文字 — 验收：有效链接、tag/源码/计划/已实现区分准确，preview帮助与实现一致，历史任务状态有证据。(covers: S2, S5; depends: T1, T2, T3)
- [x] T5：文档、命令与skill行为回归 — 验收：六种情境审查通过，命令黑盒/链接测试/REUSE/打包/安装无回归，不用静态通过冒称宿主安装完成。(covers: S6, S7; depends: T4)
- [x] T6：独立review与交付收口 — 验收：无关键事实或执行缺口，单一权威维护来源、无重复全文文档，报告验证结果及未测宿主范围。(covers: S1, S6, S7; depends: T5)
