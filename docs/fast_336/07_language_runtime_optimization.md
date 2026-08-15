# Stage 9: fast_336 Language 与 Runtime 优化

## 状态

编译器、校准回放和共享 Runtime 代码已完成；本地静态、配置、ABI 契约和生产输入验证完成。4090 独立 checkout 已具备完整 Float checkpoint 与 1200 条校准输入，生产 Prepare、HBO/HBM 编译和 S600 性能验收尚未启动。

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
| `Locateanything_PTQ` | `fast_336` / `origin/fast_336` | `ea1aca4` | 干净 |
| `hobot_locateanything` | `fast_336` / `origin/fast_336` | `d27d8c6` | 干净 |

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

生产 Prepare 完成并生成 `calibration/generated/generated.jsonl` 后，再执行 `calibrate --dry-run` 核对实际样本数与统计输出路径。本阶段未执行生产 Prepare、校准或编译。

## 已完成结果

- fused Prefill 将 Prompt 最后一行 AR Logits 与首个六行 PBD 窗口合并为 7 行输出，删除首次独立 q6 调用。
- Compact Logits 将 PBD q6-q12 固定为 6 行、AR q1-q5 固定为 1 行，KV 更新仍保留各图真实 Query 长度。
- Scale Manifest 记录并校验 `compact_logits` 与 `fuse_initial_pbd`，防止旧 Scale 静默复用。
- Source BC 与 Converted BC 原型检查均为 13/13；fused Prefill 7 行 Top-1 为 7/7 一致，最小余弦为 0.991017。
- 当前 `ea1aca4` 再次加载 13 个 Converted BC，全部通过 75 输入、73 输出、INT8 KV、256/1024 和 `7/6/1` ABI 检查，退出码为 0。
- q6/q7/q12 与 AR q1/q2/q5 的确定性合成输入烟测均为 finite，KV 更新行数与真实 Query 一致；AR Top-1 为 3/3，最低余弦为 0.994282；PBD Top-1 为 12/18，最低余弦为 0.957581。合成输入结果只用于排除非有限值和明显图损坏，不替代真实数据 Token/Box 验收。
- Float fused Prefill 与旧 Prefill + q6 的 Prompt KV 为 72/72 一致，26 个 PBD 决策 Token 一致，最小余弦为 0.999999。
- Runtime 启动时验证 13 图、75 输入、73 输出、Prefill/Cache、Logits 与 KV 形状，并分别打印 `fused_prefill` 与 `compact_logits`；混合 ABI 直接拒绝。
- S600 从干净 `fast_336@d27d8c6` 重新执行 `colcon build --symlink-install --packages-select hobot_locateanything`，1 个功能包在 44.8 秒内构建成功；安装后的 `console` 与 `hobot_locateanything` 可执行文件分别为 539384 与 2498312 Byte。旧 fast HBM 被正确识别为 `1/q/q` ABI，使用错误图集合时 Runtime 按预期拒绝启动。
- PTQ `inference/` 与 `hobot_locateanything` 的 29 个共享推理文件逐字节一致；两边 `cli.cpp` 仅保留 standalone YAML/当前目录与 ROS YAML/安装目录的适配差异。
- 使用相同旧 fast HBM、图片和 `/detect bus` 对 Device-resident KV 与 Host mirrored KV 做 A/B：Token ID、`im_end`、`bus` 标签及边界框 `[0.000, 29.440, 448.000, 371.840]` 完全一致。Device 模式每个 Language 图保留 `18.00 MiB` resident KV，Host 模式为 `0`；总耗时分别为 `190.8 ms` 与 `201.6 ms`。该结果验证 Device-resident Cache 不改变生成语义。
- 4090 生产 checkpoint 共 48 个文件、`7,796,046,769` Byte；模型索引包含 770 个权重映射和两片 Safetensors。校准输入共 1200 条、1208 个文件、`324,851,710` Byte。复制后的两棵目录已逐文件比较相对路径、大小和 SHA256，缺失、额外和不一致文件均为 0，目标目录均不是软链接。
- checkpoint 可离线加载为 `LocateAnythingConfig`、`Qwen2TokenizerFast` 和 `LocateAnythingProcessor`，词表大小为 152681。生产 Worker 显式使用 `fix_mistral_regex=True` 与 `use_fast=False`。
- 1200 条标注目标的 Token 长度均值为 77.72、P95 为 345.05、最大值为 813；2 条 OCR 标注超过运行时 768，0 条超过校准 896，验证了 Calibration 896 与 Runtime 768 必须分离。
- 4090 的 Prepare、Vision HBM 和 Language HBM dry-run 均解析到 `336x336 / 144 / 256 / 1024 / W8 / 13 图 / fused Prefill / Compact Logits / 4 核`；配置 SHA256 仍为 `25fed32e2add5e8058481280d7ac894cfb93ea5c4c7fa11ca07519b419b68361`，新输出目录为空。

以上结果证明代码和图契约已对齐，不代表新的生产 Scale、HBO、HBM 或板端性能已完成。

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
- Windows 环境没有 HBDK/OELLM 与 S600 厂商编译环境，本阶段只执行不触发生产构建的检查。
- `calibrate --dry-run` 需要 Prepare 已生成 `generated.jsonl` 才能解析实际样本数；干净输出目录下应先完成 Prepare，再执行校准计划检查。
- 4090 输入已独立复制到配置指定目录；新输出目录尚不存在，未复用任何旧 Scale、BC、HBO 或 HBM。
- Host mirrored KV 诊断在多目标长输出中会因每次图调用重复申请 UCP/ION 输入缓冲，在进程 `ulimit -n=1024` 下触发 `Too many open files`；该临时回退只用于 A/B，不进入公开 Runtime。正式 Device-resident 路径复用 KV 缓冲，不触发该问题。

## 结论与下一阶段门槛

fast_336 的代码、分支、配置、Float checkpoint、1200 条校准输入和空输出目录均已冻结，已达到启动生产 Prepare 的门槛。下一阶段从完整 1200 条 Prepare 开始；完成后依次核对生成数量与固定 Profile、执行 Calibration、13 图 Source/Converted BC、HBO/HBM 和 S600 检测性能验收，不允许切换 checkout、配置哈希或输出目录。
