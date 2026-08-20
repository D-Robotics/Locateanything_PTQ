# Stage 3 Gate: balanced_448 1200 条校准

## 状态

用户已于 2026-08-20 授权端到端执行。旧 letterbox/cache2048 Prepare、Calibration 和部分 BC 仅保留审计，不用于最终 stretch/cache1024 Profile。

## 已核对环境

| 项目 | 当前值 |
| --- | --- |
| 主机 | `DG-4090-Office` |
| GPU | NVIDIA GeForce RTX 4090，24564 MiB |
| 检查时空闲显存 | 24126 MiB |
| `/home` 可用空间 | 约 1.1 TiB |
| 其他校准/编译进程 | 未发现 |
| Float Python | `/home/kangjie.xu/miniforge3/envs/locateanything/bin/python` |
| PTQ Python | `/home/kangjie.xu/miniconda3/envs/locateanything_ptq/bin/python` |

## 只读输入

模型和数据继续使用已核验的现有输入目录，但通过远端运行 YAML 中的绝对路径显式引用，不建立 symlink、不复制模型或数据、不修改输入目录。

| 输入 | 路径 / 结果 |
| --- | --- |
| Checkpoint | `/home/kangjie.xu/oe_locateanything/fast_336_checkout/Locateanything_PTQ/compiler/models/LocateAnything-3B` |
| Checkpoint | 51 个文件，7796167047 bytes |
| Calibration data | `/home/kangjie.xu/oe_locateanything/fast_336_checkout/Locateanything_PTQ/compiler/datasets/calibration/locateanything/source` |
| 数据目录 | 1208 个文件，324986878 bytes |
| `selected.jsonl` | 1200 行，SHA256 `521c9203579b165b619934684ca0dd44f9a33dc9c68e0bb6abb17f481d17850b` |
| 唯一 `bundle_id` | 1200，重复 0 |
| 图片 | 1200，缺失 0 |

任务分布：

| Detection | GUI | Referring | OCR | Layout | Pointing | Total |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 660 | 150 | 120 | 120 | 90 | 60 | 1200 |

## 独立输出

```text
/home/kangjie.xu/oe_locateanything/balanced_448/Locateanything_PTQ/
  compiler/outputs/
    balanced_448_batch1_stretch_prefill384_cache1024_w8_fused_prefill_compact_logits/
```

检查时远端 worktree 和输出目录均不存在。确认后先推送本地 `balanced_448` 分支，再从该分支创建远端独立 worktree。远端运行 YAML 为完整配置，只将 `checkpoint`、`calibration_data` 和 `output_dir` 改成以上显式绝对路径；保存配置 SHA256 和解析摘要后冻结，不在任务运行中切分支、pull、改配置或改输出目录。

## 拟执行命令

Prepare：

```bash
/home/kangjie.xu/miniforge3/envs/locateanything/bin/python \
  compiler/quantize.py \
  --config /home/kangjie.xu/oe_locateanything/balanced_448/run_config.yaml \
  prepare
```

Calibration：

```bash
/home/kangjie.xu/miniconda3/envs/locateanything_ptq/bin/python \
  compiler/quantize.py \
  --config /home/kangjie.xu/oe_locateanything/balanced_448/run_config.yaml \
  calibrate --max-samples 1200 --checkpoint-samples 512
```

两条命令串行执行。Prepare 成功并完成输入、Profile、张量和记录审计后，才启动 Calibration。按 336 历史耗时和 448 张量规模估计，Prepare 约 15 至 25 分钟，Calibration 约 20 至 40 分钟；以实际完成日志为准。

## 必须解析的配置

```text
image=448x448
vision_input=(1,1024,588)
vision_output=(1,256,2048)
visual_tokens=256
chunk_size=384
cache_len=1024
batch_size=1
runtime.max_new_tokens=640
calibration.max_new_tokens=1024
resize_mode=stretch
vision/language/lm_head weight bits=8/8/8
language graph count=13
compact_logits=true
fuse_initial_pbd=true
```

## Prepare 验收

1. `selected.jsonl` 仍为 1200 行且 SHA256 不变，唯一 `bundle_id=1200`、缺图 0。
2. 完成 1200/1200；生成 1200 个非空 `.pt` 张量和 1200 条 `generated.jsonl`。
3. 所有记录的 `fixed_profile` 都是 448，Vision 输入 `(1,1024,588)`、输出 `(1,256,2048)`。
4. Profile、形状、Prompt 超过 Prefill 384、非有限 Float 输出和失败样本均为 0。
5. 报告 Prompt 与生成 Token 的 min/P95/max；不得因 `calibration.max_new_tokens=1024` 静默截断标准答案。
6. 保存配置、输入、`generated.jsonl` 的 SHA256、退出码、开始/结束时间和完整日志。

## Calibration 与激活统计验收

1. Vision 1200/1200、Language 1200/1200；报告实际 Replay 上下文数量。
2. Language 真实回放 Prefill、PBD q6-q12 和 AR q1-q5；实际图执行次数等于预期次数，Decode Context Coverage 通过。
3. Language 激活点无未执行、非有限值、非法 Norm 或零 Absmax。
4. Vision 动态量化路径允许 0 个静态 Observer，但必须完成 1200 次执行、输出有限且图覆盖通过，不能全局跳过审计。
5. 输出完整 1200 样本 Scale Manifest、Graph Coverage、Scale Convergence 和 512 vs 1200 收敛报告。
6. 记录 512 到 1200 的 Mean/P95/Max Drift 和超过 10% 的激活点数量；构建只能使用最终 1200 Scale。
7. Scale Manifest 中必须包含完整 448 stretch Vision Profile、Prefill 384、KV 1024、Batch 1、W8、fused Prefill 和 compact logits；任何 letterbox、336/672 Profile 串用均失败。

## 执行边界

- 仅在上一阶段完整验收后构建 Source BC、Converted BC、HBO 和 HBM；
- 仅在 HBM ABI 与数值审计通过后向 S600 部署并运行测试；
- 不修改、删除或覆盖 `fast_336`、`stable_672` 的配置、Scale、HBM 或运行目录；
- 不把进程存活、文件存在或部分样本完成写成阶段成功。
