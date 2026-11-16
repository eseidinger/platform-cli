#!/usr/bin/env python3
"""Extract the packaged public API contract from a platform OpenAPI export."""

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    source = json.loads(args.source.read_text())
    contract = {key: source[key] for key in ("paths", "components", "openapi")}
    target = Path(__file__).resolve().parents[1] / "src/platform_cli/api_contract.json"
    rendered = json.dumps(contract, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not target.exists() or target.read_text() != rendered:
            parser.exit(
                1, "CLI API contract is stale; regenerate it from the API export.\n"
            )
    else:
        target.write_text(rendered)


if __name__ == "__main__":
    main()
