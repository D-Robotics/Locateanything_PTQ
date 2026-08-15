"""LocateAnything-3B architecture constants and derived compiler profiles."""

from __future__ import annotations

from typing import Any, Mapping

IMAGE_WIDTH = 672
IMAGE_HEIGHT = 672
RESIZE_MODE = "letterbox"
LETTERBOX_FILL = 128
PATCH_SIZE = 14
SPATIAL_MERGE = 2
PATCH_COUNT = 2304
VISUAL_TOKEN_COUNT = 576
HIDDEN_SIZE = 2048
VOCAB_SIZE = 152681
IMAGE_TOKEN_ID = 151665

PBD_QUERY_LEN = 6
AR_QUERY_LEN = 1

LANGUAGE_LAYER_COUNT = 36
LANGUAGE_KV_HEAD_COUNT = 2
LANGUAGE_HEAD_DIM = 128
LANGUAGE_CACHE_TENSOR_COUNT = LANGUAGE_LAYER_COUNT * 2
LANGUAGE_INPUT_COUNT = 3 + LANGUAGE_CACHE_TENSOR_COUNT
LANGUAGE_OUTPUT_COUNT = 1 + LANGUAGE_CACHE_TENSOR_COUNT


def derive_vision_profile(
    image_width: int,
    image_height: int,
    *,
    resize_mode: str = RESIZE_MODE,
    letterbox_fill: int = LETTERBOX_FILL,
    patch_size: int = PATCH_SIZE,
    spatial_merge: int = SPATIAL_MERGE,
    hidden_size: int = HIDDEN_SIZE,
    channels: int = 3,
) -> dict[str, Any]:
    """Derive static MoonViT tensor shapes from one configurable canvas."""

    integer_fields = {
        "image_width": image_width,
        "image_height": image_height,
        "patch_size": patch_size,
        "spatial_merge": spatial_merge,
        "hidden_size": hidden_size,
        "channels": channels,
    }
    invalid = {
        name: value
        for name, value in integer_fields.items()
        if type(value) is not int or value <= 0
    }
    if invalid:
        raise ValueError(f"Vision profile values must be positive integers: {invalid}")
    if resize_mode not in {"letterbox", "stretch"}:
        raise ValueError("resize_mode must be letterbox or stretch")
    if type(letterbox_fill) is not int or not 0 <= letterbox_fill <= 255:
        raise ValueError("letterbox_fill must be an integer within [0, 255]")

    profile_multiple = patch_size * spatial_merge
    if image_width % profile_multiple or image_height % profile_multiple:
        raise ValueError(
            "image dimensions must be divisible by patch_size * spatial_merge "
            f"({profile_multiple})"
        )

    grid_width = image_width // patch_size
    grid_height = image_height // patch_size
    patch_count = grid_width * grid_height
    merge_area = spatial_merge * spatial_merge
    if patch_count % merge_area:
        raise ValueError("patch count must be divisible by the spatial merge area")
    visual_token_count = patch_count // merge_area
    patch_flat_dim = channels * patch_size * patch_size
    return {
        "image_width": image_width,
        "image_height": image_height,
        "resize_mode": resize_mode,
        "letterbox_fill": letterbox_fill,
        "patch_size": patch_size,
        "merge_size": spatial_merge,
        "grid_hw": [grid_height, grid_width],
        "patch_count": patch_count,
        "vision_input_shape": [1, patch_count, patch_flat_dim],
        "visual_token_count": visual_token_count,
        "projected_visual_shape": [1, visual_token_count, hidden_size],
    }


def resolve_vision_scale_profile(
    manifest: Mapping[str, Any],
    image_width: int,
    image_height: int,
    *,
    resize_mode: str = RESIZE_MODE,
    letterbox_fill: int = LETTERBOX_FILL,
    vision_weight_bits: int = 8,
) -> dict[str, Any]:
    """Bind a Vision scale manifest to the requested preprocessing and graph ABI."""

    expected_vision = derive_vision_profile(
        image_width,
        image_height,
        resize_mode=resize_mode,
        letterbox_fill=letterbox_fill,
    )
    raw_profile = manifest.get("profile")
    manifest_profile = raw_profile if isinstance(raw_profile, Mapping) else {}
    vision_keys = set(expected_vision)
    present_keys = vision_keys & set(manifest_profile)
    if present_keys and present_keys != vision_keys:
        missing = sorted(vision_keys - present_keys)
        raise ValueError(f"scale manifest has an incomplete Vision profile: {missing}")
    if not present_keys and (
        image_width != IMAGE_WIDTH
        or image_height != IMAGE_HEIGHT
        or resize_mode != RESIZE_MODE
        or letterbox_fill != LETTERBOX_FILL
    ):
        raise ValueError(
            "legacy scale manifests without a Vision profile may only be used "
            f"with {IMAGE_WIDTH}x{IMAGE_HEIGHT} {RESIZE_MODE} fill={LETTERBOX_FILL}"
        )
    expected_scale_profile = {"vision_weight_bits": vision_weight_bits}
    if present_keys:
        expected_scale_profile.update(expected_vision)
    return expected_scale_profile


def language_query_length(graph: str, chunk_size: int) -> int:
    """
    Function:
        Return the fixed query length for one stable Language graph.

    Args:
        graph: Stable graph name.
        chunk_size: Prefill sequence length.

    Returns:
        Number of query rows consumed by the graph.
    """

    if graph == "prefill":
        return chunk_size
    if graph == "decode":
        return PBD_QUERY_LEN
    if graph == "decode_ar":
        return AR_QUERY_LEN
    for prefix in ("decode_pbd_q", "decode_ar_q"):
        if graph.startswith(prefix):
            suffix = graph[len(prefix):]
            if suffix.isdigit() and int(suffix) > 0:
                return int(suffix)
    raise ValueError(f"unsupported Language graph: {graph}")


def language_output_shapes(
    graph: str, chunk_size: int
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """
    Function:
        Describe Host-sampling logits and per-layer KV update shapes.

    Args:
        graph: Stable graph name.
        chunk_size: Prefill sequence length.

    Returns:
        A logits shape and a single-layer KV update shape.
    """

    query_len = language_query_length(graph, chunk_size)
    logits_rows = 1 if graph == "prefill" else query_len
    return (
        (1, logits_rows, VOCAB_SIZE),
        (1, query_len, LANGUAGE_KV_HEAD_COUNT, LANGUAGE_HEAD_DIM),
    )


def language_io_contract(
    graph: str,
    chunk_size: int,
    cache_len: int,
    *,
    cache_dtype: str = "float32",
) -> tuple[
    list[tuple[tuple[int, ...], str]],
    list[tuple[tuple[int, ...], str]],
]:
    """
    Function:
        Describe all input and output tensors at a graph boundary.

    Args:
        graph: Stable graph name.
        chunk_size: Prefill sequence length.
        cache_len: KV cache capacity.
        cache_dtype: Boundary dtype used by converted graphs.

    Returns:
        Two lists containing ``(shape, dtype)`` descriptors for inputs/outputs.
    """

    query_len = language_query_length(graph, chunk_size)
    logits_shape, update_shape = language_output_shapes(graph, chunk_size)
    cache_shape = (1, cache_len, LANGUAGE_KV_HEAD_COUNT, LANGUAGE_HEAD_DIM)
    inputs = [
        ((1, query_len, HIDDEN_SIZE), "float16"),
        ((1, 1, query_len), "int32"),
        ((1, query_len, cache_len), "float16"),
        *[(cache_shape, cache_dtype) for _ in range(LANGUAGE_CACHE_TENSOR_COUNT)],
    ]
    outputs = [
        (logits_shape, "float16"),
        *[(update_shape, cache_dtype) for _ in range(LANGUAGE_CACHE_TENSOR_COUNT)],
    ]
    return inputs, outputs


def validate_compiler_profile(
    manifest: Mapping[str, Any], expected_profile: Mapping[str, Any]
) -> dict[str, Any]:
    """
    Function:
        Check ABI fields when a calibration profile is present.

    Args:
        manifest: Calibration scale manifest.
        expected_profile: ABI fields expected by the current compiler.

    Returns:
        The manifest profile, or an empty mapping for legacy manifests.

    Raises:
        ValueError: If a present profile disagrees with the expected fields.

    Notes:
        Older calibration manifests did not record a profile. They remain
        usable; a profile is validated only when the manifest contains one.
    """

    profile = manifest.get("profile")
    if not isinstance(profile, Mapping):
        return {}
    drift = {
        name: {"expected": expected, "actual": profile.get(name)}
        for name, expected in expected_profile.items()
        if profile.get(name) != expected
    }
    if drift:
        raise ValueError(f"scale manifest compiler profile mismatch: {drift}")
    return dict(profile)
