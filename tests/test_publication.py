"""Check privacy boundaries for public source, Git tracking and site output."""

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("public_snapshot", ROOT / "scripts/build_public_bundle.py")
publication = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publication)


class PublicationChecks(unittest.TestCase):
    """Keep shared defaults distinct from custom/device-specific material."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "PUBLIC_FILES.txt").write_text("README.md\n")
        (self.root / "README.md").write_text("public fixture\n")

    def test_documented_stock_password_is_allowed(self):
        (self.root / "telnet-pw.txt").write_text("slprealtek\n")
        (self.root / "README.md").write_text("Publicly documented stock default: slprealtek\n")
        self.assertIn("README.md", publication.audit(self.root))

    def test_custom_password_is_rejected_without_printing_it(self):
        secret = "custom-fixture-credential"
        (self.root / "pw.txt").write_text(secret + "\n")
        (self.root / "README.md").write_text("Accidental content: " + secret)
        with self.assertRaises(ValueError) as error:
            publication.audit(self.root)
        self.assertNotIn(secret, str(error.exception))

    def test_credential_file_is_excluded_even_for_a_public_default(self):
        (self.root / "telnet-pw.txt").write_text("slprealtek\n")
        (self.root / "PUBLIC_FILES.txt").write_text("telnet-pw.txt\n")
        with self.assertRaisesRegex(ValueError, "Excluded publication path"):
            publication.audit(self.root)

    def test_forced_tracked_private_file_fails_ci_audit(self):
        subprocess.run(["git", "init", "--quiet", "-b", "main", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "README.md"], check=True)
        publication.audit(self.root, check_tracked=True)
        (self.root / "pw.txt").write_text("private fixture")
        subprocess.run(["git", "-C", str(self.root), "add", "-f", "pw.txt"], check=True)
        with self.assertRaisesRegex(ValueError, "Tracked files outside the public allowlist"):
            publication.audit(self.root, check_tracked=True)

    def test_generated_site_secret_is_rejected(self):
        directory = self.root / "docs/public"
        directory.mkdir(parents=True)
        (self.root / "pw.txt").write_text("custom-fixture-credential")
        (directory / "index.html").write_text("custom-fixture-credential")
        with self.assertRaisesRegex(ValueError, "Sensitive content detected in website"):
            publication.audit_site(self.root, directory)

    def test_generated_binary_assets_and_public_defaults_are_allowed(self):
        directory = self.root / "docs/public"
        directory.mkdir(parents=True)
        (directory / "index.html").write_text("Stock default: slprealtek")
        (directory / "image.png").write_bytes(b"\x89PNG\x00fixture")
        self.assertEqual(publication.audit_site(self.root, directory), 2)

    def test_token_in_generated_site_is_rejected(self):
        directory = self.root / "docs/public"
        directory.mkdir(parents=True)
        (directory / "index.html").write_bytes(b"ghp_" + b"a" * 36)
        with self.assertRaisesRegex(ValueError, "Sensitive content detected in website"):
            publication.audit_site(self.root, directory)

    def test_device_specific_json_fields_are_rejected(self):
        (self.root / "PUBLIC_FILES.txt").write_text("data.json\n")
        (self.root / "data.json").write_text('{"device_info":{"dev_id":"unit-fixture-identifier"}}')
        with self.assertRaisesRegex(ValueError, "Sensitive or binary content"):
            publication.audit(self.root)

    def test_json_shared_compatibility_values_and_stock_password_are_allowed(self):
        (self.root / "PUBLIC_FILES.txt").write_text("data.json\n")
        (self.root / "data.json").write_text('{"hw_id":"shared-model-fixture","oem_id":"shared-oem-fixture","password":"slprealtek"}')
        self.assertIn("data.json", publication.audit(self.root))


if __name__ == "__main__":
    unittest.main()
