"""Check stock multipart framing and single-send downgrade behavior offline."""

from contextlib import redirect_stdout, redirect_stderr
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import requests

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("downgrade", ROOT / "scripts/downgrade.py")
upload = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(upload)


class UploadTests(unittest.TestCase):
    """Exercise framing, failure boundaries and offline default behavior."""

    def test_multipart_preserves_binary_image_and_exact_route(self):
        image = b"\0stock-image\r\n" * 100
        with requests.Session() as session:
            prepared = upload._prepare_upload(session, "192.168.1.100", "TESTTOKEN", image)
        self.assertEqual(prepared.url, "https://192.168.1.100:443/stok=TESTTOKEN/admin/system/image_upgrade")
        self.assertIn(image, prepared.body)
        self.assertIn(b'name="image"', prepared.body)
        self.assertEqual(int(prepared.headers["Content-Length"]), len(prepared.body))
        self.assertNotIn("Transfer-Encoding", prepared.headers)

    def test_token_cannot_change_request_route(self):
        with requests.Session() as session:
            for token in (None, "token/another-route", "token?query", ""):
                with self.subTest(token=token), self.assertRaises(ValueError):
                    upload._prepare_upload(session, "192.168.1.100", token, b"data")

    def test_disconnect_is_one_send_without_redirects(self):
        class Session:
            calls = 0

            def get_adapter(self, url):
                return requests.adapters.HTTPAdapter(max_retries=0)

            def send(self, prepared, **options):
                self.calls += 1
                if options != {"allow_redirects": False, "timeout": (120, 120), "verify": False}:
                    raise AssertionError("Unexpected upload options")
                raise requests.ConnectionError("synthetic disconnect")

        session = Session()
        request = requests.Request("POST", "https://192.168.1.100/", data=b"data").prepare()
        with self.assertRaises(requests.ConnectionError):
            upload._upload_once(session, request)
        self.assertEqual(session.calls, 1)

    def test_retry_enabled_adapter_rejected_before_send(self):
        class Session:
            def get_adapter(self, url):
                return requests.adapters.HTTPAdapter(max_retries=1)

            def send(self, *args, **kwargs):
                raise AssertionError("Must not send")

        request = requests.Request("POST", "https://192.168.1.100/").prepare()
        with self.assertRaises(RuntimeError):
            upload._upload_once(Session(), request)

    def test_identity_missing_from_baseline_is_rejected(self):
        with self.assertRaises(RuntimeError):
            upload._basic({"basic_info": {"device_model": "C200"}})

    def test_default_cli_does_not_connect_or_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "image.bin"
            image.write_bytes(b"synthetic image")
            output = io.StringIO()
            with patch("sys.argv", ["downgrade", "--firmware", str(image)]), \
                 patch.object(upload.reader, "load_candidate", return_value={}), \
                 patch("socket.socket", side_effect=AssertionError("No network")), \
                 patch.object(upload.getpass, "getpass", side_effect=AssertionError("No prompt")), \
                 redirect_stdout(output):
                upload.main()
            self.assertEqual(json.loads(output.getvalue())["stage"], "local_request_checked")

    def test_attempt_requires_explicit_host_and_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "image.bin"
            image.write_bytes(b"synthetic image")
            with patch("sys.argv", ["downgrade", "--firmware", str(image), "--attempt"]), \
                 patch.object(upload.reader, "load_candidate", return_value={}), \
                 patch("socket.socket", side_effect=AssertionError("No network")), \
                 patch.object(upload.getpass, "getpass", side_effect=AssertionError("No prompt")), \
                 redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                upload.main()
            self.assertEqual(error.exception.code, 1)

    def test_other_source_build_rejected_before_login(self):
        with tempfile.TemporaryDirectory() as directory:
            image, baseline = Path(directory) / "image.bin", Path(directory) / "before.json"
            image.write_bytes(b"synthetic image")
            baseline.write_text(json.dumps({"basic_info": {"device_model": "C200", "hw_version": "2.0",
                                                         "sw_version": "other", "dev_id": "synthetic"}}))
            args = ["downgrade", "--firmware", str(image), "--host", "192.168.1.100", "--baseline", str(baseline), "--attempt"]
            with patch("sys.argv", args), patch.object(upload.reader, "load_candidate", return_value={}), \
                 patch("socket.socket", side_effect=AssertionError("No network")), \
                 patch.object(upload.getpass, "getpass", side_effect=AssertionError("No prompt")), \
                 redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                upload.main()
            self.assertEqual(error.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
