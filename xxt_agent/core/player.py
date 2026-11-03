# -*- coding: utf-8 -*-
"""
Video player and chapter execution engine for Xuexitong Agent.
Controls playback rate, monitors progression, bypasses checkpoints, and handles auto-advance.
"""
import time
from typing import Dict, Any, Optional, Callable
from selenium.webdriver.common.by import By

from .anti_detect import inject_anti_blur, dismiss_face_popup, configure_video, dismiss_mid_video_quiz

def switch_to_study_frame(driver) -> bool:
    """Switch to the outer learning content iframe."""
    driver.switch_to.default_content()
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    for f in iframes:
        fid = f.get_attribute("id") or ""
        fname = f.get_attribute("name") or ""
        if "iframe" in fid or "iframe" in fname:
            driver.switch_to.frame(f)
            return True
    if iframes:
        driver.switch_to.frame(iframes[0])
        return True
    return False

def switch_to_video_frame(driver) -> bool:
    """Switch into nested video player iframe."""
    video_iframes = driver.find_elements(By.XPATH, "//iframe[contains(@src, 'video') or contains(@class, 'ans-attach-online')]")
    if video_iframes:
        driver.switch_to.frame(video_iframes[0])
        return True
    # Check all iframes inside study frame
    sub_frames = driver.find_elements(By.TAG_NAME, "iframe")
    for sf in sub_frames:
        src = sf.get_attribute("src") or ""
        if "video" in src or "ananas" in src:
            driver.switch_to.frame(sf)
            return True
    return False

def get_video_stats(driver) -> Dict[str, Any]:
    """Retrieve current playback statistics via JavaScript."""
    js = """
    var v = document.querySelector('video');
    if (v) {
        return {
            found: true,
            current: v.currentTime,
            duration: v.duration,
            paused: v.paused,
            ended: v.ended
        };
    }
    return { found: false, current: 0, duration: 0, paused: true, ended: false };
    """
    try:
        res = driver.execute_script(js)
        return res if res else {"found": False, "current": 0, "duration": 0, "paused": True, "ended": False}
    except Exception:
        return {"found": False, "current": 0, "duration": 0, "paused": True, "ended": False}

def play_current_video(
    driver,
    speed: float = 2.0,
    max_seconds: int = 1800,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Dict[str, Any]:
    """
    Play the video task point in the current chapter with automatic speed and anti-detection.
    """
    switch_to_study_frame(driver)
    switch_to_video_frame(driver)

    inject_anti_blur(driver)
    configure_video(driver, speed)

    # Click big play button if present
    try:
        play_btn = driver.find_element(By.CSS_SELECTOR, ".vjs-big-play-button")
        if play_btn.is_displayed():
            play_btn.click()
            time.sleep(1)
    except Exception:
        pass

    start_time = time.time()
    last_reported = 0

    while True:
        elapsed = time.time() - start_time
        if elapsed > max_seconds:
            return {"ok": True, "reason": "max_seconds_reached", "watched_seconds": int(elapsed)}

        stats = get_video_stats(driver)
        if not stats.get("found"):
            # Check if outer frame has another video or finished
            return {"ok": True, "reason": "no_video_found", "watched_seconds": int(elapsed)}

        current = stats.get("current", 0)
        duration = stats.get("duration", 0)
        paused = stats.get("paused", True)
        ended = stats.get("ended", False)

        # Video completed
        if ended or (duration > 0 and current >= duration - 1):
            return {
                "ok": True,
                "reason": "video_completed",
                "current": current,
                "duration": duration,
                "watched_seconds": int(elapsed)
            }

        # Check and clear popups
        dismiss_face_popup(driver)
        dismiss_mid_video_quiz(driver)

        # Resume if paused unexpectedly
        if paused:
            configure_video(driver, speed)

        # Progress reporting
        pct = round((current / duration * 100), 1) if duration > 0 else 0
        if progress_callback and (time.time() - last_reported >= 10):
            progress_callback({
                "type": "video_progress",
                "current": int(current),
                "duration": int(duration),
                "percent": pct,
                "speed": speed,
                "elapsed": int(elapsed)
            })
            last_reported = time.time()

        time.sleep(3)

def next_chapter(driver) -> bool:
    """Navigate to the next chapter."""
    driver.switch_to.default_content()
    # Next button selectors in Xuexitong study interface
    selectors = [
        "//span[contains(@class, 'next') or contains(text(), '下一节')]",
        "//a[contains(@class, 'next') or contains(text(), '下一节')]",
        "//div[contains(@class, 'jb_btn') and contains(text(), '下一节')]"
    ]
    for sel in selectors:
        btns = driver.find_elements(By.XPATH, sel)
        for btn in btns:
            if btn.is_displayed():
                try:
                    btn.click()
                    time.sleep(3)
                    return True
                except Exception:
                    pass
    return False
