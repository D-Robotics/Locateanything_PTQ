#!/usr/bin/env python3
"""Continue the LocateAnything Vision build from an exported visual BC."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPILER_ROOT = REPO_ROOT / "compiler"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(COMPILER_ROOT) not in sys.path:
    sys.path.insert(0, str(COMPILER_ROOT))

from hbdk4.compiler import load, save
from hbdk4.compiler.hbm import Hbm, Hbo

from model.base import Model
from model.contract import derive_vision_profile
from pipeline.progress import StageProgress  # noqa: E402


IO_DTYPE = "float16"


def heading(value: str) -> None:
    """
    Function:
        Print a concise Vision build stage heading.

    Args:
        value: Heading text.

    Returns:
        None.
    """
    print(f"\n================== {value} ==================", flush=True)


def canonical_dtype(value: Any) -> str:
    """
    Function:
        Normalize a Vision tensor descriptor dtype.

    Args:
        value: Compiler tensor descriptor.

    Returns:
        Canonical dtype name.
    """
    tensor_type = getattr(value, "type", None)
    raw = getattr(tensor_type, "np_dtype", None)
    if raw is None:
        raise RuntimeError("visual tensor descriptor has no np_dtype")
    text = str(raw).lower()
    for dtype in ("float16", "float32", "int8", "uint8", "int16", "int32", "int64"):
        if dtype in text:
            return dtype
    raise RuntimeError(f"unsupported visual tensor dtype: {raw!r}")


def validate_visual_function(
    function: Any,
    input_shape: tuple[int, ...],
    output_shape: tuple[int, ...],
) -> None:
    """
    Function:
        Validate one Vision function's static input/output ABI.

    Args:
        function: Compiler function descriptor.

    Returns:
        None.
    """
    if str(function.name) != "visual":
        raise RuntimeError(f"visual graph name mismatch: {function.name}")
    if len(function.inputs) != 1 or len(function.outputs) != 1:
        raise RuntimeError(
            "visual graph must expose one input and one output; "
            f"got {len(function.inputs)} and {len(function.outputs)}"
        )
    actual_input_shape = tuple(function.inputs[0].type.shape)
    actual_output_shape = tuple(function.outputs[0].type.shape)
    input_dtype = canonical_dtype(function.inputs[0])
    output_dtype = canonical_dtype(function.outputs[0])
    if actual_input_shape != input_shape or actual_output_shape != output_shape:
        raise RuntimeError(
            f"visual graph shape mismatch: input={actual_input_shape} "
            f"output={actual_output_shape}; expected {input_shape} -> {output_shape}"
        )
    if input_dtype != IO_DTYPE or output_dtype != IO_DTYPE:
        raise RuntimeError(
            f"visual graph dtype mismatch: input={input_dtype} output={output_dtype}; "
            f"expected {IO_DTYPE} -> {IO_DTYPE}"
        )


def validate_visual_bc(
    path: Path,
    input_shape: tuple[int, ...],
    output_shape: tuple[int, ...],
) -> None:
    """
    Function:
        Validate a source or converted Vision BC artifact.

    Args:
        path: BC path.

    Returns:
        None.
    """
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"visual BC is missing: {path}")
    module = load(str(path))
    functions = list(module.functions)
    if len(functions) != 1 or str(functions[0].name) != "visual":
        names = [str(function.name) for function in functions]
        raise RuntimeError(f"visual BC must contain only graph 'visual'; got {names}")
    function = functions[0]
    validate_visual_function(function, input_shape, output_shape)
    actual_input_shape = tuple(function.inputs[0].type.shape)
    actual_output_shape = tuple(function.outputs[0].type.shape)
    print(
        f"[PASS] visual: input={actual_input_shape}/{IO_DTYPE} "
        f"output={actual_output_shape}/{IO_DTYPE}",
        flush=True,
    )


def valid_function(
    path: Path,
    expected_name: str,
    input_shape: tuple[int, ...],
    output_shape: tuple[int, ...],
) -> bool:
    """
    Function:
        Check whether a converted Vision BC is readable and valid.

    Args:
        path: Candidate BC path.
        expected_name: Expected function name.

    Returns:
        True when the candidate is valid.
    """
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        module = load(str(path))
        functions = list(module.functions)
        if len(functions) != 1 or str(functions[0].name) != expected_name:
            return False
        validate_visual_function(functions[0], input_shape, output_shape)
        return True
    except Exception:
        return False


def valid_hbo(path: Path) -> bool:
    """
    Function:
        Check whether a Vision HBO artifact can be opened.

    Args:
        path: Candidate HBO path.

    Returns:
        True when the artifact is readable.
    """
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        Hbo(str(path))
        return True
    except Exception:
        return False


def hbm_contract_matches(
    path: Path,
    input_shape: tuple[int, ...],
    output_shape: tuple[int, ...],
) -> bool:
    """
    Function:
        Validate the single ``visual`` graph in a Vision HBM.

    Args:
        path: Candidate HBM path.

    Returns:
        True when the HBM matches the Vision ABI.
    """
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        model = Hbm(str(path))
        graphs = {str(graph.name): graph for graph in model.graphs}
        if set(graphs) != {"visual"}:
            return False
        graph = graphs["visual"]
        if len(graph.inputs) != 1 or len(graph.outputs) != 1:
            return False
        validate_visual_function(graph, input_shape, output_shape)
        return True
    except Exception:
        return False


def valid_hbm(
    path: Path,
    input_shape: tuple[int, ...],
    output_shape: tuple[int, ...],
) -> bool:
    """
    Function:
        Check a Vision HBM artifact against its ABI.

    Args:
        path: Candidate HBM path.

    Returns:
        True when the artifact is valid.
    """
    return hbm_contract_matches(path, input_shape, output_shape)


def parse_args() -> argparse.Namespace:
    """
    Function:
        Parse standalone Vision build options.

    Args:
        None; options are read from ``sys.argv``.

    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--bc_path", type=Path, required=True)
    parser.add_argument("--hbm_path", type=Path, required=True)
    parser.add_argument("--march", default="nash-p")
    parser.add_argument("--core_num", type=int, choices=(1, 2, 4), default=4)
    parser.add_argument("--jobs", type=int, default=16)
    parser.add_argument("--image_width", type=int, default=672)
    parser.add_argument("--image_height", type=int, default=672)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--check_only", action="store_true")
    return parser.parse_args()


def main() -> int:
    """
    Function:
        Run Vision BC validation, conversion, HBO compilation and linking.

    Args:
        None; options are read from ``sys.argv``.

    Returns:
        Process exit status.
    """
    args = parse_args()
    args.bc_path = args.bc_path.resolve()
    args.hbm_path = args.hbm_path.resolve()
    args.hbm_path.parent.mkdir(parents=True, exist_ok=True)
    vision_profile = derive_vision_profile(args.image_width, args.image_height)
    input_shape = tuple(vision_profile["vision_input_shape"])
    output_shape = tuple(vision_profile["projected_visual_shape"])

    heading("SOURCE CONTRACT")
    validate_visual_bc(args.bc_path, input_shape, output_shape)
    if args.check_only:
        heading("SOURCE CONTRACT PASSED")
        return 0

    progress = StageProgress(3, "Vision build")

    converted_path = args.hbm_path.with_suffix(".visual_convert.bc")
    with progress.stage("Convert Vision graph"):
        if args.resume and valid_function(
            converted_path, "visual", input_shape, output_shape
        ):
            print(f"[RESUME] converted visual: {converted_path}", flush=True)
        else:
            heading("CONVERT VISUAL")
            converted = Model.convert_mlir(
                load(str(args.bc_path)),
                enable_vpu=True,
                march=args.march,
                dynamic_quant=True,
            )
            function = converted.functions[0]
            if str(function.name) != "visual":
                raise RuntimeError(
                    f"converted function is {function.name}, expected visual"
                )
            function.remove_io_op(["Dequantize", "Quantize"])
            temporary = converted_path.with_name(converted_path.stem + ".partial.bc")
            save(converted, str(temporary))
            os.replace(temporary, converted_path)
            validate_visual_bc(converted_path, input_shape, output_shape)
            print(f"[PASS] converted visual: {converted_path}", flush=True)

    hbo_path = args.hbm_path.with_suffix(".visual.hbo")
    with progress.stage("Compile Vision HBO"):
        if args.resume and valid_hbo(hbo_path):
            print(f"[RESUME] HBO visual core={args.core_num}: {hbo_path}", flush=True)
        else:
            heading(f"COMPILE VISUAL CORE={args.core_num}")
            module = load(str(converted_path))
            temporary = hbo_path.with_name(hbo_path.stem + ".partial.hbo")
            kwargs = {
                "march": args.march,
                "jobs": args.jobs,
                "progress_bar": True,
                "max_time_per_fc": 0.0,
                "opt": 2,
                "debug": False,
                "advice": 0.0,
                "balance": 100,
                "input_no_padding": True,
                "output_no_padding": True,
                "core_num": args.core_num,
            }
            if args.core_num > 1:
                kwargs["max_l2m_size"] = 25165824
            Model.compile_hbo(module, save_path=str(temporary), **kwargs)
            os.replace(temporary, hbo_path)
            Hbo(str(hbo_path))
            print(f"[PASS] HBO visual core={args.core_num}: {hbo_path}", flush=True)

    with progress.stage("Link Vision HBM"):
        if args.resume and valid_hbm(args.hbm_path, input_shape, output_shape):
            print(f"[RESUME] HBM: {args.hbm_path}", flush=True)
        else:
            heading(f"LINK {args.hbm_path.name}")
            temporary = args.hbm_path.with_name(args.hbm_path.stem + ".partial.hbm")
            Model.link_models([Hbo(str(hbo_path))], str(temporary))
            os.replace(temporary, args.hbm_path)
            if not hbm_contract_matches(args.hbm_path, input_shape, output_shape):
                raise RuntimeError(f"linked HBM graph contract mismatch: {args.hbm_path}")
            print(f"[PASS] HBM: {args.hbm_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
