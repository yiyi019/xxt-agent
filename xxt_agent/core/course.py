# -*- coding: utf-8 -*-
"""
Course discovery and navigation module for Xuexitong Agent.
Lists enrolled courses, searches courses by name, and navigates chapters.
"""
import time
from typing import List, Dict, Any, Optional
from selenium.webdriver.common.by import By

COURSE_BASE_URL = "https://i.chaoxing.com/base"

def switch_to_courses_frame(driver) -> bool:
    """Ensure driver is in the course list frame context."""
    driver.switch_to.default_content()
    # Check if there is a main frame
    frames = driver.find_elements(By.TAG_NAME, "iframe")
    for frame in frames:
        frame_id = frame.get_attribute("id") or ""
        frame_src = frame.get_attribute("src") or ""
        if "frame_content" in frame_id or "visit/interaction" in frame_src or "course" in frame_src:
            driver.switch_to.frame(frame)
            return True
    return False

def list_courses(driver) -> List[Dict[str, Any]]:
    """
    Retrieve all courses enrolled under the active user account.
    """
    driver.get(COURSE_BASE_URL)
    time.sleep(2)
    switch_to_courses_frame(driver)

    courses = []
    # Try finding course items
    selectors = [
        "//div[contains(@class, 'course-item') or contains(@class, 'course')]//h3",
        "//ul[contains(@class, 'course-list')]//a[contains(@class, 'course-name') or @title]",
        "//a[contains(@href, 'studentcourse') or contains(@href, 'course')]",
        "//h3[contains(@class, 'title')]/a",
        "//span[contains(@class, 'course-name')]"
    ]

    for sel in selectors:
        elements = driver.find_elements(By.XPATH, sel)
        if elements:
            for el in elements:
                title = el.get_attribute("title") or el.text.strip()
                href = el.get_attribute("href") or ""
                if title and len(title) > 1 and not any(c["title"] == title for c in courses):
                    # Filter out system navigational buttons
                    if title not in ["首页", "我", "设置", "退出", "收起", "展开"]:
                        courses.append({
                            "title": title,
                            "url": href
                        })
            if courses:
                break

    driver.switch_to.default_content()
    return courses

def select_course(driver, course_name: str) -> Dict[str, Any]:
    """
    Find and open a specific course by name.
    """
    driver.get(COURSE_BASE_URL)
    time.sleep(2)
    switch_to_courses_frame(driver)

    # Search course element
    found_elem = None
    elements = driver.find_elements(By.XPATH, "//a | //h3/a | //span")
    for el in elements:
        text = el.get_attribute("title") or el.text.strip()
        if course_name in text:
            found_elem = el
            break

    if not found_elem:
        driver.switch_to.default_content()
        return {"ok": False, "error": f"Course '{course_name}' not found in course list."}

    initial_handles = driver.window_handles
    found_elem.click()
    time.sleep(3)

    # Handle new tab switch
    new_handles = driver.window_handles
    if len(new_handles) > len(initial_handles):
        driver.switch_to.window(new_handles[-1])

    return {
        "ok": True,
        "course": course_name,
        "current_url": driver.current_url
    }

def get_chapters(driver) -> List[Dict[str, Any]]:
    """
    Extract chapter list and completion status for the current course.
    """
    driver.switch_to.default_content()
    chapters = []
    # Common chapter node selectors in Xuexitong
    nodes = driver.find_elements(By.XPATH, "//div[contains(@class, 'posCatalog_name') or contains(@class, 'level_two')]")
    for idx, node in enumerate(nodes):
        title = node.text.strip()
        if title:
            # Check if there is an unfinished icon or orange indicator
            parent = node.find_element(By.XPATH, "..")
            is_completed = "icon_complete" in parent.get_attribute("innerHTML") or "ans-job-icon-clear" not in parent.get_attribute("innerHTML")
            chapters.append({
                "index": idx + 1,
                "title": title,
                "completed": is_completed
            })
    return chapters
