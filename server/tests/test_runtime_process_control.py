from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROCESS_LIB = ROOT / "scripts" / "termux" / "styledash-process-lib"
SHELL_FILES = [
    ROOT / "scripts" / "termux" / "styledash-process-lib",
    ROOT / "scripts" / "termux" / "start-styledash",
    ROOT / "scripts" / "termux" / "start-styledash-admin",
    ROOT / "scripts" / "termux" / "start-styledash-cloudflare",
    ROOT / "scripts" / "termux" / "start-styledash-stack",
    ROOT / "scripts" / "termux" / "deploy-payment-release",
    ROOT / "scripts" / "termux" / "rollback-payment-release",
    ROOT / "scripts" / "termux" / "styledash-health",
    ROOT / "scripts" / "termux" / "verify-styledash-processes",
]

def find_bash() -> str | None:
    found = shutil.which("bash")
    if found:
        return found
    if os.name == "nt":
        for candidate in (
            Path(r"C:\Program Files\Git\bin\bash.exe"),
            Path(r"C:\Program Files\Git\usr\bin\bash.exe"),
        ):
            if candidate.exists():
                return str(candidate)
    return None

def bash_path(path: Path) -> str:
    value = path.resolve().as_posix()
    if os.name == "nt" and len(value) >= 3 and value[1:3] == ":/":
        return f"/{value[0].lower()}/{value[3:]}"
    return value

class RuntimeProcessControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bash = find_bash()
        if cls.bash is None:
            raise unittest.SkipTest("bash is required for runtime process-control tests")

    def run_shell_file(self, body: str) -> subprocess.CompletedProcess[str]:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".sh", encoding="utf-8", newline="\n", delete=False
        ) as handle:
            handle.write(body)
            script = Path(handle.name)
        try:
            return subprocess.run(
                [self.bash, bash_path(script)],
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
        finally:
            if script.exists():
                script.unlink()

    def test_changed_shell_files_parse(self) -> None:
        for path in SHELL_FILES:
            with self.subTest(path=path.name):
                result = subprocess.run(
                    [self.bash, "-n", bash_path(path)],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_orphan_and_duplicate_processes_are_discovered_and_stopped(self) -> None:
        library = bash_path(PROCESS_LIB)
        body = f'''#!/usr/bin/env bash
set -eu
source "{library}"
p1=''
p2=''
cleanup() {{
  [ -z "$p1" ] || kill "$p1" 2>/dev/null || true
  [ -z "$p2" ] || kill "$p2" 2>/dev/null || true
}}
trap cleanup EXIT INT TERM
bash -c 'while :; do :; done' V4Y_RUNTIME_PROCESS_TEST V4Y_SECONDARY_TEST &
p1=$!
sleep 0.2
[ "$(styledash_process_count V4Y_RUNTIME_PROCESS_TEST V4Y_SECONDARY_TEST)" -eq 1 ]
styledash_assert_single_process "$p1" V4Y_RUNTIME_PROCESS_TEST V4Y_SECONDARY_TEST
bash -c 'while :; do :; done' V4Y_RUNTIME_PROCESS_TEST V4Y_SECONDARY_TEST &
p2=$!
sleep 0.2
[ "$(styledash_process_count V4Y_RUNTIME_PROCESS_TEST V4Y_SECONDARY_TEST)" -eq 2 ]
if styledash_assert_single_process "$p1" V4Y_RUNTIME_PROCESS_TEST V4Y_SECONDARY_TEST; then
  echo 'duplicate runtime was incorrectly accepted' >&2
  exit 1
fi
styledash_stop_matching_processes runtime-test V4Y_RUNTIME_PROCESS_TEST V4Y_SECONDARY_TEST
[ "$(styledash_process_count V4Y_RUNTIME_PROCESS_TEST V4Y_SECONDARY_TEST)" -eq 0 ]
echo process_control_regression=PASS
'''
        result = self.run_shell_file(body)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("process_control_regression=PASS", result.stdout)
