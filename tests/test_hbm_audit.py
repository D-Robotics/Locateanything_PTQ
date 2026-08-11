from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
COMPILER = ROOT / "compiler"
sys.path.insert(0, str(COMPILER))
SPEC = importlib.util.spec_from_file_location(
    "hbm_audit", COMPILER / "pipeline" / "hbm_audit.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class Descriptor:
    def __init__(self, shape: tuple[int, ...], dtype: str) -> None:
        self.type = SimpleNamespace(shape=shape, np_dtype=np.dtype(dtype))


class HbmAuditTests(unittest.TestCase):
    def test_tensor_metrics_reports_exact_integer_output(self) -> None:
        reference = np.arange(8, dtype=np.int8).reshape(1, 2, 2, 2)
        metrics = MODULE.tensor_metrics(reference, reference.copy())
        self.assertTrue(metrics["finite"])
        self.assertTrue(metrics["exact"])
        self.assertEqual(metrics["different_elements"], 0)

    def test_logits_metrics_detects_decision_change(self) -> None:
        reference = np.array([[[0.0, 2.0, 1.0]]], dtype=np.float16)
        candidate = np.array([[[0.0, 1.0, 2.0]]], dtype=np.float16)
        metrics = MODULE.logits_metrics(reference, candidate)
        self.assertEqual(metrics["top1_agreement_rate"], 0.0)
        self.assertEqual(metrics["top1_mismatched_rows"], [0])

    def test_input_bundle_uses_descriptor_shape_and_dtype(self) -> None:
        descriptors = [Descriptor((1, 2), "float16"), Descriptor((1,), "int32")]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            np.array([[1.0, 2.0]], dtype=np.float16).tofile(root / "input_000.bin")
            np.array([7], dtype=np.int32).tofile(root / "input_001.bin")
            values = MODULE.load_input_bundle(root, descriptors)
        self.assertEqual(values[0].shape, (1, 2))
        self.assertEqual(values[0].dtype, np.dtype("float16"))
        self.assertEqual(values[1].tolist(), [7])

    def test_input_bundle_rejects_wrong_element_count(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            np.array([1.0], dtype=np.float16).tofile(root / "input_000.bin")
            with self.assertRaisesRegex(ValueError, "expected 2"):
                MODULE.load_input_bundle(root, [Descriptor((1, 2), "float16")])


if __name__ == "__main__":
    unittest.main()
