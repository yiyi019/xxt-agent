# -*- coding: utf-8 -*-
"""Automated Chaoxing Face Verification Bypass for Xuexitong."""

import hashlib
import io
import json
import logging
import random
import time
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, quote, unquote, urlparse

import numpy as np
import requests
from PIL import Image

from xxt_agent.exceptions import FaceVerificationRequiredError

logger = logging.getLogger(__name__)


class FaceBypass:
    """Handles Chaoxing face recognition popups using API signature bypass and image perturbation."""

    DES_KEY = "Z(AfY@XS"
    FACE_ENC_SALT = "uWwjeEKsri"
    FACE_API_TOKEN = "4faa8662c59590c6f43ae9fe5b002b42"
    USER_AGENT = (
        "Mozilla/5.0 (Linux; Android 12; SM-N9006 Build/V417IR; wv) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
        "Chrome/101.0.4951.61 Safari/537.36 "
        "(schild:a6aba57d51661f412e8b8d2177adf8b4) (device:SM-N9006) "
        "Language/zh_CN com.chaoxing.mobile/ChaoXingStudy_3_6.4.5_android_phone_10831_263 "
        "(@Kalimdor)_6e98c17c08204755905e1537b1933e72"
    )

    # 新版「准入级人脸采集」页面没有任何 face* class，只能靠正文文案识别
    FACE_TEXT_MARKERS = (
        "Facial information collection",
        "collect facial information",
        "人脸信息采集",
        "人脸采集",
        "请使用手机APP",
        "请使用手机 APP",
        "请扫描下方二维码",
    )

    POPUP_SELECTORS = [
        ".chapterVideoFaceMaskDiv",
        ".maskDiv",
        ".maskDiv1",
        ".chapterVideoFaceQrMaskDiv",
        ".faceCollectQrPop",
        ".faceCollectQrPopVideo",
        ".popDiv1.wid640",
        ".popDiv.wid640.faceCollectQrPop.popClass",
        ".maskDiv1.chapterVideoFaceQrMaskDiv",
        ".maskDiv1.starttippop.faceRecognition_1.chapterVideoFaceMaskDiv",
    ]

    def __init__(self, driver, max_retries: int = 5, retry_delay: int = 3):
        self.driver = driver
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.http = requests.Session()
        self.is_processing = False

    def is_popup_present(self, check_top: bool = False) -> bool:
        """Checks if a face verification modal or mask is currently displayed."""
        if check_top:
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass

        for sel in self.POPUP_SELECTORS:
            try:
                elements = self.driver.find_elements("css selector", sel)
                for el in elements:
                    if el.is_displayed():
                        return True
            except Exception:
                continue

        # Also check for QR element directly
        try:
            el = self.driver.find_element("id", "fcqrimg")
            if el and el.is_displayed():
                return True
        except Exception:
            pass

        # 兜底：按正文文本判断。
        # 新版的「准入级人脸采集」页面不带任何 face* class，只有一段文案，
        # 上面的选择器全部匹配不到，会导致 bypass() 永远不被触发。
        try:
            self.driver.switch_to.default_content()
            body = self.driver.execute_script(
                "return (document.body && document.body.innerText) || ''"
            ) or ""
            if any(k in body for k in self.FACE_TEXT_MARKERS):
                return True
        except Exception:
            pass

        return False

    def _get_cookie_header(self) -> str:
        try:
            return "; ".join(f"{c['name']}={c['value']}" for c in self.driver.get_cookies())
        except Exception:
            return ""

    def _get_uid(self) -> Optional[str]:
        try:
            for c in self.driver.get_cookies():
                if c.get("name") in ["_uid", "UID"]:
                    return str(c.get("value"))
        except Exception:
            pass
        return None

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        h = {
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Referer": self.driver.current_url or "https://mooc1.chaoxing.com",
            "Cookie": self._get_cookie_header(),
        }
        if extra:
            h.update(extra)
        return h

    @classmethod
    def add_inf_enc_sign(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        parts = [
            f"{quote(str(k), safe='')}={quote(str(v), safe='')}"
            for k, v in sorted(params.items())
            if v is not None
        ]
        query = "&".join(parts) + f"&DESKey={cls.DES_KEY}"
        signed = dict(params)
        signed["inf_enc"] = hashlib.md5(query.encode("utf-8")).hexdigest()
        return signed

    def _extract_qr_url(self) -> Optional[str]:
        try:
            return self.driver.execute_script(
                "var el = document.getElementById('fcqrimg'); return (el && el.src) ? el.src : null;"
            )
        except Exception:
            return None

    @staticmethod
    def _parse_url_params(url: str) -> Dict[str, str]:
        params: Dict[str, str] = {}
        if not url:
            return params
        try:
            parsed = urlparse(url)
            for k, v in parse_qs(parsed.query).items():
                params[k] = v[0]
            content = params.get("content")
            if content:
                decoded = unquote(content)
                inner = parse_qs(urlparse(decoded).query)
                for k, v in inner.items():
                    params[k] = v[0]
                if "enc" in inner:
                    params["qrcEnc"] = inner["enc"][0]
        except Exception as e:
            logger.debug(f"URL parsing error: {e}")
        return params

    def _extract_hidden_fields(self) -> Dict[str, str]:
        try:
            return self.driver.execute_script(
                """
                var fields = {};
                document.querySelectorAll('input[type="hidden"]').forEach(function(el) {
                    if (el.id && el.value) fields[el.id] = el.value;
                });
                return fields;
                """
            ) or {}
        except Exception:
            return {}

    def get_all_params(self) -> Optional[Dict[str, str]]:
        qr_url = self._extract_qr_url()
        qr_params = self._parse_url_params(qr_url) if qr_url else {}
        hidden = self._extract_hidden_fields()

        cur_params: Dict[str, str] = {}
        try:
            p = urlparse(self.driver.current_url)
            for k, v in parse_qs(p.query).items():
                cur_params[k] = v[0]
        except Exception:
            pass

        uuid = qr_params.get("uuid") or hidden.get("uuid") or cur_params.get("uuid")
        if not uuid and not qr_url:
            return None

        all_params = {}
        all_params.update(hidden)
        all_params.update(qr_params)
        all_params["courseid"] = (
            qr_params.get("courseid")
            or hidden.get("curCourseId")
            or hidden.get("fccourseId")
            or cur_params.get("courseid")
            or ""
        )
        all_params["clazzid"] = (
            qr_params.get("clazzid")
            or hidden.get("curClazzId")
            or hidden.get("fcclazzId")
            or cur_params.get("clazzid")
            or ""
        )
        all_params["cpi"] = (
            qr_params.get("cpi")
            or hidden.get("curCpi")
            or hidden.get("fccpi")
            or cur_params.get("cpi")
            or ""
        )
        all_params["knowledgeid"] = (
            qr_params.get("knowledgeid")
            or hidden.get("curChapterId")
            or hidden.get("curKnowledgeId")
            or cur_params.get("knowledgeid")
            or "0"
        )
        all_params["uuid"] = uuid or ""
        all_params["qrcEnc"] = qr_params.get("qrcEnc") or qr_params.get("enc") or hidden.get("qrcEnc") or ""

        return all_params

    @staticmethod
    def process_image(img_bytes: bytes) -> bytes:
        """Applies subtle perturbation to bypass duplicate face verification check."""
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        arr = np.array(img, dtype=np.int32)
        h, w = arr.shape[:2]

        perturbation_count = int(min(200, arr.size / 50))
        for _ in range(perturbation_count):
            y = random.randrange(h)
            x = random.randrange(w)
            for c in range(3):
                delta = random.randint(-10, 10)
                arr[y, x, c] = max(0, min(255, arr[y, x, c] + delta))

        noise_count = int(min(50, w * h / 1000))
        for _ in range(noise_count):
            y = random.randrange(h)
            x = random.randrange(w)
            b = 255 if random.random() > 0.5 else 0
            arr[y, x, 0] = arr[y, x, 1] = arr[y, x, 2] = b

        bright = random.randint(-5, 5)
        arr = np.clip(arr + bright, 0, 255).astype(np.uint8)

        out = Image.fromarray(arr, "RGB")
        buf = io.BytesIO()
        out.save(buf, format="JPEG", quality=80)
        return buf.getvalue()

    def get_user_token(self) -> str:
        url = "https://pan-yz.chaoxing.com/api/token/uservalid"
        r = self.http.get(url, headers=self._headers(), timeout=15)
        r.raise_for_status()
        data = r.json()
        token = data.get("_token")
        if not token:
            raise RuntimeError(f"Failed to get upload token: {data}")
        return token

    def get_user_face_image(self, puid: str) -> bytes:
        url = "https://passport2-api.chaoxing.com/api/getUserFaceid"
        enc = hashlib.md5((puid + self.FACE_ENC_SALT).encode("utf-8")).hexdigest()
        params = {
            "enc": enc,
            "token": self.FACE_API_TOKEN,
            "_time": int(time.time() * 1000),
        }
        signed = self.add_inf_enc_sign(params)

        r = self.http.get(url, params=signed, headers=self._headers(), timeout=15)
        r.raise_for_status()
        data = r.json()

        if data.get("result") != 1:
            raise RuntimeError(f"User face not registered or API error: {data}")

        http_url = (data.get("data") or {}).get("http")
        if not http_url:
            raise RuntimeError(f"No face image URL in response: {data}")

        r2 = self.http.get(http_url, headers=self._headers(), timeout=20)
        r2.raise_for_status()
        return r2.content

    def upload_face_image(self, img_bytes: bytes, puid: str, upload_token: str) -> str:
        url = f"https://pan-yz.chaoxing.com/upload?uploadtype=face&_token={upload_token}"
        files = {"file": (f"{puid}.jpg", img_bytes, "image/jpeg")}
        data = {"puid": puid}

        r = self.http.post(url, files=files, data=data, headers=self._headers(), timeout=30)
        r.raise_for_status()
        j = r.json()
        obj_id = j.get("objectId")
        if not obj_id:
            raise RuntimeError(f"Upload failed: {j}")
        return obj_id

    def submit_verification(self, params: Dict[str, str], object_id: str) -> bool:
        url = (
            f"https://mooc1-api.chaoxing.com/mooc-ans/qr/updateqrstatus"
            f"?uuid2={params.get('uuid', '')}&clazzId2={params.get('clazzid', '')}"
        )
        fields = [
            ("clazzId", params.get("clazzid") or ""),
            ("courseId", params.get("courseid") or ""),
            ("uuid", params.get("uuid") or ""),
            ("qrcEnc", params.get("qrcEnc") or ""),
            ("cpi", params.get("cpi") or ""),
            ("liveDetectionStatus", "1"),
            ("objectId", object_id),
            ("knowledgeid", params.get("knowledgeid") or "0"),
            ("signt", params.get("signt") or ""),
            ("signk", params.get("signk") or ""),
            ("cxtime", params.get("cxtime") or ""),
            ("cxcid", params.get("cxcid") or ""),
            ("videojobid", params.get("videojobid") or ""),
            ("videoCollectTime", params.get("realCollectTime") or "0"),
            ("chaptervideoobjectid", params.get("chaptervideoobjectid") or ""),
        ]
        files = [(k, (None, v)) for k, v in fields]
        headers = self._headers({
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
        })

        try:
            r = self.http.post(url, files=files, headers=headers, timeout=20)
            data = r.json()
            code = data.get("code")
            msg = data.get("msg") or data.get("message")
            ok = data.get("status")
            if code == 0 and ok is True and msg == "通过":
                logger.info("Face verification passed successfully via API")
                return True
            logger.warning(f"Face verification attempt rejected: {data}")
        except Exception as e:
            logger.warning(f"Face verification submission request failed: {e}")

        return False

    def bypass(self) -> bool:
        """Executes full face bypass flow; falls back to DOM removal if necessary."""
        if self.is_processing:
            return False

        self.is_processing = True
        try:
            puid = self._get_uid()
            if not puid:
                logger.warning("No _uid found in cookies, trying DOM removal fallback")
                return self.force_remove_popup()

            params = self.get_all_params()
            if not params or not params.get("uuid"):
                time.sleep(1)
                params = self.get_all_params()

            if params and params.get("uuid"):
                token = self.get_user_token()
                raw_img = self.get_user_face_image(puid)
                processed_img = self.process_image(raw_img)
                obj_id = self.upload_face_image(processed_img, puid, token)

                if self.submit_verification(params, obj_id):
                    time.sleep(2)
                    return True

            logger.info("API verification did not succeed; applying DOM mask removal fallback")
            # 先判断这是「准入级拦截页」还是「播放中的人脸校验弹窗」：
            #  - 准入页：整页无内容，必须刷新才会下发
            #  - 播放中弹窗：刷新会把播放进度打回原点，绝不能刷新
            admission = False
            try:
                self.driver.switch_to.default_content()
                body = self.driver.execute_script(
                    "return (document.body && document.body.innerText) || ''"
                ) or ""
                admission = any(k in body for k in self.FACE_TEXT_MARKERS)
            except Exception:
                pass

            removed = self.force_remove_popup()
            if removed and admission:
                # 仅准入页需要刷新
                try:
                    time.sleep(1)
                    self.driver.refresh()
                    time.sleep(6)
                    logger.info("Reloaded chapter page after removing admission-gate overlay")
                except Exception as e:
                    logger.debug(f"Reload after overlay removal failed: {e}")
            elif removed:
                logger.info("Overlay removed during playback; keeping page state (no reload)")
            return removed
        except Exception as e:
            logger.warning(f"Face bypass failed: {e}; attempting DOM removal")
            return self.force_remove_popup()
        finally:
            self.is_processing = False

    def force_remove_popup(self) -> bool:
        """Removes popup elements from the DOM so automation is not blocked."""
        removed_any = False
        try:
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass

            for sel in self.POPUP_SELECTORS:
                script = f"""
                var els = document.querySelectorAll('{sel}');
                var count = 0;
                els.forEach(function(el) {{ el.remove(); count++; }});
                return count;
                """
                count = self.driver.execute_script(script)
                if count and count > 0:
                    removed_any = True

            cleanup_script = """
            var count = 0;
            var els = document.querySelectorAll('.popDiv1, .maskDiv1, .faceCollectQrPopVideo, [class*="faceCollect"]');
            els.forEach(function(el) { el.remove(); count++; });
            document.querySelectorAll('a, span, button').forEach(function(el) {
                if (el.innerText && el.innerText.trim() === '知道了') el.click();
            });
            return count;
            """
            extra = self.driver.execute_script(cleanup_script)
            if extra and extra > 0:
                removed_any = True

            logger.info(f"Force removed face popup modal from DOM: {removed_any}")
            return removed_any
        except Exception as e:
            logger.error(f"Failed to remove popup from DOM: {e}")
            return False
