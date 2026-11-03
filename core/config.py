# -*- coding: utf-8 -*-
"""
Configuration manager for Xuexitong Agent.
Resolves configuration from CLI arguments, environment variables, and config.json.
"""
import os
import json
from dataclasses import dataclass, field
from typing import Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DEFAULT_CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
DEFAULT_COOKIES_PATH = os.path.join(DATA_DIR, "cookies.pkl")
DEFAULT_FONT_DICT_PATH = os.path.join(DATA_DIR, "font_dict.txt")

@dataclass
class AgentConfig:
    phone: str = ""
    password: str = ""
    driver_path: str = ""
    browser: str = "edge"
    headless: bool = True
    speed: float = 2.0
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-v4.1-flash"
    auto_dismiss_face: bool = True
    bypass_monitor: bool = True
    cookies_path: str = DEFAULT_COOKIES_PATH
    font_dict_path: str = DEFAULT_FONT_DICT_PATH
    data_dir: str = DATA_DIR

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "AgentConfig":
        cfg = cls()
        path = config_path or DEFAULT_CONFIG_PATH
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for k, v in data.items():
                    if hasattr(cfg, k):
                        setattr(cfg, k, v)
            except Exception:
                pass

        # Environment variable overrides
        if os.getenv("XXT_PHONE"):
            cfg.phone = os.getenv("XXT_PHONE")
        if os.getenv("XXT_PASSWORD"):
            cfg.password = os.getenv("XXT_PASSWORD")
        if os.getenv("XXT_DEEPSEEK_KEY"):
            cfg.deepseek_api_key = os.getenv("XXT_DEEPSEEK_KEY")
        if os.getenv("XXT_HEADLESS"):
            cfg.headless = os.getenv("XXT_HEADLESS").lower() in ("1", "true", "yes")
        if os.getenv("XXT_SPEED"):
            try:
                cfg.speed = float(os.getenv("XXT_SPEED"))
            except ValueError:
                pass

        # Driver path fallback resolution
        if not cfg.driver_path or not os.path.exists(cfg.driver_path):
            candidates = [
                os.path.join(BASE_DIR, "..", "edgedriver_win64", "msedgedriver.exe"),
                os.path.join(BASE_DIR, "..", "chromedriver_win64", "chromedriver.exe"),
            ]
            for cand in candidates:
                cand_abs = os.path.abspath(cand)
                if os.path.exists(cand_abs):
                    cfg.driver_path = cand_abs
                    break

        return cfg

    def save(self, config_path: Optional[str] = None):
        path = config_path or DEFAULT_CONFIG_PATH
        data = {
            "phone": self.phone,
            "password": self.password,
            "driver_path": self.driver_path,
            "browser": self.browser,
            "headless": self.headless,
            "speed": self.speed,
            "deepseek_api_key": self.deepseek_api_key,
            "deepseek_model": self.deepseek_model,
            "auto_dismiss_face": self.auto_dismiss_face,
            "bypass_monitor": self.bypass_monitor
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
