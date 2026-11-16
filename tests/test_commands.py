import json

import httpx
from typer.testing import CliRunner

from platform_cli.__main__ import app
from platform_cli.client import PlatformClient
from platform_cli.commands import _body
from platform_cli.models import OperationAccepted, OperationStatus
from platform_cli.registry import COMMANDS


def test_project_grant_accepts_username_without_issuer_or_subject():
    spec = next(command for command in COMMANDS if command.command == "grants set")
    assert _body(spec, {"preferred_username": "alice", "role": "developer"}) == {
        "preferred_username": "alice",
        "role": "developer",
    }


def test_auth_status_reports_environment_source_without_token(monkeypatch):
    monkeypatch.setenv("PLATFORM_API_URL", "https://platform.example")
    monkeypatch.setenv("PLATFORM_ACCESS_TOKEN", "should-not-appear")

    result = CliRunner().invoke(app, ["auth", "status", "--output", "json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "source": "access-token-environment",
        "persistent": False,
    }
    assert "should-not-appear" not in result.output


def test_metrics_requires_component_before_contacting_api(monkeypatch):
    monkeypatch.setenv("PLATFORM_API_URL", "https://platform.example")
    monkeypatch.setenv("PLATFORM_ACCESS_TOKEN", "fixture-token")

    def unexpected_client(config):
        raise AssertionError("API client created")

    monkeypatch.setattr("platform_cli.commands.PlatformClient", unexpected_client)
    result = CliRunner().invoke(app, ["metrics", "get", "--project", "demo"])

    assert result.exit_code == 2


def test_json_output_formats_configuration_errors(monkeypatch, tmp_path):
    monkeypatch.setenv("DEVPLAT_CONFIG_DIR", str(tmp_path))
    for key in (
        "PLATFORM_API_URL",
        "PLATFORM_ACCESS_TOKEN",
        "PLATFORM_TOKEN_ENDPOINT",
        "PLATFORM_CLIENT_ID",
        "PLATFORM_CLIENT_SECRET",
    ):
        monkeypatch.delenv(key, raising=False)

    result = CliRunner().invoke(
        app,
        [
            "metrics",
            "get",
            "--project",
            "demo",
            "--component",
            "web",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 2
    assert json.loads(result.stderr) == {
        "status": None,
        "detail": "PLATFORM_API_URL is required",
        "code": "configuration_error",
        "request_id": None,
        "retryable": False,
    }


def test_quiet_deployment_wait_suppresses_progress(monkeypatch, tmp_path):
    monkeypatch.setenv("DEVPLAT_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("PLATFORM_API_URL", "https://platform.example")
    monkeypatch.setenv("PLATFORM_ACCESS_TOKEN", "fixture-token")

    class FakeClient:
        def __init__(self, config):
            self.config = config

        def access_token(self):
            return "fixture-token"

        def deploy(self, project, body, token, if_match):
            return OperationAccepted(
                operation_id="op-1",
                state="queued",
                revision=1,
                status_url="/v1/operations/op-1",
            )

        def close(self):
            pass

    status = OperationStatus.model_validate(
        {
            "operation_id": "op-1",
            "state": "succeeded",
            "revision": 1,
            "readiness": {"state": "ready"},
        }
    )

    def wait_for_operation(
        client, accepted, token, timeout, interval, clock, sleep, update
    ):
        update(status)
        return status

    monkeypatch.setattr("platform_cli.__main__.PlatformClient", FakeClient)
    monkeypatch.setattr("platform_cli.__main__.wait_for_operation", wait_for_operation)
    declaration = {
        "apiVersion": "platform.eseidinger.de/v1",
        "kind": "Application",
        "metadata": {"name": "orders"},
        "spec": {
            "components": [
                {
                    "name": "web",
                    "type": "service",
                    "runtime": {"type": "container", "image": "example:v1"},
                }
            ]
        },
    }
    args = ["deploy", "apply", "--project", "orders", "--file", "-", "--wait"]

    verbose = CliRunner().invoke(app, args, input=json.dumps(declaration))
    quiet = CliRunner().invoke(app, ["--quiet", *args], input=json.dumps(declaration))

    assert verbose.exit_code == 0, verbose.output
    assert "Operation op-1:" in verbose.stderr
    assert quiet.exit_code == 0, quiet.output
    assert quiet.stderr == ""
    assert "succeeded" in quiet.stdout


def test_existing_deploy_apply_works_with_environment_auth_and_broken_profile(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("DEVPLAT_CONFIG_DIR", str(tmp_path))
    (tmp_path / "profiles.toml").write_text("invalid = [", encoding="utf-8")
    monkeypatch.setenv("PLATFORM_API_URL", "https://platform.example")
    monkeypatch.setenv("PLATFORM_ACCESS_TOKEN", "existing-token")
    seen = []
    declaration = {
        "apiVersion": "platform.eseidinger.de/v1",
        "kind": "Application",
        "metadata": {"name": "orders"},
        "spec": {
            "components": [
                {
                    "name": "web",
                    "type": "service",
                    "runtime": {"type": "container", "image": "example:v1"},
                }
            ]
        },
    }

    def handler(request):
        seen.append(request)
        assert request.method == "PUT"
        assert request.url.path == "/v1/projects/orders/application"
        assert request.headers["authorization"] == "Bearer existing-token"
        assert request.headers["if-match"] == '"2"'
        assert json.loads(request.content) == declaration
        return httpx.Response(
            202,
            json={
                "operation_id": "op-1",
                "state": "queued",
                "revision": 3,
                "status_url": "/v1/operations/op-1",
            },
        )

    transport = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        "platform_cli.__main__.PlatformClient",
        lambda config: PlatformClient(config, transport),
    )
    result = CliRunner().invoke(
        app,
        [
            "deploy",
            "apply",
            "--project",
            "orders",
            "--file",
            "-",
            "--if-match",
            '"2"',
            "--output",
            "json",
        ],
        input=json.dumps(declaration),
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["revision"] == 3
    assert len(seen) == 1
    assert "existing-token" not in result.output


def test_operations_watch_resumes_an_existing_operation(monkeypatch, tmp_path):
    monkeypatch.setenv("DEVPLAT_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("PLATFORM_API_URL", "https://platform.example")
    monkeypatch.setenv("PLATFORM_ACCESS_TOKEN", "existing-token")
    seen = []

    def handler(request):
        seen.append(request)
        assert request.method == "GET"
        assert request.url.path == "/v1/operations/op-1"
        assert request.headers["authorization"] == "Bearer existing-token"
        return httpx.Response(
            200,
            json={
                "operation_id": "op-1",
                "state": "succeeded",
                "revision": 3,
                "readiness": {"state": "ready"},
            },
        )

    transport = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        "platform_cli.__main__.PlatformClient",
        lambda config: PlatformClient(config, transport),
    )
    result = CliRunner().invoke(
        app, ["operations", "watch", "op-1", "--output", "json"]
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["operation_id"] == "op-1"
    assert len(seen) == 2
    assert "existing-token" not in result.output
