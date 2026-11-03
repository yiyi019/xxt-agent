# -*- coding: utf-8 -*-
"""Headless & clean browser automation manager for Xuexitong."""

import ctypes
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService

from xxt_agent.config import XXTConfig
from xxt_agent.exceptions import BrowserError

logger = logging.getLogger(__name__)


def set_keep_awake(enabled: bool = True) -> None:
    """Uses Windows Kernel32 SetThreadExecutionState to prevent PC sleep without GUI mouse moving."""
    if sys.platform != "win32":
        return
    try:
        if enabled:
            # ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001 | 0x00000002)
        else:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
    except Exception as e:
        logger.debug(f"SetThreadExecutionState error: {e}")


class BrowserManager:
    """Manages browser lifecycle, headless options, driver resolution and anti-detection."""

    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
    )

    ANTI_DETECTION_SCRIPT = """
    // Disable webdriver property
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

    // Override alert & confirm to prevent hanging headless executions
    window._originalConfirm = window.confirm;
    window.confirm = function(msg) {
        console.log('[xxt_agent] Auto-confirmed dialog:', msg);
        return true;
    };
    window._originalAlert = window.alert;
    window.alert = function(msg) {
        console.log('[xxt_agent] Auto-dismissed alert:', msg);
    };

    // Intercept detect.chaoxing.com monitoring scripts
    if (!window._originalAppendChild) {
        window._originalAppendChild = Element.prototype.appendChild;
        Element.prototype.appendChild = function() {
            try {
                if (arguments[0].src && arguments[0].src.indexOf('detect.chaoxing.com') > 0) {
                    console.log('[xxt_agent] Blocked monitoring script:', arguments[0].src);
                    return;
                }
            } catch (e) {}
            return window._originalAppendChild.apply(this, arguments);
        };
    }

    // Auto Play Video Blocker (reference project content.js reproduction)
    window.addEventListener('mouseout', function(e) {
        e.stopPropagation();
        e.preventDefault();
    }, true);

    if (window.ananas && window.ananas.pause) {
        window.ananas.pause = function () {
            console.log('[xxt_agent] ananas pause blocked');
        };
    }

    setInterval(function() {
        var v = document.querySelector('video');
        if (v) {
            if (!v._pause_blocked) {
                v._pause_blocked = true;
                v.pause = function() {
                    console.log('[xxt_agent] Video.pause blocked');
                };
            }
            if (v.paused) {
                v.muted = true;
                v.play().catch(function(){});
            }
        }
    }, 500);
    """

    @classmethod
    def create_driver(cls, config: XXTConfig) -> webdriver.Remote:
        """Creates and configures a Selenium WebDriver instance based on configuration."""
        browser_type = config.browser.lower()
        headless = config.headless

        driver_path = config.driver_path
        if driver_path and not Path(driver_path).exists():
            logger.warning(f"Configured driver_path {driver_path} not found; letting Selenium Manager resolve driver")
            driver_path = None

        set_keep_awake(True)

        try:
            if browser_type == "chrome":
                return cls._create_chrome_driver(driver_path, headless)
            else:
                return cls._create_edge_driver(driver_path, headless)
        except Exception as e:
            logger.error(f"Failed to create {browser_type} driver: {e}")
            # If specified path failed, retry letting Selenium Manager resolve
            if driver_path:
                logger.info("Retrying driver creation with automatic Selenium Manager resolution...")
                try:
                    if browser_type == "chrome":
                        return cls._create_chrome_driver(None, headless)
                    else:
                        return cls._create_edge_driver(None, headless)
                except Exception as e2:
                    raise BrowserError(f"Driver initialization failed: {e2}") from e2
            raise BrowserError(f"Driver initialization failed: {e}") from e

    @classmethod
    def _create_edge_driver(cls, driver_path: Optional[str], headless: bool) -> webdriver.Edge:
        options = EdgeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(f"user-agent={cls.DEFAULT_USER_AGENT}")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        ext_path = Path(__file__).parent / "extensions" / "chrome-extension.crx"
        if ext_path.exists() and not headless:
            try:
                options.add_extension(str(ext_path))
            except Exception as e:
                logger.debug(f"Could not load chrome-extension.crx: {e}")

        service = EdgeService(executable_path=driver_path) if driver_path else EdgeService()
        driver = webdriver.Edge(service=service, options=options)
        cls._inject_cdp_scripts(driver)
        driver.implicitly_wait(3)
        return driver

    @classmethod
    def _create_chrome_driver(cls, driver_path: Optional[str], headless: bool) -> webdriver.Chrome:
        options = ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument(f"user-agent={cls.DEFAULT_USER_AGENT}")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        ext_path = Path(__file__).parent / "extensions" / "chrome-extension.crx"
        if ext_path.exists() and not headless:
            try:
                options.add_extension(str(ext_path))
            except Exception as e:
                logger.debug(f"Could not load chrome-extension.crx: {e}")

        service = ChromeService(executable_path=driver_path) if driver_path else ChromeService()
        driver = webdriver.Chrome(service=service, options=options)
        cls._inject_cdp_scripts(driver)
        driver.implicitly_wait(3)
        return driver

    @classmethod
    def _inject_cdp_scripts(cls, driver) -> None:
        """Injects anti-detection and popup-suppression scripts via Chrome DevTools Protocol."""
        try:
            driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": cls.ANTI_DETECTION_SCRIPT},
            )
        except Exception as e:
            logger.debug(f"CDP script injection warning: {e}")
