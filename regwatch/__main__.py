"""Run the command line as ``python -m regwatch``, which a schedule uses."""

from __future__ import annotations

import sys

from regwatch.cli import main

if __name__ == "__main__":
    sys.exit(main())
