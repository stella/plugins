#!/usr/bin/env python3
"""Build a reproducible stella package: python3 scripts/build_zip.py [output.zip]."""

import hashlib
import os
from pathlib import Path
import sys
from zipfile import ZIP_STORED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/stella"
DOT_DIRECTORIES = {".codex-plugin", ".claude-plugin"}
MTIME = (1980, 1, 1, 0, 0, 0)


def package_files(plugin):
    files = []
    for directory, directories, names in os.walk(plugin, followlinks=False):
        parent = Path(directory)
        directories[:] = [name for name in directories
                          if not name.startswith(".")
                          or (parent == plugin and name in DOT_DIRECTORIES)]
        for name in directories:
            if (parent / name).is_symlink():
                raise ValueError(f"symlink in package: {parent / name}")
        for name in names:
            if name.startswith(".") and not (parent == plugin and name == ".mcp.json"):
                continue
            path = parent / name
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"not a regular package file: {path}")
            files.append(path)
    return sorted(files, key=lambda path: path.relative_to(plugin).as_posix())


def build_zip(plugin, output):
    if output.resolve().is_relative_to(plugin.resolve()):
        raise ValueError("ZIP output must be outside the plugin directory")
    files = package_files(plugin)
    required = {".codex-plugin/plugin.json", ".claude-plugin/plugin.json", ".mcp.json"}
    if not required.issubset({path.relative_to(plugin).as_posix() for path in files}):
        raise ValueError("missing required plugin manifests or MCP configuration")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Stored entries avoid compressor-version differences; metadata and order
    # are independent of local file timestamps and permissions.
    with ZipFile(output, "w", compression=ZIP_STORED) as archive:
        for path in files:
            entry = ZipInfo(path.relative_to(plugin).as_posix(), MTIME)
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, path.read_bytes())
    return hashlib.sha256(output.read_bytes()).hexdigest()


if __name__ == "__main__":
    try:
        if len(sys.argv) > 2:
            raise ValueError("usage: build_zip.py [output.zip]")
        output = Path(sys.argv[1]) if len(sys.argv) == 2 else ROOT / "dist/stella.zip"
        print(f"sha256: {build_zip(PLUGIN, output)}")
    except (ValueError, OSError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
