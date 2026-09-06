#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Utility to verify Doppler CLI installation, configuration, and secret keys.

Checks whether the Doppler CLI is installed, verifies project configuration,
and confirms the presence of required secret keys without logging or exposing
secret values.

Usage:
    python3 check_doppler.py [--require KEY_NAME ...]
"""

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence


def is_doppler_installed() -> bool:
    """Checks whether the doppler CLI executable is available in PATH.

    Returns:
        True if doppler is discovered in PATH, False otherwise.
    """
    return shutil.which("doppler") is not None


def run_doppler_command(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Executes a doppler CLI command and captures its output safely.

    Args:
        args: Sequence of command arguments following 'doppler'.

    Returns:
        CompletedProcess instance containing stdout, stderr, and returncode.
    """
    cmd = ["doppler", *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )


def check_auth_status() -> bool:
    """Verifies whether the current user is authenticated with Doppler.

    Returns:
        True if authenticated, False otherwise.
    """
    result = run_doppler_command(["me", "--json"])
    return result.returncode == 0


def get_project_config() -> Mapping[str, str]:
    """Retrieves current project and environment config bindings.

    Returns:
        Mapping containing configuration keys such as 'project' and 'config'.
    """
    result = run_doppler_command(["configure", "get", "--json"])
    if result.returncode != 0:
        return {}
    try:
        data = json.loads(result.stdout)
        if isinstance(data, dict):
            return {
                str(k): str(v)
                for k, v in data.items()
                if isinstance(k, str) and isinstance(v, (str, int, bool))
            }
    except json.JSONDecodeError:
        pass
    return {}


def list_secret_keys() -> Sequence[str]:
    """Lists the names of available secrets without exposing values.

    Returns:
        Sequence of secret name strings.
    """
    result = run_doppler_command(["secrets", "--names", "--json"])
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout)
        if isinstance(data, list):
            return [str(item) for item in data]
    except json.JSONDecodeError:
        pass
    return []


def verify_setup(
    required_keys: Sequence[str] | None = None,
) -> tuple[bool, Sequence[str]]:
    """Runs verification checks and returns status and informational messages.

    Args:
        required_keys: Optional sequence of secret names that must exist.

    Returns:
        Tuple of (passed_boolean, messages_sequence).
    """
    messages: list[str] = []

    if not is_doppler_installed():
        messages.append("ERROR: 'doppler' CLI is not installed or not in PATH.")
        return False, messages

    messages.append("OK: 'doppler' CLI executable found.")

    if not check_auth_status():
        messages.append("WARNING: Doppler CLI is not logged in. Run 'doppler login'.")
        return False, messages

    messages.append("OK: Doppler CLI authenticated.")

    config = get_project_config()
    project = config.get("project")
    env_config = config.get("config")
    if not project or not env_config:
        messages.append("WARNING: No project/config configured. Run 'doppler setup'.")
        return False, messages

    messages.append(f"OK: Configured for project '{project}', config '{env_config}'.")

    if required_keys:
        available_keys = set(list_secret_keys())
        missing_keys = [k for k in required_keys if k not in available_keys]
        if missing_keys:
            messages.append(
                f"ERROR: Missing required secrets: {', '.join(missing_keys)}"
            )
            return False, messages
        messages.append(
            f"OK: All {len(required_keys)} required secret key(s) are present."
        )

    return True, messages


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for Doppler setup verification.

    Args:
        argv: Optional command line argument sequence.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    parser = argparse.ArgumentParser(
        description="Verify Doppler installation, authentication, and secrets."
    )
    parser.add_argument(
        "--require",
        action="append",
        dest="required_keys",
        default=[],
        help="Secret key name required to be present (can be repeated).",
    )
    args = parser.parse_args(argv)

    passed, messages = verify_setup(required_keys=args.required_keys)
    for msg in messages:
        print(msg)

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
