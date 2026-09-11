from __future__ import annotations

import unittest

import candy_metrics as m


class MetricsTests(unittest.TestCase):
    def test_hook_experiment_starts_at_post_25_and_alternates(self):
        self.assertEqual('cover-hook', m.hook_variant(24))
        self.assertEqual('cover-hook', m.hook_variant(25))
        self.assertEqual('question-first-hook', m.hook_variant(26))
        self.assertEqual('cover-hook', m.hook_variant(27))

    def test_metric_summary_extracts_core_tiktok_signals(self):
        metrics = [
            {'type': 'views', 'name': 'Views', 'value': 100, 'unit': 'count'},
            {'type': 'likes', 'name': 'Likes', 'value': 5, 'unit': 'count'},
            {'type': 'comments', 'name': 'Comments', 'value': 2, 'unit': 'count'},
            {'type': 'shares', 'name': 'Shares', 'value': 1, 'unit': 'count'},
            {'type': 'follows', 'name': 'Follows', 'value': 3, 'unit': 'count'},
        ]
        summary = m.summarize(metrics)
        self.assertEqual(100, summary['views'])
        self.assertEqual(2, summary['comments'])
        self.assertEqual(1, summary['shares'])
        self.assertEqual(3, summary['follows'])
        self.assertAlmostEqual(8.0, summary['engagement_rate'])


if __name__ == '__main__':
    unittest.main()
