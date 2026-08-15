# Stage 2：Float 低分辨率与 672 精度对比

## 状态

**测量完成；224 未通过，336 经 350 帧全量复核后由用户选为 fast 候选，2026-08-14。**

本阶段完成了四类固定样例对比、24 个带官方检测框标注样本的分辨率筛查，以及一段 350 帧多人视频在 224、336、672 下的完整推理和同帧对照。224 的检测误差明显超过门槛；336 与 672 的全视频总框数分别为 5913 和 5914，视觉效果经用户确认可以接受，因此选为 fast 候选。逐帧框数误差和框位置不一致率仍超过 15%，作为相对 672 的偏差保留，不写成数值通过。

## 实际配置

| 项目 | 值 |
| --- | --- |
| Checkpoint | `/home/kangjie.xu/Eagle/Embodied/LocateAnything-3B` |
| Float dtype | BF16 |
| Device | NVIDIA GeForce RTX 4090，`cuda:0` |
| 图像预处理 | 保持比例缩放，RGB 128 Letterbox |
| 对比 Profile | 672 x 672、224 x 224、336 x 336 |
| Generation Mode | slow |
| 随机种子 | 20260814；检测样本按 `seed + sample_index` 成对固定 |
| 固定样例最大生成 Token | 64 至 192，按任务设置 |
| 检测筛查最大生成 Token | 192 |
| 检测匹配条件 | 类别一致且 Box IoU >= 0.5，贪心一对一匹配 |

本阶段比较原始 Float 模型，不包含 W8A8、Prefill 256、KV Cache 1024、PBD q6、AR q1 或 S600 性能。

多人视频补充测试使用 Float BF16、Hybrid Generation、`max_new_tokens=512`。224、336 和 672 均对全部 350 帧逐帧推理；三者使用相同视频、Prompt 和逐帧固定种子。先完成 35 帧筛查，再以全部 350 个同帧结果复核 336。

## 输入

### 固定任务样例

| 任务 | 图片 | Prompt | SHA256 |
| --- | --- | --- | --- |
| 多类别检测 | `07_detection_multiclass.jpg` | `Locate all the instances that matches the following description: person</c>bus</c>bicycle.` | `a5f577d2df8562a276aa68f9f3a56b35c67994d8bb7f60463b46d52462f2d1f8` |
| OCR | `04_ocr_scrapbook.jpg` | `Detect all the text in box format.` | `4b029ded5bf209006e194f12ac7719b0cbdfb301a104cd0371f18c3069a2b7ab` |
| GUI 框定位 | `02_gui_rstudio.jpg` | `Locate the region that matches the following description: Go to file/function.` | `e9309c590a3e16dcd020218ada1f953c09824a94342addebcd7a3a2c5952e621` |
| 指代定位 | `03_referring_graduation.jpg` | `Locate all the instances that match the following description: person wearing a graduation cap.` | `7ab46d6d58fc0f63c905aba243525f82a164a08a3222def4eb8c66e1654f0bfd` |

### 标注检测样本

数据来自 1200 条校准包中的 `selected.jsonl`：

```text
/home/kangjie.xu/oe_locateanything/LocateAnything/compiler/datasets/
  calibration/locateanything/source/selected.jsonl
```

- `selected.jsonl`：1200 条，SHA256 `521c9203579b165b619934684ca0dd44f9a33dc9c68e0bb6abb17f481d17850b`；
- Detection：660 条，其中 500 条为单查询类别，作为本次抽样池；
- 按 Sample ID 的固定哈希排序，从目标数量 1、2 至 4、5 至 9、10 至 20 四档各取 6 条；
- 共 24 张图片、24 个 Prompt、147 个官方框；
- 小/中/大目标按原图像素面积 `<32^2`、`32^2` 至 `<96^2`、`>=96^2` 划分。

该抽样用于 Profile 早期淘汰，不作为公开精度 Benchmark。

### 多人视频

| 项目 | 值 |
| --- | --- |
| 视频 | `inference/image/person_video.avi` |
| SHA256 | `6e726db669584e633a647c64e2349f1aa5840c49e4666e24760029ea30e5357e` |
| 规格 | 856 x 480、25 FPS、350 帧、14 秒 |
| Prompt | `Locate all the instances that matches the following description: person.` |
| 224 完整推理 | 350/350 帧 |
| 336 完整推理 | 350/350 帧 |
| 672 完整基准 | 350/350 帧 |
| 35 帧初筛 | 等间隔采样，约每 0.41 秒一帧 |
| 全量复核 | 336 与 672 的全部 350 个同帧 |
| 对照条件 | 同一原始帧、Prompt、Hybrid Generation 和逐帧固定种子 |
| Box 匹配 | 映射回原视频坐标后，IoU >= 0.5 贪心一对一匹配 |

用户验收口径以检测框为主：相对 672 的框数误差和框位置不一致率在 10% 至 15% 内可以接受；小目标和 OCR 下降不作为本轮 fast Profile 的硬门槛。

## 命令

环境与 GPU 检查沿用 Stage 1。固定样例和标注检测筛查均在单次模型加载后成对执行：

```powershell
@'
# 读取固定样例或 selected.jsonl。
# 对每张图片分别生成 672 和 224 Letterbox 输入。
# 使用同一 Prompt、Generation Mode 和随机种子执行 Float 推理。
# 检测样本将官方框转换到 Letterbox 坐标，并按 IoU 0.5 贪心匹配。
# 每个样本保留原始输出、预测框、官方框和匹配结果，最后汇总指标。
'@ | ssh 4090 /home/kangjie.xu/miniforge3/envs/locateanything/bin/python -
```

结果文件核验：

```bash
wc -l /home/kangjie.xu/oe_locateanything/LocateAnything/artifacts/fast_224/float_accuracy_20260814/detection_pairwise.jsonl
sha256sum /home/kangjie.xu/oe_locateanything/LocateAnything/artifacts/fast_224/float_accuracy_20260814/detection_pairwise.jsonl
```

多人视频分别使用单次 Float 模型会话逐帧执行 224 和 336 推理，同时保存原始输出、映射回视频坐标的框、带框视频和固定采样帧。随后将低分辨率结果与已保存的 672 同帧输出进行 IoU 对照：

```text
Input:  person_video.avi, 350 frames
Run:    Float BF16, 224 x 224, hybrid, /detect person
Render: person_video_224_annotated.mp4
Compare: 35 shared frames, Float 224 vs Float 672, IoU >= 0.5

Run:    Float BF16, 336 x 336, hybrid, /detect person
Render: person_video_336_annotated.mp4
Compare: 35 shared frames, Float 336 vs Float 672, IoU >= 0.5

Run:    Float BF16, 672 x 672, hybrid, /detect person
Render: person_video_672_annotated.mp4
Compare: 350 shared frames, Float 336 vs Float 672, IoU >= 0.5
```

## 完成数量

| 项目 | 完成情况 |
| --- | ---: |
| 固定任务样例 | 4/4 |
| 固定样例 Profile 推理 | 8/8 |
| 标注检测样本 | 24/24 |
| 检测分辨率 Profile | 7/7：224、336、392、448、504、560、672 |
| 检测 Profile 推理 | 168/168 |
| 官方检测框 | 147 |
| 正常输出 `<|im_end|>` | 每个分辨率均为 24/24 |
| 多人视频 224 推理 | 350/350 帧 |
| 多人视频 224/672 同帧对照 | 35/35 帧 |
| 224 带框视频 | 350 帧、25 FPS，已验证首帧可解码 |
| 多人视频 336 推理 | 350/350 帧 |
| 多人视频 336/672 同帧对照 | 35/35 帧 |
| 336 带框视频 | 350 帧、25 FPS，已验证首帧可解码 |
| 多人视频 672 完整基准 | 350/350 帧 |
| 多人视频 336/672 全量同帧复核 | 350/350 帧 |
| 336/672 并排对照视频 | 350 帧、25 FPS，已验证首帧可解码 |
| 完整 1200 条校准 | 0，本阶段不执行 |

## 结果

### 标注检测筛查

| 指标 | Float 672 | Float 224 | 变化 |
| --- | ---: | ---: | ---: |
| 预测框 | 113 | 73 | -40 |
| IoU 0.5 真阳性框 | 86 | 41 | -45 |
| Precision@0.5 | 76.1% | 56.2% | -19.9 pp |
| Recall@0.5 | 58.5% | 27.9% | -30.6 pp |
| 大目标 Recall@0.5，55 个 GT | 83.6% | 67.3% | -16.4 pp |
| 中目标 Recall@0.5，66 个 GT | 53.0% | 6.1% | -47.0 pp |
| 小目标 Recall@0.5，26 个 GT | 19.2% | 0.0% | -19.2 pp |

224 对大目标仍有一定检测能力，但中目标召回降至 6.1%，本次抽样中的 26 个小目标没有一个达到 IoU 0.5。

### 分辨率补充筛查

224 未通过后，使用完全相同的 24 张图片、Prompt、Ground Truth、随机种子和 IoU 规则补测 336、392、448、504 与 560。Prefill 候选值按“Visual Token + 已观测最长 70 个非视觉 Prompt Token”计算并向 64 的倍数留出余量。

| 分辨率 | Visual Token | Prefill 候选 | Precision@0.5 | Recall@0.5 | 大目标 Recall | 中目标 Recall | 小目标 Recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 224 | 64 | 256 | 56.2% | 27.9% | 67.3% | 6.1% | 0.0% |
| 336 | 144 | 256 | 58.3% | 38.1% | 72.7% | 24.2% | 0.0% |
| 392 | 196 | 320 | 66.7% | 43.5% | 72.7% | 36.4% | 0.0% |
| **448** | **256** | **384** | **66.7%** | **53.1%** | **80.0%** | **50.0%** | **3.8%** |
| 504 | 324 | 448 | 71.3% | 52.4% | 78.2% | 48.5% | 7.7% |
| 560 | 400 | 512 | 73.1% | 53.7% | 74.5% | 54.5% | 7.7% |
| stable_672 | 576 | 1024 | 76.1% | 58.5% | 83.6% | 53.0% | 19.2% |

448 是当前曲线的效率拐点：总体召回达到 stable_672 的 90.7%，大目标和中目标召回分别达到 stable_672 的 95.7% 和 94.3%。继续增加到 504 或 560，总体召回没有形成与 Visual Token 增长相称的提升。

小目标是例外。448、504 和 560 的小目标召回均明显低于 stable_672，因此小目标检测仍应使用 stable_672，不能用当前全图缩放快速 Profile 替代。

分辨率变化并不保证单个指标严格单调；生成模型的离散输出、位置编码插值和固定随机采样都会造成小幅波动。本表用于选择候选档位，不作为公开 Benchmark。

### 多人视频 224 与 672 同帧对照

35 个固定采样帧只比较映射回原视频坐标后的可见框，落在 Letterbox 填充区且映射后无有效面积的框不计入两侧数量。

| 指标 | Float 224 | Float 672 基准 | 224 相对误差 |
| --- | ---: | ---: | ---: |
| 可见检测框总数 | 460 | 592 | 22.30% |
| 逐帧绝对框数误差加权值 | - | - | 22.97% |
| IoU >= 0.5 匹配参考框 | 329 | 592 | 一致率 55.57% |
| 参考框位置不一致率 | - | - | 44.43% |
| 匹配框平均 IoU | 0.713 | - | - |
| 匹配框中位 IoU | 0.712 | - | - |

三个检测框指标均未达到 15% 门槛。完整 350 帧的 224 推理共产生 4652 个可见框，平均每帧 13.29 个。补齐 672 全 350 帧后，224 的总框数差为 21.34%、逐帧框数误差为 22.66%、框位置不一致率为 44.52%，与 35 帧初筛结论一致。

可视化显示误差不只来自远处小行人：224 在密集区域存在漏框、相邻行人框合并或漂移，以及预测落入 Letterbox 填充区后映射成狭长边缘框的情况。因此即使不要求小目标和 OCR，224 仍不满足当前多人检测场景。

### 多人视频 336 与 672 同帧对照

336 沿用与 224 完全相同的 35 个固定采样帧和统计规则。

| 指标 | Float 336 | Float 672 基准 | 336 相对误差 |
| --- | ---: | ---: | ---: |
| 可见检测框总数 | 565 | 592 | 4.56% |
| 逐帧绝对框数误差加权值 | - | - | 17.74% |
| IoU >= 0.5 匹配参考框 | 422 | 592 | 一致率 71.28% |
| 参考框位置不一致率 | - | - | 28.72% |
| 匹配框平均 IoU | 0.762 | - | - |
| 匹配框中位 IoU | 0.779 | - | - |

336 的总框数差已经进入 10% 范围，但该值包含不同帧多检与漏检的相互抵消。逐帧绝对框数误差为 17.74%，框位置不一致率为 28.72%，仍未达到 15% 门槛。

完整 350 帧的 336 推理共产生 5913 个可见框，平均每帧 16.89 个。可视化中 224 的大量狭长边缘框已明显减少，普通近景行人框更稳定；剩余误差主要集中在密集人群中的漏框、相邻目标框合并和局部框漂移。

### 多人视频 336 与 672 全量复核

672 完整处理同一视频的 350 帧后，对全部同帧重新计算：

| 指标 | Float 336 | Float 672 基准 | 336 相对误差 |
| --- | ---: | ---: | ---: |
| 可见检测框总数 | 5913 | 5914 | 0.017% |
| 平均每帧可见框 | 16.894 | 16.897 | 0.003 框 |
| 逐帧绝对框数误差加权值 | - | - | 18.45% |
| IoU >= 0.5 匹配参考框 | 4341 | 5914 | 一致率 73.40% |
| 参考框位置不一致率 | - | - | 26.60% |
| 匹配框平均 IoU | 0.766 | - | - |
| 匹配框中位 IoU | 0.777 | - | - |

全量结果确认 336 没有系统性少检：总框数只差 1 个。但不同分辨率在同一帧上的框数分配和框位置仍有差异，逐帧指标没有达到原 15% 门槛。由于视频没有人工 Ground Truth，672 的多检、漏检和框偏差同样会被计算为 336 的“不一致”；因此该指标用于描述 Profile 差异，不等价于 336 的真实错误率。

用户在查看 336 带框视频后确认效果可以接受。综合总框数量、视觉验收以及不追求小目标的使用边界，本阶段将 336 选为 fast 候选，同时完整保留上述数值偏差。

### 固定任务样例

| 任务 | Float 672 | Float 224 | 结论 |
| --- | --- | --- | --- |
| 多类别检测 | 3 类、6 框 | 3 类、4 框 | person 与 bus 保留；3 个 bicycle 只保留 1 个 |
| OCR | 5 段文字、5 框 | 2 段文字、2 框 | 漏掉 3 段，并出现字符识别错误 |
| GUI 框定位 | 1 框 | 1 框 | 两框 IoU 为 0，224 未定位到 672 对应区域 |
| 指代定位 | 1 框 | 1 框 | 两框 IoU 为 0.045，结果差异显著，需要人工任务标注判定 |

多类别检测中，224 保留框与 672 对应框的最佳 IoU 分别为：person 0.948/0.791、bus 0.935、bicycle 0.932。主要问题是小自行车漏检，不是保留框整体漂移。

### 耗时说明

Float 推理在同一进程内依次执行，包含不同程度的 CUDA 预热和缓存影响。本阶段不将 Float 耗时作为 S600 性能结论，性能统一留到 Stage 7。

## 产物路径

| 产物 | 路径 |
| --- | --- |
| 原始逐样本检测结果 | `/home/kangjie.xu/oe_locateanything/LocateAnything/artifacts/fast_224/float_accuracy_20260814/detection_pairwise.jsonl` |
| 结果行数 | 53 |
| 结果 SHA256 | `ece65be8550d4fb64cccdd78ebaa91c1d53972a28764853e4beb3a3b607430bc` |
| 336 补测结果 | `/home/kangjie.xu/oe_locateanything/LocateAnything/artifacts/fast_224/float_accuracy_20260814/resolution_sweep_336.jsonl` |
| 336 结果行数 / SHA256 | 28 / `0a29be040f1af5fef7d07be5faec82c40ef61d1b464b1de701e47277fb686285` |
| 392 至 560 补测结果 | `/home/kangjie.xu/oe_locateanything/LocateAnything/artifacts/fast_224/float_accuracy_20260814/resolution_sweep_392_448_504_560.jsonl` |
| 392 至 560 行数 / SHA256 | 103 / `c5f578b3d787e2f4f8f2de09404f0d7311ac06f3392573854e7db587d24c319e` |
| 224 多人视频逐帧结果 | `/home/kangjie.xu/oe_locateanything/LocateAnything/artifacts/fast_224/person_video_224_review/person_video_224_full.jsonl` |
| 逐帧结果行数 / SHA256 | 352 / `a5669f8995e462f7fcc4c1e6c8235ff349149831d9a43212ecbca2424bbf52cf` |
| 224 带框视频 | `/home/kangjie.xu/oe_locateanything/LocateAnything/artifacts/fast_224/person_video_224_review/person_video_224_annotated.mp4` |
| 带框视频大小 / SHA256 | 6808632 bytes / `6d308008a5d54ca3bc910dc2dfbc8702c1d1e8bbed688261b04d3f058b1def3b` |
| 224/672 同帧报告 | `/home/kangjie.xu/oe_locateanything/LocateAnything/artifacts/fast_224/person_video_224_review/comparison_672/person_video_224_vs_672_report.json` |
| 同帧报告 SHA256 | `d826054193a95d0184aceb59ecdd5de2b3d526a99840836c4607d85bc740559f` |
| 224/672 全量同帧报告 | `/home/kangjie.xu/oe_locateanything/LocateAnything/artifacts/fast_224/person_video_224_review/comparison_672_full/person_video_224_vs_672_report.json` |
| 224/672 全量报告 SHA256 | `a566204b815988c9f3f01f5f8737bad8b341a0b41c640f37408612d5b5203c4a` |
| 代表帧对照拼图 | `/home/kangjie.xu/oe_locateanything/LocateAnything/artifacts/fast_224/person_video_224_review/comparison_672/person_video_224_vs_672_contact_sheet.jpg` |
| 本机可视化副本 | `analysis/fast_resolution/person_video_224_review/` |
| 336 多人视频逐帧结果 | `/home/kangjie.xu/oe_locateanything/LocateAnything/artifacts/fast_224/person_video_336_review/person_video_336_full.jsonl` |
| 336 逐帧结果行数 / SHA256 | 352 / `9101dc8b6f1d3fa92ccecf535de93e62c7cf4034ca89d2874b97830640f7b551` |
| 336 带框视频 | `/home/kangjie.xu/oe_locateanything/LocateAnything/artifacts/fast_224/person_video_336_review/person_video_336_annotated.mp4` |
| 336 带框视频 SHA256 | `bb1460eac918524a62cb265261e129060056346b1efa9339923790305865d854` |
| 336/672 同帧报告 | `/home/kangjie.xu/oe_locateanything/LocateAnything/artifacts/fast_224/person_video_336_review/comparison_672/person_video_336_vs_672_report.json` |
| 336 同帧报告 SHA256 | `eef6f9a8e7cb816515cc2db715762f1acd22cf4152b8fa805f11d014a554b85b` |
| 336 代表帧对照拼图 | `/home/kangjie.xu/oe_locateanything/LocateAnything/artifacts/fast_224/person_video_336_review/comparison_672/person_video_336_vs_672_contact_sheet.jpg` |
| 336 本机可视化副本 | `analysis/fast_resolution/person_video_336_review/` |
| 672 多人视频逐帧结果 | `/home/kangjie.xu/oe_locateanything/LocateAnything/artifacts/fast_224/person_video_672_review/person_video_672_full.jsonl` |
| 672 逐帧结果行数 / SHA256 | 352 / `14f8aca213ba2a40b6a48b3821e711e773de74726072a837e80c5f7da071009a` |
| 672 带框视频 SHA256 | `64d80497c636655889996aff7197b4891d8004ff87dece19de5c14c5bdbfda68` |
| 336/672 全量同帧报告 | `/home/kangjie.xu/oe_locateanything/LocateAnything/artifacts/fast_224/person_video_336_review/comparison_672_full/person_video_336_vs_672_report.json` |
| 全量报告 SHA256 | `6c7bd1c71129fa5a0fda134618e438ac7731c97fd66090e0edfae5543a90c552` |
| 336/672 全量并排视频 | `/home/kangjie.xu/oe_locateanything/LocateAnything/artifacts/fast_224/person_video_336_review/comparison_672_full/person_video_336_vs_672_annotated.mp4` |
| 并排视频 SHA256 | `7df3260992bca683e9bbb4ef5a230bf17274b8b9035cc7bf380cb4aeb27573bf` |
| 全量对照本机副本 | `analysis/fast_resolution/person_video_336_review/comparison_672_full/` |
| 本阶段记录 | `docs/fast_336/02_float_accuracy_comparison.md` |

没有生成校准 Tensor、Scale、BC、HBO 或 HBM。

## 问题与偏差

1. 24 条检测数据来自校准数据而不是独立评测集，因此只用于方案筛查；不能对外宣称为模型精度。
2. 生成采用固定随机种子的 slow 模式，保证本轮成对可复现，但单个种子不等于完整统计评测。
3. GUI、OCR 和指代固定样例没有像检测样本一样计算任务 Ground Truth 指标；其结论限于输出数量、文本内容和 672/224 差异。
4. 当前环境的 MoonViT 使用 SDPA 回退路径。该路径不影响分辨率造成的输入信息损失判断，但 Float 耗时不用于性能比较。
5. 多人视频没有人工 Ground Truth，672 在该项中作为相对基准，因此这里只能衡量低分辨率相对稳定分辨率的框数和框位置变化，不能将 672 自身的误检视为正确标注。
6. 完整 224 视频生成期间同一 4090 上存在另一用户进程；本阶段不采信 Float 耗时作为性能结果，检测输出和同帧精度对照仍保留。

## 结论

原 fast_224 的 Stage 2 未通过。224 x 224 能完成 Float 前向和端到端生成，但当前全图缩放方案不满足以检测为主的精度门槛。即使明确接受小目标与 OCR 下降，多人视频相对 672 的框数误差仍为 22% 至 23%，框位置不一致率为 44.43%，不能按 10% 至 15% 标准验收。

336 x 336 相比 224 明显改善。350 帧全量结果中，336 与 672 的总框数只差 1 个；用户确认 336 视觉效果可以接受，因此选择 336 进入下一阶段。逐帧框数误差 18.45%、框位置不一致率 26.60%，未达到原 15% 数值门槛，作为已知偏差保留。

当前 fast 候选调整为 **336 x 336**，其结构契约为：

```text
Patch Grid       24 x 24
Vision input     (1,576,588)
Visual Token     144
Projected output (1,144,2048)
```

336 可继续使用 Prefill 256。按已观测最长 70 个非视觉 Prompt Token，`144 + 70 = 214`，小于 256；运行时最多生成 768 Token 时，`256 + 768 = 1024`，与 KV Cache 1024 一致。

因此暂停以下工作：

- 不启动完整 1200 条 fast_336 校准；
- 不生成 fast_336 W8A8 Scale；
- 不启动 fast_336 BC/HBO/HBM 编译；
- 不覆盖或清理 stable_672 及任何已接受产物。

## 下一阶段门槛

Stage 3 按以下候选契约进行配置参数化：

```text
image_size             336 x 336
visual_tokens          144
prefill                256
kv_cache               1024
runtime_max_new_tokens 768
pbd_query               6
ar_query                1
quantization            stable_672 W8A8 strategy, regenerate activation Scale
```

Stage 3 只改参数化和形状推导，不启动 1200 条校准。Stage 4 开始前仍需单独确认校准输入、输出、命令和验收条件。
