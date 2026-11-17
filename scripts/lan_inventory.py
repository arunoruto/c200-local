#!/usr/bin/env python3
"""Check selected TCP listeners on one explicitly supplied LAN address.

No application data, login attempts, exploit payloads, or UDP broadcasts
are sent. Open ports do not establish a service identity or shell access.
The default invocation without an address only prints command help.
"""

import argparse
from datetime import datetime, timezone
import ipaddress
import json
import socket

PORTS = {22: "possible SSH", 23: "possible telnet", 443: "HTTPS management",
         554: "RTSP", 2020: "ONVIF", 2323: "possible custom telnet",
         8800: "proprietary stream",
         20002: "historical tp_manage TCP listener"}


def probe(address: str, port: int, timeout: float) -> dict:
    """Attempt one TCP connection and close it without sending data.

    Parameters
    ----------
    address : str
        Literal IP address of the selected device.
    port : int
        TCP port to check.
    timeout : float
        Maximum connection wait in seconds.

    Returns
    -------
    dict
        Port, connection result, and optional operating system error.
    """
    try:
        with socket.create_connection((address, port), timeout=timeout):
            return {"port": port, "tcp": "open"}
    except ConnectionRefusedError:
        return {"port": port, "tcp": "refused"}
    except (TimeoutError, socket.timeout):
        return {"port": port, "tcp": "timeout"}
    except OSError as exc:
        return {"port": port, "tcp": "error", "detail": str(exc)}


def main() -> None:
    """Check one private unicast address when explicitly requested."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Camera's literal private LAN IP")
    parser.add_argument("--timeout", type=float, default=1.5)
    args = parser.parse_args()
    try:
        address = ipaddress.ip_address(args.host)
    except ValueError:
        parser.error("Provide one literal IP, not a hostname, range, or subnet")
    if not address.is_private or address.is_multicast or address.is_unspecified or address.is_reserved:
        parser.error("Provide a private unicast LAN IP (loopback is allowed for testing)")
    if not 0 < args.timeout <= 10:
        parser.error("Timeout must be greater than 0 and at most 10 seconds")
    print(json.dumps({
        "target": str(address),
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "method": "TCP connect only; service names are hypotheses",
        "ports": [dict(probe(str(address), port, args.timeout), expected=label)
                  for port, label in PORTS.items()],
    }, indent=2))


if __name__ == "__main__":
    main()
