#!/usr/bin/env python3
"""Reject release tags that differ from the CLI distribution version."""

import os
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAG = re.compile(r"v((?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))")


def validate(reference_type: str | None, tag: str, package_version: str) -> str:
    match = TAG.fullmatch(tag)
    if reference_type != "tag" or match is None:
        raise ValueError("CLI releases require a vMAJOR.MINOR.PATCH tag")
    if match[1] != package_version:
        raise ValueError(
            f"Release tag {tag} does not match package version {package_version}"
        )
    return package_version


def main() -> None:
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    validate(
        os.environ.get("GITHUB_REF_TYPE"),
        os.environ.get("GITHUB_REF_NAME", ""),
        version,
    )
    print(f"Validated CLI release {version}")


if __name__ == "__main__":
    main()
