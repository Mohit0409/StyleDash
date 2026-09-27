from __future__ import annotations

import subprocess
import tempfile
import unittest
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "ops" / "deploy-vibe4you.ps1"


@unittest.skipUnless(os.name == "nt", "deployment wrapper behavioral harness requires Windows PowerShell")
class DeployVibe4YouWrapperGateTests(unittest.TestCase):
    def run_gate(self, scenario: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            identity = root / "identity"
            identity.write_text("fixture", encoding="ascii")
            harness = root / "harness.ps1"
            harness.write_text(
                f'''$ErrorActionPreference = 'Continue'
$scenario = '{scenario}'
$identity = '{identity.as_posix()}'
$wrapper = '{WRAPPER.as_posix()}'
function git {{
  if ($args[0] -eq 'fetch') {{ $global:LASTEXITCODE = 0; return }}
  if ($args[0] -eq 'rev-parse') {{ $global:LASTEXITCODE = 0; return ('a' * 40) }}
  if ($args[0] -eq 'merge-base') {{ $global:LASTEXITCODE = $(if ($scenario -eq 'unmerged') {{ 1 }} else {{ 0 }}); return }}
  if ($args[0] -eq 'archive') {{ 'ARCHIVE_CALLED'; $global:LASTEXITCODE = 0; return }}
  throw "unexpected git invocation: $($args -join ' ')"
}}
function gh {{
  if ($args[0] -ne 'api') {{ throw 'unexpected gh invocation' }}
  $endpoint = $args | Where-Object {{ $_ -like 'repos/*' }} | Select-Object -Last 1
  if ($scenario -eq 'ci-failed') {{ '{{"check_runs":[]}}'; $global:LASTEXITCODE = 0; return }}
  if ($endpoint -like '*/check-runs') {{ '{{"check_runs":[{{"name":"StyleDash Required CI","head_sha":"{('a' * 40)}","status":"completed","conclusion":"success","details_url":"https://github.com/Mohit0409/StyleDash/actions/runs/123"}}]}}'; $global:LASTEXITCODE = 0; return }}
  if ($endpoint -like '*/actions/runs/123') {{ '{{"head_sha":"{('a' * 40)}","name":"Wrong workflow","path":".github/workflows/not-ci.yml","status":"completed","conclusion":"success"}}'; $global:LASTEXITCODE = 0; return }}
  throw "unexpected gh endpoint: $endpoint"
}}
& $wrapper -Commit ('a' * 40) -SshIdentity $identity
exit $LASTEXITCODE
''',
                encoding="utf-8",
            )
            return subprocess.run(
                ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(harness)],
                capture_output=True,
                text=True,
                cwd=ROOT,
                check=False,
            )

    def assert_refused_before_archive(self, scenario: str, expected: str) -> None:
        result = self.run_gate(scenario)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(expected, result.stdout + result.stderr)
        self.assertNotIn("ARCHIVE_CALLED", result.stdout + result.stderr)

    def test_unmerged_sha_is_refused_before_archive(self) -> None:
        self.assert_refused_before_archive("unmerged", "UNAPPROVED_SHA")

    def test_missing_exact_sha_ci_is_refused_before_archive(self) -> None:
        self.assert_refused_before_archive("ci-failed", "CI_NOT_GREEN")

    def test_wrong_workflow_identity_is_refused_before_archive(self) -> None:
        self.assert_refused_before_archive("workflow-mismatch", "CI_NOT_GREEN")


if __name__ == "__main__":
    unittest.main()
