# Runbook — 冻结请求与精确候选门禁

本手册是当前入口；旧记录仍是实验历史。不要运行旧 run_flow/record_generation/review_check，它们已经禁用。不要把 reviewer=dev、脚本成功或预览存在当作人审通过。

## 0. 环境

在父任务完成源码修订并重建 `D:\codes\maliang\dist` 的 wheel 后，准备依赖 wheelhouse，再重锁安装。脚本不构建或修改马良。

```powershell
# 仅下载依赖 wheel，无上传；已有离线 wheelhouse 时跳过。
python -m pip download --only-binary=:all: --dest .wheelhouse 'Pillow>=10.4,<13' 'PyYAML>=6,<7'
python scripts/lock_environment.py --source-repo D:\codes\maliang --wheel D:\codes\maliang\dist\maliang_game_art-0.1.0-py3-none-any.whl --wheelhouse .wheelhouse --dry-run
python scripts/lock_environment.py --source-repo D:\codes\maliang --wheel D:\codes\maliang\dist\maliang_game_art-0.1.0-py3-none-any.whl --wheelhouse .wheelhouse
& .\.venv\Scripts\python.exe -I -m unittest discover -s tests -v
```

从项目外验证安装，不导入源码：

```powershell
& D:\codes\art-pilot\.venv\Scripts\python.exe -I -c 'import maliang_art.production; print(maliang_art.production.__file__)'
```

锁记录的是 wheel 的真实字节哈希和观察时的源码状态，不伪造历史构建时刻。`--record-existing-test-install` 只用于记录现有测试 wheel 与源码差异，不是放行真实探索的替代方案。当前锁若为 test-only-pending-parent-rebuild，应先等待重建。

## 1. 编译 brief

用本项目的 Python 执行 `-m maliang_art design compile`，提供现有合同、草案和全新的输出目录。默认包不得包含 debug 导引作为 imageInputs；调试布局不是身份或姿态证明。保留旧包，不覆盖旧图。

后续所有 source 参数都是 **相对 --project 根目录的路径**，不是相对 design.json，也不接受绝对路径或 `..` 越界。选择独立任务 `--task-index`；不得以任意文字 prompt 替代完整 compiled prompt。

## 2. prepare（实际调用前）

先保存后端真实参数 JSON，例如明确的 size/output_format/background；未知实际模型写 unknown，不猜订阅或模型标识。

```powershell
& .\.venv\Scripts\python.exe -I scripts/production.py prepare --attempt falcon-v03 --contract characters/falcon-idle/family-contract.json --draft characters/falcon-idle/draft-v03.json --design characters/falcon-idle/design-packet-v03/design.json --parameters characters/falcon-idle/backend-params-v03.json --provider actual-provider --model unknown
```

prepare 必须提供权威合同与 Draft，使用安装包重新编译并精确核对 prompt、任务、输入图顺序/职责、acceptance、designId、targets 等执行字段；删改包以省略或降级必需项会报错。检查每张真实输入图的哈希，冻结输入图及权威合同/Draft 原字节。身份清单为编译 acceptance 的 identity ID，不另造 identity.feature 名称。未知 method/重复 ID/缺身份项报错；没有手填 required 参数。

验收提取也必须验证同一份权威输入，不需要复制输出到 prepare：

```powershell
& .\.venv\Scripts\python.exe -I scripts/production.py acceptance --contract characters/falcon-idle/family-contract.json --draft characters/falcon-idle/draft-v03.json --design characters/falcon-idle/design-packet-v03/design.json
# 兼容入口同样需要 --contract --draft --design：
& .\.venv\Scripts\python.exe -I scripts/extract_acceptance.py --contract characters/falcon-idle/family-contract.json --draft characters/falcon-idle/draft-v03.json --design characters/falcon-idle/design-packet-v03/design.json
```

编辑时仍必须提供编辑任务对应的权威 `--contract --draft --design`，再加 `--parent <精确父 attempt>` 和 `--instruction <明确修改指令>`。父源图作为第一张 edit-source，之后按原包参考顺序排列；kind=edit，完整 brief、父源图和修改指令分别留证，不把编辑说成原始生成。

```powershell
& .\.venv\Scripts\python.exe -I scripts/production.py prepare --attempt falcon-v03-edit1 --contract characters/falcon-idle/family-contract.json --draft characters/falcon-idle/draft-v03-edit1.json --design characters/falcon-idle/design-packet-v03-edit1/design.json --parameters characters/falcon-idle/backend-params-v03.json --provider actual-provider --model unknown --parent falcon-v03 --instruction '仅按用户反馈修改，保持其余身份特征不变'
```

## 3. 外部工具执行与 complete

Agent/项目执行器必须先读取 `production/attempts/<id>/prepared.json`，按其 invocation 执行真实服务，并保留真实工具回执。库和此脚本不调用服务、不证明服务确实接收图片；执行器必须真实提交冻结输入。

完成回执 JSON 格式：

```json
{
  "preparedEventId": "从 prepared.json 原样复制",
  "invocation": "这里应是 prepared.json 中完整 invocation 对象，而非字符串",
  "outcome": "success",
  "artifactSha256": "实际交付文件 SHA-256",
  "executionEvidence": "真实服务/tool 调用记录的位置和标识；不要伪造"
}
```

```powershell
& .\.venv\Scripts\python.exe -I scripts/production.py complete --attempt falcon-v03 --receipt characters/falcon-idle/receipt-v03.json --image characters/falcon-idle/raw/source-v03.png
# 服务失败（无成功图）：
& .\.venv\Scripts\python.exe -I scripts/production.py fail --attempt falcon-v03 --category timeout --message '真实错误摘要'
```

complete 必须精确匹配 prepared event、完整 invocation、成功回执、输出 SHA。人工拼一个 receipt 不能证明实际调用；不要用这种方式回填旧图。既有外部图应 `import --attempt ... --contract ... --draft ... --design ... --image ... --provenance ... [--historical]`，不会伪造 invocation 或旧时间。

导入示例（仅在获得真实素材使用授权后执行；本轮不执行）：

```powershell
& .\.venv\Scripts\python.exe -I scripts/production.py import --attempt falcon-external-v01 --contract characters/falcon-idle/family-contract.json --draft characters/falcon-idle/draft-v03.json --design characters/falcon-idle/design-packet-v03/design.json --image characters/falcon-idle/raw/external-v01.png --provenance '实际外部作者、修改来源与授权记录'
```

存储保留 `source.bin` 的 core 格式；内容是原始图像字节，Pillow 根据签名仍可解码 PNG/JPEG。不是把原图改成无法解码的二进制格式。

## 4. derive 与技术结果

```powershell
& .\.venv\Scripts\python.exe -I scripts/production.py derive --attempt falcon-v03-west --parent falcon-v03 --operation flip-x
& .\.venv\Scripts\python.exe -I scripts/production.py technical --attempt falcon-v03
```

derive 只提供 copy / flip-x 确定性操作，绑定父源与参数；不是原生 UL 生图，也不隐式接受换手。每个 attempt ID 只能创建一次。technical 实际解码图像，对包中每个必需 alpha-bounds 项运行尺寸/非空 alpha/边界检查并保存精确候选证据，不提供手填 pass 开关。不以 alpha bbox 代替核心蒙版/接点或艺术判断。未知自动方法在 prepare 报错，不能降为 human 掩盖缺能力。

## 5. 实际人类判断

人类应查看精确候选与身份/风格/姿态等全清单。由真实用户决定生成 decision-file，字段包括：

- `actorType: "human"`，`reviewer`（真实决定人的归属名称）；
- `candidate`：当前 outcome 的 eventId、attemptId、artifact 全对象；
- `identityChecklist: ["identity"]`；
- `statement`：真实决定和反馈的非空原话/摘要；
- `decidedAt`：真实带时区时间，不伪造过去时间；
- `decision`：adopt/reject/pending；
- `checklist`：design.json 全部必需 human 项的真实 pass/fail/pending/unsupported。

```powershell
& .\.venv\Scripts\python.exe -I scripts/production.py review --attempt falcon-v03 --decision-file characters/falcon-idle/human-decision-v03.json
```

Agent 不得为推进流程编写真实 human pass。合成测试 fixture 的假定人审不是生产认可。

## 6. 采用与版本安全

```powershell
& .\.venv\Scripts\python.exe -I scripts/production.py adopt --attempt falcon-v03 --asset falcon-idle --review production/events/<human-review-event>.json --result production/events/<automatic-result-event>.json
```

每个必需 automatic 结果都要传一个 --result。漏技术项、人审漏项、pending/fail/unsupported、旧人审/旧结果绑定其他候选均拒绝；候选满足全部要求可直接 adopt，无需二次生成。采用事件不可变，current/falcon-idle.json 使用 core 的原子替换投影；新版本不覆盖旧产物或记录。

## 验证边界

离线黑盒使用临时合成图片与明确的模拟执行/决定 fixture，验证路径隔离、输入顺序、全 acceptance、两版本、编辑/派生、导入/失败、门禁和原子投影。尚无真实参考图接收测试、真实视觉质量验收或真实人类采用；父任务重建后必须重锁和重跑。当前不迁移旧历史、不上传、不提交 Git、不改变 characters 原件。
