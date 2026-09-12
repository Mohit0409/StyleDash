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

    def run_shell_file(self, body: str, timeout: int = 20) -> subprocess.CompletedProcess[str]:
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
                timeout=timeout,
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

    def test_runit_supervisor_is_paused_before_watchdog_shutdown(self) -> None:
        library = bash_path(PROCESS_LIB)
        body = f'''#!/usr/bin/env bash
set -eu
source "{library}"
tmp="$(mktemp -d)"
export HOME="$tmp/home"
export PREFIX="$tmp/prefix"
mkdir -p "$HOME/run" "$HOME/logs" "$PREFIX/var/service/styledash-health" "$tmp/bin"
touch "$PREFIX/var/service/styledash-health/run"
cat > "$tmp/bin/sv" <<'SV'
#!/usr/bin/env bash
set -eu
cmd="$1"; service="$2"
case "$cmd" in
  down) touch "$service/down-test" ;;
  up) rm -f "$service/down-test" ;;
  status) [ -f "$service/down-test" ] && echo down || echo run ;;
  *) exit 2 ;;
esac
SV
chmod +x "$tmp/bin/sv"
export PATH="$tmp/bin:$PATH"
pidfile="$HOME/run/styledash-health.pid"
childfile="$HOME/run/fake-supervised-child.pid"
service="$PREFIX/var/service/styledash-health"
spawn_child() {{
  bash -c 'printf "%s\\n" "$$" > "$1"; trap "exit 0" TERM INT; while :; do sleep 1; done' V4Y_SUPERVISED_WATCHDOG "$pidfile" </dev/null >/dev/null 2>&1 &
  printf '%s\n' "$!" > "$childfile"
}}
supervisor_loop() {{
  while :; do
    if [ ! -f "$service/down-test" ]; then
      child="$(cat "$childfile" 2>/dev/null || true)"
      case "$child" in ''|*[!0-9]*) child='' ;; esac
      if [ -z "$child" ] || ! kill -0 "$child" 2>/dev/null; then spawn_child; fi
    fi
    sleep 0.05
  done
}}
supervisor_loop </dev/null >/dev/null 2>&1 & supervisor_pid=$!
cleanup() {{
  touch "$service/down-test" 2>/dev/null || true
  kill "$supervisor_pid" 2>/dev/null || true
  wait "$supervisor_pid" 2>/dev/null || true
  child="$(cat "$childfile" 2>/dev/null || true)"
  if [ -n "$child" ]; then
    kill "$child" 2>/dev/null || true
    wait "$child" 2>/dev/null || true
  fi
  styledash_stop_matching_processes cleanup V4Y_SUPERVISED_WATCHDOG '' >/dev/null 2>&1 || true
  rm -rf "$tmp"
}}
trap cleanup EXIT INT TERM
for _ in $(seq 1 40); do [ -s "$pidfile" ] && break; sleep 0.05; done
[ -s "$pidfile" ]
old_pid="$(cat "$pidfile")"
kill "$old_pid"
for _ in $(seq 1 40); do new_pid="$(cat "$pidfile" 2>/dev/null || true)"; [ -n "$new_pid" ] && [ "$new_pid" != "$old_pid" ] && kill -0 "$new_pid" 2>/dev/null && break; sleep 0.05; done
[ "$(cat "$pidfile")" != "$old_pid" ]
styledash_watchdog_stop V4Y_SUPERVISED_WATCHDOG "$pidfile"
[ -f "$service/down-test" ]
[ "$(styledash_process_count V4Y_SUPERVISED_WATCHDOG '')" -eq 0 ]
sleep 0.2
[ "$(styledash_process_count V4Y_SUPERVISED_WATCHDOG '')" -eq 0 ]
styledash_watchdog_start V4Y_SUPERVISED_WATCHDOG "$pidfile" "$HOME/logs/watchdog.log"
[ ! -f "$service/down-test" ]
[ "$(styledash_process_count V4Y_SUPERVISED_WATCHDOG '')" -eq 1 ]
echo runit_watchdog_regression=PASS
'''
        result = self.run_shell_file(body, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("runit_watchdog_regression=PASS", result.stdout)

    def test_watchdog_manual_fallback_without_runit(self) -> None:
        library = bash_path(PROCESS_LIB)
        body = f'''#!/usr/bin/env bash
set -eu
source "{library}"
tmp="$(mktemp -d)"
export HOME="$tmp/home"
export PREFIX="$tmp/prefix"
mkdir -p "$HOME/bin" "$HOME/run" "$HOME/logs"
cat > "$HOME/bin/styledash-health" <<'SH'
#!/usr/bin/env bash
set -u
printf '%s\n' "$$" > "$HOME/run/styledash-health.pid"
trap 'rm -f "$HOME/run/styledash-health.pid"; exit 0' TERM INT EXIT
while :; do sleep 1; done
SH
chmod +x "$HOME/bin/styledash-health"
marker="$HOME/bin/styledash-health"
cleanup() {{ styledash_stop_matching_processes cleanup "$marker" '' >/dev/null 2>&1 || true; rm -rf "$tmp"; }}
trap cleanup EXIT INT TERM
styledash_watchdog_start "$marker" "$HOME/run/styledash-health.pid" "$HOME/logs/styledash-health.log"
pid="$(cat "$HOME/run/styledash-health.pid")"
styledash_assert_single_process "$pid" "$marker" ''
styledash_watchdog_stop "$marker" "$HOME/run/styledash-health.pid"
[ "$(styledash_process_count "$marker" '')" -eq 0 ]
[ ! -e "$HOME/run/styledash-health.pid" ]
echo manual_watchdog_fallback=PASS
'''
        result = self.run_shell_file(body)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("manual_watchdog_fallback=PASS", result.stdout)
