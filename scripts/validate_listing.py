#!/usr/bin/env python3
"""Validate this release offline.

Usage: python3 scripts/validate_listing.py [--self-test] [--zip PACKAGE.zip]

listing.schema.json is a focused release schema, not a vendor schema. This
dependency-free evaluator supports only the keywords it uses and rejects other
keywords. File, skill, transport, and cross-manifest checks supplement the schema.
With --zip, the built archive is checked against the same package rules.
"""

import copy
import json
from pathlib import Path
import re
import struct
import sys
import tempfile
import zipfile
import zlib


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(Path(__file__).with_name("listing.schema.json").read_text())
KEYWORDS = {
    "$schema", "title", "type", "const", "properties", "required",
    "additionalProperties", "minLength", "maxLength", "pattern", "items",
    "minItems", "maxItems", "uniqueItems",
}
# The onboarding skill path is fixed by the package format.
ONBOARDING = "skills/get-started/SKILL.md"
# Light icon field -> optional dark variant field.
ICONS = {"logo": "logoDark", "composerIcon": "composerIconDark"}
# Package files that may start with a dot; every other hidden entry is rejected.
DOT_FILES = {".codex-plugin/plugin.json", ".claude-plugin/plugin.json", ".mcp.json"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(value, schema, path="$"):
    require(not set(schema) - KEYWORDS, f"{path}: unsupported schema keyword")
    if "const" in schema:
        require(type(value) is type(schema["const"]) and value == schema["const"],
                f"{path}: expected {schema['const']!r}")
    kind = schema.get("type")
    if kind:
        expected = {"object": dict, "string": str, "array": list}[kind]
        require(type(value) is expected, f"{path}: expected {kind}")
    if kind == "object":
        properties = schema.get("properties", {})
        require(not set(schema.get("required", [])) - set(value),
                f"{path}: missing required field")
        if schema.get("additionalProperties") is False:
            require(not set(value) - set(properties), f"{path}: unknown field")
        for key, item in value.items():
            if key in properties:
                validate(item, properties[key], f"{path}.{key}")
    elif kind == "string":
        require(len(value) >= schema.get("minLength", 0), f"{path}: empty text")
        require(len(value) <= schema.get("maxLength", float("inf")),
                f"{path}: text too long")
        if "pattern" in schema:
            require(re.search(schema["pattern"], value) is not None,
                    f"{path}: invalid text")
    elif kind == "array":
        require(len(value) >= schema.get("minItems", 0),
                f"{path}: too few items")
        require(len(value) <= schema.get("maxItems", float("inf")),
                f"{path}: too many items")
        if schema.get("uniqueItems"):
            require(len({json.dumps(x, sort_keys=True) for x in value}) == len(value),
                    f"{path}: duplicate items")
        for index, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{index}]")


def bundled(plugin, relative):
    require(relative.startswith("./"), "path must start with ./")
    path = plugin / relative
    require(".." not in Path(relative).parts, "path traversal")
    require(path.resolve().is_relative_to(plugin.resolve()), "path outside package")
    require(path.is_file() and not path.is_symlink(), f"missing file: {relative}")
    return path


def png(data, path):
    require(len(data) <= 5 * 1024 * 1024, f"icon exceeds 5 MiB: {path}")
    require(data[:8] == b"\x89PNG\r\n\x1a\n", f"invalid PNG: {path}")
    position, dimensions, image_data, ended = 8, None, bytearray(), False
    while position < len(data):
        require(position + 12 <= len(data), "truncated PNG chunk")
        length = struct.unpack(">I", data[position:position + 4])[0]
        kind = data[position + 4:position + 8]
        payload = data[position + 8:position + 8 + length]
        end = position + 12 + length
        require(end <= len(data), "truncated PNG")
        crc = struct.unpack(">I", data[end - 4:end])[0]
        require(zlib.crc32(kind + payload) == crc, "invalid PNG checksum")
        if position == 8:
            require(kind == b"IHDR" and length == 13, "missing PNG header")
            dimensions = struct.unpack(">II", payload[:8])
        if kind == b"IDAT":
            image_data.extend(payload)
        if kind == b"IEND":
            require(end == len(data), "trailing PNG data")
            ended = True
        position = end
    require(ended and image_data, "incomplete PNG")
    width, height = dimensions
    require(width == height and 48 <= width <= 4096, "icon dimensions out of range")
    require(dimensions == (512, 512), "release icons must be 512 x 512")
    require(bool(zlib.decompress(image_data)), "empty PNG image data")


def transport(config):
    # URL-backed transport in Codex; the shared HTTP discriminator is needed
    # by the other manifest format. No executable, headers, or auth secrets.
    require(config == {"mcpServers": {"stella": {
        "type": "http", "url": "https://api.stll.app/mcp",
    }}}, "expected one HTTPS stella server with type http")


def icons(manifest, read):
    """Check required icons and optional dark variants; read maps a ./path to bytes."""
    interface = manifest["interface"]
    for light, dark in ICONS.items():
        light_data = read(interface[light])
        png(light_data, interface[light])
        if dark in interface:
            dark_data = read(interface[dark])
            png(dark_data, interface[dark])
            require(dark_data != light_data,
                    f"{dark} repeats {light}; omit the optional dark variant instead")


def skill(text, folder):
    require(text.startswith("---\n"), f"missing skill front matter: {folder}")
    header = text.split("---\n", 2)[1]
    fields = dict(line.split(": ", 1) for line in header.strip().splitlines())
    require(fields.get("name") == folder, f"skill name must match its folder: {folder}")
    require(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", folder) is not None,
            f"invalid skill name: {folder}")
    require(len(f"stella:{folder}") <= 64, "skill identity too long")
    require(0 < len(fields.get("description", "")) <= 1024,
            "skill description must be 1–1024 characters")


def skills(files):
    """files maps package-relative POSIX paths to text for every skills/ entry."""
    folders = {}
    for name, text in files.items():
        parts = name.split("/")
        require(len(parts) == 3 and parts[2] == "SKILL.md",
                f"unexpected skills entry: {name}")
        folders[parts[1]] = text
    require(ONBOARDING.split("/")[1] in folders, f"missing {ONBOARDING}")
    for folder, text in folders.items():
        skill(text, folder)


def package_entry(name):
    """Reject entries that public package submission does not accept."""
    parts = name.split("/")
    require(name and not name.startswith("/") and "\\" not in name
            and ".." not in parts and "" not in parts, f"invalid package path: {name}")
    require(parts[0] != "hooks" and parts[-1] not in {"hooks.json", ".app.json"},
            f"lifecycle hooks and app references are not packaged: {name}")
    require(name not in {"plugin.json", "mcp.json"},
            f"one manifest and one MCP configuration only: {name}")
    require(name in DOT_FILES or not any(part.startswith(".") for part in parts),
            f"hidden package entry: {name}")


def archive(path, plugin):
    """Check a built package ZIP against the same rules as the source tree."""
    with zipfile.ZipFile(path) as package_zip:
        names = package_zip.namelist()
        require(len(names) == len(set(names)), "duplicate ZIP entries")
        files = {}
        for name in names:
            require(not name.endswith("/"), f"directory entry in ZIP: {name}")
            package_entry(name)
            files[name] = package_zip.read(name)
            source = plugin / name
            require(source.is_file() and source.read_bytes() == files[name],
                    f"ZIP entry differs from the package source: {name}")
    for required in (".codex-plugin/plugin.json", ".claude-plugin/plugin.json",
                     ".mcp.json", ONBOARDING, "README.md", "LICENSE"):
        require(required in files, f"ZIP is missing {required}")
    manifest = json.loads(files[".codex-plugin/plugin.json"])
    validate(manifest, SCHEMA)
    transport(json.loads(files[".mcp.json"]))

    def read(relative):
        require(relative.startswith("./"), "path must start with ./")
        require(relative[2:] in files, f"ZIP is missing {relative}")
        return files[relative[2:]]

    icons(manifest, read)
    skills({name: data.decode() for name, data in files.items()
            if name.startswith("skills/")})
    print(f"PASS: package ZIP ({len(files)} entries)")


def package(root):
    plugin = root / "plugins/stella"
    load = lambda path: json.loads(path.read_text())
    manifest = load(plugin / ".codex-plugin/plugin.json")
    validate(manifest, SCHEMA)
    require(manifest["name"] == "stella", "release name must be stella")
    require(tuple(map(int, manifest["version"].split("."))) > (1, 0, 0),
            "release must exceed hosted version 1.0.0")
    other = load(plugin / ".claude-plugin/plugin.json")
    for key in ("name", "version", "description", "author"):
        require(manifest[key] == other[key], f"manifest mismatch: {key}")
    icons(manifest, lambda relative: bundled(plugin, relative).read_bytes())
    bundled(plugin, manifest["extensions"]["com.openai"]["onboardingSkill"])
    skills({path.relative_to(plugin).as_posix(): path.read_text()
            for path in (plugin / "skills").rglob("*") if path.is_file()})
    require(len((plugin / "README.md").read_text().split()) >= 40,
            "README must contain at least 40 words")
    require((plugin / "LICENSE").is_file(), "missing LICENSE")
    transport(load(plugin / ".mcp.json"))
    agents = load(root / ".agents/plugins/marketplace.json")
    require(agents["name"] == "stella" and agents["interface"]["displayName"] == "stella",
            "invalid root listing identity")
    require(len(agents["plugins"]) == 1, "expected one root plugin entry")
    entry = agents["plugins"][0]
    require(entry["name"] == "stella" and entry["category"] == "Productivity"
            and entry["source"] == {"source": "local", "path": "./plugins/stella"},
            "invalid root listing entry")
    entries = load(root / ".claude-plugin/marketplace.json")["plugins"]
    require(len(entries) == 1 and entries[0]["source"] == "./plugins/stella",
            "invalid root plugin path")
    for key in ("name", "version", "description"):
        require(entries[0][key] == manifest[key], f"root entry mismatch: {key}")
    for path in plugin.rglob("*"):
        require(not path.is_symlink(), f"symlink in package: {path}")
        require(path.name not in {".git", ".gitmodules", ".DS_Store"},
                f"unwanted package entry: {path}")
        if path.is_file():
            package_entry(path.relative_to(plugin).as_posix())
            with path.open("rb") as stream:
                require(not stream.read(128).startswith(b"version https://git-lfs.github.com/spec/"),
                        f"LFS pointer: {path}")
    print("PASS: both manifests, both root entries, listing limits, HTTP config, skills, icons, package files")


def self_test():
    manifest = json.loads((ROOT / "plugins/stella/.codex-plugin/plugin.json").read_text())
    count = 0

    def check(value, schema, valid):
        nonlocal count
        try:
            validate(value, schema)
        except ValueError:
            require(not valid, "self-test rejected valid boundary")
        else:
            require(valid, "self-test accepted invalid boundary")
        count += 1

    # Every declared scalar limit and each array count/item limit, including
    # valid boundaries, missing fields, wrong types, duplicates and mentions.
    def boundaries(value, schema):
        if "maxLength" in schema:
            limit = schema["maxLength"]
            sample = "https://a/" if schema.get("pattern", "").startswith("^https") else "a"
            check(sample + "a" * (limit - len(sample)), schema, True)
            check(sample + "a" * (limit + 1 - len(sample)), schema, False)
        if schema.get("type") == "object":
            for key, child in schema["properties"].items():
                sample = value.get(key, "https://example.com/demo")
                boundaries(sample, child)
                missing = copy.deepcopy(value)
                missing.pop(key, None)
                check(missing, schema, key not in schema.get("required", []))
        if schema.get("type") == "array":
            boundaries(value[0] if value else "US", schema["items"])
            sample = [copy.deepcopy(value[0]) if value else str(i)
                      for i in range(schema["maxItems"])]
            if schema.get("uniqueItems"):
                sample = [str(i) for i in range(schema["maxItems"])]
            if schema["items"].get("pattern") == "^[A-Z]{2}$":
                sample = [chr(65 + i // 26) + chr(65 + i % 26) for i in range(len(sample))]
            check(sample, schema, True)
            check(sample + ["ZZ"], schema, False)
            if "minItems" in schema:
                check(sample[:schema["minItems"] - 1], schema, False)
        if "type" in schema:
            check(None, schema, False)

    boundaries(manifest, SCHEMA)
    with_demo = copy.deepcopy(manifest)
    with_demo["extensions"]["com.openai"]["review"]["demo_recording_url"] = "https://example.com/demo"
    check(with_demo, SCHEMA, True)
    for label, mutate in (
        ("four positive cases", lambda review: review["test_cases"]["positive"].pop()),
        ("129-character prompt", lambda review: review["test_cases"]["positive"][0].update(prompt="a" * 129)),
        ("empty tools", lambda review: review["test_cases"]["positive"][0].update(tools_triggered="")),
        ("HTTP demo URL", lambda review: review.update(demo_recording_url="http://example.com/demo")),
    ):
        bad = copy.deepcopy(manifest)
        mutate(bad["extensions"]["com.openai"]["review"])
        check(bad, SCHEMA, False)
        print(f"PASS: rejects {label}")
    for field, bad in [("defaultPrompt", ["same", "same"]),
                       ("defaultPrompt", ["Ask @stella"]),
                       ("websiteURL", "https://user:secret@stll.app")]:
        check(bad, SCHEMA["properties"]["interface"]["properties"][field], False)
    for field in ("id", "hooks", "apps", "test_credentials", "reviewer_instructions"):
        bad = copy.deepcopy(manifest)
        bad[field] = "unexpected"
        check(bad, SCHEMA, False)
    for bad in ({}, {"mcpServers": {"stella": {"url": "http://api.stll.app/mcp"}}}):
        try:
            transport(bad)
        except ValueError:
            count += 1
        else:
            raise ValueError("self-test accepted invalid transport")
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for relative in ("../outside", "./missing.png", "/outside"):
            try:
                bundled(root, relative)
            except ValueError:
                count += 1
            else:
                raise ValueError("self-test accepted invalid package path")
    count += package_self_test(manifest)
    print(f"PASS: {count} self-tests")


def rejects(label, action):
    try:
        action()
    except (ValueError, KeyError):
        print(f"PASS: rejects {label}")
        return 1
    raise ValueError(f"self-test accepted {label}")


def package_self_test(manifest):
    plugin = ROOT / "plugins/stella"
    count = 0
    good_skill = "---\nname: get-started\ndescription: Connect.\n---\n"
    skills({ONBOARDING: good_skill, "skills/other/SKILL.md": good_skill.replace("get-started", "other")})
    for label, files in (
        ("missing onboarding skill", {"skills/other/SKILL.md": good_skill.replace("get-started", "other")}),
        ("skill name differing from its folder", {ONBOARDING: good_skill.replace("get-started", "connect")}),
        ("skill without front matter", {ONBOARDING: "# Connect\n"}),
        ("nested skill file", {ONBOARDING: good_skill, "skills/get-started/a/b.md": ""}),
    ):
        count += rejects(label, lambda files=files: skills(files))
    for name in (".codex-plugin/plugin.json", ".mcp.json", "assets/logo.png", ONBOARDING):
        package_entry(name)
    for name in ("hooks/hooks.json", "hooks.json", "x/.app.json", "plugin.json", "mcp.json",
                 "../outside", "/outside", "a//b", ".env", "assets/.hidden", "a\\b"):
        count += rejects(f"package entry {name}", lambda name=name: package_entry(name))
    logo = (plugin / "assets/logo.png").read_bytes()
    copy_dark = copy.deepcopy(manifest)
    copy_dark["interface"]["logoDark"] = copy_dark["interface"]["logo"]
    count += rejects("dark icon identical to its light icon",
                     lambda: icons(copy_dark, lambda relative: logo))
    with tempfile.TemporaryDirectory() as temporary:
        sources = {path.relative_to(plugin).as_posix(): path.read_bytes()
                   for path in sorted(plugin.rglob("*")) if path.is_file()
                   and path.name != ".DS_Store"}

        def build(name, changes):
            path = Path(temporary) / name
            with zipfile.ZipFile(path, "w") as package_zip:
                for relative, data in {**sources, **changes}.items():
                    if data is not None:
                        package_zip.writestr(relative, data)
            return path

        archive(build("good.zip", {}), plugin)
        for label, changes in (
            ("ZIP without the onboarding skill", {ONBOARDING: None}),
            ("ZIP without the composer icon", {"assets/composer-icon.png": None}),
            ("ZIP with lifecycle hooks", {"hooks/hooks.json": b"{}"}),
            ("ZIP with an app reference", {".app.json": b"{}"}),
            ("ZIP with a hidden file", {".env": b"TOKEN=x"}),
            ("ZIP entry differing from source", {"README.md": b"stale"}),
        ):
            count += rejects(label, lambda name=label, changes=changes:
                             archive(build(f"{len(name)}.zip", changes), plugin))
    return count


if __name__ == "__main__":
    try:
        arguments = sys.argv[1:]
        test = arguments[:1] == ["--self-test"]
        zip_path = arguments[1 + test:] if arguments[test:test + 1] == ["--zip"] else []
        require(len(arguments) == test + (2 if zip_path else 0) and len(zip_path) <= 1,
                "usage: validate_listing.py [--self-test] [--zip PACKAGE.zip]")
        if test:
            self_test()
        package(ROOT)
        if zip_path:
            archive(Path(zip_path[0]), ROOT / "plugins/stella")
    except (ValueError, KeyError, OSError, zlib.error, zipfile.BadZipFile,
            UnicodeDecodeError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
