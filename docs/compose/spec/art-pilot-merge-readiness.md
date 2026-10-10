---
feature: art-pilot-merge-readiness
status: in-progress
branch: feat/state-machine-core
commits:
---

# art-pilot 示例迁移与 main 合并前收口

## Report

## [S1] 问题与基线

规划工作区 D:\codes\maliang，沿用已选择的 feat/state-machine-core；当前 HEAD 0283eb9，规划前工作树干净。最近 GitHub API 查询远端仅 main 与 feat/state-machine-core，无开放 PR；远端 feature 的 CI run 37952070866 在 licensing 阶段失败。main 缓存为 00d772f，实施/合并前须重新核验远端。

已观察的问题：

- REUSE.toml 覆盖 src/tests/schemas、根 Markdown、synthetic 与 poet-cast，但未为新增 docs/**、examples/art-pilot/** 定义适当覆盖。
- 迁移后 examples 测试14项中2项失败：安装测试假定示例自身.venv；旧入口禁用测试引用没有被复制的旧脚本。
- 默认 pytest testpaths 仅 tests，不能覆盖全部迁入示例测试。
- 压缩后 PNG 字节已改变，旧参考哈希/调用记录不能直接当压缩图来源证明；还复制了约1.26MB source.bin，不满足仅精选小图的目标。
- 示例复制了本机锁、绝对路径、旧审核及不实V03参考图回执；展示、可执行样例、历史审计三者混杂。
- 实际偏好的Codex游隼与MiMo V04不在原art-pilot raw清单内；不能因v03文件名就将其断言为最终获选版本。

用户明确：tactics柴犬/诗人、游隼、凤头鹰均为用户资产，可放马良/远端；朋友24点游戏资产不能进入任何远端Git。本任务不得触碰或复制24点美术。允许公开不等于选定具体再利用许可证。

## [S2] 收口设计

### 2.1 授权、范围及保留策略

先输出精确的保留/排除清单，确认最终游隼源图及图片许可证后才能执行素材整理。推荐示例代码/文档继续MIT；用户自有示例图片使用CC-BY-4.0，沿用现有poet-cast惯例，但须用户明确确认，不自行授权。

只维护马良内一份可运行sample，不同步维护两份脚本。D:\codes\art-pilot 的原始图与历史记录保留不动，作为本机原始实验资料。

目标展示集：最终确认的游隼、用户表示保留的凤头鹰、必要的一份诗人风格参考。去重前比较实际字节与视觉内容，不能仅按同名文件认定一致。失败稿/调试图不进入精选sample；若保留历史说明，必须标注不具可执行或批准权威。

不改写已推送历史、不force push、不用reset/clean。移出公开示例目录的历史文件须有明确清单和本机留存确认，通过正常后续提交移除；不伪造或就地修改旧receipt。已有远端历史仍包含此前提交的文件，删除当前文件不会消除历史，若需清历史另行授权。

### 2.2 压缩资产与哈希

64色量化是有损处理，不声称无损或保留全部细节。先确认用哪张源图，再生成单独压缩派生，保留本机原图；不重压原始文件。压缩前后检查尺寸、alpha语义、边缘和小图视觉。允许图片更大以保画质；不以32/64色作为全项目固定规范。

新增精选资产清单记录：角色/用途、源哈希（可指本机未公开原件）、入库派生哈希、尺寸/大小、处理工具版本与参数、版权/许可、用户认可范围。压缩图不复用原图的immutable approval/delivery。外部本机源不可作为运行sample必需依赖。

清单及公开输入只引用仓库相对路径，提供完整性测试。必要时导出新示例合同/Draft，引用压缩参考的新哈希；不把旧调用记录重算成新的“历史”。检查元数据不盲目strip色彩资料或平台标注。

### 2.3 可移植sample与证据整理

README/runbook 使用仓库相对路径与当前Python，不绑定D盘/用户名、外部maliang源码或作者机器的.venv。依赖外部Codex登录/图像工具的命令是可选人工路径，不是离线测试先决条件。

机器本地lock不作为公共可复现锁；改为可生成的锁说明/模板，精确wheel验证仍保留在工具或合成测试中。独立安装验证在临时环境实施，不假定examples/art-pilot/.venv存在；Windows与Unix路径按运行平台构造。

旧脚本禁用测试与sample边界一致：公开sample只列新入口，不靠不存在文件证明门禁；需要验证禁用行为则测试实际随包提供的入口，不能删除有效拒绝覆盖来凑绿。

V03不实回执移出可执行sample，保留本机证据和明确更正说明（实际未提交图片参考、实际prompt与冻结包不一致）。V04和Codex外部试作只描述可证明的输入/输出及用户反馈，不补造完整执行链。朋友游戏细节、本机绝对路径与源日志不直接打包。

### 2.4 许可证与发行边界

经用户许可选择后，修改REUSE.toml对docs和sample代码/文档/图片分组覆盖；审查压缩派生、二进制文件及参考图来源，不对未知来源整体套MIT。编写必要署名和资产清单，不公开附件照片直到其许可明确。

推荐与poet-cast一致：art-pilot大图与真实实验素材作为仓库示例，不进入wheel/sdist；通用库代码/运行schemas/template正常打包。从sdist构建wheel并在干净目录安装运行验证，测试不得依赖被排除示例。按既有惯例可将真实样例完整性测试限定仓库环境，行为测试继续使用合成fixture。

### 2.5 验证、审查与合并门禁

实施先复现两项sample失败及hash问题，添加回归，再最小修复。验证顺序：库测试→sample合成E2E→精选资产hash与隐私扫描→reuse lint→sdist/wheel构建与安装烟测→git diff --check。检查实际lint/typecheck配置，缺失就如实说明。

修改CI须作为本收口计划批准范围，保留现有OS/Python矩阵与licensing gate，只补sample覆盖及发行检查；不跳过错误、不关闭许可检查。所有本地验证退出后派发独立review，对规格、正确性、仓库一致性分别给结论。

修复提交后，经单独push授权推送feature；要求最新HEAD的全部必需CI成功，不能引用旧SHA绿灯。PR创建、合并main、删分支均需用户另行明确授权。提交范围包含完整当前feature差异，不只看收口补丁；检查已有main变更及冲突。

## [S3] 范围外

本轮不开发Codex provider执行桥、不继续生图、不训练模型、不改tactics工作区、不重写Git历史、不升级发布tag/PyPI、不自动push/开PR/合并。image-execution-providers仍是计划，不将手工探测冒称库已支持自动执行。几何/视觉尚未验收的范围不因合并而标为delivered。

## Tasks

- [ ] T1：资产/许可决策清单 — 验收：用户确认实际最终游隼、精选集、图片许可证；列出排除记录与本机留存位置。(covers: S1, S2.1)
- [ ] T2：整理压缩派生与来源清单 — 验收：所有保留PNG可解码、尺寸/alpha核对、hash匹配；无隐蔽原图bin与重复大图混入；不伪造原生成链。(covers: S2.1, S2.2; depends: T1)
- [ ] T3：修复sample运行与测试可移植性 — 验收：迁移后的sampleE2E与临时安装测试通过；新checkout不依赖作者D盘/venv，生产完整门禁回归保留。(covers: S2.3; depends: T1)
- [ ] T4：许可证、文档与发行边界 — 验收：reuse lint零缺失；sample署名/许可明确；真实素材不进入wheel/sdist；从sdist安装烟测通过，旧回执不再冒称真实执行。(covers: S2.3, S2.4, S3; depends: T2, T3)
- [ ] T5：CI覆盖与完整独立审查 — 验收：本地全部命令新鲜通过，CI配置纳入sample检查，review无关键问题；未完成provider和美术验收仍显式未完成。(covers: S2.5, S3; depends: T4)
- [ ] T6：经授权提交推送并观察最新HEAD CI — 验收：工作树/提交范围可核对，全部必需远端job成功；报告PR/合并建议，不自动合并。(covers: S2.5; depends: T5)
