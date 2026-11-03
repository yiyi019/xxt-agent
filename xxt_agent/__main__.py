import sys
from pathlib import Path

pkg_parent = str(Path(__file__).resolve().parent.parent)
if pkg_parent not in sys.path:
    sys.path.insert(0, pkg_parent)

from xxt_agent.cli import main

if __name__ == "__main__":
    sys.exit(main())
