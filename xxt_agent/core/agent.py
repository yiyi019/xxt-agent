# -*- coding: utf-8 -*-
"""
High-level Xuexitong Agent SDK.
Provides a unified, clean, and agent-friendly interface for autonomous execution.
"""
import time
from typing import Dict, Any, List, Optional, Callable

from .config import AgentConfig
from .browser import create_driver, close_driver
from .auth import ensure_authenticated, check_login_status
from .course import list_courses, select_course, get_chapters
from .player import play_current_video, next_chapter
from .solver import DeepSeekSolver
from .font_decoder import FontDecoder

class XuexitongAgent:
    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig.load()
        self.driver = None
        self.solver = DeepSeekSolver(
            api_key=self.config.deepseek_api_key,
            model=self.config.deepseek_model
        )
        self.font_decoder = FontDecoder(self.config.font_dict_path)

    def _ensure_driver(self, headless: Optional[bool] = None):
        if self.driver is None:
            self.driver = create_driver(self.config, headless=headless)
        return self.driver

    def get_status(self) -> Dict[str, Any]:
        """Check the status of credentials, driver, and AI configuration."""
        import os
        return {
            "ok": True,
            "browser": self.config.browser,
            "driver_path": self.config.driver_path,
            "driver_exists": bool(self.config.driver_path and os.path.exists(self.config.driver_path)),
            "cookies_exist": bool(self.config.cookies_path and os.path.exists(self.config.cookies_path)),
            "api_key_configured": bool(self.config.deepseek_api_key and "sk-" in self.config.deepseek_api_key),
            "deepseek_model": self.config.deepseek_model,
            "headless_mode": self.config.headless,
            "default_speed": self.config.speed
        }

    def login(self, headless: Optional[bool] = None) -> Dict[str, Any]:
        """Authenticate using cookies or credentials."""
        driver = self._ensure_driver(headless=headless)
        return ensure_authenticated(driver, self.config)

    def list_courses(self) -> Dict[str, Any]:
        """List all courses enrolled on the account."""
        auth_res = self.login()
        if not auth_res.get("ok"):
            return auth_res

        courses = list_courses(self.driver)
        return {
            "ok": True,
            "count": len(courses),
            "courses": courses
        }

    def get_course_chapters(self, course_name: str) -> Dict[str, Any]:
        """Open course and list its chapters."""
        auth_res = self.login()
        if not auth_res.get("ok"):
            return auth_res

        sel_res = select_course(self.driver, course_name)
        if not sel_res.get("ok"):
            return sel_res

        chapters = get_chapters(self.driver)
        return {
            "ok": True,
            "course": course_name,
            "total_chapters": len(chapters),
            "chapters": chapters
        }

    def run_course(
        self,
        course_name: str,
        duration_seconds: int = 3600,
        speed: Optional[float] = None,
        max_chapters: int = 15,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Execute automated study on a specified course.
        Watches chapter videos up to duration_seconds or max_chapters.
        """
        auth_res = self.login()
        if not auth_res.get("ok"):
            return auth_res

        sel_res = select_course(self.driver, course_name)
        if not sel_res.get("ok"):
            return sel_res

        playback_speed = speed if speed is not None else self.config.speed
        start_time = time.time()
        chapters_processed = 0

        while chapters_processed < max_chapters:
            elapsed = time.time() - start_time
            if elapsed >= duration_seconds:
                break

            # Play video in current chapter
            video_res = play_current_video(
                self.driver,
                speed=playback_speed,
                max_seconds=int(duration_seconds - elapsed),
                progress_callback=progress_callback
            )
            chapters_processed += 1

            # Advance to next chapter
            has_next = next_chapter(self.driver)
            if not has_next:
                break
            time.sleep(2)

        total_elapsed = int(time.time() - start_time)
        return {
            "ok": True,
            "course": course_name,
            "chapters_processed": chapters_processed,
            "duration_seconds": total_elapsed,
            "speed": playback_speed,
            "status": "completed"
        }

    def solve(
        self,
        question: str,
        q_type: str = "单选题",
        options: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Directly query DeepSeek AI solver for an answer."""
        decoded_title = self.font_decoder.decode(question)
        decoded_options = [self.font_decoder.decode(opt) for opt in options] if options else None
        return self.solver.solve(decoded_title, q_type=q_type, options=decoded_options)

    def close(self):
        """Clean up driver resources."""
        if self.driver:
            close_driver(self.driver)
            self.driver = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
