# -*- coding: utf-8 -*-
import io
import unittest
from PIL import Image
from xxt_agent.face_bypass import FaceBypass


class TestFaceBypass(unittest.TestCase):
    def test_add_inf_enc_sign(self):
        params = {"token": "test_token", "puid": "123456"}
        signed = FaceBypass.add_inf_enc_sign(params)
        self.assertIn("inf_enc", signed)
        self.assertEqual(len(signed["inf_enc"]), 32)  # md5 hex

    def test_parse_url_params(self):
        url = "https://mooc1.chaoxing.com/face?courseid=100&clazzid=200&uuid=xyz123"
        parsed = FaceBypass._parse_url_params(url)
        self.assertEqual(parsed.get("courseid"), "100")
        self.assertEqual(parsed.get("clazzid"), "200")
        self.assertEqual(parsed.get("uuid"), "xyz123")

    def test_parse_nested_content_url(self):
        inner_url = "https://pan-yz.chaoxing.com/qr?uuid=inner_uuid&enc=enc_val"
        from urllib.parse import quote
        url = f"https://mooc1.chaoxing.com/face?content={quote(inner_url)}"
        parsed = FaceBypass._parse_url_params(url)
        self.assertEqual(parsed.get("uuid"), "inner_uuid")
        self.assertEqual(parsed.get("qrcEnc"), "enc_val")

    def test_image_perturbation(self):
        # Create a small dummy RGB image
        img = Image.new("RGB", (50, 50), color=(100, 150, 200))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        raw_bytes = buf.getvalue()

        perturbed = FaceBypass.process_image(raw_bytes)
        self.assertIsInstance(perturbed, bytes)
        self.assertGreater(len(perturbed), 0)
        # Verify it can be reopened as image
        perturbed_img = Image.open(io.BytesIO(perturbed))
        self.assertEqual(perturbed_img.size, (50, 50))


if __name__ == "__main__":
    unittest.main()
