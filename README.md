English | [简体中文](./README_ZH.md)

# Locateanything_PTQ

![PTQ](https://img.shields.io/badge/PTQ-LocateAnything--3B-4C8C4A)
![W8](https://img.shields.io/badge/weights-W8-E67E22)
![RDK S600](https://img.shields.io/badge/target-RDK%20S600-2F6BFF)
![C++17](https://img.shields.io/badge/inference-C%2B%2B17-00599C?logo=cplusplus)
![License](https://img.shields.io/badge/license-Apache--2.0-lightgrey)

<p align="center">
  <img src="assets/LocateAnything.jpg" alt="LocateAnything" width="100%">
</p>

`Locateanything_PTQ` converts LocateAnything-3B into W8 HBM models for the
D-Robotics RDK S600. It includes calibration, PTQ, BC/HBO/HBM compilation, and
a C++ inference executable.

## Model overview

[LocateAnything](https://github.com/NVlabs/Eagle/tree/main/Embodied) performs open-semantic visual detection and grounding from text instructions. Its tasks include open-vocabulary object detection, referring expression grounding, GUI grounding, OCR, text grounding, document layout grounding, and point localization. PBD (Parallel Box Decoding) generates bounding-box coordinates in parallel.

### Task categories

| Type | Description | Output |
| --- | --- | --- |
| Open-vocabulary object detection | Detects objects by user-provided category names without a fixed category list | Object categories and bounding boxes |
| Referring expression grounding | Locates objects from descriptions of appearance, attributes, position, or relationships | Object bounding boxes |
| GUI grounding | Locates buttons, icons, input fields, and other interface controls | Control points or bounding boxes |
| OCR | Recognizes text and its position in an image | Recognized text and text bounding boxes |
| Text grounding | Locates user-specified text in an image | Specified text and bounding boxes |
| Document layout grounding | Locates titles, body text, tables, figures, and other document regions | Layout categories and bounding boxes |
| Point localization | Locates objects in general visual scenes from natural-language descriptions | Object point coordinates |

LocateAnything uses relatively fixed Prompt formats for detection and grounding. We provide built-in task templates based on its training data. Enter only the query through the corresponding command. `<query>` denotes a query target; separate multiple queries with commas. `<type>` denotes a document layout element type.

| Command | Example | Description |
| --- | --- | --- |
| `/detect <query>[,<query>...]` | `/detect person,bus,bicycle` | Detects all person, bus, and bicycle instances |
| `/ground <query>[,<query>...]` | `/ground person wearing a graduation cap,woman in a black dress,clock tower` | Locates all objects matching the three descriptions |
| `/ground_single <query>[,<query>...]` | `/ground_single person wearing a graduation cap` | Locates one object matching the description |
| `/gui <query>[,<query>...]` | `/gui Go to file/function` | Locates a GUI control and returns an interaction point |
| `/gui_box <query>[,<query>...]` | `/gui_box Go to file/function,Environment tab,Files tab` | Locates the three GUI controls and returns their bounding boxes |
| `/text` | `/text` | Recognizes all text and its position in the image |
| `/ground_text <query>[,<query>...]` | `/ground_text LIVE love LAUGH,laugh giggle be silly,Yes Virginia` | Locates the three specified text strings |
| `/layout <type>[,<type>...]` | `/layout plot,text` | Locates plot and text regions in a document |
| `/point <query>[,<query>...]` | `/point succulent,the succulent in the center` | Returns point coordinates for the two queries |

Model: [D-Robotics/LocateAnything-3B-BPU](https://huggingface.co/D-Robotics/LocateAnything-3B-BPU)

## Model and quantization

<p align="center">
  <img src="assets/LocateAnything_pipeline.png" alt="LocateAnything pipeline" width="100%">
</p>

| Item | Configuration |
| --- | --- |
| Model | LocateAnything-3B |
| Vision | MoonViT, 27 blocks, `672 x 672` |
| Language | Qwen2.5 decoder, 36 layers, hidden size 2048 |
| Linear layers | W8A8: signed W8 weights and dynamically quantized INT8 activations |
| Attention QK / WV | Dynamic INT8 |
| KV cache | INT8 |
| Calibration | 1,200 images |
| Prefill length | 1024 tokens |
| KV cache capacity | 4096 tokens per query |
| Decode | PBD q=6, AR q=1, host sampling |
| Target | Nash-P, four BPU cores, L2 `6:6:6:6` |

## Environment

| Item | Requirement |
| --- | --- |
| Build host | Linux x86_64, NVIDIA GPU, CUDA |
| SDK | D-Robotics LLM S600 SDK 1.0.5 |
| Python | Python 3.10, PyTorch |
| Target | RDK S600, AArch64 |

## Build

### 1. Clone the repository

```bash
git clone https://github.com/D-Robotics/Locateanything_PTQ.git
cd Locateanything_PTQ
```

### 2. Create a Conda environment and install the OELLM SDK

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

### 3. Download LocateAnything-3B

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

### 4. Download calibration data

```bash
mkdir -p compiler/datasets/calibration/locateanything/source
wget -c -P compiler/datasets/calibration/locateanything \
  https://hf-mirror.com/datasets/xkj521999/OE_LA_Calibration_data/resolve/main/source.zip

unzip -qo \
  compiler/datasets/calibration/locateanything/source.zip \
  -d compiler/datasets/calibration/locateanything/source
```

### 5. Build HBM

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

## Inference

Clone the repository on the RDK S600:

```bash
git clone https://github.com/D-Robotics/Locateanything_PTQ.git
cd Locateanything_PTQ
```

### 1. Prepare the model

Choose either method below.

#### Download the release model

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

#### Use a locally compiled model

Run from the repository root on the build host to transfer the HBM files,
embedding table, and tokenizer to the RDK S600:

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

The runtime reads these files:

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

### 2. Build the inference executable

```bash
cmake -S inference -B inference/build -DCMAKE_BUILD_TYPE=Release
cmake --build inference/build --parallel 2
```

### 3. Basic feature: object detection

#### Start the Console

```bash
./inference/build/console --config inference/config.yaml
```

Console output:

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

Load an image:

```text
/image inference/image/07_detection_multiclass.jpg
```

Image loading output:

```text
Image loaded  inference/image/07_detection_multiclass.jpg
```

Enter a detection command:

```text
/detect person,bus,bicycle
```

Inference output:

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

<img src="assets/results/detection_multiclass.jpg" alt="Object detection" width="720">

### 4. Advanced tasks

Separate multiple queries with commas. Vision runs once per image or video frame. Language runs once per query, and the predictions are merged.

#### GUI grounding

Load an image:

```text
/image inference/image/02_gui_rstudio.jpg
```

Image loading output:

```text
Image loaded  inference/image/02_gui_rstudio.jpg
```

Enter a grounding command:

```text
/gui_box Go to file/function,Environment tab,Files tab
```

Inference output:

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

<img src="assets/results/gui_rstudio.jpg" alt="GUI grounding" width="720">

#### Referring grounding

Load an image:

```text
/image inference/image/03_referring_graduation.jpg
```

Image loading output:

```text
Image loaded  inference/image/03_referring_graduation.jpg
```

Enter a grounding command:

```text
/ground person wearing a graduation cap,woman in a black dress,clock tower
```

Inference output:

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

<img src="assets/results/referring_graduation.jpg" alt="Referring grounding" width="520">

#### OCR

Load an image:

```text
/image inference/image/04_ocr_scrapbook.jpg
```

Image loading output:

```text
Image loaded  inference/image/04_ocr_scrapbook.jpg
```

Enter the OCR command:

```text
/text
```

Inference output:

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

#### Text grounding

Load an image:

```text
/image inference/image/04_ocr_scrapbook.jpg
```

Image loading output:

```text
Image loaded  inference/image/04_ocr_scrapbook.jpg
```

Enter a grounding command:

```text
/ground_text LIVE love LAUGH,laugh giggle be silly,Yes Virginia
```

Inference output:

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

<img src="assets/results/ground_text_scrapbook.jpg" alt="Text grounding" width="720">

#### Document layout grounding

Load an image:

```text
/image inference/image/05_layout_plot.jpg
```

Image loading output:

```text
Image loaded  inference/image/05_layout_plot.jpg
```

Enter a layout command:

```text
/layout plot,text
```

Inference output:

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

<img src="assets/results/layout_plot.jpg" alt="Document layout" width="720">

#### Point localization

Load an image:

```text
/image inference/image/06_pointing_succulent.jpg
```

Image loading output:

```text
Image loaded  inference/image/06_pointing_succulent.jpg
```

Enter a point command:

```text
/point succulent,the succulent in the center
```

Inference output:

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

<img src="assets/results/point_succulent.jpg" alt="Point localization" width="512">

### 5. Image and video outputs

Image results are saved as `inference/outputs/<image-name>/annotated.jpg` and `prediction.json`.

Load a video with `/video`; task commands are the same as for images:

```text
/video inference/image/person_video.avi
/detect person
```

Video results are saved under:

```text
inference/outputs/person_video/
├── annotated.mp4
├── predictions.jsonl
└── summary.json
```

## Performance

The table reports one query per task. Multiple queries share one Vision run; Prefill, Decode, output tokens, and total latency are accumulated across queries.

| Task | Output tokens | Vision (ms) | Prefill (ms) | Decode (ms) | Total (ms) | Decode (tokens/s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Object detection | 47 | 254.7 | 151.6 | 526.3 | 978.5 | 89.3 |
| GUI grounding | 14 | 253.2 | 149.7 | 266.0 | 720.7 | 52.6 |
| Referring grounding | 14 | 246.0 | 152.3 | 164.5 | 603.6 | 85.1 |
| OCR | 66 | 245.5 | 152.4 | 665.3 | 1148.3 | 99.2 |
| Text grounding | 15 | 253.0 | 150.2 | 166.6 | 653.5 | 90.0 |
| Document layout | 43 | 245.4 | 151.8 | 448.1 | 904.7 | 96.0 |
| Point localization | 37 | 246.0 | 152.2 | 480.5 | 923.5 | 77.0 |

### Resource Usage

| Task | Avg BPU (%) | CPU (%) | Console RSS (MiB) | DDR Read (GiB/s) | DDR Write (GiB/s) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Object detection | 30.4 | 40.2 | 167.1 | 74.2 | 15.6 |
| GUI grounding | 39.9 | 28.7 | 179.3 | 70.9 | 18.6 |
| Referring grounding | 34.5 | 26.6 | 175.6 | 70.8 | 23.6 |
| OCR | 41.3 | 49.0 | 185.3 | 65.9 | 12.4 |
| Text grounding | 29.5 | 34.7 | 182.4 | 65.3 | 20.1 |
| Document layout | 39.6 | 39.4 | 182.6 | 69.1 | 16.0 |
| Point localization | 43.5 | 34.7 | 180.4 | 76.6 | 15.1 |
