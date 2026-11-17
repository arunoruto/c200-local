#!/usr/bin/env python3
"""Prepare, build, validate, or preview the local Hugo documentation site.

Only prepare downloads checksum-pinned public website dependencies.
The other commands build, inspect, or preview local documentation.
"""

import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import urlopen

from build_public_bundle import audit

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
TOOLS = ROOT / "work/site-tools"


def _download(spec):
    """Read one verified cached dependency or download it with a size cap."""
    directory = TOOLS / "downloads"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / spec["sha256"]
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == spec["sha256"]:
        return target
    with urlopen(spec["url"], timeout=60) as response, tempfile.NamedTemporaryFile(dir=directory, delete=False) as output:
        temporary = Path(output.name)
        try:
            size = 0
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                size += len(chunk)
                if size > 128 * 1024 * 1024:
                    raise ValueError("Website dependency exceeds the download limit")
                output.write(chunk)
            output.flush()
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != spec["sha256"]:
                raise ValueError("Website dependency checksum mismatch")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    return target


def _hugo():
    """Find the installed Hugo executable or the prepared local binary."""
    installed = shutil.which("hugo")
    if installed:
        return installed
    cached = TOOLS / "bin/hugo"
    if cached.is_file():
        return str(cached)
    raise ValueError("Hugo is missing: run site.py prepare, or install Hugo 0.170.0 on your PATH")


def prepare() -> None:
    """Install the pinned theme/search assets and a Linux Hugo if needed.

    Notes
    -----
    Existing managed assets are reused. On other operating systems,
    install Hugo separately before running this command.
    """
    dependencies = json.loads((DOCS / "dependencies.json").read_text())
    try:
        _hugo()
    except ValueError:
        machine = {"x86_64": "amd64", "aarch64": "arm64"}.get(platform.machine(), platform.machine())
        key = platform.system().lower() + "-" + machine
        spec = dependencies["hugo"].get(key)
        if not spec:
            raise ValueError("Install Hugo 0.170.0 for this host first; automatic setup supports Linux amd64/arm64") from None
        archive = _download(spec)
        target = TOOLS / "bin/hugo"
        target.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive) as bundle:
            member = bundle.getmember("hugo")
            if not member.isfile():
                raise ValueError("Unexpected Hugo archive entry")
            target.write_bytes(bundle.extractfile(member).read())
        target.chmod(0o755)
    spec = dependencies["hextra"]
    theme = DOCS / "themes/hextra"
    marker = theme / ".c200-sha256"
    if theme.exists() and (not marker.is_file() or marker.read_text().strip() != spec["sha256"]):
        raise ValueError("Existing unmanaged theme directory; preserve it before preparing Hextra")
    if not theme.exists():
        archive = _download(spec)
        theme.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=theme.parent) as directory, tarfile.open(archive) as bundle:
            if sum(member.size for member in bundle.getmembers()) > 64 * 1024 * 1024:
                raise ValueError("Theme archive exceeds the extraction limit")
            bundle.extractall(directory, filter="data")
            source = Path(directory) / ("hextra-" + spec["version"])
            source.rename(theme)
        marker.write_text(spec["sha256"] + "\n")
    vendor = DOCS / "assets/vendor"
    vendor.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_download(dependencies["flexsearch"]), vendor / "flexsearch.bundle.min.js")
    licenses = DOCS / "static/licenses"
    licenses.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(theme / "LICENSE", licenses / "hextra.txt")
    shutil.copyfile(_download(dependencies["flexsearch_license"]), licenses / "flexsearch.txt")
    shutil.copyfile(ROOT / "LICENSE", licenses / "project.txt")
    _downloads()
    print("Prepared Hugo, Hextra and local search assets.")


def _downloads():
    """Copy the public bootstrap templates and reference metadata."""
    directory = DOCS / "static/downloads"
    directory.mkdir(parents=True, exist_ok=True)
    for name in ("boot.sh", "launch.sh"):
        shutil.copyfile(ROOT / "camera" / name, directory / name)
    for name in ("assets.json", "PUBLIC_FILES.txt"):
        shutil.copyfile(ROOT / name, directory / name)


def _ready():
    """Require prepared dependencies without performing network access."""
    required = (DOCS / "themes/hextra/.c200-sha256", DOCS / "assets/vendor/flexsearch.bundle.min.js",
                DOCS / "static/licenses/hextra.txt", DOCS / "static/licenses/flexsearch.txt",
                DOCS / "static/licenses/project.txt")
    if not all(path.is_file() for path in required):
        raise ValueError("Website dependencies missing: run site.py prepare first")
    public = set(audit(ROOT))
    generated = {"docs/assets/vendor/flexsearch.bundle.min.js"}
    generated.update("docs/static/licenses/" + name for name in ("hextra.txt", "flexsearch.txt", "project.txt"))
    generated.update("docs/static/downloads/" + name for name in ("boot.sh", "launch.sh", "assets.json", "PUBLIC_FILES.txt"))
    for directory in ("content", "layouts", "assets", "static"):
        for path in (DOCS / directory).rglob("*"):
            if path.is_symlink():
                raise ValueError("Symlink in website input: " + str(path.relative_to(ROOT)))
            if path.is_file() and str(path.relative_to(ROOT)) not in public | generated:
                raise ValueError("Website input is outside the public allowlist: " + str(path.relative_to(ROOT)))
    _downloads()


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in ("href", "src") and value:
                self.links.append(value)


def check(base_url: str) -> int:
    """Check generated page links and required downloads without networking.

    Parameters
    ----------
    base_url : str
        Build base URL, including a project subpath when applicable.

    Returns
    -------
    int
        Number of generated HTML pages checked.

    Raises
    ------
    ValueError
        The output is absent or a local link points outside/misses it.
    """
    output = DOCS / "public"
    pages = list(output.rglob("*.html"))
    if not (output / "index.html").is_file():
        raise ValueError("No built website: run site.py build first")
    origin = urlsplit(base_url)
    prefix = origin.path.rstrip("/")
    broken = []
    for page in pages:
        parser = _Links()
        parser.feed(page.read_text())
        current = prefix + "/" + str(page.relative_to(output))
        for link in parser.links:
            parsed = urlsplit(link)
            if link.startswith("#") or (parsed.scheme and parsed.scheme not in ("http", "https")):
                continue
            if parsed.netloc and parsed.netloc != origin.netloc:
                continue
            path = unquote(urlsplit(urljoin(current, link)).path)
            if prefix:
                if path != prefix and not path.startswith(prefix + "/"):
                    broken.append((str(page.relative_to(output)), link))
                    continue
                path = path[len(prefix):]
            target = output / path.lstrip("/")
            if target.is_dir():
                target = target / "index.html"
            if not target.resolve().is_relative_to(output.resolve()) or not target.is_file():
                broken.append((str(page.relative_to(output)), link))
    if broken:
        raise ValueError("Broken local website links: " + json.dumps(broken[:12]))
    for name in ("boot.sh", "launch.sh"):
        if (output / "downloads" / name).read_bytes() != (ROOT / "camera" / name).read_bytes():
            raise ValueError("Website bootstrap download differs from its public source")
    return len(pages)


def main() -> None:
    """Prepare dependencies, build/check static HTML, or serve a preview."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "build", "check", "serve"))
    parser.add_argument("--base-url", default="http://localhost:1313/", help="Absolute deployment URL, ending in /")
    parser.add_argument("--port", type=int, default=1313)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            prepare()
            return
        if args.command == "check":
            print("Checked", check(args.base_url), "generated pages and local assets.")
            return
        _ready()
        command = [_hugo(), "--source", str(DOCS)]
        if args.command == "serve":
            command += ["server", "--bind", "127.0.0.1", "--port", str(args.port), "--disableFastRender"]
        else:
            if urlsplit(args.base_url).scheme not in ("http", "https") or not args.base_url.endswith("/"):
                raise ValueError("Use an absolute HTTP(S) base URL ending in /")
            command += ["--minify", "--baseURL", args.base_url, "--cleanDestinationDir"]
        subprocess.run(command, check=True, cwd=ROOT)
        if args.command == "build":
            print("Checked", check(args.base_url), "generated pages and local assets.")
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, "Website command failed: " + str(error) + "\n")


if __name__ == "__main__":
    main()
