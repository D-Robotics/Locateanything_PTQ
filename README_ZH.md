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

## 算法简介

[LocateAnything](https://github.com/NVlabs/Eagle/tree/main/Embodied) 通过文本指令完成开放语义视觉检测与定位，包括开放词汇目标检测、指代定位、GUI 定位、OCR、文本定位、文档版面定位和点定位。PBD（Parallel Box Decoding）以并行方式生成边界框坐标。

### 任务类型

| 类型 | 任务说明 | 输出 |
| --- | --- | --- |
| 开放词汇目标检测 | 根据用户给出的类别名称检测目标，不受预设类别表限制 | 目标类别及边界框 |
| 指代定位 | 根据目标的外观、属性、位置或关系等自然语言描述定位目标 | 目标边界框 |
| GUI 定位 | 根据文字描述定位软件界面中的按钮、图标、输入框等控件 | 控件点坐标或边界框 |
| OCR | 识别图像中的文字内容及其所在位置 | 识别文字及文字边界框 |
| 文本定位 | 根据用户给出的文字内容定位其在图像中的位置 | 指定文字及边界框 |
| 文档版面定位 | 定位文档中的标题、正文、表格、图片等结构区域 | 版面元素类别及边界框 |
| 点定位 | 根据自然语言描述定位普通视觉场景中的目标位置 | 目标点坐标 |

LocateAnything 的检测与定位任务使用相对固定的 Prompt 格式。我们按照训练数据采用的提示词格式内置了各类任务模板，使用时只需通过对应命令输入查询目标（Query）。`<query>` 表示查询目标，多个 Query 使用英文逗号分隔；`<type>` 表示版面元素类型。

| 命令 | 使用示例 | 说明 |
| --- | --- | --- |
| `/detect <query>[,<query>...]` | `/detect person,bus,bicycle` | 检测 person、bus 和 bicycle 类别的全部目标 |
| `/ground <query>[,<query>...]` | `/ground person wearing a graduation cap,woman in a black dress,clock tower` | 分别定位符合三个自然语言描述的全部目标 |
| `/ground_single <query>[,<query>...]` | `/ground_single person wearing a graduation cap` | 定位一个符合自然语言描述的目标 |
| `/gui <query>[,<query>...]` | `/gui Go to file/function` | 定位指定界面控件并返回操作点 |
| `/gui_box <query>[,<query>...]` | `/gui_box Go to file/function,Environment tab,Files tab` | 分别定位三个界面控件并返回边界框 |
| `/text` | `/text` | 识别图像中的全部文字及其位置 |
| `/ground_text <query>[,<query>...]` | `/ground_text LIVE love LAUGH,laugh giggle be silly,Yes Virginia` | 分别定位三段指定文字 |
| `/layout <type>[,<type>...]` | `/layout plot,text` | 定位文档中的图表和文本区域 |
| `/point <query>[,<query>...]` | `/point succulent,the succulent in the center` | 分别返回两处目标的点坐标 |

模型仓库：[D-Robotics/LocateAnything-3B-BPU](https://huggingface.co/D-Robotics/LocateAnything-3B-BPU)

## 模型与量化

<p align="center">
  <img src="assets/LocateAnything_pipeline.png" alt="LocateAnything 推理流程" width="100%">
</p>

| 项目 | 配置 |
| --- | --- |
| 模型 | LocateAnything-3B |
| Vision | MoonViT，27 个 Block，`672 x 672` |
| Language | Qwen2.5 Decoder，36 层，Hidden Size 2048 |
| 线性层 | W8A8：有符号 W8 权重，激活动态量化为 INT8 |
| Attention QK / WV | 动态 INT8 |
| KV Cache | INT8 |
| 校准 | 1,200 张图片 |
| Prefill 长度 | 1024 Token |
| KV Cache 容量 | 每个 Query 4096 Token |
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
git clone https://github.com/D-Robotics/Locateanything_PTQ.git
cd Locateanything_PTQ
```

### 2. 创建 Conda 环境并安装 OELLM SDK

```bash
conda create -n locateanything_ptq python=3.10 -y
conda activate locateanything_ptq
python -m pip install -U pip

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
MODEL_DIR="compiler/models/LocateAnything-3B"
MODEL_URL="https://hf-mirror.com/nvidia/LocateAnything-3B/resolve/main"
mkdir -p "$MODEL_DIR"

for file in \
  config.json generation_config.json preprocessor_config.json \
  processor_config.json tokenizer_config.json special_tokens_map.json \
  added_tokens.json chat_template.json vocab.json merges.txt \
  model.safetensors.index.json \
  model-00001-of-00002.safetensors model-00002-of-00002.safetensors \
  configuration_locateanything.py configuration_qwen2.py \
  modeling_locateanything.py modeling_qwen2.py modeling_vit.py \
  processing_locateanything.py image_processing_locateanything.py \
  generate_utils.py mask_magi_utils.py mask_sdpa_utils.py; do
  wget -c -P "$MODEL_DIR" "$MODEL_URL/$file"
done
```

### 4. 下载校准数据

```bash
mkdir -p compiler/datasets/calibration/locateanything/source
wget -c -P compiler/datasets/calibration/locateanything \
  https://hf-mirror.com/datasets/xkj521999/OE_LA_Calibration_data/resolve/main/source.zip

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

在 RDK S600 上下载代码：

```bash
git clone https://github.com/D-Robotics/Locateanything_PTQ.git
cd Locateanything_PTQ
```

### 1. 准备模型

以下两种方式任选其一。

#### 下载发布模型

```bash
MODEL_DIR="inference/models"
MODEL_URL="https://hf-mirror.com/D-Robotics/LocateAnything-3B-BPU/resolve/main"
mkdir -p "$MODEL_DIR/tokenizer"

wget -c -P "$MODEL_DIR" "$MODEL_URL/LocateAnything-3B_vision.hbm"
wget -c -P "$MODEL_DIR" "$MODEL_URL/LocateAnything-3B_language.hbm"
wget -c -P "$MODEL_DIR" "$MODEL_URL/LocateAnything-3B_embed_tokens.bin"
wget -c -P "$MODEL_DIR/tokenizer" "$MODEL_URL/tokenizer/vocab.json"
wget -c -P "$MODEL_DIR/tokenizer" "$MODEL_URL/tokenizer/merges.txt"
wget -c -P "$MODEL_DIR/tokenizer" "$MODEL_URL/tokenizer/added_tokens.json"
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

```bash
cmake -S inference -B inference/build -DCMAKE_BUILD_TYPE=Release
cmake --build inference/build --parallel 2
```

### 3. 基础功能：目标检测

#### 启动 Console

```bash
./inference/build/console --config inference/config.yaml
```

终端输出：

```text
[UCP]: UCP version = 3.12.3
[DNN]: 3.12.3_(4.5.4 HBRT)
Loading Vision HBM...
Loading Language HBM...
HBM loaded  [============================] 16.7 s
Ready  S600/Nash-P  |  hybrid  |  max tokens 4096
Tasks
  /detect cat,dog              目标检测
  /ground <query>[,<query>...] 指代表达，多查询
  /ground_single <query>[,...] 指代表达，单目标查询
  /gui <query>[,<query>...]    GUI 点定位
  /gui_box <query>[,<query>...] GUI 框定位
  /text                        文本 OCR
  /ground_text <query>[,...]   指定文本定位
  /layout title,table,figure   文档版面分析
  /point <query>[,<query>...]  通用点定位
Session
  /image <image_path>          加载图片
  /video <video_path>          加载视频并处理全部帧
  regen                        重跑上次请求
  reset                        清除当前媒体
  exit                         退出程序
```

加载图片：

```text
/image inference/image/07_detection_multiclass.jpg
```

图片加载结果：

```text
Image loaded  inference/image/07_detection_multiclass.jpg
```

输入检测指令：

```text
/detect person,bus,bicycle
```

推理结果：

```text
[Assistant] >>> /detect person,bus,bicycle
Performance
  Vision   254.7 ms
  Prefill  151.6 ms  620 tokens
  Decode   526.3 ms  47 tokens  89.3 tokens/s
  Host     41.4 ms
  Total    978.5 ms
Result
  Labels bicycle, bus, person  |  Boxes 6  |  Points 0  |  Stop im_end
Saved
  Image  inference/outputs/07_detection_multiclass/annotated.jpg
  JSON   inference/outputs/07_detection_multiclass/prediction.json
```

<img src="assets/results/detection_multiclass.jpg" alt="目标检测" width="720">

### 4. 进阶功能

多个查询使用逗号分隔。同一图像或视频帧只执行一次 Vision，各项 Language 推理完成后合并结果。

#### GUI 定位

加载图片：

```text
/image inference/image/02_gui_rstudio.jpg
```

图片加载结果：

```text
Image loaded  inference/image/02_gui_rstudio.jpg
```

输入定位指令：

```text
/gui_box Go to file/function,Environment tab,Files tab
```

推理结果：

```text
[Assistant] >>> /gui_box Go to file/function,Environment tab,Files tab
Performance
  Vision   252.9 ms
  Prefill  463.7 ms  1848 tokens
  Decode   519.8 ms  36 tokens  69.3 tokens/s
  Host     29.4 ms
  Total    1342.8 ms
Result
  Labels Environment tab, Files tab, Go to file/function  |  Boxes 3  |  Points 0  |  Stop im_end
```

<img src="assets/results/gui_rstudio.jpg" alt="GUI 定位" width="720">

#### 指代定位

加载图片：

```text
/image inference/image/03_referring_graduation.jpg
```

图片加载结果：

```text
Image loaded  inference/image/03_referring_graduation.jpg
```

输入定位指令：

```text
/ground person wearing a graduation cap,woman in a black dress,clock tower
```

推理结果：

```text
[Assistant] >>> /ground person wearing a graduation cap,woman in a black dress,clock tower
Performance
  Vision   250.4 ms
  Prefill  462.5 ms  1854 tokens
  Decode   461.2 ms  39 tokens  84.6 tokens/s
  Host     29.9 ms
  Total    1268.8 ms
Result
  Labels clock tower, person wearing a graduation cap, woman in a black dress  |  Boxes 3  |  Points 0  |  Stop im_end
```

<img src="assets/results/referring_graduation.jpg" alt="指代定位" width="520">

#### OCR

加载图片：

```text
/image inference/image/04_ocr_scrapbook.jpg
```

图片加载结果：

```text
Image loaded  inference/image/04_ocr_scrapbook.jpg
```

输入 OCR 指令：

```text
/text
```

推理结果：

```text
[Assistant] >>> /text
Performance
  Vision   246.2 ms
  Prefill  155.7 ms  610 tokens
  Decode   666.4 ms  66 tokens  99.0 tokens/s
  Host     63.0 ms
  Total    1153.9 ms
Result
  Labels LIVE love LAUGH, Yes, Virginiaina, [to-day]], laugh giggle be silly
  Boxes 5  |  Points 0  |  Stop im_end
```

<img src="assets/results/ocr_scrapbook.jpg" alt="OCR" width="720">

#### 指定文本定位

加载图片：

```text
/image inference/image/04_ocr_scrapbook.jpg
```

图片加载结果：

```text
Image loaded  inference/image/04_ocr_scrapbook.jpg
```

输入定位指令：

```text
/ground_text LIVE love LAUGH,laugh giggle be silly,Yes Virginia
```

推理结果：

```text
[Assistant] >>> /ground_text LIVE love LAUGH,laugh giggle be silly,Yes Virginia
Performance
  Vision   246.0 ms
  Prefill  471.6 ms  1838 tokens
  Decode   459.4 ms  43 tokens  93.6 tokens/s
  Host     30.4 ms
  Total    1311.1 ms
Result
  Labels LIVE love LAUGH., Yes Virginia., laugh giggle be silly.  |  Boxes 3  |  Points 0  |  Stop im_end
```

<img src="assets/results/ground_text_scrapbook.jpg" alt="指定文本定位" width="720">

#### 文档版面定位

加载图片：

```text
/image inference/image/05_layout_plot.jpg
```

图片加载结果：

```text
Image loaded  inference/image/05_layout_plot.jpg
```

输入定位指令：

```text
/layout plot,text
```

推理结果：

```text
[Assistant] >>> /layout plot,text
Performance
  Vision   245.6 ms
  Prefill  155.0 ms  620 tokens
  Decode   448.1 ms  43 tokens  96.0 tokens/s
  Host     37.2 ms
  Total    908.8 ms
Result
  Labels plot, text  |  Boxes 6  |  Points 0  |  Stop im_end
```

<img src="assets/results/layout_plot.jpg" alt="文档版面" width="720">

#### 点定位

加载图片：

```text
/image inference/image/06_pointing_succulent.jpg
```

图片加载结果：

```text
Image loaded  inference/image/06_pointing_succulent.jpg
```

输入定位指令：

```text
/point succulent,the succulent in the center
```

推理结果：

```text
[Assistant] >>> /point succulent,the succulent in the center
Performance
  Vision   245.9 ms
  Prefill  310.5 ms  1220 tokens
  Decode   645.4 ms  50 tokens  77.5 tokens/s
  Host     47.4 ms
  Total    1272.7 ms
Result
  Labels succulent, the succulent in the center  |  Boxes 0  |  Points 9  |  Stop im_end
```

<img src="assets/results/point_succulent.jpg" alt="点定位" width="512">

### 5. 图片与视频输出

图片结果保存在 `inference/outputs/<图片名>/annotated.jpg` 和 `prediction.json`。

视频通过 `/video` 加载，任务命令与图片一致：

```text
/video inference/image/person_video.avi
/detect person
```

视频结果保存在：

```text
inference/outputs/person_video/
├── annotated.mp4
├── predictions.jsonl
└── summary.json
```

## 性能

下表为各任务单 Query 测试。多 Query 共用一次 Vision，Prefill、Decode、输出 Token 和总耗时按各 Query 累计。

| 任务 | 输出 Token | Vision (ms) | Prefill (ms) | Decode (ms) | 总耗时 (ms) | Decode (Token/s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 目标检测 | 47 | 254.7 | 151.6 | 526.3 | 978.5 | 89.3 |
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
