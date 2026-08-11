"""Regression tests for the stable S600 Language compiler contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMPILER_ROOT = PROJECT_ROOT / "compiler"
if str(COMPILER_ROOT) not in sys.path:
    sys.path.insert(0, str(COMPILER_ROOT))

from configuration import load_config_file  # noqa: E402
from build_adapter import build_parser as build_adapter_parser  # noqa: E402
from build_adapter import validate_device  # noqa: E402
from model.contract import (  # noqa: E402
    LANGUAGE_INPUT_COUNT,
    LANGUAGE_OUTPUT_COUNT,
    language_io_contract,
    language_query_length,
)
from model.graphs import LANGUAGE_GRAPHS  # noqa: E402


EXPECTED_GRAPHS = (
    "prefill",
    "decode",
    "decode_ar",
    "decode_pbd_q7",
    "decode_pbd_q8",
    "decode_pbd_q9",
    "decode_pbd_q10",
    "decode_pbd_q11",
    "decode_pbd_q12",
    "decode_ar_q2",
    "decode_ar_q3",
    "decode_ar_q4",
    "decode_ar_q5",
)


class StableLanguageContractTests(unittest.TestCase):
    """Verify graph names, ABI shapes, configuration, and removed BPU ABI."""

    def test_exact_thirteen_graph_catalog(self) -> None:
        self.assertEqual(LANGUAGE_GRAPHS, EXPECTED_GRAPHS)

    def test_every_graph_has_stable_host_abi(self) -> None:
        for graph in LANGUAGE_GRAPHS:
            with self.subTest(graph=graph):
                query_len = language_query_length(graph, 1024)
                inputs, outputs = language_io_contract(graph, 1024, 4096)
                self.assertEqual(len(inputs), LANGUAGE_INPUT_COUNT)
                self.assertEqual(len(outputs), LANGUAGE_OUTPUT_COUNT)
                self.assertEqual(inputs[0], ((1, query_len, 2048), "float16"))
                self.assertEqual(inputs[2], ((1, query_len, 4096), "float16"))
                expected_logits_rows = 1 if graph == "prefill" else query_len
                self.assertEqual(
                    outputs[0], ((1, expected_logits_rows, 152681), "float16")
                )
                self.assertEqual(
                    outputs[1], ((1, query_len, 2, 128), "float32")
                )

    def test_default_config_matches_stable_profile(self) -> None:
        config = load_config_file(COMPILER_ROOT / "config" / "quantization.yaml")
        self.assertEqual(config["language"], {"chunk_size": 1024, "cache_len": 4096})
        self.assertEqual(config["quantization"]["language_weight_bits"], 8)
        self.assertEqual(config["quantization"]["lm_head_weight_bits"], 8)
        self.assertEqual(config["build"]["cores"]["prefill"], 4)
        self.assertEqual(config["build"]["cores"]["pbd"], 4)
        self.assertEqual(config["build"]["cores"]["ar"], 4)

    def test_build_adapter_defaults_match_stable_profile(self) -> None:
        args = build_adapter_parser().parse_args(
            [
                "--model_name",
                "locateanything-lm-3b",
                "--march",
                "nash-p",
                "--input_model_path",
                str(PROJECT_ROOT),
                "--output_model_path",
                str(PROJECT_ROOT / "unused-test-output"),
            ]
        )
        self.assertEqual(args.chunk_size, 1024)
        self.assertEqual(args.cache_len, 4096)
        self.assertEqual(args.decode_seq_len, 6)
        self.assertEqual((args.image_width, args.image_height), (672, 672))
        self.assertEqual(args.prefill_core_num, [4])
        self.assertEqual(args.decode_core_num, [4])
        self.assertEqual(args.vit_core_num, [4])

    def test_device_parser_does_not_probe_local_cuda(self) -> None:
        self.assertEqual(validate_device("cuda:7"), ["cuda:7"])

    def test_text_export_only_slices_prefill_logits(self) -> None:
        source = (COMPILER_ROOT / "model" / "text.py").read_text(encoding="utf-8")
        self.assertIn("num_tokens == self.config.prefill_seq_len", source)
        self.assertIn("return (logits, *new_keys, *new_values)", source)

    def test_compiler_has_no_bpu_sampling_graph_abi(self) -> None:
        forbidden = (
            "sampling_backend",
            "history_mask",
            "random_values",
            "build_pbd_sampler",
            "_export_cache_rows",
            "_export_output_range",
        )
        offenders: list[str] = []
        for path in COMPILER_ROOT.rglob("*"):
            if path.suffix not in {".py", ".sh", ".yaml"}:
                continue
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                if token in text:
                    offenders.append(f"{path.relative_to(PROJECT_ROOT)}: {token}")
        self.assertEqual(offenders, [])
        self.assertFalse((COMPILER_ROOT / "model" / "sampler.py").exists())


if __name__ == "__main__":
    unittest.main()
