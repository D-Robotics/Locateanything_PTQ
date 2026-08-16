#!/usr/bin/env python3
"""Convert and compile the fixed LocateAnything Language graphs."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
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
from model.contract import (
    language_io_contract,
    language_output_shapes,
    language_query_length,
)
from model.graphs import LANGUAGE_GRAPHS
from pipeline.progress import StageProgress, format_status_line  # noqa: E402


KNOWN_STAGES = set(LANGUAGE_GRAPHS)


@dataclass(frozen=True)
class LanguageContract:
    chunk_size: int
    cache_len: int
    batch_size: int = 1
    compact_logits: bool = False
    fuse_initial_pbd: bool = False


def expected_contract(
    name: str, contract: LanguageContract
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """
    Function:
        Return the expected logits and KV update shapes for a graph.

    Args:
        name: Stable Language graph name.
        contract: Chunk/cache dimensions.

    Returns:
        Logits and per-layer KV update shapes.
    """
    return language_output_shapes(
        name,
        contract.chunk_size,
        batch_size=contract.batch_size,
        compact_logits=contract.compact_logits,
        fuse_initial_pbd=contract.fuse_initial_pbd,
    )


def query_length(name: str, contract: LanguageContract) -> int:
    """
    Function:
        Return the query length of a stable Language graph.

    Args:
        name: Stable Language graph name.
        contract: Chunk/cache dimensions.

    Returns:
        Static query length.
    """
    if name not in KNOWN_STAGES:
        raise ValueError(f"unsupported Language graph: {name}")
    return language_query_length(name, contract.chunk_size)


def graph_label(name: str) -> str:
    """
    Function:
        Format a stable graph name for progress output.

    Args:
        name: Stable Language graph name.

    Returns:
        Human-readable graph label.
    """
    if name == "prefill":
        return "Prefill"
    if name == "decode":
        return "Decode PBD q=6"
    if name == "decode_ar":
        return "Decode AR q=1"
    if name.startswith("decode_pbd_q"):
        return f"Decode PBD q={int(name.rsplit('q', 1)[1])}"
    if name.startswith("decode_ar_q"):
        return f"Decode AR q={int(name.rsplit('q', 1)[1])}"
    raise ValueError(f"unsupported Language graph: {name}")


def _canonical_dtype(value: Any) -> str:
    """
    Function:
        Normalize a compiler tensor descriptor dtype.

    Args:
        value: Compiler tensor descriptor.

    Returns:
        Canonical dtype name.
    """
    tensor_type = getattr(value, "type", None)
    raw = getattr(tensor_type, "np_dtype", None)
    if raw is None:
        raise RuntimeError("tensor descriptor has no np_dtype")
    text = str(raw).lower()
    for dtype in (
        "float16", "float32", "int8", "uint8", "int16", "int32", "int64"
    ):
        if dtype in text:
            return dtype
    raise RuntimeError(f"unsupported tensor dtype: {raw!r}")


def _descriptor_contract(value: Any) -> tuple[tuple[int, ...], str]:
    """
    Function:
        Extract a static shape and dtype from a tensor descriptor.

    Args:
        value: Compiler tensor descriptor.

    Returns:
        ``(shape, dtype)`` contract tuple.
    """
    tensor_type = getattr(value, "type", None)
    shape = tuple(getattr(tensor_type, "shape", ()))
    if not shape or not all(isinstance(axis, int) and axis > 0 for axis in shape):
        raise RuntimeError(f"tensor has non-static shape: {shape}")
    return shape, _canonical_dtype(value)


def expected_io_contract(
    name: str,
    contract: LanguageContract,
    *,
    cache_dtype: str = "float32",
) -> tuple[list[tuple[tuple[int, ...], str]], list[tuple[tuple[int, ...], str]]]:
    """
    Function:
        Return the full stable graph boundary contract.

    Args:
        name: Stable Language graph name.
        contract: Chunk/cache dimensions.
        cache_dtype: Converted graph cache dtype.

    Returns:
        Input and output descriptor lists.
    """
    return language_io_contract(
        name,
        contract.chunk_size,
        contract.cache_len,
        batch_size=contract.batch_size,
        cache_dtype=cache_dtype,
        compact_logits=contract.compact_logits,
        fuse_initial_pbd=contract.fuse_initial_pbd,
    )


def validate_graph_contract(
    function: Any,
    name: str,
    contract: LanguageContract,
    *,
    cache_dtype: str = "float32",
) -> None:
    """
    Function:
        Validate one source or converted graph against the stable ABI.

    Args:
        function: Compiler function descriptor.
        name: Expected stable graph name.
        contract: Chunk/cache dimensions.
        cache_dtype: Expected cache boundary dtype.

    Returns:
        None.
    """
    actual_name = str(function.name)
    if actual_name != name:
        raise RuntimeError(
            f"Language graph name mismatch: expected {name}, got {actual_name}"
        )
    expected_inputs, expected_outputs = expected_io_contract(
        name, contract, cache_dtype=cache_dtype
    )
    if len(function.inputs) != len(expected_inputs):
        raise RuntimeError(
            f"{name} contract has {len(function.inputs)} inputs; "
            f"expected {len(expected_inputs)}"
        )
    if len(function.outputs) != len(expected_outputs):
        raise RuntimeError(
            f"{name} contract has {len(function.outputs)} outputs; "
            f"expected {len(expected_outputs)}"
        )
    for direction, actual, expected in (
        ("input", function.inputs, expected_inputs),
        ("output", function.outputs, expected_outputs),
    ):
        for index, (descriptor, expected_descriptor) in enumerate(
            zip(actual, expected)
        ):
            try:
                actual_descriptor = _descriptor_contract(descriptor)
            except RuntimeError as exc:
                raise RuntimeError(f"{name} {direction}[{index}]: {exc}") from exc
            if actual_descriptor != expected_descriptor:
                raise RuntimeError(
                    f"{name} {direction}[{index}] mismatch: "
                    f"got {actual_descriptor}, expected {expected_descriptor}"
                )


def heading(value: str) -> None:
    """
    Function:
        Print a concise compiler stage heading.

    Args:
        value: Heading text.

    Returns:
        None.
    """
    print(f"\n================== {value} ==================", flush=True)


def discover_bc(
    bc_dir: Path,
    contract: LanguageContract,
) -> dict[str, Path]:
    """
    Function:
        Discover and validate all thirteen source BC graphs.

    Args:
        bc_dir: Directory containing source BC files.
        contract: Chunk/cache dimensions.

    Returns:
        Mapping from graph name to source BC path.
    """
    expected = set(LANGUAGE_GRAPHS)
    discovered: dict[str, Path] = {}
    candidates = [
        path for path in sorted(bc_dir.glob("*.bc"))
        if not path.name.endswith(("_convert.bc", ".partial.bc"))
    ]
    for path in candidates:
        module = load(str(path))
        functions = list(module.functions)
        if len(functions) != 1:
            raise RuntimeError(f"{path} contains {len(functions)} functions")
        function = functions[0]
        name = str(function.name)
        if name not in KNOWN_STAGES:
            continue
        if name in discovered:
            raise RuntimeError(f"duplicate {name} BC: {discovered[name]} and {path}")
        validate_graph_contract(function, name, contract)
        logits_shape = tuple(function.outputs[0].type.shape)
        cache_shape = tuple(function.outputs[1].type.shape)
        discovered[name] = path.resolve()
        print(
            f"[DETAIL] {name}: logits={logits_shape} cache={cache_shape} "
            f"inputs={len(function.inputs)} outputs={len(function.outputs)}",
            flush=True,
        )
        print(
            format_status_line(
                "build.language",
                len(discovered),
                len(expected),
                "PROGRESS",
                "Validate source BC",
                details=f"graph={name}",
            ),
            flush=True,
        )
    missing = sorted(expected - set(discovered))
    if missing:
        raise RuntimeError(f"missing BC graphs in {bc_dir}: {missing}")
    print(
        f"[PASS] fixed {len(discovered)}-graph source BC contract",
        flush=True,
    )
    return discovered


def valid_function(
    path: Path, expected_name: str, contract: LanguageContract
) -> bool:
    """
    Function:
        Check whether a converted BC has the expected graph contract.

    Args:
        path: Candidate BC path.
        expected_name: Expected graph name.
        contract: Chunk/cache dimensions.

    Returns:
        True when the candidate is valid.
    """
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        module = load(str(path))
        functions = list(module.functions)
        if len(functions) != 1:
            return False
        validate_graph_contract(
            functions[0], expected_name, contract, cache_dtype="int8"
        )
        return True
    except Exception:
        return False


def convert_stage(source: Path, destination: Path, name: str,
                  march: str, resume: bool, contract: LanguageContract) -> None:
    """
    Function:
        Convert one source BC graph and preserve its stable ABI.

    Args:
        source: Source BC path.
        destination: Converted BC path.
        name: Stable graph name.
        march: Target compiler march.
        resume: Reuse a valid converted graph.
        contract: Chunk/cache dimensions.
    """
    if resume and valid_function(destination, name, contract):
        print(f"[RESUME] converted {name}: {destination}", flush=True)
        return
    heading(f"CONVERT {name.upper()}")
    converted = Model.convert_mlir(
        load(str(source)),
        enable_vpu=True,
        march=march,
        dynamic_quant=True,
    )
    function = converted.functions[0]
    if str(function.name) != name:
        raise RuntimeError(f"converted function is {function.name}, expected {name}")
    function.remove_io_op(["Dequantize", "Quantize"])
    # Removing the boundary quantization wrappers exposes the integer KV cache
    # contract consumed by HBO compilation and the linked HBM.
    validate_graph_contract(function, name, contract, cache_dtype="int8")
    temporary = destination.with_name(destination.stem + ".partial.bc")
    save(converted, str(temporary))
    os.replace(temporary, destination)
    print(f"[PASS] converted {name}: {destination}", flush=True)


def valid_hbo(path: Path) -> bool:
    """
    Function:
        Check whether an HBO artifact can be opened.

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


def compile_stage(converted_bc: Path, destination: Path, name: str,
                  core_num: int, args: argparse.Namespace) -> None:
    """
    Function:
        Compile one converted graph into an HBO artifact.

    Args:
        converted_bc: Converted BC path.
        destination: HBO output path.
        name: Stable graph name.
        core_num: BPU core count.
        args: Language build options and contract.
    """
    if args.resume and valid_hbo(destination):
        print(f"[RESUME] HBO {name} core={core_num}: {destination}", flush=True)
        return
    heading(f"COMPILE {name.upper()} CORE={core_num}")
    module = load(str(converted_bc))
    functions = list(module.functions)
    if len(functions) != 1:
        raise RuntimeError(f"{converted_bc} contains {len(functions)} functions")
    validate_graph_contract(
        functions[0], name, args.contract, cache_dtype="int8"
    )
    temporary = destination.with_name(destination.stem + ".partial.hbo")
    kwargs = {
        "march": args.march,
        "jobs": args.jobs,
        "progress_bar": True,
        "max_time_per_fc": 0.0,
        "opt": 2,
        "debug": False,
        "advice": 0.0,
        "balance": 100,
        "enable_hpc": True,
        "input_no_padding": True,
        "output_no_padding": True,
        "core_num": core_num,
    }
    if core_num > 1:
        kwargs["max_l2m_size"] = 25165824
    Model.compile_hbo(module, save_path=str(temporary), **kwargs)
    os.replace(temporary, destination)
    Hbo(str(destination))
    print(f"[PASS] HBO {name} core={core_num}: {destination}", flush=True)


def hbm_contract_matches(
    path: Path, expected_names: list[str], contract: LanguageContract
) -> bool:
    """
    Function:
        Validate the graph catalog and ABI of one linked Language HBM.

    Args:
        path: Candidate HBM path.
        expected_names: Required graph names.
        contract: Chunk/cache dimensions.

    Returns:
        True when the HBM matches the stable contract.
    """
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        model = Hbm(str(path))
        graphs = {str(graph.name): graph for graph in model.graphs}
        if set(graphs) != set(expected_names):
            return False
        for name in expected_names:
            graph = graphs[name]
            validate_graph_contract(graph, name, contract, cache_dtype="int8")
        return True
    except Exception:
        return False


def valid_hbm(
    path: Path, expected_names: list[str], contract: LanguageContract
) -> bool:
    """
    Function:
        Check a linked HBM against the expected graph contract.

    Args:
        path: Candidate HBM path.
        expected_names: Required graph names.
        contract: Chunk/cache dimensions.

    Returns:
        True when the HBM is valid.
    """
    return hbm_contract_matches(path, expected_names, contract)


def link_variant(hbos: list[Path], destination: Path,
                 resume: bool, expected_names: list[str],
                 contract: LanguageContract) -> None:
    """
    Function:
        Link all graph HBOs into one validated Language HBM.

    Args:
        hbos: Ordered graph HBO paths.
        destination: HBM output path.
        resume: Reuse a valid existing HBM.
        expected_names: Required graph names.
        contract: Chunk/cache dimensions.
    """
    if resume and valid_hbm(destination, expected_names, contract):
        print(f"[RESUME] HBM: {destination}", flush=True)
        return
    if resume and destination.is_file() and destination.stat().st_size > 0:
        try:
            Hbm(str(destination))
            print(f"[STALE] HBM graph contract mismatch: {destination}", flush=True)
        except Exception:
            pass
    heading(f"LINK {destination.name}")
    temporary = destination.with_name(destination.stem + ".partial.hbm")
    Model.link_models([Hbo(str(path)) for path in hbos], str(temporary))
    os.replace(temporary, destination)
    if not hbm_contract_matches(destination, expected_names, contract):
        raise RuntimeError(f"linked HBM graph contract mismatch: {destination}")
    print(f"[PASS] HBM: {destination}", flush=True)


def parse_args() -> argparse.Namespace:
    """
    Function:
        Parse the standalone Language build options.

    Args:
        None; options are read from ``sys.argv``.

    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--bc_dir", type=Path, required=True)
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--march", default="nash-p")
    parser.add_argument("--prefill_core_num", type=int, choices=(1, 2, 4), default=4)
    parser.add_argument("--decode_core_num", type=int, choices=(1, 2, 4), default=4)
    parser.add_argument(
        "--ar_core_nums", type=int, nargs="+", choices=(1, 2, 4),
        default=[1, 2, 4],
    )
    parser.add_argument("--jobs", type=int, default=16)
    parser.add_argument("--chunk-size", type=int, default=1024)
    parser.add_argument("--cache-len", type=int, default=4096)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--language-w-bits", type=int, choices=(4, 8), default=8)
    parser.add_argument("--lm-head-w-bits", type=int, choices=(4, 8), default=8)
    parser.add_argument("--compact-logits", action="store_true")
    parser.add_argument("--fuse-initial-pbd", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--convert_only", action="store_true")
    parser.add_argument("--check_only", action="store_true")
    parser.add_argument(
        "--hbm_path", type=Path,
        help="Exact release HBM path; also selects its matching BC prefix.",
    )
    parser.add_argument("--embedding_path", type=Path)
    parser.add_argument("--expected_embedding_bytes", type=int)
    return parser.parse_args()


def main() -> int:
    """
    Function:
        Run source validation, conversion, HBO compilation and HBM linking.

    Args:
        None; options are read from ``sys.argv``.

    Returns:
        Process exit status.
    """
    args = parse_args()
    args.bc_dir = args.bc_dir.resolve()
    args.output_dir = args.output_dir.resolve()
    if args.hbm_path:
        args.hbm_path = args.hbm_path.resolve()
    if args.embedding_path:
        args.embedding_path = args.embedding_path.resolve()
    args.ar_core_nums = sorted(set(args.ar_core_nums))
    if (
        not 128 <= args.chunk_size <= 2048
        or not 256 <= args.cache_len <= 4096
        or args.cache_len <= args.chunk_size
        or args.chunk_size % 64
        or args.cache_len % 64
    ):
        raise RuntimeError("chunk/cache lengths must be multiples of 64 with cache > chunk")
    if args.batch_size not in (1, 2):
        raise RuntimeError("batch size must be 1 or 2")
    args.contract = LanguageContract(
        args.chunk_size,
        args.cache_len,
        batch_size=args.batch_size,
        compact_logits=args.compact_logits,
        fuse_initial_pbd=args.fuse_initial_pbd,
    )
    if args.hbm_path and len(args.ar_core_nums) != 1:
        raise RuntimeError("--hbm_path requires exactly one --ar_core_nums value")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.hbm_path:
        args.hbm_path.parent.mkdir(parents=True, exist_ok=True)
        converted_dir = args.hbm_path.parent
        hbo_dir = args.hbm_path.parent
    else:
        converted_dir = args.output_dir / "converted_bc"
        hbo_dir = args.output_dir / "hbo"
        converted_dir.mkdir(exist_ok=True)
        hbo_dir.mkdir(exist_ok=True)

    heading("SOURCE CONTRACT")
    source_bc = discover_bc(
        args.bc_dir,
        args.contract,
    )
    if args.embedding_path:
        if not args.embedding_path.is_file():
            raise RuntimeError(f"token embedding is missing: {args.embedding_path}")
        if (
            args.expected_embedding_bytes is not None
            and args.embedding_path.stat().st_size != args.expected_embedding_bytes
        ):
            raise RuntimeError(
                f"token embedding size is {args.embedding_path.stat().st_size}; "
                f"expected {args.expected_embedding_bytes}"
            )
    if args.check_only:
        heading("SOURCE CONTRACT PASSED")
        return 0
    stage_order = list(LANGUAGE_GRAPHS)
    pbd_stages = [
        graph for graph in stage_order
        if graph == "decode" or graph.startswith("decode_pbd_q")
    ]
    ar_stages = [graph for graph in stage_order if graph.startswith("decode_ar")]
    total_stages = len(stage_order)
    if not args.convert_only:
        total_stages += 1 + len(pbd_stages)
        total_stages += len(args.ar_core_nums) * (len(ar_stages) + 1)
    progress = StageProgress(total_stages, "Language build")
    if args.hbm_path:
        converted = {
            name: args.hbm_path.with_suffix(f".{name}_convert.bc")
            for name in stage_order
        }
    else:
        converted = {
            name: converted_dir / f"{name}_convert.bc" for name in stage_order
        }
    for name in stage_order:
        with progress.stage(f"Convert {graph_label(name)}"):
            convert_stage(
                source_bc[name], converted[name], name, args.march,
                args.resume, args.contract,
            )
    if args.convert_only:
        heading("CONVERT ONLY COMPLETED")
        return 0

    prefill_hbo = (
        args.hbm_path.with_suffix(".prefill.hbo")
        if args.hbm_path
        else hbo_dir / f"prefill_core{args.prefill_core_num}.hbo"
    )
    with progress.stage(f"Compile {graph_label('prefill')} HBO"):
        compile_stage(
            converted["prefill"], prefill_hbo, "prefill",
            args.prefill_core_num, args,
        )
    shared_hbos = {"prefill": prefill_hbo}
    for name in pbd_stages:
        if name not in converted:
            continue
        hbo = (
            args.hbm_path.with_suffix(f".{name}.hbo")
            if args.hbm_path
            else hbo_dir / f"{name}_core{args.decode_core_num}.hbo"
        )
        with progress.stage(f"Compile {graph_label(name)} HBO"):
            compile_stage(converted[name], hbo, name, args.decode_core_num, args)
        shared_hbos[name] = hbo
    for ar_core in args.ar_core_nums:
        ar_hbos: dict[str, Path] = {}
        for name in ar_stages:
            if name not in converted:
                continue
            ar_hbo = (
                args.hbm_path.with_suffix(f".{name}.hbo")
                if args.hbm_path
                else hbo_dir / f"{name}_core{ar_core}.hbo"
            )
            with progress.stage(f"Compile {graph_label(name)} HBO"):
                compile_stage(converted[name], ar_hbo, name, ar_core, args)
            ar_hbos[name] = ar_hbo
        hbm = args.hbm_path or args.output_dir / (
            f"LocateAnything-3B_language_chunk_{args.chunk_size}_cache_{args.cache_len}_"
            f"decoder_w{args.language_w_bits}_lmhead_w{args.lm_head_w_bits}_{args.march}_"
            f"prefill{args.prefill_core_num}_pbd{args.decode_core_num}_ar{ar_core}.hbm"
        )
        all_hbos = {**shared_hbos, **ar_hbos}
        with progress.stage(f"Link Language HBM (AR cores={ar_core})"):
            link_variant(
                [all_hbos[name] for name in stage_order],
                hbm,
                args.resume,
                stage_order,
                args.contract,
            )

    heading("ALL VARIANTS COMPLETED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
