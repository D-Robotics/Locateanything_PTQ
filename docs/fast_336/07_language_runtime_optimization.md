# Stage 9: fast_336 Language 与 Runtime 优化

## 状态

编译器、校准回放、共享 Runtime 代码和 S600 检测验收已完成。4090 独立 checkout 已完成生产 Prepare、Calibration、Vision HBM 和 Language HBM 构建；Language 13 图 ABI 审计通过。S600 fast_336 Release Runtime、新 Language HBM、Console 烟测和 ROS 30 FPS 本地回灌均已通过。

## 实际配置

| 参数 | 值 |
| --- | --- |
| Image | 336 x 336 |
| Visual Token | 144 |
| Prefill / KV Cache | 256 / 1024 |
| Calibration / Runtime max new tokens | 896 / 768 |
| Language 图 | Prefill、PBD q6-q12、AR q1-q5，共 13 图 |
| Logits ABI | Prefill 7 行、PBD 6 行、AR 1 行 |
| Quantization | W8A8，与稳定版策略一致，重新生成激活 Scale |
| Core | Vision / Prefill / PBD / AR 均为 4 |
| 输出目录 | `compiler/outputs/fast_336_prefill256_cache1024_w8_fused_prefill_compact_logits/` |

## 分支与配置冻结

| 仓库 | 本地 / 远端分支 | 优化代码基线 | 工作树 |
| --- | --- | --- | --- |
| `Locateanything_PTQ` | `fast_336` / `origin/fast_336` | `c935a4a` | 干净 |
| `hobot_locateanything` | `fast_336` / `origin/fast_336` | `9ee4e2f` | 干净 |

本记录提交前，4090 独立 checkout 与 PTQ 优化代码基线一致，S600 独立 checkout 与 Runtime 优化代码基线一致。PTQ fast 配置 SHA256 为 `25fed32e2add5e8058481280d7ac894cfb93ea5c4c7fa11ca07519b419b68361`，Runtime fast 配置 SHA256 为 `f8232b84aa0b0a5b361dd4add904d8e0e435fc38ba050e2c2098418acf748f7d`。

生产任务只允许从以下两个独立 Git checkout 启动：

- 4090：`/home/kangjie.xu/oe_locateanything/fast_336_checkout/Locateanything_PTQ`
- S600：`/home/sunrise/LA_Test/hobot_locateanything_fast_336_checkout`

`/home/kangjie.xu/oe_locateanything/fast_336/Locateanything_PTQ` 与 `/home/sunrise/LA_Test/hobot_locateanything_fast_336` 是历史复制/构建目录，不是本轮源码入口。前者执行 Git 命令时会向上解析到父仓库的 `main`，因此禁止从该目录启动校准或编译。PTQ 的早期参数化与检测记录已在建立 `fast_336` 前进入 `develop`；本轮 Language 优化提交 `6384774` 及其后续提交只存在于 `fast_336`，本阶段未改写或提交 `develop/main`。

## 输入与命令

配置入口：

```bash
python compiler/quantize.py --config compiler/config/fast_336.yaml prepare --dry-run
python compiler/quantize.py --config compiler/config/fast_336.yaml build --component vision --target hbm --dry-run
python compiler/quantize.py --config compiler/config/fast_336.yaml build --component language --target hbm --dry-run
```

生产输入位于：

- Float checkpoint：`compiler/models/LocateAnything-3B/`
- 校准数据：`compiler/datasets/calibration/locateanything/source/`

生产 Prepare、Calibration、Vision HBM 和 Language HBM 均从上述 4090 独立 checkout 执行，期间未切换 checkout、配置哈希或输出目录。

## 已完成结果

- fused Prefill 将 Prompt 最后一行 AR Logits 与首个六行 PBD 窗口合并为 7 行输出，删除首次独立 q6 调用。
- Compact Logits 将 PBD q6-q12 固定为 6 行、AR q1-q5 固定为 1 行，KV 更新仍保留各图真实 Query 长度。
- Scale Manifest 记录并校验 `compact_logits` 与 `fuse_initial_pbd`，防止旧 Scale 静默复用。
- Source BC 与 Converted BC 原型检查均为 13/13；fused Prefill 7 行 Top-1 为 7/7 一致，最小余弦为 0.991017。
- 当前 `ea1aca4` 再次加载 13 个 Converted BC，全部通过 75 输入、73 输出、INT8 KV、256/1024 和 `7/6/1` ABI 检查，退出码为 0。
- q6/q7/q12 与 AR q1/q2/q5 的确定性合成输入烟测均为 finite，KV 更新行数与真实 Query 一致；AR Top-1 为 3/3，最低余弦为 0.994282；PBD Top-1 为 12/18，最低余弦为 0.957581。合成输入结果只用于排除非有限值和明显图损坏，不替代真实数据 Token/Box 验收。
- Float fused Prefill 与旧 Prefill + q6 的 Prompt KV 为 72/72 一致，26 个 PBD 决策 Token 一致，最小余弦为 0.999999。
- Runtime 启动时验证 13 图、75 输入、73 输出、Prefill/Cache、Logits 与 KV 形状，并分别打印 `fused_prefill` 与 `compact_logits`；混合 ABI 直接拒绝。
- S600 从独立 `fast_336` checkout 执行 Release `colcon build --merge-install --packages-select hobot_locateanything`，1 个功能包构建成功；安装后的 `console` 与 `hobot_locateanything` 可执行文件正常启动，并打印 `fused_prefill=true compact_logits=true logits=7/6/1`。
- PTQ `inference/` 与 `hobot_locateanything` 的 29 个共享推理文件逐字节一致；两边 `cli.cpp` 仅保留 standalone YAML/当前目录与 ROS YAML/安装目录的适配差异。
- 使用相同旧 fast HBM、图片和 `/detect bus` 对 Device-resident KV 与 Host mirrored KV 做 A/B：Token ID、`im_end`、`bus` 标签及边界框 `[0.000, 29.440, 448.000, 371.840]` 完全一致。Device 模式每个 Language 图保留 `18.00 MiB` resident KV，Host 模式为 `0`；总耗时分别为 `190.8 ms` 与 `201.6 ms`。该结果验证 Device-resident Cache 不改变生成语义。
- 4090 生产 checkpoint 共 48 个文件、`7,796,046,769` Byte；模型索引包含 770 个权重映射和两片 Safetensors。校准输入共 1200 条、1208 个文件、`324,851,710` Byte。复制后的两棵目录已逐文件比较相对路径、大小和 SHA256，缺失、额外和不一致文件均为 0，目标目录均不是软链接。
- checkpoint 可离线加载为 `LocateAnythingConfig`、`Qwen2TokenizerFast` 和 `LocateAnythingProcessor`，词表大小为 152681。生产 Worker 显式使用 `fix_mistral_regex=True` 与 `use_fast=False`。
- 1200 条标注目标的 Token 长度均值为 77.72、P95 为 345.05、最大值为 813；2 条 OCR 标注超过运行时 768，0 条超过校准 896，验证了 Calibration 896 与 Runtime 768 必须分离。
- 4090 的生产 Prepare、Calibration、Vision HBM 和 Language HBM 均解析到 `336x336 / 144 / 256 / 1024 / W8 / 13 图 / fused Prefill / Compact Logits / 4 核`；配置 SHA256 为 `25fed32e2add5e8058481280d7ac894cfb93ea5c4c7fa11ca07519b419b68361`。
- Language Source BC、Converted BC 和 4-Core HBO 均为 13/13；最终链接 HBM 含固定 13 图，大小为 `3,467,994,368` Byte，SHA256 为 `ad4a861bd91f7de6c41f218afb3b095fc8e5456c8ce25f91cc034495706326e8`。
- HBM 链接耗时 12 分 39 秒；最终恢复阶段退出码为 0。`language_hbm_contract_resume2.json` 对 13 个图的 Converted BC 与 Linked HBM ABI 审计结果均为 `passed`。
- Token Embedding SHA256 为 `8668944fcb527faf3bbcd1c03a88d9da69f400b0700028f51ac6abe700e04011`，与上一版 fast_336 一致。

以上结果证明新生产 Scale、HBO、HBM 和 4090 图契约已完成；以下为本轮 S600 Runtime 优化与本地回灌证据。

## S600 Runtime 优化

### 可并行与必须串行

- 同一帧的 Prefill、PBD q9/q12、AR 转移、KV 提交和结构状态机保持串行；这些步骤有真实的 Token/KV 因果依赖，不能为了速度删除。
- 下一帧的 Prompt/Token 准备、图像预处理和 Vision 与当前帧 Language 重叠执行。ROS 节点使用深度为 1 的 prepared 槽，槽满后停止继续运行 Vision，避免 30 FPS 输入造成无效推理。
- 当前 Language 仍为单路串行，因此没有复制第二套 3.4 GB Language HBM 或第二套 KV Cache。

### 已实施优化

1. 共享推理核心增加 `Prepare` / `Complete` 两阶段接口，ROS 使用双线程流水线；原有 Console `Infer` 接口保持兼容。
2. 固定 Prompt 的模板和 Token 缓存最多保留 16 项；固定输入尺寸的双三次插值系数使用线程本地有界缓存。
3. Vision Patch 以已拥有的 FP16 字节缓冲直接移交图输入，去掉一次约 0.66 MiB 的 Host memcpy。
4. Prefill、PBD 和图输出工作区在 Language Engine 内复用，避免每帧重新申请约 8.9 MiB 的输出向量。
5. Prefill 零 KV 输入首次分配时清零；后续图输入只重置逻辑偏移，不重复写入约 18 MiB 的零数据。HBRT 图输入为只读，输出使用独立缓冲。

### S600 30 FPS 本地回灌

命令、输入图片、Prompt 和安装路径与正式 ROS 路径一致，使用 `hobot_image_publisher` 共享内存回灌，`publish_fps:=30`。性能不使用 Console 数据。

| Prompt | 完成样本 | 结果正确性 | 输出吞吐 | Preprocess | Vision | Language | Pipeline latency |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| `/detect bus` | 40 | 40/40，1 box，`im_end` | 8.084 FPS | 8.756 ms | 55.780 ms | 123.524 ms | 247.210 ms |
| `/detect person,bus,bicycle` | 40 | 40/40，5 boxes，`im_end` | 2.200 FPS | 8.791 ms | 55.781 ms | 454.417 ms | 909.094 ms |

单目标 100 帧资源窗口（模型加载已排除）：进程 CPU 均值 `57.0%`，RSS 均值 `174.1 MiB`，四核 BPU 均值 `79.4%`（各核 78.9%-79.9%），DDR `Bandwidth` Read 均值 `78.8 GiB/s`、Write `0.86 GiB/s`、Read+Write `79.6 GiB/s`。原始 MiB/s 除以 1024 转为 GiB/s。DDR Read 仍是主要资源压力，Write 已明显低于 Read。

### Core Mask 探针

尝试将 Vision/Language 运行时 mask 改为 `1/14`、`1/15` 或 `3/12` 时，HBRT 拒绝提交并报告 compiled model BPU core num 为 4。当前 HBM 必须按 4-core mask 运行，不能通过 YAML 临时拆分核心；若后续要做核心分区，需要重新编译对应的 HBM 变体并独立验收。

### 结论

本轮优化在不改变 W8A8、不改变 Prompt 采样策略、不删除 q9/q12 的前提下，将单目标 ROS 本地回灌从基线 `6.942 FPS` 提升到连续实测 `8.084-8.092 FPS`。多目标路径保持语义正确，但 Language 工作量随生成 Token 和 PBD 调用数增加，吞吐为 `2.200 FPS`。当前主要瓶颈仍是 Language 图的 BPU/DDR 读流量；下一阶段若继续追求更高吞吐，应针对新编译图契约或多流调度做受控实验，不应复制 KV 或删除有因果依赖的图调用。

## 产物路径

- 编译配置：`compiler/config/fast_336.yaml`
- 编译器契约：`compiler/model/contract.py`
- Language 导出与构建：`compiler/model/language.py`、`compiler/pipeline/language_build.py`
- 校准回放：`compiler/pipeline/calibrate.py`、`compiler/pipeline/replay.py`
- 独立输出目录：`compiler/outputs/fast_336_prefill256_cache1024_w8_fused_prefill_compact_logits/`
- Runtime：`inference/src/runtime/`

## 问题与边界

- `compiler/pipeline/language_audit.py` 是 stable_672 三图、1024/4096 的历史诊断工具，不进入 `quantize.py`，不能用于 fast_336 验收。
- 上一版 fast_336 Scale/HBM 的 Logits ABI 为 `1/q/q`，只能作为性能基线，不能通过 `--resume` 进入本轮输出目录。
- Language HBO 编译进程在完成 AR q2 后常驻内存接近 100 GiB，主机无 Swap。为避免系统 OOM，在完整落盘点受控终止首个进程，再以同一 checkout、配置和输出目录执行 `--resume`；最终复用 10/13 HBO，完成 q3-q5 与 HBM 链接。
- S600 首次传输时旧 `scp` 与后启动的 `sftp reput` 同时写入同一 `.partial`，最终尺寸超过源文件，已按损坏临时文件处理。后续只允许单连接写入唯一临时文件，并在改名前校验原始 HBM SHA256。
- Host mirrored KV 诊断在多目标长输出中会因每次图调用重复申请 UCP/ION 输入缓冲，在进程 `ulimit -n=1024` 下触发 `Too many open files`；该临时回退只用于 A/B，不进入公开 Runtime。正式 Device-resident 路径复用 KV 缓冲，不触发该问题。

## 结论与下一阶段门槛

fast_336 的代码、分支、配置、1200 条校准、Vision HBM、新 13 图 Language HBM 和 S600 检测优先路径已完成。后续若继续优化，应建立独立的编译图或多流实验目录，保留当前 `fast_336` 作为可回退基线；任何新图都必须重新通过 HBM ABI、同图框结果、30 FPS ROS 回灌和资源采样门槛。
