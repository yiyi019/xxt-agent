# -*- coding: utf-8 -*-
"""Handlers for supplementary course materials (PPT, Reading, Audio, Discussion)."""

import logging
import time
from typing import Callable, Optional

from selenium.webdriver.common.by import By

from xxt_agent.ai_solver import DeepSeekSolver
from xxt_agent.models import RunEvent

logger = logging.getLogger(__name__)


class PPTHandler:
    """Automates viewing PPT and PDF slide attachments."""

    def __init__(self, driver, event_callback: Optional[Callable[[RunEvent], None]] = None):
        self.driver = driver
        self.event_callback = event_callback or (lambda e: None)

    def process(self, course_name: str) -> int:
        self.driver.switch_to.default_content()
        try:
            self.driver.switch_to.frame("iframe")
        except Exception:
            return 0

        ppt_iframes = self.driver.find_elements(
            By.CSS_SELECTOR,
            '[class*="insertdoc-online-ppt"], [class*="insertdoc-online-pdf"]'
        )
        if not ppt_iframes:
            return 0

        logger.info(f"Found {len(ppt_iframes)} PPT/PDF attachment(s)")
        count = 0
        for idx, iframe in enumerate(ppt_iframes):
            try:
                self.driver.switch_to.default_content()
                self.driver.switch_to.frame("iframe")
                self.driver.switch_to.frame(iframe)

                pan_view = self.driver.find_element(By.ID, "panView")
                self.driver.switch_to.frame(pan_view)

                slides = self.driver.find_elements(By.TAG_NAME, "li")
                logger.info(f"Scrolling through {len(slides)} PPT slides...")
                for _ in range(min(len(slides), 30)):
                    self.driver.execute_script("window.scrollBy(0, 1500);")
                    time.sleep(0.3)

                time.sleep(1)
                count += 1
                self.event_callback(RunEvent(event_type="ppt_finished", data={"index": idx + 1, "slides": len(slides)}))
            except Exception as e:
                logger.debug(f"PPT handling error: {e}")

        return count


class ReadingHandler:
    """Automates reading document tasks."""

    def __init__(self, driver, event_callback: Optional[Callable[[RunEvent], None]] = None):
        self.driver = driver
        self.event_callback = event_callback or (lambda e: None)

    def process(self, course_name: str) -> int:
        self.driver.switch_to.default_content()
        try:
            self.driver.switch_to.frame("iframe")
        except Exception:
            return 0

        read_iframes = self.driver.find_elements(
            By.CSS_SELECTOR,
            '[class*="ans-book"], [src*="/ananas/modules/read/"]'
        )
        if not read_iframes:
            return 0

        logger.info(f"Found {len(read_iframes)} Reading attachment(s)")
        count = 0
        for idx, iframe in enumerate(read_iframes):
            try:
                self.driver.switch_to.default_content()
                self.driver.switch_to.frame("iframe")
                self.driver.switch_to.frame(iframe)

                # Check for bookiframe
                try:
                    book_frame = self.driver.find_element(By.NAME, "bookifame")
                    self.driver.switch_to.frame(book_frame)
                    read_web = self.driver.find_element(By.ID, "Readweb")
                    for i in range(1, 11):
                        self.driver.execute_script(
                            "arguments[0].scrollTo(0, arguments[0].scrollHeight * arguments[1]);",
                            read_web,
                            i / 10,
                        )
                        time.sleep(0.5)
                except Exception:
                    # Alternative reader
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(3)

                count += 1
                self.event_callback(RunEvent(event_type="reading_finished", data={"index": idx + 1}))
            except Exception as e:
                logger.debug(f"Reading handling error: {e}")

        return count


class AudioHandler:
    """Automates listening to audio tasks."""

    def __init__(self, driver, event_callback: Optional[Callable[[RunEvent], None]] = None):
        self.driver = driver
        self.event_callback = event_callback or (lambda e: None)

    def process(self, course_name: str) -> int:
        self.driver.switch_to.default_content()
        try:
            self.driver.switch_to.frame("iframe")
        except Exception:
            return 0

        audio_iframes = self.driver.find_elements(By.CSS_SELECTOR, '[class*="ans-insertaudio"]')
        if not audio_iframes:
            return 0

        logger.info(f"Found {len(audio_iframes)} Audio attachment(s)")
        count = 0
        for idx, iframe in enumerate(audio_iframes):
            try:
                self.driver.switch_to.default_content()
                self.driver.switch_to.frame("iframe")
                self.driver.switch_to.frame(iframe)

                play_btn = self.driver.find_element(By.CSS_SELECTOR, ".vjs-play-control")
                play_btn.click()
                time.sleep(1)

                # Try fast forwarding
                try:
                    ff_btn = self.driver.find_element(By.ID, "vjs-fast-forward-button")
                    for _ in range(10):
                        ff_btn.click()
                        time.sleep(0.1)
                except Exception:
                    pass

                time.sleep(2)
                count += 1
                self.event_callback(RunEvent(event_type="audio_finished", data={"index": idx + 1}))
            except Exception as e:
                logger.debug(f"Audio handling error: {e}")

        return count


class DiscussionHandler:
    """Handles course discussion tasks."""

    def __init__(
        self,
        driver,
        solver: Optional[DeepSeekSolver] = None,
        mode: str = "skip",
        event_callback: Optional[Callable[[RunEvent], None]] = None,
    ):
        self.driver = driver
        self.solver = solver
        self.mode = mode
        self.event_callback = event_callback or (lambda e: None)

    def process(self, course_name: str) -> int:
        if self.mode == "skip":
            logger.info("Discussion mode set to 'skip'; skipping discussion")
            return 0

        self.driver.switch_to.default_content()
        try:
            self.driver.switch_to.frame("iframe")
        except Exception:
            return 0

        bbs_iframes = self.driver.find_elements(By.CSS_SELECTOR, '[src*="/ananas/modules/insertbbs/"]')
        if not bbs_iframes:
            return 0

        count = 0
        for idx, iframe in enumerate(bbs_iframes):
            try:
                self.driver.switch_to.default_content()
                self.driver.switch_to.frame("iframe")
                self.driver.switch_to.frame(iframe)

                # Retrieve topic question
                topic_title = self.driver.find_element(By.CLASS_NAME, "topicDetail_title").text
                reply_input = self.driver.find_element(By.CSS_SELECTOR, ".textareawrap textarea")
                reply_btn = self.driver.find_element(By.CSS_SELECTOR, ".addReply")

                reply_text = "了解并学习了相关知识点，受益匪浅。"
                if self.solver:
                    answers = self.solver.solve_single(topic_title, [], "简答题")
                    if answers:
                        reply_text = answers[0]

                reply_input.click()
                reply_input.send_keys(reply_text)
                time.sleep(0.5)
                reply_btn.click()
                time.sleep(1)
                count += 1
                self.event_callback(RunEvent(event_type="discussion_replied", data={"index": idx + 1, "reply": reply_text}))
            except Exception as e:
                logger.debug(f"Discussion handling error: {e}")

        return count
