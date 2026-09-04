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

    def test_every_question_answer_match_must_pass(self):
        checks = {'checks': [
            {'index': 0, 'question_answer_match': True,
             'answer_factually_supported': True, 'source_supports_answer': True},
            {'index': 1, 'question_answer_match': True,
             'answer_factually_supported': True, 'source_supports_answer': True},
        ]}
        with patch.object(content, 'request_json', return_value=checks):
            content.verify_question_answers(self.facts)

    def test_one_mismatched_answer_rejects_entire_batch(self):
        checks = {'checks': [
            {'index': 0, 'question_answer_match': True,
             'answer_factually_supported': True, 'source_supports_answer': True},
            {'index': 1, 'question_answer_match': False,
             'answer_factually_supported': True, 'source_supports_answer': True},
        ]}
        with patch.object(content, 'request_json', return_value=checks):
            with self.assertRaisesRegex(CloudError, 'QUESTION_ANSWER_VERIFICATION_FAILED'):
                content.verify_question_answers(self.facts)

    def test_missing_check_rejects_entire_batch(self):
        checks = {'checks': [
            {'index': 0, 'question_answer_match': True,
             'answer_factually_supported': True, 'source_supports_answer': True},
        ]}
        with patch.object(content, 'request_json', return_value=checks):
            with self.assertRaisesRegex(CloudError, 'QUESTION_ANSWER_VERIFICATION_FAILED'):
                content.verify_question_answers(self.facts)


if __name__ == '__main__':
    unittest.main()
