# -*- coding: utf-8 -*-
"""
Anti-detection, popup bypass, and stealth injection for Xuexitong Agent.
Bypasses face verification overlays, focus-blur detection, and video pausing.
"""
from typing import Optional

JS_ANTI_BLUR = """
(function() {
    try {
        Object.defineProperty(document, 'hidden', { value: false, writable: false });
        Object.defineProperty(document, 'visibilityState', { value: 'visible', writable: false });
        Object.defineProperty(document, 'webkitVisibilityState', { value: 'visible', writable: false });
        window.addEventListener('blur', function(e) { e.stopImmediatePropagation(); }, true);
        document.addEventListener('visibilitychange', function(e) { e.stopImmediatePropagation(); }, true);
        window.onblur = null;
        document.onvisibilitychange = null;
    } catch(e) {}
})();
"""

JS_DISMISS_FACE = """
(function() {
    var selectors = [
        '.popDiv.faceCollectQrPop',
        '.chapterVideoFaceQrMaskDiv',
        '.maskDiv1',
        '.maskDiv',
        '.popDiv.wid640',
        '#maskDiv',
        '#maskDiv1'
    ];
    var removed = 0;
    selectors.forEach(function(sel) {
        var elements = document.querySelectorAll(sel);
        for (var i = 0; i < elements.length; i++) {
            elements[i].remove();
            removed++;
        }
    });
    document.body.style.overflow = 'auto';
    return removed;
})();
"""

JS_CONFIGURE_VIDEO = """
(function(speed) {
    var videos = document.querySelectorAll('video');
    var count = 0;
    for (var i = 0; i < videos.length; i++) {
        var v = videos[i];
        v.muted = true;
        try {
            v.playbackRate = speed;
        } catch(e) {}
        if (v.paused) {
            try { v.play(); } catch(e) {}
        }
        count++;
    }
    return count;
})(arguments[0]);
"""

def inject_anti_blur(driver) -> bool:
    """Inject script to neutralize focus and visibility change detection."""
    try:
        driver.execute_script(JS_ANTI_BLUR)
        return True
    except Exception:
        return False

def dismiss_face_popup(driver) -> int:
    """Dismiss and remove any face verification overlay popups."""
    try:
        removed = driver.execute_script(JS_DISMISS_FACE)
        return int(removed) if removed else 0
    except Exception:
        return 0

def configure_video(driver, speed: float = 2.0) -> int:
    """Mute and set playback speed on all visible video elements."""
    try:
        count = driver.execute_script(JS_CONFIGURE_VIDEO, speed)
        return int(count) if count else 0
    except Exception:
        return 0

def dismiss_mid_video_quiz(driver) -> bool:
    """Dismiss or submit in-video checkpoint questions to let the video continue."""
    js = """
    (function() {
        var submitBtn = document.querySelector('.ans-videoquiz-submit') || 
                        document.querySelector('#ext-gen1043') ||
                        document.querySelector('.ans-videoquiz-opt-btn');
        if (submitBtn) {
            // Select first option if none is selected
            var opt = document.querySelector('.ans-videoquiz-opt input') || document.querySelector('.ans-videoquiz-opt');
            if (opt) {
                opt.click();
            }
            submitBtn.click();
            return true;
        }
        return false;
    })();
    """
    try:
        return bool(driver.execute_script(js))
    except Exception:
        return False
