---
feature: concept-art-dual-track
status: designed
branch:
commits:
---

# 原画与游戏内资产双轨

## Report

**状态核对**：已实现记录、校验与示例。合成示例 concept-demo 停在“原画待人工定稿”，还没有生成任何原画或资产图，也没有任何人工审批。所以本文仍然只是 designed，不代表端到端已经交付。

## [S1] 问题

原画和游戏内资产可以风格差异很大，参考《最终幻想》的天野原画配像素小人，以及《灌篮高手》彩稿配 Q 版。这种情况下，原画不能当胶囊资产的风格参考图，否则笔触和比例会污染资产。能从原画传到资产的，只有“认人特征”：物种轮廓、服饰配色、武器、配饰、印记，以及变身后仍要保留的特征。

## [S2] 设计

- 两份风格规则：原画用 `concept-style-guide`；游戏内资产沿用 `art-family-contract`，不做改动。
- `character-concept` 记录每个形态的原画，比如常态和变身。审批只能由人工写入：pending 状态不能填写审批人，approved 状态必须绑定图片和审批人。
- `identity-markers` 是两条轨道之间唯一的桥。每个特征都写明 `capsuleTranslation`；状态为 frozen 时，引用的原画必须全部已审批。
- `derived-usage` 记录半身对话头像（必须有裁切框，且不能超出原画尺寸）和宣传用途。
- 确定性检查只覆盖结构、引用、裁切框范围、draft 是否带齐必须保留的特征，以及色板容差；色板检查的颜色计数由调用方提供。“像不像”只能人工审批。
- 确认流程：`concept review --format questions` 输出三道确认题，由 agent 交给提问工具（没有提问工具时用 Markdown 确认单原样贴到会话里）；用户回复后，agent 运行 `concept approve` 写入结论，审批人自动取 git 身份或操作系统登录名，并在 `reviewerSource` 里记录来源。不要求正式签字，但必须有人明确确认。
- 不涉及生图。每次实际生图前都要用户单独授权。

## [S3] 验证：新用户试用

记录链的结构由合成示例 `examples/art-pilot/characters/concept-demo/`（示例苍鹭，两种形态）演示，它不是真实角色。端到端验证改为由用户在新会话中模拟新用户试用，角色为小熊猫德鲁伊，步骤和观察点见 [新用户试用清单：小熊猫德鲁伊](new-user-trial-red-panda.md)。agent 不代为执行试用。
