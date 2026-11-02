# -*- coding: utf-8 -*-
import sys
from pathlib import Path

# Ensure Xuexitong root is in sys.path for test discovery from any directory
pkg_parent = str(Path(__file__).resolve().parent.parent.parent)
if pkg_parent not in sys.path:
    sys.path.insert(0, pkg_parent)
