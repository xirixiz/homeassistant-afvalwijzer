"""Test that constants in `const.py` are referenced elsewhere in the repo.

This verifies that constants defined in `custom_components/afvalwijzer/const/const.py`
are used somewhere outside that file. It ignores a small set of known
exceptions.
"""

import ast
from pathlib import Path
import re

IGNORED = {"API", "NAME", "VERSION", "ISSUE_URL", "DOMAIN_DATA", "STARTUP_MESSAGE"}


def _collect_constants(const_path: Path):
    src = const_path.read_text(encoding="utf8")
    module = ast.parse(src)
    names = []
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    name = target.id
                    if name.isupper() and not name.startswith("_"):
                        names.append(name)
    return sorted(set(names))


def _is_referenced(repo_root: Path, name: str, const_path: Path) -> bool:
    pattern = re.compile(r"\b" + re.escape(name) + r"\b")
    for path in repo_root.rglob("*"):
        if path.resolve() == const_path.resolve() or not path.is_file():
            continue
        text = path.read_text(encoding="utf8")
        if pattern.search(text):
            return True
    return False


def test_constants_are_used_somewhere():
    """Check all constants created in const.py are used somewhere."""
    repo_root = Path(__file__).resolve().parents[1]
    const_path = repo_root / "const" / "const.py"

    assert const_path.exists(), f"const.py not found at {const_path}"

    constants = _collect_constants(const_path)
    constants = [c for c in constants if c not in IGNORED]
    unused = [
        name for name in constants if not _is_referenced(repo_root, name, const_path)
    ]

    if unused:
        unused.sort()
        pytest_msg = (
            "The following constants in const.py are not referenced elsewhere: "
            + ", ".join(unused)
        )
        raise AssertionError(pytest_msg)
