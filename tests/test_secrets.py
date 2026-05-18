"""
Verify no new potential secrets have been introduced since the baseline was committed.

If this test fails:
  1. Run: detect-secrets scan --baseline .secrets.baseline
  2. Run: detect-secrets audit .secrets.baseline   # mark any false positives
  3. Commit the updated .secrets.baseline

detect-secrets docs: https://github.com/Yelp/detect-secrets
"""

import subprocess
import sys
from pathlib import Path


def test_no_new_secrets():
    baseline = Path(__file__).resolve().parent.parent / ".secrets.baseline"
    assert baseline.exists(), (
        ".secrets.baseline not found. "
        "Generate it with: detect-secrets scan > .secrets.baseline"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "detect_secrets",
            "scan",
            "--baseline",
            str(baseline),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "detect-secrets found potential secrets not present in the baseline.\n\n"
        "To investigate:\n"
        "  detect-secrets scan --baseline .secrets.baseline\n"
        "  detect-secrets audit .secrets.baseline\n\n"
        f"Raw output:\n{result.stdout}\n{result.stderr}"
    )
