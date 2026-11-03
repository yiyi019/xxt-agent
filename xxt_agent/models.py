# -*- coding: utf-8 -*-
"""Data models for Xuexitong Agent system."""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import json


class QuestionType(str, Enum):
    SINGLE = "单选题"
    MULTIPLE = "多选题"
    JUDGE = "判断题"
    FILL = "填空题"
    ESSAY = "简答题"
    DISCUSSION = "论述题"
    EXPLAIN = "名词解释"
    OTHER = "其他"

    @classmethod
    def from_str(cls, text: str) -> "QuestionType":
        for item in cls:
            if item.value in text:
                return item
        return cls.OTHER


@dataclass
class QuizQuestion:
    index: int
    question_type: str
    title: str
    options: List[str] = field(default_factory=list)
    raw_title: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QuizAnswerResult:
    question_index: int
    question_type: str
    question_title: str
    answers: List[str]
    matched_option_indices: List[int] = field(default_factory=list)
    success: bool = True
    error_msg: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CourseInfo:
    name: str
    course_id: Optional[str] = None
    class_id: Optional[str] = None
    teacher: Optional[str] = None
    completed_points: int = 0
    total_points: int = 0
    progress_percent: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChapterInfo:
    index: int
    title: str
    has_tasks: bool = False
    completed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RunEvent:
    event_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class CourseRunSummary:
    course_name: str
    start_time: str
    end_time: str
    chapters_processed: int = 0
    videos_completed: int = 0
    quizzes_completed: int = 0
    ppt_completed: int = 0
    reading_completed: int = 0
    audio_completed: int = 0
    daily_limit_reached: bool = False
    daily_limit_reason: str = ""
    errors: List[str] = field(default_factory=list)
    success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
