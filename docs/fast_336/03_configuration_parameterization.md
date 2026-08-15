# Stage 3: 配置参数化与双 Profile 共用实现

## 状态

代码完成，本地非模型验证通过。未启动 1200 条校准、BC/HBO/HBM 编译或 S600 测试。

## 实际配置

| 参数 | fast_336 | stable_672 |
| --- | ---: | ---: |
| 图像尺寸 | 336 x 336 | 672 x 672 |
| Patch Grid | 24 x 24 | 48 x 48 |
| Patch 数量 | 576 | 2304 |
| Vision 输入 | `(1,576,588)` | `(1,2304,588)` |
| Visual Token | 144 | 576 |
| Vision 输出 | `(1,144,2048)` | `(1,576,2048)` |
| Prefill | 256 | 1024 |
| 文本位置上限 | 112 | 448 |
| KV Cache | 1024 | 4096 |
| 运行时最大生成 Token | 768 | 当前稳定配置 |
| PBD / AR Query | 6 / 1 | 6 / 1 |
| 量化 | W8A8，重新生成激活 Scale | W8A8 稳定版 |

fast 配置文件为 `compiler/config/fast_336.yaml`。stable 配置继续使用
`compiler/config/quantization.yaml`，原有输出目录不变。

## 输入

- fast_336 与 stable_672 两套 YAML。
- MoonViT 固定架构参数：Patch 14、Merge 2、Hidden 2048。
- 当前 Prepare、Calibration、Vision Build 和 Console 运行时实现。

## 实现结果

1. `compiler/model/contract.py` 根据图像宽高推导 Grid、Patch 数量、Visual Token 和 Vision 输入输出形状，不限制分辨率白名单。
2. Prepare 删除 672 release 白名单与 `(1,2304,588)` 固定校验，保存张量时按当前 Profile 校验。
3. Calibration 接收图像宽高、缩放方式和填充值；生成记录和张量的 `fixed_profile` 必须一致。
4. Scale Manifest 记录完整 Vision Profile；336 构建会拒绝无 Vision Profile 的旧 672 Scale，也会拒绝显式记录为 672 的 Scale。
5. Vision BC、Converted BC、HBO 和 HBM 的 ABI 校验由当前图像尺寸推导。
6. Console 使用同一份 `VisionProfile` 驱动图像预处理、视觉 Token、Vision HBM ABI 和坐标恢复；稳定版默认仍为 672。
7. Prompt 超过 HBM Prefill 输入长度时明确报错，不进行静默截断。

## 验证命令

```bash
python -m py_compile \
  compiler/model/contract.py compiler/quantize.py compiler/build_adapter.py \
  compiler/model/factory.py compiler/model/vision.py \
  compiler/pipeline/prepare.py compiler/pipeline/calibrate.py \
  compiler/pipeline/vision_build.py

bash -n compiler/pipeline/run_prepare.sh \
  compiler/pipeline/run_calibrate.sh compiler/pipeline/build_vision.sh

python compiler/quantize.py --config compiler/config/fast_336.yaml prepare --dry-run
python compiler/quantize.py --config compiler/config/fast_336.yaml \
  calibrate --max-samples 2 --checkpoint-samples 1 --dry-run
python compiler/quantize.py --config compiler/config/fast_336.yaml \
  build --component vision --target bc --dry-run
python compiler/quantize.py --config compiler/config/fast_336.yaml \
  build --component language --target bc --dry-run
python compiler/quantize.py --config compiler/config/quantization.yaml prepare --dry-run
python compiler/quantize.py --config compiler/config/quantization.yaml \
  build --component vision --target bc --dry-run
```

## 完成数量与结果

| 检查 | 数量 | 结果 |
| --- | ---: | --- |
| YAML Profile 加载 | 2 | 通过 |
| Pipeline dry-run | 6 | 通过 |
| Python 语法文件 | 8 | 通过 |
| Shell 语法文件 | 3 | 通过 |
| 336/672 Vision 形状推导 | 2 | 通过 |
| 非法 350 尺寸拒绝 | 1 | 通过 |
| `256 + 769 > 1024` 拒绝 | 1 | 通过 |
| 672 Scale 用于 336 的拒绝路径 | 2 | 通过 |
| 运行时固定 672/576/2304 业务常量审计 | 5 个关键文件 | 通过 |

fast_336 dry-run 实际解析结果：

```text
image=336x336
visual_tokens=144
chunk_size=256
cache_len=1024
runtime.max_new_tokens=768
prepare.max_new_tokens=768
```

## 产物路径

- 配置：`compiler/config/fast_336.yaml`
- 编译器契约：`compiler/model/contract.py`
- 编译器入口：`compiler/quantize.py`
- Prepare / Calibration / Vision Build：`compiler/pipeline/`
- Console Profile：`inference/include/model_profile.hpp`
- 阶段记录：`docs/fast_336/03_configuration_parameterization.md`

本阶段没有生成新的 Scale、BC、HBO 或 HBM。

## 问题与偏差

- 当前 Windows Python 不含完整 `numpy + torch` 组合，因此未在本机执行 Calibration replay；只完成语法、纯 Profile、配置和调度验证。
- 当前 Windows 环境没有 S600 C++ 编译器和厂商头文件，Console 参数化代码尚未完成板端编译。该项在后续 S600 阶段验收，不写为已通过。
- `compiler/pipeline/coordinates.py` 的 672 像素换算属于独立 Language 审计报告，不在标准 Prepare/Build/Console 路径；若后续用它评估 fast_336，需在该审计前参数化。

## 结论

fast_336 与 stable_672 已共用同一套参数化实现。336 Profile 的编译输入输出、Prefill/KV 约束、Scale 隔离和 Console 数据路径已经贯通，本地契约验证未发现配置串用或静默截断路径。

## 下一阶段门槛

Stage 4 为完整 1200 条 fast_336 校准。开始前必须单独确认以下内容：

1. 校准输入为 HF `source.zip` 对应的 1200 条数据，实际记录数和文件完整性先检查。
2. `calibration.max_new_tokens=896` 用于离线 Float 预测；运行时仍为 768。
3. 使用独立目录 `compiler/outputs/fast_336_prefill256_cache1024_w8_fused_prefill_compact_logits/`，不复用 stable_672 或上一版 fast_336 Scale。
4. 先列出 4090 环境、输入、命令、预计产物和验收条件，再获得确认后启动长时任务。
