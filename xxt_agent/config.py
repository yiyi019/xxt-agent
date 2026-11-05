# -*- coding: utf-8 -*-
"""Configuration manager for Xuexitong Agent."""

import json
import os
import shutil
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


PACKAGE_DIR = Path(__file__).resolve().parent


def _resolve_home_dir() -> Path:
    """User-level directory for config, cookies and runtime state.

    Override with the XXT_AGENT_HOME environment variable.
    """
    env = os.environ.get("XXT_AGENT_HOME")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".config" / "xxt-agent"


CONFIG_DIR = _resolve_home_dir()
DEFAULT_CONFIG_PATH = CONFIG_DIR / "config.json"
DATA_DIR = CONFIG_DIR / "data"  # cookies, debug dumps (user data, never packaged)
STATUS_FILE_PATH = CONFIG_DIR / "live_status.json"
RESOURCE_DIR = PACKAGE_DIR / "data"  # read-only resources bundled with the package (font_dict.txt)

# Locations used by earlier versions; still read once and migrated to CONFIG_DIR.
LEGACY_CONFIG_PATH = PACKAGE_DIR.parent / "task" / "tool" / "account_info.json"
LEGACY_LOCATIONS = [
    PACKAGE_DIR / "config.json",
    PACKAGE_DIR.parent / "config.json",
]
LEGACY_COOKIES_PATH = PACKAGE_DIR / "data" / "cookies.pkl"


@dataclass
class XXTConfig:
    phone_number: str = ""
    password: str = ""
    api_key: str = ""
    api_model: str = "deepseek-flash"
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
    font_dict_path: str = str(RESOURCE_DIR / "font_dict.txt")

    def _normalize_paths(self, migrated: bool) -> None:
        """Repairs path fields saved by older versions (they pointed inside the package dir)."""
        if not Path(self.font_dict_path).exists():
            self.font_dict_path = str(RESOURCE_DIR / "font_dict.txt")
        if migrated:
            try:
                inside_package = PACKAGE_DIR.resolve() in Path(self.cookies_path).resolve().parents
            except OSError:
                inside_package = False
            if inside_package:
                self.cookies_path = str(DATA_DIR / "cookies.pkl")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save(self, path: Optional[Path] = None) -> None:
        target_path = Path(path) if path else DEFAULT_CONFIG_PATH
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        try:
            os.chmod(target_path, 0o600)  # file holds plaintext credentials
        except OSError:
            pass

    @staticmethod
    def _migrate_legacy_files() -> Optional[Path]:
        """Copies a config/cookies file from an old location into CONFIG_DIR.

        Old files are left untouched. Returns the old config path that was migrated, if any.
        """
        migrated = None
        for old in LEGACY_LOCATIONS:
            if old.exists():
                try:
                    DEFAULT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(old, DEFAULT_CONFIG_PATH)
                    migrated = old
                except OSError:
                    return None
                break
        new_cookies = DATA_DIR / "cookies.pkl"
        if LEGACY_COOKIES_PATH.exists() and not new_cookies.exists():
            try:
                DATA_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copy2(LEGACY_COOKIES_PATH, new_cookies)
            except OSError:
                pass
        return migrated

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "XXTConfig":
        """Loads configuration from an explicit path or CONFIG_DIR (migrating old locations once)."""
        if path:
            target_path = Path(path)
        else:
            target_path = DEFAULT_CONFIG_PATH
            if not target_path.exists():
                cls._migrate_legacy_files()

        if target_path.exists():
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cfg = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
                cfg._normalize_paths(migrated=path is None)
                return cfg
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
