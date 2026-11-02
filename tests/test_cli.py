# -*- coding: utf-8 -*-
import io
import json
import unittest
from unittest.mock import patch
from xxt_agent.cli import main


class TestCLI(unittest.TestCase):
    def test_cli_config_show(self):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            exit_code = main(["--format", "json", "config", "show"])
            self.assertEqual(exit_code, 0)
            output = mock_stdout.getvalue()
            parsed = json.loads(output)
            self.assertIn("api_model", parsed)
            self.assertIn("browser", parsed)

    def test_cli_solve(self):
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            exit_code = main([
                "--format", "json",
                "solve",
                "-q", "中国首都是哪里？",
                "-o", "A. 北京",
                "-o", "B. 上海",
                "-t", "单选题",
            ])
            self.assertEqual(exit_code, 0)
            output = mock_stdout.getvalue()
            parsed = json.loads(output)
            self.assertEqual(parsed["question"], "中国首都是哪里？")
            self.assertIn("A", parsed["answers"])
            self.assertEqual(parsed["matched_option_indices"], [0])


if __name__ == "__main__":
    unittest.main()
