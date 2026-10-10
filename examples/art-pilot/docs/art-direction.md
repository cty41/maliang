# 美术方向与精选素材

本示例保留用户选定的 Codex 游隼、凤头鹰和一份诗人风格参考。图片署名 **cty41**，许可 **CC-BY-4.0**；代码、示例输入和文档为 MIT。逐文件来源/派生哈希、尺寸、处理参数见 [assets.json](../assets.json)，署名见 [ATTRIBUTION.md](../ATTRIBUTION.md)。

## 精选集

| 用途 | sample 相对路径 | 入库处理 |
|---|---|---|
| 游隼静立，选定的 Codex 版本 | `characters/falcon-idle/raw/codex-idle.png` | 1254×1254 → 512×512 RGB，LANCZOS |
| 凤头鹰静立 | `characters/crested-goshawk-idle/raw/v01-a001.png` | 1254×1254 → 512×512 RGB，LANCZOS |
| 共用诗人风格参考 | `characters/shared/poet-idle-dr-style.png` | 256×256 RGBA，原字节保留 |

鸟图对比了 RGB、64 色、256 色 MEDIANCUT 无抖动版本的小图。64 色会损失眼部与轮廓色差；选用 RGB 缩图以保留细节、渐变及源图背景纹理，接受更大的文件。缩放是有损派生，不称无损。未裁图、抠图、去除可见标记或做 alpha 修复；鸟图仍是不透明品红背景，诗人参考保留原 alpha。

鸟图源文件的 `caBX`、`eXIf`、`iTXt` 块逐字节保留，包括平台来源信息。嵌入的尺寸和签名属于原图，不能验证缩图为原始签名内容；新来源清单不是生成回执或 C2PA 重新签名。

## 风格与验收边界

- 胶囊体型、粗深色轮廓、紧凑静立姿态，优先让小尺寸下读出鸟类轮廓。
- 诗人仅用于风格参考，不能复制其犬类身份、四肢或配色为鸟类特征。
- 选定视觉方向不代表几何、朝向、alpha、锚点或生产门禁已通过。图上仍有渐变和背景纹理，也不能把合同中的硬边色块目标冒充已满足。
- `characters/falcon-idle/draft-example.json` 是整理后新建的教学 authoring brief：借用旧意图结构，绑定当前共用参考的路径与哈希。它不是选定 Codex 图的实际输入，不是对旧请求的历史更正或生成证据。
- `family-contract.json` 是将来试作的目标约束，不是对这些 512px 展示图的检验结果；其 1024px source、256px output 等约束须由新的独立运行满足。

## 历史隔离

旧 V03 invocation/delivery/review/transition、整个 production 存储（含 source.bin 和 inputs）、V04 请求/结果、凤头鹰历史请求、本机 lock、失败 V03 图及重复参考已从公共 sample 移除。对应原始实验文件在维护者本机原实验工作区保留，运行本示例不需要它们。

旧 V03 回执曾错误宣称已提交图片参考；实际未提交参考图，实际 prompt 与冻结包也不一致。因此不保留为可执行生产证据，也不改写哈希将它伪装成新图的回执。V04 与 Codex 外部试作不补造完整生成链。Git 既有历史未重写。

本机 `maliang.lock.json` 不再分发；需要精确 wheel 校验时，使用 `scripts/lock_environment.py` 为当前安装生成新本机锁。所有新运行的审核、回执与产物写入独立本机工作目录，不回填到这些展示资产上。
