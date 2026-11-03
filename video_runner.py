# -*- coding: utf-8 -*-
"""Video playback progression and in-video quiz automation for Xuexitong."""

import logging
import time
from typing import Callable, Optional

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from xxt_agent.ai_solver import DeepSeekSolver
from xxt_agent.exceptions import DailyLimitReachedError
from xxt_agent.face_bypass import FaceBypass
from xxt_agent.font_decoder import FontDecoder
from xxt_agent.models import RunEvent

logger = logging.getLogger(__name__)


class VideoRunner:
    """Manages HTML5 video playback, speed control, in-video quiz answering, and completion verification."""

    def __init__(
        self,
        driver,
        solver: Optional[DeepSeekSolver] = None,
        font_decoder: Optional[FontDecoder] = None,
        face_bypass: Optional[FaceBypass] = None,
        speed: float = 1.0,
        pass_video: bool = False,
        video_solve_mode: str = "ai",
        event_callback: Optional[Callable[[RunEvent], None]] = None,
    ):
        self.driver = driver
        self.solver = solver
        self.font_decoder = font_decoder or FontDecoder()
        self.face_bypass = face_bypass or FaceBypass(driver)
        self.speed = speed
        self.pass_video = pass_video
        self.video_solve_mode = video_solve_mode
        self.event_callback = event_callback or (lambda e: None)

    def _emit(self, event_type: str, data: dict) -> None:
        event = RunEvent(event_type=event_type, data=data)
        try:
            self.event_callback(event)
        except Exception as e:
            logger.debug(f"Event callback error: {e}")

    def process_chapter_videos(self, course_name: str) -> int:
        """Finds all video tasks in the current chapter iframe and watches them."""
        self.driver.switch_to.default_content()
        try:
            self.driver.switch_to.frame("iframe")
        except Exception:
            return 0

        job_icons = self.driver.find_elements(By.CLASS_NAME, "ans-job-icon-clear ")
        if not job_icons:
            job_icons = self.driver.find_elements(By.CSS_SELECTOR, '[class*="ans-insertvideo-online"]')

        total_videos = len(job_icons)
        logger.info(f"Detected {total_videos} video attachment(s) in chapter")
        self._emit("video_batch_found", {"total": total_videos})

        completed_count = 0
        for i in range(total_videos):
            self.driver.switch_to.default_content()
            self.driver.switch_to.frame("iframe")

            job_icons = self.driver.find_elements(By.CLASS_NAME, "ans-job-icon-clear ")
            if i >= len(job_icons):
                break

            icon = job_icons[i]
            parent = icon.find_element(By.XPATH, "..")
            parent_class = parent.get_attribute("class") or ""
            status_text = icon.get_attribute("aria-label") or ""

            if "ans-job-finished" in parent_class or status_text == "任务点已完成":
                logger.info(f"Video #{i+1} already completed; skipping")
                completed_count += 1
                continue

            try:
                vido_iframe = icon.find_element(By.XPATH, "following-sibling::iframe[1]")
            except Exception:
                # Try finding within parent
                vido_iframe = parent.find_element(By.TAG_NAME, "iframe")

            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", vido_iframe)
            self._watch_single_video(vido_iframe, i + 1, total_videos, course_name=course_name)
            completed_count += 1

        return completed_count

    def check_daily_limit_popup(self) -> Optional[str]:
        """Checks if the Chaoxing daily limit modal (.jobCountDiv) is displayed."""
        try:
            self.driver.switch_to.default_content()
            popups = self.driver.find_elements(By.CSS_SELECTOR, ".jobCountDiv, .videoLimitTip, .jobLimitTip")
            for p in popups:
                if p.is_displayed():
                    text = p.text.strip()
                    logger.warning(f"Detected Chaoxing daily watch limit popup: {text}")
                    # Click '知道了' or close modal
                    try:
                        btn = self.driver.find_element(By.CSS_SELECTOR, ".jobCountDiv div.popBottom a.jb_btn, .jobCountDiv .popClose")
                        self.driver.execute_script("arguments[0].click();", btn)
                    except Exception:
                        try:
                            self.driver.execute_script("if (typeof closeDeleteWindow === 'function') closeDeleteWindow();")
                        except Exception:
                            pass
                    return text or "今日视频观看时长或任务点已达上限"
        except Exception:
            pass
        return None

    def _switch_to_video_frame(self, video_index: int = 0) -> bool:
        """Reliably switches context into the video player iframe without stale references."""
        try:
            self.driver.switch_to.default_content()
            self.driver.switch_to.frame("iframe")
            v_iframes = self.driver.find_elements(By.CSS_SELECTOR, "iframe.ans-insertvideo-online, iframe[src*='video'], iframe")
            target = v_iframes[video_index] if (v_iframes and video_index < len(v_iframes)) else (v_iframes[0] if v_iframes else None)
            if target:
                self.driver.switch_to.frame(target)
                return True
        except Exception as e:
            logger.debug(f"Switch to video frame failed: {e}")
        return False

    def _watch_single_video(self, vido_iframe, index: int, total: int, course_name: str = "") -> None:
        """Watches a single video until completed, handling pauses, daily limits, and popups."""
        logger.info(f"Starting playback for video {index}/{total}...")
        self._emit("video_start", {"index": index, "total": total, "course": course_name})

        video_idx = index - 1
        self._switch_to_video_frame(video_idx)

        # 1. Start playback
        self._trigger_play()

        # 2. Mute audio and set playback rate with Auto-Play Blocker
        self._configure_playback()

        # 3. Fast-forward if pass_video enabled
        if self.pass_video:
            self._try_drag_progress_end()

        # 4. Monitor loop
        last_time_str = ""
        stagnant_seconds = 0
        start_ts = time.time()

        while True:
            time.sleep(1)

            # Check daily limit popup (Image 2)
            limit_msg = self.check_daily_limit_popup()
            if limit_msg:
                logger.warning(f"Course '{course_name}' reached daily watch limit: {limit_msg}")
                self._emit("daily_limit_reached", {"course": course_name, "message": limit_msg, "video_index": index})
                raise DailyLimitReachedError(course_name=course_name, message=limit_msg)

            # Check face popup in top-level document
            try:
                self.driver.switch_to.default_content()
                if self.face_bypass.is_popup_present():
                    logger.info("Face popup detected during video playback")
                    self._emit("face_popup_detected", {"video_index": index})
                    self.face_bypass.bypass()
            except Exception:
                pass
            finally:
                # Restore video iframe context dynamically
                self._switch_to_video_frame(video_idx)

            # Check in-video quiz
            self._check_and_solve_in_video_quiz()

            # Retrieve video duration and current time
            times = self._get_video_times()
            cur_time = times.get("current_seconds", 0)
            duration = times.get("duration_seconds", 1)
            cur_time_str = times.get("current_text", "")
            duration_str = times.get("duration_text", "")

            # Check completion via parent job icon
            if self._is_job_finished(video_idx):
                logger.info(f"Video {index}/{total} completed successfully")
                self._emit("video_finished", {
                    "index": index,
                    "duration_sec": round(time.time() - start_ts, 1),
                })
                break

            # Check completion via video ended
            if duration > 0 and cur_time >= duration - 1:
                logger.info(f"Video {index}/{total} reached end time ({cur_time_str}/{duration_str})")
                time.sleep(2)
                self._emit("video_finished", {
                    "index": index,
                    "duration_sec": round(time.time() - start_ts, 1),
                })
                break

            # Auto-resume if video paused or stalled
            if times.get("paused"):
                logger.debug("Video is paused; triggering play immediately...")
                self._trigger_play()

            if cur_time_str == last_time_str and cur_time_str != "":
                stagnant_seconds += 1
                if stagnant_seconds >= 2:
                    logger.debug("Playback stalled; clicking play to resume...")
                    self._trigger_play()
                    stagnant_seconds = 0
            else:
                stagnant_seconds = 0
                last_time_str = cur_time_str

            percent = round((cur_time / duration * 100), 1) if duration > 0 else 0.0
            self._emit("video_progress", {
                "index": index,
                "current": cur_time_str,
                "duration": duration_str,
                "percent": percent,
            })

    def _trigger_play(self) -> None:
        """Resumes video playback using Video.js API, DOM click, and HTML5 video element play."""
        try:
            self.driver.execute_script(
                """
                // 1. Video.js player API
                if (window.videojs) {
                    var players = Object.values(window.videojs.players || {});
                    players.forEach(function(p) {
                        try { if (p && p.play) p.play(); } catch(e){}
                    });
                }
                // 2. Click play control or big play button
                var btn = document.querySelector('.vjs-play-control, .vjs-big-play-button, button[title*="播放"]');
                if (btn) {
                    try { btn.click(); } catch(e){}
                }
                // 3. Raw HTML5 video element play
                var v = document.querySelector('video');
                if (v && v.paused) {
                    v.muted = true;
                    try { v.play(); } catch(e){}
                }
                """
            )
        except Exception as e:
            logger.debug(f"Script trigger play failed: {e}")

        try:
            btns = self.driver.find_elements(By.CSS_SELECTOR, ".vjs-play-control, .vjs-big-play-button")
            for b in btns:
                if b.is_displayed():
                    b.click()
                    break
        except Exception:
            pass

    def _configure_playback(self) -> None:
        """Sets mute, requested playback rate, and injects Auto-Play Blocker from reference project."""
        try:
            self.driver.execute_script(
                """
                // 1. Anti-blur & mouseout blocking (Auto Play Video Blocker from reference project)
                window.onblur = null;
                window.onfocus = null;
                window.onmouseleave = null;
                document.onvisibilitychange = null;
                try {
                    Object.defineProperty(document, 'hidden', { get: function() { return false; }, configurable: true });
                    Object.defineProperty(document, 'visibilityState', { get: function() { return 'visible'; }, configurable: true });
                } catch(e){}

                window.addEventListener('mouseout', function(e) {
                    e.stopPropagation();
                    e.preventDefault();
                }, true);

                if (window.ananas && window.ananas.pause) {
                    window.ananas.pause = function() {};
                }

                // 2. Video element configuration & pause hijacking
                var v = document.querySelector('video');
                if (v) {
                    v.muted = true;
                    v.volume = 0;
                    if (arguments[0] && arguments[0] > 0) {
                        v.playbackRate = arguments[0];
                    }
                    // Override video.pause so clicking pause or window blur CANNOT pause it mid-play,
                    // but allow pause when video has naturally reached the end
                    v._orig_pause = v.pause;
                    v.pause = function() {
                        var vid = document.querySelector('video');
                        if (vid && (vid.ended || (vid.duration && vid.currentTime >= vid.duration - 1))) {
                            if (v._orig_pause) v._orig_pause.call(v);
                            return;
                        }
                        console.log('[xxt_agent] Pause blocked by Auto-Play Blocker');
                    };
                    // 500ms auto-play heartbeat interval (reference project content.js)
                    if (!window._auto_play_interval) {
                        window._auto_play_interval = setInterval(function() {
                            var vid = document.querySelector('video');
                            if (vid && vid.paused && !vid.ended && (!vid.duration || vid.currentTime < (vid.duration - 1))) {
                                vid.muted = true;
                                vid.play().catch(function(){});
                            }
                        }, 500);
                    }
                }
                """,
                self.speed,
            )
        except Exception as e:
            logger.debug(f"Could not configure playback rate via script: {e}")

    def _try_drag_progress_end(self) -> None:
        try:
            self.driver.execute_script(
                """
                var v = document.querySelector('video');
                if (v && v.duration) {
                    v.currentTime = v.duration;
                }
                """
            )
            logger.info("Attempted fast-forward to video duration")
        except Exception:
            pass

    def _get_video_times(self) -> dict:
        try:
            return self.driver.execute_script(
                """
                var v = document.querySelector('video');
                if (!v) return { current_seconds: 0, duration_seconds: 0, current_text: '', duration_text: '', paused: true };
                function fmt(s) {
                    var m = Math.floor(s / 60);
                    var sec = Math.floor(s % 60);
                    return m + ':' + (sec < 10 ? '0' : '') + sec;
                }
                return {
                    current_seconds: v.currentTime || 0,
                    duration_seconds: v.duration || 0,
                    current_text: fmt(v.currentTime || 0),
                    duration_text: fmt(v.duration || 0),
                    paused: !!v.paused
                };
                """
            ) or {}
        except Exception:
            return {}

    def _is_job_finished(self, icon_index: int) -> bool:
        """Switches briefly to parent chapter iframe to check if task point icon shows finished."""
        is_finished = False
        try:
            self.driver.switch_to.default_content()
            self.driver.switch_to.frame("iframe")
            icons = self.driver.find_elements(By.CLASS_NAME, "ans-job-icon-clear ")
            if not icons:
                icons = self.driver.find_elements(By.CSS_SELECTOR, '[class*="ans-insertvideo-online"], [class*="ans-job-icon"]')
            if 0 <= icon_index < len(icons):
                icon = icons[icon_index]
                parent = icon.find_element(By.XPATH, "..")
                parent_class = parent.get_attribute("class") or ""
                label = icon.get_attribute("aria-label") or ""
                is_finished = "ans-job-finished" in parent_class or label == "任务点已完成" or "ans-attach-ct ans-job-finished" in parent_class
        except Exception:
            pass
        finally:
            self._switch_to_video_frame(icon_index)
        return is_finished

    def _check_and_solve_in_video_quiz(self) -> None:
        """Detects in-video quiz modal (.tkTopic) and answers it using DeepSeek or random choice."""
        try:
            topics = self.driver.find_elements(By.CLASS_NAME, "tkTopic")
            if not topics or not topics[0].is_displayed():
                return

            element = topics[0]
            logger.info("In-video quiz detected")
            self._emit("in_video_quiz_detected", {})

            # Extract title and type
            title = ""
            q_type = "单选题"
            try:
                title = element.find_element(By.CLASS_NAME, "tkItem_title").text.strip()
            except Exception:
                pass

            try:
                q_type = element.find_element(By.CLASS_NAME, "tkTopic_type").text.strip()
            except Exception:
                try:
                    q_type = element.find_element(By.CLASS_NAME, "tkTopic_title").text.strip()
                except Exception:
                    pass

            options_list = element.find_elements(By.CSS_SELECTOR, ".tkItem_ul li")
            options_text = [opt.text.strip() for opt in options_list]
            submit_btn = element.find_element(By.ID, "videoquiz-submit")

            logger.info(f"Quiz question: {title} | Type: {q_type} | Options: {options_text}")

            # Answer
            if self.video_solve_mode == "ai" and self.solver:
                answers = self.solver.solve_single(title, options_text, q_type)
                logger.info(f"DeepSeek answered in-video quiz: {answers}")
                matched_idxs = self.solver.match_options(answers, options_text, q_type)
                if not matched_idxs and options_list:
                    matched_idxs = [0]

                for idx in matched_idxs:
                    if idx < len(options_list):
                        options_list[idx].click()
                        time.sleep(0.5)
            else:
                # Random option
                if options_list:
                    options_list[0].click()

            submit_btn.click()
            time.sleep(1)

            # Continue learning
            try:
                cont_btn = element.find_element(By.ID, "videoquiz-continue")
                if cont_btn.is_displayed():
                    cont_btn.click()
            except Exception:
                pass

            # Back to video
            try:
                back_btn = self.driver.find_element(
                    By.CSS_SELECTOR, '[class*="ans-videoquiz-back"]'
                )
                if back_btn.is_displayed():
                    back_btn.click()
            except Exception:
                pass

            logger.info("In-video quiz completed")
        except Exception as e:
            logger.debug(f"In-video quiz handling error: {e}")
