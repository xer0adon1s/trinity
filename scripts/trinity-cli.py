#!/usr/bin/env python3
"""Thin Click entrypoint so coverage-sim can drive the real CLI without
`python -m trinity` or a uv-installed console script."""

from trinity.cli.main import cli

if __name__ == "__main__":
    cli()
