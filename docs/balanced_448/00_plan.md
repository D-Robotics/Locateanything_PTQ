# LocateAnything balanced_448 batch-1 分阶段计划

## 目标

在不修改 `fast_336` 和 `stable_672` 配置、Scale、HBM 及板端运行目录的前提下，建立 `448 x 448`、Batch 1 的独立 W8A8 Profile。该 Profile 以提高相对 `fast_336` 的检测精度为目标，但在 Float、HBM 和 S600 对照完成前只称为候选档，不预先声明精度提升。

## 固定契约

| 参数 | balanced_448 |
| --- | ---: |
| Batch | 1 |
| Image | 448 x 448 |
| Patch Size / Merge Size | 14 / 2 |
| Patch Grid | 32 x 32 |
| Patch 数量 | 1024 |
| Visual Token | 256 |
| Vision 输入 / 输出 | `(1,1024,588)` / `(1,256,2048)` |
| Resize | stretch |
| Prefill | 384 |
| 文本位置容量 | 128 |
| KV Cache | 1024 |
| Runtime max new tokens | 640 |
| Calibration max new tokens | 1024 |
| PBD / AR | q6 / q1 |
| 量化 | W8A8，独立 1200 条 Scale |

`384 + 640 = 1024`，因此运行时生成上限不超过 KV Cache 契约。`448 / 14 = 32`，经 `2 x 2` Patch Merge 后得到 `16 x 16 = 256` 个 Visual Token。已有 Float 筛查中最长非视觉 Prompt 为 70 个 Token，Prefill 384 可容纳 256 个 Visual Token 和该文本 Prompt，并留出 58 个位置。校准标准答案完整保存，不按运行时 KV 容量截断。

## 隔离路径

- 编译配置：`compiler/config/balanced_448.yaml`
- 编译输出：`compiler/outputs/balanced_448_batch1_stretch_prefill384_cache1024_w8_fused_prefill_compact_logits/`
- 板端模型：`inference/models/balanced_448/`
- 板端输出：`inference/outputs/balanced_448/`
- 阶段记录：`docs/balanced_448/`

禁止复用 `fast_336` 或 `stable_672` 的激活 Scale、Vision HBM、Language HBM、BC、HBO 和运行输出目录。

## 阶段与门槛

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| 1 | stretch、KV 1024、形状、Batch 1、路径隔离和 dry-run | 进行中 |
| 2 | 448 Float 精度对照 | 旧 letterbox 筛查仅作历史参考；stretch 结果重新验证 |
| 3 | 1200 条 Prepare、校准、激活统计与收敛审计 | 已授权，重新执行 |
| 4 | Vision Float -> Eager -> BC -> Converted BC -> HBO -> HBM | 已授权，校准通过后执行 |
| 5 | Language Float -> Eager -> BC -> Converted BC -> HBO -> HBM | 已授权，校准通过后执行 |
| 6 | S600 ABI、数值、任务精度、时延与资源验收 | 已授权，HBM 审计通过后执行 |

## 精度验收原则

1. 使用带官方标注的固定检测样本比较 `balanced_448`、`fast_336` 和 `stable_672`，报告 Precision@0.5、Recall@0.5 和匹配 IoU。
2. `balanced_448` 必须在 Precision@0.5 和 Recall@0.5 上均不低于 `fast_336`，且至少一项有实质提升，否则不进入正式构建。
3. 无人工标注的视频对照只报告框数、匹配率和位置一致性，不把 672 输出当作 Ground Truth。
4. 量化阶段逐级比较相同输入的输出；HBM 加载成功、非零 logits 或产物存在都不等于验收通过。
5. 最终 S600 使用相同图片、Prompt、生成模式和 NMS 参数，对比 Float Slow 与 HBM Slow 的 token、box、停止原因和坐标有效性。

## 1200 条校准验收

- 输入固定为 1200 个唯一 `bundle_id`，图片缺失、重复和任务计数均为 0 异常。
- 任务覆盖 Detection、GUI、Referring、OCR、Layout 和 Pointing。
- Prepare 1200/1200，Profile 与 Vision 输入输出形状错误为 0，Prompt 不超过 Prefill 384。
- Vision 1200/1200；Language 1200/1200，并回放真实 Prefill、PBD q6 和 AR q1 状态机。
- 激活统计无未执行点、非有限值、非法 Norm 或零 Absmax；动态量化 Vision 按组件契约审计。
- 使用完整 1200 样本最终 Scale，不用检查点 Scale 替代。

本目标已于 2026-08-20 获得端到端执行授权。配置或输入发生漂移时必须停止，不得静默继续。
