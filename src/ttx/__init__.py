"""Kard-X Sandbox's TTX multiplayer game package."""

from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]
try:
    __version__ = version("kard-x-sandbox")
except PackageNotFoundError:
    # Source-only imports have no installed distribution metadata.
    __version__ = "0+unknown"
