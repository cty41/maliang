---
feature: repository-audit-fixes
status: delivered
branch: fix/repository-audit-fixes
commits: 62cceff..d198fb5
---

# 全仓审查修复：数据正确性、边界与示例

## Report

**What was built** — F01–F13 已完成本地实现、回归验证与独立审查。包含内置图像步骤串联、逐步深快照、硬链接有界核验与清理失败处理、适用Review案例冲突检查、mappingVersion=2像素中心采样与接点保存检查、蒙版兼容性/越界拒绝、大图预算与预览边界、严格版本类型、示例入口与安装文档修正、运行产物Git忽略。

**Verification** — 在现有工作区 .venv 下执行 `python -m pytest tests examples/art-pilot/tests -q`：440 passed、6 skipped（Windows符号链接权限）；`python -m reuse lint`：108/108；`python -m build` 首次因PyPI TLS/超时失败，正常重试后sdist及wheel成功；`smoke_wheel.py` 使用本机离线依赖目录在临时环境安装验证37个资源成功；`git diff --check`通过。新独立review对规格/正确性/一致性未发现P1/P2。以上为原交付记录的本地验证，不是本轮重跑结果。本轮仅以本地 Git 核对合并；未联网复查远端跨平台 CI，不能用本机 skip 或 merge commit 代替链接安全覆盖。

**交付状态** — 基线 62cceff，修复代码 641d34a，文档收口 d198fb5；已由 main 合并提交 5c5fa08（PR #2，父提交 62cceff / d198fb5）纳入。原实施分支 fix/repository-audit-fixes 仅作历史定位。以下 F01–F13 是修复前问题及其验收设计，不表示当前仍存在这些缺陷；当前行为以代码和回归测试为准。此合并不代表 provider 桥或视觉验收交付。

**Journey log** —
- 每个缺陷先用合成输入复现；像素最终结果比仅检查步骤顺序更重要。
- 硬链接不能按文件名判断归属；清理失败阻止成功，但不能覆盖原始失败原因。
- 小数采样明确版本和像素中心；丢失接点拒绝，不夹紧伪造。
- 发布tag的使用指南与当前源码能力分开，不移动旧tag。

## [S1] 问题与基线

范围为全仓只读审查的13项发现，11项P2和2项P3。审查代码HEAD458c667与origin/main62cceff文件树一致；规划时工作树干净。历史基线为356 passed / 6 Windows symlink skipped、REUSE107/107，并非修复后的验证结果。

规划沿用已选D:\codes\maliang工作区，仅新增此规格。不在已合并feature分支继续实施：实现前刷新main，基于明确的最新main创建fix/repository-audit-fixes工作分支，默认独立worktree；若环境隔离拒绝则报告，由用户/主编排器处理，不能绕过策略。规划文件须带入实际实现工作区后更新branch。

## [S2] 状态机步骤与证据快照（F01、F02）

F01：machine.py当前把同一原始image_path传给每一步。当output不同于input时，align-canvas重新读取原图并覆盖去幕输出。

修复：为内置图像步骤定义明确的输出传递契约，成功返回output后下一步使用该图作为输入。非图像步骤不凭任意detail字段猜测文件；保留既有公共返回记录结构，不创建通用数据流框架。步骤异常不得记录为成功，不承诺本轮实现跨步骤事务回滚。文档写清中间输出及overwrite边界。

验收：4×4品红图去幕后再对齐、输入输出不同，最终alpha为零；相同路径与单步不回归；中间插入非图像步骤仍传递正确；失败步骤不返回成功转换。

F02：dict(detail)浅拷贝导致调用方/自定义步骤修改嵌套列表后，旧记录内容变而ID不变。

修复：在收集每步证据时做独立深快照，不能只在所有步骤结束后复制；后续步骤不得通过共享对象修改前步证据。维持JSON合法性检查与现有ID算法，对等值输入的ID不变。不将公开dict可被调用方主动修改包装成不可变保证。

验收：调用后修改context列表、step持有字典，以及后续step修改共享对象均不改变前步记录；以原转换字段重算ID一致。

## [S3] 不可变发布与案例冲突（F03、F06）

F03：core.py凭临时命名模式放行既有硬链接。修复不能把文件名当所有权证明，不能删未知alias。发布前存在的任意别名包括.tmp伪装必须拒绝；真正本次/并发发布短暂alias需有可验证归属或有界等待消失后重新核验。继续满足已支持的并发同内容幂等、不同内容collision、Windows路径约束；不新增服务型锁系统，不降低SECURITY承诺。

验收：预先创建.record.bin.preexisting.tmp硬链接后相同内容发布失败；无别名幂等成功；并发同内容发布无误报、异内容失败；不删除用户alias、不改目标字节。测试覆盖线程及独立进程的现有支持范围；若无法同时保证则停止该切片并报告，不能靠文档淡化绕过。

F06：review.py只对rule做冲突检测，case同ID/version不同artifact可同时进入policy。

修复：在适用case集合冻结前检查稳定身份；完全相同重复条目去重，不同内容同caseId/version拒绝；同caseId多个适用版本不得让无版本acceptanceCaseId歧义通过，应明确拒绝，历史不适用case仍按现有scope/lifecycle过滤。输入排列不影响合法policy的ID。

验收：双冲突图重现失败；相同重复幂等；调换不同唯一case顺序ID稳定；scope外历史不误阻塞；不重写旧policy文件。

## [S4] 几何映射与蒙版安全（F04、F05）

F04：图片resize维度分别取整，接触点却直接乘请求scale，可能成功返回越界点。

修复：定义统一的像素坐标约定（点代表像素中心），由同一名义等比变换驱动图像、蒙版与接触点，整数输出尺寸仅作采样范围，不引入未声明的独立x/y拉伸。若使用既有resize路径，必须记录并正确处理其实际采样映射，不能继续声称不同映射相同。所有变换后接触点必须做有效性/越界检查，不可静默clamp到边缘伪造接地。请求缩放、有效采样和整数平移的记录含义明确；变更序列化字段时保留兼容或新版本，不静默改历史含义。

验收：审查5×7、0.5倍、2×4目标的接点用例，不再返回越界成功；增加非方形、0.5/1.5倍、identity/整数倍与边缘标记点/蒙版一致性测试。无法保留的接触点明确报错，而不是掩盖采样丢失。

F05：仅检查图像alpha越界，mask可被静默裁剪。

修复：输入验证明确核心mask像素须与候选有效像素相容；全部参与变换的mask占用也须在目标画布内，异常在paste前失败。空蒙版/尺寸不等/无核心继续按既有异常；不从alpha推断核心。

验收：审查8×8→3×3、scale1使core宽5→3的例子必须拒绝；合法带尾翼图片与mask一致变换；无mask仍不宣称core通过。

## [S5] 图像资源预算与姿态边界（F07、F08、F09）

F07：pose接受8192画布，但默认半尺寸预览超4194304像素上限。

修复：省略preview size时等比选择不超过现有像素预算的尺寸，兼容小画布默认半尺寸；用户显式超预算尺寸仍拒绝。保留全部形体而非裁切；API/CLI说明默认缩放规则。

验收：8192²合法草案可产出受限默认预览；窄长画布也受限；显式超预算失败；正常256默认128保持。

F08：audit_alpha_bounds先RGBA解码后比尺寸，derive镜像无显式像素预算。

修复：先读取header，尺寸不符直接返回失败和原始尺寸，尚未计算的alphaBounds显式为空；不要伪造alpha结果。必须解码时受明确像素预算限制，默认不高于authoring当前最大画布2048²；derive同样先预算检查。不要全局禁用Pillow保护，超限使用现有错误通道返回。未来高分辨率需求通过明确扩展而非无界分配。

验收：12000²header假对象的convert哨兵不被触发；真实小图正常；大小匹配但超预算也拒绝；mirror先检查再解码；截断或无效图清楚失败。

F09：pose schemaVersion=true因Python相等规则被接受。

修复：draft/card严格区分bool与整数，允许int1拒绝true；schema/runtime对照测试覆盖true,false,1,0,2及错误类型。

## [S6] 文档、入口与误发布保护（F10–F13）

F10：README安装v0.1.0却展示flow命令，policy schema标识指向该tag不存在文件。

修复：双语文档分别说明已发布tag与当前源码功能，flow/design新功能给出可执行源码安装步骤；不移动旧tag或承诺新发行。schema标识采用稳定且可解析的项目定位或非URL稳定ID，不伪造旧tag资源；调整引用和测试。

F11：extract_acceptance在全部参数前插入子命令，--project失效。

修复：正确解析并转发全局project和子命令参数，支持文档调用；不复制production验收逻辑。测试从仓库外临时目录运行，自定义project路径含空格，验证确实读取该project；未知参数仍报错。

F12：本机锁与运行产物未被Git忽略。

修复：精确忽略examples/art-pilot/maliang.lock.json、examples/art-pilot/production/、work/art-pilot/及此工作流明确产生的临时产物。不能用全局*.json/*.png误排公开资产或schemas。说明忽略不追溯删除已tracked文件、不代替发布审查。

验收：git check-ignore --no-index命中上述私有路径，精选images/assets.json/schema未被忽略；不提交真实私有fixture。

F13：design_trial仍读取已移除draft-partial。

修复：默认使用随仓draft-example.json，允许显式指定草案，路径与项目入口一致。当前falcon教学brief可通过，不调用生图；缺文件仍清楚报错。

## [S7] 实施、验证与审查

每项先用合成输入复现，再写回归、小修复；不为绿色测试放松门禁。实现并行边界：A machine/core/review；B geometry；C pose/authoring图像预算；D docs/sample（production mirror与C协调，避免同文件并行编辑）。

阶段顺序：数据处理和证据正确性优先（S2–S4），随后资源边界和使用体验（S5–S6）；独立模块可并行，最后统一集成。

验证命令：

- python -m pytest tests examples/art-pilot/tests -q
- python -m reuse lint
- python -m build
- python examples/art-pilot/scripts/smoke_wheel.py --wheel <本次生成wheel>
- git diff --check；补充sdist中无真实sample图片/生产记录、wheel资源完整性检查。

本地受限符号链接测试若skip应如实报告，Windows/Linux/macOS CI核对原矩阵；不可用本地skip证明安全用例通过。读取项目lint/typecheck配置，未配置不虚构结果。

全部验证退出后独立review，分别检查规格、正确性与一致性，回归证据对应F01–F13。未解决项保持未完成。只做文件与代码修复，不调用真实生图、不修改用户素材。

## [S8] 范围外与交付

不开发provider自动执行、不重构整个管线、不改tactics、不重压资产、不移动release tag、不重写已有记录/历史、不绕过安全限制。

批准计划不自动授权push/PR/merge。完成后列出修复提交/分支/工作区、验证、未完成项，再按用户明确授权执行提交或远端操作。

## Tasks

- [x] T1：修复图像步骤传递与嵌套证据快照（F01/F02）— 验收：最终像素证明去幕未丢失，外部与后续步骤修改不改变先前记录/ID。(covers: S2)
- [x] T2：关闭伪装临时硬链接放行（F03）— 验收：既有alias拒绝、不删别名，同时并发幂等测试保持。(covers: S3)
- [x] T3：拒绝冲突Review案例（F06）— 验收：同身份冲突拒绝、完全重复去重、合法顺序无关。(covers: S3)
- [x] T4：统一几何采样/接点映射与mask边界（F04/F05）— 验收：小数缩放不返回越界成功，mask不静默裁切，普通等比路径不回归。(covers: S4)
- [x] T5：姿态默认预览和schema版本边界（F07/F09）— 验收：大画布默认预览受限成功，bool版本拒绝。(covers: S5)
- [x] T6：图像检查/镜像解码前预算（F08）— 验收：超大header无需分配即失败，正常技术检查保持。(covers: S5)
- [x] T7：发布文档与schema引用纠偏（F10）— 验收：tag和源码命令边界明确，无不存在tag资源标识。(covers: S6)
- [x] T8：修复示例project转发与草案入口（F11/F13）— 验收：临时project验收提取成功，随仓falcon教学草案试跑成功。(covers: S6)
- [x] T9：Git运行产物隔离（F12）— 验收：私有运行路径被忽略，公开素材/配置仍可跟踪。(covers: S6)
- [x] T10：集成验证、独立审查、文档收口 — 验收：完整测试/许可/构建/安装通过，逐项关联13个发现，无关键review问题，远端操作另经授权。(covers: S1, S7, S8; depends: T1,T2,T3,T4,T5,T6,T7,T8,T9)
