# -*- coding: utf-8 -*-
"""Course progression orchestrator for Xuexitong."""

import datetime
import logging
import re
import time
from typing import Callable, List, Optional

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
)
from selenium.webdriver.common.by import By

from xxt_agent.ai_solver import DeepSeekSolver
from xxt_agent.config import XXTConfig
from xxt_agent.content_handlers import AudioHandler, DiscussionHandler, PPTHandler, ReadingHandler
from xxt_agent.exceptions import CourseNotFoundError
from xxt_agent.face_bypass import FaceBypass
from xxt_agent.font_decoder import FontDecoder
from xxt_agent.models import CourseInfo, CourseRunSummary, RunEvent
from xxt_agent.quiz_runner import QuizRunner
from xxt_agent.session import SessionManager
from xxt_agent.video_runner import VideoRunner

logger = logging.getLogger(__name__)


class CourseRunner:
    """Orchestrates course selection, chapter navigation, and delegated task execution."""

    def __init__(
        self,
        driver,
        config: XXTConfig,
        solver: Optional[DeepSeekSolver] = None,
        event_callback: Optional[Callable[[RunEvent], None]] = None,
    ):
        self.driver = driver
        self.config = config
        self.event_callback = event_callback or (lambda e: None)
        self.session_manager = SessionManager(driver, config)
        self.font_decoder = FontDecoder(config.font_dict_path)
        self.solver = solver or DeepSeekSolver(
            api_key=config.api_key,
            primary_model=config.api_model,
            base_url=config.api_base_url,
        )
        self.face_bypass = FaceBypass(driver)

        # Handlers
        self.video_runner = VideoRunner(
            driver=driver,
            solver=self.solver,
            font_decoder=self.font_decoder,
            face_bypass=self.face_bypass,
            speed=config.speed,
            pass_video=config.pass_video,
            video_solve_mode=config.video_solve_mode,
            event_callback=self._emit,
        )
        self.quiz_runner = QuizRunner(
            driver=driver,
            solver=self.solver,
            font_decoder=self.font_decoder,
            submit_threshold=config.submit_threshold,
            event_callback=self._emit,
        )
        self.ppt_handler = PPTHandler(driver, self._emit)
        self.reading_handler = ReadingHandler(driver, self._emit)
        self.audio_handler = AudioHandler(driver, self._emit)
        self.discussion_handler = DiscussionHandler(
            driver=driver,
            solver=self.solver,
            mode=config.discussion_mode,
            event_callback=self._emit,
        )

    def _emit(self, event: RunEvent) -> None:
        try:
            self.event_callback(event)
        except Exception as e:
            logger.debug(f"Event emission error: {e}")

    def list_courses(self) -> List[CourseInfo]:
        """Fetches the list of active courses available in the user account."""
        self.session_manager.ensure_authenticated()
        self.driver.get("https://i.chaoxing.com/")
        time.sleep(2)

        # Navigate to Courses tab
        self._navigate_to_course_list_tab()

        courses: List[CourseInfo] = []
        try:
            course_elements = self.driver.find_elements(By.CLASS_NAME, "course-name")
            if not course_elements:
                course_elements = self.driver.find_elements(By.CLASS_NAME, "courseName")
            if not course_elements:
                course_elements = self.driver.find_elements(By.CSS_SELECTOR, '[class*="w_cour_txtH"]')

            for el in course_elements:
                title = el.get_attribute("title") or el.text.strip()
                if title:
                    courses.append(CourseInfo(name=title))

            logger.info(f"Found {len(courses)} course(s)")
        except Exception as e:
            logger.error(f"Error reading course list: {e}")

        return courses

    def _navigate_to_course_list_tab(self) -> None:
        """Navigates the personal space page to the 'My Courses' tab."""
        try:
            tabs = self.driver.find_elements(By.CSS_SELECTOR, '[title*="课程"], [title="新泛雅"]')
            if tabs:
                tabs[0].click()
                time.sleep(1)
        except Exception:
            pass

        try:
            self.driver.switch_to.frame("frame_content")
            tab_divs = self.driver.find_elements(By.CSS_SELECTOR, ".course-tab div")
            for div in tab_divs:
                if "我学" in div.text:
                    div.click()
                    time.sleep(1)
                    break
        except Exception:
            pass

    def select_course(self, course_name: str) -> bool:
        """Finds and clicks into a specified course by name."""
        self.session_manager.ensure_authenticated()
        self.driver.get("https://i.chaoxing.com/")
        time.sleep(2)
        self._navigate_to_course_list_tab()

        course_elements = self.driver.find_elements(By.CLASS_NAME, "course-name")
        if not course_elements:
            course_elements = self.driver.find_elements(By.CLASS_NAME, "courseName")
        if not course_elements:
            course_elements = self.driver.find_elements(By.CSS_SELECTOR, '[class*="w_cour_txtH"]')

        orig_handles = list(self.driver.window_handles)
        for el in course_elements:
            title = el.get_attribute("title") or el.text.strip()
            if course_name in title:
                logger.info(f"Found target course: {title}")
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                time.sleep(0.5)
                self.driver.execute_script("arguments[0].click();", el)
                time.sleep(3)

                new_handles = [h for h in self.driver.window_handles if h not in orig_handles]
                if new_handles:
                    self.driver.switch_to.window(new_handles[-1])
                else:
                    self._switch_to_window(course_name)

                time.sleep(2)
                # Check if course entry face verification popup appears
                if self.config.pass_face and self.face_bypass.is_popup_present():
                    logger.info("Face verification popup present on course entry page; executing bypass...")
                    self.face_bypass.bypass()
                    time.sleep(3)

                return True

        raise CourseNotFoundError(course_name)

    def get_chapters(self, course_name: str) -> List[dict]:
        """Inspects and returns the chapter list for a given course."""
        self.select_course(course_name)
        time.sleep(2)
        try:
            navs = self.driver.find_elements(By.CLASS_NAME, "nav_content")
            if not navs:
                navs = self.driver.find_elements(By.CSS_SELECTOR, "li[data-nav-name='章节']")
            for nav in navs:
                if "章节" in nav.text:
                    nav.click()
                    time.sleep(1)
                    break
        except Exception:
            pass

        self.driver.switch_to.default_content()
        frames = self.driver.find_elements(By.TAG_NAME, "iframe")
        for f in frames:
            try:
                src = f.get_attribute("src") or ""
                if "courselist" in src or "catalog" in src or "work" in src:
                    self.driver.switch_to.frame(f)
                    break
            except Exception:
                pass

        chapters = []
        nodes = self.driver.find_elements(By.CSS_SELECTOR, ".posCatalog_name, .catalog_name, .level_two")
        for idx, n in enumerate(nodes):
            t = n.get_attribute("title") or n.text.strip()
            if t:
                try:
                    parent = n.find_element(By.XPATH, "..")
                    parent_html = parent.get_attribute("innerHTML") or ""
                except Exception:
                    parent_html = ""
                has_mission = "catalog_tishi" in parent_html or "ans-job-icon" in parent_html
                completed = "icon_complete" in parent_html or ("catalog_tishi" not in parent_html and "ans-job-icon-clear" not in parent_html)
                chapters.append({
                    "index": idx + 1,
                    "title": t,
                    "has_mission": has_mission,
                    "completed": completed
                })
        self.driver.switch_to.default_content()
        return chapters

    def find_and_enter_mission_point(self, course_name: str) -> bool:
        """Locates the first unfinished chapter mission point and opens it."""
        try:
            # Click experience if present
            exp_btn = self.driver.find_elements(By.CLASS_NAME, "experience")
            if exp_btn:
                exp_btn[0].click()
                time.sleep(1)
        except Exception:
            pass

        # Switch to chapter nav
        try:
            navs = self.driver.find_elements(By.CLASS_NAME, "nav_content")
            if not navs:
                navs = self.driver.find_elements(By.CSS_SELECTOR, "li[data-nav-name='章节']")
            for nav in navs:
                if "章节" in nav.text:
                    nav.click()
                    time.sleep(1)
                    break
        except Exception:
            pass

        # Search for unfinished task indicators (.catalog_tishi120)
        self.driver.switch_to.default_content()
        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        target_marker = None

        for iframe in iframes:
            try:
                self.driver.switch_to.frame(iframe)
                markers = self.driver.find_elements(By.CSS_SELECTOR, ".catalog_tishi120")
                if markers:
                    target_marker = markers[0]
                    break
            except Exception:
                self.driver.switch_to.default_content()
                continue

        if not target_marker:
            logger.info("No unfinished mission points (.catalog_tishi120) found in chapter tree")
            return False

        logger.info("Found unfinished chapter mission point; entering...")
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_marker)
        time.sleep(0.5)
        self.driver.execute_script("arguments[0].click();", target_marker)
        time.sleep(2)
        return True

    def run_course(self, course_name: str, max_chapters: Optional[int] = None) -> CourseRunSummary:
        """Runs automated progression through course chapters."""
        start_time = datetime.datetime.now().isoformat()
        logger.info(f"Initiating automated run for course: {course_name}")
        self._emit(RunEvent(event_type="course_run_start", data={"course": course_name}))

        summary = CourseRunSummary(
            course_name=course_name,
            start_time=start_time,
            end_time="",
        )

        try:
            self.select_course(course_name)
            has_mission = self.find_and_enter_mission_point(course_name)
            if not has_mission:
                logger.info(f"Course '{course_name}' has no pending missions; already complete!")
                summary.end_time = datetime.datetime.now().isoformat()
                self._emit(RunEvent(event_type="course_run_complete", data=summary.to_dict()))
                return summary

            self._switch_to_window("学生学习页面")
            self._fold_sidebar()

            chapters_done = 0
            while True:
                # 1. Face popup check
                if self.config.pass_face and self.face_bypass.is_popup_present():
                    logger.info("Face verification popup present; executing bypass...")
                    self.face_bypass.bypass()

                # 2. Process tasks on current chapter page
                self._fold_sidebar()
                content_types = self._detect_page_contents()
                logger.info(f"Chapter content detected: {list(content_types.keys())}")
                self._emit(RunEvent(event_type="chapter_content_detected", data={"types": list(content_types.keys())}))

                if "视频" in content_types:
                    summary.videos_completed += self.video_runner.process_chapter_videos(course_name)

                if "测验" in content_types and self.config.quiz_solve_mode != "skip":
                    summary.quizzes_completed += self.quiz_runner.process_chapter_quizzes(course_name)

                if "ppt" in content_types:
                    summary.ppt_completed += self.ppt_handler.process(course_name)

                if "阅读" in content_types:
                    summary.reading_completed += self.reading_handler.process(course_name)

                if "音频" in content_types:
                    summary.audio_completed += self.audio_handler.process(course_name)

                if "讨论" in content_types:
                    self.discussion_handler.process(course_name)

                chapters_done += 1
                summary.chapters_processed = chapters_done
                self._emit(RunEvent(event_type="chapter_completed", data={"chapter_index": chapters_done}))

                if max_chapters and chapters_done >= max_chapters:
                    logger.info(f"Reached max requested chapters ({max_chapters}); stopping")
                    break

                # 3. Advance to next page
                self.driver.switch_to.default_content()
                has_next = self._click_next_page()
                if not has_next:
                    logger.info("Finished all chapters in this course!")
                    break

                time.sleep(2)

        except Exception as e:
            logger.error(f"Course run encountered error: {e}", exc_info=True)
            summary.errors.append(str(e))
            summary.success = False
        finally:
            summary.end_time = datetime.datetime.now().isoformat()
            self._emit(RunEvent(event_type="course_run_complete", data=summary.to_dict()))

        return summary

    def _detect_page_contents(self) -> dict:
        """Inspects current chapter iframe for content widgets."""
        self.driver.switch_to.default_content()
        result = {}
        try:
            iframe = self.driver.find_element(By.ID, "iframe")
            self.driver.switch_to.frame(iframe)

            selectors = [
                ("视频", '[class*="ans-insertvideo-online"], [class*="ans-job-icon-clear"]'),
                ("测验", '//iframe[contains(@src, "/ananas/modules/work/index.html")]'),
                ("ppt", '[class*="insertdoc-online-ppt"], [class*="insertdoc-online-pdf"]'),
                ("阅读", '[class*="ans-book"], [src*="/ananas/modules/read/"]'),
                ("音频", '[class*="ans-insertaudio"]'),
                ("讨论", '[src*="/ananas/modules/insertbbs/"]'),
            ]

            for name, sel in selectors:
                by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
                els = self.driver.find_elements(by, sel)
                if els:
                    result[name] = True
        except Exception:
            pass

        return result

    def _click_next_page(self) -> bool:
        """Clicks next chapter button (#prevNextFocusNext)."""
        next_btn_xpath = '//*[@id="prevNextFocusNext"]'
        try:
            btn = self.driver.find_element(By.XPATH, next_btn_xpath)
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            time.sleep(0.5)
            self.driver.execute_script("arguments[0].click();", btn)
            return True
        except (ElementNotInteractableException, NoSuchElementException):
            return False
        except Exception as e:
            logger.debug(f"Click next page exception: {e}")
            return False

    def _fold_sidebar(self) -> None:
        """Folds side chapter menu for unobstructed layout."""
        try:
            self.driver.switch_to.default_content()
            fold_btn = self.driver.find_elements(By.XPATH, '//*[@id="selector"]/div[2]')
            if fold_btn:
                fold_btn[0].click()
        except Exception:
            pass

    def _switch_to_window(self, title_substr: str) -> bool:
        for handle in self.driver.window_handles:
            try:
                self.driver.switch_to.window(handle)
                if title_substr in (self.driver.title or ""):
                    return True
            except Exception:
                continue
        return False
