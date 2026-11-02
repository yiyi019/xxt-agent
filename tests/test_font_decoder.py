# -*- coding: utf-8 -*-
import unittest
from pathlib import Path
from xxt_agent.font_decoder import FontDecoder


class TestFontDecoder(unittest.TestCase):
    def setUp(self):
        self.decoder = FontDecoder()

    def test_font_dict_loaded(self):
        self.assertGreater(len(self.decoder._font_dict), 1000)

    def test_decode_unmapped_text(self):
        text = "标准中文测试123"
        decoded = self.decoder.decode_text(text, {})
        self.assertEqual(decoded, text)

    def test_decode_with_char_map(self):
        # Simulate mapped char
        char_map = {ord("A"): "乙", ord("B"): "甲"}
        text = "选择A还是B"
        decoded = self.decoder.decode_text(text, char_map)
        self.assertEqual(decoded, "选择乙还是甲")

    def test_extract_base64_from_css(self):
        css = """
        @font-face {
            font-family: 'cxsecret';
            src: url('data:application/font-ttf;charset=utf-8;base64,AAEAAAASAQA12345') format('truetype');
        }
        """
        b64 = self.decoder.extract_font_base64_from_css(css)
        self.assertEqual(b64, "AAEAAAASAQA12345")

    def test_empty_input(self):
        self.assertEqual(self.decoder.decode_text("", {}), "")
        self.assertEqual(self.decoder.build_char_map(""), {})


if __name__ == "__main__":
    unittest.main()
