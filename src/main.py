"""Compatibility entry point for the old `python -m src.main` command."""

from .kardx.main import main


if __name__ == "__main__":
    main()
