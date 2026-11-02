# -*- coding: utf-8 -*-
import unittest
from xxt_agent.ai_solver import DeepSeekSolver


class TestDeepSeekSolver(unittest.TestCase):
    def setUp(self):
        self.solver = DeepSeekSolver(api_key="sk-test-dummy")

    def test_parse_json_list(self):
        raw = '["A", "B"]'
        parsed = self.solver._parse_answer_list(raw)
        self.assertEqual(parsed, ["A", "B"])

    def test_parse_markdown_fence(self):
        raw = "```json\n[\"答案文本\"]\n```"
        parsed = self.solver._parse_answer_list(raw)
        self.assertEqual(parsed, ["答案文本"])

    def test_parse_thinking_block(self):
        raw = "<think>思考中...</think>\n[\"C\"]"
        parsed = self.solver._parse_answer_list(raw)
        self.assertEqual(parsed, ["C"])

    def test_parse_slash_format(self):
        raw = "A/B/C"
        parsed = self.solver._parse_answer_list(raw)
        self.assertEqual(parsed, ["A", "B", "C"])

    def test_match_options_letter(self):
        options = ["A. 莫扎特", "B. 贝多芬", "C. 肖邦"]
        matched = self.solver.match_options(["B"], options)
        self.assertEqual(matched, [1])

    def test_match_options_text_content(self):
        options = ["A. 莫扎特", "B. 贝多芬", "C. 肖邦"]
        matched = self.solver.match_options(["贝多芬"], options)
        self.assertEqual(matched, [1])

    def test_match_options_multiple(self):
        options = ["A. 苹果", "B. 香蕉", "C. 橙子", "D. 葡萄"]
        matched = self.solver.match_options(["A", "C"], options, question_type="多选题")
        self.assertEqual(matched, [0, 2])

    def test_match_options_judge(self):
        options = ["A. 对", "B. 错"]
        matched_true = self.solver.match_options(["正确"], options, question_type="判断题")
        self.assertEqual(matched_true, [0])
        matched_false = self.solver.match_options(["错"], options, question_type="判断题")
        self.assertEqual(matched_false, [1])


if __name__ == "__main__":
    unittest.main()
