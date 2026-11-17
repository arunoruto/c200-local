#!/usr/bin/env python3
"""Inspect a local firmware image without running its contents.

Python 3.10 or later is required. Basic inspection uses the standard
library. Extraction needs the uv project's optional analysis group.
Extracted symlinks and device nodes are recorded, never created.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import struct

SUPERBLOCK = struct.Struct("<5I6H8Q")
COMPRESSION = {1: "gzip", 2: "lzma", 3: "lzo", 4: "xz", 5: "lz4", 6: "zstd"}
MAX_INPUT = 64 * 1024 * 1024
MAX_EXTRACTED = 256 * 1024 * 1024
MAX_NODES = 20000


def inspect_image(data: bytes) -> dict:
    """Hash an image and identify plausible SquashFS superblocks.

    Parameters
    ----------
    data : bytes
        Firmware bytes. Offsets refer to this file, not physical flash.

    Returns
    -------
    dict
        Hashes, entropy, image size, and candidate filesystem metadata.

    Notes
    -----
    A valid-looking header does not prove filesystem integrity, a valid
    vendor signature, hardware compatibility, or that flashing is safe.
    """
    length = len(data)
    counts = Counter(data)
    entropy = -sum((n / length) * math.log2(n / length) for n in counts.values()) if length else 0
    report = {
        "size_bytes": length,
        "sha256": hashlib.sha256(data).hexdigest(),
        "git_blob_sha1": hashlib.sha1(f"blob {length}\0".encode() + data).hexdigest(),
        "entropy_bits_per_byte": round(entropy, 6),
        "vendor_signature_verified": False,
        "squashfs": [],
    }
    position = 0
    while True:
        offset = data.find(b"hsqs", position)
        if offset < 0:
            break
        position = offset + 4
        if offset + SUPERBLOCK.size > length:
            continue
        fields = SUPERBLOCK.unpack_from(data, offset)
        _, inodes, timestamp, block_size, fragments, compression, block_log, flags, ids, major, minor, _, size, *_ = fields
        if not (
            major == 4 and minor == 0 and compression in COMPRESSION
            and 4096 <= block_size <= 1048576
            and block_size == 1 << block_log and 0 < inodes <= MAX_NODES
            and fragments <= MAX_NODES and 0 < ids <= MAX_NODES
            and SUPERBLOCK.size <= size <= length - offset
        ):
            continue
        report["squashfs"].append({
            "offset": offset,
            "offset_hex": hex(offset),
            "bytes_used": size,
            "inodes": inodes,
            "created_utc": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
            "block_size": block_size,
            "fragments": fragments,
            "compression": COMPRESSION[compression],
            "flags": flags,
            "ids": ids,
            "version": f"{major}.{minor}",
        })
    return report


def extract_filesystems(data: bytes, filesystems: list[dict], destination: Path) -> list[dict]:
    """Extract regular files and record metadata in a fresh directory.

    Parameters
    ----------
    data : bytes
        Firmware bytes containing the candidate filesystems.
    filesystems : list of dict
        Superblock metadata returned by `inspect_image`.
    destination : pathlib.Path
        New output directory. Existing directories are refused.

    Returns
    -------
    list of dict
        Extracted filesystem names and manifest locations.

    Raises
    ------
    FileExistsError
        Output already exists.
    RuntimeError
        Optional dependencies are missing or extraction limits are hit.
    ValueError
        A filesystem contains an unsafe filename.
    """
    try:
        from dissect.squashfs import SquashFS
    except ImportError as exc:
        raise RuntimeError("Run uv sync --locked --group analysis to extract filesystems") from exc

    destination.mkdir(parents=True, exist_ok=False)
    result = []
    total_bytes = 0
    total_nodes = 0
    for header in filesystems:
        offset = header["offset"]
        fs = SquashFS(io.BytesIO(data[offset:offset + header["bytes_used"]]))
        fs_destination = destination / f"squashfs-{offset:08x}"
        fs_destination.mkdir()
        entries = []
        stack = [(fs.root, Path())]
        while stack:
            node, relative = stack.pop()
            total_nodes += 1
            if total_nodes > MAX_NODES:
                raise RuntimeError("Extraction node limit reached")
            target = fs_destination / relative
            metadata = {"path": relative.as_posix(), "mode": oct(node.mode), "size": node.size}
            if node.is_dir():
                metadata["type"] = "directory"
                target.mkdir(exist_ok=True)
                children = sorted(node.iterdir(), key=lambda entry: entry.name, reverse=True)
                for child in children:
                    if child.name in ("", ".", "..") or "/" in child.name or "\\" in child.name or "\0" in child.name:
                        raise ValueError(f"Unsafe filename: {child.name!r}")
                    stack.append((child, relative / child.name))
            elif node.is_file():
                metadata["type"] = "file"
                size = node.size
                if size is None or size < 0 or total_bytes + size > MAX_EXTRACTED:
                    raise RuntimeError("Extraction byte limit reached")
                content = node.open().read(size + 1)
                if len(content) != size:
                    raise ValueError(f"File size mismatch: {relative}")
                total_bytes += size
                with target.open("xb") as fh:
                    fh.write(content)
                target.chmod(0o600)
                metadata["sha256"] = hashlib.sha256(content).hexdigest()
                if content[:4] == b"\x7fELF" and len(content) >= 52 and content[4] == 1 and content[5] in (1, 2):
                    endian = "<" if content[5] == 1 else ">"
                    metadata["elf"] = {
                        "class": 32,
                        "byte_order": "little" if content[5] == 1 else "big",
                        "machine": struct.unpack_from(endian + "H", content, 18)[0],
                        "flags_hex": hex(struct.unpack_from(endian + "I", content, 36)[0]),
                    }
            elif node.is_symlink():
                metadata.update(type="symlink_not_created", target=node.link)
            else:
                metadata["type"] = "special_node_not_created"
            entries.append(metadata)
        manifest = destination / f"squashfs-{offset:08x}-manifest.json"
        manifest.write_text(json.dumps(entries, indent=2) + "\n")
        result.append({"offset": offset, "directory": str(fs_destination), "manifest": str(manifest)})
    return result


def main() -> None:
    """Run the offline inspection command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("--extract-to", type=Path, help="Extract to a NEW directory")
    args = parser.parse_args()
    if args.image.stat().st_size > MAX_INPUT:
        parser.error("Image exceeds the 64 MiB input limit")
    data = args.image.read_bytes()
    report = inspect_image(data)
    report["input"] = str(args.image)
    if args.extract_to:
        if not report["squashfs"]:
            parser.error("No plausible plaintext SquashFS header found; encryption is only one possible reason")
        report["extracted"] = extract_filesystems(data, report["squashfs"], args.extract_to)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
