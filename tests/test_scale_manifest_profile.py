"""Tests that calibration scales cannot drift from the compiler profile."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMPILER_ROOT = PROJECT_ROOT / "compiler"
if str(COMPILER_ROOT) not in sys.path:
    sys.path.insert(0, str(COMPILER_ROOT))

from model.contract import validate_compiler_profile  # noqa: E402


class ScaleManifestProfileTests(unittest.TestCase):
    """Reject calibration data generated for a different Language ABI."""

    def manifest(self, chunk_size: int) -> dict:
        return {
            "profile": {
                "chunk_size": chunk_size,
                "cache_len": 4096,
                "pbd_query_len": 6,
            },
        }

    def test_matching_profile_is_accepted(self) -> None:
        profile = validate_compiler_profile(
            self.manifest(1024),
            {
                "chunk_size": 1024,
                "cache_len": 4096,
                "pbd_query_len": 6,
            },
        )
        self.assertEqual(profile["chunk_size"], 1024)

    def test_chunk_drift_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "compiler profile mismatch"):
            validate_compiler_profile(
                self.manifest(768),
                {
                    "chunk_size": 1024,
                    "cache_len": 4096,
                    "pbd_query_len": 6,
                },
            )

    def test_legacy_manifest_without_profile_remains_usable(self) -> None:
        profile = validate_compiler_profile(
            {"sample_count": 1200},
            {"chunk_size": 1024, "cache_len": 4096},
        )
        self.assertEqual(profile, {})


if __name__ == "__main__":
    unittest.main()
