# -*- coding: utf-8 -*-
import json
import unittest
from xxt_agent.models import CourseInfo, CourseRunSummary, QuestionType, QuizQuestion, RunEvent


class TestModels(unittest.TestCase):
    def test_quiz_question_serialization(self):
        q = QuizQuestion(
            index=1,
            question_type=QuestionType.SINGLE.value,
            title="何为乐理？",
            options=["A. 音乐基础理论", "B. 舞蹈动作"],
        )
        d = q.to_dict()
        self.assertEqual(d["title"], "何为乐理？")
        self.assertEqual(len(d["options"]), 2)

    def test_run_event_json(self):
        ev = RunEvent(event_type="video_progress", data={"percent": 50.0})
        s = ev.to_json()
        parsed = json.loads(s)
        self.assertEqual(parsed["event_type"], "video_progress")
        self.assertEqual(parsed["data"]["percent"], 50.0)

    def test_course_run_summary(self):
        s = CourseRunSummary(
            course_name="音乐鉴赏",
            start_time="2026-11-02T20:00:00",
            end_time="2026-11-02T20:10:00",
            videos_completed=3,
            quizzes_completed=1,
            success=True,
        )
        d = s.to_dict()
        self.assertEqual(d["videos_completed"], 3)
        self.assertTrue(d["success"])


if __name__ == "__main__":
    unittest.main()
