"""Guards a mistake this workspace has now made twice.

None of these packages use `__init__.py` in their test directories, so
pytest imports test modules by bare basename under its rootdir-relative
import mode. Two test files sharing a basename across *different*
packages therefore collide and break collection — but only when pytest is
invoked without a package path, which is exactly the invocation nobody
runs day to day.

First occurrence: `test_coverage.py` in both atlas-detect and
atlas-redteam. Second: `test_report.py` in both atlas-assurance and
atlas-redteam, introduced by this very package and caught only because a
README claimed basenames were unique and that claim got checked. This
test makes the invariant enforceable instead of remembered.
"""

from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_no_duplicate_test_module_basenames_across_packages() -> None:
    test_files = list(REPO_ROOT.glob("packages/*/tests/**/test_*.py"))
    assert len(test_files) > 20, "glob found suspiciously few test files — check the pattern"

    counts = Counter(p.name for p in test_files)
    duplicates = {
        name: sorted(str(p.relative_to(REPO_ROOT)) for p in test_files if p.name == name)
        for name, count in counts.items()
        if count > 1
    }

    assert not duplicates, (
        "test module basenames must be unique across packages (no __init__.py in these "
        f"test dirs, so pytest imports by bare basename and these collide): {duplicates}"
    )
