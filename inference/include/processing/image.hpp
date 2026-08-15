#pragma once

#include <cstdint>
#include <vector>

#include <opencv2/core/mat.hpp>

#include "model_profile.hpp"

namespace locateanything {

/** Geometric transform needed to map model coordinates to source pixels. */
struct ImageTransform {
  int source_width = 0;
  int source_height = 0;
  int canvas_width = 0;
  int canvas_height = 0;
  int resized_width = 0;
  int resized_height = 0;
  int pad_left = 0;
  int pad_top = 0;
  float scale_x = 1.0f;
  float scale_y = 1.0f;
};

/** Prepared Vision input and its source-to-model transform. */
struct PreparedImage {
  std::vector<uint16_t> patches;
  ImageTransform transform;
};

class ImagePreprocessor {
 public:
  explicit ImagePreprocessor(VisionProfile profile = {});
  /**
   * @brief Resize, pad, normalize, and tile a BGR image for Vision.
   * @param bgr Non-empty three-channel source image.
   * @return FP16 Vision patches and source-coordinate transform.
   */
  PreparedImage Prepare(const cv::Mat& bgr) const;

 private:
  VisionProfile profile_;
};

}  // namespace locateanything
