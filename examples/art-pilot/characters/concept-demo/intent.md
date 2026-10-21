# concept-demo

合成示例角色“示例苍鹭”，只用来演示原画与游戏内资产双轨的记录链：“设定原画 → 认人特征清单 → 胶囊资产与半身头像”。它不是任何项目的真实角色。

本目录只有意图和记录，没有任何生成图。两张原画都处于 pending 状态，等待用户单独授权生图，并由人工定稿。

## 两种形态

- base：常态，拟人苍鹭，手持短杖。
- alt-form：展翼形态。特征清单中的 `wing-span` 只适用于这一形态（`forms: ["alt-form"]`），用来演示确认问答按形态过滤特征。

## 两条轨道

- 原画：淡墨线描的单人全身，纸底。见 `records/concept-style-guide.json`。
- 游戏内资产：胶囊、粗描线、isometric。见 `family-contract.json` 和 `draft-example.json`。
- 两条轨道只通过 `records/identity-markers.json` 连接。生成胶囊资产时，不把原画当参考图输入。

## 半身对话头像

从常态原画定稿图中裁切，见 `records/portrait-bust.json`。裁切框要等原画定稿、尺寸确定后再填写，并由人工审批。

## 禁止

- 自动生成原画，或自动写入审批结果。
