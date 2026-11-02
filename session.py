# -*- coding: utf-8 -*-
"""Session and authentication management for Xuexitong."""

import logging
import pickle
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from xxt_agent.config import XXTConfig
from xxt_agent.exceptions import AuthenticationError

logger = logging.getLogger(__name__)


class SessionManager:
    """Handles login, cookie persistence, and authentication status verification."""

    BASE_URL = "https://i.chaoxing.com"

    def __init__(self, driver, config: XXTConfig):
        self.driver = driver
        self.config = config
        self.cookies_path = Path(config.cookies_path)

    def load_cookies(self) -> bool:
        """Loads saved cookies into the browser session."""
        target_path = self.cookies_path
        # Fallback to legacy path if not in current data dir
        if not target_path.exists():
            legacy = Path(r"D:\Xuexitong_shuake\Xuexitong_shuake-master\task\tool\cookies.pkl")
            if legacy.exists():
                target_path = legacy

        if not target_path.exists():
            logger.info("No saved cookies file found")
            return False

        try:
            with open(target_path, "rb") as f:
                cookies = pickle.load(f)

            logger.info(f"Injecting {len(cookies)} cookies into session...")
            self.driver.get(self.BASE_URL)
            time.sleep(1)

            # Pass 1: add .chaoxing.com cookies
            for cookie in cookies:
                try:
                    c = cookie.copy()
                    if "sameSite" in c:
                        del c["sameSite"]
                    self.driver.add_cookie(c)
                except Exception:
                    pass

            # Navigate to base domain with active cookies
            self.driver.get(self.BASE_URL)
            time.sleep(2)

            # Pass 2: add i.chaoxing.com or sub-domain cookies
            for cookie in cookies:
                try:
                    c = cookie.copy()
                    if "sameSite" in c:
                        del c["sameSite"]
                    self.driver.add_cookie(c)
                except Exception:
                    pass

            self.driver.get(self.BASE_URL)
            time.sleep(2)
            return True
        except Exception as e:
            logger.warning(f"Failed to load cookies: {e}")
            return False

    def save_cookies(self) -> bool:
        """Saves current browser cookies to file."""
        try:
            self.cookies_path.parent.mkdir(parents=True, exist_ok=True)
            cookies = self.driver.get_cookies()
            with open(self.cookies_path, "wb") as f:
                pickle.dump(cookies, f)
            logger.info(f"Saved {len(cookies)} cookies to {self.cookies_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save cookies: {e}")
            return False

    def is_logged_in(self) -> Tuple[bool, Dict[str, Any]]:
        """Verifies whether the current browser session is authenticated."""
        try:
            title = self.driver.title or ""
            current_url = self.driver.current_url or ""

            if "用户登录" in title or "passport2.chaoxing.com" in current_url:
                return False, {}

            # Retrieve user information if possible
            profile: Dict[str, Any] = {}
            for cookie in self.driver.get_cookies():
                name = cookie.get("name")
                if name in ["_uid", "UID"]:
                    profile["uid"] = cookie.get("value")
                elif name == "uname":
                    profile["uname"] = cookie.get("value")

            # Try to grab name from page header if visible
            try:
                user_el = self.driver.find_elements("css selector", ".user-name, .userName, #userName")
                if user_el and user_el[0].text:
                    profile["display_name"] = user_el[0].text.strip()
            except Exception:
                pass

            is_valid = bool(profile.get("uid")) or ("个人空间" in title or "学习通" in title or "课程" in title)
            return is_valid, profile
        except Exception as e:
            logger.debug(f"Error checking login status: {e}")
            return False, {}

    def ensure_authenticated(self) -> Dict[str, Any]:
        """Ensures the browser has a valid authenticated session, using cookies or credentials."""
        # 1. Try saved cookies
        if self.load_cookies():
            logged_in, profile = self.is_logged_in()
            if logged_in:
                logger.info(f"Authenticated via cookies. Profile: {profile}")
                return profile

        # 2. Try credentials login if provided
        if self.config.phone_number and self.config.password:
            logger.info(f"Logging in with credentials ({self.config.phone_number})...")
            self.login_with_credentials(self.config.phone_number, self.config.password)
            logged_in, profile = self.is_logged_in()
            if logged_in:
                self.save_cookies()
                logger.info("Credentials login succeeded")
                return profile

        raise AuthenticationError("Could not authenticate with cookies or credentials. Manual login required.")

    def login_with_credentials(self, phone: str, password: str) -> None:
        """Performs form-based login using phone number and password."""
        self.driver.get("https://i.chaoxing.com/")
        time.sleep(2)

        try:
            phone_input = self.driver.find_element("id", "phone")
            pwd_input = self.driver.find_element("id", "pwd")
            login_btn = self.driver.find_element("id", "loginBtn")

            phone_input.clear()
            phone_input.send_keys(phone)
            time.sleep(0.5)

            pwd_input.clear()
            pwd_input.send_keys(password)
            time.sleep(0.5)

            login_btn.click()
            time.sleep(3)
        except Exception as e:
            raise AuthenticationError(f"Form login interaction failed: {e}") from e
