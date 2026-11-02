# -*- coding: utf-8 -*-
"""
Font Decoder for Xuexitong custom obfuscated web fonts.
Maps encoded glyphs to authentic Chinese characters using fontTools and glyph contours MD5.
"""
import io
import re
import os
import json
import base64
import hashlib
import unicodedata
from xml.dom.minidom import parseString
from fontTools.ttLib import TTFont
from selenium.webdriver.common.by import By

class FontDecoder:
    def __init__(self, font_dict_path: str = ""):
        if not font_dict_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            font_dict_path = os.path.join(base_dir, "data", "font_dict.txt")
        self.font_dict_path = font_dict_path
        self._font_dict = {}
        self._secret_dict = {}
        self._load_font_dict()

    def _load_font_dict(self):
        if os.path.exists(self.font_dict_path):
            try:
                with open(self.font_dict_path, "r", encoding="utf-8") as f:
                    self._font_dict = json.load(f)
            except Exception:
                self._font_dict = {}

    def parse_page_font(self, driver) -> bool:
        """Extract and parse @font_face from the current page."""
        try:
            head = driver.find_element(By.TAG_NAME, "head")
            css_elements = head.find_elements(By.CSS_SELECTOR, '[type="text/css"]')
            font_b64 = None
            for elem in css_elements:
                html = elem.get_attribute("innerHTML") or ""
                matches = re.findall(r";base64,(.*?)'[)]\s*format", html)
                if matches:
                    font_b64 = matches[0]
                    break
            if not font_b64:
                return False

            font_bytes = base64.b64decode(font_b64)
            font = TTFont(io.BytesIO(font_bytes))
            xml_stream = io.StringIO()
            font.saveXML(xml_stream)
            xml_str = xml_stream.getvalue()

            dom = parseString(xml_str)
            root = dom.documentElement
            glyphs = root.getElementsByTagName("TTGlyph")
            new_secret = {}
            for g in glyphs:
                name = g.getAttribute("name")
                if name == ".notdef" or not name.startswith("uni"):
                    continue
                try:
                    code = int(name[3:], 16)
                except ValueError:
                    continue
                contours = g.getElementsByTagName("contour")
                contour_str = "".join(c.toxml() for c in contours)
                md5_val = hashlib.md5(contour_str.encode("utf-8")).hexdigest()
                new_secret[code] = md5_val

            self._secret_dict = new_secret
            return True
        except Exception:
            return False

    def decode(self, text: str) -> str:
        """Decode obfuscated string into standard text."""
        if not text or not self._font_dict or not self._secret_dict:
            return text
        result = []
        for ch in text:
            code = ord(ch)
            glyph_md5 = self._secret_dict.get(code)
            if glyph_md5 and glyph_md5 in self._font_dict:
                true_char = chr(self._font_dict[glyph_md5])
                result.append(unicodedata.normalize('NFKC', true_char))
            else:
                result.append(ch)
        return "".join(result)
