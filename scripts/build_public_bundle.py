#!/usr/bin/env python3
"""Audit an explicit publication allowlist and optionally build a snapshot.

No camera, Git service, or remote endpoint is contacted. Only selected
UTF-8 files are copied; known local credentials are checked in memory.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parent.parent
BLOCKED = {"work", "private", "firmware", "pwntapo", ".git", ".aws",
           ".agents", ".codex", ".venv", "HANDOFF.md", "pw.txt",
           "telnet-pw.txt"}
PATTERNS = (
    rb"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----",
    rb"\bgh[pousr]_[A-Za-z0-9]{20,}\b",
    rb"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
    rb"\bsk-[A-Za-z0-9_-]{24,}\b",
    rb"\$[156]\$[A-Za-z0-9./]{1,16}\$[A-Za-z0-9./]{20,}",
)
# Shared firmware default, published by the original C200 researchers:
# https://github.com/nervous-inhuman/tplink-tapo-c200-re#default-root-password-and-u-boot-console
PUBLIC_DEFAULTS = frozenset({b"slprealtek"})
PRIVATE_FIELDS = frozenset({"dev_id", "device_id", "serial_number", "mac", "mac_addr",
                            "mac_address", "ssid", "bssid", "wifi_password", "psk",
                            "stok", "token", "access_token", "refresh_token"})


def _secrets(root):
    """Read local custom credentials without classifying shared defaults."""
    values = []
    for name in ("pw.txt", "telnet-pw.txt", "private/owner-password.txt"):
        path = root / name
        if path.is_file():
            value = path.read_bytes().removesuffix(b"\n").removesuffix(b"\r")
            if value and value not in PUBLIC_DEFAULTS:
                values.append(value)
    return values


def _sensitive(data, root):
    """Detect known custom credentials and common private-key/token forms."""
    return any(secret in data for secret in _secrets(root)) or any(
        re.search(pattern, data) for pattern in PATTERNS)


def _private_json(data):
    """Reject unit/account fields in public JSON, preserving shared defaults."""
    try:
        document = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        raise ValueError("Invalid JSON in public source or website") from None

    def walk(value):
        if isinstance(value, list):
            return any(walk(item) for item in value)
        if not isinstance(value, dict):
            return False
        for key, item in value.items():
            key = key.lower()
            if key in PRIVATE_FIELDS and item not in (None, "", [], {}):
                return True
            if key in ("password", "passwd", "pwd") and item:
                if not isinstance(item, str) or item.encode() not in PUBLIC_DEFAULTS:
                    return True
            if walk(item):
                return True
        return False

    return walk(document)


def audit(root: Path, check_tracked: bool = False) -> dict[str, bytes]:
    """Load and inspect only the explicit public files.

    Parameters
    ----------
    root : pathlib.Path
        Project directory containing the allowlist.
    check_tracked : bool, optional
        Reject Git-tracked files outside the explicit public allowlist.

    Returns
    -------
    dict of str to bytes
        Audited relative names and their exact source contents.

    Raises
    ------
    ValueError
        An entry is unsafe, missing, duplicated, non-text, or sensitive.
    """
    names = [line.strip() for line in (root / "PUBLIC_FILES.txt").read_text().splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    if not names or len(names) != len(set(names)):
        raise ValueError("Public allowlist is empty or contains duplicates")
    if check_tracked:
        result = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if result.returncode:
            raise ValueError("--check-tracked requires a Git checkout")
        tracked = {name for name in result.stdout.decode().split("\0") if name}
        extra = sorted(tracked - set(names))
        if extra:
            raise ValueError("Tracked files outside the public allowlist: " + ", ".join(extra))
    files = {}
    for name in names:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or BLOCKED.intersection(relative.parts):
            raise ValueError("Excluded publication path: " + name)
        source = root / relative
        if any((root / Path(*relative.parts[:i])).is_symlink()
               for i in range(1, len(relative.parts) + 1)):
            raise ValueError("Symlink in publication path: " + name)
        if not source.is_file() or not source.resolve().is_relative_to(root.resolve()):
            raise ValueError("Missing or escaped publication file: " + name)
        data = source.read_bytes()
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("Non-UTF-8 publication file: " + name) from None
        if b"\0" in data or _sensitive(data, root) or (source.suffix == ".json" and _private_json(data)):
            raise ValueError("Sensitive or binary content detected in: " + name)
        files[name] = data
    return files


def audit_site(root: Path, directory: Path) -> int:
    """Check generated website bytes for known secrets and token/key forms.

    Parameters
    ----------
    root : pathlib.Path
        Project directory supplying optional local credential references.
    directory : pathlib.Path
        Built website directory inside the project.

    Returns
    -------
    int
        Number of generated files checked.

    Raises
    ------
    ValueError
        The website is missing, outside the project, linked, or sensitive.
    """
    if not directory.is_dir() or not directory.resolve().is_relative_to(root.resolve()):
        raise ValueError("Expected a built website directory inside the project")
    if directory.is_symlink():
        raise ValueError("Linked website directory")
    count = 0
    for path in directory.rglob("*"):
        if path.is_symlink():
            raise ValueError("Symlink in generated website: " + str(path.relative_to(root)))
        if path.is_file():
            data = path.read_bytes()
            if _sensitive(data, root) or (path.suffix == ".json" and _private_json(data)):
                raise ValueError("Sensitive content detected in website file: " + str(path.relative_to(root)))
            count += 1
    if not count:
        raise ValueError("Built website is empty")
    return count


def main() -> None:
    """Check public inputs or write an audited, checksum-listed snapshot."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="Create a fresh public directory and tarball")
    parser.add_argument("--check-tracked", action="store_true", help="Reject tracked files outside PUBLIC_FILES.txt")
    parser.add_argument("--site-dir", type=Path, help="Also scan this built website for private content")
    args = parser.parse_args()
    try:
        files = audit(ROOT, check_tracked=args.check_tracked)
        site_files = audit_site(ROOT, ROOT / args.site_dir) if args.site_dir else None
    except (ValueError, OSError) as error:
        parser.exit(1, "Public audit failed: " + str(error) + "\n")
    result = {"audit_passed": True, "files": len(files),
              "bytes": sum(map(len, files.values())), "bundle_created": False}
    if args.check_tracked:
        result["tracked_files_checked"] = True
    if site_files is not None:
        result["website_files_checked"] = site_files
    if args.build:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        destination = ROOT / "work" / "public-release" / ("c200-local-" + stamp)
        destination.mkdir(parents=True, exist_ok=False, mode=0o700)
        sums = "".join(hashlib.sha256(data).hexdigest() + "  " + name + "\n"
                       for name, data in sorted(files.items()))
        entries = dict(files, SHA256SUMS=sums.encode())
        for name, data in entries.items():
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(0o644)
        archive = destination.with_suffix(".tar.gz")
        with archive.open("xb") as output, tarfile.open(fileobj=output, mode="w:gz") as bundle:
            for name, data in sorted(entries.items()):
                info = tarfile.TarInfo("c200-local/" + name)
                info.size, info.mode, info.mtime = len(data), 0o644, 0
                bundle.addfile(info, io.BytesIO(data))
        archive.chmod(0o600)
        result.update(bundle_created=True, directory=str(destination.relative_to(ROOT)),
                      archive=str(archive.relative_to(ROOT)),
                      archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
