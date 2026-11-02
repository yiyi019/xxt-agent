# -*- coding: utf-8 -*-
"""
DeepSeek AI question solver for Xuexitong Agent.
Calls DeepSeek API with specialized prompts for choice, judgment, fill-in, and essay questions.
"""
import re
import json
import requests
from typing import Dict, Any, List, Optional

class DeepSeekSolver:
    MODELS = ["deepseek-v4.1-flash", "deepseek-flash", "deepseek-chat"]
    API_URL = "https://api.deepseek.com/chat/completions"

    def __init__(self, api_key: str, model: str = "deepseek-v4.1-flash", temperature: float = 0.6):
        self.api_key = api_key.strip()
        self.model = model
        self.temperature = temperature

    def solve(self, title: str, q_type: str = "单选题", options: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Solve a question using DeepSeek API.
        Returns structured dictionary with answers and metadata.
        """
        if not self.api_key:
            return {
                "ok": False,
                "error": "DeepSeek API key not configured.",
                "answer": []
            }

        # Build prompt based on question type
        options_text = ""
        if options:
            options_text = "\n选项：\n" + "\n".join(options)

        if q_type in ["单选题", "判断题"]:
            prompt = (
                "你是一个答题助手。请直接给出题目的正确答案，不要任何多余的解释或寒暄。\n"
                "答案必须严格从给出的选项中选择，只能有一个答案。\n"
                "返回格式必须是一个 JSON 字符串数组，例如：[\"答案内容\"]\n\n"
                f"【{q_type}】{title}{options_text}"
            )
        elif q_type == "多选题":
            prompt = (
                "你是一个答题助手。请直接给出题目的正确答案，不要任何多余的解释或寒暄。\n"
                "答案必须严格从给出的选项中选择，可以包含多个正确选项。\n"
                "返回格式必须是一个 JSON 字符串数组，例如：[\"答案1\", \"答案2\"]\n\n"
                f"【{q_type}】{title}{options_text}"
            )
        elif q_type in ["填空题"]:
            prompt = (
                "你是一个答题助手。请直接给出题目的填空答案，不要任何多余的解释或寒暄。\n"
                "有多少个空，返回的数组中就必须有多少个元素。\n"
                "返回格式必须是一个 JSON 字符串数组，例如：[\"空1答案\", \"空2答案\"]\n\n"
                f"【{q_type}】{title}{options_text}"
            )
        else:
            prompt = (
                "你是一个答题助手。请直接给出题目的回答，语言简练精炼，不要多余的寒暄。\n"
                "返回格式必须是一个 JSON 字符串数组，例如：[\"简答答案\"]\n\n"
                f"【{q_type}】{title}{options_text}"
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Model trial order: user chosen model first, then fallback list
        models_to_try = [self.model] + [m for m in self.MODELS if m != self.model]

        last_err = ""
        for mod in models_to_try:
            payload = {
                "model": mod,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.temperature,
                "stream": False
            }
            try:
                res = requests.post(self.API_URL, headers=headers, json=payload, timeout=40)
                if res.status_code == 200:
                    data = res.json()
                    content = data["choices"][0]["message"]["content"].strip()
                    answers = self._parse_json_answers(content)
                    return {
                        "ok": True,
                        "question": title,
                        "q_type": q_type,
                        "answer": answers,
                        "raw_response": content,
                        "model": mod
                    }
                else:
                    last_err = f"HTTP {res.status_code}: {res.text[:200]}"
            except Exception as e:
                last_err = str(e)

        return {
            "ok": False,
            "error": f"DeepSeek API failed on all models: {last_err}",
            "answer": []
        }

    def _parse_json_answers(self, text: str) -> List[str]:
        """Extract answers from model response."""
        # Try direct json parse
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed]
        except Exception:
            pass

        # Try regex extract array [...]
        match = re.search(r'\[(.*?)\]', text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed]
            except Exception:
                pass
            # Split by comma
            raw_items = match.group(1).split(",")
            clean = [re.sub(r'[\'\"`]', '', item).strip() for item in raw_items if item.strip()]
            if clean:
                return clean

        # Fallback: clean lines
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return lines if lines else [text.strip()]
