"""Check local website links, subpath hosting and private-input rejection."""

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("documentation_site", ROOT / "scripts/site.py")
site = importlib.util.module_from_spec(SPEC)
with patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
    SPEC.loader.exec_module(site)


class WebsiteChecks(unittest.TestCase):
    """Exercise the output checker without Hugo or network access."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.docs = self.root / "docs"
        self.output = self.docs / "public"
        (self.output / "downloads").mkdir(parents=True)
        (self.output / "guide").mkdir()
        (self.root / "camera").mkdir()
        for name in ("boot.sh", "launch.sh"):
            data = "# public fixture\n"
            (self.root / "camera" / name).write_text(data)
            (self.output / "downloads" / name).write_text(data)
        self.patches = patch.multiple(site, ROOT=self.root, DOCS=self.docs)
        self.patches.start()
        self.addCleanup(self.patches.stop)

    def pages(self, prefix=""):
        """Write a root page and one child with relative and absolute links.

        Parameters
        ----------
        prefix : str, optional
            Deployment subpath, without a trailing slash.
        """
        (self.output / "index.html").write_text('<a href="' + prefix + '/guide/">Guide</a><a href="https://outside.invalid/">Source</a>')
        (self.output / "guide/index.html").write_text('<a href="../">Home</a><a href="' + prefix + '/downloads/boot.sh">Download</a>')

    def test_root_and_project_subpath_links(self):
        for prefix in ("", "/c200"):
            with self.subTest(prefix=prefix):
                self.pages(prefix)
                self.assertEqual(site.check("https://docs.invalid" + prefix + "/"), 2)

    def test_missing_local_asset_is_rejected(self):
        self.pages()
        (self.output / "guide/index.html").write_text('<img src="/missing.svg">')
        with self.assertRaisesRegex(ValueError, "Broken local website links"):
            site.check("https://docs.invalid/")

    def test_bootstrap_download_must_match_its_public_source(self):
        self.pages()
        (self.output / "downloads/boot.sh").write_text("changed fixture")
        with self.assertRaisesRegex(ValueError, "differs from its public source"):
            site.check("https://docs.invalid/")

    def test_project_subpath_cannot_escape_to_domain_root(self):
        self.pages("/c200")
        (self.output / "guide/index.html").write_text('<a href="/downloads/boot.sh">Wrong root</a>')
        with self.assertRaisesRegex(ValueError, "Broken local website links"):
            site.check("https://docs.invalid/c200/")

    def test_unlisted_static_file_is_rejected_before_build(self):
        required = ("themes/hextra/.c200-sha256", "assets/vendor/flexsearch.bundle.min.js",
                    "static/licenses/hextra.txt", "static/licenses/flexsearch.txt", "static/licenses/project.txt")
        for name in required:
            p = self.docs / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("prepared fixture")
        (self.docs / "static/private-report.json").write_text('{"private":"fixture"}')
        with patch.object(site, "audit", return_value={}), patch.object(site, "_downloads") as downloads:
            with self.assertRaisesRegex(ValueError, "outside the public allowlist"):
                site._ready()
            downloads.assert_not_called()


if __name__ == "__main__":
    unittest.main()
