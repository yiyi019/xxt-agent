# -*- coding: utf-8 -*-
import json
import tempfile
from pathlib import Path
import unittest

from xxt_agent.config import XXTConfig


class TestXXTConfig(unittest.TestCase):
    def test_default_config(self):
        cfg = XXTConfig()
        self.assertEqual(cfg.browser, "edge")
        self.assertTrue(cfg.headless)
        self.assertEqual(cfg.api_model, "deepseek-flash")
        self.assertTrue(cfg.pass_face)
        self.assertFalse(cfg.pass_video)

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "config.json"
            cfg = XXTConfig(
                phone_number="13800000000",
                password="testpassword",
                api_key="sk-testkey",
                speed=2.0,
                headless=False,
            )
            cfg.save(tmp_path)
            self.assertTrue(tmp_path.exists())

            loaded = XXTConfig.load(tmp_path)
            self.assertEqual(loaded.phone_number, "13800000000")
            self.assertEqual(loaded.password, "testpassword")
            self.assertEqual(loaded.api_key, "sk-testkey")
            self.assertEqual(loaded.speed, 2.0)
            self.assertFalse(loaded.headless)

    def test_to_dict(self):
        cfg = XXTConfig()
        d = cfg.to_dict()
        self.assertIn("api_model", d)
        self.assertIn("headless", d)
        self.assertIn("cookies_path", d)


if __name__ == "__main__":
    unittest.main()
