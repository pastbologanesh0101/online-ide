"""
Ensures the project root (where app.py, sandbox.py, db.py live) is on
sys.path when pytest collects tests from the tests/ directory.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
