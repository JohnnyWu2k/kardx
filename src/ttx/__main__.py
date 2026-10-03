"""Allow `python -m ttx` to use the installed console entry point."""

from ttx.cli import main

raise SystemExit(main())
