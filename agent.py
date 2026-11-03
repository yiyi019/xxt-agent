# -*- coding: utf-8 -*-
"""High-level programmatic agent interface for Xuexitong course automation."""

import logging
from typing import Any, Callable, Dict, List, Optional

from xxt_agent.ai_solver import DeepSeekSolver
from xxt_agent.browser import BrowserManager, set_keep_awake
from xxt_agent.config import XXTConfig
from xxt_agent.course_runner import CourseRunner
from xxt_agent.face_bypass import FaceBypass
from xxt_agent.font_decoder import FontDecoder
from xxt_agent.models import CourseInfo, CourseRunSummary, RunEvent
from xxt_agent.session import SessionManager

logger = logging.getLogger(__name__)


class XXTAgent:
    """Unified entry-point for AI agents to automate, inspect, and control Xuexitong."""

    def __init__(
        self,
        config: Optional[XXTConfig] = None,
        headless: Optional[bool] = None,
        api_key: Optional[str] = None,
        event_callback: Optional[Callable[[RunEvent], None]] = None,
    ):
        self.config = config or XXTConfig.load()
        if headless is not None:
            self.config.headless = headless
        if api_key is not None:
            self.config.api_key = api_key

        self.event_callback = event_callback or (lambda e: None)
        self.driver = None
        self._course_runner: Optional[CourseRunner] = None
        self._session_manager: Optional[SessionManager] = None
        self._font_decoder: Optional[FontDecoder] = None
        self._solver: Optional[DeepSeekSolver] = None
        self._face_bypass: Optional[FaceBypass] = None

    def __enter__(self) -> "XXTAgent":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def start(self) -> None:
        """Initializes the browser and internal sub-systems."""
        if self.driver is None:
            logger.info("Initializing XXTAgent browser session...")
            self.driver = BrowserManager.create_driver(self.config)
            self._session_manager = SessionManager(self.driver, self.config)
            self._font_decoder = FontDecoder(self.config.font_dict_path)
            self._solver = DeepSeekSolver(
                api_key=self.config.api_key,
                primary_model=self.config.api_model,
                base_url=self.config.api_base_url,
            )
            self._face_bypass = FaceBypass(self.driver)
            self._course_runner = CourseRunner(
                driver=self.driver,
                config=self.config,
                solver=self._solver,
                event_callback=self.event_callback,
            )

    def close(self) -> None:
        """Gracefully closes browser and releases system resources."""
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
            self._course_runner = None
            self._session_manager = None
            set_keep_awake(False)
            logger.info("XXTAgent browser session closed")

    def check_session(self) -> Dict[str, Any]:
        """Validates current authentication status and returns profile details."""
        self.start()
        profile = self._session_manager.ensure_authenticated()
        return {
            "authenticated": True,
            "profile": profile,
        }

    def list_courses(self) -> List[CourseInfo]:
        """Returns the list of enrolled courses."""
        self.start()
        return self._course_runner.list_courses()

    def run_course(self, course_name: str, max_chapters: Optional[int] = None) -> CourseRunSummary:
        """Executes full automated progression for the given course."""
        self.start()
        return self._course_runner.run_course(course_name, max_chapters=max_chapters)

    def run_queue(
        self,
        courses: List[str],
        max_chapters_per_course: Optional[int] = None
    ) -> Dict[str, Any]:
        """Executes queue progression over multiple courses, automatically switching on daily limits."""
        self.start()
        total_courses = len(courses)
        logger.info(f"Starting multi-course queue with {total_courses} course(s): {courses}")
        self.event_callback(RunEvent(event_type="queue_start", data={"courses": courses, "total": total_courses}))

        results: Dict[str, Any] = {
            "total_courses": total_courses,
            "courses_processed": 0,
            "course_summaries": {},
            "statuses": {},
        }

        for idx, course_name in enumerate(courses):
            logger.info(f"=== Queue [{idx + 1}/{total_courses}]: Starting course '{course_name}' ===")
            self.event_callback(RunEvent(
                event_type="queue_course_start",
                data={"course": course_name, "index": idx + 1, "total": total_courses}
            ))

            summary = self._course_runner.run_course(course_name, max_chapters=max_chapters_per_course)
            results["course_summaries"][course_name] = summary.to_dict()
            results["courses_processed"] += 1

            if summary.daily_limit_reached:
                results["statuses"][course_name] = "daily_limit_reached"
                logger.warning(
                    f"Course '{course_name}' hit daily limit ({summary.daily_limit_reason}). "
                    f"Automatically switching to next course in queue..."
                )
                self.event_callback(RunEvent(
                    event_type="queue_course_switched",
                    data={
                        "course": course_name,
                        "reason": summary.daily_limit_reason,
                        "next_index": idx + 2 if idx + 1 < total_courses else None
                    }
                ))
            elif summary.success:
                results["statuses"][course_name] = "completed"
                logger.info(f"Course '{course_name}' finished all pending tasks!")
            else:
                results["statuses"][course_name] = "error"
                logger.warning(f"Course '{course_name}' finished with errors: {summary.errors}")

            # Clean up extra windows/tabs and return to base space before next course
            try:
                if len(self.driver.window_handles) > 1:
                    main_h = self.driver.window_handles[0]
                    for h in list(self.driver.window_handles):
                        if h != main_h:
                            try:
                                self.driver.switch_to.window(h)
                                self.driver.close()
                            except Exception:
                                pass
                    self.driver.switch_to.window(main_h)
            except Exception as e:
                logger.debug(f"Window cleanup error: {e}")

        logger.info(f"Multi-course queue completed. Summary: {results['statuses']}")
        self.event_callback(RunEvent(event_type="queue_complete", data=results))
        return results

    def solve_question(
        self,
        question_title: str,
        options: Optional[List[str]] = None,
        question_type: str = "单选题",
    ) -> List[str]:
        """Standalone utility to answer an individual quiz question via DeepSeek."""
        if self._solver is None:
            self._solver = DeepSeekSolver(
                api_key=self.config.api_key,
                primary_model=self.config.api_model,
                base_url=self.config.api_base_url,
            )
        return self._solver.solve_single(question_title, options, question_type)

    def decode_font(self, base64_ttf: str, text: str) -> str:
        """Standalone utility to decrypt custom font obfuscated text."""
        if self._font_decoder is None:
            self._font_decoder = FontDecoder(self.config.font_dict_path)
        char_map = self._font_decoder.build_char_map(base64_ttf)
        return self._font_decoder.decode_text(text, char_map)

    def bypass_face_popup(self) -> bool:
        """Checks and performs face popup bypass if a popup is active in the browser."""
        self.start()
        return self._face_bypass.bypass()
