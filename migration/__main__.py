#!/usr/bin/env python3
"""
CLI entry point for nevernet-sql-diff
"""

import sys
import os

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import main

if __name__ == "__main__":
    sys.exit(main())
