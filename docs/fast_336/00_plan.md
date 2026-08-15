# LocateAnything fast_336 分阶段实施计划

## 状态

| 阶段 | 内容 | 状态 | 记录 |
| --- | --- | --- | --- |
| 1 | Float 224 结构验证 | 已通过 | `01_float_224_validation.md` |
| 2 | Float 分辨率精度对比 | 已完成；224 未通过，336 经全视频复核后选为 fast 候选 | `02_float_accuracy_comparison.md` |
| 3 | 配置参数化与双 Profile 共用实现 | 代码完成；本地契约验证通过 | `03_configuration_parameterization.md` |
| 4 | 1200 条 fast_336 校准 | 已完成并通过验收 | `03_calibration.md` |
| 5 | Vision 编译与逐级验证 | 已完成并通过验收 | `04_vision_build.md` |
| 6 | Language 编译与逐级验证 | 已完成并通过验收 | `05_language_build.md` |
| 7 | S600 对比验收 | 已完成并通过工程验收，数值偏差完整保留 | `06_s600_comparison.md` |
| 8 | 最终汇总 | 已完成 | `FINAL_SUMMARY.md` |

## 已确认 Profile

| 参数 | fast_336 | stable_672 |
| --- | ---: | ---: |
| 图像尺寸 | 336 x 336 | 672 x 672 |
| Patch Size | 14 | 14 |
| Merge Size | 2 | 2 |
| Patch Grid | 24 x 24 | 48 x 48 |
| Patch 数量 | 576 | 2304 |
| Visual Token | 144 | 576 |
| Prefill | 256 | 1024 |
| KV Cache | 1024 | 4096 |
| 运行时最大生成 Token | 768 | 现有稳定配置 |
| PBD Query | 6 | 6 |
| AR Query | 1 | 1 |
| 量化 | 沿用 stable_672 的 W8A8 策略，重新生成激活 Scale | W8A8 稳定版 |

fast_336 仅对目标检测、帧率、阶段耗时和资源占用进行对比验收。stable_672 保持不变，不作为待淘汰产物处理。

> 2026-08-14 Float 筛查表明 224 未通过检测门槛。336 的 350 帧多人视频总框数为 5913，stable_672 为 5914，用户确认视觉效果可以接受，因此将 fast 候选调整为 336。逐帧框数误差 18.45%、IoU 0.5 框位置不一致率 26.60%，未达到原 15% 数值门槛，该偏差保留在 Stage 2 记录中，不作为人工 Ground Truth 精度结论。

## 执行原则

1. 672 与 336 使用同一套 Prepare、编译和推理实现，通过 YAML 选择 Profile。
2. 图像尺寸、Prefill、KV Cache、生成上限、量化、路径和输出目录保持解耦，不限定用户只能使用 672 或 336。
3. Patch 数量、Visual Token 数量和 Vision 输入输出形状由配置及模型结构推导。
4. fast_336 使用独立的校准、Float、BC、HBO、HBM、日志和报告目录，不复用 stable_672 的激活 Scale 或 HBM。
5. 每阶段完成后立即写记录，不以进程存活、文件存在、非零输出或 HBM 可加载代替验收。
6. 每个长时阶段开始前单独列出输入、输出和验收条件；按用户当前授权连续执行，仅在参数决策、破坏性操作或验收失败时暂停。
7. fast_336 通过后，未采用的 fast_224 运行产物移入回收站；stable_672 始终保留。

## 校准生成上限

Prepare 阶段的 Float 预测和运行时统一使用 `max_new_tokens=768`。数据集标准答案会单独保存为 `target_token_ids`，不由 Prepare 的生成上限截断；因此不再使用 896 这一额外上限。

```yaml
calibration:
  max_new_tokens: 768

runtime:
  max_new_tokens: 768
```

`Prefill 256 + max_new_tokens 768 = KV Cache 1024`，与 fast_336 的 Language 图固定容量一致。

## 阶段记录要求

每份记录必须包含：实际配置、输入、命令、完成数量、结果、产物路径、问题或偏差、结论和下一阶段门槛。
