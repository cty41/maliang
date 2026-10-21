---
feature: repo-as-workspace
status: designed
branch:
commits:
---

# 仓库即默认工作区

## Report

**状态核对**：`AGENTS.md` 已改为路由器，`.gitignore` 已忽略整个 `/work/`，并有文档测试覆盖。新用户在仓库里开会话能否被正确分流，要等小熊猫试用（见 [新用户试用清单](new-user-trial-red-panda.md)）验证，所以本文仍为 designed。

## [S1] 决定

马良的源码 checkout 同时是开发者和使用者的默认工作区。skill、runbook、schema 和命令行都只在 checkout 里，Agent 在同一个目录里就能拿到全部所需，不需要另行配置 checkout 位置。

本决定取代 [Agent 使用文档](agent-usage-documentation.md) 中“根 AGENTS.md 只给修改马良代码的 Agent”的定位。

## [S2] 分流

- 自动加载的 `AGENTS.md` 开头先分两类请求：
  - 使用马良做图、改图、审图：先读 `skills/maliang-art/SKILL.md` 并照做；
  - 修改马良本身：遵守开发规则。
- 生图、审批、提交、发布等边界条款两类请求都适用，写在分流之后、开发规则之前。

## [S3] 产物位置

- 使用者的资产项目放在 `work/` 下的新目录，例如 `work/red-panda-trial-001`。
- 整个 `/work/` 被 Git 忽略，避免把用户的原画和记录误提交进马良仓库。
- 代码跟随 `git pull` 更新；`work/` 里的内容归使用者，记录都带 `schemaVersion`。

## [S4] 暂不覆盖

- 在自己的游戏项目里开会话时，马良的 `AGENTS.md` 不会加载，需要手动把 skill 路径告诉 Agent。
- 不提供 init 命令，也不把 skill 安装到宿主的自动发现位置。

## [S5] 重新评估的条件

出现以下任一情况时，重新评估是否把使用工作区与源码仓库彻底分离：

- 有人需要在自己的游戏项目里使用马良；
- 升级马良（`git pull`）和用户产物发生冲突；
- 同一个会话里，开发请求和使用请求互相干扰。
