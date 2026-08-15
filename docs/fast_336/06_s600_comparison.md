# Stage 7: fast_336 S600 对比验收

## 状态

待确认，未开始板端传输、编译或推理。

## 目标

在同一台 RDK S600、相同输入和 Prompt 下，对比 stable_672 与 fast_336 的功能、检测结果、Vision / Prefill / Decode / Total 耗时、CPU、BPU、内存和 DDR。检测是主要验收任务；OCR 与 GUI 只做兼容性检查，不用作 fast_336 的主要精度门槛。

## 输入

| 输入 | 路径或值 |
| --- | --- |
| fast_336 Vision HBM | `compiler/outputs/fast_336_prefill256_cache1024_w8/build/vision/LocateAnything-3B_vision.hbm` |
| fast_336 Language HBM | `compiler/outputs/fast_336_prefill256_cache1024_w8/build/language/LocateAnything-3B_language.hbm` |
| fast_336 Embedding | `compiler/outputs/fast_336_prefill256_cache1024_w8/build/language/LocateAnything-3B_embed_tokens.bin` |
| fast_336 Runtime 配置 | `inference/config_fast_336.yaml` |
| stable_672 Runtime 配置 | `inference/config_stable_672.yaml` |
| Runtime 源码 | `inference/` |
| 检测图片 | 与 stable_672 当前手册验收相同的图片和 Prompt |
| 多人视频 | Stage 2 使用的同一 350 帧视频 |
| 主 Prompt | `/detect person,bus,bicycle` 及多人视频使用的 `/detect person` |

fast_336 固定产物：

| 文件 | 大小（bytes） | SHA256 |
| --- | ---: | --- |
| Vision HBM | 见 `04_vision_build.md` | `0f476272b0442d2457e772a158697eb340484db0f4e43724cbe7a2100947a090` |
| Language HBM | 3467789616 | `6ff906d7fd236530c42872b20055c3b7ea1b9abcf2ebe324eca07c9985bbec41` |
| Embedding | 625381376 | `8668944fcb527faf3bbcd1c03a88d9da69f400b0700028f51ac6abe700e04011` |

## 板端隔离目录

```text
inference/models/
├── stable_672/             # stable_672 对比产物，不覆盖
├── fast_336/
│   ├── LocateAnything-3B_vision.hbm
│   ├── LocateAnything-3B_language.hbm
│   └── LocateAnything-3B_embed_tokens.bin
└── tokenizer/
    ├── vocab.json
    ├── merges.txt
    └── added_tokens.json
```

运行结果分别写入：

```text
inference/outputs/stable_672/
inference/outputs/fast_336/
```

## 计划命令

板端源码编译：

```bash
cmake -S inference -B inference/build -DCMAKE_BUILD_TYPE=Release
cmake --build inference/build --parallel 2
```

fast_336 Console：

```bash
./inference/build/console --config inference/config_fast_336.yaml
```

stable_672 Console：

```bash
./inference/build/console --config inference/config_stable_672.yaml
```

两套配置都使用同一可执行文件，模型目录和输出目录完全分离；不得覆盖 fast_336 或当前稳定产物。

交互输入：

```text
/image <same_detection_image>
/detect person,bus,bicycle
```

```text
/video <same_350_frame_video>
/detect person
```

## 对比矩阵

| 项目 | stable_672 | fast_336 | 记录 |
| --- | --- | --- | --- |
| 配置契约 | 672 / 576 Visual Token / 1024 / 4096 | 336 / 144 Visual Token / 256 / 1024 | 启动日志与图 ABI |
| 图片检测 | 同图同 Prompt | 同图同 Prompt | 标签、框数、坐标、保存 JSON/图片 |
| 视频检测 | 同 350 帧视频 | 同 350 帧视频 | 总框数、逐帧框数、IoU 匹配 |
| 性能 | 预热后重复采样 | 预热后重复采样 | Vision、Prefill、Decode、Host、Total、tokens/s |
| 资源 | 同采样窗口 | 同采样窗口 | CPU、BPU、Mem、DDR Read/Write/Total |
| OCR / GUI | 稳定参考 | 兼容性检查 | 是否可运行、输出是否可解析 |

## 验收条件

1. Runtime 在 S600 上编译成功，fast_336 配置解析为 336 x 336、Prefill 256、KV Cache 1024、最大生成 768；
2. Vision 和 Language HBM 均成功加载，Language 固定 13 图契约通过，无 HBM 损坏、IOVA、Shape、Dtype 或图名错误；
3. 图片与视频检测均完成，输出标签、边界框、渲染结果和 JSON，不出现空输出、重复框爆炸、越界框或持续生成至上限；
4. stable_672 与 fast_336 使用同一输入、Prompt、运行模式、NMS 和采样方法；
5. 报告总框数、逐帧框数差异和 IoU 0.5 匹配结果，不用单次画面或总框数代替逐帧对比；
6. 性能至少记录预热后的多次 Vision、Prefill、Decode、Host、Total 和 Decode tokens/s，报告样本数、均值、中位数、P95 与范围；
7. 资源采样覆盖实际推理窗口，报告 CPU、BPU、Mem 和同一时刻的 DDR Read、Write、Read+Write；
8. fast_336 的检测结果不得相对已接受的 Float 336 出现明显新增退化；若超过原 10%-15% 目标范围，保留数据并由人工画面复核决定，不将无 Ground Truth 的 672 差异写成绝对精度；
9. stable_672 的模型、配置和结果完整保留；测试不覆盖或删除稳定产物；
10. 所有命令、输入、完成数量、原始日志、产物路径、问题和结论写入本文件。

## 输出

完成后本文件补充：

- 板端系统、TROS、DNN、HBRT 和 Runtime 版本；
- 两套模型的 SHA256 与实际加载路径；
- 编译、启动、图片和视频推理退出状态；
- 逐任务结果、性能统计与资源统计；
- 保存图片、视频、JSON、JSONL 和原始日志路径；
- 与 stable_672、Float 336 的差异、问题和最终结论。

## 当前门槛

开始 S600 长时传输和测试前，需要确认本阶段的板端目标目录、stable_672 实际模型目录，以及使用 Stage 2 的同一 350 帧视频。确认前保持 `待执行`。
