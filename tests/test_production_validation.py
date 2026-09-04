from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "candy_production_validation", ROOT / "candy_production_validation.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ProductionValidationTests(unittest.TestCase):
    def test_42_post_rotation_is_exactly_28_a_and_14_b(self) -> None:
        plan = MODULE.rotation_plan([])
        templates = [row["visualTemplate"] for row in plan]
        self.assertEqual(42, len(templates))
        self.assertEqual(28, templates.count("A"))
        self.assertEqual(14, templates.count("B"))
        self.assertEqual(["A", "A", "B", "A", "A", "B"], templates[:6])

    def test_rate_parser(self) -> None:
        self.assertEqual(30.0, MODULE.parse_rate("30/1"))
        self.assertAlmostEqual(29.97, MODULE.parse_rate("30000/1001"), places=2)

    def test_approved_templates_exclude_c(self) -> None:
        self.assertEqual(("A", "B"), MODULE.APPROVED_TEMPLATES)


if __name__ == "__main__":
    unittest.main()
