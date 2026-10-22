# 小橙子：从一句话到采用的精灵图

[English](README.md)

这是 2026-10-22 在 Cursor 里真实跑的一次 MaLiang 流程。生图宿主是
`cursor-desktop`（GenerateImage，模型未知），回执是 `host-agent-attested`，
即 agent 自述，不是机器观测。图片按交付原样保留，被拒的也留着，用来展示决策过程，
不是一张完美的成品。生产事件库留在私有的 `work/` 项目里，这里只收录输入、记录、
提示词和图片。

## 1. 需求与 intake

用户只说了一句：“请为我画一个 小橙子 agent 的形象 它是一个程序员 他快乐又毒舌”。

agent 先说明这次走 MaLiang，然后逐个维度提问。[intake.json](intake.json)
记录了答案：游戏资产、2D、RPG、正面视角、Q 版、线稿平涂、双轨（原画加生产精灵图）、
古典线描原画风格、宣传优先、明亮配色、现代题材。第一次 intake 选错了类型，
已答维度不可修改，所以另开了一份新的 intake。

## 2. 原画轨

| 原画 | 提示词 | 图片 | 人工决定 |
|---|---|---|---|
| `little-orange-base` | [concept-prompt.txt](concept-prompt.txt) | [concept/base.jpg](concept/base.jpg) | 拒绝 |
| `little-orange-base-v2` | [concept-prompt-v2.txt](concept-prompt-v2.txt) | [concept/base-v2.jpg](concept/base-v2.jpg) | 批准 |

v1 的修改意见记在 [records/concept-base.json](records/concept-base.json)：
橙皮太写实；帽衫是刻板印象；身体应该就是橙子本身，配很小的 Q 版手脚。
这三点写进了 [records/concept-style-guide.json](records/concept-style-guide.json)
的风格规则和 v2 提示词。原画提示词没有冻结和哈希，这是已知缺口。

从批准的 v2 冻结了 [records/identity-markers.json](records/identity-markers.json)：
必需项是橙子身体、歪向一侧的叶子、单边反光的方框眼镜、Q 版手脚；笔记本是可选项；
配色 `#F7931E`、`#4CAF50`、`#3FD3E0`。

## 3. 生产轨

[design/family-contract.json](design/family-contract.json) 和
[design/draft.json](design/draft.json) 编译成
[design/design.json](design/design.json)。其中的 `prompt` 就是原样交给
GenerateImage 的文本；原画不作为参考图输入（`imageInputs` 为空）。

| 尝试 | 图片 | 结果 |
|---|---|---|
| `orange-front-001` | [candidates/orange-front-001.jpg](candidates/orange-front-001.jpg) | 画出了假棋盘格而不是透明，笔记本上有水果标志；技术检查失败，人工拒绝 |
| `orange-front-002` | 无 | agent 填错角色名和宿主名；记为操作失误，从未发出 |
| `orange-front-003` | [candidates/orange-front-003.jpg](candidates/orange-front-003.jpg) | 纯色品红背景、无标志；JPEG 没有透明通道，技术检查按预期失败 |
| `orange-front-003-sprite` | [candidates/orange-front-003-sprite.png](candidates/orange-front-003-sprite.png) | `derive --operation matte-resize --tolerance 40`，按四角取背景色 `#F50696`；技术检查通过，用户用 `review-quick` 通过，已采用 |

这里收录的是 003 版设计：新增 `flat-key-background` 规则，并禁止
`checkerboard-background` 和 `brand-logo`。Cursor GenerateImage 没有透明背景参数，
所以先画纯色底再做确定性抠图，才能得到真正的透明通道。

## 这次实跑给 MaLiang 带来的改动

- `review-quick`：用户只需选通过或不通过，可选勾问题和写意见；评审人和时间自动填写。
- `preview`：输出绝对路径和扩展名正确的查看副本，因为聊天界面显示不了 `work/` 里的图。
- `orange-front-002` 的拼写错误促成了 `--new-character` 校验。
