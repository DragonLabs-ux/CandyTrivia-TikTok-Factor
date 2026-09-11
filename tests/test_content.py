import unittest
from unittest.mock import patch

import candy_content as content
from candy_cloud import CloudError


class ContentVerificationTests(unittest.TestCase):
    def setUp(self):
        self.facts = [
            {'question': 'What planet is known as the Red Planet?',
             'answer': 'Mars', 'source_url': 'https://example.org/mars'},
            {'question': 'How many sides does a triangle have?',
             'answer': 'Three', 'source_url': 'https://example.org/triangle'},
        ]

    @staticmethod
    def check(index, matches=True, question=None, answer=None, source=None):
        return {'index': index, 'question_answer_match': matches,
                'answer_factually_supported': matches, 'source_supports_answer': matches,
                'corrected_question': question, 'corrected_answer': answer,
                'corrected_source_url': source}

    def test_every_question_answer_match_must_pass(self):
        checks = {'checks': [self.check(0), self.check(1)]}
        with patch.object(content, 'request_json', return_value=checks):
            self.assertEqual(self.facts, content.verify_question_answers(self.facts))

    def test_mismatched_answer_is_corrected_and_rechecked(self):
        first = {'checks': [self.check(0), self.check(
            1, False, 'How many sides does a square have?', 'Four', 'https://example.org/square')]}
        second = {'checks': [self.check(0), self.check(1)]}
        with patch.object(content, 'request_json', side_effect=[first, second]):
            corrected = content.verify_question_answers(self.facts)
        self.assertEqual('Four', corrected[1]['answer'])
        self.assertEqual('How many sides does a square have?', corrected[1]['question'])

    def test_failed_autocorrection_rejects_entire_batch(self):
        failed = {'checks': [self.check(0), self.check(
            1, False, 'How many sides does a square have?', 'Four', 'https://example.org/square')]}
        with patch.object(content, 'request_json', side_effect=[failed, failed]):
            with self.assertRaisesRegex(CloudError, 'QUESTION_ANSWER_AUTOCORRECT_FAILED'):
                content.verify_question_answers(self.facts)

    def test_missing_check_rejects_entire_batch(self):
        checks = {'checks': [self.check(0)]}
        with patch.object(content, 'request_json', return_value=checks):
            with self.assertRaisesRegex(CloudError, 'QUESTION_ANSWER_VERIFICATION_FAILED'):
                content.verify_question_answers(self.facts)


if __name__ == '__main__':
    unittest.main()
