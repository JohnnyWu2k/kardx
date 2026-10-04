# Release guide

The current release candidate is `0.2.0`. Version `0.1.0` is already published. The PyPI distribution is `kard-x-sandbox`, and the main command is `ttx`. The **Prepare release** GitHub Actions workflow validates distributions and provides downloadable artifacts. The maintainer uploads the verified files manually.

## Build and validate

From the repository root, use uv 0.12.7 or newer:

```powershell
uv sync --locked --reinstall-package kard-x-sandbox
uv run --locked pytest -q
uv run --locked ttx --version
uv build --no-sources --out-dir dist/release
uv run --locked python tools/check_release.py dist/release --write-checksums
uv run --isolated --no-project --python 3.12 --with twine twine check --strict dist/release/kard_x_sandbox-0.2.0.tar.gz dist/release/kard_x_sandbox-0.2.0-py3-none-any.whl
```

The reinstall option repairs shared command launchers in existing checkouts that were previously installed under the `ttx` distribution name.

`check_release.py` verifies package identity, version, dependencies, license, console entry point, and matching runtime files in the source distribution and wheel. It also rejects personal documentation in the source archive and writes `dist/release/SHA256SUMS`. Twine checks PyPI metadata and README formatting.

Run the complete tests against installed distributions in isolated environments. These commands also confirm that imports come from the installed package rather than the checkout's `src/` directory:

```powershell
uv run --isolated --no-project --python 3.10 --with .\dist\release\kard_x_sandbox-0.2.0-py3-none-any.whl --with 'pytest>=8,<10' python -c "import pathlib,sys,ttx,kardx,pytest; source=(pathlib.Path.cwd()/'src').resolve(); assert all(not pathlib.Path(module.__file__).resolve().is_relative_to(source) for module in (ttx,kardx)); sys.exit(pytest.main(['tests','-q']))"
uv run --isolated --no-project --python 3.12 --with .\dist\release\kard_x_sandbox-0.2.0.tar.gz --with 'pytest>=8,<10' python -c "import pathlib,sys,ttx,kardx,pytest; source=(pathlib.Path.cwd()/'src').resolve(); assert all(not pathlib.Path(module.__file__).resolve().is_relative_to(source) for module in (ttx,kardx)); sys.exit(pytest.main(['tests','-q']))"
uvx --from .\dist\release\kard_x_sandbox-0.2.0-py3-none-any.whl ttx --version
```

## Manual playthrough

Launch the built wheel in a real terminal:

```powershell
uvx --from .\dist\release\kard_x_sandbox-0.2.0-py3-none-any.whl ttx
```

Check hosting and LAN discovery, creating/loading a Unicode-named world, movement and jumping, held-button gathering and building, all four viewport edges, the ten-slot hotbar, the `E` backpack, entering and leaving combat, pause, window resizing, saving and rehosting after quitting. Confirm that text from world-name input does not remain in loading screens or the world, and that opening a menu, releasing the mouse or exhausting a block stack stops a held action. Perform a playthrough on both Windows and Linux before publication. Automated tests do not validate the feel or appearance of a real terminal session.

## Manual publication

Upload only the exact two files for the intended version. The `dist/` directory can contain older builds, and `SHA256SUMS` is not a distribution to upload.

Preview the upload plan:

```powershell
uv publish --dry-run --trusted-publishing never dist/release/kard_x_sandbox-0.2.0.tar.gz dist/release/kard_x_sandbox-0.2.0-py3-none-any.whl
```

The preview can access the index. Do not add `--offline`: uv 0.12.7 rejects publication commands in offline mode, including dry runs.

Set the PyPI API token in your own shell's `UV_PUBLISH_TOKEN` environment variable, then upload:

```powershell
uv publish --trusted-publishing never dist/release/kard_x_sandbox-0.2.0.tar.gz dist/release/kard_x_sandbox-0.2.0-py3-none-any.whl
```

Keep the token out of source files, documentation, and version control. Uploaded files cannot be replaced with different contents under the same filenames; bump the version if a published release needs a fix.

For a TestPyPI trial, use a TestPyPI token and the same artifacts:

```powershell
uv publish --index testpypi --trusted-publishing never dist/release/kard_x_sandbox-0.2.0.tar.gz dist/release/kard_x_sandbox-0.2.0-py3-none-any.whl
```

After publication, verify the public installation:

```powershell
uvx --from kard-x-sandbox ttx
uv tool install kard-x-sandbox
ttx --version
```

Commit the code, `pyproject.toml`, `uv.lock`, README, and release notes before publishing so that source links correspond to the release. Create the version tag and GitHub release after a successful upload.

## Documentation and subsequent releases

Keep public documents in English. Personal review reports, working notes, and Traditional Chinese copies belong under `docs/`, which is ignored by Git and excluded from release archives.

For the next release, use `uv version --bump patch` (or `minor` / `major`), update `CHANGELOG.md` and the example artifact filenames in this guide, then repeat the checks. `ttx --version` reads the installed distribution metadata, so there is no second version constant to update.

## Current limitations

- Multiplayer battle results and player identity are client-reported; the current release targets trusted local/LAN sessions.
- Named worlds and player profiles are saved on the host, with periodic autosaves, explicit saves and a save on shutdown. Save files are local and are not synchronized between hosts.
- Linux has automated coverage; a manual Linux terminal playthrough remains outstanding.

References: [uv building and publishing](https://docs.astral.sh/uv/guides/package/), [uv tool installation](https://docs.astral.sh/uv/guides/tools/), and [uv source exclusions](https://docs.astral.sh/uv/reference/settings/#source-exclude).
