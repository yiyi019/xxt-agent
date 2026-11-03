# -*- coding: utf-8 -*-
"""
Authentication and session persistence for Xuexitong Agent.
Manages cookie storage, session restoration, and credential login.
"""
import os
import time
import pickle
from typing import Dict, Any, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .config import AgentConfig

LOGIN_URL = "https://i.chaoxing.com/"
DASHBOARD_INDICATORS = [
    "//div[contains(@class, 'user-info')]",
    "//div[contains(@class, 'nav')]",
    "//ul[contains(@class, 'nav')]",
    "//a[contains(text(), '退出')]",
    "//a[contains(@href, 'logout')]"
]

def check_login_status(driver) -> bool:
    """Check if the driver is currently authenticated."""
    current_url = driver.current_url.lower()
    if "passport2" in current_url or "login" in current_url:
        return False
    for xpath in DASHBOARD_INDICATORS:
        try:
            elem = driver.find_elements(By.XPATH, xpath)
            if elem:
                return True
        except Exception:
            pass
    # If URL is i.chaoxing.com/base or contains space
    return "i.chaoxing.com/base" in current_url or "space" in current_url

def save_cookies(driver, cookies_path: str) -> bool:
    """Save session cookies to disk."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(cookies_path)), exist_ok=True)
        cookies = driver.get_cookies()
        with open(cookies_path, "wb") as f:
            pickle.dump(cookies, f)
        return True
    except Exception:
        return False

def login_with_cookies(driver, cookies_path: str) -> bool:
    """Attempt authentication via saved cookies."""
    if not os.path.exists(cookies_path):
        return False

    try:
        driver.get(LOGIN_URL)
        time.sleep(1)
        with open(cookies_path, "rb") as f:
            cookies = pickle.load(f)

        for cookie in cookies:
            # Avoid domain mismatch issues
            c = dict(cookie)
            if "domain" in c and "chaoxing.com" not in c["domain"]:
                continue
            try:
                driver.add_cookie(c)
            except Exception:
                pass

        driver.get("https://i.chaoxing.com/base")
        time.sleep(2)
        return check_login_status(driver)
    except Exception:
        return False

def login_with_credentials(driver, phone: str, password: str, cookies_path: Optional[str] = None) -> Dict[str, Any]:
    """Perform automated credential-based login."""
    if not phone or not password:
        return {"ok": False, "error": "Phone number or password not provided."}

    try:
        driver.get(LOGIN_URL)
        time.sleep(2)

        # Select phone/account login tab if tab exists
        try:
            tabs = driver.find_elements(By.XPATH, "//a[contains(text(), '验证码登录') or contains(text(), '密码登录') or contains(text(), '账号登录')]")
            for tab in tabs:
                if "密码" in tab.text or "账号" in tab.text:
                    tab.click()
                    time.sleep(0.5)
                    break
        except Exception:
            pass

        # Locate phone & password inputs
        phone_input = None
        for sel in ["#phone", "input[name='uname']", "input[type='text']", "#uname"]:
            try:
                elem = driver.find_element(By.CSS_SELECTOR, sel)
                if elem.is_displayed():
                    phone_input = elem
                    break
            except Exception:
                pass

        pwd_input = None
        for sel in ["#pwd", "input[name='password']", "input[type='password']"]:
            try:
                elem = driver.find_element(By.CSS_SELECTOR, sel)
                if elem.is_displayed():
                    pwd_input = elem
                    break
            except Exception:
                pass

        if not phone_input or not pwd_input:
            return {"ok": False, "error": "Could not locate login form inputs on page."}

        phone_input.clear()
        phone_input.send_keys(phone)
        time.sleep(0.3)
        pwd_input.clear()
        pwd_input.send_keys(password)
        time.sleep(0.3)

        # Click login button
        login_btn = None
        for sel in ["#loginBtn", "button[type='submit']", ".btn-big", "#submitBtn"]:
            try:
                elem = driver.find_element(By.CSS_SELECTOR, sel)
                if elem.is_displayed():
                    login_btn = elem
                    break
            except Exception:
                pass

        if login_btn:
            login_btn.click()
        else:
            pwd_input.submit()

        # Wait for redirect
        time.sleep(3)
        if check_login_status(driver):
            if cookies_path:
                save_cookies(driver, cookies_path)
            return {"ok": True, "message": "Login successful."}
        else:
            return {"ok": False, "error": "Login failed (check credentials or captcha challenge)."}

    except Exception as e:
        return {"ok": False, "error": f"Login exception: {str(e)}"}

def ensure_authenticated(driver, config: AgentConfig) -> Dict[str, Any]:
    """
    Ensure the driver is logged in:
    1. Try cookie login first.
    2. If invalid, try credential login.
    """
    if config.cookies_path and login_with_cookies(driver, config.cookies_path):
        return {"ok": True, "method": "cookies", "message": "Authenticated via saved cookies."}

    if config.phone and config.password:
        res = login_with_credentials(driver, config.phone, config.password, config.cookies_path)
        if res.get("ok"):
            res["method"] = "credentials"
            return res
        return res

    return {
        "ok": False,
        "error": "No valid cookies found and no credentials provided in config."
    }
