#!/usr/bin/env python3
"""Download checksum-pinned public reference assets, or verify local copies.

Nothing is extracted, executed, sent to a camera, or flashed.
"""

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from urllib.request import urlopen


def verify(path: Path, asset: dict) -> bool:
    """Check a reference file against its recorded size and hash.

    Parameters
    ----------
    path : pathlib.Path
        Local downloaded asset.
    asset : dict
        Manifest entry containing ``size`` and ``sha256``.

    Returns
    -------
    bool
        Whether both the size and SHA-256 match the manifest.
    """
    if not path.is_file() or path.stat().st_size != asset["size"]:
        return False
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == asset["sha256"]


def main() -> None:
    """Fetch missing assets after verification, or check without networking."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="No network; fail if any asset is absent or changed")
    parser.add_argument("--asset", action="append", metavar="NAME", help="Select a manifest filename; repeat to select several")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    assets = json.loads((root / "assets.json").read_text())["assets"]
    if args.asset:
        unknown = set(args.asset) - {asset["file"] for asset in assets}
        if unknown:
            parser.error("Unknown reference filename: " + ", ".join(sorted(unknown)))
        assets = [asset for asset in assets if asset["file"] in args.asset]
    destination = root / "work" / "downloads"
    destination.mkdir(parents=True, exist_ok=True)
    failed = False
    for asset in assets:
        name = asset["file"]
        if Path(name).name != name:
            raise ValueError("Asset filenames must not contain directory components")
        path = destination / name
        if verify(path, asset):
            print(f"verified {name}")
            continue
        if args.verify_only:
            print(f"missing or changed: {name}")
            failed = True
            continue
        if path.exists():
            raise FileExistsError(f"Refusing to replace an existing unverified file: {path}")
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination, delete=False) as output:
                temp_path = Path(output.name)
                with urlopen(asset["url"], timeout=60) as response:
                    size = 0
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > asset["size"]:
                            raise ValueError(f"Unexpected download length: {name}")
                        output.write(chunk)
            if not verify(temp_path, asset):
                raise ValueError(f"Size or checksum mismatch: {name}")
            if path.exists():
                raise FileExistsError(f"Destination appeared during download: {path}")
            temp_path.rename(path)
            print(f"downloaded and verified {name}")
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
