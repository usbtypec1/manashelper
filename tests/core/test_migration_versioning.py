import re
import shutil
import subprocess
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[2]


def test_numbered_revisions_extend_existing_history_without_a_database(tmp_path):
    original = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
    original_head = original.get_current_head()
    last_number = max(int(re.match(r"V(\d+)_", Path(script.path).name)[1]) for script in original.walk_revisions())
    scripts = tmp_path / "alembic"
    shutil.copytree(ROOT / "alembic" / "versions", scripts / "versions")
    shutil.copyfile(ROOT / "alembic" / "script.py.mako", scripts / "script.py.mako")
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(scripts))
    config_path = tmp_path / "alembic.ini"
    with config_path.open("w") as stream:
        config.file_config.write(stream)

    for message in ("first example", "second example"):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "new_migration.py"), "-m", message],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    updated = ScriptDirectory.from_config(Config(str(config_path)))
    second = updated.get_revision(updated.get_current_head())
    first = updated.get_revision(second.down_revision)
    assert first.down_revision == original_head
    assert first.revision == f"V{last_number + 1}"
    assert second.revision == f"V{last_number + 2}"
    for revision in (first, second):
        assert Path(revision.path).name.startswith(revision.revision + "_")
    assert first.revision != second.revision
    for revision in original.walk_revisions():
        retained = updated.get_revision(revision.revision)
        assert retained.down_revision == revision.down_revision
        assert Path(retained.path).read_bytes() == Path(revision.path).read_bytes()
