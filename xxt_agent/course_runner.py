# -*- coding: utf-8 -*-
"""Course progression orchestrator for Xuexitong."""

import datetime
import logging
import os
import re
import time
from pathlib import Path
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
from xxt_agent.exceptions import (
    CourseNotFoundError,
    DailyLimitReachedError,
    VideoNotFoundError,
    BlockedByFaceVerificationError,
)
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

    def _dump_debug_state(self, prefix: str = "debug") -> None:
        """Helper to dump current page HTML and screenshot to data/debug/ for troubleshooting."""
        try:
            debug_dir = Path(__file__).resolve().parent / "data" / "debug"
            debug_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            html_path = debug_dir / f"{prefix}_{ts}.html"
            png_path = debug_dir / f"{prefix}_{ts}.png"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
            self.driver.save_screenshot(str(png_path))
            logger.warning(f"Dumped debug DOM snapshot: {html_path} and screenshot: {png_path}")
        except Exception as e:
            logger.debug(f"Failed to dump debug state: {e}")

    def list_courses(self) -> List[CourseInfo]:
        """Fetches the complete list of courses (MOOC/Erya/general & regular) under current account."""
        self.session_manager.ensure_authenticated()

        courses: List[CourseInfo] = []
        seen_titles = set()

        # 1. Primary: Visit interaction hub (covers all Erya, MOOC, and general education courses)
        primary_url = os.environ.get("XXT_COURSE_URL", "https://mooc1.chaoxing.com/visit/interaction")
        try:
            logger.info(f"Fetching courses from primary portal: {primary_url}")
            self.driver.get(primary_url)
            time.sleep(2.5)

            course_selectors = [
                "span.course-name",
                "h3.course-name",
                ".course-name.overHidden2",
                ".course-name",
                ".courseName",
                "[class*='course-name']",
                "[class*='w_cour_txtH']",
            ]
            course_elements = []
            for sel in course_selectors:
                els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if els:
                    course_elements = els
                    break

            for el in course_elements:
                title = el.get_attribute("title") or el.text.strip()
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    courses.append(CourseInfo(name=title))

            logger.info(f"Found {len(courses)} course(s) on primary interaction portal")
        except Exception as e:
            logger.warning(f"Error fetching from primary interaction portal: {e}")

        # 2. Fallback: If 0 courses found, try i.chaoxing.com
        if not courses:
            try:
                logger.info("Primary portal returned 0 courses; falling back to i.chaoxing.com...")
                self.driver.get("https://i.chaoxing.com/")
                time.sleep(2)
                self._navigate_to_course_list_tab()

                fallback_selectors = [
                    (By.CLASS_NAME, "course-name"),
                    (By.CLASS_NAME, "courseName"),
                    (By.CSS_SELECTOR, '[class*="w_cour_txtH"]')
                ]
                for by_type, sel in fallback_selectors:
                    els = self.driver.find_elements(by_type, sel)
                    for el in els:
                        title = el.get_attribute("title") or el.text.strip()
                        if title and title not in seen_titles:
                            seen_titles.add(title)
                            courses.append(CourseInfo(name=title))
                    if courses:
                        break
            except Exception as e:
                logger.error(f"Error reading fallback course list: {e}")

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
        """Finds, clicks into, and navigates to the specified course page, bypassing face checkpoints."""
        self.session_manager.ensure_authenticated()

        orig_handles = list(self.driver.window_handles)

        # 1. Primary: Locate on interaction hub
        primary_url = os.environ.get("XXT_COURSE_URL", "https://mooc1.chaoxing.com/visit/interaction")
        try:
            self.driver.get(primary_url)
            time.sleep(2.5)

            course_selectors = [
                "span.course-name",
                "h3.course-name",
                ".course-name.overHidden2",
                ".course-name",
                ".courseName",
                "[class*='course-name']"
            ]
            target_el = None
            for sel in course_selectors:
                els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for el in els:
                    title = el.get_attribute("title") or el.text.strip()
                    if course_name in title:
                        target_el = el
                        break
                if target_el:
                    break

            if target_el:
                logger.info(f"Found target course '{course_name}' on primary interaction portal")
                try:
                    parent_a = target_el.find_element(By.XPATH, "./ancestor::a[1]")
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", parent_a)
                    time.sleep(0.3)
                    self.driver.execute_script("arguments[0].click();", parent_a)
                except Exception:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_el)
                    time.sleep(0.3)
                    self.driver.execute_script("arguments[0].click();", target_el)

                time.sleep(3)
                new_handles = [h for h in self.driver.window_handles if h not in orig_handles]
                if new_handles:
                    self.driver.switch_to.window(new_handles[-1])
                else:
                    self._switch_to_window(course_name)

                # Check and bypass face verification on transition page (stucoursemiddle / faceCollectQrPop)
                time.sleep(2)
                if self.config.pass_face and self.face_bypass.is_popup_present(check_top=True):
                    logger.info("Face verification popup present on course transition page; executing bypass...")
                    self.face_bypass.bypass()
                    time.sleep(3)

                # Wait for transition/redirect away from stucoursemiddle
                for _ in range(6):
                    if "stucoursemiddle" not in self.driver.current_url:
                        break
                    time.sleep(1)

                if len(self.driver.window_handles) > len(orig_handles):
                    self.driver.switch_to.window(self.driver.window_handles[-1])

                return True
        except Exception as e:
            logger.warning(f"Failed to open course via primary portal: {e}")

        # 2. Fallback: Try via i.chaoxing.com
        try:
            logger.info("Attempting fallback course selection via i.chaoxing.com...")
            self.driver.get("https://i.chaoxing.com/")
            time.sleep(2)
            self._navigate_to_course_list_tab()

            course_elements = self.driver.find_elements(By.CLASS_NAME, "course-name")
            if not course_elements:
                course_elements = self.driver.find_elements(By.CLASS_NAME, "courseName")
            if not course_elements:
                course_elements = self.driver.find_elements(By.CSS_SELECTOR, '[class*="w_cour_txtH"]')

            for el in course_elements:
                title = el.get_attribute("title") or el.text.strip()
                if course_name in title:
                    logger.info(f"Found target course on i.chaoxing.com: {title}")
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
                    if self.config.pass_face and self.face_bypass.is_popup_present(check_top=True):
                        logger.info("Face verification popup present on course entry page; executing bypass...")
                        self.face_bypass.bypass()
                        time.sleep(3)

                    return True
        except Exception as e:
            logger.warning(f"Fallback selection error: {e}")

        raise CourseNotFoundError(course_name)

    def get_chapters(self, course_name: str) -> List[dict]:
        """Inspects and returns the chapter list for a given course."""
        self.select_course(course_name)
        time.sleep(2)

        # 1. Switch to chapter tab if present
        try:
            navs = self.driver.find_elements(By.CSS_SELECTOR, ".nav_content, li[data-nav-name*='章节'], [title*='章节'], a[title*='章节']")
            for nav in navs:
                t = nav.get_attribute("title") or nav.text.strip()
                if "章节" in t:
                    self.driver.execute_script("arguments[0].click();", nav)
                    time.sleep(2)
                    break
        except Exception:
            pass

        # 2. Check for face popup if landed here
        if self.config.pass_face and self.face_bypass.is_popup_present(check_top=True):
            self.face_bypass.bypass()
            time.sleep(2)

        # 3. Locate candidate chapter elements across top document and ALL iframes
        chapters = []
        candidate_selectors = [
            ".posCatalog_name, .catalog_name, .level_two",
            "[class*='posCatalog_name']",
            "[class*='catalog_name']",
            "[class*='level_two']",
            "[class*='posCatalog']"
        ]

        def extract_nodes_from_context(ctx) -> List[dict]:
            parsed = []
            for sel in candidate_selectors:
                nodes = ctx.find_elements(By.CSS_SELECTOR, sel)
                if nodes:
                    for idx, n in enumerate(nodes):
                        t = n.get_attribute("title") or n.text.strip()
                        if t:
                            try:
                                parent = n.find_element(By.XPATH, "..")
                                parent_html = parent.get_attribute("innerHTML") or ""
                            except Exception:
                                parent_html = ""
                            has_mission = (
                                "knowledgeJobCount" in parent_html
                                or "catalog_tishi" in parent_html
                                or "ans-job-icon" in parent_html
                            )
                            completed = (
                                "icon_yiwanc" in parent_html
                                or "icon_complete" in parent_html
                            )
                            parsed.append({
                                "index": idx + 1,
                                "title": t,
                                "has_mission": has_mission,
                                "completed": completed
                            })
                    if parsed:
                        break
            return parsed

        # First check top-level document
        self.driver.switch_to.default_content()
        chapters = extract_nodes_from_context(self.driver)

        # If not in top document, inspect all iframes prioritizing frame_content-zj
        if not chapters:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            def iframe_priority(f):
                fid = (f.get_attribute("id") or "").lower()
                fname = (f.get_attribute("name") or "").lower()
                fsrc = (f.get_attribute("src") or "").lower()
                if "frame_content-zj" in fid or "frame_content-zj" in fname:
                    return 0
                if "studentcourse" in fsrc or "stu" in fsrc:
                    return 1
                if "catalog" in fsrc or "courselist" in fsrc:
                    return 2
                return 3

            sorted_iframes = sorted(iframes, key=iframe_priority)
            for f in sorted_iframes:
                try:
                    self.driver.switch_to.default_content()
                    self.driver.switch_to.frame(f)
                    chapters = extract_nodes_from_context(self.driver)
                    if chapters:
                        break
                except Exception:
                    continue

        self.driver.switch_to.default_content()

        # 4. If chapters is still empty, dump DOM and screenshot for debugging (Issue #4 recommendation)
        if not chapters:
            logger.warning(f"Could not locate chapter nodes for course '{course_name}'; dumping debug DOM snapshot...")
            self._dump_debug_state(prefix=f"chapter_empty_{course_name}")

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

        # Search for unfinished task indicators (.catalog_tishi120 / .catalog_tishi / .ans-job-icon)
        self.driver.switch_to.default_content()
        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        target_marker = None

        def iframe_priority(f):
            fid = (f.get_attribute("id") or "").lower()
            fname = (f.get_attribute("name") or "").lower()
            fsrc = (f.get_attribute("src") or "").lower()
            if "frame_content-zj" in fid or "frame_content-zj" in fname:
                return 0
            if "studentcourse" in fsrc or "stu" in fsrc:
                return 1
            if "catalog" in fsrc or "courselist" in fsrc:
                return 2
            return 3

        for iframe in sorted(iframes, key=iframe_priority):
            try:
                self.driver.switch_to.default_content()
                self.driver.switch_to.frame(iframe)

                # Strategy 1: Iterate .catalog_title blocks, skipping completed ones
                title_divs = self.driver.find_elements(By.CSS_SELECTOR, ".catalog_title, [class*='catalog_title']")
                if title_divs:
                    for td in title_divs:
                        html = td.get_attribute("outerHTML") or ""
                        # Skip if completed
                        if "icon_yiwanc" in html or "icon_complete" in html:
                            continue
                        # Skip if no task indicator
                        if "knowledgeJobCount" not in html and "catalog_tishi" not in html and "ans-job-icon" not in html:
                            continue
                        links = td.find_elements(By.CSS_SELECTOR, "a.clicktitle, a")
                        target_marker = links[0] if links else td
                        target_title = td.text.strip()[:60]
                        break

                # Strategy 2: If no target from catalog_title, check catalog markers that do NOT have icon_yiwanc
                if not target_marker:
                    markers = self.driver.find_elements(By.CSS_SELECTOR, ".catalog_tishi120, .catalog_tishi, [class*='catalog_tishi']")
                    for m in markers:
                        try:
                            parent = m.find_element(By.XPATH, "..")
                            p_html = parent.get_attribute("outerHTML") or ""
                            if "icon_yiwanc" in p_html or "icon_complete" in p_html:
                                continue
                            target_marker = m
                            target_title = parent.text.strip()[:60]
                            break
                        except Exception:
                            continue

                if target_marker:
                    break
            except Exception:
                self.driver.switch_to.default_content()
                continue

        if not target_marker:
            logger.info("No unfinished mission points found in chapter tree")
            return False

        logger.info(f"Target unfinished chapter: {target_title}; entering...")
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_marker)
        time.sleep(0.5)
        self.driver.execute_script("arguments[0].click();", target_marker)
        time.sleep(2)
        return True

    def check_course_daily_limits(self) -> dict:
        """Inspects course chapter catalog page for daily watch duration and mission point limits."""
        res = {
            "has_limit": False,
            "limit_reached": False,
            "duration_cur": 0,
            "duration_max": 0,
            "tasks_cur": 0,
            "tasks_max": 0,
            "reason": ""
        }
        try:
            self.driver.switch_to.default_content()
            frames = self.driver.find_elements(By.TAG_NAME, "iframe")
            target_frame = None
            for f in frames:
                fid = f.get_attribute("id") or ""
                fname = f.get_attribute("name") or ""
                if "frame_content-zj" in fid or "frame_content-zj" in fname:
                    target_frame = f
                    break

            if target_frame:
                self.driver.switch_to.frame(target_frame)

            text = self.driver.execute_script("return (document.body && document.body.innerText) ? document.body.innerText : '';")
            self.driver.switch_to.default_content()

            # 1. Match: 今日已观看视频时长（分钟）: 45/45
            dur_match = re.search(r"今日已观看视频时长[^\d]*(\d+)\s*/\s*(\d+)", text)
            if dur_match:
                cur_d, max_d = int(dur_match.group(1)), int(dur_match.group(2))
                res["has_limit"] = True
                res["duration_cur"] = cur_d
                res["duration_max"] = max_d
                if max_d > 0 and cur_d >= max_d:
                    res["limit_reached"] = True
                    res["reason"] = f"今日已观看视频时长达上限 ({cur_d}/{max_d}分钟)"

            # 2. Match: 今日可完成视频任务点: 2/5 (递减计数，剩余额度；0/5 才代表今日额度耗尽)
            task_match = re.search(r"今日可完成视频任务点[^\d]*(\d+)\s*/\s*(\d+)", text)
            if task_match:
                cur_t, max_t = int(task_match.group(1)), int(task_match.group(2))
                res["has_limit"] = True
                res["tasks_cur"] = cur_t
                res["tasks_max"] = max_t
                # 只有剩余任务点为 0 且上限 > 0 时才判定为额度耗尽
                if max_t > 0 and cur_t <= 0:
                    res["limit_reached"] = True
                    if not res["reason"]:
                        res["reason"] = f"今日可完成视频任务点已耗尽 (0/{max_t})"

        except Exception as e:
            logger.debug(f"Error checking daily limits: {e}")
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass

        return res

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

        before_done = set()
        try:
            chapters_before = self.get_chapters(course_name)
            before_done = {ch["title"] for ch in chapters_before if ch.get("completed")}
            logger.info(f"Pre-run completed chapters count: {len(before_done)}")
        except Exception as e:
            logger.debug(f"Could not snapshot pre-run chapters: {e}")

        try:
            self.select_course(course_name)

            # Check if course has already hit daily limits on catalog page (Image 1)
            limits = self.check_course_daily_limits()
            if limits.get("limit_reached"):
                reason = limits.get("reason", "今日观看时长或任务点已达上限")
                logger.warning(f"Course '{course_name}' has reached today's limit: {reason}")
                summary.daily_limit_reached = True
                summary.daily_limit_reason = reason
                summary.end_time = datetime.datetime.now().isoformat()
                self._emit(RunEvent(event_type="daily_limit_reached", data={"course": course_name, "reason": reason}))
                self._emit(RunEvent(event_type="course_run_complete", data=summary.to_dict()))
                return summary

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

                # 2. Daily limit modal check (Image 2) on student study page
                limit_popup = self.video_runner.check_daily_limit_popup()
                if limit_popup:
                    logger.warning(f"Daily watch limit reached for '{course_name}': {limit_popup}")
                    summary.daily_limit_reached = True
                    summary.daily_limit_reason = limit_popup
                    self._emit(RunEvent(event_type="daily_limit_reached", data={"course": course_name, "reason": limit_popup}))
                    break

                # 3. Process tasks on current chapter page
                self._fold_sidebar()
                chapter_title = self._get_current_chapter_title()
                logger.info(f"--- Processing Chapter {chapters_done + 1}: {chapter_title} ---")

                # Check for blocking server-side face verification overlay
                FACE_BLOCKERS = [
                    "Facial information collection", "人脸信息采集",
                    "扫描二维码", "请使用手机APP", "请使用手机 APP",
                    "face collection", "faceCollect",
                    "人脸采集", "请扫描下方二维码进入",
                ]
                try:
                    self.driver.switch_to.default_content()
                    body_text = self.driver.execute_script(
                        "return (document.body && document.body.innerText) || '';"
                    ) or ""
                    try:
                        self.driver.switch_to.frame("iframe")
                        iframe_text = self.driver.execute_script(
                            "return (document.body && document.body.innerText) || '';"
                        ) or ""
                        body_text += " " + iframe_text
                    except Exception:
                        pass
                    self.driver.switch_to.default_content()

                    if any(kw in body_text for kw in FACE_BLOCKERS):
                        msg = (
                            f"课程 '{course_name}' 章节 '{chapter_title}' 被强制人脸核验拦截。"
                            f"需要在学习通 APP 扫码完成人脸采集后才能继续，自动化无法绕过此类服务端强制验证。"
                        )
                        logger.error(msg)
                        summary.errors.append(msg)
                        summary.success = False
                        self._emit(RunEvent(
                            event_type="face_blocked",
                            data={"course": course_name, "chapter": chapter_title, "message": msg}
                        ))
                        break
                except Exception as e:
                    logger.debug(f"Face blocker check error: {e}")

                # Iterate through all sub-tabs (e.g. 1 视频, 2 章节测验) in current chapter
                self.driver.switch_to.default_content()
                sub_tabs = self.driver.find_elements(By.CSS_SELECTOR, ".prev_ul li")
                total_tabs = max(1, len(sub_tabs))
                logger.info(f"Chapter '{chapter_title}' contains {total_tabs} sub-tab(s)")

                for tab_idx in range(total_tabs):
                    self.driver.switch_to.default_content()
                    if total_tabs > 1:
                        sub_tabs = self.driver.find_elements(By.CSS_SELECTOR, ".prev_ul li")
                        if tab_idx < len(sub_tabs):
                            target_tab = sub_tabs[tab_idx]
                            raw_t = target_tab.get_attribute("title") or target_tab.text.strip()
                            clean_t = re.sub(r"[\u200b\s]+", " ", raw_t).strip()
                            logger.info(f"Switching to chapter sub-tab {tab_idx + 1}/{total_tabs}: {clean_t}")
                            self.driver.execute_script("arguments[0].click();", target_tab)
                            time.sleep(2)

                    # Face check on sub-tab
                    if self.config.pass_face and self.face_bypass.is_popup_present():
                        self.face_bypass.bypass()

                    content_types = self._detect_page_contents()
                    logger.info(f"Sub-tab {tab_idx + 1}/{total_tabs} content detected: {list(content_types.keys())}")
                    self._emit(RunEvent(event_type="chapter_content_detected", data={"types": list(content_types.keys()), "tab": tab_idx + 1}))

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
                self._emit(RunEvent(event_type="chapter_completed", data={"chapter_index": chapters_done, "title": chapter_title}))

                if max_chapters and chapters_done >= max_chapters:
                    logger.info(f"Reached max requested chapters ({max_chapters}); stopping")
                    break

                # 4. Advance to next page
                self.driver.switch_to.default_content()
                has_next = self._click_next_page()

                # 兜底：按钮点不动时，直接从目录里跳转到下一个未完成章节。
                # （学习通改版后「下一节」的 XPath 经常失效，不能就此判定课程结束）
                if not has_next:
                    logger.info("Next-page button failed; jumping to next unfinished chapter via catalog")
                    try:
                        has_next = self.find_and_enter_mission_point(course_name)
                        if has_next:
                            self._switch_to_window("学生学习页面")
                            self._fold_sidebar()
                            time.sleep(2)
                    except Exception as e:
                        logger.warning(f"Catalog fallback navigation failed: {e}")
                        has_next = False

                if not has_next:
                    logger.info("Finished all chapters in this course!")
                    break

                time.sleep(2)

        except DailyLimitReachedError as dle:
            logger.warning(f"Daily watch limit reached during execution: {dle.message}")
            summary.daily_limit_reached = True
            summary.daily_limit_reason = dle.message
            self._emit(RunEvent(event_type="daily_limit_reached", data={"course": course_name, "reason": dle.message}))
        except VideoNotFoundError as vnf:
            logger.error(f"Video element not found: {vnf.message}")
            summary.errors.append(str(vnf.message))
            summary.success = False
            self._emit(RunEvent(event_type="video_blocked", data={
                "course": course_name,
                "message": vnf.message
            }))
        except BlockedByFaceVerificationError as bfe:
            logger.error(f"Blocked by face verification: {bfe.message}")
            summary.errors.append(str(bfe.message))
            summary.success = False
            self._emit(RunEvent(event_type="face_blocked", data={
                "course": course_name,
                "message": bfe.message
            }))
        except Exception as e:
            logger.error(f"Course run encountered error: {e}", exc_info=True)
            summary.errors.append(str(e))
            summary.success = False
        finally:
            # Cross-verify newly completed chapters via course catalog
            try:
                chapters_after = self.get_chapters(course_name)
                after_done = {ch["title"] for ch in chapters_after if ch.get("completed")}
                newly_done = after_done - before_done
                summary.newly_completed_count = len(newly_done)

                processed_claim = (
                    summary.videos_completed + summary.quizzes_completed
                    + summary.ppt_completed + summary.reading_completed + summary.audio_completed
                )

                if before_done and after_done and not newly_done and processed_claim > 0 and not summary.daily_limit_reached:
                    summary.success = False
                    msg = (
                        f"目录验证失败：内部计数声称完成 {processed_claim} 项，"
                        f"但目录已完成节点数运行前后均为 {len(after_done)}，实际未新增任何完成章节。"
                    )
                    summary.errors.append(msg)
                    logger.warning(msg)
            except Exception as e:
                logger.debug(f"Post-run verification failed: {e}")

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

    def _get_current_chapter_title(self) -> str:
        """Retrieves title of the currently loaded chapter."""
        try:
            self.driver.switch_to.default_content()
            els = self.driver.find_elements(By.CSS_SELECTOR, ".prev_title")
            if els:
                t = els[0].get_attribute("title") or els[0].text.strip()
                return re.sub(r"[\u200b\s]+", " ", t).strip()
        except Exception:
            pass
        return ""

    def _navigate_to_next_chapter_via_sidebar(self) -> bool:
        """Fallback chapter navigation: finds and clicks the next unfinished chapter in the sidebar."""
        try:
            self.driver.switch_to.default_content()
            next_chapter_el = self.driver.execute_script(
                """
                var currentTitle = ((document.querySelector('.prev_title') || {}).getAttribute('title') || '').trim();
                var items = Array.from(document.querySelectorAll('.posCatalog_select'));
                
                var currentIdx = -1;
                for (var i = 0; i < items.length; i++) {
                    var nameEl = items[i].querySelector('.posCatalog_name');
                    var t = nameEl ? (nameEl.getAttribute('title') || nameEl.innerText.trim()) : '';
                    if (currentTitle && t && (t === currentTitle || t.includes(currentTitle) || currentTitle.includes(t))) {
                        currentIdx = i;
                        break;
                    }
                }
                
                // 1. Search for next unfinished chapter after currentIdx
                for (var j = currentIdx + 1; j < items.length; j++) {
                    var pointsEl = items[j].querySelector('.catalog_points_yi .orangeNew, .catalog_tishi, .catalog_tishi120');
                    var nameEl = items[j].querySelector('.posCatalog_name');
                    if (pointsEl && nameEl) {
                        return nameEl;
                    }
                }
                
                // 2. Search for any unfinished chapter from beginning
                for (var k = 0; k < items.length; k++) {
                    var pointsEl = items[k].querySelector('.catalog_points_yi .orangeNew, .catalog_tishi, .catalog_tishi120');
                    var nameEl = items[k].querySelector('.posCatalog_name');
                    if (pointsEl && nameEl) {
                        return nameEl;
                    }
                }
                return null;
                """
            )
            if next_chapter_el:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_chapter_el)
                time.sleep(0.5)
                self.driver.execute_script("arguments[0].click();", next_chapter_el)
                time.sleep(3)
                logger.info("Successfully navigated to next chapter via sidebar catalog")
                return True
        except Exception as e:
            logger.debug(f"Sidebar catalog navigation fallback failed: {e}")
        return False

    def _click_next_page(self) -> bool:
        """Clicks next chapter button, handles confirmation dialogs, and falls back to sidebar catalog navigation."""
        self.driver.switch_to.default_content()
        curr_url = self.driver.current_url
        curr_title = self._get_current_chapter_title()
        logger.info(f"Advancing from current chapter '{curr_title}' to next chapter...")

        # 1. Try standard next buttons: #prevNextFocusNext, .nextChapter, .prev_next.next
        next_selectors = [
            '//*[@id="prevNextFocusNext"]',
            '//div[contains(@class, "prev_next")]//a[contains(text(), "下一节")]',
            '//div[contains(@class, "prev_next")]//div[contains(text(), "下一节")]',
            '//a[contains(@class, "nextChapter")]',
        ]
        for xpath in next_selectors:
            try:
                btns = self.driver.find_elements(By.XPATH, xpath)
                for btn in btns:
                    if btn.is_displayed():
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                        time.sleep(0.3)
                        self.driver.execute_script("arguments[0].click();", btn)
                        break
            except Exception:
                continue

        time.sleep(1.5)

        # 2. Check and handle confirmation popups
        try:
            # Check modal nextChapter button (e.g. .jobFinishTip "当前章节还有任务点未完成，是否去完成？")
            confirm_btns = self.driver.find_elements(
                By.CSS_SELECTOR,
                ".jobFinishTip .nextChapter, #mainid div.popBottom a.nextChapter, a.nextChapter, #popok"
            )
            for c_btn in confirm_btns:
                if c_btn.is_displayed() or c_btn.get_attribute("class"):
                    self.driver.execute_script("arguments[0].click();", c_btn)
                    time.sleep(1)
                    break

            # Reference project modal confirm: //*[@id="mainid"]/div[1]/div/div[3]/a[2]
            ref_confirm = self.driver.find_elements(By.XPATH, '//*[@id="mainid"]/div[1]/div/div[3]/a[2]')
            if ref_confirm and ref_confirm[0].is_displayed():
                self.driver.execute_script("arguments[0].click();", ref_confirm[0])
                time.sleep(1)
        except Exception as e:
            logger.debug(f"Confirmation modal handling: {e}")

        # Check JS alert if any
        try:
            alert = self.driver.switch_to.alert
            alert.accept()
        except Exception:
            pass

        time.sleep(2)

        # 3. Verify if chapter changed
        self.driver.switch_to.default_content()
        new_url = self.driver.current_url
        new_title = self._get_current_chapter_title()
        if (new_url != curr_url) or (new_title and new_title != curr_title):
            logger.info(f"Successfully transitioned to next chapter: {new_title}")
            return True

        # 4. Fallback: If still on same chapter, locate and click next chapter in sidebar catalog
        logger.info("Next page button did not change chapter; trying sidebar catalog navigation fallback...")
        return self._navigate_to_next_chapter_via_sidebar()

    def _fold_sidebar(self) -> None:
        """Folds side chapter menu for unobstructed layout and injects anti-blur focus protection."""
        try:
            self.driver.switch_to.default_content()
            self.driver.execute_script(
                """
                window.onblur = null;
                window.onfocus = null;
                window.onmouseleave = null;
                document.onvisibilitychange = null;
                try {
                    Object.defineProperty(document, 'hidden', { get: function() { return false; }, configurable: true });
                    Object.defineProperty(document, 'visibilityState', { get: function() { return 'visible'; }, configurable: true });
                } catch(e){}
                """
            )
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
