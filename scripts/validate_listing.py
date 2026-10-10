#!/usr/bin/env python3
"""Validate this release offline: python3 scripts/validate_listing.py [--self-test].

listing.schema.json is a focused release schema, not a vendor schema. This
dependency-free evaluator supports only the keywords it uses and rejects other
keywords. File, skill, transport, and cross-manifest checks supplement the schema.
"""

import copy
import json
from pathlib import Path
import re
import struct
import sys
import tempfile
import zlib


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(Path(__file__).with_name("listing.schema.json").read_text())
KEYWORDS = {
    "$schema", "title", "type", "const", "properties", "required",
    "additionalProperties", "minLength", "maxLength", "pattern", "items",
    "maxItems", "uniqueItems",
}


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


def png(path):
    require(path.stat().st_size <= 5 * 1024 * 1024, f"icon exceeds 5 MiB: {path}")
    data = path.read_bytes()
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
    for name in ("logo", "logoDark", "composerIcon", "composerIconDark"):
        png(bundled(plugin, manifest["interface"][name]))
    extension = manifest["extensions"]["com.openai"]
    skill = bundled(plugin, extension["onboardingSkill"]).read_text()
    require(skill.startswith("---\n"), "missing skill front matter")
    header = skill.split("---\n", 2)[1]
    fields = dict(line.split(": ", 1) for line in header.strip().splitlines())
    require(fields.get("name") == "connect-stella", "invalid skill name")
    require(len(f"stella:{fields['name']}") <= 64, "skill identity too long")
    require(0 < len(fields.get("description", "")) <= 1024,
            "skill description must be 1–1024 characters")
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
            with path.open("rb") as stream:
                require(not stream.read(128).startswith(b"version https://git-lfs.github.com/spec/"),
                        f"LFS pointer: {path}")
    print("PASS: both manifests, both root entries, listing limits, HTTP config, skill, icons, package files")


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
                boundaries(value[key], child)
                missing = copy.deepcopy(value)
                del missing[key]
                check(missing, schema, key not in schema.get("required", []))
        if schema.get("type") == "array":
            boundaries(value[0] if value else "US", schema["items"])
            sample = [str(i) for i in range(schema["maxItems"])]
            if schema["items"].get("pattern") == "^[A-Z]{2}$":
                sample = [chr(65 + i // 26) + chr(65 + i % 26) for i in range(len(sample))]
            check(sample, schema, True)
            check(sample + ["ZZ"], schema, False)
        if "type" in schema:
            check(None, schema, False)

    boundaries(manifest, SCHEMA)
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
    print(f"PASS: {count} self-tests")


if __name__ == "__main__":
    try:
        require(sys.argv[1:] in ([], ["--self-test"]), "usage: validate_listing.py [--self-test]")
        if "--self-test" in sys.argv:
            self_test()
        package(ROOT)
    except (ValueError, KeyError, OSError, zlib.error) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
