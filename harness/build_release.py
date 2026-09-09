"""Assemble the release zip: the official embeddable Python, the runtime wheels from uv.lock
extracted next to it, the app and the launcher, in one folder.

    uv run python harness/build_release.py [--skip-tests] [--skip-smoke] [--keep-stage]
    uv run python harness/build_release.py --notes        # print the release notes and stop

Layout of the zip (one top folder):

    Calandria-<version>/
      Calandria.cmd  README.md  CHANGELOG.md
      python/        python.exe, python314.zip, python314._pth (python314.zip / . /
                     Lib\\site-packages / ..\\app), the DLLs, Lib/site-packages/<wheels extracted>
      app/calandria/ the package (no bytecode)

Wheels come from the URLs in uv.lock and are checked against the lock's sha256. lxml and pillow
take the compiled cp314-cp314-win_amd64 wheel (never cp314t); everything else takes the pure
wheel, so the zip carries the fewest native files. The whole test suite runs first (the parity
gates included) and the staged interpreter is smoke-tested before the zip is written. Downloads
are cached in build/cache/.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tomllib
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY_VERSION = "3.14.7"
EMBED_URL = f"https://www.python.org/ftp/python/{PY_VERSION}/python-{PY_VERSION}-embed-amd64.zip"
EMBED_SHA256 = ""              # pinned after the first verified download (see the plan, Task 3)
NATIVE = {"lxml", "pillow"}    # the only packages whose compiled wheel is vendored
PLATFORM_TAG = "cp314-cp314-win_amd64"
PURE_TAGS = ("py3-none-any", "py2.py3-none-any")
PTH_NAME = "python314._pth"
PTH_TEXT = "python314.zip\n.\nLib\\site-packages\n..\\app\n"
CACHE = ROOT / "build" / "cache"
STAGE = ROOT / "build" / "stage"
DIST = ROOT / "dist"
SMOKE_IMPORTS = "import lxml, PIL, fontTools, fpdf, calandria"

DESCRIPTION = (
    "**Calandria** is an offline Word (`.docx`) redline / compare tool from HeckSoft (a King of Heck "
    "Company), the successor to SorkWhare Compare. Extract the zip anywhere, double-click "
    "`Calandria.cmd`, drop the original and the modified document on the page: the redline is laid "
    "out page by page on screen and saved as a PDF from the same drawing. No install, no admin "
    "rights, no internet connection; the documents never leave your computer."
)


def pth_lines() -> list[str]:
    return PTH_TEXT.splitlines()


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def runtime_packages(lock: dict) -> list[dict]:
    """The lock entries of the project's runtime closure, sorted by name (dev groups excluded)."""
    by_name = {p["name"]: p for p in lock["package"]}
    project = next(p for p in lock["package"] if "editable" in p.get("source", {}))
    wanted, todo = set(), [d["name"] for d in project.get("dependencies", [])]
    while todo:
        name = todo.pop()
        if name in wanted:
            continue
        wanted.add(name)
        todo.extend(d["name"] for d in by_name[name].get("dependencies", []))
    return [by_name[n] for n in sorted(wanted)]


def pick_wheel(pkg: dict) -> tuple[str, str]:
    """(url, sha256) of the wheel to vendor: compiled for NATIVE packages, pure for the rest."""
    tags = (PLATFORM_TAG,) if pkg["name"] in NATIVE else PURE_TAGS
    for tag in tags:
        for w in pkg.get("wheels", []):
            if w["url"].endswith(f"-{tag}.whl"):
                return w["url"], w["hash"].removeprefix("sha256:")
    raise LookupError(f"{pkg['name']} {pkg['version']}: no wheel tagged {' / '.join(tags)} in uv.lock")


def wheel_members(names: list[str]) -> list[str]:
    """The wheel members to extract: no `<dist>.data/` trees (scripts, headers) and no RECORD."""
    out = []
    for n in names:
        top = n.split("/", 1)[0]
        if top.endswith(".data"):
            continue
        if top.endswith(".dist-info") and n.endswith("/RECORD"):
            continue
        out.append(n)
    return out


def stage_app(src: Path, dst: Path) -> list[Path]:
    """Copy the package tree without bytecode; return the copied files, sorted."""
    copied = []
    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        if "__pycache__" in rel.parts or path.suffix == ".pyc" or path.is_dir():
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        copied.append(target)
    return copied


def changelog_entry(text: str, version: str) -> str:
    """The `## v<version>` section of the changelog (heading through the line before the next `## `)."""
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith(f"## v{version} ")
                  or l == f"## v{version}"), None)
    if start is None:
        raise LookupError(f"CHANGELOG.md has no '## v{version}' entry")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).rstrip() + "\n"


def release_notes(changelog_text: str, version: str) -> str:
    entry = changelog_entry(changelog_text, version)
    return (f"{DESCRIPTION}\n\n---\n\n{entry}\n---\n\n"
            f"**Download:** `Calandria-{version}.zip` (attached below) — extract it anywhere and "
            f"double-click `Calandria.cmd` inside the extracted folder. 64-bit Windows; no install.\n")
