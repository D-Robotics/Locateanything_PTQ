# Stage 1: balanced_448 配置与本地契约

## 状态

配置已新增，本地语法、配置、形状、隔离路径和四条 dry-run 验证通过。本阶段未生成校准张量、激活 Scale、BC、HBO 或 HBM。

## 配置决策

- `448 x 448` 由现有通用 Vision Profile 推导，不新增分辨率白名单或硬编码形状。
- `chunk_size=384` 为 256 个 Visual Token 保留 128 个文本位置；已有固定样本最长非视觉 Prompt 为 70 个 Token。
- `cache_len=2048` 与 `runtime.max_new_tokens=1536` 满足 `chunk + generation <= cache`，并保留 128 个 KV 位置余量。
- `batch_size=1` 显式写入配置，避免依赖默认值。
- 保留当前 W8A8、fused Prefill、compact logits、PBD q6 和 AR q1 契约。
- `calibration.max_new_tokens=1024` 只控制离线 Float 生成，不复用 336 的激活 Scale。

## 已执行验证

```bash
python -m py_compile \
  compiler/configuration.py compiler/quantize.py compiler/build_adapter.py \
  compiler/model/contract.py compiler/pipeline/prepare.py \
  compiler/pipeline/calibrate.py compiler/pipeline/vision_build.py \
  compiler/pipeline/language_build.py

python compiler/quantize.py \
  --config compiler/config/balanced_448.yaml prepare --dry-run

python compiler/quantize.py \
  --config compiler/config/balanced_448.yaml \
  calibrate --max-samples 2 --checkpoint-samples 1 --dry-run

python compiler/quantize.py \
  --config compiler/config/balanced_448.yaml \
  build --component vision --target bc --dry-run

python compiler/quantize.py \
  --config compiler/config/balanced_448.yaml \
  build --component language --target bc --dry-run
```

## 预期解析值

```text
image=448x448
vision_input=(1,1024,588)
vision_output=(1,256,2048)
visual_tokens=256
chunk_size=384
cache_len=2048
batch_size=1
runtime.max_new_tokens=1536
```

实际解析值与上述契约一致：

```text
grid_hw=[32,32]
patch_count=1024
vision_input_shape=[1,1024,588]
visual_token_count=256
projected_visual_shape=[1,256,2048]
batch_size=1
language_graph_count=13
compact_logits=true
fuse_initial_pbd=true
```

## 验证结果

| 检查 | 结果 |
| --- | --- |
| Python 语法 | 通过，8 个关键文件 |
| YAML 加载与 schema | 通过 |
| 448 Vision 形状推导 | 通过 |
| Prepare dry-run | 通过，未执行子进程 |
| Calibration dry-run | 通过，`max_samples=2`，未执行子进程 |
| Vision BC dry-run | 通过，Batch 1、448 ABI 和独立 Scale 路径已传递 |
| Language BC dry-run | 通过，Prefill 512、KV 2048、Batch 1、13 图已传递 |
| 输出目录隔离 | 通过，未指向 336/672 目录 |
| KV 越界拒绝 | 通过，`384 + 1665 > 2048` 在调度前失败 |
| 336 Scale Profile 串用拒绝 | 通过，报告 336/448 的 Grid、Patch、输入输出和 Visual Token 漂移 |
| `git diff --check` | 通过 |

本地 Windows 环境只完成配置与调度验证，没有模型、CUDA/OELLM SDK 结果；不能据此声称 Float、Calibration 或 HBM 已通过。

## 下一阶段门槛

完成语法、配置加载、形状推导、输出隔离和四条 dry-run 后，使用已核验的固定样本 448 Float 证据作为进入校准的筛查依据。该证据只用于 Profile 选择，不作为公开 Benchmark。下一步提交 1200 条校准阶段确认。
