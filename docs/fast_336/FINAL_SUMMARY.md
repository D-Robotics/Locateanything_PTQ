# LocateAnything fast_336 最终汇总

> 本页保留 2026-08-15 的 350 帧 Profile 对比，并补充当前 fused Prefill、Compact Logits、KV Runtime 和 ROS 流水线验收。两组数据口径不同，不直接混合计算变化率。

## 状态

fast_336 已完成 Float 验证、参数化、1200 条独立校准、Vision HBM、Language HBM、S600 Console/ROS 检测、stable_672 对比和当前 Runtime 优化验收。

stable_672 全程保留，未覆盖其校准 Scale、BC、HBO、HBM、配置或板端工作树。

## 最新实时 USB 验收

2026-08-18 的正式检测口径已切换为 S600 `/dev/video0`、1280×720、30 FPS、336×336 `stretch`、`/detect box`、无 WebSocket。Batch 1 和 Batch 2 各采集 120 秒稳态窗口，完整阶段与资源时序图、CSV 和严格时间窗 FPS 计算见：

- [Batch 1 实时 USB 记录](08_batch1_live_usb.md)
- [Batch 2 实时 USB 记录](09_batch2_live_usb.md)

严格时间窗输出为 Batch 1 `7.833 FPS`（940 结果）和 Batch 2 `11.400 FPS`（1368 结果），两轮均为 1 box、10 Token、3 次 PBD、`im_end`，推理错误为 0。该结果替代本页后续历史回灌数字作为当前实时吞吐口径；历史数据仍保留用于过程追溯。

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
| S600 | Console 单图、350 帧视频、ROS 回灌和 30 FPS 流水线检测全部通过 | `06_s600_comparison.md` |

## 关键编译产物

| 产物 | 大小（bytes） | SHA256 |
| --- | ---: | --- |
| Vision HBM | 491258184 | `0f476272b0442d2457e772a158697eb340484db0f4e43724cbe7a2100947a090` |
| Language HBM (current fused fast_336) | 3467994368 | `ad4a861bd91f7de6c41f218afb3b095fc8e5456c8ce25f91cc034495706326e8` |
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

## 当前 ROS 流水线验收

当前 fast_336 Runtime 在 ROS 本地回灌中使用深度为 1 的 prepared 槽。下一帧的 Prompt/预处理/Vision 与当前帧 Language 重叠；同一帧的 Prefill、PBD/AR 和 KV 提交保持串行。模型 HBM、Tokenizer、图元数据、图 IO 和单路 Language KV 工作区只加载/分配一次并复用。

| Prompt | 样本 | 正确性 | 输出 FPS | Preprocess | Vision | Language | Pipeline latency |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| `/detect bus` | 40 | 40/40，1 box，`im_end` | 8.084 | 8.756 ms | 55.780 ms | 123.524 ms | 247.210 ms |
| `/detect person,bus,bicycle` | 40 | 40/40，5 boxes，`im_end` | 2.200 | 8.791 ms | 55.781 ms | 454.417 ms | 909.094 ms |

单目标基线为 `6.942 FPS`，当前连续三次 40 帧结果为 `8.090`、`8.092` 和 `8.084 FPS`。100 帧资源窗口（不含模型加载）为：进程 CPU `57.0%`，RSS `174.1 MiB`，四核 BPU `79.4%`，DDR Read `78.8 GiB/s`，Write `0.86 GiB/s`，Read+Write `79.6 GiB/s`。DDR 使用同一 `hrut_ddr` 表的 `Bandwidth` 列，原始 MiB/s 除以 1024 转换。

本轮实现了 Prompt/Token 缓存、固定尺寸插值系数缓存、Vision Patch 移交时去除一次 Host 拷贝、Language 输出工作区复用，以及 Prefill 零 KV 首次清零后复用。没有删除 q9/q12、改变量化精度或复制第二套 Language/KV。

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

fast_336 已完成代码、校准、编译和 S600 实机闭环。该 Profile 将 Vision Token 从 576 降至 144，将 Prefill 从 1024 降至 256，将 KV Cache 从 4096 降至 1024；350 帧顺序检测对比中平均总耗时降低 18.34%，当前 ROS 单目标回灌输出约 8.1 FPS，同时保留可用的多人检测结果。

fast_336 作为检测优先的快速档交付；stable_672 继续作为稳定档，两者由配置和模型目录显式选择，不建立隐藏别名，不覆盖彼此产物。
