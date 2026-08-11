"""Fixed LocateAnything-3B compiler and Language graph specification."""

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
