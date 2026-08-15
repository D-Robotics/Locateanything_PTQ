# Stage 5: fast_336 Vision 构建

## 状态

已完成并通过 4090 编译产物验收。

本阶段完成 Source BC、Converted BC、4-Core HBO 和 HBM。独立 `--resume` 复验再次加载四类产物并校验图契约，未重新编译。

## 实际配置

| 参数 | 值 |
| --- | ---: |
| 图像尺寸 | 336 x 336 |
| Patch Grid | 24 x 24 |
| Vision 输入 | `(1,576,588)` FP16 |
| Vision 输出 | `(1,144,2048)` FP16 |
| Vision Linear 权重 | W8 |
| 激活 Scale | Stage 4 完整 1200 样本结果 |
| March | nash-p |
| BPU Core | 4 |
| 编译 Jobs | 16 |
| HBDK / HBRT | `4.10.2a2.dev202603180400+4c23b55.develop` |

Scale Manifest：

```text
compiler/outputs/fast_336_prefill256_cache1024_w8/calibration/statistics/calibration_scale_manifest.json
```

SHA256：

```text
06968b05f1e2524fe90ebd081bc2165e7308a9619660fa9b92110d00b30ef1dd
```

## 输入

| 输入 | 路径 |
| --- | --- |
| Float 模型 | `/home/kangjie.xu/ptq_acceptance/20260814_105905/Locateanything_PTQ/compiler/models/LocateAnything-3B` |
| fast_336 配置 | `compiler/config/fast_336.yaml` |
| 1200 样本 Scale | `compiler/outputs/fast_336_prefill256_cache1024_w8/calibration/statistics/calibration_scale_manifest.json` |
| 构建输出 | `compiler/outputs/fast_336_prefill256_cache1024_w8/build/vision/` |

Stage 4 的 1200 样本 Float / Eager Vision 对照为：Cosine Mean `0.9961627783`，Cosine Min `0.9832256436`。

## 命令

Source BC：

```bash
/home/kangjie.xu/miniconda3/envs/locateanything_ptq/bin/python \
  compiler/quantize.py \
  --config compiler/config/fast_336.yaml \
  build --component vision --target bc
```

复用 Source BC，继续 Converted BC、HBO 和 HBM：

```bash
/home/kangjie.xu/miniconda3/envs/locateanything_ptq/bin/python \
  compiler/quantize.py \
  --config compiler/config/fast_336.yaml \
  build --component vision --target hbm --resume
```

独立复验：

```bash
/home/kangjie.xu/miniconda3/envs/locateanything_ptq/bin/python \
  compiler/pipeline/vision_build.py \
  --bc_path compiler/outputs/fast_336_prefill256_cache1024_w8/build/vision/LocateAnything-3B_vision_336x336_w8_nash-p_corenum_4.visual.bc \
  --hbm_path compiler/outputs/fast_336_prefill256_cache1024_w8/build/vision/LocateAnything-3B_vision.hbm \
  --march nash-p --core_num 4 --jobs 16 \
  --image_width 336 --image_height 336 --resume
```

## 完成数量与结果

| 项目 | 结果 |
| --- | --- |
| Source BC | 1/1，通过 |
| Converted BC | 1/1，通过 |
| HBO | 1/1，通过，可由 `Hbo` 接口重新打开 |
| HBM | 1/1，通过，可由 `Hbm` 接口重新打开 |
| HBM 图目录 | 仅 `visual` |
| HBM ABI | `(1,576,588)` FP16 -> `(1,144,2048)` FP16 |
| `.partial.*` 残留 | 0 |
| Source BC 构建耗时 | 14.0 s |
| Converted BC 耗时 | 5 s |
| HBO 编译耗时 | 2:04:27 |
| HBM Link 耗时 | 17 s |
| HBM Pipeline 总耗时 | 2:04:50 |
| `vision_bc.exit.txt` | `exit_code=0` |
| `vision_hbm.exit.txt` | `exit_code=0` |

## 产物

| 产物 | 大小（bytes） | SHA256 |
| --- | ---: | --- |
| `LocateAnything-3B_vision_336x336_w8_nash-p_corenum_4.visual.bc` | 428303920 | `8bdb22deb6c29affc06b98accaed18917431278583af5a5fa29dbf99479bb791` |
| `LocateAnything-3B_vision.visual_convert.bc` | 428597890 | `c0f036a1f2667f71f13c1e5ef5bc2832fff15d8edc0b8ad11a04fafb4dd9028e` |
| `LocateAnything-3B_vision.visual.hbo` | 517026520 | `534f75f0a8f7a9d9bf35ff693955d4ad9dffabb635ff30d045936b033d12c2e1` |
| `LocateAnything-3B_vision.hbm` | 491258184 | `0f476272b0442d2457e772a158697eb340484db0f4e43724cbe7a2100947a090` |

## 问题与偏差

- Vision 当前没有静态激活 Observer；构建使用包含完整 fast_336 Profile 的 Stage 4 Scale Manifest，未复用 stable_672 Scale。
- HBDK 的 HBO 进度条使用回车原地刷新，长时间停留在日志的 10% 后才集中写出 11%-100%；进程 CPU、内存和最终退出码均正常。
- 外层 SSH 等待在 2 小时时达到本地超时，但远端编译进程未退出；最终原任务正常完成，没有重启或覆盖产物。
- 4090 验收只覆盖编译产物、可加载性和图契约，不等同于 S600 数值推理通过。

## 结论

fast_336 Vision 的 Source BC、Converted BC、4-Core HBO 和 HBM 已全部构建完成，图名、输入输出形状、边界精度、文件完整性和退出状态均通过验收。stable_672 未修改。

## 下一阶段门槛

进入 Stage 6 Language 构建。Language 必须使用同一 Stage 4 Scale Manifest，生成固定 13 图目录，并通过 Prefill 256、KV Cache 1024、PBD q6-q12、AR q1-q5 的完整 ABI 检查。
