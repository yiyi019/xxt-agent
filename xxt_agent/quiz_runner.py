# -*- coding: utf-8 -*-
"""Chapter quiz and test automation for Xuexitong."""

import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional

from selenium.webdriver.common.by import By

from xxt_agent.ai_solver import DeepSeekSolver
from xxt_agent.font_decoder import FontDecoder
from xxt_agent.models import QuizAnswerResult, QuizQuestion, RunEvent

logger = logging.getLogger(__name__)



def _normalize_qtype(raw: str) -> str:
    """把 AI 返回的英文题型（Single Choice / Multiple Choice / True or False…）
    统一成中文，供后续分支判断使用。"""
    t = (raw or "").strip().lower()
    if not t:
        return "单选题"
    if ("multiple" in t) or ("多选" in raw) or ("checkbox" in t):
        return "多选题"
    if ("true" in t) or ("false" in t) or ("判断" in raw) or ("boolean" in t):
        return "判断题"
    if ("blank" in t) or ("填空" in raw):
        return "填空题"
    if ("short" in t) or ("essay" in t) or ("简答" in raw) or ("论述" in raw) or ("名词" in raw):
        return "简答题"
    if ("single" in t) or ("单选" in raw) or ("choice" in t):
        return "单选题"
    return raw

class QuizRunner:
    """Automates chapter test and homework questions using FontTools decryption and DeepSeek AI."""

    def __init__(
        self,
        driver,
        solver: DeepSeekSolver,
        font_decoder: Optional[FontDecoder] = None,
        submit_threshold: float = 1.0,
        event_callback: Optional[Callable[[RunEvent], None]] = None,
    ):
        self.driver = driver
        self.solver = solver
        self.font_decoder = font_decoder or FontDecoder()
        self.submit_threshold = submit_threshold
        self.event_callback = event_callback or (lambda e: None)

    def _emit(self, event_type: str, data: dict) -> None:
        event = RunEvent(event_type=event_type, data=data)
        try:
            self.event_callback(event)
        except Exception as e:
            logger.debug(f"Event callback error: {e}")

    def process_chapter_quizzes(self, course_name: str) -> int:
        """Finds all quiz iframes in current chapter and solves them."""
        self.driver.switch_to.default_content()
        try:
            self.driver.switch_to.frame("iframe")
        except Exception:
            return 0

        quiz_iframes = self.driver.find_elements(
            By.XPATH, '//iframe[contains(@src, "/ananas/modules/work/index.html")]'
        )
        if not quiz_iframes:
            return 0

        logger.info(f"Detected {len(quiz_iframes)} quiz iframe(s)")
        self._emit("quiz_batch_found", {"count": len(quiz_iframes)})

        solved_count = 0
        for i, q_iframe in enumerate(quiz_iframes):
            self.driver.switch_to.default_content()
            self.driver.switch_to.frame("iframe")

            # Check if finished
            try:
                preceding = q_iframe.find_element(By.XPATH, "preceding-sibling::div[1]")
                if preceding.get_attribute("aria-label") == "任务点已完成":
                    logger.info(f"Quiz #{i+1} already completed; skipping")
                    solved_count += 1
                    continue
            except Exception:
                pass

            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", q_iframe)
            success = self._solve_single_quiz(q_iframe, i + 1, len(quiz_iframes))
            if success:
                solved_count += 1

        return solved_count

    def _solve_single_quiz(self, test_frame, index: int, total: int) -> bool:
        """Parses questions, decodes fonts, solves with DeepSeek, fills answers, and submits."""
        logger.info(f"Entering quiz {index}/{total}...")
        self._emit("quiz_start", {"index": index, "total": total})

        self.driver.switch_to.frame(test_frame)
        try:
            self.driver.switch_to.frame("frame_content")
        except Exception:
            pass

        # Check if already submitted
        try:
            status_el = self.driver.find_elements(By.CLASS_NAME, "testTit_status")
            if status_el and "已完成" in status_el[0].text:
                logger.info(f"Quiz #{index} status shows '已完成'")
                return True
        except Exception:
            pass

        # 1. Decode obfuscated font
        char_map = self.font_decoder.extract_and_build_map_from_driver(self.driver)
        logger.info(f"Font decryption map loaded: {len(char_map)} character substitutions")

        # 2. Extract question elements
        question_elements = self.driver.find_elements(By.CSS_SELECTOR, ".singleQuesId")
        if not question_elements:
            logger.warning(f"No questions found in quiz #{index}")
            return False

        logger.info(f"Found {len(question_elements)} questions in quiz #{index}")
        parsed_questions: List[QuizQuestion] = []
        option_elements_map: Dict[int, List[Any]] = {}

        for q_idx, q_elem in enumerate(question_elements):
            # Extract raw title text
            try:
                title_elem = q_elem.find_element(
                    By.CSS_SELECTOR, '[class*="font-cxsecret"], [class*="fontLabel"], .clearfix'
                )
                raw_title = title_elem.text.strip()
            except Exception:
                raw_title = q_elem.text.strip().split("\n")[0]

            decoded_title = self.font_decoder.decode_text(raw_title, char_map)
            decoded_title = re.sub(r"\s+", " ", decoded_title).strip()

            # Determine question type
            q_type = "单选题"
            type_match = re.search(r"【(.*?)】", decoded_title)
            if type_match:
                q_type = type_match.group(1).strip()

            # Clean title
            title_text = re.sub(r"^[0-9]+[\.、\s]*【.*?】", "", decoded_title).strip()
            if not title_text:
                title_text = decoded_title

            # Extract options
            opts_elements = q_elem.find_elements(By.TAG_NAME, "li")
            if not opts_elements:
                # 诊断：新版测验若不用 <li>，把真实结构打出来
                try:
                    html = q_elem.get_attribute("outerHTML") or ""
                    kids = self.driver.execute_script(
                        "var q=arguments[0],o=[];"
                        "q.querySelectorAll('*').forEach(function(e){"
                        " if(o.length<12 && typeof e.className==='string' && e.className)"
                        "   o.push(e.tagName+'.'+e.className.slice(0,36));});"
                        "return o;", q_elem)
                    logger.warning(f"Q#{q_idx+1} 没有 <li> 选项；子元素: {kids}")
                    logger.warning(f"Q#{q_idx+1} HTML: {html[:400]}")
                except Exception as _e:
                    logger.debug(f"option diag failed: {_e}")
            option_elements_map[q_idx] = opts_elements

            decoded_options = []
            for opt_el in opts_elements:
                opt_raw = opt_el.text.strip()
                opt_decoded = self.font_decoder.decode_text(opt_raw, char_map)
                decoded_options.append(re.sub(r"\s+", " ", opt_decoded).strip())

            parsed_questions.append(
                QuizQuestion(
                    index=q_idx,
                    question_type=q_type,
                    title=title_text,
                    options=decoded_options,
                    raw_title=decoded_title,
                )
            )

        # 3. Solve with DeepSeek
        self._emit("quiz_solving", {"question_count": len(parsed_questions)})
        results = self.solver.bulk_solve(parsed_questions)

        # 4. Fill in answers
        success_answers = 0
        for res in results:
            q_idx = res.question_index
            q_elem = question_elements[q_idx]
            q_type = _normalize_qtype(res.question_type)
            answers = res.answers
            matched_idxs = res.matched_option_indices
            opt_elements = option_elements_map.get(q_idx, [])

            logger.info(f"Filling Q#{q_idx+1} ({q_type}) answers: {answers} -> matched {matched_idxs}")

            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", q_elem)
                time.sleep(0.3)

                if q_type in ["单选题", "判断题"]:
                    if matched_idxs and matched_idxs[0] < len(opt_elements):
                        target_opt = opt_elements[matched_idxs[0]]
                        if target_opt.get_attribute("aria-checked") != "true":
                            target_opt.click()
                        success_answers += 1
                elif q_type == "多选题":
                    for m_idx in matched_idxs:
                        if m_idx < len(opt_elements):
                            target_opt = opt_elements[m_idx]
                            if target_opt.get_attribute("aria-checked") != "true":
                                target_opt.click()
                                time.sleep(0.2)
                    if matched_idxs:
                        success_answers += 1
                elif q_type in ["简答题", "论述题", "名词解释"]:
                    text_frames = q_elem.find_elements(By.TAG_NAME, "iframe")
                    if text_frames and answers:
                        self.driver.switch_to.frame(text_frames[0])
                        p_elem = self.driver.find_element(By.TAG_NAME, "p")
                        if not p_elem.text.strip():
                            p_elem.click()
                            p_elem.send_keys(answers[0])
                        self.driver.switch_to.parent_frame()
                        success_answers += 1
                elif q_type == "填空题":
                    text_frames = q_elem.find_elements(By.TAG_NAME, "iframe")
                    for b_idx, ans_text in enumerate(answers):
                        if b_idx < len(text_frames):
                            self.driver.switch_to.frame(text_frames[b_idx])
                            p_elem = self.driver.find_element(By.TAG_NAME, "p")
                            if not p_elem.text.strip():
                                p_elem.click()
                                p_elem.send_keys(ans_text)
                            self.driver.switch_to.parent_frame()
                            time.sleep(0.2)
                    if answers:
                        success_answers += 1
            except Exception as e:
                logger.warning(f"Error filling answer for Q#{q_idx+1}: {e}")

        # 5. Submit or Save draft
        total_q = len(parsed_questions)
        rate = success_answers / total_q if total_q > 0 else 0.0
        logger.info(f"Quiz answered {success_answers}/{total_q} (Rate: {round(rate*100, 1)}%)")

        self._emit("quiz_answered", {
            "index": index,
            "solved": success_answers,
            "total": total_q,
            "rate": rate,
        })

        if rate >= self.submit_threshold:
            logger.info("Answer rate meets threshold; submitting quiz...")
            self._submit_quiz()
            return True

        # 未达阈值：只存草稿，**不能**算作已完成，
        # 否则 run_course 会误判章节已完成（这是此前“假成功”的源头）。
        logger.info(f"Answer rate {rate:.1%} below threshold {self.submit_threshold:.1%}; "
                    f"saving draft (NOT counted as completed)")
        self._save_draft()
        return False

    def _submit_quiz(self) -> None:
        try:
            btn = self.driver.find_element(By.CSS_SELECTOR, ".btnSubmit.workBtnIndex, .btnSubmit")
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            self.driver.execute_script("arguments[0].click();", btn)
            time.sleep(1)

            # Confirm dialog
            self.driver.switch_to.default_content()
            try:
                popok = self.driver.find_element(By.ID, "popok")
                popok.click()
                time.sleep(1)
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Error submitting quiz: {e}")

    def _save_draft(self) -> None:
        try:
            btn = self.driver.find_element(By.CSS_SELECTOR, ".btnSave.workBtnIndex, .btnSave")
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            self.driver.execute_script("arguments[0].click();", btn)
            time.sleep(1)
        except Exception as e:
            logger.warning(f"Error saving quiz draft: {e}")
