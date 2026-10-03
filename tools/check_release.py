"""Validate the exact release pair and optionally write its SHA-256 checksums."""

import argparse
import configparser
import hashlib
import re
import tarfile
import zipfile
from email.parser import BytesParser
from importlib.metadata import distribution
from pathlib import Path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def check_release(directory: Path) -> list[tuple[Path, str]]:
    package = distribution("kard-x-sandbox")
    name, version = package.metadata["Name"], package.version
    require(name == "kard-x-sandbox", "Installed package has the wrong public name.")
    normalized = re.sub(r"[-_.]+", "_", name)
    stem = f"{normalized}-{version}"
    wheel_path = directory / f"{stem}-py3-none-any.whl"
    sdist_path = directory / f"{stem}.tar.gz"
    for path in (wheel_path, sdist_path):
        require(path.is_file(), f"Missing release artifact: {path}")

    info = f"{stem}.dist-info"
    source = f"{stem}/"
    with zipfile.ZipFile(wheel_path) as wheel, tarfile.open(sdist_path, "r:gz") as sdist:
        wheel_names = wheel.namelist()
        require(len(wheel_names) == len(set(wheel_names)), "Wheel contains duplicate paths.")
        metadata = BytesParser().parsebytes(wheel.read(f"{info}/METADATA"))
        for field in ("Name", "Version", "Requires-Python", "License-Expression"):
            require(metadata[field] == package.metadata[field], f"Wheel {field} differs from the project.")
        require(metadata["Description-Content-Type"] == "text/markdown", "README is not Markdown metadata.")
        require(set(metadata.get_all("Requires-Dist", [])) == set(package.metadata.get_all("Requires-Dist", [])),
                "Wheel dependencies differ from the project.")
        require(bool(wheel.read(f"{info}/licenses/LICENSE")), "MIT license is missing.")
        entries = configparser.ConfigParser()
        entries.read_string(wheel.read(f"{info}/entry_points.txt").decode("utf-8"))
        require(entries.get("console_scripts", "ttx", fallback="") == "ttx.cli:main", "ttx entry point is incorrect.")
        require(wheel.testzip() is None, "Wheel archive is corrupt.")
        require(all(member.startswith(("ttx/", "kardx/", f"{info}/")) for member in wheel_names),
                "Wheel contains files outside the game packages and metadata.")
        require(not any(member == f"{source}docs" or member.startswith(f"{source}docs/")
                        for member in sdist.getnames()), "Source archive contains personal documentation.")

        for member in wheel_names:
            if member.startswith(("ttx/", "kardx/")) and not member.endswith("/"):
                archived = sdist.extractfile(f"{source}src/{member}")
                require(archived is not None, f"Source archive is missing {member}.")
                with archived:
                    require(archived.read() == wheel.read(member), f"Source and wheel differ at {member}.")

        required_sources = (
            "pyproject.toml", "README.md", "LICENSE", "uv.lock", ".python-version",
            "CHANGELOG.md", "RELEASING.md", "tests/test_packaging.py", "tools/check_release.py",
        )
        for member in required_sources:
            require(sdist.getmember(f"{source}{member}").isfile(), f"Source archive is missing {member}.")
        sdist_metadata = sdist.extractfile(f"{source}PKG-INFO")
        require(sdist_metadata is not None, "Source archive has no package metadata.")
        with sdist_metadata:
            source_metadata = BytesParser().parse(sdist_metadata)
        require(source_metadata["Name"] == name and source_metadata["Version"] == version,
                "Source metadata does not match the wheel.")

    return [(path, hashlib.sha256(path.read_bytes()).hexdigest()) for path in (sdist_path, wheel_path)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=Path("dist/release"))
    parser.add_argument("--write-checksums", action="store_true")
    args = parser.parse_args()
    try:
        checked = check_release(args.directory)
        checksums = "".join(f"{digest}  {path.name}\n" for path, digest in checked)
        if args.write_checksums:
            (args.directory / "SHA256SUMS").write_text(checksums, encoding="utf-8")
    except (OSError, ValueError, KeyError, tarfile.TarError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"Release check failed: {exc}\n")
    print("Release metadata, entry point, license, and source/wheel contents match.")
    print(checksums, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
