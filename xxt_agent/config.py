# -*- coding: utf-8 -*-
"""Configuration manager for Xuexitong Agent."""

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


LEGACY_CONFIG_PATH = Path(__file__).resolve().parent.parent / "task" / "tool" / "account_info.json"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass
class XXTConfig:
    phone_number: str = ""
    password: str = ""
    api_key: str = ""
    api_model: str = "deepseek-v4.1-flash"
    api_base_url: str = "https://api.deepseek.com"
    browser: str = "edge"  # "edge" or "chrome"
    headless: bool = True
    driver_path: Optional[str] = None
    default_courses: List[str] = field(default_factory=lambda: ["音乐鉴赏"])
    speed: float = 1.0
    pass_face: bool = True
    pass_video: bool = False
    video_solve_mode: str = "ai"  # "ai", "random", "skip"
    quiz_solve_mode: str = "ai"   # "ai", "random", "skip"
    submit_threshold: float = 1.0  # 1.0 means 100%, <1.0 saves or submits depending on accuracy
    discussion_mode: str = "skip"  # "skip", "ai"
    multi_device_bypass: bool = True
    timeout: int = 60
    cookies_path: str = str(DATA_DIR / "cookies.pkl")
    font_dict_path: str = str(DATA_DIR / "font_dict.txt")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save(self, path: Optional[Path] = None) -> None:
        target_path = Path(path) if path else DEFAULT_CONFIG_PATH
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "XXTConfig":
        """Loads configuration from specified path, default path, or imports from legacy."""
        target_path = Path(path) if path else DEFAULT_CONFIG_PATH
        if not target_path.exists() and (Path(__file__).resolve().parent.parent / "config.json").exists():
            target_path = Path(__file__).resolve().parent.parent / "config.json"

        if target_path.exists():
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except Exception:
                pass

        # Try to import from legacy config if available
        cfg = cls()
        if LEGACY_CONFIG_PATH.exists():
            try:
                with open(LEGACY_CONFIG_PATH, "r", encoding="utf-8") as f:
                    legacy_data = json.load(f)
                cfg.phone_number = legacy_data.get("phone_number", "")
                cfg.password = legacy_data.get("password", "")
                cfg.api_key = legacy_data.get("API", "")
                cfg.default_courses = legacy_data.get("cour", ["音乐鉴赏"])
                cfg.pass_face = bool(legacy_data.get("pass_face", 1))
                cfg.pass_video = bool(legacy_data.get("pass_vido", 0))
                try:
                    cfg.speed = float(legacy_data.get("speed", 1))
                except (ValueError, TypeError):
                    cfg.speed = 1.0

                # Let Selenium Manager resolve driver by default unless explicitly configured
                cfg.driver_path = legacy_data.get("driver_path") if legacy_data.get("driver_path") and not legacy_data.get("driver_path", "").startswith("edgedriver") else None

                # Save imported configuration
                cfg.save(target_path)
            except Exception:
                pass

        return cfg
