"""Keep the reusable engine importable without loading the Telegram application."""

import ast
import subprocess
import sys
from textwrap import dedent

import pytest

from tests.paths import PROJECT_ROOT


def test_engine_and_shared_metadata_import_without_host_application(tmp_path):
    script = dedent("""
        import importlib
        import pkgutil
        import sys

        import common
        import ui_flows

        for package in (common, ui_flows):
            for module in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
                importlib.import_module(module.name)

        from common.database import Base

        assert not Base.metadata.tables
        assert not any(name == "manashelper" or name.startswith("manashelper.") for name in sys.modules)
    """)
    result = subprocess.run([sys.executable, "-I", "-c", script], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("package", "forbidden"),
    [
        ("ui_flows", {"manashelper", "aiogram", "fastapi", "sqlalchemy", "dishka"}),
        ("common", {"manashelper", "ui_flows", "aiogram", "fastapi"}),
    ],
)
def test_package_dependencies_point_towards_shared_infrastructure(package, forbidden):
    for path in (PROJECT_ROOT / "src" / package).rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                assert module.split(".")[0] not in forbidden, f"{path}: dependency on {module}"
