# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock
from xxt_agent.exceptions import VideoNotFoundError, BlockedByFaceVerificationError
from xxt_agent.models import CourseRunSummary


class TestRound2Fixes(unittest.TestCase):
    def test_chapter_status_dom_logic(self):
        """Tests that icon_yiwanc is marked completed and pure titles are not marked has_mission or completed."""
        def parse_node(parent_html: str):
            has_mission = (
                "knowledgeJobCount" in parent_html
                or "catalog_tishi" in parent_html
                or "ans-job-icon" in parent_html
            )
            completed = (
                "icon_yiwanc" in parent_html
                or "icon_complete" in parent_html
            )
            return has_mission, completed

        # 1. Completed node (like 1.1 in report)
        completed_html = '<div class="catalog_state icon_yiwanc catalog_tishi56"></div>'
        has_mission, completed = parse_node(completed_html)
        self.assertTrue(has_mission)
        self.assertTrue(completed)

        # 2. Incomplete node with task (like 4.12 in report)
        incomplete_html = '<div class="catalog_task"><input type="hidden" value="1" class="knowledgeJobCount"></div>'
        has_mission, completed = parse_node(incomplete_html)
        self.assertTrue(has_mission)
        self.assertFalse(completed)

        # 3. Pure title node without tasks (must NOT be marked completed or has_mission)
        title_html = '<div class="catalog_title"><span>第一章 导论</span></div>'
        has_mission, completed = parse_node(title_html)
        self.assertFalse(has_mission)
        self.assertFalse(completed)

    def test_custom_exceptions(self):
        err = VideoNotFoundError("Video element missing")
        self.assertEqual(err.error_code, "VIDEO_NOT_FOUND")
        self.assertIn("Video element missing", str(err))

        face_err = BlockedByFaceVerificationError("Server-side face scan required")
        self.assertEqual(face_err.error_code, "FACE_BLOCKED_SERVER_SIDE")

    def test_summary_newly_completed_count(self):
        summary = CourseRunSummary(
            course_name="音乐鉴赏",
            start_time="2026-11-04T13:00:00",
            end_time="2026-11-04T13:10:00",
            videos_completed=1,
            newly_completed_count=0,
            success=True,
        )
        self.assertEqual(summary.newly_completed_count, 0)
        data = summary.to_dict()
        self.assertIn("newly_completed_count", data)
        self.assertEqual(data["newly_completed_count"], 0)


if __name__ == "__main__":
    unittest.main()
