# Stage 7: fast_336 S600 对比验收

> 本页保留上一版 fast_336 与 stable_672 的 350 帧完整对比；文末补充当前 fused Prefill、Compact Logits、Device KV 和流水线 Runtime 的 30 FPS ROS 验收。两组数据口径不同，不直接混合计算变化率。

## 状态

已完成，2026-08-15。

fast_336 和 stable_672 均在同一台 RDK S600 上完成同图检测、350 帧同视频检测、逐帧结果对比、性能与资源采样。fast_336 另完成 ROS 2 本地图片回灌检测。两套运行均为 Hybrid、NMS IoU 0.9、四 BPU 核，输入文件与 Prompt 相同。

fast_336 完成工程验收，可用于检测优先的快速档。逐帧框数差异仍高于原 15% 数值线，该结果完整保留；stable_672 继续用于小目标、高分辨率和精度敏感任务。

## 板端环境

| 项目 | 实际值 |
| --- | --- |
| Platform | RDK S600, AArch64 |
| OS | Ubuntu 24.04.3 LTS |
| Kernel | `6.1.158-rt58-DR-5.0.0-2512121202-ga90adc-ga4d2d5-dirty` |
| CPU / Memory | 18 CPU, 14 GiB RAM |
| TROS | Jazzy |
| DNN | `3.12.3` |
| HBRT | `4.5.4` |
| BPULib | `2.2.15` |
| fast_336 Runtime | `D-Robotics/hobot_locateanything:fast_336@8bdfe309a4fb4436ebd31f9ced987581c21e3298` |
| stable_672 Runtime | 板端现有 `develop@e135b91cfbc2796e542e989a8c7061541b776f96` |

两个工作树在测试前后均为 clean。stable_672 的源码、配置和模型未修改。

## 实际配置

| 参数 | fast_336 | stable_672 |
| --- | ---: | ---: |
| 图像尺寸 | 336 x 336 | 672 x 672 |
| Visual Token | 144 | 576 |
| Prefill | 256 | 1024 |
| KV Cache | 1024 | 4096 |
| Runtime max new tokens | 768 | 4096 |
| PBD / AR | q6 / q1 | q6 / q1 |
| Generation | Hybrid | Hybrid |
| NMS IoU | 0.9 | 0.9 |
| BPU Core | 4 | 4 |
| L2 | `6:6:6:6` | `6:6:6:6` |

fast_336 模型：

| 文件 | 大小（bytes） | SHA256 |
| --- | ---: | --- |
| Vision HBM | 491258184 | `0f476272b0442d2457e772a158697eb340484db0f4e43724cbe7a2100947a090` |
| Language HBM | 3467789616 | `6ff906d7fd236530c42872b20055c3b7ea1b9abcf2ebe324eca07c9985bbec41` |
| Embedding | 625381376 | `8668944fcb527faf3bbcd1c03a88d9da69f400b0700028f51ac6abe700e04011` |

stable_672 模型：

| 文件 | 大小（bytes） | SHA256 |
| --- | ---: | --- |
| Vision HBM | 576176512 | `6bb19e75f82e140e3e86a15a126da9f6b750158deb21f0ba918ffa9785c85ea7` |
| Language HBM | 3725462040 | `c18c7cdcb7c5a70ea5937e9ba09ec4964471676e5b7c0da1da765de8c64a143f` |
| Embedding | 625381376 | `8668944fcb527faf3bbcd1c03a88d9da69f400b0700028f51ac6abe700e04011` |

## 构建与启动

fast_336 在独立工作树构建：

```bash
source /opt/tros/jazzy/setup.bash
colcon build --merge-install --packages-select hobot_locateanything \
  --cmake-args -DCMAKE_BUILD_TYPE=Release
```

结果：`1 package finished`，`COLCON_EXIT=0`。

Console 使用各自安装目录和配置：

```bash
source /opt/tros/jazzy/setup.bash
source install/setup.bash
install/lib/hobot_locateanything/console \
  --config install/lib/hobot_locateanything/config/config_fast_336.yaml
```

```text
/video install/lib/hobot_locateanything/image/person_video.avi
/detect person
```

stable_672 使用板端现有 `config/config.yaml`，输入与 Prompt 完全相同。

## 输入

| 输入 | 值 |
| --- | --- |
| 单图 | `07_detection_multiclass.jpg`, 640 x 480 |
| 单图 Prompt | `/detect person,bus,bicycle` |
| 视频 | `person_video.avi`, 856 x 480, 25 FPS, 350 帧 |
| 视频 SHA256 | `6e726db669584e633a647c64e2349f1aa5840c49e4666e24760029ea30e5357e` |
| 视频 Prompt | `/detect person` |
| Float 336 对照 | 350 帧，SHA256 `9101dc8b6f1d3fa92ccecf535de93e62c7cf4034ca89d2874b97830640f7b551` |
| Box 匹配 | 同帧、同标签、IoU >= 0.5，贪心一对一匹配 |

## 单图检测

| 指标 | fast_336 | stable_672 |
| --- | ---: | ---: |
| Labels | bicycle, bus, person | bicycle, bus, person |
| Boxes | 5 | 6 |
| Vision | 24.0 ms | 247.2 ms |
| Prefill | 49.0 ms | 160.0 ms |
| Decode | 449.4 ms | 525.0 ms |
| Host | 39.8 ms | 41.3 ms |
| Total | 541.5 ms | 974.5 ms |
| Stop | `im_end` | `im_end` |

fast_336 的 5 个框均与 stable_672 达到 IoU 0.5，匹配框平均 IoU 为 0.915，中位数为 0.890。差异为 stable_672 多检出 1 个 bicycle。

## 350 帧视频检测

### fast_336 与 stable_672

| 指标 | 结果 |
| --- | ---: |
| 完成帧 | 350 / 350 |
| fast_336 总框数 | 6204 |
| stable_672 总框数 | 6025 |
| 总框数差 | +179, +2.97% |
| 逐帧绝对框数误差加权值 | 19.60% |
| 同帧框数相同 | 33 / 350, 9.43% |
| IoU >= 0.5 匹配框 | 4501 |
| 相对 stable_672 匹配率 | 74.71% |
| 相对 fast_336 匹配率 | 72.55% |
| 匹配框平均 / 中位 IoU | 0.779 / 0.796 |
| 含至少一个匹配框的帧 | 350 / 350 |

### fast_336 HBM 与 Float 336

| 指标 | 结果 |
| --- | ---: |
| fast_336 HBM 总框数 | 6204 |
| Float 336 总框数 | 5913 |
| 总框数差 | +291, +4.92% |
| 逐帧绝对框数误差加权值 | 17.13% |
| 同帧框数相同 | 68 / 350, 19.43% |
| IoU >= 0.5 匹配框 | 4983 |
| 相对 Float 336 匹配率 | 84.27% |
| 相对 fast_336 HBM 匹配率 | 80.32% |
| 匹配框平均 / 中位 IoU | 0.848 / 0.879 |

Float 336 与 stable_672 的 Stage 2 全量对照为 5913 / 5914 框、逐帧框数误差 18.45%、相对 stable_672 的 IoU 0.5 匹配率 73.40%。S600 fast_336 的相对 stable_672 匹配率为 74.71%，没有出现新的结构性下降。

## 完整性检查

| 检查 | fast_336 | stable_672 |
| --- | ---: | ---: |
| 非法、零面积或越界框 | 0 | 0 |
| 同帧同标签 IoU >= 0.9 疑似重复框对 | 0 | 0 |
| Fallback 帧 | 0 | 0 |
| `im_end` | 350 / 350 | 350 / 350 |
| 最大生成 Token | 190 / 768 | 154 / 4096 |
| Generation Mode | 350 / 350 Hybrid | 350 / 350 Hybrid |

8 个固定同帧和完整 350 帧并排视频经人工复核，没有边缘长条框、越界框或重复框爆炸。Fast 在密集人群中常将相邻实例分得更细，因此部分帧框数和 Decode Token 更多。

## 性能统计

所有统计均覆盖 350 帧。单位为 ms，Decode throughput 为 Token/s。

| 指标 | Profile | Mean | Median | P95 | Range |
| --- | --- | ---: | ---: | ---: | ---: |
| Vision | fast_336 | 23.0 | 23.0 | 23.2 | 22.7-24.2 |
| Vision | stable_672 | 247.3 | 246.1 | 252.0 | 245.3-252.6 |
| Prefill | fast_336 | 51.1 | 51.0 | 52.1 | 48.7-52.5 |
| Prefill | stable_672 | 153.7 | 153.0 | 156.2 | 152.3-156.5 |
| Decode | fast_336 | 1125.1 | 1105.2 | 1641.8 | 522.4-2036.2 |
| Decode | stable_672 | 1049.6 | 1018.7 | 1408.7 | 554.9-1754.2 |
| Host | fast_336 | 93.4 | 90.5 | 132.8 | 47.6-158.0 |
| Host | stable_672 | 90.1 | 92.7 | 107.5 | 62.4-128.3 |
| Total | fast_336 | 1220.0 | 1200.5 | 1737.6 | 618.1-2131.7 |
| Total | stable_672 | 1493.9 | 1463.6 | 1853.8 | 1004.5-2195.6 |
| Decode throughput | fast_336 | 102.0 | 99.7 | 136.3 | 55.4-164.2 |
| Decode throughput | stable_672 | 105.7 | 102.2 | 142.0 | 61.7-144.1 |

fast_336 相对 stable_672 的均值变化：

| 指标 | 变化 |
| --- | ---: |
| Vision | -90.70% |
| Prefill | -66.77% |
| Decode | +7.19% |
| Host | +3.64% |
| Total | -18.34% |
| Decode throughput | -3.52% |

视频墙钟时间为 fast_336 `428.92 s`、stable_672 `524.72 s`，fast_336 缩短 18.26%。Decode 增加与 fast_336 平均生成 111.0 Token、17.73 框有关；stable_672 平均生成 107.9 Token、17.21 框。

| Profile | 完成帧 | 墙钟时间 | 实际处理 FPS |
| --- | ---: | ---: | ---: |
| fast_336 | 350 | 428.92 s | 0.816 |
| stable_672 | 350 | 524.72 s | 0.667 |

fast_336 的实际处理 FPS 提升 22.34%。该 FPS 是逐帧顺序执行完整检测并写入带框视频和 JSONL 的端到端结果。

## 资源统计

资源采样从 `predictions.jsonl` 创建开始，到 Console 退出结束，不包含 HBM 加载。CPU 为 Console 进程占一个 CPU 核的百分比；Memory 为 Console RSS。BPU 为四核利用率的同采样均值。DDR 使用 `hrut_ddr -t rr_all -p 100000` 每张表中同一时刻的 `Bandwidth` Read、Write 和 Read+Write，单位为 GiB/s。

| 指标 | Profile | Samples | Mean | Median | P95 | Range |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Process CPU (%) | fast_336 | 428 | 56.0 | 56.0 | 64.0 | 44.0-70.0 |
| Process CPU (%) | stable_672 | 524 | 46.4 | 44.0 | 59.0 | 31.0-66.0 |
| RSS (MiB) | fast_336 | 428 | 184.8 | 185.7 | 185.7 | 177.3-186.3 |
| RSS (MiB) | stable_672 | 524 | 204.5 | 207.4 | 207.4 | 188.8-207.9 |
| Four-core BPU (%) | fast_336 | 350 | 64.1 | 63.5 | 75.0 | 0.0-94.3 |
| Four-core BPU (%) | stable_672 | 423 | 67.2 | 70.5 | 91.3 | 0.0-100.0 |
| DDR Read (GiB/s) | fast_336 | 107 | 88.0 | 88.2 | 92.4 | 75.0-93.9 |
| DDR Read (GiB/s) | stable_672 | 131 | 80.7 | 81.1 | 85.0 | 59.7-88.4 |
| DDR Write (GiB/s) | fast_336 | 107 | 0.79 | 0.78 | 0.94 | 0.59-0.99 |
| DDR Write (GiB/s) | stable_672 | 131 | 11.13 | 11.75 | 13.33 | 7.88-15.38 |
| DDR Read+Write (GiB/s) | fast_336 | 107 | 88.8 | 89.1 | 93.1 | 75.7-94.7 |
| DDR Read+Write (GiB/s) | stable_672 | 131 | 91.8 | 92.0 | 96.3 | 68.2-99.1 |

`rr_all` 在 20 个 master range 间轮询，因此各 master 列不是严格同一瞬时值；每张表的 Read 与 Write 及其 `Bandwidth` 列属于同一表，可用于本次两 Profile 的一致口径比较。

## ROS 2 回灌

使用 `hobot_image_publisher` 将同一图片以共享内存发布到 `/hbmem_img`，fast_336 ROS 节点订阅图片与 `/locateanything/prompt`，并在 `/perception/locateanything` 发布 `ai_msgs/msg/PerceptionTargets`。

```bash
export CAM_TYPE=fb
export ROS_DOMAIN_ID=96
ros2 launch hobot_locateanything hobot_locateanything.launch.py \
  config_file:=install/lib/hobot_locateanything/config/config_fast_336.yaml \
  publish_image_source:=install/lib/hobot_locateanything/image/07_detection_multiclass.jpg \
  locateanything_image_width:=640 \
  locateanything_image_height:=480
```

结果：退出码 0，5 个目标，坐标与 Console fast_336 单图结果一致；`Vision 24.0 ms`、`Language 540.4 ms`、`Total 572.9 ms`。

## 产物与证据

板端原始产物：

```text
/home/sunrise/LA_Test/hobot_locateanything_fast_336/outputs/fast_336/person_video/
/home/sunrise/LA_Test/hobot_locateanything/outputs/person_video/
/home/sunrise/LA_Test/fast_336_validation/
```

关键文件：

| 文件 | 大小（bytes） | SHA256 |
| --- | ---: | --- |
| fast_336 `predictions.jsonl` | 934535 | `8e86fa48c7828d3abeab2f22d1555790fa91e1a5d1287d8dd9c89895d899ec6c` |
| fast_336 `annotated.mp4` | 10975082 | `826d4add959cb3ec71c0d3a565baa2f1e8dae31e5a596b361091e4453dbe2548` |
| stable_672 `predictions.jsonl` | 895522 | `2028e37953d9319d27c3ff1ec15e2803b79bad602a37d90f81a5ee9d6258d2cc` |
| stable_672 `annotated.mp4` | 8694853 | `13cf2960f267e2ec04edd3b1855269a17dcda89e50bf52b1935b2e91038ea9e3` |
| 350 帧并排视频 | 19426007 | `485f5850b75ea6e1821490ac7e74f197f3506bf54ef53bdd5f9073bd764d4566` |
| 8 帧同帧拼图 | 688190 | `123b2938007e754185f7bf88dd2b104faa70edb215a21da668ea175c1b2297f3` |

原始日志、视频、JSON、临时分析脚本和 HBM 不提交到 GitHub。

## 问题与处理

1. 首次非交互 Console 没有加载 TROS 环境，因缺少 `libament_index_cpp.so` 以 127 退出，未开始推理。补充 `source /opt/tros/jazzy/setup.bash` 和 `source install/setup.bash` 后通过。
2. fast_336 首次资源采样结束时，两个 `sudo` 包装的监控子进程没有随 Console 退出。按 `inference_end.txt` 裁掉尾部空闲样本，并修正临时脚本的子进程终止逻辑；Stable 采样按修正后逻辑一次完成。
3. fast_336 的 Decode 均值比 stable_672 高 7.19%，原因是该视频中 fast_336 生成的框和 Token 更多。Vision、Prefill 和总耗时仍显著降低。
4. HBM fast_336 相对 Float 336 的逐帧框数误差为 17.13%，相对 stable_672 为 19.60%，未达到原 15% 数值线。该视频没有人工 Ground Truth，差异不能写成真实错误率；完整并排视频和固定帧复核未见结构性异常。

## 当前 fused Runtime ROS 验收

当前 Language HBM 大小为 `3,467,994,368` Byte，SHA256 为 `ad4a861bd91f7de6c41f218afb3b095fc8e5456c8ce25f91cc034495706326e8`。S600 安装目录为：

```text
/home/sunrise/LA_Test/hobot_locateanything_fast_336_checkout/install_fast_336_fused
```

使用 30 FPS 本地图片回灌和正式 ROS 共享内存路径，单目标与多目标均连续完成 40 帧：

| Prompt | 结果 | Output FPS | Preprocess | Vision | Language | Pipeline latency |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `/detect bus` | 40/40，1 box，`im_end` | 8.084 | 8.756 ms | 55.780 ms | 123.524 ms | 247.210 ms |
| `/detect person,bus,bicycle` | 40/40，5 boxes，`im_end` | 2.200 | 8.791 ms | 55.781 ms | 454.417 ms | 909.094 ms |

单目标基线为 `6.942 FPS`，当前连续三次 40 帧测试为 `8.090`、`8.092` 和 `8.084 FPS`。流水线提高输出吞吐，但 prepared 深度为 1，因此 `Pipeline latency` 包含等待上一帧 Language 的时间，不能与旧串行单帧 `Total` 直接比较。

100 帧稳态资源窗口不包含模型加载：

| 指标 | 样本 | 均值 | 范围 |
| --- | ---: | ---: | ---: |
| Process CPU | 15 | 57.0% | 55%-59% |
| RSS | 15 | 174.1 MiB | 174.06-174.19 MiB |
| Four-core BPU | 56 | 79.4% | 66%-92% |
| DDR Read `Bandwidth` | 3 | 78.8 GiB/s | 78.5-79.1 GiB/s |
| DDR Write `Bandwidth` | 3 | 0.86 GiB/s | 0.82-0.88 GiB/s |
| DDR Read+Write `Bandwidth` | 3 | 79.6 GiB/s | 79.4-79.9 GiB/s |

监控开启期间的 100 帧实际吞吐为 `8.048 FPS`。首个未进入稳态的 BPU/DDR 样本已排除；Read、Write 和 Read+Write 均来自同一张 `hrut_ddr` 表的 `Bandwidth` 列，原始 MiB/s 除以 1024 转为 GiB/s。

## 结论

fast_336 的 336 x 336 Vision、Prefill 256、KV Cache 1024、13 图 Language HBM、Console 视频检测和 ROS 2 检测路径均已在 S600 实机通过。350 帧检测中无越界框、重复框爆炸、Fallback 或生成到上限；相对 stable_672 的平均总耗时降低 18.34%，实际处理 FPS 提升 22.34%，RSS 平均降低约 19.7 MiB。

fast_336 作为检测优先的快速 Profile 完成工程验收。当前 fused Runtime 在不修改量化精度、不删除因果图调用的前提下，将单目标 ROS 回灌稳定提升到约 8.1 FPS。其逐帧差异高于严格 15% 数值线，适用边界必须保留；stable_672 继续作为小目标、高分辨率和精度敏感任务的稳定 Profile。
