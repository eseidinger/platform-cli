# Developer Platform CLI

This repository builds and releases the `devplat` command-line client for the
Developer Platform API. The [CLI guide](https://github.com/eseidinger/developer-platform/blob/main/docs/developers/cli.md)
documents commands and authentication.

`devplat` is the command-line client for the Developer Platform API. It supports
CI deployments and project administration, including hosted application access.
Use `devplat --help` and `devplat access --help` to inspect commands.

Install an editable development copy:

```bash
python3 -m pip install -e '.[dev]'
python3 -m pytest tests
devplat contract check --output json
```

Set the values returned when the deployment credential was created. Keep the
secret in the CI system's protected environment and disable shell tracing around
this step:

```bash
export PLATFORM_API_URL=https://platform.example
export PLATFORM_TOKEN_ENDPOINT=\
https://identity.example/realms/platform/protocol/openid-connect/token
export PLATFORM_CLIENT_ID='...'
export PLATFORM_CLIENT_SECRET='...'
devplat deploy apply --project hello --file application.json --wait
```

`PLATFORM_ACCESS_TOKEN` may be used instead of the deployment-credential
variables for a short-lived, externally obtained token. The CLI never persists
either form of authentication material. Deployment credentials authorize
deployment and observation only; access administration requires a human
project-administrator login or an externally supplied administrator token. See
the [CLI guide](https://github.com/eseidinger/developer-platform/blob/main/docs/developers/cli.md)
for profiles, login, access commands, and versioned updates.

## Update the API contract

The checked-in `src/platform_cli/api_contract.json` is extracted from the API's
OpenAPI export in the [developer-platform repository](https://github.com/eseidinger/developer-platform).
After an API contract change, check out both repositories side by side and run:

```bash
python3 scripts/generate-cli-contract.py --source ../developer-platform/docs/api/openapi.json
devplat contract check --output json
python3 -m pytest tests
```

Review and commit the resulting contract change here with any CLI command
updates. A tag `vMAJOR.MINOR.PATCH` must match `pyproject.toml`; the CLI
repository builds, tests, and publishes that version from its own CI workflow.
