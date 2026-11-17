"""Check offline parsing, non-writing LAN queries, and extraction behavior."""

import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inspector = _load("inspect_firmware")
inventory = _load("lan_inventory")
reader = _load("read_camera_info")
fetcher = _load("fetch_assets")


def _node(name, kind, children=(), link=""):
    return SimpleNamespace(
        name=name, mode=0o40755 if kind == "dir" else 0o120777,
        size=0, link=link, is_dir=lambda: kind == "dir",
        is_file=lambda: False, is_symlink=lambda: kind == "link",
        iterdir=lambda: iter(children),
    )


class FirmwareInspectionTests(unittest.TestCase):
    """Check image boundaries and avoid filesystem side effects."""

    def test_plaintext_header_at_nonzero_offset(self):
        header = struct.pack("<5I6H8Q", 0x73717368, 1, 0, 131072, 0,
                             4, 17, 0, 1, 4, 0, 0, 96, 0, 0, 0, 0, 0, 0)
        data = b"x" * 32 + header
        result = inspector.inspect_image(data)
        self.assertEqual(result["squashfs"][0]["offset"], 32)
        self.assertEqual(result["squashfs"][0]["compression"], "xz")
        self.assertFalse(result["vendor_signature_verified"])

    def test_truncated_and_out_of_bounds_headers_rejected(self):
        self.assertEqual(inspector.inspect_image(b"hsqs")["squashfs"], [])
        header = struct.pack("<5I6H8Q", 0x73717368, 1, 0, 131072, 0,
                             4, 17, 0, 1, 4, 0, 0, 1000, 0, 0, 0, 0, 0, 0)
        self.assertEqual(inspector.inspect_image(header)["squashfs"], [])

    def test_symlinks_recorded_but_never_created(self):
        root = _node("/", "dir", [_node("escape", "link", link="/etc/passwd")])
        fake_module = SimpleNamespace(SquashFS=lambda _: SimpleNamespace(root=root))
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "extracted"
            with patch.dict("sys.modules", {"dissect.squashfs": fake_module}):
                inspector.extract_filesystems(b"", [{"offset": 0, "bytes_used": 0}], destination)
            link_path = destination / "squashfs-00000000" / "escape"
            self.assertFalse(link_path.exists())
            self.assertFalse(link_path.is_symlink())
            manifest = json.loads((destination / "squashfs-00000000-manifest.json").read_text())
            self.assertEqual(manifest[1]["type"], "symlink_not_created")

    def test_path_traversal_in_filename_rejected(self):
        root = _node("/", "dir", [_node("../escape", "link", link="anything")])
        fake_module = SimpleNamespace(SquashFS=lambda _: SimpleNamespace(root=root))
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("sys.modules", {"dissect.squashfs": fake_module}):
                with self.assertRaises(ValueError):
                    inspector.extract_filesystems(b"", [{"offset": 0, "bytes_used": 0}], Path(directory) / "out")
            self.assertFalse((Path(directory) / "escape").exists())

    def test_existing_extraction_destination_refused(self):
        fake_module = SimpleNamespace(SquashFS=lambda _: None)
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("sys.modules", {"dissect.squashfs": fake_module}):
                with self.assertRaises(FileExistsError):
                    inspector.extract_filesystems(b"", [], Path(directory))


class LocalInformationTests(unittest.TestCase):
    """Verify selected queries without a camera or external connection."""

    def test_tcp_probe_open_and_refused(self):
        try:
            listener = socket.socket()
        except PermissionError:
            self.skipTest("Session sandbox forbids localhost socket creation")
        with listener:
            try:
                listener.bind(("127.0.0.1", 0))
            except PermissionError:
                self.skipTest("Session sandbox forbids localhost socket binding")
            listener.listen(1)
            port = listener.getsockname()[1]
            self.assertEqual(inventory.probe("127.0.0.1", port, 1)["tcp"], "open")
        self.assertEqual(inventory.probe("127.0.0.1", port, 1)["tcp"], "refused")

    def test_tcp_probe_classifies_results_without_sending_payloads(self):
        connection = MagicMock()
        with patch.object(inventory.socket, "create_connection", return_value=connection):
            self.assertEqual(inventory.probe("127.0.0.1", 12345, 1)["tcp"], "open")
        connection.__enter__.return_value.send.assert_not_called()
        connection.__enter__.return_value.sendall.assert_not_called()
        for error, state in [(ConnectionRefusedError(), "refused"), (socket.timeout(), "timeout")]:
            with patch.object(inventory.socket, "create_connection", side_effect=error):
                self.assertEqual(inventory.probe("127.0.0.1", 12345, 1)["tcp"], state)

    def test_only_device_and_cached_upgrade_reads_requested(self):
        calls = []
        camera = SimpleNamespace(
            basicInfo={"model": "C200"},
            executeFunction=lambda method, params, **kwargs: calls.append((method, params, kwargs)) or {"version": "cached"},
        )
        result = reader.collect_info(camera)
        self.assertEqual(calls, [
            ("getDeviceInfo", {"device_info": {"name": ["basic_info", "info"]}}, {"retry": True}),
            ("getCloudConfig", {"cloud_config": {"name": ["upgrade_info"]}}, {"retry": True}),
        ])
        self.assertEqual(result["basic_info"]["model"], "C200")

    def test_failed_optional_query_does_not_copy_exception_secrets(self):
        def fail(*args, **kwargs):
            raise ValueError("sensitive response contents")
        result = reader.collect_info(SimpleNamespace(basicInfo={}, executeFunction=fail))
        self.assertEqual(result["cached_upgrade_info_error"], "ValueError")
        self.assertNotIn("sensitive", json.dumps(result))

    def test_reference_hash_mismatch_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample"
            path.write_bytes(b"original")
            asset = {"size": 8, "sha256": hashlib.sha256(b"original").hexdigest()}
            self.assertTrue(fetcher.verify(path, asset))
            path.write_bytes(b"tampered")
            self.assertFalse(fetcher.verify(path, asset))


if __name__ == "__main__":
    unittest.main()
