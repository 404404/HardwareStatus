"""Guard source files that are actually copied into the Python 3.8 Client image."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile.client"


def client_runtime_sources():
    sources = []
    for line in DOCKERFILE.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] == "COPY":
            source = fields[1]
            if source.endswith(".py") and source.startswith(("clients/", "scripts/")):
                sources.append(ROOT / source)
    return sources


class Python38RuntimeCompatibilityTests(unittest.TestCase):
    def test_image_sources_do_not_use_known_post38_apis(self):
        forbidden_calls = (
            ".removeprefix(",
            ".removesuffix(",
            ".is_relative_to(",
            ".walk(",
            ".with_stem(",
            ".hardlink_to(",
            ".is_junction(",
            ".copy_into(",
        )
        sources = client_runtime_sources()
        self.assertTrue(sources, "Dockerfile.client runtime sources were not discovered")
        for source in sources:
            text = source.read_text(encoding="utf-8")
            for api in forbidden_calls:
                with self.subTest(source=source.relative_to(ROOT), api=api):
                    self.assertNotIn(api, text)
            self.assertNotRegex(
                text,
                r"(?m)^\s*(?:from|import)\s+(?:zoneinfo|graphlib|tomllib)\b",
            )

    def test_builtin_generic_and_union_annotations_are_postponed(self):
        modern_annotations = re.compile(
            r"\b(?:list|dict|set|tuple|frozenset)\s*\[|"
            r"\b(?:str|int|bool|bytes|Any|Path|Mapping|Sequence)\s*\|\s*"
        )
        for source in client_runtime_sources():
            text = source.read_text(encoding="utf-8")
            if modern_annotations.search(text):
                with self.subTest(source=source.relative_to(ROOT)):
                    self.assertIn("from __future__ import annotations", text)


if __name__ == "__main__":
    unittest.main()
