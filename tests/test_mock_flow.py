# -*- coding: utf-8 -*-
"""Mock-based tests for course progression and queue switching logic.

No browser, network, or account is involved: the Selenium driver and the
course runner are replaced with MagicMock objects.
"""
import unittest
from unittest.mock import MagicMock

from xxt_agent.agent import XXTAgent
from xxt_agent.config import XXTConfig
from xxt_agent.course_runner import CourseRunner
from xxt_agent.models import CourseRunSummary, RunEvent


def _make_runner(page_text: str) -> CourseRunner:
    """Builds a CourseRunner whose driver returns the given catalog page text."""
    runner = CourseRunner.__new__(CourseRunner)
    driver = MagicMock()
    driver.find_elements.return_value = []
    driver.execute_script.return_value = page_text
    runner.driver = driver
    runner.event_callback = lambda e: None
    return runner


class TestDailyLimitDetection(unittest.TestCase):
    def test_duration_limit_reached(self):
        res = _make_runner("今日已观看视频时长（分钟）: 45/45").check_course_daily_limits()
        self.assertTrue(res["has_limit"])
        self.assertTrue(res["limit_reached"])
        self.assertEqual((res["duration_cur"], res["duration_max"]), (45, 45))
        self.assertIn("45/45", res["reason"])

    def test_duration_limit_not_reached(self):
        res = _make_runner("今日已观看视频时长（分钟）: 20/45").check_course_daily_limits()
        self.assertTrue(res["has_limit"])
        self.assertFalse(res["limit_reached"])

    def test_task_quota_exhausted(self):
        # "今日可完成视频任务点" is a remaining quota: 0/5 means exhausted.
        res = _make_runner("今日可完成视频任务点: 0/5").check_course_daily_limits()
        self.assertTrue(res["limit_reached"])
        self.assertEqual((res["tasks_cur"], res["tasks_max"]), (0, 5))

    def test_task_quota_remaining(self):
        res = _make_runner("今日可完成视频任务点: 2/5").check_course_daily_limits()
        self.assertTrue(res["has_limit"])
        self.assertFalse(res["limit_reached"])

    def test_no_limit_text(self):
        res = _make_runner("第一章 绪论").check_course_daily_limits()
        self.assertFalse(res["has_limit"])
        self.assertFalse(res["limit_reached"])

    def test_driver_error_is_swallowed(self):
        runner = _make_runner("")
        runner.driver.execute_script.side_effect = RuntimeError("boom")
        res = runner.check_course_daily_limits()
        self.assertFalse(res["limit_reached"])


class TestRunCourseDailyLimit(unittest.TestCase):
    def test_returns_early_when_limit_already_reached(self):
        runner = _make_runner("")
        runner.get_chapters = MagicMock(return_value=[{"title": "第一章", "completed": True}])
        runner.select_course = MagicMock(return_value=True)
        runner.check_course_daily_limits = MagicMock(
            return_value={"limit_reached": True, "reason": "今日已观看视频时长达上限 (45/45分钟)"}
        )
        runner.find_and_enter_mission_point = MagicMock()

        summary = runner.run_course("艺术鉴赏")

        self.assertTrue(summary.daily_limit_reached)
        self.assertIn("45/45", summary.daily_limit_reason)
        runner.find_and_enter_mission_point.assert_not_called()


def _summary(name: str, **kwargs) -> CourseRunSummary:
    return CourseRunSummary(course_name=name, start_time="t0", end_time="t1", **kwargs)


class TestRunQueue(unittest.TestCase):
    def _agent(self, summaries):
        events = []
        agent = XXTAgent(config=XXTConfig(), event_callback=events.append)
        agent.driver = MagicMock()  # non-None so start() does not create a browser
        agent.driver.window_handles = ["main"]
        agent._course_runner = MagicMock()
        agent._course_runner.run_course.side_effect = summaries
        return agent, events

    def test_switches_to_next_course_on_daily_limit(self):
        agent, events = self._agent([
            _summary("A", daily_limit_reached=True, daily_limit_reason="上限"),
            _summary("B"),
        ])

        res = agent.run_queue(["A", "B"])

        self.assertEqual(res["courses_processed"], 2)
        self.assertEqual(res["statuses"], {"A": "daily_limit_reached", "B": "completed"})
        self.assertEqual(
            [c.args[0] for c in agent._course_runner.run_course.call_args_list], ["A", "B"]
        )
        switched = [e for e in events if e.event_type == "queue_course_switched"]
        self.assertEqual(len(switched), 1)
        self.assertEqual(switched[0].data["next_index"], 2)
        self.assertEqual(events[-1].event_type, "queue_complete")

    def test_last_course_limit_has_no_next_index(self):
        agent, events = self._agent([_summary("A", daily_limit_reached=True, daily_limit_reason="上限")])

        agent.run_queue(["A"])

        switched = [e for e in events if e.event_type == "queue_course_switched"]
        self.assertIsNone(switched[0].data["next_index"])

    def test_error_course_is_marked_and_queue_continues(self):
        agent, _ = self._agent([_summary("A", success=False, errors=["x"]), _summary("B")])

        res = agent.run_queue(["A", "B"])

        self.assertEqual(res["statuses"], {"A": "error", "B": "completed"})

    def test_extra_windows_are_closed_between_courses(self):
        agent, _ = self._agent([_summary("A"), _summary("B")])
        agent.driver.window_handles = ["main", "popup"]

        agent.run_queue(["A", "B"])

        agent.driver.close.assert_called()
        agent.driver.switch_to.window.assert_any_call("main")


if __name__ == "__main__":
    unittest.main()
