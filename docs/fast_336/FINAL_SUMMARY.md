# LocateAnything fast_336 最终汇总

## 状态

fast_336 已完成 Float 验证、参数化、1200 条独立校准、Vision HBM、Language HBM、S600 Console/ROS 检测和 stable_672 对比验收，2026-08-15。

stable_672 全程保留，未覆盖其校准 Scale、BC、HBO、HBM、配置或板端工作树。

## 最终参数

| 参数 | fast_336 | stable_672 |
| --- | ---: | ---: |
| Image | 336 x 336 | 672 x 672 |
| Patch Grid | 24 x 24 | 48 x 48 |
| Vision 输入 | `(1,576,588)` FP16 | `(1,2304,588)` FP16 |
| Visual Token | 144 | 576 |
| Vision 输出 | `(1,144,2048)` FP16 | `(1,576,2048)` FP16 |
| Prefill | 256 | 1024 |
| KV Cache | 1024 | 4096 |
| Runtime max new tokens | 768 | 4096 |
| PBD / AR | q6 / q1 | q6 / q1 |
| Quantization | W8A8, 独立 1200 条 Scale | W8A8 稳定版 |
| Target | Nash-P, 4 BPU Core | Nash-P, 4 BPU Core |

`Prefill 256 + max_new_tokens 768 = KV Cache 1024`。Prepare 实测 Prompt Token 最大值为 214，未超过 Prefill 256。

## 阶段结果

| 阶段 | 完成结果 | 记录 |
| --- | --- | --- |
| Float 结构 | 224 和 336 均可完成 MoonViT 前向；224 后续精度未通过 | `01_float_224_validation.md` |
| Float 精度 | 336 经 350 帧完整复核后选为 fast 候选 | `02_float_accuracy_comparison.md` |
| 参数化 | 672 与 336 共用一套实现，由 YAML 配置形状和路径 | `03_configuration_parameterization.md` |
| Prepare | 1200 / 1200，Prompt 形状和 Profile 错误均为 0 | `03_calibration.md` |
| Calibration | Vision 1200，Language 1200，1393 个 Replay 上下文，289 / 289 激活点有效 | `03_calibration.md` |
| Vision Build | Source BC、Converted BC、4-Core HBO、HBM 全部通过 | `04_vision_build.md` |
| Language Build | 13 Source BC、13 Converted BC、13 HBO、13 图 HBM ABI 全部通过 | `05_language_build.md` |
| S600 | Console 单图、350 帧视频和 ROS 回灌检测全部通过 | `06_s600_comparison.md` |

## 关键编译产物

| 产物 | 大小（bytes） | SHA256 |
| --- | ---: | --- |
| Vision HBM | 491258184 | `0f476272b0442d2457e772a158697eb340484db0f4e43724cbe7a2100947a090` |
| Language HBM | 3467789616 | `6ff906d7fd236530c42872b20055c3b7ea1b9abcf2ebe324eca07c9985bbec41` |
| Embedding | 625381376 | `8668944fcb527faf3bbcd1c03a88d9da69f400b0700028f51ac6abe700e04011` |
| Scale Manifest | - | `06968b05f1e2524fe90ebd081bc2165e7308a9619660fa9b92110d00b30ef1dd` |
| Language HBM ABI Report | 13 / 13 passed | 见 `05_language_build.md` |

输出根目录：

```text
compiler/outputs/fast_336_prefill256_cache1024_w8/
├── calibration/
├── build/vision/
├── build/language/
├── reports/
└── logs/
```

## Float 选择依据

24 张带官方框样本中，336 的 Precision@0.5 为 58.3%，Recall@0.5 为 38.1%；stable_672 分别为 76.1% 和 58.5%。336 不面向小目标精度替代。

350 帧多人视频 Float 对照：

| 指标 | Float 336 | Float 672 |
| --- | ---: | ---: |
| 总框数 | 5913 | 5914 |
| 逐帧框数误差 | 18.45% | 基准 |
| IoU >= 0.5 匹配率 | 73.40% | 基准 |
| 匹配框平均 IoU | 0.766 | - |

该视频没有人工 Ground Truth，以上数据描述 Profile 差异，不等价于真实错误率。用户查看完整带框视频后确认 336 视觉效果可接受。

## S600 结果

同一 350 帧视频、同一 `/detect person`、Hybrid 和 NMS 0.9：

| 指标 | fast_336 | stable_672 | fast_336 变化 |
| --- | ---: | ---: | ---: |
| 总框数 | 6204 | 6025 | +2.97% |
| Vision Mean | 23.0 ms | 247.3 ms | -90.70% |
| Prefill Mean | 51.1 ms | 153.7 ms | -66.77% |
| Decode Mean | 1125.1 ms | 1049.6 ms | +7.19% |
| Total Mean | 1220.0 ms | 1493.9 ms | -18.34% |
| 视频墙钟 | 428.92 s | 524.72 s | -18.26% |
| 实际处理 FPS | 0.816 | 0.667 | +22.34% |
| Process CPU Mean | 56.0% | 46.4% | +9.6 pp |
| RSS Mean | 184.8 MiB | 204.5 MiB | -19.7 MiB |
| Four-core BPU Mean | 64.1% | 67.2% | -3.1 pp |
| DDR Read+Write Mean | 88.8 GiB/s | 91.8 GiB/s | -3.0 GiB/s |

fast_336 HBM 与 Float 336 的逐帧框数误差为 17.13%，IoU 0.5 匹配率为 84.27%，匹配框平均 IoU 为 0.848。所有 350 帧均以 `im_end` 停止，无 Fallback、越界框、零面积框或 IoU 0.9 疑似重复框。

## 检测路径

| 路径 | 结果 |
| --- | --- |
| Console 单图检测 | 通过，3 类 5 框 |
| Console 350 帧视频 | 350 / 350，通过 |
| ROS 2 本地图片回灌 | 通过，`/hbmem_img` 输入和 `/perception/locateanything` 输出正常 |

## 已知边界

1. 336 的逐帧框数差异高于原 15% 数值线，不能写成与 stable_672 等精度。
2. Fast 在密集人群帧中生成的框和 Token 更多，因此 Decode 不一定比 stable_672 更短；主要收益来自 Vision 和 Prefill。
3. 小目标、高分辨率和精度敏感检测继续使用 stable_672。
4. DDR `rr_all` 的 master range 是轮询采样；本报告只用同一表的 `Bandwidth` Read、Write 和 Read+Write 做一致口径对比。

## 最终结论

fast_336 已完成代码、校准、编译和 S600 实机闭环。该 Profile 将 Vision Token 从 576 降至 144，将 Prefill 从 1024 降至 256，将 KV Cache 从 4096 降至 1024，在本次 350 帧检测视频上将平均总耗时降低 18.34%，同时保留可用的多人检测结果。

fast_336 作为检测优先的快速档交付；stable_672 继续作为稳定档，两者由配置和模型目录显式选择，不建立隐藏别名，不覆盖彼此产物。
