[English](./README.md) | 简体中文

# Locateanything_PTQ

![PTQ](https://img.shields.io/badge/PTQ-LocateAnything--3B-4C8C4A)
![W8](https://img.shields.io/badge/权重-W8-E67E22)
![RDK S600](https://img.shields.io/badge/目标平台-RDK%20S600-2F6BFF)
![C++17](https://img.shields.io/badge/Console-C%2B%2B17-00599C?logo=cplusplus)

<p align="center">
  <img src="assets/LocateAnything.jpg" alt="LocateAnything" width="100%">
</p>

`Locateanything_PTQ` 提供 LocateAnything-3B 的主机端校准、训练后量化以及
BC/HBO/HBM 编译流程，并包含用于验证 HBM 的独立 C++ Console。本仓库不依赖
ROS 或 TROS；运行时集成由
[hobot_locateanything](https://github.com/LiuAnclouds/hobot_locateanything) 维护。

源码采用 CC BY-NC 4.0 协议发布，不授予商业使用权。

## 支持任务

| Console 命令 | 任务 |
| --- | --- |
| `/detect person,car` | 开放词汇目标检测 |
| `/ground <phrase>` | 指代定位 |
| `/ground_single <phrase>` | 单目标指代定位 |
| `/gui <element>` | GUI 点定位 |
| `/gui_box <element>` | GUI 框定位 |
| `/text` | 带文本框的 OCR |
| `/ground_text <text>` | 指定文本定位 |
| `/layout title,table,figure` | 文档版面定位 |
| `/point <target>` | 点定位 |

## 模型与量化

<p align="center">
  <img src="assets/LocateAnything_pipeline.png" alt="LocateAnything 推理流程" width="100%">
</p>

模型流程为 `图像 + Prompt -> MoonViT -> Qwen2.5 Decoder -> 结构化结果解析`。

| 项目 | 配置 |
| --- | --- |
| 模型 | LocateAnything-3B |
| Vision | MoonViT，27 个 Block，`672 x 672`，W8 权重 |
| Language | Qwen2.5 Decoder，36 层，Hidden Size 2048，W8 权重 |
| LM Head | W8，词表大小 152681 |
| 激活 | 动态量化 |
| 校准数据 | 1,200 张选定图片 |
| Language 图 | 固定 13 个图 |
| Prefill / KV Cache | 1024 / 4096 Token |
| 解码 | PBD q=6、AR q=1、Host 采样 |
| 目标平台 | Nash-P，4 个 BPU 核，L2 `6:6:6:6` |

## 开发环境

| 项目 | 要求 |
| --- | --- |
| 编译主机 | Linux x86_64、CUDA、PyTorch |
| SDK | D-Robotics OELLM/HBDK 环境 |
| Python | Python 3，以及 `compiler/requirements-host.txt` 中的依赖 |
| Console | C++17、CMake、OpenCV、yaml-cpp |
| 部署目标 | 地瓜机器人 RDK S600，AArch64 |

## 使用介绍

### 1. 准备源模型

将官方 LocateAnything-3B 权重和 `locateanything_worker.py` 放到
`compiler/config/quantization.yaml` 指定的位置：

```text
compiler/models/LocateAnything-3B/
```

该路径相对于仓库根目录，可在 YAML 中修改。

### 2. 下载校准数据

校准数据仓库提供 `source.zip`。下载并解压后，编译器应能读取
`compiler/datasets/calibration/locateanything/source`：

```bash
export HF_ENDPOINT="https://hf-mirror.com"
CALIB_DIR="compiler/datasets/calibration/locateanything"
mkdir -p "$CALIB_DIR"

hf download xkj521999/OE_LA_Calibration_data source.zip \
  --repo-type dataset \
  --local-dir "$CALIB_DIR"
unzip -qo "$CALIB_DIR/source.zip" -d "$CALIB_DIR"

test -f "$CALIB_DIR/source/selected.jsonl"
```

数据集和生成的张量只作为本地输入，不提交到代码仓库。

### 3. 执行 PTQ 与编译

先进入外部 OELLM/HBDK 环境，再安装主机端 Python 依赖：

```bash
python -m pip install -r compiler/requirements-host.txt
```

按顺序执行：

```bash
python compiler/quantize.py \
  --config compiler/config/quantization.yaml \
  prepare

python compiler/quantize.py \
  --config compiler/config/quantization.yaml \
  calibrate --component all

python compiler/quantize.py \
  --config compiler/config/quantization.yaml \
  build --component all --target hbm
```

`--target bc` 只导出 BC；`--target hbm` 继续完成 HBO 编译和 HBM 链接。普通编译
使用配置文件中的输出目录；只有继续同一编译目录时才使用 `--resume`。

最终产物位于：

```text
compiler/outputs/chunk1024_cache4096_w8/
├── calibration/
├── build/vision/LocateAnything-3B_vision.hbm
├── build/language/LocateAnything-3B_language.hbm
├── build/language/LocateAnything-3B_embed_tokens.bin
└── logs/
```

### 4. 独立 C++ Console

Console 不依赖 ROS 或 ament。将生成的 HBM、Embedding 二进制和词表文件放到
`inference/config.yaml` 指定的位置，然后在仓库根目录编译：

```bash
cmake -S inference -B inference/build -DCMAKE_BUILD_TYPE=Release
cmake --build inference/build --parallel 2
./inference/build/console --config inference/config.yaml
```

交互示例：

```text
[User] <<< /image <image-path>
[User] <<< /detect person,car,bicycle
```

视频输入使用 `/video <path>`，随后输入任务命令。结果写入
`inference/outputs/<input-name>/`：

```text
annotated.jpg                  # 图片输入
prediction.json
annotated.mp4                  # 视频输入
predictions.jsonl
summary.json
```

同一输入重复推理时，目录中的结果文件会被覆盖。

## 结果展示

### 示例

目标检测，`/detect person,bus,bicycle`

<img src="assets/results/detection_multiclass.jpg" alt="目标检测" width="720">

GUI 定位，`/gui_box Go to file/function; Environment tab; Files tab`

<img src="assets/results/gui_rstudio.jpg" alt="GUI 定位" width="720">

指代定位，`/ground person wearing a graduation cap; woman in a black dress; clock tower`

<img src="assets/results/referring_graduation.jpg" alt="指代定位" width="520">

OCR，`/text`

<img src="assets/results/ocr_scrapbook.jpg" alt="OCR" width="720">

指定文本定位，`/ground_text LIVE love LAUGH; laugh giggle be silly; Yes Virginia`

<img src="assets/results/ground_text_scrapbook.jpg" alt="指定文本定位" width="720">

文档版面，`/layout plot,text`

<img src="assets/results/layout_plot.jpg" alt="文档版面" width="720">

点定位，`/point succulent`

<img src="assets/results/point_succulent.jpg" alt="点定位" width="512">

### 性能

| 任务 | 输出 Token | Vision (ms) | Prefill (ms) | Decode (ms) | 总耗时 (ms) | Decode (Token/s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 目标检测 | 47 | 252.5 | 149.9 | 525.0 | 970.5 | 89.5 |
| GUI 定位 | 14 | 253.2 | 149.7 | 266.0 | 720.7 | 52.6 |
| 指代定位 | 14 | 246.0 | 152.3 | 164.5 | 603.6 | 85.1 |
| OCR | 66 | 245.5 | 152.4 | 665.3 | 1148.3 | 99.2 |
| 指定文本定位 | 15 | 253.0 | 150.2 | 166.6 | 653.5 | 90.0 |
| 文档版面 | 43 | 245.4 | 151.8 | 448.1 | 904.7 | 96.0 |
| 点定位 | 37 | 246.0 | 152.2 | 480.5 | 923.5 | 77.0 |
