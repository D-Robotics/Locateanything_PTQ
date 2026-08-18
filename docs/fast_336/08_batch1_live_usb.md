# LocateAnything fast_336 Batch 1 实时推理说明

## 1. 范围与结论

本文记录 fast_336 单 Batch（Batch 1）版本在 RDK S600 上的编译契约、推理链路和实时 USB 相机验收结果。测试只覆盖目标检测，Prompt 固定为 `/detect box`；OCR、GUI 和高分辨率任务继续使用对应的稳定配置。

本轮使用 `/dev/video0` USB 相机，输入 1280×720、30 FPS，模型输入 336×336，预处理为 stretch，不启动 WebSocket。120 秒稳态窗口内得到 940 个有效结果，严格窗口输出吞吐为 **7.833 FPS**，每帧均输出 1 个 `box`，停止原因为 `im_end`，推理错误为 0。

## 2. 编译配置

### 2.1 fast_336 Batch 1 契约

| 参数 | 值 |
| --- | --- |
| Image | 336×336 |
| Resize | `stretch` |
| Patch Grid | 24×24 |
| Vision 输入 / 输出 | `(1,576,588)` / `(1,144,2048)` FP16 |
| Visual Token | 144 |
| Prefill | 256 |
| KV Cache | 1024 |
| Runtime max new tokens | 768 |
| Calibration max new tokens | 896 |
| PBD / AR | q6 / q1 |
| 量化 | W8A8，fast_336 独立激活 Scale |
| Language Batch | 1 |
| BPU Core | 4 |

运行时配置从 YAML 读取，模型路径、图像尺寸、resize 模式和 Batch 维度均由配置决定。Batch 1 和 Batch 2 使用相同的 336 Vision 结构，Language HBM 与运行时状态分别管理。

### 2.2 编译侧优化

1. **缩短视觉序列**：336×336 产生 576 个 Patch，经 Merge 后为 144 个 Visual Token；Vision 输入输出固定为 `(1,576,588) -> (1,144,2048)`。
2. **缩短 Language 上限**：Prefill 设为 256，KV Cache 设为 1024，运行时生成上限为 768；校准上限独立为 896。
3. **Fused Prefill**：Prefill 一次输出 1 行 AR logits 加首个 PBD 窗口 6 行 logits，共 7 行，直接进入首轮决策。
4. **Compact Logits**：PBD 图输出 6 行，AR 图输出 1 行，保留当前状态需要的 KV 行。
5. **量化策略保持**：继续使用 W8A8，fast_336 生成独立激活 Scale，量化精度不因 Batch 1 推理改变。

## 3. 推理侧优化

### 3.1 两阶段流水线

Prepare 阶段处理当前输入帧的预处理和 Vision，Complete 阶段执行当前帧的 Language、采样和结果发布：

```text
帧 N+1: 预处理 -> Vision --------------------┐
                                             v
帧 N:   预处理 -> Vision -> Prefill -> PBD/AR -> 结果
```

下一帧的 Prepare 与当前帧的 Language 重叠。Prepared 槽深度为 1，输入持续到达时保留最新待处理帧。

### 3.2 固定输入缓存

同一检测命令的 Prompt 模板和 Token ID 复用；同一摄像头分辨率的缩放索引与插值权重复用。图片像素、Vision Feature、Language KV 和检测结果仍按当前帧重新计算。

### 3.3 图像缓冲区移交

预处理直接生成最终 FP16 Patch 缓冲区，再将该缓冲区交给 Vision Tensor 使用，省去中间 Host Patch 数组的一次复制。336 档每帧减少的复制量为 `576 × 588 × 2 Byte`，约 661 KiB。

### 3.4 图 IO、工作区和 KV

HBM 图 IO、Embedding、Attention Mask、采样缓冲、后处理工作区和 Prefill 全零 KV 在首次申请后复用。单帧开始时 Past KV 为空，上一帧的有效 KV 不作为下一帧上下文；复用的是设备缓冲区地址和容量，当前帧会覆盖本帧有效区域。

## 4. 实时 USB 验收

### 4.1 测试条件

| 项目 | 本轮设置 |
| --- | --- |
| 平台 | RDK S600，18 CPU 核，4 BPU Core |
| 输入 | USB `/dev/video0`，1280×720，30 FPS |
| ROS 输入 | `/hbmem_img` 共享内存 |
| Prompt | `/detect box` |
| 模型输入 | 336×336，`stretch` |
| WebSocket | disabled |
| 预热 | 20 个结果 |
| 稳态窗口 | 120 s |
| 结果日志 | `steady.log` 中每条真实推理结果 |
| 资源窗口 | 与稳态窗口同起止时间 |

执行的监控链路同时记录：

```bash
pidstat -h -r -u -p <hobot_locateanything_pid> 1
hrut_somstatus -n 1000 -d 1
hrut_ddr -t rr_all -p 1000
/proc/<pid>/status
/proc/meminfo
/sys/kernel/debug/ion/heaps/ion_cma
/sys/kernel/debug/ion/heaps/ion_uncache
```

DDR 统计读取同一张完整表的 `Bandwidth` 列，将 Read 与 Write 配对后相加。日志中的 `Elapsed time` 显示本轮实际配对间隔均值为 50.228 ms；因此表格使用日志时间，不把命令参数直接当作采样周期。所有采样点保留，不删除零值、峰值或离群点，不做平滑。

### 4.2 正确性与实时吞吐

| 指标 | Batch 1 实时 USB |
| --- | ---: |
| 监控窗口 | 120.004311 s |
| 脚本采集结果 | 940 |
| 严格时间窗结果 | 940 |
| 输出吞吐 | **7.833 FPS** |
| 每帧框数 | 1（940/940） |
| 生成 Token | 10/帧 |
| PBD 调用 | 3/帧 |
| Stop reason | `im_end`（940/940） |
| 推理错误 | 0 |

FPS 定义为 `严格时间窗结果数 / (monitor_end - monitor_start)`。它是连续实时输出吞吐，不是 `1000 / total_ms`；单帧记录延迟与流水线吞吐属于不同指标。

### 4.3 阶段耗时

| 阶段 | 均值 | 中位数 | P95 | 峰值 | 样本 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Preprocess | 18.525 ms | 18.498 ms | 18.944 ms | 20.216 ms | 940 |
| Vision | 47.234 ms | 47.192 ms | 47.897 ms | 50.366 ms | 940 |
| Language | 127.570 ms | 127.213 ms | 129.834 ms | 134.395 ms | 940 |
| Postprocess | 0.015 ms | 0.014 ms | 0.016 ms | 0.062 ms | 940 |
| 单帧端到端记录 | 255.350 ms | 254.827 ms | 259.056 ms | 263.942 ms | 940 |

### 4.4 资源占用

| 指标 | 均值 | 中位数 | P95 | 峰值 | 样本 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Process CPU | 74.28% | 74.00% | 79.00% | 107.00% | 119 |
| Process CPU（折算 18 核整机容量） | 4.13% | 4.11% | 4.39% | 5.94% | 119 |
| RSS | 174.56 MiB | 174.56 MiB | 174.56 MiB | 174.56 MiB | 223 |
| VmHWM | 174.69 MiB | 174.69 MiB | 174.69 MiB | 174.69 MiB | 223 |
| VSZ | 8056.94 MiB | 8056.94 MiB | 8056.94 MiB | 8057.50 MiB | 119 |
| BPU Core 0 | 80.31% | 81.00% | 90.30% | 100.00% | 95 |
| BPU Core 1 | 80.97% | 81.00% | 95.80% | 100.00% | 95 |
| BPU Core 2 | 80.75% | 82.00% | 94.20% | 100.00% | 95 |
| BPU Core 3 | 80.33% | 81.00% | 95.60% | 100.00% | 95 |
| Four-core BPU 平均 | 80.59% | 81.50% | 92.12% | 100.00% | 95 |
| MemAvailable | 12133.22 MiB | 12133.75 MiB | 12147.30 MiB | 12104.50 MiB（最低） | 223 |
| ION `ion_cma` Heap | 0.00 MiB | 0.00 MiB | 0.00 MiB | 0.00 MiB | 223 |
| ION `ion_uncache` Heap | 302.06 MiB | 302.06 MiB | 302.06 MiB | 302.06 MiB | 223 |
| DDR Read | 78.91 GiB/s | 76.99 GiB/s | 107.18 GiB/s | 117.25 GiB/s | 2388 |
| DDR Write | 1.42 GiB/s | 1.23 GiB/s | 2.65 GiB/s | 3.53 GiB/s | 2388 |
| DDR Read + Write | 80.33 GiB/s | 78.39 GiB/s | 108.23 GiB/s | 118.96 GiB/s | 2388 |

Process CPU 中 100% 表示一个 CPU Core；`Process CPU / 18` 只是将进程占用折算为整机 18 核容量。ION Heap 是系统全局共享堆，RSS 是进程 Host 常驻物理内存，两者不重复相加。

### 4.5 时序图

![Batch 1 实时输出 FPS](assets/live_box_compare/01_output_fps_timeline.png)

![Batch 1/Batch 2 阶段耗时原始时序](assets/live_box_compare/02_stage_latency_timeline.png)

![Batch 1/Batch 2 CPU 与内存时序](assets/live_box_compare/03_compute_memory_timeline.png)

![Batch 1/Batch 2 BPU 四核时序](assets/live_box_compare/04_bpu_per_core_timeline.png)

![Batch 1/Batch 2 DDR Read、Write 与合计时序](assets/live_box_compare/05_ddr_bandwidth_timeline.png)

图中的阶段、CPU、内存和 DDR 均为本轮完整原始采样；资源图同时展示 Batch 2，便于后续横向核对。

## 5. 产物与复核路径

### 5.1 S600 原始数据

```text
/home/sunrise/LA_LIVE_BOX_COMPARE_20260818/results/batch1
```

包含 `steady.log`、`pidstat.log`、`bpu.log`、`ddr.log`、`memory_ion.log`、`errors.log`、`abi.log` 和 `run.env`。

### 5.2 本地分析产物

```text
assets/live_box_compare/data/
assets/live_box_compare/resource_comparison_summary.json
assets/live_box_compare/summary_tables.md
assets/live_box_compare/01_output_fps_timeline.png
assets/live_box_compare/02_stage_latency_timeline.png
assets/live_box_compare/03_compute_memory_timeline.png
assets/live_box_compare/04_bpu_per_core_timeline.png
assets/live_box_compare/05_ddr_bandwidth_timeline.png
```

### 5.3 Batch 1 模型

```text
/home/sunrise/LA_TEST_336_BATCH1/install/lib/hobot_locateanything/models/fast_336/LocateAnything-3B_language.hbm
SHA256 ad4a861bd91f7de6c41f218afb3b095fc8e5456c8ce25f91cc034495706326e8
```

## 6. 结论

fast_336 Batch 1 在实时 USB `/detect box` 场景下以 7.833 FPS 稳定输出 1 框结果。阶段耗时中 Language 均值 127.570 ms，是流水线吞吐的主要节拍；四核 BPU 均值 80.59%，DDR Read + Write 均值 80.33 GiB/s，ION uncache Heap 稳定为 302.06 MiB。Batch 2 的同口径对比和增益见《LocateAnything_Batch2_优化说明.md》。
