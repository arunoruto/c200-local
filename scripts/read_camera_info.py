#!/usr/bin/env python3
"""Collect camera metadata or compare a saved report with stock V2 1.1.15.

Use --from-report for offline analysis; it never imports the camera client.
Live collection requires an explicit --host and --username. The collector
requests device information and cached upgrade metadata, not an upgrade,
cloud refresh, diagnostic action, or configuration change. Normal local
reads were verified on one owned C200 V2 running 1.3.17 and then 1.1.15.
"""

import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import struct


ROOT = Path(__file__).resolve().parent.parent
FIRMWARE_NAME = "Tapo_C200v2_en_1.1.15_Build_211112_Rel.10589n__1637888842077.bin"
FIRMWARE_SHA256 = "12f60580ed051950d22559478dda9453c4312f5a981f4e38212eefbd377eb83e"
DEFAULT_FIRMWARE = ROOT / "firmware" / "v2-1.1.15" / FIRMWARE_NAME
_BASIC_KEYS = {"oem_id", "hw_desc", "device_model", "hw_version", "sw_version"}
UNVERIFIED = [
    "Fresh factory state at the next SD-update boot",
    "Exact installed updater and bootloader enforcement",
    "Current flash layout and selected ISP profile",
    "Vendor signature and embedded integrity acceptance",
    "Flash writes, configuration migration, and successful boot",
    "Applicability of the historical shell vulnerability",
]


def load_candidate(path: Path) -> dict:
    """Read compatibility fields from the exact archived V2 1.1.15 file.

    Parameters
    ----------
    path : pathlib.Path
        Local unmodified stock firmware image.

    Returns
    -------
    dict
        Verified file identity and plaintext header compatibility fields.

    Raises
    ------
    OSError
        The file cannot be read.
    ValueError
        Its size or SHA-256 does not match the pinned candidate.

    Notes
    -----
    A file-hash match identifies the reference, not its vendor signature.
    """
    if path.stat().st_size != 8258048:
        raise ValueError("Expected the 8,258,048-byte V2 1.1.15 image")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != FIRMWARE_SHA256:
        raise ValueError("Firmware SHA-256 does not match the pinned V2 1.1.15 image")
    hardware_count, oem_count, descriptor_count = struct.unpack_from(">3H", data, 0xa0)
    header_size, vendor_id, zone_code = struct.unpack_from(">3H", data, 0x18)
    cursor = 0xb2
    candidate = {
        "version": "1.1.15 Build 211112 Rel.10589n",
        "filename": FIRMWARE_NAME,
        "sha256": FIRMWARE_SHA256,
        "vendor_signature_verified": False,
        "vendor_id": vendor_id,
        "zone_code": zone_code,
    }
    for name, count in (("hw_ids", hardware_count),
                        ("hw_descriptors", descriptor_count),
                        ("oem_ids", oem_count)):
        end = cursor + 16 * count
        if end > header_size or header_size > len(data):
            raise ValueError("Compatibility arrays exceed the image header")
        candidate[name] = [data[i:i + 16].hex() for i in range(cursor, end, 16)]
        cursor = end
    return candidate


def _sections(payload, depth=0):
    """Read recognized successful device-info response wrappers only."""
    if depth > 4 or not isinstance(payload, dict) or payload.get("error_code", 0) != 0:
        return {}, {}
    if "result" in payload:
        return _sections(payload["result"], depth + 1)
    if "responses" in payload:
        responses = payload["responses"]
        matches = [item for item in responses if isinstance(item, dict)
                   and item.get("method") == "getDeviceInfo"] if isinstance(responses, list) else []
        return _sections(matches[0], depth + 1) if len(matches) == 1 else ({}, {})
    module = payload.get("device_info", payload)
    if not isinstance(module, dict):
        return {}, {}
    basic, info = module.get("basic_info", {}), module.get("info", {})
    if not isinstance(basic, dict) or not _BASIC_KEYS.intersection(basic):
        basic = module if _BASIC_KEYS.intersection(module) else {}
    return basic, info if isinstance(info, dict) else {}


def extract_factory_values(report: dict) -> dict:
    """Extract observed values from collector or device-info responses.

    Parameters
    ----------
    report : dict
        A new or legacy collector report, raw result, or successful
        getDeviceInfo response, including its multipleRequest wrapper.

    Returns
    -------
    dict
        Observed factory/configuration fields and identity context.
        Missing values are None. Previously computed comparison fields
        are ignored; no identifier is inferred from a model or device ID.
    """
    basic, info = {}, {}
    if report.get("error_code", 0) != 0:
        report = {}
    for source in (report.get("basic_info"), report, report.get("device_info_response")):
        source_basic, source_info = _sections(source)
        basic.update(source_basic)
        info.update(source_info)
    values = {name: basic.get(name) for name in ("oem_id", "hw_desc")}
    values.update({name: info.get(name) for name in ("hw_id", "vendor_id", "zone_code", "language", "cur_isp_version")})
    for name in ("device_model", "hw_version", "sw_version"):
        values[name] = basic.get(name, info.get(name))
    return values


def compare_factory_values(values: dict, candidate: dict) -> dict:
    """Compare exposed values without certifying a working downgrade.

    Parameters
    ----------
    values : dict
        Observed values returned by `extract_factory_values`.
    candidate : dict
        Pinned candidate fields returned by `load_candidate`.

    Returns
    -------
    dict
        Per-field match, mismatch or unknown results, an overall exposed
        field status, and explicit checks that remain unverified.
    """
    checks = {}
    sources = {
        "oem_id": "device_info.basic_info.oem_id",
        "hw_desc": "device_info.basic_info.hw_desc",
        "hw_id": "device_info.info.hw_id",
        "vendor_id": "device_info.info.vendor_id",
        "zone_code": "device_info.info.zone_code",
    }
    for name, expected_name in (("oem_id", "oem_ids"), ("hw_desc", "hw_descriptors"), ("hw_id", "hw_ids")):
        observed = values.get(name)
        valid = isinstance(observed, str) and re.fullmatch(r"[0-9a-fA-F]{32}", observed.strip())
        normalized = observed.strip().lower() if valid else None
        checks[name] = {
            "source": sources[name], "observed": observed,
            "normalized": normalized, "expected": candidate[expected_name],
            "status": "unknown" if not valid else ("match" if normalized in candidate[expected_name] else "mismatch"),
            "reason": "missing_or_invalid_32_hex_digits" if not valid else "candidate_id_membership",
        }
    for name in ("vendor_id", "zone_code"):
        observed = values.get(name)
        valid = isinstance(observed, str) and re.fullmatch(r"(?:0[xX])?[0-9a-fA-F]{1,8}", observed.strip())
        parsed = int(observed.strip(), 16) if valid else None
        normalized = None if parsed is None else ((parsed >> 16) & 0xffff if name == "vendor_id" else parsed & 0xffff)
        checks[name] = {
            "source": sources[name], "observed": observed,
            "normalized": normalized, "expected": candidate[name],
            "status": "unknown" if not valid else ("match" if normalized == candidate[name] else "mismatch"),
            "reason": "missing_or_invalid_hex_u32_string" if not valid else ("upper_16_bits" if name == "vendor_id" else "lower_16_bits"),
        }
    statuses = {check["status"] for check in checks.values()}
    status = "mismatch" if "mismatch" in statuses else ("incomplete" if "unknown" in statuses else "exposed_fields_match")
    return {
        "candidate": candidate,
        "status": status,
        "checks": checks,
        "parsing_scope": "1.3.17 Build 260112 updater's traced vendor/zone rules",
        "downgrade_confirmed": False,
        "unverified": list(UNVERIFIED),
    }


def _sanitize_error(error):
    """Keep allowlisted diagnostics without messages, responses or locals."""
    details = {"exception_type": type(error).__name__, "category": "unclassified_client_error"}
    categories = {
        -40209: "authentication_rejected", -40418: "authentication_rejected",
        -40414: "local_password_required", -40401: "session_rejected",
        -40421: "session_rejected", -40105: "unsupported_method",
        -40106: "unsupported_method", -40210: "unsupported_method",
        -40404: "device_restricted", -40408: "device_restricted",
        -40406: "device_restricted", -52405: "rate_or_session_limit",
        -52419: "rate_or_session_limit", -52407: "rate_or_session_limit",
    }
    messages = {
        "Invalid authentication data": "authentication_rejected",
        "Failed to detect device type.": "unexpected_device_info",
        "Failure detecting hashing algorithm.": "authentication_negotiation_failed",
    }
    types = {
        "SSLError": "tls_error", "ConnectTimeout": "connection_timeout",
        "ReadTimeout": "read_timeout", "Timeout": "network_timeout",
        "TimeoutError": "network_timeout", "ConnectionRefusedError": "connection_refused",
        "ConnectionError": "connection_error", "PermissionError": "network_access_denied",
    }
    current, seen = error, set()
    for _ in range(4):
        if current is None or id(current) in seen:
            break
        seen.add(id(current))
        message = str(current)
        code = getattr(current, "code", None)
        if type(code) is not int:
            code = getattr(current, "error_code", None)
        if type(code) is not int and message.startswith("Error: ") and ", Response: " in message:
            try:
                response = json.loads(message.split(", Response: ", 1)[1])
                code = response.get("error_code") if isinstance(response, dict) else None
            except ValueError:
                code = None
        if "error_code" not in details and type(code) is int and code != 0 and -(2 ** 31) <= code < 2 ** 31:
            details["error_code"] = code
        if details["category"] == "unclassified_client_error":
            if message in messages:
                details["category"] = messages[message]
            elif message.startswith("Temporary Suspension:"):
                details["category"] = "temporary_suspension"
            else:
                for cls in type(current).__mro__:
                    if cls.__name__ in types:
                        details["category"] = types[cls.__name__]
                        break
        operation = getattr(current, "_camera_info_operation", None)
        if "operation" not in details and operation in {"getDeviceInfo", "get_device_info", "getPresetConfig", "getCloudConfig"}:
            details["operation"] = operation
        origin = None
        traceback = current.__traceback__
        while traceback is not None:
            frame = traceback.tb_frame
            module = frame.f_globals.get("__name__", "")
            function = frame.f_code.co_name
            if module.startswith("pytapo.") or module == "pytapo":
                if re.fullmatch(r"[A-Za-z0-9_.]+", module) and re.fullmatch(r"[A-Za-z0-9_]+", function):
                    origin = {"module": module, "function": function, "line": traceback.tb_lineno}
            traceback = traceback.tb_next
        if origin is not None:
            details.setdefault("client_origin", origin)
        current = current.__cause__ or current.__context__
    if "error_code" in details:
        details["category"] = categories.get(details["error_code"], details["category"])
    return details


def _write_report(path, report):
    """Create a private JSON file without overwriting an existing file."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump(report, output, indent=2)
        output.write("\n")


def collect_info(camera) -> dict:
    """Read device information and cached firmware metadata over the LAN.

    Parameters
    ----------
    camera : pytapo.Tapo
        Authenticated client with basic information already loaded.
        The live entry point suppresses PyTapo's cruise-changing retry.

    Returns
    -------
    dict
        Raw basic and expanded information, normalized field locations,
        and cached upgrade state. Query errors include type names and
        allowlisted diagnostics.
    """
    result = {"basic_info": camera.basicInfo}
    for key, method, params in (
        ("device_info_response", "getDeviceInfo", {"device_info": {"name": ["basic_info", "info"]}}),
        ("cached_upgrade_info", "getCloudConfig", {"cloud_config": {"name": ["upgrade_info"]}}),
    ):
        try:
            # In pinned PyTapo 3.4.31, True suppresses setCruise(False)
            # on error -64303; it does not trigger an extra retry.
            result[key] = camera.executeFunction(method, params, retry=True)
        except Exception as exc:
            result[key + "_error"] = type(exc).__name__
            result[key + "_diagnostic"] = _sanitize_error(exc)
    result["factory_values"] = extract_factory_values(result)
    return result


def _read_only_client_type(base_type):
    """Suppress the known mutating fallback during initialization too."""
    class InformationClient(base_type):
        def executeFunction(self, method, params, retry=True):
            """Dispatch through the library without cruise-changing retry.

            Parameters
            ----------
            method : str
                Library method name.
            params : dict or None
                Method parameters.
            retry : bool, optional
                Ignored; the known mutating fallback is always disabled.

            Returns
            -------
            dict or list
                Library response, with normal library errors preserved.
            """
            try:
                return super().executeFunction(method, params, retry=True)
            except Exception as exc:
                if method in {"getDeviceInfo", "get_device_info", "getPresetConfig", "getCloudConfig"}:
                    try:
                        exc._camera_info_operation = method
                    except (AttributeError, TypeError):
                        pass
                raise
    return InformationClient


def main() -> None:
    """Collect or reanalyze metadata and save a private comparison report."""
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--host", help="Camera's private LAN IPv4 address; enables live collection")
    source.add_argument("--from-report", type=Path, help="Compare saved JSON without importing PyTapo or using the network")
    parser.add_argument("--username", help="Camera Account username, or admin for supported legacy login")
    parser.add_argument("--firmware", type=Path, default=DEFAULT_FIRMWARE, help="Local pinned stock V2 1.1.15 image")
    parser.add_argument("--output", type=Path, default=ROOT / "private" / "device-info.json")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; choose a new filename")
    try:
        candidate = load_candidate(args.firmware)
    except (OSError, ValueError) as exc:
        parser.error(f"Cannot load pinned V2 1.1.15 firmware ({type(exc).__name__})")
    if args.from_report:
        if args.username:
            parser.error("--username is only used with --host")
        try:
            report = json.loads(args.from_report.read_text())
        except (OSError, ValueError) as exc:
            parser.error(f"Cannot read saved JSON ({type(exc).__name__})")
        if not isinstance(report, dict):
            parser.error("Saved report must be a JSON object")
        report["source_report"] = str(args.from_report)
        report["collection_mode"] = "offline_reanalysis"
        report["camera_contacted_this_run"] = False
    else:
        if not args.username:
            parser.error("--username is required with --host")
        try:
            address = ipaddress.IPv4Address(args.host)
        except ValueError:
            parser.error("Supply one literal private IPv4 address")
        if not address.is_private or address.is_multicast or address.is_unspecified or address.is_reserved:
            parser.error("Supply a private unicast IPv4 address")
        try:
            from pytapo import Tapo
        except ImportError:
            parser.error("Run uv sync --locked in the project directory")
        password = getpass.getpass("Camera login password: ")
        camera, report = None, None
        stage = "client_initialization"
        try:
            client_type = _read_only_client_type(Tapo)
            camera = client_type(str(address), args.username, password,
                                 printDebugInformation=False, printWarnInformation=False,
                                 redactConfidentialInformation=True, retryStok=False)
            stage = "metadata_collection"
            report = collect_info(camera)
        except Exception as exc:
            diagnostic = dict(_sanitize_error(exc), stage=stage)
            failure = {
                "schema_version": 2, "collection_mode": "live_api_failed",
                "target": str(address), "checked_utc": datetime.now(timezone.utc).isoformat(),
                "camera_connection_attempted_this_run": True,
                "camera_contacted_this_run": True if camera is not None else None, "failure": diagnostic,
                "downgrade_confirmed": False,
            }
            message = f"Local collection failed: {diagnostic['category']} ({diagnostic['exception_type']}); stage={stage}"
            if "error_code" in diagnostic:
                message += f"; error_code={diagnostic['error_code']}"
            try:
                _write_report(args.output, failure)
                message += f". Sanitized diagnostic saved to {args.output}"
            except OSError as write_error:
                message += f". Could not save diagnostic ({type(write_error).__name__})"
            raise SystemExit(message) from None
        finally:
            if camera is not None:
                try:
                    camera.close()
                except Exception as close_error:
                    if isinstance(report, dict):
                        report["close_diagnostic"] = dict(_sanitize_error(close_error), stage="session_cleanup")
        report["checked_utc"] = datetime.now(timezone.utc).isoformat()
        report["target"] = str(address)
        report["collection_mode"] = "live_api"
        report["camera_contacted_this_run"] = True
    report["schema_version"] = 2
    report["factory_values"] = extract_factory_values(report)
    report["downgrade_comparison"] = compare_factory_values(report["factory_values"], candidate)
    report["compared_utc"] = datetime.now(timezone.utc).isoformat()
    _write_report(args.output, report)
    print(f"Saved metadata and V2 1.1.15 comparison to {args.output}")
    print(f"Exposed-field comparison: {report['downgrade_comparison']['status']}")
    print("A field match does not confirm a working downgrade; see unverified checks in the report.")
    if "close_diagnostic" in report:
        print("Session cleanup failed; collected metadata was preserved in the report.")


if __name__ == "__main__":
    main()
