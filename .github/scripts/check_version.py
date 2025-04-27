#!/usr/bin/env python

import os
import sys

try:
    import tomllib
except ModuleNotFoundError:
    print("Error: tomllib not found (requires Python 3.11+).", file=sys.stderr)
    sys.exit(1)

# Get tag from GitHub Actions environment variable
tag_name = os.environ.get("GITHUB_REF_NAME")
if not tag_name:
    print("Error: GITHUB_REF_NAME environment variable not found.", file=sys.stderr)
    sys.exit(1)

# Define path to pyproject.toml relative to script location (assuming script is in .github/scripts/)
# Adjust if script is placed elsewhere
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, "..", ".."))  # Go up two levels
pyproject_path = os.path.join(project_root, "pyproject.toml")

print(f"Checking Git tag '{tag_name}' against version in {pyproject_path}...")

try:
    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)
    project_version = data.get("project", {}).get("version")
    if not project_version:
        print(
            f"Error: Could not find [project.version] in {pyproject_path}",
            file=sys.stderr,
        )
        sys.exit(1)
except FileNotFoundError:
    print(f"Error: {pyproject_path} not found.", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"Error reading or parsing {pyproject_path}: {e}", file=sys.stderr)
    sys.exit(1)

print(f"Git tag: {tag_name}")
print(f"pyproject.toml version: {project_version}")

if tag_name == project_version:
    print("Version check passed.")
    sys.exit(0)
else:
    print(
        f"Error: Git tag '{tag_name}' does not match pyproject.toml version '{project_version}'",
        file=sys.stderr,
    )
    sys.exit(1)
