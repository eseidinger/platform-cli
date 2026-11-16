"""Keep publishing restricted to tags matching the packaged version."""

import importlib.util
from pathlib import Path

import pytest


def release_script():
    path = Path(__file__).resolve().parents[1] / "scripts/cli-release.py"
    spec = importlib.util.spec_from_file_location("cli_release", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_only_matching_strict_version_tags_can_publish():
    validate = release_script().validate
    assert validate("tag", "v1.2.3", "1.2.3") == "1.2.3"
    for kind, tag, version in (
        ("branch", "v1.2.3", "1.2.3"),
        ("tag", "v1.2.4", "1.2.3"),
        ("tag", "v01.2.3", "1.2.3"),
        ("tag", "v1.2.3\ninjected", "1.2.3"),
        ("tag", "v1.2.3rc1", "1.2.3"),
        ("tag", "cli-v1.2.3", "1.2.3"),
    ):
        with pytest.raises(ValueError):
            validate(kind, tag, version)
