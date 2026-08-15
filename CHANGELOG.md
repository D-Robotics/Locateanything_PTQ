# Changelog for Locateanything_PTQ

## Unreleased

- Aligned the standalone Console output and saved artifacts with `hobot_locateanything`.
- Added comma-separated multi-query inference with one shared Vision pass.
- Aligned standalone CMake lookup paths with the RDK S600 runtime layout.
- Updated model and calibration downloads to use direct `wget` URLs.

## 0.1.0 (2026-08-12)

- Added LocateAnything-3B calibration and W8 post-training quantization.
- Added BC, HBO, and HBM compilation for RDK S600.
- Added standalone C++ inference for local images and videos.
