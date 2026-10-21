---
feature: new-user-trial-red-panda
status: designed
branch:
commits:
---

# 新用户试用清单：小熊猫德鲁伊

## Report

**状态核对**：本文只是试用脚本，尚未执行。试用由用户本人在全新会话中扮演新用户完成，agent 不代为执行、不预先生成任何图片，也不预先写入问询答案或审批结论。

## [S1] 目的

- 按新用户的真实路径走一遍马良：从一句宽泛的需求出发，经过美术方向问询、水墨原画、确认问答、认人特征，最后到胶囊游戏小人。
- 顺带检验 Cursor 的生图功能（GenerateImage）能否在这个流程里正常出图、展示和落盘。
- 仓库里不放小熊猫的任何记录。合成示例 `examples/art-pilot/characters/concept-demo/` 与小熊猫无关，agent 不应把它当作答案照抄。

## [S2] 准备

- 开一个全新的 Cursor 会话，工作区为马良 checkout 根目录。产物应放在 `work/red-panda-trial-001`，该目录已被 Git 忽略。见 [仓库即默认工作区](repo-as-workspace.md)。
- 附上自己拍的小熊猫展馆照片，作为物种参考。
- 设定只给两条：鼬之一族（虚构族名），职业德鲁伊，无变身形态。

开场提示词（原样发送，不额外解释马良的用法）：

> 我想用马良做一个小熊猫德鲁伊，先出水墨原画，再做游戏里的小人。

## [S3] 预期步骤与观察点

1. **分流、技能触发与复述**：agent 按 `AGENTS.md` 的分流读取 `skills/maliang-art/SKILL.md`，复述需求，说明接下来先问询。
   - 观察：是否读取了 skill，有没有把请求当成修改马良代码的开发任务；产物目录是否选在 `work/` 下；有没有直接开始生图；复述有没有加入你没给的设定。
2. **美术方向问询**：agent 用 `intake start` / `intake next` 出选择题，并通过提问工具提问。
   - 观察：第一题是不是最终用途；每个选项是否写明后果和风险；视角题是否给出 isometric、横版、俯视、正面四种，并且风险说明不再写“只支持 isometric”；自由填写题（如主题）是否让你自己写，或在你同意后才采纳 AI 建议。
3. **生图授权与 Cursor 出图**：agent 先写 `concept-style-guide` 和 `character-concept`（pending、image 为 null），并在生成水墨原画前明确征求授权。
   - 观察：是否先问再生成；GenerateImage 是否出图、图片是否在会话里展示、文件存到了哪里；画面是否是拟人小熊猫、水墨基调、单人全身、纸底。
4. **原画确认问答**：agent 运行 `concept review --format questions`，把三道题交给提问工具：风格检查多选、认人特征多选、结论单选。
   - 观察：题目是否能看懂；你作答之前，agent 是否没有执行 approve；approve 写入的审批人是否是你的 git 身份，`reviewerSource` 是否正确；选“需修改”时不满足项是否写进 note。
5. **冻结认人特征**：agent 从定稿原画提炼 `identity-markers`，每条写明 `capsuleTranslation`，冻结前请你确认。
   - 观察：是否抓住小熊猫的关键特征（红棕色毛、白色脸斑、泪痕纹、环纹长尾、深色四肢）；是否误写成熊或鼬科。
6. **从特征生成胶囊 draft**：agent 用 `markers_to_identity` 生成 draft 的 identity。
   - 观察：水墨原画是否没有被当作胶囊资产的参考图（`imageInputs` 里不应出现原画）。
7. **design compile 与生产门禁**：agent 写家族约定和 draft，运行 `design compile`，再按 runbook 走 `--provider cursor-desktop` 的 prepare、cursor-packet、GenerateImage、cursor-complete，以及后续审核门禁。
   - 观察：选正面视角时，提示词里是否有白话的 `cameraGuide`，不用的方向是否标为 not-applicable；每次生图前是否再次征求授权；门禁是否在需要人工判断的地方停下。

## [S4] 已知缺口

- 在自己的游戏项目里开会话时，马良的 `AGENTS.md` 不会加载，需要手动告诉 agent skill 路径。本次试用不覆盖这种情况。
- 原画轨道没有冻结的生图任务包。第 3 步由 agent 直接调用 GenerateImage，提示词和参数不会像胶囊资产那样被冻结、记录哈希。试用时请记下 agent 实际使用的提示词。

## [S5] 问题记录

| 步骤 | 现象 | 期望 | 严重程度（阻断 / 严重 / 一般 / 建议） |
| --- | --- | --- | --- |
|  |  |  |  |
