# Stage 4: fast_336 1200 条校准

## 状态

已完成并通过验收。

- Prepare：1200 / 1200；
- Vision Calibration：1200 / 1200；
- Language Calibration：1200 / 1200，共 1393 个 Replay 上下文；
- 激活 Scale、图覆盖和 Decode 上下文覆盖审计全部通过；
- 未启动 BC、HBO、HBM 编译或 S600 测试。

## 实际配置

| 参数 | 值 |
| --- | ---: |
| 图像尺寸 | 336 x 336 |
| Patch Grid | 24 x 24 |
| Patch 数量 | 576 |
| Visual Token | 144 |
| Vision 输入 / 输出 | `(1,576,588)` / `(1,144,2048)` |
| Prefill | 256 |
| KV Cache | 1024 |
| Prepare 最大生成 Token | 768 |
| 运行时最大生成 Token | 768 |
| PBD / AR Query | 6 / 1 |
| Vision / Decoder / LM Head 权重 | W8 / W8 / W8 |
| 激活统计精度 | FP16 |
| 校准样本 | 1200 |
| 收敛检查点 | 64、128、256、512、1200 |
| 随机种子 | 20260729 |

`Prefill 256 + max_new_tokens 768 = KV Cache 1024`。数据集标准答案单独保存为 `target_token_ids`，不由 Prepare 的 Float 预测上限截断。

## 环境

| 项目 | 实际值 |
| --- | --- |
| 主机 | `DG-4090-Office` |
| GPU | NVIDIA GeForce RTX 4090，24 GiB |
| 工作目录 | `/home/kangjie.xu/oe_locateanything/fast_336/Locateanything_PTQ` |
| Prepare Python | `/home/kangjie.xu/miniforge3/envs/locateanything/bin/python` |
| Calibration Python | `/home/kangjie.xu/miniconda3/envs/locateanything_ptq/bin/python` |
| Float 模型 | `/home/kangjie.xu/ptq_acceptance/20260814_105905/Locateanything_PTQ/compiler/models/LocateAnything-3B` |
| 输出目录 | `compiler/outputs/fast_336_prefill256_cache1024_w8` |

fast_336 使用独立工作目录和输出目录，未写入 `LA_TEST`，未覆盖 stable_672 的张量、Scale 或 HBM。

## 输入

输入包：

```text
compiler/datasets/calibration/locateanything/source.zip
```

| 检查 | 结果 |
| --- | --- |
| ZIP 大小 | 312121430 bytes |
| ZIP SHA256 | `e5beb7e87311db951a9d26587cde4008a7b4953dc3dc6c73e951d6f56ec243da` |
| `selected.jsonl` 记录 | 1200 |
| `selected.jsonl` SHA256 | `521c9203579b165b619934684ca0dd44f9a33dc9c68e0bb6abb17f481d17850b` |
| 图片文件 | 1200 |
| 缺失图片 | 0 |
| 重复 `bundle_id` | 0 |

任务分布：

| 任务 | 数量 |
| --- | ---: |
| Detection | 660 |
| GUI | 150 |
| Layout | 90 |
| OCR | 120 |
| Pointing | 60 |
| Referring | 120 |
| 合计 | 1200 |

## 执行命令

```bash
unzip -qo \
  compiler/datasets/calibration/locateanything/source.zip \
  -d compiler/datasets/calibration/locateanything/source
```

```bash
/home/kangjie.xu/miniforge3/envs/locateanything/bin/python \
  compiler/quantize.py \
  --config compiler/config/fast_336.yaml prepare
```

```bash
/home/kangjie.xu/miniconda3/envs/locateanything_ptq/bin/python \
  compiler/quantize.py \
  --config compiler/config/fast_336.yaml \
  calibrate --max-samples 1200 --checkpoint-samples 512
```

## Prepare 结果

| 检查 | 结果 |
| --- | ---: |
| 完成数量 | 1200 / 1200 |
| 唯一 `bundle_id` | 1200 |
| 非空 `.pt` 张量 | 1200 |
| Profile 错误 | 0 |
| Vision 输入形状错误 | 0 |
| Vision 输出形状错误 | 0 |
| Prompt 超过 256 | 0 |
| Prompt Token 最小 / P95 / 最大 | 175 / 197 / 214 |
| Float 预测 Token 最小 / P95 / 最大 | 7 / 210 / 771 |
| 标准答案 Token 最小 / P95 / 最大 | 7 / 345 / 813 |
| `generated.jsonl` SHA256 | `5eda27d6ac633677cac3294fd196f863a596b924a4e13633a084681816cada89` |
| 退出状态 | `succeeded`，exit code 0 |

时间：

- 启动：2026-08-14 21:50:49 +08:00；
- 完成：2026-08-14 22:01:34 +08:00；
- Float 生成进度耗时：10 分 08 秒；
- Prepare 总墙钟时间：10 分 45 秒。

## Calibration 结果

### 样本与上下文

| 检查 | 结果 |
| --- | ---: |
| Vision 样本 | 1200 |
| Language 样本 | 1200 |
| Language Replay 上下文 | 1393 |
| Base 上下文 | 1200 |
| Detection target-tail 补充上下文 | 193 |
| 需要深层 Detection 上下文的样本 | 218 |
| 已覆盖的必需 target 上下文 | 218 |
| 缺失必需 target 上下文 | 0 |

### 图路径覆盖

| 路径 | 实际次数 | 预期次数 |
| --- | ---: | ---: |
| Vision | 1200 | 1200 |
| Prefill | 1393 | 1393 |
| PBD q6-q12，每个图 | 1393 | 1393 |
| AR q1-q5，每个图 | 1393 | 1393 |

结果：

```text
all_stages_executed=true
decode_context_coverage_passed=true
stage_execution_counts == expected_stage_execution_counts
```

### 激活统计

| 检查 | 结果 |
| --- | --- |
| Language 激活点 | 289 / 289 |
| 未执行激活点 | 0 |
| 非有限值 | 0 |
| 非法 Norm | 0 |
| 零 Absmax | 0 |
| Language 审计 | passed |
| Vision 静态激活点 | 0，not applicable |
| 总体审计 | `activation_statistics_audit_passed=true` |

Vision 当前量化路径没有静态激活 Observer，因此 0 个激活点是既定实现，不表示遗漏。Vision Float 对照结果：

| 指标 | 数值 |
| --- | ---: |
| Cosine Mean | 0.9961627783 |
| Cosine Min | 0.9832256436 |

### Scale 收敛

Language 各检查点相对 1200 样本最终 Scale：

| 检查点 | Mean Drift | P95 Drift | Max Drift | 超过 10% 的点 |
| ---: | ---: | ---: | ---: | ---: |
| 64 | 4.16% | 16.33% | 37.27% | 43 |
| 128 | 2.95% | 12.34% | 32.36% | 28 |
| 256 | 1.81% | 9.13% | 20.73% | 10 |
| 512 | 1.18% | 8.22% | 20.73% | 7 |

最终构建使用完整 1200 样本 Scale。512 到 1200 仍有 7 个激活点漂移超过 10%，说明不能用 512 样本检查点代替最终 Scale；该结果不影响 1200 样本最终 Scale 的完整性审计。

时间：

- 有效任务启动：2026-08-14 22:04:57 +08:00；
- 完成：2026-08-14 22:21:20 +08:00；
- Vision Replay：约 19 秒；
- Language Replay：15 分 41 秒；
- Calibration 总墙钟时间：16 分 23 秒；
- 退出状态：`succeeded`，exit code 0。

## 产物

Prepare：

```text
compiler/outputs/fast_336_prefill256_cache1024_w8/calibration/generated/
├── generated.jsonl
├── generation_summary.json
├── generation_progress.jsonl
└── tensors/                 # 1200 个 .pt
```

Calibration：

```text
compiler/outputs/fast_336_prefill256_cache1024_w8/calibration/statistics/
├── calibration_scale_manifest.json
├── calibration_graph_coverage.json
├── scale_convergence.json
└── scale_convergence_512_vs_1200.json
```

关键产物 SHA256：

| 文件 | SHA256 |
| --- | --- |
| `calibration_scale_manifest.json` | `06968b05f1e2524fe90ebd081bc2165e7308a9619660fa9b92110d00b30ef1dd` |
| `calibration_graph_coverage.json` | `375741d8bc526ac1451ad675c7c78bbb1557a136b550a7ae86186e1f041e7dd8` |
| `scale_convergence.json` | `e7ed97a9e563b649070ad9af8a2a3b2b9127e06bc0fa79a58a62798f3f283b16` |
| `scale_convergence_512_vs_1200.json` | `fa543af5616cb912b60eb5f56359164c41407499ec5646d75fc8f3260e9b2cd3` |

日志：

```text
compiler/outputs/fast_336_prefill256_cache1024_w8/logs/
├── prepare.log
├── prepare.exit.txt
├── calibrate.log
├── calibrate.exit.txt
└── calibrate.metadata.json
```

## 问题与处理

第一次 Calibration 使用了 Float 验证环境：

```text
/home/kangjie.xu/miniforge3/envs/locateanything
```

该环境没有 `hbdk4`，任务在 0.8 秒内、处理任何样本前失败：

```text
ModuleNotFoundError: No module named 'hbdk4'
```

随后改用已安装 OELLM SDK 的环境：

```text
/home/kangjie.xu/miniconda3/envs/locateanything_ptq
```

该环境通过 `torch + CUDA + transformers + hbdk4.compiler.leap` 导入检查，完整 Calibration 成功。失败尝试没有生成 Scale；最终退出记录和四个统计 JSON 均来自成功任务。

## 结论

fast_336 已使用原始 1200 条数据重新生成 336 Profile 校准张量和独立 W8A8 激活 Scale。Profile、样本数量、图路径、激活点、Decode 上下文和产物哈希均已核验，Stage 4 通过。

## 下一阶段门槛

Stage 5 为 Vision 逐级构建与验证：

```text
Float -> Eager -> BC -> Converted BC -> HBO -> HBM
```

开始长时编译前需单独确认 Stage 5 的输入、命令、产物路径和验收条件。Stage 5 必须使用本阶段完整 1200 样本 Scale，不能使用 512 检查点或 stable_672 Scale。
