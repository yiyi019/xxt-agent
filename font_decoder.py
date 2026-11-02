# -*- coding: utf-8 -*-
"""Font decryption utility using FontTools for Xuexitong."""

import base64
import hashlib
import io
import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Dict, Optional
from xml.dom.minidom import parse

from fontTools.ttLib import TTFont

logger = logging.getLogger(__name__)


class FontDecoder:
    """In-memory font decrypter for Xuexitong custom obfuscated fonts."""

    def __init__(self, font_dict_path: Optional[str] = None):
        self.font_dict_path = Path(font_dict_path) if font_dict_path else (
            Path(__file__).resolve().parent / "data" / "font_dict.txt"
        )
        self._font_dict: Dict[str, int] = {}
        self._cache: Dict[str, Dict[int, str]] = {}
        self._load_font_dict()

    def _load_font_dict(self) -> None:
        """Loads the pre-computed contour MD5 -> unicode char code mapping."""
        # Fallback to legacy path if not in current data dir
        if not self.font_dict_path.exists():
            legacy = Path(r"D:\Xuexitong_shuake\Xuexitong_shuake-master\task\tool\font_dict.txt")
            if legacy.exists():
                self.font_dict_path = legacy

        if self.font_dict_path.exists():
            try:
                with open(self.font_dict_path, "r", encoding="utf-8") as f:
                    self._font_dict = json.load(f)
                logger.debug(f"Loaded font dict with {len(self._font_dict)} entries")
            except Exception as e:
                logger.warning(f"Failed to load font dictionary: {e}")
        else:
            logger.warning(f"Font dictionary file not found at: {self.font_dict_path}")

    def build_char_map(self, base64_ttf: str) -> Dict[int, str]:
        """
        Parses a base64-encoded TTF font completely in-memory, extracting glyph contour
        MD5 hashes and mapping obfuscated character ordinals to real unicode characters.
        """
        if not base64_ttf:
            return {}

        font_hash = hashlib.md5(base64_ttf.encode("utf-8")).hexdigest()
        if font_hash in self._cache:
            return self._cache[font_hash]

        char_map: Dict[int, str] = {}
        try:
            raw_ttf = base64.b64decode(base64_ttf)
            font = TTFont(io.BytesIO(raw_ttf))
            xml_buf = io.BytesIO()
            font.saveXML(xml_buf)
            xml_buf.seek(0)

            dom_tree = parse(xml_buf)
            root_node = dom_tree.documentElement
            ttglyph_list = root_node.getElementsByTagName("TTGlyph")

            for ttglyph in ttglyph_list:
                name = ttglyph.getAttribute("name")
                if not name or name == ".notdef":
                    continue

                code_match = re.findall(r"uni([0-9a-fA-F]+)", name)
                if not code_match:
                    continue

                code = int(code_match[0], 16)
                ttglyph_str = ""
                contour_list = ttglyph.getElementsByTagName("contour")
                for contour in contour_list:
                    ttglyph_str += contour.toxml()

                contour_md5 = hashlib.md5(ttglyph_str.encode("utf-8")).hexdigest()
                true_word_code = self._font_dict.get(contour_md5)
                if true_word_code is not None:
                    char_map[code] = unicodedata.normalize("NFKC", chr(true_word_code))

            self._cache[font_hash] = char_map
            logger.debug(f"Built font mapping with {len(char_map)} character substitutions")
        except Exception as e:
            logger.error(f"Error building font character map: {e}")

        return char_map

    def decode_text(self, text: str, char_map: Dict[int, str]) -> str:
        """Decodes an obfuscated text string using a character substitution map."""
        if not text or not char_map:
            return text

        result = []
        for ch in text:
            code = ord(ch)
            if code in char_map:
                result.append(char_map[code])
            else:
                result.append(ch)

        return "".join(result)

    @staticmethod
    def extract_font_base64_from_css(css_content: str) -> Optional[str]:
        """Extracts base64 TTF string from CSS @font-face rule, handling linebreaks and whitespace."""
        if not css_content:
            return None
        match = re.search(r";base64,([A-Za-z0-9+/=\s\r\n]+?)['\"\)]", css_content)
        if match:
            clean = re.sub(r"\s+", "", match.group(1))
            if clean:
                return clean
        match2 = re.search(r";base64,([A-Za-z0-9+/=]+)", css_content)
        if match2:
            return match2.group(1).strip()
        return None

    def extract_and_build_map_from_driver(self, driver) -> Dict[int, str]:
        """Extracts @font-face CSS from the current page/iframe in Selenium and builds char map."""
        try:
            style_elements = driver.find_elements("css selector", 'head style, head [type="text/css"], style')
            for el in style_elements:
                inner_html = el.get_attribute("innerHTML") or ""
                b64 = self.extract_font_base64_from_css(inner_html)
                if b64:
                    return self.build_char_map(b64)
        except Exception as e:
            logger.debug(f"Failed to extract font from driver: {e}")

        return {}
