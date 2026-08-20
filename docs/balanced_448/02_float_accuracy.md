# Stage 2: balanced_448 Float 精度筛查

## 状态

已有 2026-08-14 的固定样本 Float 分辨率筛查证据，但该证据使用 Letterbox，只作为分辨率选择的历史参考。最终 balanced_448 使用 stretch，必须重新验证 Float、PTQ 和 S600 结果。

## 输入与口径

- 同一 LocateAnything-3B Float checkpoint；
- 同一 24 张检测图片、24 个 Prompt、147 个官方框；
- 同一随机种子、Letterbox 预处理和 IoU 0.5 贪心一对一匹配；该预处理与最终 stretch Profile 不同；
- 同时比较 336、392、448、504、560 和 stable_672；
- 该抽样来自校准数据，只用于 Profile 早期筛查，不作为公开 Benchmark。

## 结果

| Profile | Visual Token | Prefill 候选 | Precision@0.5 | Recall@0.5 | 大目标 Recall | 中目标 Recall | 小目标 Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fast_336 | 144 | 256 | 58.3% | 38.1% | 72.7% | 24.2% | 0.0% |
| balanced_448 | 256 | 384 | 66.7% | 53.1% | 80.0% | 50.0% | 3.8% |
| stable_672 | 576 | 1024 | 76.1% | 58.5% | 83.6% | 53.0% | 19.2% |

448 相对 336 的 Precision@0.5 提升 8.4 pp，Recall@0.5 提升 15.0 pp；大目标、中目标和小目标 Recall 均未下降，达到计划中“Precision 与 Recall 均不低于 336，且至少一项实质提升”的进入条件。

448 的总体 Recall 为 stable_672 的 90.7%，但小目标 Recall 仍明显低于 672。`balanced_448` 不能替代 `stable_672` 的小目标、高分辨率或精度敏感用途。

## 原始证据

```text
/home/kangjie.xu/oe_locateanything/LocateAnything/artifacts/fast_224/
  float_accuracy_20260814/resolution_sweep_392_448_504_560.jsonl
```

| 检查 | 值 |
| --- | --- |
| 行数 | 103 |
| 文件大小 | 187455 bytes |
| SHA256 | `c5f578b3d787e2f4f8f2de09404f0d7311ac06f3392573854e7db587d24c319e` |
| 远端重新核对日期 | 2026-08-20 |

## 结论

该结果支持选择 448 分辨率，但不能证明 stretch Profile 的最终精度。后续从原始图片重新生成 1200 条 stretch 校准张量和激活 Scale，并逐级完成 Float、量化与板端对照。
