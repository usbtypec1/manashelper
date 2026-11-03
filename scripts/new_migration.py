"""Create the next V-numbered Alembic revision, forwarding revision flags."""

import re
import sys
from pathlib import Path

from alembic.config import Config
from alembic.config import main as alembic_main
from alembic.script import ScriptDirectory


def main() -> None:
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    versions = [
        int(match[1]) for script in scripts.walk_revisions() if (match := re.match(r"V(\d+)_", Path(script.path).name))
    ]
    revision = f"V{max(versions, default=0) + 1}"
    alembic_main(argv=["revision", "--rev-id", revision, *sys.argv[1:]])


if __name__ == "__main__":
    main()
