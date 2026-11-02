# -*- coding: utf-8 -*-
"""
Browser manager for Xuexitong Agent.
Sets up lightweight, stealth Edge or Chrome WebDriver with optional headless support.
"""
import os
import shutil
from typing import Optional
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService

from .config import AgentConfig

def create_driver(config: AgentConfig, headless: Optional[bool] = None):
    """
    Instantiate and configure a WebDriver tailored for background agent automation.
    """
    is_headless = config.headless if headless is None else headless
    browser_type = config.browser.lower()

    if browser_type == "chrome":
        options = ChromeOptions()
        if is_headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--mute-audio")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        service = ChromeService(executable_path=config.driver_path) if config.driver_path and os.path.exists(config.driver_path) else ChromeService()
        driver = webdriver.Chrome(service=service, options=options)
    else:
        # Default: Edge
        options = EdgeOptions()
        if is_headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--mute-audio")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        service = EdgeService(executable_path=config.driver_path) if config.driver_path and os.path.exists(config.driver_path) else EdgeService()
        driver = webdriver.Edge(service=service, options=options)

    # Apply CDP stealth script
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.navigator.chrome = { runtime: {} };
                """
            }
        )
    except Exception:
        pass

    driver.set_page_load_timeout(30)
    driver.implicitly_wait(5)
    return driver

def close_driver(driver):
    """Safely quit driver instance."""
    if driver:
        try:
            driver.quit()
        except Exception:
            pass
