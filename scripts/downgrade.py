#!/usr/bin/env python3
"""Prepare or send one stock C200 V2 1.3.17 to 1.1.15 firmware upload.

Default mode checks only local image/request bytes. The explicit
--attempt mode authenticates normally and flashes if the camera accepts
the upload. There are no automatic firmware retries or reboots here.
"""

import argparse
from datetime import datetime, timezone
from email.parser import BytesParser
from email.policy import default
import getpass
import hashlib
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
import uuid

import requests

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("camera_reader", ROOT / "scripts/read_camera_info.py")
reader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reader)
SOURCE_VERSION = "1.3.17 Build 260112 Rel.58281n(4555)"


def _prepare_upload(session, host, token, data):
    """Build the exact single-file multipart request without sending it."""
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9]+", token):
        raise ValueError("Unexpected normal session-token format")
    prepared = session.prepare_request(requests.Request(
        "POST", f"https://{host}:443/stok={token}/admin/system/image_upgrade",
        headers={"Referer": f"https://{host}:443", "Accept": "application/json",
                 "User-Agent": "Tapo CameraClient Android", "requestByApp": "true"},
        files={"image": (reader.FIRMWARE_NAME, data, "application/octet-stream")},
    ))
    body = prepared.body
    if not isinstance(body, bytes) or int(prepared.headers["Content-Length"]) != len(body) or len(body) >= 0x1000001:
        raise ValueError("Unexpected multipart length")
    content_type = prepared.headers["Content-Type"]
    parsed = BytesParser(policy=default).parsebytes(
        ("Content-Type: " + content_type + "\r\nMIME-Version: 1.0\r\n\r\n").encode() + body)
    parts = list(parsed.iter_parts())
    if len(parts) != 1 or parts[0].get_payload(decode=True) != data:
        raise ValueError("Multipart altered the stock image")
    boundary = parsed.get_boundary().encode()
    if not 0 < len(boundary) < 128 or not body.endswith(b"\r\n--" + boundary + b"--\r\n") or "Transfer-Encoding" in prepared.headers:
        raise ValueError("Unexpected multipart framing")
    return prepared


def _upload_once(session, prepared):
    """Send once with redirects and adapter retries disabled."""
    if session.get_adapter(prepared.url).max_retries.total != 0:
        raise RuntimeError("Upload adapter must have retries disabled")
    return session.send(prepared, allow_redirects=False, timeout=(120, 120), verify=False)


def _basic(report):
    """Find the normal device identity in a saved or fresh collector report."""
    for value in (report.get("device_info_response"), report.get("basic_info"), report):
        basic, _ = reader._sections(value)
        if basic.get("dev_id"):
            return basic
    raise RuntimeError("Device identity missing from report")


def main() -> None:
    """Check locally or execute one explicitly requested stock downgrade."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firmware", type=Path, default=ROOT / "work/downloads/c200v2-1.1.15.bin")
    parser.add_argument("--host", help="One literal private camera IPv4 address")
    parser.add_argument("--username", default="admin", help="Normal owner/admin login")
    parser.add_argument("--baseline", type=Path, help="Private pre-downgrade collector report")
    parser.add_argument("--attempt", action="store_true", help="Send one upload; acceptance starts flashing")
    args = parser.parse_args()
    try:
        candidate = reader.load_candidate(args.firmware)
        data = args.firmware.read_bytes()
        host = str(ipaddress.IPv4Address(args.host or "192.168.1.100"))
        address = ipaddress.IPv4Address(host)
        if not address.is_private or address.is_multicast or address.is_unspecified or address.is_reserved:
            raise ValueError("Expected a private unicast camera IPv4 address")
        if args.attempt and (not args.host or not args.baseline):
            raise ValueError("--attempt requires --host and --baseline")
        baseline = json.loads(args.baseline.read_text()) if args.attempt else None
        if baseline is not None and not isinstance(baseline, dict):
            raise ValueError("Expected a collector report object")
        expected = _basic(baseline) if baseline is not None else None
        if expected is not None and (expected.get("device_model") != "C200" or expected.get("hw_version") != "2.0" or expected.get("sw_version") != SOURCE_VERSION):
            raise ValueError("Baseline is not the exact tested source model/build")
        with requests.Session() as session:
            prepared = _prepare_upload(session, host, "OFFLINETESTTOKEN", data)
            print(json.dumps({"stage": "local_request_checked", "image_bytes": len(data),
                              "multipart_bytes": len(prepared.body), "image_sha256": hashlib.sha256(data).hexdigest()}), flush=True)
    except (OSError, ValueError, RuntimeError, TypeError):
        parser.exit(1, "Local checks failed; verify the pinned image and exact-source baseline.\n")
    if not args.attempt:
        return

    def restrict_target(event, arguments):
        if event == "socket.sendto":
            raise PermissionError("The upload needs only the selected TCP management endpoint")
        if event == "socket.connect":
            endpoint = arguments[1]
            if not isinstance(endpoint, tuple) or endpoint[:2] != (host, 443):
                raise PermissionError("Only the selected camera management endpoint is permitted")

    sys.addaudithook(restrict_target)
    from pytapo import Tapo
    password = getpass.getpass("Owner/admin camera password: ")
    if not password or any(c in password for c in "\r\n\0"):
        parser.exit(1, "Invalid password framing.\n")
    private = ROOT / "private"
    private.mkdir(mode=0o700, exist_ok=True)
    journal = private / ("downgrade-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8] + ".json")
    record = {"events": [], "firmware_post_attempts": 0, "downgrade_confirmed": False,
              "target_version": "1.1.15 Build 211112 Rel.10589n", "firmware_sha256": reader.FIRMWARE_SHA256}
    camera, token = None, None

    def save(stage, **fields):
        event = {"utc": datetime.now(timezone.utc).isoformat(), "stage": stage, **fields}
        record["events"].append(event)
        serialized = json.dumps(record, indent=2)
        if (len(password) >= 6 and password in serialized) or (token and token in serialized):
            raise RuntimeError("Credential excluded from operation journal")
        temporary = journal.with_suffix(".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as output:
            output.write(serialized + "\n")
        os.replace(temporary, journal)
        print(json.dumps(event), flush=True)

    failed = False
    try:
        save("owner_prechecks_started")
        camera = reader._read_only_client_type(Tapo)(host, args.username, password,
            printDebugInformation=False, printWarnInformation=False,
            redactConfidentialInformation=True, retryStok=False)
        snapshot = reader.collect_info(camera)
        basic = _basic(snapshot)
        if basic.get("dev_id") != expected["dev_id"] or basic.get("sw_version") != SOURCE_VERSION or basic.get("device_model") != "C200" or basic.get("hw_version") != "2.0":
            raise RuntimeError("Fresh source identity/model/build mismatch")
        comparison = reader.compare_factory_values(snapshot["factory_values"], candidate)
        if comparison["status"] != "exposed_fields_match":
            raise RuntimeError("Compatibility prechecks did not all match")
        status = camera.executeFunction("getFirmwareUpdateStatus", {"cloud_config": {"name": "upgrade_status"}}, retry=True)
        auto = camera.executeFunction("getFirmwareAutoUpgradeConfig", {"auto_upgrade": {"name": ["common"]}}, retry=True)
        if status["cloud_config"]["upgrade_status"]["state"] != "normal" or auto["auto_upgrade"]["common"]["enabled"] != "off":
            raise RuntimeError("Upgrade busy or automatic upgrades enabled")
        transport = camera.transport
        if transport.method != "pytapo" or not isinstance(transport.session, requests.Session):
            raise RuntimeError("Unexpected normal authenticated transport")
        token = transport.stok
        prepared = _prepare_upload(transport.session, host, token, data)
        if hashlib.sha256(args.firmware.read_bytes()).hexdigest() != reader.FIRMWARE_SHA256:
            raise RuntimeError("Stock image changed after local checks")
        if transport.session.get_adapter(prepared.url).max_retries.total != 0:
            raise RuntimeError("Firmware retry adapter is enabled")
        record["firmware_post_attempts"] = 1
        save("submitting_one_firmware_request", automatic_flashing_if_accepted=True,
             retries=0, redirects=False, socket_timeout_seconds=120)
        try:
            response = _upload_once(transport.session, prepared)
            result = {"http_status": response.status_code}
            try:
                payload = response.json()
            except ValueError:
                payload = None
            if isinstance(payload, dict):
                result.update({k: payload[k] for k in ("error_code", "wait_time") if type(payload.get(k)) is int})
            result["accepted_response"] = response.status_code == 200 and result.get("error_code") == 0
            failed = not result["accepted_response"]
            save("firmware_http_response", **result)
        except requests.RequestException as error:
            failed = True
            save("firmware_http_outcome_unknown", exception_type=type(error).__name__, retry_performed=False)
    except Exception as error:
        failed = True
        save("operation_stopped", exception_type=type(error).__name__, stage_after_post=record["firmware_post_attempts"] > 0)
    finally:
        if camera is not None:
            try:
                camera.close()
            except Exception as error:
                save("session_cleanup_diagnostic", exception_type=type(error).__name__)
        print(json.dumps({"journal": str(journal.relative_to(ROOT)), "downgrade_confirmed": False}), flush=True)
        password = ""
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
