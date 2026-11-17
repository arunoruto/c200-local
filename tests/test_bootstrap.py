"""Exercise public bootstrap account/filter behavior with host-only stubs.

Only absolute filesystem paths are redirected into a temporary fixture.
Firewall, network tools and Telnet are stubs; no camera is contacted.
"""

import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


class BootstrapTests(unittest.TestCase):
    """Run the actual shell control flow with isolated account fixtures."""

    def exercise(self, layout):
        """Run one account layout and always terminate the stub listener.

        Parameters
        ----------
        layout : str
            Direct, shadow-backed, empty, or locked root account fixture.
        """
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            config, run = base / "etc/config/local_access", base / "tmp/tapo-local-access"
            config.mkdir(parents=True)
            run.mkdir(parents=True)
            commands = base / "bin"
            commands.mkdir()
            (base / "usr/sbin").mkdir(parents=True)
            hashes = {"direct": "$1$fixture$fixture", "shadow": "x", "empty": "", "locked": "!"}
            passwd = base / "etc/passwd"
            shadow = base / "etc/shadow"
            passwd.write_text("root:" + hashes[layout] + ":0:0:root:/root:/bin/sh\n")
            shadow.write_text("root:$1$fixture$fixture:0:0:99999:7:::\n")
            before = passwd.read_bytes(), shadow.read_bytes()

            def executable(path, text):
                path.write_text("#!/bin/sh\n" + text + "\n")
                path.chmod(0o700)

            executable(commands / "iptables", '''
printf '%s\\n' "$*" >> "FIXTURE/rules"
case "$1 $2" in
    '-S OUTPUT') [ ! -e "FIXTURE/attached" ] || echo '-A OUTPUT -j TAPO_LOCAL_ONLY'; exit 0;;
    '-S TAPO_LOCAL_ONLY') [ -e "FIXTURE/created" ]; exit $?;;
    '-N TAPO_LOCAL_ONLY') touch "FIXTURE/created";;
    '-I OUTPUT') touch "FIXTURE/attached";;
esac
exit 0
'''.replace("FIXTURE", str(base)))
            executable(commands / "ifconfig", "echo 'br-wan inet addr:192.168.1.100  Bcast:192.168.1.255'")
            executable(commands / "netstat", "exit 0")
            executable(commands / "login", "exit 1")
            executable(base / "usr/sbin/telnetd", "exec sleep 60")
            text = (ROOT / "camera/boot.sh").read_text()
            text = re.sub(r"/(?:etc|tmp|proc|usr/sbin)/", lambda match: str(base) + match[0], text)
            text = text.replace("/bin/login", str(commands / "login"))
            script = config / "boot.sh"
            script.write_text(text)
            env = dict(os.environ, PATH=str(commands) + os.pathsep + os.environ["PATH"])
            pid = None
            try:
                result = subprocess.run(["sh", str(script)], env=env, capture_output=True, timeout=5)
                self.assertEqual((passwd.read_bytes(), shadow.read_bytes()), before)
                if layout in ("empty", "locked"):
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse((run / "telnet.pid").exists())
                    self.assertFalse((base / "rules").exists())
                    return
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                pid = int((run / "telnet.pid").read_text())
                rules = (base / "rules").read_text()
                self.assertIn("-d 228.67.43.91 -p udp --sport 15947 --dport 15947 -j RETURN", rules)
                self.assertIn("-d 239.255.255.250 --dport 3702 -j RETURN", rules)
                self.assertIn("-d 162.159.200.1 -p udp --dport 123 -j RETURN", rules)
                self.assertLess(rules.index("--dport 53 -j DROP"), rules.index("-d 192.168.1.0/24 -j RETURN"))
                proc = base / "proc" / str(pid)
                proc.mkdir(parents=True)
                proc.joinpath("cmdline").write_text("telnetd -F -b 192.168.1.100 -p 2323 -l " + str(commands / "login"))
                again = subprocess.run(["sh", str(script)], env=env, capture_output=True, timeout=5)
                self.assertEqual(again.returncode, 0, again.stderr.decode())
                self.assertEqual(int((run / "telnet.pid").read_text()), pid)
                self.assertEqual((passwd.read_bytes(), shadow.read_bytes()), before)
            finally:
                if pid is None and (run / "telnet.pid").exists():
                    pid = int((run / "telnet.pid").read_text())
                if pid is not None:
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass

    def test_stock_direct_hash_and_shadow_layouts(self):
        for layout in ("direct", "shadow"):
            with self.subTest(layout=layout):
                self.exercise(layout)

    def test_empty_and_locked_accounts_do_not_start_services(self):
        for layout in ("empty", "locked"):
            with self.subTest(layout=layout):
                self.exercise(layout)


if __name__ == "__main__":
    unittest.main()
