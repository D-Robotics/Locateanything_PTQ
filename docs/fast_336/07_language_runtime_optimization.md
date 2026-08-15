# Stage 9: fast_336 Language 与 Runtime 优化

## 状态

编译器、校准回放和共享 Runtime 代码已完成；本地静态、配置和 ABI 契约验证完成。尚未启动新的 1200 条生产校准、HBO/HBM 编译或 S600 性能验收。

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

## 输入与命令

配置入口：

```bash
python compiler/quantize.py --config compiler/config/fast_336.yaml prepare --dry-run
python compiler/quantize.py --config compiler/config/fast_336.yaml calibrate --dry-run
python compiler/quantize.py --config compiler/config/fast_336.yaml build --component language --target hbm --dry-run
```

生产校准与编译命令需在阶段开始前再次冻结输入、输出目录和验收条件；本阶段未执行长时任务。

## 已完成结果

- fused Prefill 将 Prompt 最后一行 AR Logits 与首个六行 PBD 窗口合并为 7 行输出，删除首次独立 q6 调用。
- Compact Logits 将 PBD q6-q12 固定为 6 行、AR q1-q5 固定为 1 行，KV 更新仍保留各图真实 Query 长度。
- Scale Manifest 记录并校验 `compact_logits` 与 `fuse_initial_pbd`，防止旧 Scale 静默复用。
- Source BC 与 Converted BC 原型检查均为 13/13；fused Prefill 7 行 Top-1 为 7/7 一致，最小余弦为 0.991017。
- Float fused Prefill 与旧 Prefill + q6 的 Prompt KV 为 72/72 一致，26 个 PBD 决策 Token 一致，最小余弦为 0.999999。
- Runtime 启动时验证 13 图、75 输入、73 输出、Prefill/Cache、Logits 与 KV 形状，并分别打印 `fused_prefill` 与 `compact_logits`；混合 ABI 直接拒绝。
- PTQ `inference/` 与 `hobot_locateanything` 共享推理核心保持逐文件一致。

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

## 结论与下一阶段门槛

代码侧已具备新一轮生产校准和编译条件。开始 1200 条校准前必须再次确认：输入为完整 1200 条数据、配置哈希与 Git 提交固定、输出目录为空或为同契约可恢复目录，并明确 Source BC、Converted BC、HBO、HBM 和 S600 检测验收标准。
