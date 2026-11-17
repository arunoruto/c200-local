"""Check downgrade prechecks with synthetic data and no camera access."""

import builtins
from contextlib import redirect_stdout, redirect_stderr
import importlib.util
import io
import json
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
CANDIDATE_AVAILABLE = (ROOT / "firmware" / "v2-1.1.15" /
                       "Tapo_C200v2_en_1.1.15_Build_211112_Rel.10589n__1637888842077.bin").is_file()
spec = importlib.util.spec_from_file_location("camera_reader", ROOT / "scripts/read_camera_info.py")
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


def sample_response():
    """Return synthetic values that satisfy all five exposed ID checks."""
    return {"device_info": {
        "basic_info": {
            "oem_id": "6C6C8A3E1B5801A276305D7B2FEFFF67",
            "hw_desc": "48574445534300000000000000000001",
            "device_model": "C200", "hw_version": "2.0",
            "sw_version": "1.3.17 Build 260112 Rel.58281n(4555)",
        },
        "info": {
            "hw_id": "9C09BC4DF198CCF158CEDAD8A5584B41",
            "vendor_id": "0000ffff", "zone_code": "0x12340000",
            "language": "en_US", "cur_isp_version": "1",
        },
    }}


@unittest.skipUnless(CANDIDATE_AVAILABLE, "Optional pinned 1.1.15 firmware is not installed")
class CameraComparisonTests(unittest.TestCase):
    """Exercise mismatch and uncertainty cases against the real candidate."""

    @classmethod
    def setUpClass(cls):
        cls.candidate = reader.load_candidate(reader.DEFAULT_FIRMWARE)

    def compare(self, response):
        return reader.compare_factory_values(reader.extract_factory_values(response), self.candidate)

    def test_pinned_reference_has_expected_id_sets(self):
        self.assertEqual(self.candidate["hw_ids"], ["9c09bc4df198ccf158cedad8a5584b41"])
        self.assertEqual(len(self.candidate["oem_ids"]), 4)
        self.assertEqual(self.candidate["vendor_id"], 0)
        self.assertEqual(self.candidate["zone_code"], 0)
        self.assertFalse(self.candidate["vendor_signature_verified"])

    def test_all_matches_never_confirm_a_working_downgrade(self):
        result = self.compare(sample_response())
        self.assertEqual(result["status"], "exposed_fields_match")
        self.assertTrue(all(c["status"] == "match" for c in result["checks"].values()))
        self.assertFalse(result["downgrade_confirmed"])
        self.assertTrue(result["unverified"])

    def test_new_oem_ids_mismatch_even_when_another_field_is_missing(self):
        for oem in ("fd4044b0e71c74b13c208f883a6097d9", "278c4dac5252b72b366a989654e0f23b"):
            with self.subTest(oem=oem):
                response = sample_response()
                response["device_info"]["basic_info"]["oem_id"] = oem
                del response["device_info"]["info"]["zone_code"]
                result = self.compare(response)
                self.assertEqual(result["status"], "mismatch")
                self.assertEqual(result["checks"]["oem_id"]["status"], "mismatch")
                self.assertEqual(result["checks"]["zone_code"]["status"], "unknown")

    def test_missing_and_malformed_values_stay_unknown(self):
        for bad in (None, "", "0", 123, True, [], {}, "a" * 64, "g" * 32):
            with self.subTest(value=bad):
                response = sample_response()
                response["device_info"]["basic_info"]["oem_id"] = bad
                result = self.compare(response)
                self.assertEqual(result["status"], "incomplete")
                self.assertEqual(result["checks"]["oem_id"]["status"], "unknown")

    def test_zero_descriptor_is_a_valid_candidate_value(self):
        response = sample_response()
        response["device_info"]["basic_info"]["hw_desc"] = "0" * 32
        self.assertEqual(self.compare(response)["checks"]["hw_desc"]["status"], "match")

    def test_vendor_uses_upper_word_zone_uses_lower_word_and_hex(self):
        response = sample_response()
        response["device_info"]["info"].update(vendor_id="00010000", zone_code="10")
        checks = self.compare(response)["checks"]
        self.assertEqual(checks["vendor_id"]["normalized"], 1)
        self.assertEqual(checks["zone_code"]["normalized"], 0x10)
        self.assertEqual(checks["vendor_id"]["status"], "mismatch")
        for bad in (0, False, "", "-1", "0x", "100000000", "xyz"):
            response["device_info"]["info"]["vendor_id"] = bad
            self.assertEqual(self.compare(response)["checks"]["vendor_id"]["status"], "unknown")

    def test_supported_response_wrappers_and_legacy_partial_report(self):
        response = sample_response()
        wrapped = {"error_code": 0, "result": response}
        batched = {"error_code": 0, "result": {"responses": [
            {"method": "getDeviceInfo", "error_code": 0, "result": response}
        ]}}
        collected = {"basic_info": {"device_info": {"basic_info": {"oem_id": "0" * 32}}},
                     "device_info_response": response}
        for value in (response, wrapped, batched, collected):
            with self.subTest(value=value):
                self.assertEqual(self.compare(value)["status"], "exposed_fields_match")
        old = {"basic_info": {"device_info": {"basic_info": response["device_info"]["basic_info"]}}}
        checks = self.compare(old)["checks"]
        self.assertEqual(checks["oem_id"]["status"], "match")
        self.assertEqual(checks["hw_id"]["status"], "unknown")

    def test_error_responses_other_methods_and_stale_computations_are_ignored(self):
        response = sample_response()
        for value in (
            {"error_code": -1, "result": response},
            {"error_code": -1, "basic_info": response["device_info"]["basic_info"]},
            {"result": {"responses": [{"method": "getCloudConfig", "error_code": 0, "result": response}]}},
            {"factory_values": reader.extract_factory_values(response), "downgrade_comparison": {"downgrade_confirmed": True}},
        ):
            with self.subTest(value=value):
                result = self.compare(value)
                self.assertEqual(result["status"], "incomplete")
                self.assertTrue(all(c["status"] == "unknown" for c in result["checks"].values()))

    def test_device_id_and_displayed_version_are_not_hardware_id_fallbacks(self):
        response = sample_response()
        del response["device_info"]["info"]["hw_id"]
        response["device_info"]["basic_info"].update(dev_id=self.candidate["hw_ids"][0], hw_id=self.candidate["hw_ids"][0])
        self.assertEqual(self.compare(response)["checks"]["hw_id"]["status"], "unknown")

    def test_wrong_firmware_size_or_hash_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong.bin"
            path.write_bytes(b"wrong")
            with self.assertRaises(ValueError):
                reader.load_candidate(path)
            with path.open("wb") as handle:
                handle.truncate(8258048)
            with self.assertRaises(ValueError):
                reader.load_candidate(path)

    def test_collector_preserves_initial_values_if_expanded_query_fails(self):
        def execute(method, params, **kwargs):
            if method == "getDeviceInfo":
                raise ValueError("SECRET_RESPONSE")
            return {}
        camera = SimpleNamespace(basicInfo=sample_response(), executeFunction=execute)
        result = reader.collect_info(camera)
        self.assertEqual(result["factory_values"]["oem_id"], sample_response()["device_info"]["basic_info"]["oem_id"])
        self.assertEqual(result["device_info_response_error"], "ValueError")
        self.assertNotIn("SECRET_RESPONSE", json.dumps(result))

    def test_mutating_retry_is_suppressed_during_constructor_and_direct_calls(self):
        calls = []
        class FakeTapo:
            def __init__(self):
                self.executeFunction("getDeviceInfo", {})
            def executeFunction(self, method, params, retry=False):
                calls.append(retry)
                if not retry:
                    raise AssertionError("would trigger mutating fallback")
                return {}
        camera = reader._read_only_client_type(FakeTapo)()
        camera.executeFunction("getCloudConfig", {}, retry=False)
        self.assertEqual(calls, [True, True])

    def test_offline_cli_never_imports_client_prompts_or_opens_a_socket(self):
        real_import = builtins.__import__
        def no_client(name, *args, **kwargs):
            if name == "pytapo" or name.startswith("pytapo."):
                raise AssertionError("offline mode imported a camera client")
            return real_import(name, *args, **kwargs)
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "saved.json", Path(directory) / "compared.json"
            source.write_text(json.dumps(sample_response()))
            original = source.read_bytes()
            args = ["read_camera_info.py", "--from-report", str(source), "--output", str(output)]
            with patch("sys.argv", args), patch("builtins.__import__", side_effect=no_client), \
                 patch("socket.socket", side_effect=AssertionError("network access")), \
                 patch.object(reader.getpass, "getpass", side_effect=AssertionError("password prompt")), \
                 redirect_stdout(io.StringIO()):
                reader.main()
            result = json.loads(output.read_text())
            self.assertEqual(result["downgrade_comparison"]["status"], "exposed_fields_match")
            self.assertFalse(result["camera_contacted_this_run"])
            self.assertFalse(result["downgrade_comparison"]["downgrade_confirmed"])
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
            self.assertEqual(source.read_bytes(), original)
            with patch("sys.argv", args), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    reader.main()
            self.assertEqual(error.exception.code, 2)
            with patch("sys.argv", args + ["--host", "192.168.1.10"]), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    reader.main()
            self.assertEqual(error.exception.code, 2)


class DiagnosticTests(unittest.TestCase):
    """Retain actionable error metadata while dropping secrets and locals."""

    def test_known_auth_and_schema_messages_are_categorized(self):
        for message, category in (("Invalid authentication data", "authentication_rejected"),
                                  ("Failed to detect device type.", "unexpected_device_info")):
            result = reader._sanitize_error(Exception(message))
            self.assertEqual(result["category"], category)
            self.assertNotIn(message, json.dumps(result))

    def test_numeric_response_code_is_kept_but_payload_is_not(self):
        error = Exception('Error: SECRET, Response: {"error_code": -40209, "password": "SECRET", "token": "SECRET"}')
        result = reader._sanitize_error(error)
        self.assertEqual(result["error_code"], -40209)
        self.assertEqual(result["category"], "authentication_rejected")
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertNotIn("password", result)
        for value in ('Error: x, Response: {"error_code": "SECRET"}',
                      'Error: x, Response: {"error_code": true}',
                      'Error: x, Response: {"password": {"error_code": -40209}}',
                      'SECRET error_code=-40209', 'Error: x, Response: SECRET'):
            self.assertNotIn("error_code", reader._sanitize_error(Exception(value)))

    def test_typed_codes_chains_and_cycles_are_handled(self):
        class CodedError(Exception):
            code = -40414
        error = Exception("SECRET")
        error.__cause__ = CodedError("SECRET")
        result = reader._sanitize_error(error)
        self.assertEqual(result["category"], "local_password_required")
        self.assertNotIn("SECRET", json.dumps(result))
        error.__cause__ = error
        self.assertEqual(reader._sanitize_error(error)["category"], "unclassified_client_error")
        self.assertEqual(reader._sanitize_error(TimeoutError("SECRET"))["category"], "network_timeout")

    def test_client_traceback_never_copies_locals_or_full_path(self):
        namespace = {"__name__": "pytapo.synthetic"}
        exec(compile('def fail():\n password = "SECRET"\n raise Exception(password)\n', '/private/SECRET/client.py', 'exec'), namespace)
        try:
            namespace['fail']()
        except Exception as error:
            result = reader._sanitize_error(error)
        self.assertEqual(result["client_origin"]["module"], "pytapo.synthetic")
        self.assertEqual(result["client_origin"]["function"], "fail")
        self.assertNotIn("SECRET", json.dumps(result))
        self.assertNotIn("/private/", json.dumps(result))

    def test_optional_query_errors_get_safe_diagnostics(self):
        def execute(method, params, **kwargs):
            raise Exception('Error: SECRET, Response: {"error_code": -40105, "token": "SECRET"}')
        result = reader.collect_info(SimpleNamespace(basicInfo=sample_response(), executeFunction=execute))
        self.assertEqual(result["device_info_response_diagnostic"]["category"], "unsupported_method")
        self.assertEqual(result["cached_upgrade_info_diagnostic"]["error_code"], -40105)
        self.assertNotIn("SECRET", json.dumps(result))

    @unittest.skipUnless(CANDIDATE_AVAILABLE, "Optional pinned 1.1.15 firmware is not installed")
    def test_initialization_failure_writes_private_sanitized_report(self):
        class FakeTapo:
            def __init__(self, *args, **kwargs):
                raise Exception('Error: SECRET, Response: {"error_code": -40209, "token": "SECRET"}')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'failed.json'
            args = ['reader', '--host', '192.168.1.100', '--username', 'camera-user', '--output', str(output)]
            with patch('sys.argv', args), patch.dict('sys.modules', {'pytapo': SimpleNamespace(Tapo=FakeTapo)}), \
                 patch.object(reader.getpass, 'getpass', return_value='SECRET'), \
                 patch('socket.socket', side_effect=AssertionError('network access')):
                with self.assertRaises(SystemExit) as context:
                    reader.main()
            report = json.loads(output.read_text())
            self.assertEqual(report['failure']['stage'], 'client_initialization')
            self.assertEqual(report['failure']['error_code'], -40209)
            self.assertIsNone(report['camera_contacted_this_run'])
            self.assertTrue(report['camera_connection_attempted_this_run'])
            self.assertFalse(report['downgrade_confirmed'])
            self.assertNotIn('SECRET', json.dumps(report))
            self.assertNotIn('SECRET', str(context.exception))
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)

    @unittest.skipUnless(CANDIDATE_AVAILABLE, "Optional pinned 1.1.15 firmware is not installed")
    def test_cleanup_error_does_not_discard_collected_values(self):
        class FakeTapo:
            def __init__(self, *args, **kwargs):
                self.basicInfo = sample_response()
            def executeFunction(self, method, params, **kwargs):
                return sample_response() if method == 'getDeviceInfo' else {}
            def close(self):
                raise Exception('SECRET')
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'collected.json'
            args = ['reader', '--host', '192.168.1.100', '--username', 'camera-user', '--output', str(output)]
            with patch('sys.argv', args), patch.dict('sys.modules', {'pytapo': SimpleNamespace(Tapo=FakeTapo)}), \
                 patch.object(reader.getpass, 'getpass', return_value='SECRET'), \
                 patch('socket.socket', side_effect=AssertionError('network access')), \
                 redirect_stdout(io.StringIO()):
                reader.main()
            report = json.loads(output.read_text())
            self.assertEqual(report['downgrade_comparison']['status'], 'exposed_fields_match')
            self.assertEqual(report['close_diagnostic']['stage'], 'session_cleanup')
            self.assertNotIn('SECRET', json.dumps(report))


if __name__ == "__main__":
    unittest.main()
