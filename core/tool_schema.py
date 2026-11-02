# -*- coding: utf-8 -*-
"""
Agent Tool Definition Schema for LLM Function Calling.
Compatible with OpenAI, Anthropic, Gemini, LangChain, and AutoGen.
"""
from typing import List, Dict, Any

AGENT_TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "xxt_get_status",
            "description": "Check Xuexitong agent environment readiness, including driver path, cookies, and DeepSeek AI configuration.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xxt_list_courses",
            "description": "Retrieve all enrolled courses under the current Xuexitong account.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xxt_get_chapters",
            "description": "Retrieve all chapter titles and their completion statuses for a given course name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "course_name": {
                        "type": "string",
                        "description": "Exact or partial name of the course (e.g. '艺术鉴赏', '音乐鉴赏')."
                    }
                },
                "required": ["course_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xxt_run_course",
            "description": "Execute automated headless study on a specific course for a designated duration.",
            "parameters": {
                "type": "object",
                "properties": {
                    "course_name": {
                        "type": "string",
                        "description": "Name of the course to run."
                    },
                    "duration_seconds": {
                        "type": "integer",
                        "description": "Maximum study duration in seconds (default: 3600 for 1 hour)."
                    },
                    "speed": {
                        "type": "number",
                        "description": "Video playback speed multiplier (e.g. 1.0, 2.0, 4.0; default: 2.0)."
                    },
                    "max_chapters": {
                        "type": "integer",
                        "description": "Maximum number of chapters to process (default: 15)."
                    }
                },
                "required": ["course_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xxt_solve_question",
            "description": "Solve a single quiz or homework question using DeepSeek AI with font decryption.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Title / body text of the question."
                    },
                    "q_type": {
                        "type": "string",
                        "enum": ["单选题", "多选题", "判断题", "填空题", "简答题"],
                        "description": "Question classification."
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of answer choices (for choice questions)."
                    }
                },
                "required": ["question"]
            }
        }
    }
]

def get_agent_tools_schema() -> List[Dict[str, Any]]:
    return AGENT_TOOLS_SCHEMA
