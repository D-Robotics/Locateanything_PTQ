#!/usr/bin/env python3
"""Compare the archived stable Language Converted BC and HBM contracts/results."""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from model.graphs import LANGUAGE_GRAPHS
from pipeline.language_audit import (
    LanguageBCArtifact,
    _descriptor_dtype,
    _descriptor_shape,
)


@dataclass(frozen=True)
class TensorSignature:
    """Describe one graph boundary tensor.

    Args:
        shape: Static tensor dimensions.
        dtype: Canonical NumPy dtype name.
    """

    shape: tuple[int, ...]
    dtype: str


def descriptor_signature(descriptor: Any) -> TensorSignature:
    """Return the stable shape and dtype of one HBDK tensor descriptor.

    Args:
        descriptor: HBDK BC or HBM tensor descriptor.
    """

    return TensorSignature(
        shape=_descriptor_shape(descriptor),
        dtype=_descriptor_dtype(descriptor).name,
    )


def graph_contract(artifact: LanguageBCArtifact) -> dict[str, Any]:
    """Serialize every input and output descriptor for one graph.

    Args:
        artifact: Loaded Converted BC or HBM graph wrapper.
    """

    def serialize(values: Iterable[Any]) -> list[dict[str, Any]]:
        """
        Function:
            Serialize an ordered descriptor collection.

        Args:
            values: Tensor descriptors from a graph boundary.

        Returns:
            JSON-compatible descriptor records.
        """
        return [
            {
                "index": index,
                "shape": list(descriptor_signature(value).shape),
                "dtype": descriptor_signature(value).dtype,
            }
            for index, value in enumerate(values)
        ]

    return {
        "inputs": serialize(artifact.inputs),
        "outputs": serialize(artifact.outputs),
    }


def compare_graph_contracts(
    converted_bc: LanguageBCArtifact,
    hbm: LanguageBCArtifact,
) -> dict[str, Any]:
    """Compare BC and HBM boundary tensors by semantic index.

    Args:
        converted_bc: Converted BC graph.
        hbm: Graph loaded from the linked HBM catalog.
    """

    bc_contract = graph_contract(converted_bc)
    hbm_contract = graph_contract(hbm)
    mismatches: list[dict[str, Any]] = []
    for direction in ("inputs", "outputs"):
        left = bc_contract[direction]
        right = hbm_contract[direction]
        if len(left) != len(right):
            mismatches.append(
                {
                    "direction": direction,
                    "reason": "count",
                    "converted_bc": len(left),
                    "hbm": len(right),
                }
            )
            continue
        for index, (bc_value, hbm_value) in enumerate(zip(left, right, strict=True)):
            if bc_value != hbm_value:
                mismatches.append(
                    {
                        "direction": direction,
                        "index": index,
                        "reason": "descriptor",
                        "converted_bc": bc_value,
                        "hbm": hbm_value,
                    }
                )
    return {
        "status": "passed" if not mismatches else "failed",
        "converted_bc": bc_contract,
        "hbm": hbm_contract,
        "mismatches": mismatches,
    }


def discover_converted_bc(bc_dir: Path) -> dict[str, Path]:
    """Resolve exactly one Converted BC file for every stable graph.

    Args:
        bc_dir: Directory containing the archived Language graph files.
    """

    resolved = bc_dir.expanduser().resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(resolved)
    discovered: dict[str, Path] = {}
    for graph in LANGUAGE_GRAPHS:
        suffix = f".{graph}_convert.bc"
        matches = sorted(path for path in resolved.glob(f"*{suffix}") if path.is_file())
        if len(matches) != 1:
            raise ValueError(
                f"{resolved}: expected one {graph} Converted BC, found {len(matches)}"
            )
        discovered[graph] = matches[0]
    return discovered


def load_converted_bc(path: Path, graph: str) -> LanguageBCArtifact:
    """Load one Converted BC graph through the installed HBDK environment.

    Args:
        path: Converted BC file.
        graph: Expected graph name.
    """

    from hbdk4.compiler import load

    module = load(str(path))
    functions = list(module.functions)
    if len(functions) != 1 or str(functions[0].name) != graph:
        names = [str(function.name) for function in functions]
        raise ValueError(f"{path}: expected only graph {graph}, got {names}")
    function = functions[0]
    return LanguageBCArtifact(
        graph=graph,
        path=path,
        function=function,
        inputs=list(function.inputs),
        outputs=list(function.outputs),
    )


def load_hbm_graphs(
    path: Path,
) -> tuple[Any, dict[str, LanguageBCArtifact]]:
    """Load the linked HBM once and expose the complete stable graph catalog.

    Args:
        path: Archived stable Language HBM.
    """

    from hbdk4.compiler.hbm import Hbm

    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    catalog = Hbm(str(resolved))
    functions = {str(function.name): function for function in catalog.graphs}
    expected = set(LANGUAGE_GRAPHS)
    missing = sorted(expected - set(functions))
    unexpected = sorted(set(functions) - expected)
    if missing or unexpected:
        raise ValueError(
            f"{resolved}: HBM graph catalog mismatch; missing={missing}, "
            f"unexpected={unexpected}"
        )
    artifacts = {
        graph: LanguageBCArtifact(
            graph=graph,
            path=resolved,
            function=functions[graph],
            inputs=list(functions[graph].inputs),
            outputs=list(functions[graph].outputs),
        )
        for graph in LANGUAGE_GRAPHS
    }
    return catalog, artifacts


def load_input_bundle(
    input_dir: Path,
    descriptors: list[Any],
) -> list[np.ndarray]:
    """Load indexed binary inputs using graph descriptor shapes and dtypes.

    Args:
        input_dir: Directory containing ``input_NNN.bin`` files.
        descriptors: Ordered graph input descriptors.
    """

    resolved = input_dir.expanduser().resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(resolved)
    values: list[np.ndarray] = []
    for index, descriptor in enumerate(descriptors):
        path = resolved / f"input_{index:03d}.bin"
        if not path.is_file():
            raise FileNotFoundError(path)
        signature = descriptor_signature(descriptor)
        raw = np.fromfile(path, dtype=np.dtype(signature.dtype))
        expected = math.prod(signature.shape)
        if raw.size != expected:
            raise ValueError(
                f"{path}: expected {expected} {signature.dtype} values, got {raw.size}"
            )
        values.append(np.ascontiguousarray(raw.reshape(signature.shape)))
    return values


def tensor_metrics(reference: np.ndarray, candidate: np.ndarray) -> dict[str, Any]:
    """Measure exact and numerical agreement for one BC/HBM output tensor.

    Args:
        reference: Converted BC output.
        candidate: HBM simulation output.
    """

    if reference.shape != candidate.shape:
        raise ValueError(f"shape mismatch: {reference.shape} != {candidate.shape}")
    if reference.dtype != candidate.dtype:
        raise ValueError(f"dtype mismatch: {reference.dtype} != {candidate.dtype}")
    exact = bool(np.array_equal(reference, candidate))
    finite = bool(np.isfinite(reference).all() and np.isfinite(candidate).all())
    left = reference.astype(np.float32, copy=False).reshape(-1)
    right = candidate.astype(np.float32, copy=False).reshape(-1)
    difference = right - left
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return {
        "shape": list(reference.shape),
        "dtype": reference.dtype.name,
        "finite": finite,
        "exact": exact,
        "different_elements": int(np.count_nonzero(reference != candidate)),
        "max_abs_error": float(np.max(np.abs(difference), initial=0.0)),
        "mean_abs_error": float(np.mean(np.abs(difference), dtype=np.float64)),
        "cosine": None if denominator == 0.0 else float(np.dot(left, right) / denominator),
    }


def logits_metrics(reference: np.ndarray, candidate: np.ndarray) -> dict[str, Any]:
    """Extend tensor metrics with row-level vocabulary decisions.

    Args:
        reference: Converted BC logits.
        candidate: HBM simulation logits.
    """

    metrics = tensor_metrics(reference, candidate)
    if reference.ndim != 3:
        raise ValueError(f"logits must be rank 3, got {reference.shape}")
    bc_top1 = np.argmax(reference.astype(np.float32), axis=-1)
    hbm_top1 = np.argmax(candidate.astype(np.float32), axis=-1)
    mismatched = np.flatnonzero(bc_top1.reshape(-1) != hbm_top1.reshape(-1))
    metrics.update(
        {
            "converted_bc_top1": bc_top1.reshape(-1).astype(int).tolist(),
            "hbm_top1": hbm_top1.reshape(-1).astype(int).tolist(),
            "top1_agreement_rate": float(np.mean(bc_top1 == hbm_top1)),
            "top1_mismatched_rows": mismatched.astype(int).tolist(),
        }
    )
    return metrics


def compare_graph_outputs(
    converted_bc: LanguageBCArtifact,
    hbm: LanguageBCArtifact,
    inputs: list[np.ndarray],
) -> dict[str, Any]:
    """Execute one graph in both formats and compare all 73 outputs.

    Args:
        converted_bc: Converted BC graph.
        hbm: Matching linked HBM graph.
        inputs: Descriptor-aligned fixed graph inputs.
    """

    started = time.monotonic()
    bc_outputs = converted_bc.run_outputs(inputs)
    bc_seconds = time.monotonic() - started
    started = time.monotonic()
    hbm_outputs = hbm.run_outputs(inputs)
    hbm_seconds = time.monotonic() - started
    if len(bc_outputs) != len(hbm_outputs):
        raise ValueError(
            f"output count mismatch: {len(bc_outputs)} != {len(hbm_outputs)}"
        )
    rows: list[dict[str, Any]] = []
    for index, (bc_output, hbm_output) in enumerate(
        zip(bc_outputs, hbm_outputs, strict=True)
    ):
        metrics = (
            logits_metrics(bc_output, hbm_output)
            if index == 0
            else tensor_metrics(bc_output, hbm_output)
        )
        rows.append({"index": index, **metrics})
    logits_agree = rows[0]["top1_agreement_rate"] == 1.0
    caches_exact = all(row["exact"] for row in rows[1:])
    finite = all(row["finite"] for row in rows)
    return {
        "status": "passed" if logits_agree and caches_exact and finite else "failed",
        "timing_seconds": {
            "converted_bc": bc_seconds,
            "hbm_simulation": hbm_seconds,
        },
        "acceptance": {
            "logits_top1_exact": logits_agree,
            "integer_kv_exact": caches_exact,
            "all_finite": finite,
        },
        "outputs": rows,
    }


def write_json(path: Path, value: dict[str, Any]) -> None:
    """Atomically write a validation report without touching model artifacts.

    Args:
        path: Destination JSON file.
        value: Serializable report payload.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def parser() -> argparse.ArgumentParser:
    """Build the explicit, read-only HBM audit command line."""

    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--bc-dir", type=Path, required=True)
    result.add_argument("--hbm", type=Path, required=True)
    result.add_argument("--report", type=Path, required=True)
    result.add_argument("--graph", choices=LANGUAGE_GRAPHS)
    result.add_argument(
        "--input-dir",
        type=Path,
        help="fixed input_NNN.bin bundle; required when --graph is used",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    """Validate all contracts and optionally execute one fixed graph comparison.

    Args:
        argv: Optional command-line argument override for tests.
    """

    args = parser().parse_args(argv)
    if (args.graph is None) != (args.input_dir is None):
        raise ValueError("--graph and --input-dir must be supplied together")
    bc_paths = discover_converted_bc(args.bc_dir)
    hbm_catalog, hbm_graphs = load_hbm_graphs(args.hbm)
    contracts: dict[str, Any] = {}
    requested_bc: LanguageBCArtifact | None = None
    for index, graph in enumerate(LANGUAGE_GRAPHS, 1):
        converted_bc = load_converted_bc(bc_paths[graph], graph)
        contracts[graph] = compare_graph_contracts(converted_bc, hbm_graphs[graph])
        if graph == args.graph:
            requested_bc = converted_bc
        print(
            f"[INFO] [hbm.audit] [{index}/{len(LANGUAGE_GRAPHS)}] CONTRACT "
            f"graph={graph} status={contracts[graph]['status']}",
            flush=True,
        )
    contract_passed = all(row["status"] == "passed" for row in contracts.values())
    execution = None
    if args.graph is not None:
        if requested_bc is None:
            raise RuntimeError(f"requested graph was not loaded: {args.graph}")
        inputs = load_input_bundle(args.input_dir, requested_bc.inputs)
        execution = compare_graph_outputs(
            requested_bc, hbm_graphs[args.graph], inputs
        )
    report = {
        "schema_version": 1,
        "status": (
            "passed"
            if contract_passed and (execution is None or execution["status"] == "passed")
            else "failed"
        ),
        "scope": "archived Converted BC versus linked HBM in the installed HBDK environment",
        "contracts": contracts,
        "execution": execution,
    }
    write_json(args.report.expanduser().resolve(), report)
    print(
        f"[INFO] [hbm.audit] [-/-] COMPLETE status={report['status']} "
        f"report={args.report.expanduser().resolve()}",
        flush=True,
    )
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
