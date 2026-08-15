# Stage 1：Float 224 结构验证

## 状态

**结构验证已通过；224 后续在 Stage 2 精度验收中被淘汰，2026-08-14。**

本阶段只验证原始 Float 模型能否处理 224 x 224 输入及其结构形状，不包含量化、校准、BC/HBO/HBM 编译或 S600 测试。

## 实际配置

| 项目 | 值 |
| --- | --- |
| Checkpoint | `/home/kangjie.xu/Eagle/Embodied/LocateAnything-3B` |
| Float dtype | BF16 |
| Device | NVIDIA GeForce RTX 4090，`cuda:0` |
| 图像预处理 | 保持比例缩放，RGB 128 Letterbox |
| Patch Size | 14 |
| Merge Size | 2 |
| 对照分辨率 | 672 x 672 |
| 验证分辨率 | 224 x 224 |
| Prompt | `Locate all the instances that matches the following description: person</c>bus</c>bicycle.` |
| Generation Mode | slow，Stage 1 只用于确认端到端输出 |
| Stage 1 最大生成 Token | 96 |
| 随机种子 | 20260814 |

原 fast_224 候选的 Prefill 256、KV Cache 1024、运行时最大生成 768、PBD q6 和 AR q1 未在本阶段编译或验证。Stage 2 已将当前候选调整为 fast_336。

## 输入

| 项目 | 值 |
| --- | --- |
| 图片 | `/home/kangjie.xu/LA_TEST/Locateanything_PTQ/inference/image/07_detection_multiclass.jpg` |
| 原始尺寸 | 640 x 480 |
| SHA256 | `a5f577d2df8562a276aa68f9f3a56b35c67994d8bb7f60463b46d52462f2d1f8` |
| 查询类别 | person、bus、bicycle |

## 环境与命令

环境盘点：

```bash
ssh 4090
nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu \
  --format=csv,noheader
/home/kangjie.xu/miniforge3/envs/locateanything/bin/python -c \
  "import torch, transformers, decord, lmdb; print(torch.__version__, transformers.__version__)"
```

实测环境为 Python 3.10.20、PyTorch 2.5.1+cu121、Transformers 4.57.1、Decord 0.6.0 和 LMDB 2.2.1。执行前 GPU 空闲，显存占用 82 MiB。

验证脚本通过标准输入发送到 4090：

```powershell
@'
# 加载本地 AutoTokenizer、AutoProcessor 和 AutoModel。
# 对同一图片依次生成 672 和 224 Letterbox 输入。
# 记录 pixel_values、image_grid_hws、extract_feature 和 mlp1 形状。
# 使用相同 Prompt 和随机种子运行一次 slow Float 推理并解析框。
'@ | ssh 4090 /home/kangjie.xu/miniforge3/envs/locateanything/bin/python -
```

核心模型调用：

```python
vision = model.extract_feature(pixel_values, image_grid_hws)
vision = torch.cat(list(vision), dim=0)
projected = model.mlp1(vision).reshape(1, -1, 2048)
response = model.generate(
    pixel_values=pixel_values,
    input_ids=input_ids,
    attention_mask=attention_mask,
    image_grid_hws=image_grid_hws,
    tokenizer=tokenizer,
    max_new_tokens=96,
    use_cache=True,
    generation_mode="slow",
)
```

## 完成数量

| 项目 | 完成情况 |
| --- | ---: |
| Checkpoint 加载 | 1/1 |
| 分辨率 Profile | 2/2 |
| 图片 | 1/1 |
| Prompt | 1/1 |
| 224 结构检查 | 6/6 |
| 校准样本 | 0，本阶段不执行 |

224 的六项结构检查为：Letterbox 尺寸、16 x 16 Grid、256 Patch、588 Patch 展平维度、64 Visual Token、2048 Language Hidden Size。

## 结果

| Profile | Grid | Processor 输出 | Vision 输入 | Vision Merger 输出 | 投影输出 | Prompt Token | 有效框 |
| --- | --- | --- | --- | --- | --- | ---: | ---: |
| Float 672 | 48 x 48 | `(2304,3,14,14)` | `(1,2304,588)` | `(576,4608)` | `(1,576,2048)` | 620 | 6 |
| Float 224 | 16 x 16 | `(256,3,14,14)` | `(1,256,588)` | `(64,4608)` | `(1,64,2048)` | 108 | 4 |

224 投影结果全部为有限值，没有 NaN 或 Inf。MoonViT 完成了 16 x 16 Grid 的位置编码插值和前向计算。

Float 224 输出：

```text
<ref>person</ref><box><120><359><243><743></box>
<box><735><395><854><770></box>
<ref>bus</ref><box><0><166><620><701></box>
<ref>bicycle</ref><box><814><599><995><868></box><|im_end|>
```

同一输入下，672 返回 6 个框，224 返回 4 个框。该单样例说明 224 已能完成端到端检测，同时提示分辨率下降可能造成漏检；它不能替代 Stage 2 的多任务、同输入精度对比。

本次 Float 耗时不作为性能结论：672 首次执行包含 CUDA/算子预热，224 在热缓存后执行，两者时序条件不一致。

## 产物路径

| 产物 | 路径 |
| --- | --- |
| 阶段计划 | `docs/fast_336/00_plan.md` |
| 本阶段记录 | `docs/fast_336/01_float_224_validation.md` |
| 模型、校准和 HBM 产物 | 无，本阶段未生成 |

远程 Checkpoint、图片和仓库均未修改。

## 问题与处理

1. `/home/kangjie.xu/miniconda3/envs/locateanything_ptq` 缺少 `decord` 和 `lmdb`，未修改该环境，改用依赖完整的 `miniforge3/envs/locateanything`。
2. 官方 Processor 的 `image_grid_hws` 为 NumPy 数组，验证时显式转换为 CUDA 上的 `torch.int32`。
3. MoonViT 的 Flash Attention 和 MAGI Attention 在当前环境不可用，Float 验证按官方回退路径使用 SDPA。结构验收不受影响，Float 性能数据不采信。
4. Transformers 报告 `torch_dtype` 弃用和 GenerationMixin 兼容性警告；本次前向与生成成功，后续参数化时不借此改动上游模型代码。

## 结论

Stage 1 通过：MoonViT 支持 224 x 224 对应的 16 x 16 Patch Grid，并实测完成：

```text
(1,256,588) -> (1,64,2048)
```

Float 端到端检测输出可解析为有效边界框。本阶段只证明 224 结构可运行；Stage 2 的检测结果证明其精度不满足当前场景，后续实施使用 336。

## 下一阶段门槛

Stage 2 使用相同图片、相同 Prompt 和固定随机设置对比 224 与 672，至少覆盖：

- 目标检测：主要验收指标，同时覆盖多目标和小目标；
- OCR：记录长文本和小文字退化；
- GUI：记录小控件定位退化；
- 指代或小目标场景：记录框数量、类别和明显漏检。

Stage 2 必须分别保留原始输出和可解析结果。精度差异确认前不启动完整 1200 条校准。
