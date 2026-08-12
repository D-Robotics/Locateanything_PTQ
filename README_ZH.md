[English](./README.md) | 简体中文

# Locateanything_PTQ

![PTQ](https://img.shields.io/badge/PTQ-LocateAnything--3B-4C8C4A)
![W8](https://img.shields.io/badge/权重-W8-E67E22)
![RDK S600](https://img.shields.io/badge/目标平台-RDK%20S600-2F6BFF)
![C++17](https://img.shields.io/badge/推理-C%2B%2B17-00599C?logo=cplusplus)
![License](https://img.shields.io/badge/协议-Apache--2.0-lightgrey)

<p align="center">
  <img src="assets/LocateAnything.jpg" alt="LocateAnything" width="100%">
</p>

`Locateanything_PTQ` 将 LocateAnything-3B 转换为面向地瓜机器人 RDK S600 的
W8 HBM 模型，包含校准、PTQ、BC/HBO/HBM 编译和 C++ 推理程序。

## 支持任务

| 命令 | 任务 |
| --- | --- |
| `/detect person,car` | 开放词汇目标检测 |
| `/ground <phrase>` | 指代定位 |
| `/ground_single <phrase>` | 单目标指代定位 |
| `/gui <element>` | GUI 点定位 |
| `/gui_box <element>` | GUI 框定位 |
| `/text` | OCR |
| `/ground_text <text>` | 指定文本定位 |
| `/layout title,table,figure` | 文档版面定位 |
| `/point <target>` | 点定位 |

## 模型与量化

<p align="center">
  <img src="assets/LocateAnything_pipeline.png" alt="LocateAnything 推理流程" width="100%">
</p>

| 项目 | 配置 |
| --- | --- |
| 模型 | LocateAnything-3B |
| Vision | MoonViT，27 个 Block，`672 x 672` |
| Language | Qwen2.5 Decoder，36 层，Hidden Size 2048 |
| 量化 | Vision W8、Language W8、LM Head W8 |
| 校准 | 1,200 张图片，动态激活量化 |
| Prefill / KV Cache | 1024 / 4096 Token |
| 解码 | PBD q=6、AR q=1、Host 采样 |
| 目标平台 | Nash-P，4 个 BPU 核，L2 `6:6:6:6` |

## 开发环境

| 项目 | 要求 |
| --- | --- |
| 编译主机 | Linux x86_64、NVIDIA GPU、CUDA |
| SDK | D-Robotics LLM S600 SDK 1.0.5 |
| Python | Python 3.10、PyTorch |
| 部署平台 | RDK S600，AArch64 |

## 编译

### 1. 下载代码

```bash
git clone git@github.com:D-Robotics/Locateanything_PTQ.git
cd Locateanything_PTQ
```

### 2. 创建 Conda 环境并安装 OELLM SDK

```bash
conda create -n locateanything_ptq python=3.10 -y
conda activate locateanything_ptq
python -m pip install -U pip huggingface_hub

cd ..
wget https://d-robotics-aitoolchain.oss-cn-beijing.aliyuncs.com/llm_s600/1.0.5/D-Robotics_LLM_S600_1.0.5_SDK.tar.gz
tar -xzf D-Robotics_LLM_S600_1.0.5_SDK.tar.gz
cd D-Robotics_LLM_S600_1.0.5_SDK/oellm_build
python -m pip install -r requirements.txt
python -m pip install hbdk4_compiler-*.whl leap_llm-*.whl

cd ../../Locateanything_PTQ
python -m pip install -r compiler/requirements-host.txt
```

### 3. 下载 LocateAnything-3B

```bash
export HF_ENDPOINT="https://hf-mirror.com"

hf download nvidia/LocateAnything-3B \
  --local-dir compiler/models/LocateAnything-3B
```

### 4. 下载校准数据

```bash
mkdir -p compiler/datasets/calibration/locateanything/source

hf download xkj521999/OE_LA_Calibration_data source.zip \
  --repo-type dataset \
  --local-dir compiler/datasets/calibration/locateanything

unzip -qo \
  compiler/datasets/calibration/locateanything/source.zip \
  -d compiler/datasets/calibration/locateanything/source
```

### 5. 编译 HBM

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

## 推理

先在 RDK S600 上下载代码：

```bash
cd /home/sunrise
git clone git@github.com:D-Robotics/Locateanything_PTQ.git
cd Locateanything_PTQ
```

### 1. 准备模型

以下两种方式任选其一。

#### 下载发布模型

在 RDK S600 上执行：

```bash
python3 -m pip install -U huggingface_hub
export HF_ENDPOINT="https://hf-mirror.com"

hf download xkj521999/LocateAnything-3B-S600 \
  --local-dir inference/models
```

#### 使用自行编译的模型

在编译主机的仓库根目录执行，将 HBM、Embedding 和词表传到 RDK S600：

```bash
export S600_HOST="sunrise@<S600_IP>"
export S600_REPO="/home/sunrise/Locateanything_PTQ"

ssh "$S600_HOST" "mkdir -p '$S600_REPO/inference/models/tokenizer'"

scp \
  compiler/outputs/chunk1024_cache4096_w8/build/vision/LocateAnything-3B_vision.hbm \
  compiler/outputs/chunk1024_cache4096_w8/build/language/LocateAnything-3B_language.hbm \
  compiler/outputs/chunk1024_cache4096_w8/build/language/LocateAnything-3B_embed_tokens.bin \
  "${S600_HOST}:${S600_REPO}/inference/models/"

scp compiler/models/LocateAnything-3B/{vocab.json,merges.txt,added_tokens.json} \
  "${S600_HOST}:${S600_REPO}/inference/models/tokenizer/"
```

运行时读取以下文件：

```text
inference/models/
├── LocateAnything-3B_vision.hbm
├── LocateAnything-3B_language.hbm
├── LocateAnything-3B_embed_tokens.bin
└── tokenizer/
    ├── vocab.json
    ├── merges.txt
    └── added_tokens.json
```

### 2. 编译推理程序

将仓库复制到 RDK S600，在仓库根目录执行：

```bash
cmake -S inference -B inference/build -DCMAKE_BUILD_TYPE=Release
cmake --build inference/build --parallel 2
```

### 3. 启动推理

```bash
./inference/build/console --config inference/config.yaml
```

启动后先加载图片或视频，再输入任务命令。

#### 目标检测

```text
[User] <<< /image inference/image/07_detection_multiclass.jpg
[User] <<< /detect person,bus,bicycle
```

<img src="assets/results/detection_multiclass.jpg" alt="目标检测" width="720">

#### GUI 定位

```text
[User] <<< /image inference/image/02_gui_rstudio.jpg
[User] <<< /gui_box Go to file/function; Environment tab; Files tab
```

<img src="assets/results/gui_rstudio.jpg" alt="GUI 定位" width="720">

#### 指代定位

```text
[User] <<< /image inference/image/03_referring_graduation.jpg
[User] <<< /ground person wearing a graduation cap; woman in a black dress; clock tower
```

<img src="assets/results/referring_graduation.jpg" alt="指代定位" width="520">

#### OCR

```text
[User] <<< /image inference/image/04_ocr_scrapbook.jpg
[User] <<< /text
```

<img src="assets/results/ocr_scrapbook.jpg" alt="OCR" width="720">

#### 指定文本定位

```text
[User] <<< /image inference/image/04_ocr_scrapbook.jpg
[User] <<< /ground_text LIVE love LAUGH; laugh giggle be silly; Yes Virginia
```

<img src="assets/results/ground_text_scrapbook.jpg" alt="指定文本定位" width="720">

#### 文档版面定位

```text
[User] <<< /image inference/image/05_layout_plot.jpg
[User] <<< /layout plot,text
```

<img src="assets/results/layout_plot.jpg" alt="文档版面" width="720">

#### 点定位

```text
[User] <<< /image inference/image/06_pointing_succulent.jpg
[User] <<< /point succulent
```

<img src="assets/results/point_succulent.jpg" alt="点定位" width="512">

#### 视频目标检测

```text
[User] <<< /video inference/image/person_video.avi
[User] <<< /detect person
```

图片结果保存在 `inference/outputs/<图片名>/annotated.jpg` 和
`prediction.json`。视频结果保存在 `annotated.mp4`、`predictions.jsonl`
和 `summary.json`。同一输入重复推理时覆盖原结果。

## 性能

| 任务 | 输出 Token | Vision (ms) | Prefill (ms) | Decode (ms) | 总耗时 (ms) | Decode (Token/s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 目标检测 | 47 | 252.5 | 149.9 | 525.0 | 970.5 | 89.5 |
| GUI 定位 | 14 | 253.2 | 149.7 | 266.0 | 720.7 | 52.6 |
| 指代定位 | 14 | 246.0 | 152.3 | 164.5 | 603.6 | 85.1 |
| OCR | 66 | 245.5 | 152.4 | 665.3 | 1148.3 | 99.2 |
| 指定文本定位 | 15 | 253.0 | 150.2 | 166.6 | 653.5 | 90.0 |
| 文档版面 | 43 | 245.4 | 151.8 | 448.1 | 904.7 | 96.0 |
| 点定位 | 37 | 246.0 | 152.2 | 480.5 | 923.5 | 77.0 |

### 资源占用

| 任务 | Avg BPU (%) | CPU (%) | Console RSS (MiB) | DDR Read (GiB/s) | DDR Write (GiB/s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 目标检测 | 30.4 | 40.2 | 167.1 | 74.2 | 15.6 |
| GUI 定位 | 39.9 | 28.7 | 179.3 | 70.9 | 18.6 |
| 指代定位 | 34.5 | 26.6 | 175.6 | 70.8 | 23.6 |
| OCR | 41.3 | 49.0 | 185.3 | 65.9 | 12.4 |
| 指定文本定位 | 29.5 | 34.7 | 182.4 | 65.3 | 20.1 |
| 文档版面 | 39.6 | 39.4 | 182.6 | 69.1 | 16.0 |
| 点定位 | 43.5 | 34.7 | 180.4 | 76.6 | 15.1 |
