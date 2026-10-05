"""Focused contract tests for the local Vocal Practice Companion."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

import vocal_practice  # noqa: E402


class ArchiveBoundaryTests(unittest.TestCase):
    def test_canonical_archive_is_accepted(self) -> None:
        self.assertEqual(
            vocal_practice.archive_root_or_error(vocal_practice.canonical_archive_root()),
            vocal_practice.canonical_archive_root(),
        )

    def test_arbitrary_archive_path_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "canonical private archive"):
            vocal_practice.archive_root_or_error("/tmp/vocal-practice-test")

    def test_cli_rejects_alternate_archive_before_writing(self) -> None:
        self.assertEqual(
            vocal_practice.main(["--data-dir", "/tmp/vocal-practice-test", "verify-archive"]),
            2,
        )

    def test_account_name_accepts_safe_local_label(self) -> None:
        self.assertEqual(vocal_practice.account_name_or_error("Evening practice-2"), "Evening practice-2")

    def test_account_name_rejects_path_like_label(self) -> None:
        with self.assertRaisesRegex(ValueError, "account name"):
            vocal_practice.account_name_or_error("../other-profile")


class EvidenceCatalogTests(unittest.TestCase):
    def test_catalog_resolves_to_local_documents_with_matching_ids(self) -> None:
        vocal_practice.validate_evidence_catalog()

    def test_catalog_rejects_out_of_corpus_path(self) -> None:
        original = vocal_practice.EVIDENCE["immediate-sovte-warmup-singers"]["path"]
        try:
            vocal_practice.EVIDENCE["immediate-sovte-warmup-singers"]["path"] = "README.md"
            with self.assertRaisesRegex(RuntimeError, "does not resolve"):
                vocal_practice.validate_evidence_catalog()
        finally:
            vocal_practice.EVIDENCE["immediate-sovte-warmup-singers"]["path"] = original


if __name__ == "__main__":
    unittest.main()
