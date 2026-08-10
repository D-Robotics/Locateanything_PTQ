# Locateanything_PTQ

This repository owns LocateAnything-3B calibration, post-training
quantization, and BC/HBO/HBM compilation. It also contains a standalone
non-ROS validation Console. TROS integration is maintained separately in
`hobot_locateanything`.

The source is released under CC BY-NC 4.0 and is not licensed for commercial
use. Third-party source notices are kept in `THIRD_PARTY_NOTICES`.

## Layout

```text
Locateanything_PTQ/
├── compiler/
│   ├── config/          # PTQ and HBM settings
│   ├── datasets/        # calibration source and generated inputs
│   ├── model/           # LocateAnything graph/model definitions
│   ├── models/          # user-provided Float checkpoint
│   ├── outputs/         # calibration, BC, HBO, HBM and logs
│   ├── pipeline/        # prepare, calibrate and build stages
│   ├── quantize.py      # public Python entry point
│   └── requirements-host.txt
├── inference/           # independent plain-CMake validation Console
│   ├── CMakeLists.txt
│   ├── config.yaml
│   ├── include/          # shared runtime and processing interfaces
│   ├── src/              # Console, InferenceSession and runtime
│   ├── models/           # user-provided HBM bundle and tokenizer
│   └── outputs/          # annotated media and JSON reports
├── LICENSE
└── README.md
```

Compiler outputs are project-local under `compiler/outputs/`; they are not
required to run the Console. The Console model path is configured separately
under `inference/config.yaml`, so users can replace the HBM bundle without
changing compiler paths.

## PTQ workflow

Install the host dependencies in the OELLM/HBDK environment, then use the
single Python entry point:

```bash
python -m pip install -r compiler/requirements-host.txt
python compiler/quantize.py prepare --config compiler/config/quantization.yaml
python compiler/quantize.py calibrate --config compiler/config/quantization.yaml --component all
python compiler/quantize.py build --config compiler/config/quantization.yaml \
  --component all --target hbm
```

Use `--resume` only to reuse an existing, explicitly selected output directory;
a normal build must point at a new final output directory. The dry-run and
help forms are safe for checking a configuration:

```bash
python compiler/quantize.py --help
python compiler/quantize.py build --config compiler/config/quantization.yaml \
  --component all --target hbm --dry-run
```

## Standalone Console

This Console is C++ and has no ROS/TROS or ament dependency. Build it inside
the installed OELLM/S600 runtime environment:

```bash
cmake -S inference -B inference/build -DCMAKE_BUILD_TYPE=Release
cmake --build inference/build -j2
./inference/build/console --config inference/config.yaml
```

Use `/image path`, `/video path`, then a task such as `/detect person,car`.
The Console calls the same in-process `InferenceSession` state machine used by
the TROS repository, including the PBD/AR/KV ordering. It writes annotated
media and JSON reports to the configured `inference/outputs/` directory.
