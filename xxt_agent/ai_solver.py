# -*- coding: utf-8 -*-
"""DeepSeek AI Question Solver for Xuexitong."""

import ast
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

from xxt_agent.exceptions import SolverError
from xxt_agent.models import QuestionType, QuizQuestion, QuizAnswerResult

logger = logging.getLogger(__name__)


class DeepSeekSolver:
    """Solves Xuexitong quiz questions using the DeepSeek API."""

    FALLBACK_MODELS = ["deepseek-v4.1-flash", "deepseek-flash", "deepseek-chat"]

    def __init__(
        self,
        api_key: str,
        primary_model: str = "deepseek-v4.1-flash",
        base_url: str = "https://api.deepseek.com",
        timeout: int = 45,
    ):
        self.api_key = api_key.strip()
        self.primary_model = primary_model.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        self.models = [self.primary_model]
        for m in self.FALLBACK_MODELS:
            if m not in self.models:
                self.models.append(m)
        self.working_model: Optional[str] = None

    def _call_api(self, prompt: str, temperature: float = 0.3) -> str:
        """Sends request to DeepSeek API with automatic model fallback and working model caching."""
        if not self.api_key:
            raise SolverError("DeepSeek API Key is empty", details={"api_key": ""})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # If a working model has already succeeded, try it first
        candidate_models = list(self.models)
        if self.working_model and self.working_model in candidate_models:
            candidate_models.remove(self.working_model)
            candidate_models.insert(0, self.working_model)

        last_err = ""
        for model in candidate_models:
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "stream": False,
            }
            try:
                url = f"{self.base_url}/chat/completions"
                logger.debug(f"Calling DeepSeek API with model: {model}")
                res = requests.post(url, headers=headers, json=payload, timeout=self.timeout)

                if res.status_code == 200:
                    data = res.json()
                    choices = data.get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                        self.working_model = model
                        return content.strip()
                    raise SolverError("Empty choices in DeepSeek response", details={"response": data})
                else:
                    last_err = f"Model {model} returned HTTP {res.status_code}: {res.text}"
                    logger.warning(last_err)
            except Exception as e:
                last_err = f"Model {model} connection error: {e}"
                logger.warning(last_err)

        raise SolverError(f"All DeepSeek models failed. Last error: {last_err}")

    def solve_single(
        self,
        question_title: str,
        options: Optional[List[str]] = None,
        question_type: str = "单选题",
    ) -> List[str]:
        """
        Solves a single question and returns a list of answer strings.
        """
        options = options or []
        opts_str = "\n".join(options) if options else "无选项"

        if question_type in ["单选题", "判断题"]:
            prompt = (
                "你是一个学术考试答题助手。请回答以下单项选择题或判断题。\n"
                "【严格规则】：\n"
                "1. 仅从提供的选项中选择唯一的正确答案。\n"
                "2. 不要任何解释或分析，仅以 JSON 列表格式返回答案，例如: [\"A\"] 或 [\"选项文本\"]\n\n"
                f"题目类型：{question_type}\n"
                f"题目内容：{question_title}\n"
                f"候选选项：\n{opts_str}\n"
            )
        elif question_type == "多选题":
            prompt = (
                "你是一个学术考试答题助手。请回答以下多项选择题。\n"
                "【严格规则】：\n"
                "1. 从提供的选项中选择所有正确答案。\n"
                "2. 不要任何解释或分析，仅以 JSON 列表格式返回答案，例如: [\"A\", \"B\"] 或 [\"选项1\", \"选项2\"]\n\n"
                f"题目类型：{question_type}\n"
                f"题目内容：{question_title}\n"
                f"候选选项：\n{opts_str}\n"
            )
        elif question_type in ["简答题", "论述题", "名词解释"]:
            prompt = (
                "你是一个学术考试答题助手。请回答以下简答/论述题。\n"
                "【严格规则】：\n"
                "1. 语言凝练，字数适中（50-150字），直击要点。\n"
                "2. 仅以 JSON 列表格式返回纯文本答案，例如: [\"答案文字内容\"]\n\n"
                f"题目类型：{question_type}\n"
                f"题目内容：{question_title}\n"
            )
        elif question_type == "填空题":
            prompt = (
                "你是一个学术考试答题助手。请回答以下填空题。\n"
                "【严格规则】：\n"
                "1. 题中有几个空，列表中就按顺序包含几个答案字符串。\n"
                "2. 仅以 JSON 列表格式返回答案，例如: [\"空1答案\", \"空2答案\"]\n\n"
                f"题目类型：{question_type}\n"
                f"题目内容：{question_title}\n"
            )
        else:
            prompt = (
                f"请回答以下题目，直接给出答案，格式为JSON列表，例如: [\"答案\"]\n\n"
                f"题目：{question_title}\n"
                f"选项：\n{opts_str}\n"
            )

        raw_output = self._call_api(prompt)
        return self._parse_answer_list(raw_output)

    def bulk_solve(self, questions: List[QuizQuestion]) -> List[QuizAnswerResult]:
        """
        Solves multiple questions, matching answers against provided option elements.
        """
        results: List[QuizAnswerResult] = []

        # If 3 or fewer questions, solve sequentially to maximize accuracy; if many, solve per question
        for q in questions:
            try:
                answers = self.solve_single(q.title, q.options, q.question_type)
                matched_indices = self.match_options(answers, q.options, q.question_type)
                results.append(
                    QuizAnswerResult(
                        question_index=q.index,
                        question_type=q.question_type,
                        question_title=q.title,
                        answers=answers,
                        matched_option_indices=matched_indices,
                        success=bool(answers),
                    )
                )
            except Exception as e:
                logger.error(f"Failed to solve question #{q.index}: {e}")
                results.append(
                    QuizAnswerResult(
                        question_index=q.index,
                        question_type=q.question_type,
                        question_title=q.title,
                        answers=[],
                        matched_option_indices=[],
                        success=False,
                        error_msg=str(e),
                    )
                )

        return results

    def _parse_answer_list(self, raw_text: str) -> List[str]:
        """Parses LLM output into a clean list of string answers."""
        if not raw_text:
            return []

        cleaned = raw_text.strip()
        # Remove thinking blocks if present
        cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL).strip()

        # Check for markdown code fence anywhere
        code_block = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL)
        if code_block:
            json_cand = code_block.group(1).strip()
            try:
                parsed = json.loads(json_cand)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except Exception:
                pass

        # Try JSON array parsing on the whole text
        match = re.search(r"\[(.*?)\]", cleaned, flags=re.DOTALL)
        if match:
            candidate = match.group(0)
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except Exception:
                try:
                    parsed = ast.literal_eval(candidate)
                    if isinstance(parsed, (list, tuple)):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except Exception:
                    pass

        # Check for multiple single letter answers e.g. "A, B, C" or "A/B/C"
        parts = [p.strip() for p in re.split(r"[/,\n、\s]+", cleaned) if p.strip()]
        if parts and all(re.match(r"^[\(\[\{]?[A-Ga-g][\)\]\}\.\、\:]?$", p) for p in parts):
            return [re.sub(r"[\(\)\[\]\{\}\.\、\:\s]", "", p).upper() for p in parts]

        # Check for concatenated letters e.g. "ABCD"
        if re.match(r"^[A-Ga-g]{2,}$", cleaned):
            return list(cleaned.upper())

        # Fallback: check for single letter answer e.g. "A"
        letter_match = re.findall(r"\b([A-Ga-g])\b", cleaned)
        if letter_match:
            return [l.upper() for l in letter_match]

        # Fallback: split by slash or comma or newline
        lines = [line.strip() for line in re.split(r"[/,\n]+", cleaned) if line.strip()]
        return lines if lines else [cleaned]

    @staticmethod
    def match_options(
        answers: List[str],
        options: List[str],
        question_type: str = "单选题",
    ) -> List[int]:
        """
        Given answers and candidate option strings (e.g. ['A. 音乐', 'B. 舞蹈']),
        returns the indices of options that match.
        """
        if not answers or not options:
            return []

        matched_indices: List[int] = []
        letters = [chr(ord("A") + i) for i in range(len(options))]

        # Flatten any concatenated letters e.g. ["ABCD"] or ["A, B"] in answers
        expanded_answers: List[str] = []
        for ans in answers:
            ans_str = str(ans).strip()
            # If answer is like "ABCD" or "ABC"
            if re.match(r"^[A-Ga-g]{2,}$", ans_str):
                expanded_answers.extend(list(ans_str.upper()))
            # If answer is comma or slash separated letters like "A, B"
            elif "," in ans_str or "/" in ans_str or "、" in ans_str:
                splits = [s.strip() for s in re.split(r"[,/、\s]+", ans_str) if s.strip()]
                if all(re.match(r"^[A-Ga-g]$", s, re.I) for s in splits):
                    expanded_answers.extend([s.upper() for s in splits])
                else:
                    expanded_answers.append(ans_str)
            else:
                expanded_answers.append(ans_str)

        for ans in expanded_answers:
            ans_clean = ans.strip().strip("'\"")

            # Check single letter with optional punctuation, e.g. "A", "A.", "(A)", "[A]", "A、"
            letter_match = re.match(r"^[\(\[\{\<]?\s*([A-Za-z])\s*[\)\]\}\>\.\、\:\s]*$", ans_clean)
            if letter_match:
                single_letter = letter_match.group(1).upper()
                if single_letter in letters:
                    idx = letters.index(single_letter)
                    if idx not in matched_indices:
                        matched_indices.append(idx)
                    continue

            # Check if answer is a substring of option, or option substring of answer
            ans_lower = ans_clean.lower()
            ans_text_only = re.sub(r"^[\(\[\{]?[0-9A-Za-z][\)\]\}\.\、\:\s]+", "", ans_lower).strip()

            found = False
            for idx, opt in enumerate(options):
                opt_lower = opt.lower().strip()
                opt_text_only = re.sub(r"^[\(\[\{]?[0-9A-Za-z][\)\]\}\.\、\:\s]+", "", opt_lower).strip()

                if ans_text_only and len(ans_text_only) >= 1:
                    if ans_text_only in opt_text_only or opt_text_only in ans_text_only:
                        if idx not in matched_indices:
                            matched_indices.append(idx)
                        found = True
                        break

            # Handle Judgment questions (对 / 错 / 正确 / 错误)
            if not found and question_type == "判断题":
                ans_upper = ans_clean.upper()
                is_true = any(k in ans_upper for k in ["对", "正确", "√", "TRUE", "T", "YES", "Y"])
                is_false = any(k in ans_upper for k in ["错", "错误", "×", "FALSE", "F", "NO", "N"])

                # Determine which option is True and which is False dynamically from option content
                true_idx = None
                false_idx = None
                for idx, opt in enumerate(options):
                    opt_u = opt.upper()
                    if any(k in opt_u for k in ["对", "正确", "√", "TRUE"]):
                        true_idx = idx
                    elif any(k in opt_u for k in ["错", "错误", "×", "FALSE"]):
                        false_idx = idx

                # Default fallback if keywords not found in options: 0 is True, 1 is False
                if true_idx is None:
                    true_idx = 0 if len(options) > 0 else None
                if false_idx is None:
                    false_idx = 1 if len(options) > 1 else None

                if is_true and true_idx is not None and true_idx not in matched_indices:
                    matched_indices.append(true_idx)
                elif is_false and false_idx is not None and false_idx not in matched_indices:
                    matched_indices.append(false_idx)

        return sorted(matched_indices) if question_type == "多选题" else matched_indices
