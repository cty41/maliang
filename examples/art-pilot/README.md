# Art Pilot

项目本地的受控视觉探索与生产记录试点。工具回归通过不代表角色设计通过；当前未导入真实参考图、未调用真实图像服务、未进行真实人审或正式采用。

## 独立环境与构建锁

使用本项目 `.venv` 安装 wheel，禁止 editable install、`PYTHONPATH` 或源码路径注入。`maliang.lock.json` 记录 wheel SHA-256、基线提交、观察到的 dirty 状态和安装文件核对。基线 `55320d6` **不包含新增未提交模块**，不能把它当作新代码的提交钉。

当前 wheel 已重建并锁定，源码与已安装包的全部资源（含 schemas、模板）核对通过。后续变更须运行 `scripts/lock_environment.py` 重新锁定并重跑黑盒测试；它默认拒绝陈旧 wheel，已有 `.venv` 解释器时直接复用，不重建正在运行的解释器。详见 [运行手册](docs/runbook.md)。

## 当前入口

- `scripts/production.py`：prepare → 外部真实执行 → complete / fail；另有 import、derive、technical、review、adopt。
- prepare、编辑准备、import、acceptance 提取都必须提供 `--contract <家族合同.json> --draft <草案.json> --design <design.json>`；使用安装包重新编译并核对执行字段，不能用删改过的 packet 省略必需项。
- 完整 compiled prompt、任务、参数与真实参考图哈希/顺序冻结；权威合同和 Draft 原字节同时冻结，不接受手填 `--required-*`。
- `alpha-bounds` → automatic；human → human；未知方法或重复 ID 报错。身份清单使用编译包的 `identity` ID。
- 原图与版本事件不可覆盖；采用只更新原子 current projection。旧候选证据不适用于新候选。
- `record_generation.py`、`run_flow.py`、`review_check.py` 已禁用；旧图片和历史记录原样保留，不迁移或改写。

技术检查只证明对应谓词，不能代替风格、身份或姿态的人类判断。reviewer 是记录归属，不是自动批准权限；Agent 不得自称人类或生成真实批准证据。

## 离线回归

```powershell
& .\.venv\Scripts\python.exe -I -m unittest discover -s tests -v
```

测试在临时目录使用合成 PNG、模拟 receipt 与人工决定 fixture，包括两版本、编辑分支、派生、缺技术证据拒绝、旧人审错配拒绝及完整门禁后直接采用。测试批准仅属于合成 fixture。
