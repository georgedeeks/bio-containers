#!/usr/bin/env python3
"""Create a tool's Dockerfile, workflow and notes without replacing existing files."""

import argparse
import json
import re
import shlex
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tool", help="lowercase folder/image name, e.g. samtools")
    parser.add_argument("package", help="[channel::]package=version[=build]")
    parser.add_argument("executable", help="installed command, e.g. samtools")
    parser.add_argument("--channel", help="optional additional Conda channel name")
    parser.add_argument("--smoke-arg", action="append", help="repeat for each argument; default: --help")
    args = parser.parse_args()

    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.tool):
        parser.error("tool must contain lowercase letters/digits with optional internal hyphens")
    package_pattern = r"(?:[a-z0-9][a-z0-9_-]*::)?[a-z0-9][a-z0-9_.-]*=[A-Za-z0-9][A-Za-z0-9_.+-]*(?:=[A-Za-z0-9][A-Za-z0-9_.+-]*)?"
    if not re.fullmatch(package_pattern, args.package):
        parser.error("use a pinned package=version or channel::package=version[=build]")
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.+-]*", args.executable):
        parser.error("executable must be a command name, not a path or shell expression")
    if args.channel and not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", args.channel):
        parser.error("channel must be a simple Conda channel name")
    smoke = [args.executable, *(args.smoke_arg or ["--help"])]
    if any("\n" in value or "\r" in value or "\x00" in value for value in smoke):
        parser.error("smoke command arguments must be single-line strings without NUL bytes")

    root = Path(__file__).resolve().parent.parent
    tool_dir = root / args.tool
    workflow = root / ".github" / "workflows" / f"build-{args.tool}.yml"
    if tool_dir.exists() or tool_dir.is_symlink() or workflow.exists() or workflow.is_symlink():
        parser.error("tool directory or workflow already exists; edit it explicitly instead")

    replacements = {
        "__TOOL__": args.tool,
        "__PACKAGE_SPEC__": args.package,
        "__EXECUTABLE__": args.executable,
        "__EXTRA_CHANNEL__": f"--channel {args.channel}" if args.channel else "",
        "__SMOKE_JSON__": json.dumps(smoke),
        "__SMOKE_SHELL__": shlex.join(smoke),
    }
    files = [("Dockerfile.tmpl", tool_dir / "Dockerfile"),
             ("README.md.tmpl", tool_dir / "README.md"),
             ("workflow.yml.tmpl", workflow)]
    rendered = []
    for template, destination in files:
        content = (root / "templates" / template).read_text()
        content = re.sub(r"__[A-Z_]+__", lambda match: replacements[match.group()], content)
        rendered.append((destination, content))

    # Render everything before creating paths, and use exclusive writes.
    tool_dir.mkdir()
    workflow.parent.mkdir(parents=True, exist_ok=True)
    for destination, content in rendered:
        with destination.open("x") as output:
            output.write(content)
        print(f"Created {destination.relative_to(root)}")
    print(f"Next: check HPC_COMPATIBILITY.md, complete {args.tool}/README.md, review, commit and push.")


if __name__ == "__main__":
    main()
