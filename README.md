English | [简体中文](./README_ZH.md)

# Locateanything_PTQ

![PTQ](https://img.shields.io/badge/PTQ-LocateAnything--3B-4C8C4A)
![W8](https://img.shields.io/badge/weights-W8-E67E22)
![RDK S600](https://img.shields.io/badge/target-RDK%20S600-2F6BFF)
![C++17](https://img.shields.io/badge/Console-C%2B%2B17-00599C?logo=cplusplus)

<p align="center">
  <img src="assets/LocateAnything.jpg" alt="LocateAnything" width="100%">
</p>

`Locateanything_PTQ` provides the host-side calibration, post-training
quantization, and BC/HBO/HBM build pipeline for LocateAnything-3B. It also
contains an independent C++ Console for validating the generated HBM files.
The repository does not depend on ROS or TROS. Runtime integration is
maintained in [hobot_locateanything](https://github.com/LiuAnclouds/hobot_locateanything).

The source is released under CC BY-NC 4.0. Commercial use is not granted.

## Supported tasks

| Console command | Task |
| --- | --- |
| `/detect person,car` | Open-vocabulary detection |
| `/ground <phrase>` | Referring grounding |
| `/ground_single <phrase>` | Single-instance grounding |
| `/gui <element>` | GUI point grounding |
| `/gui_box <element>` | GUI box grounding |
| `/text` | OCR with text boxes |
| `/ground_text <text>` | Text grounding |
| `/layout title,table,figure` | Document layout grounding |
| `/point <target>` | Point localization |

## Model and quantization

<p align="center">
  <img src="assets/LocateAnything_pipeline.png" alt="LocateAnything pipeline" width="100%">
</p>

The model path is `image + prompt -> MoonViT -> Qwen2.5 decoder -> structured result parsing`.

| Item | Configuration |
| --- | --- |
| Model | LocateAnything-3B |
| Vision | MoonViT, 27 blocks, `672 x 672`, W8 weights |
| Language | Qwen2.5 decoder, 36 layers, hidden size 2048, W8 weights |
| LM Head | W8, vocabulary size 152681 |
| Activations | Dynamic quantization |
| Calibration | 1,200 selected images |
| Language graphs | 13 fixed graphs |
| Prefill / KV cache | 1024 / 4096 tokens |
| Decode | PBD q=6, AR q=1, host sampling |
| Target | Nash-P, four BPU cores, L2 `6:6:6:6` |

## Environment

| Item | Requirement |
| --- | --- |
| Build host | Linux x86_64, CUDA and PyTorch |
| SDK | D-Robotics OELLM/HBDK environment |
| Python | Python 3 with the packages in `compiler/requirements-host.txt` |
| Console | C++17, CMake, OpenCV, yaml-cpp |
| Deploy target | D-Robotics RDK S600, AArch64 |

## Usage

### 1. Prepare the source model

Place the official LocateAnything-3B checkpoint and its
`locateanything_worker.py` implementation at the path used by
`compiler/config/quantization.yaml`:

```text
compiler/models/LocateAnything-3B/
```

The path is relative to the repository and can be changed in the YAML file.

### 2. Download calibration data

The calibration repository contains `source.zip`. Download and extract it so
that the compiler can read `compiler/datasets/calibration/locateanything/source`:

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

The dataset and generated tensors are local inputs; they are not committed to
this repository.

### 3. Run PTQ and build

Activate the external OELLM/HBDK environment first, then install the host-side
Python requirements:

```bash
python -m pip install -r compiler/requirements-host.txt
```

Run the stages in order:

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

`--target bc` stops after BC export. `--target hbm` continues through HBO and
HBM linking. A normal build uses the output directory in the configuration;
use `--resume` only when continuing that same build directory.

The final artifacts are written under:

```text
compiler/outputs/chunk1024_cache4096_w8/
├── calibration/
├── build/vision/LocateAnything-3B_vision.hbm
├── build/language/LocateAnything-3B_language.hbm
├── build/language/LocateAnything-3B_embed_tokens.bin
└── logs/
```

### 4. Standalone C++ Console

The Console has no ROS or ament dependency. Copy the generated HBM files, the
embedding binary, and tokenizer assets into the paths configured in
`inference/config.yaml`, then build from the repository root:

```bash
cmake -S inference -B inference/build -DCMAKE_BUILD_TYPE=Release
cmake --build inference/build --parallel 2
./inference/build/console --config inference/config.yaml
```

Example session:

```text
[User] <<< /image <image-path>
[User] <<< /detect person,car,bicycle
```

For video, use `/video <path>` followed by a task command. Results are written
to `inference/outputs/<input-name>/`:

```text
annotated.jpg                  # image input
prediction.json
annotated.mp4                  # video input
predictions.jsonl
summary.json
```

Repeated inference for the same input replaces the files in that directory.

## Results

### Examples

Object detection, `/detect person,bus,bicycle`

<img src="assets/results/detection_multiclass.jpg" alt="Object detection" width="720">

GUI grounding, `/gui_box Go to file/function; Environment tab; Files tab`

<img src="assets/results/gui_rstudio.jpg" alt="GUI grounding" width="720">

Referring grounding, `/ground person wearing a graduation cap; woman in a black dress; clock tower`

<img src="assets/results/referring_graduation.jpg" alt="Referring grounding" width="520">

OCR, `/text`

<img src="assets/results/ocr_scrapbook.jpg" alt="OCR" width="720">

Text grounding, `/ground_text LIVE love LAUGH; laugh giggle be silly; Yes Virginia`

<img src="assets/results/ground_text_scrapbook.jpg" alt="Text grounding" width="720">

Document layout, `/layout plot,text`

<img src="assets/results/layout_plot.jpg" alt="Document layout" width="720">

Point localization, `/point succulent`

<img src="assets/results/point_succulent.jpg" alt="Point localization" width="512">

### Performance

| Task | Output tokens | Vision (ms) | Prefill (ms) | Decode (ms) | Total (ms) | Decode (tokens/s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Object detection | 47 | 252.5 | 149.9 | 525.0 | 970.5 | 89.5 |
| GUI grounding | 14 | 253.2 | 149.7 | 266.0 | 720.7 | 52.6 |
| Referring grounding | 14 | 246.0 | 152.3 | 164.5 | 603.6 | 85.1 |
| OCR | 66 | 245.5 | 152.4 | 665.3 | 1148.3 | 99.2 |
| Text grounding | 15 | 253.0 | 150.2 | 166.6 | 653.5 | 90.0 |
| Document layout | 43 | 245.4 | 151.8 | 448.1 | 904.7 | 96.0 |
| Point localization | 37 | 246.0 | 152.2 | 480.5 | 923.5 | 77.0 |
